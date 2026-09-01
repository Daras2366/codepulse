"""Goal progress calculator.

Computes real-time progress for each of the six goal types using live
database data.  This is the single source of truth for all goal progress
values — the frontend never calculates progress independently.

Architecture
------------
GoalService
    → GoalProgressCalculator       (this module)
        → GoalProgressRepository   (SQL queries)
        → Goal model fields        (start_date, deadline, platform, …)

Pace Calculation
----------------
For goals with both start_date and deadline, we calculate whether the
user is "ahead", "on_track", or "behind" based on:

    expected_pct = elapsed_days / total_days * 100
    actual_pct   = current_value / target_value * 100

    ahead    : actual_pct > expected_pct + 10
    on_track : |actual_pct - expected_pct| <= 10
    behind   : actual_pct < expected_pct - 10

Note: RATING goals do not use linear pace since rating changes are not
linear. They show "ahead"/"behind" relative to a simple linear model
but this should be taken as directional only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from app.models.enums import GoalStatus, GoalType
from app.repositories.goal_progress_repository import GoalProgressRepository

if TYPE_CHECKING:
    from app.models.goal import Goal


@dataclass
class GoalProgressResult:
    """All computed progress fields for a single goal."""

    goal_id: int
    current_value: int
    target_value: int
    progress_percentage: float
    remaining: int
    days_remaining: Optional[int]
    is_overdue: bool
    is_completed: bool
    status: GoalStatus
    pace: str  # "ahead" | "on_track" | "behind" | "completed" | "overdue" | "no_deadline"
    completed_at: Optional[datetime]


class GoalProgressCalculator:
    """Calculate real-time progress for any goal type."""

    def __init__(self, db: Session) -> None:
        self._repo = GoalProgressRepository(db)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate(self, goal: "Goal") -> GoalProgressResult:
        """Compute progress for a single goal and return a GoalProgressResult."""
        current_value = self._get_current_value(goal)
        today = date.today()
        deadline = goal.deadline
        target = goal.target_value

        # ----------------------------------------------------------------
        # Progress percentage
        # ----------------------------------------------------------------
        if target <= 0:
            progress_pct = 0.0
        else:
            progress_pct = round(min(current_value / target * 100, 100.0), 1)

        remaining = max(0, target - current_value)

        # ----------------------------------------------------------------
        # Days remaining
        # ----------------------------------------------------------------
        if deadline is not None:
            days_remaining = (deadline - today).days
        else:
            days_remaining = None

        # ----------------------------------------------------------------
        # Completion / overdue detection
        # ----------------------------------------------------------------
        is_completed = current_value >= target
        is_overdue = (
            not is_completed
            and deadline is not None
            and today > deadline
        )

        # ----------------------------------------------------------------
        # Status update
        # ----------------------------------------------------------------
        if is_completed:
            new_status = GoalStatus.COMPLETED
        elif is_overdue:
            new_status = GoalStatus.OVERDUE
        elif goal.status == GoalStatus.PAUSED:
            new_status = GoalStatus.PAUSED
        else:
            new_status = GoalStatus.ACTIVE

        # Preserve the original completed_at or set it now
        completed_at = goal.completed_at
        if is_completed and completed_at is None:
            completed_at = datetime.now(tz=timezone.utc)

        # ----------------------------------------------------------------
        # Pace
        # ----------------------------------------------------------------
        pace = self._compute_pace(
            goal=goal,
            current_value=current_value,
            is_completed=is_completed,
            is_overdue=is_overdue,
            today=today,
        )

        return GoalProgressResult(
            goal_id=goal.id,
            current_value=current_value,
            target_value=target,
            progress_percentage=progress_pct,
            remaining=remaining,
            days_remaining=days_remaining,
            is_overdue=is_overdue,
            is_completed=is_completed,
            status=new_status,
            pace=pace,
            completed_at=completed_at,
        )

    # ------------------------------------------------------------------
    # Per-type current value calculation
    # ------------------------------------------------------------------

    def _get_current_value(self, goal: "Goal") -> int:
        t = goal.goal_type
        if t == GoalType.RATING:
            return self._calc_rating(goal)
        if t == GoalType.PROBLEMS:
            return self._calc_problems(goal)
        if t == GoalType.TOPIC:
            return self._calc_topic(goal)
        if t == GoalType.CONSISTENCY:
            return self._calc_consistency(goal)
        if t == GoalType.CONTEST:
            return self._calc_contest(goal)
        if t == GoalType.PLACEMENT:
            return self._calc_placement(goal)
        return 0

    # ---- RATING ----

    def _calc_rating(self, goal: "Goal") -> int:
        """Return current rating from PlatformProfile.current_rating."""
        if goal.platform is None:
            return 0
        return self._repo.get_rating_for_platform(goal.user_id, goal.platform)

    # ---- PROBLEMS ----

    def _calc_problems(self, goal: "Goal") -> int:
        """Count distinct accepted problems in the goal's date window."""
        return self._repo.get_problems_solved_in_range(
            user_id=goal.user_id,
            start_date=goal.start_date,
            end_date=goal.deadline,
            platform=goal.platform,
            difficulty=goal.difficulty_filter,
        )

    # ---- TOPIC ----

    def _calc_topic(self, goal: "Goal") -> int:
        """Return topic-specific solved count.

        LeetCode: uses PlatformTopicStat (profile-level cumulative count).
                  Progress is calculated as (current_count - start_value) to exclude
                  problems solved before the goal was created.
        Codeforces: uses ProblemTopic join, filtered by goal date range.
        """
        if goal.topic_slug is None:
            return 0

        platform = goal.platform
        if platform == "leetcode":
            current_count = self._repo.get_topic_solved_count_leetcode(
                user_id=goal.user_id,
                topic_slug=goal.topic_slug,
            )
            # Calculate progress from the baseline (start_value)
            return max(0, current_count - goal.start_value)
        elif platform == "codeforces":
            return self._repo.get_topic_solved_count_codeforces(
                user_id=goal.user_id,
                topic_slug=goal.topic_slug,
                start_date=goal.start_date,
                end_date=goal.deadline,
            )
        else:
            # Cross-platform: LeetCode uses baseline, CF uses date filtering
            lc_current = self._repo.get_topic_solved_count_leetcode(
                user_id=goal.user_id,
                topic_slug=goal.topic_slug,
            )
            lc_progress = max(0, lc_current - goal.start_value)
            
            cf = self._repo.get_topic_solved_count_codeforces(
                user_id=goal.user_id,
                topic_slug=goal.topic_slug,
                start_date=goal.start_date,
                end_date=goal.deadline,
            )
            return lc_progress + cf

    # ---- CONSISTENCY ----

    def _calc_consistency(self, goal: "Goal") -> int:
        """Count distinct active coding days in the goal's date window."""
        return self._repo.get_active_days_in_range(
            user_id=goal.user_id,
            start_date=goal.start_date,
            end_date=goal.deadline,
            platform=goal.platform,
        )

    # ---- CONTEST ----

    def _calc_contest(self, goal: "Goal") -> int:
        """Count contests participated in within the goal's date window."""
        return self._repo.get_contests_in_range(
            user_id=goal.user_id,
            start_date=goal.start_date,
            end_date=goal.deadline,
            platform=goal.platform,
        )

    # ---- PLACEMENT ----

    def _calc_placement(self, goal: "Goal") -> int:
        """Placement = accepted problems with optional difficulty filter."""
        return self._repo.get_problems_solved_in_range(
            user_id=goal.user_id,
            start_date=goal.start_date,
            end_date=goal.deadline,
            platform=goal.platform,
            difficulty=goal.difficulty_filter,
        )

    # ------------------------------------------------------------------
    # Pace helper
    # ------------------------------------------------------------------

    def _compute_pace(
        self,
        goal: "Goal",
        current_value: int,
        is_completed: bool,
        is_overdue: bool,
        today: date,
    ) -> str:
        if is_completed:
            return "completed"
        if is_overdue:
            return "overdue"

        # RATING goals: simple ahead/behind vs target (no linear timeline)
        if goal.goal_type == GoalType.RATING:
            if goal.target_value <= 0:
                return "no_deadline"
            start_val = goal.start_value or 0
            denominator = goal.target_value - start_val
            if denominator <= 0:
                return "on_track"
            pct = (current_value - start_val) / denominator * 100
            if pct >= 100:
                return "completed"
            if goal.deadline is None:
                return "on_track"
            total_days = (goal.deadline - (goal.start_date or goal.created_at.date())).days
            elapsed = (today - (goal.start_date or goal.created_at.date())).days
            if total_days <= 0:
                return "on_track"
            expected_pct = elapsed / total_days * 100
            return self._pace_label(pct, expected_pct)

        # Other types with a deadline
        if goal.deadline is None or goal.start_date is None:
            return "no_deadline"

        total_days = (goal.deadline - goal.start_date).days
        elapsed = (today - goal.start_date).days

        if total_days <= 0:
            return "on_track"

        expected_pct = elapsed / total_days * 100
        actual_pct = (
            current_value / goal.target_value * 100
            if goal.target_value > 0
            else 0.0
        )
        return self._pace_label(actual_pct, expected_pct)

    @staticmethod
    def _pace_label(actual_pct: float, expected_pct: float) -> str:
        diff = actual_pct - expected_pct
        if diff > 10:
            return "ahead"
        if diff < -10:
            return "behind"
        return "on_track"
