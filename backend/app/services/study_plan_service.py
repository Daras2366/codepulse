"""Study Plan Service.

Builds a personalized daily study plan entirely from real, persisted user
data:

    PerformanceAnalyzer → focus topic → unsolved Problem records → plan

No value shown to the user is invented:
- Problems are real ``Problem`` rows the user has NOT solved (verified
  against ACCEPTED submissions).
- The daily target is derived only from an active user-configured goal with
  a deadline; when no such goal exists ``daily_target`` is ``None`` and the
  UI prompts the user to create one.
- The upcoming contest is the next ``Contest`` row whose ``start_time`` is
  strictly in the future.
- Session duration is an explicit, labelled estimate.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, time, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.contest import Contest
from app.models.enums import GoalStatus, GoalType, SubmissionStatus
from app.models.goal import Goal
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
from app.schemas.study_plan import (
    StudyPlanContest,
    StudyPlanDailyTarget,
    StudyPlanProblem,
    StudyPlanResponse,
)
from app.services.agent_tools import get_solved_problem_ids
from app.services.goal_progress_calculator import GoalProgressCalculator
from app.services.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)

# Explicit, documented estimation rule: rough minutes per problem by
# difficulty. Surfaced to the UI as a labelled estimate, never as fact.
ESTIMATED_MINUTES_BY_DIFFICULTY = {
    "Easy": 15,
    "Medium": 25,
    "Hard": 40,
}
DEFAULT_ESTIMATED_MINUTES = 25
PLAN_SIZE = 5
_CANDIDATE_POOL = 100

# Goal types whose target_value counts *problems* — the only goals that can
# ground a daily "problems per day" target.
_PROBLEM_GOAL_TYPES = {GoalType.PROBLEMS, GoalType.TOPIC, GoalType.PLACEMENT}


def resolve_timezone(tz_name: Optional[str]) -> tuple[ZoneInfo, str]:
    """Resolve an IANA timezone name, falling back to UTC when invalid."""
    if tz_name:
        try:
            return ZoneInfo(tz_name), tz_name
        except (ZoneInfoNotFoundError, ValueError):
            logger.warning("study_plan: invalid timezone %r — using UTC", tz_name)
    return ZoneInfo("UTC"), "UTC"


class StudyPlanService:
    """Builds the daily study plan for an authenticated user."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_plan(self, user_id: int, tz_name: Optional[str] = None) -> StudyPlanResponse:
        profile = PerformanceAnalyzer(self._db).analyze_user_performance(user_id)
        tz, tz_label = resolve_timezone(tz_name)

        has_sufficient = (
            profile.overview.solved_problems > 0
            or profile.submission_behavior.total_submissions > 0
        )

        focus_topic, focus_reason, focus_source = self._choose_focus(profile, user_id)
        daily = self._build_daily_target(user_id, tz, tz_label)
        contest = self._next_upcoming_contest()
        limitations: list[str] = []

        problems: list[StudyPlanProblem] = []
        total_minutes = 0
        catalog_size = self._db.query(func.count(Problem.id)).scalar() or 0

        if has_sufficient:
            problems = self._select_problems(profile, focus_topic, user_id)
            total_minutes = sum(p.estimated_minutes for p in problems)
            if not problems:
                limitations.append(
                    "No unsolved problems matching your focus area were found in "
                    "the local catalog. Sync more submissions to expand it."
                )
            if catalog_size == 0:
                limitations.append(
                    "The problem catalog is empty — sync a platform to populate it."
                )
        else:
            limitations.append(
                "Not enough practice data yet. Sync a platform and solve some "
                "problems to generate a personalized plan."
            )

        return StudyPlanResponse(
            has_sufficient_data=has_sufficient,
            focus_topic=focus_topic,
            focus_reason=focus_reason,
            problems=problems,
            problems_planned=len(problems),
            total_estimated_minutes=total_minutes,
            estimate_note=(
                "Estimated duration assumes roughly "
                + "/".join(
                    f"{v} min for {k}" for k, v in ESTIMATED_MINUTES_BY_DIFFICULTY.items()
                )
                + " problems."
            ),
            daily=daily,
            upcoming_contest=contest,
            catalog_size=catalog_size,
            limitations=limitations,
        )

    # ------------------------------------------------------------------
    # Focus topic
    # ------------------------------------------------------------------

    def _choose_focus(self, profile, user_id: int) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Pick the plan's focus area.

        Priority:
        1. An active TOPIC goal (user-configured intent).
        2. The weakest topic from PerformanceAnalyzer (evidence-based).
        3. None — insufficient data.
        """
        goal_topic = self._active_topic_goal(user_id)
        if goal_topic:
            return (
                goal_topic,
                "Aligned with your active topic goal.",
                "goal",
            )

        weak = [t for t in profile.topic_performance if t.strength_level == "weak"]
        if weak:
            # Most neglected weak topic = fewest solved among weak topics.
            topic = min(weak, key=lambda t: t.solved_count)
            return (
                topic.topic,
                (
                    f"Weakest area in your profile ({topic.solved_count} solved, "
                    f"{topic.percentage:.1f}% of tagged problems)."
                ),
                "performance",
            )

        moderate_neglected = [
            t
            for t in profile.topic_performance
            if t.strength_level == "moderate" and t.recent_activity == 0
        ]
        if moderate_neglected:
            topic = min(moderate_neglected, key=lambda t: t.recent_activity)
            return (
                topic.topic,
                "Moderate topic with no practice in the last 30 days — good refresher.",
                "performance",
            )

        return None, None, None

    def _active_topic_goal(self, user_id: int) -> Optional[str]:
        goal = (
            self._db.query(Goal)
            .filter(
                Goal.user_id == user_id,
                Goal.status == GoalStatus.ACTIVE,
                Goal.goal_type == GoalType.TOPIC,
                Goal.topic_name.isnot(None),
            )
            .order_by(Goal.deadline.asc().nullslast(), Goal.created_at.desc())
            .first()
        )
        return goal.topic_name if goal else None

    # ------------------------------------------------------------------
    # Problem selection
    # ------------------------------------------------------------------

    def _preferred_difficulties(self, profile) -> list[str]:
        """Ordered difficulty preference derived from the performance profile."""
        solved = profile.overview.solved_problems
        ar = profile.submission_behavior.acceptance_rate
        if solved < 20:
            return ["Easy", "Medium"]
        if ar is not None and ar > 0.7:
            return ["Medium", "Easy", "Hard"]
        return ["Medium", "Easy"]

    def _select_problems(
        self, profile, focus_topic: Optional[str], user_id: int
    ) -> list[StudyPlanProblem]:
        solved_ids = get_solved_problem_ids(self._db, user_id)
        preferred = self._preferred_difficulties(profile)
        diff_rank = {d: i for i, d in enumerate(preferred)}

        query = self._db.query(Problem).filter(
            Problem.id.notin_(solved_ids) if solved_ids else True
        )

        candidates = (
            query.order_by(
                Problem.acceptance_rate.desc().nullslast(),
                Problem.id.asc(),
            )
            .limit(_CANDIDATE_POOL)
            .all()
        )
        if not candidates:
            return []

        # Batch-load topic names for all candidates.
        candidate_ids = [p.id for p in candidates]
        topic_rows = (
            self._db.query(ProblemTopic.problem_id, Topic.name)
            .join(Topic, Topic.id == ProblemTopic.topic_id)
            .filter(ProblemTopic.problem_id.in_(candidate_ids))
            .all()
        )
        topics_by_problem: dict[int, list[str]] = {}
        for pid, name in topic_rows:
            topics_by_problem.setdefault(pid, []).append(name)

        focus_lower = focus_topic.lower() if focus_topic else None

        def difficulty_value(prob: Problem) -> str:
            d = prob.difficulty
            return d.value if hasattr(d, "value") else str(d or "")

        def platform_value(prob: Problem) -> str:
            p = prob.platform
            return p.value if hasattr(p, "value") else str(p or "")

        def score(prob: Problem) -> tuple:
            topics = topics_by_problem.get(prob.id, [])
            topic_match = bool(
                focus_lower
                and any(focus_lower in t.lower() or t.lower() in focus_lower for t in topics)
            )
            return (
                0 if topic_match else 1,
                diff_rank.get(difficulty_value(prob), len(preferred)),
                -(prob.acceptance_rate or 0.0),
                prob.id,
            )

        ranked = sorted(candidates, key=score)
        selected = ranked[:PLAN_SIZE]

        return [
            StudyPlanProblem(
                id=p.id,
                title=p.title,
                platform=platform_value(p),
                difficulty=difficulty_value(p) or None,
                url=p.problem_url,
                topics=topics_by_problem.get(p.id, []),
                estimated_minutes=ESTIMATED_MINUTES_BY_DIFFICULTY.get(
                    difficulty_value(p), DEFAULT_ESTIMATED_MINUTES
                ),
                acceptance_rate=p.acceptance_rate,
            )
            for p in selected
        ]

    # ------------------------------------------------------------------
    # Daily progress & target
    # ------------------------------------------------------------------

    def _local_day_window_utc(self, tz: ZoneInfo) -> tuple[datetime, datetime]:
        """Return [start, end) UTC bounds of the user's local calendar day."""
        now_local = datetime.now(tz)
        start_local = datetime.combine(now_local.date(), time.min, tzinfo=tz)
        end_local = start_local + timedelta(days=1)
        return (
            start_local.astimezone(timezone.utc),
            end_local.astimezone(timezone.utc),
        )

    def _count_solved_today(
        self, user_id: int, start_utc: datetime, end_utc: datetime
    ) -> int:
        """Distinct problems with an ACCEPTED submission in the local day."""
        return (
            self._db.query(func.count(func.distinct(Submission.problem_id)))
            .filter(
                Submission.profile_id.in_(
                    self._db.query(PlatformProfile.id)
                    .filter(PlatformProfile.user_id == user_id)
                ),
                Submission.status == SubmissionStatus.ACCEPTED,
                Submission.submitted_at >= start_utc,
                Submission.submitted_at < end_utc,
            )
            .scalar()
            or 0
        )

    def _build_daily_target(
        self, user_id: int, tz: ZoneInfo, tz_label: str
    ) -> StudyPlanDailyTarget:
        start_utc, end_utc = self._local_day_window_utc(tz)
        solved_today = self._count_solved_today(user_id, start_utc, end_utc)

        target, label, source = self._derive_daily_target_from_goals(user_id)

        return StudyPlanDailyTarget(
            solved_today=solved_today,
            daily_target=target,
            target_label=label,
            target_source=source,
            timezone=tz_label,
        )

    def _derive_daily_target_from_goals(
        self, user_id: int
    ) -> tuple[Optional[int], Optional[str], Optional[str]]:
        """Derive a daily problem target from the nearest-deadline active
        problem-count goal. Returns (target, label, source) — all None when no
        suitable goal exists (never invent a default)."""
        goals = (
            self._db.query(Goal)
            .filter(
                Goal.user_id == user_id,
                Goal.status == GoalStatus.ACTIVE,
                Goal.goal_type.in_(_PROBLEM_GOAL_TYPES),
                Goal.deadline.isnot(None),
            )
            .order_by(Goal.deadline.asc())
            .all()
        )
        if not goals:
            return None, None, None

        calculator = GoalProgressCalculator(self._db)
        today = datetime.now(timezone.utc).date()

        best: tuple[int, str, int] | None = None  # (days_remaining, title, target)
        for goal in goals:
            result = calculator.calculate(goal)
            if result.is_completed or result.remaining <= 0:
                continue
            if result.days_remaining is None or result.days_remaining <= 0:
                continue
            daily = math.ceil(result.remaining / result.days_remaining)
            candidate = (result.days_remaining, goal.title, daily)
            if best is None or candidate[0] < best[0]:
                best = candidate

        if best is None:
            return None, None, None

        days_remaining, title, daily = best
        return (
            daily,
            f"{daily} problems/day to reach \"{title}\" ({days_remaining} days left)",
            "goal",
        )

    # ------------------------------------------------------------------
    # Upcoming contest
    # ------------------------------------------------------------------

    def _as_aware_utc(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def upcoming_contests(self, limit: int = 5) -> list[StudyPlanContest]:
        """Return upcoming contests (start_time strictly in the future)."""
        now = datetime.now(timezone.utc)
        rows = (
            self._db.query(Contest)
            .order_by(Contest.start_time.asc())
            .all()
        )
        upcoming = [
            c for c in rows if self._as_aware_utc(c.start_time) > now
        ][:limit]
        return [self._to_contest_schema(c) for c in upcoming]

    def _next_upcoming_contest(self) -> Optional[StudyPlanContest]:
        contests = self.upcoming_contests(limit=1)
        return contests[0] if contests else None

    def _to_contest_schema(self, c: Contest) -> StudyPlanContest:
        platform = c.platform
        platform_val = platform.value if hasattr(platform, "value") else str(platform)
        return StudyPlanContest(
            id=c.id,
            title=c.title,
            platform=platform_val,
            contest_url=c.contest_url,
            start_time=self._as_aware_utc(c.start_time),
            duration_minutes=c.duration_minutes,
        )
