"""Agent tool implementations for the AI recommendation agent.

Each function is a pure Python function that the agent loop calls.
All DB queries are scoped by user_id. No cross-user data leakage.

Security contract:
  - user_id is ALWAYS passed from the authenticated session, never from model output.
  - All queries include a user_id filter to prevent cross-user data leakage.
  - No live external API calls are made here (testable in isolation).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, distinct, select
from sqlalchemy.orm import Session

from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.enums import Difficulty as DifficultyEnum
from app.models.enums import Platform as PlatformEnum
from app.models.enums import SubmissionStatus
from app.models.goal import Goal
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
from app.services.candidate_ranker import (
    CANDIDATE_POOL_LIMIT,
    allowed_difficulty_band,
    build_user_context,
    score_candidate,
    select_diverse,
)
from app.services.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def get_solved_problem_ids(db: Session, user_id: int) -> set[int]:
    """Return the set of problem IDs that the authenticated user has ACCEPTED.

    Used internally by search_candidate_problems and get_problem_details to
    determine which problems the user has already solved.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID (never from model output).

    Returns:
        Set of problem IDs with at least one ACCEPTED submission.
    """
    # Get all profile IDs that belong to this user
    profile_ids = select(PlatformProfile.id).where(
        PlatformProfile.user_id == user_id
    )

    rows = (
        db.query(distinct(Submission.problem_id))
        .filter(
            Submission.profile_id.in_(profile_ids),
            Submission.status == SubmissionStatus.ACCEPTED,
        )
        .all()
    )
    return {row[0] for row in rows}


def _get_attempted_problem_ids(db: Session, user_id: int) -> set[int]:
    """Return problem IDs that this user has ANY submission for (attempted, not necessarily solved).

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID.

    Returns:
        Set of problem IDs the user has ever attempted.
    """
    profile_ids = select(PlatformProfile.id).where(
        PlatformProfile.user_id == user_id
    )

    rows = (
        db.query(distinct(Submission.problem_id))
        .filter(Submission.profile_id.in_(profile_ids))
        .all()
    )
    return {row[0] for row in rows}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """Normalise a datetime to aware-UTC (SQLite may return naive values)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def get_user_performance_profile(db: Session, user_id: int) -> dict:
    """Get the authenticated user's performance profile.

    Returns a compact JSON-serializable dict summarising solved counts,
    streaks, acceptance rate, and per-platform ratings.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID.

    Returns:
        Dict with keys: solved_problems, total_submissions, active_days,
        current_streak_days, longest_streak_days, acceptance_rate,
        ratings_by_platform, data_quality, and optionally note.
    """
    analyzer = PerformanceAnalyzer(db)
    profile = analyzer.analyze_user_performance(user_id)

    overview = profile.overview
    behavior = profile.submission_behavior
    dq = profile.data_quality

    ratings = [
        {
            "platform": pr.platform,
            "current_rating": pr.current_rating,
            "max_rating": pr.max_rating,
        }
        for pr in overview.ratings_by_platform
    ]

    result: dict = {
        "solved_problems": overview.solved_problems,
        "total_submissions": behavior.total_submissions,
        "active_days": overview.active_days,
        "current_streak_days": behavior.current_streak_days,
        "longest_streak_days": behavior.longest_streak_days,
        "acceptance_rate": behavior.acceptance_rate,
        "ratings_by_platform": ratings,
        "data_quality": {
            "has_topic_data": dq.has_topic_data,
            "has_submission_data": dq.has_submission_data,
            "has_contest_data": dq.has_contest_data,
            "profile_reported_solved": dq.profile_reported_solved,
            "locally_tagged_solved": dq.locally_tagged_solved,
        },
    }

    if len(ratings) > 1:
        result["note"] = (
            "LeetCode and Codeforces ratings use different scales — do not compare them."
        )

    return result


def get_topic_performance(db: Session, user_id: int) -> list[dict]:
    """Return per-topic performance for the authenticated user.

    Returns up to 20 topics sorted by solved_count descending.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID.

    Returns:
        List of dicts with keys: topic, solved_count, strength_level,
        recent_activity_30d.
    """
    analyzer = PerformanceAnalyzer(db)
    profile = analyzer.analyze_user_performance(user_id)

    topics = profile.topic_performance[:20]

    return [
        {
            "topic": t.topic,
            "solved_count": t.solved_count,
            "strength_level": t.strength_level,
            "recent_activity_30d": t.recent_activity,
        }
        for t in topics
    ]


def get_recent_submissions(
    db: Session, user_id: int, limit: int = 20
) -> list[dict]:
    """Return the most recent submissions for the authenticated user.

    Joins Submission → Problem through the user's platform profiles so only
    this user's data is returned.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID.
        limit: Maximum number of submissions to return (default 20).

    Returns:
        List of dicts with keys: problem_title, platform, difficulty,
        status, submitted_at (ISO string). Ordered most-recent first.
    """
    limit = max(1, min(limit, 50))

    profile_ids_subq = select(PlatformProfile.id).where(
        PlatformProfile.user_id == user_id
    )

    rows = (
        db.query(
            Problem.title.label("problem_title"),
            Problem.platform.label("platform"),
            Problem.difficulty.label("difficulty"),
            Submission.status.label("status"),
            Submission.submitted_at.label("submitted_at"),
        )
        .join(Problem, Problem.id == Submission.problem_id)
        .filter(Submission.profile_id.in_(profile_ids_subq))
        .order_by(Submission.submitted_at.desc())
        .limit(limit)
        .all()
    )

    result = []
    for row in rows:
        submitted_at = row.submitted_at
        if submitted_at is not None:
            if hasattr(submitted_at, "isoformat"):
                submitted_at_str = submitted_at.isoformat()
            else:
                submitted_at_str = str(submitted_at)
        else:
            submitted_at_str = None

        difficulty = row.difficulty
        if difficulty is not None and hasattr(difficulty, "value"):
            difficulty = difficulty.value

        platform = row.platform
        if platform is not None and hasattr(platform, "value"):
            platform = platform.value

        status = row.status
        if status is not None and hasattr(status, "value"):
            status = status.value

        result.append(
            {
                "problem_title": row.problem_title,
                "platform": platform,
                "difficulty": difficulty,
                "status": status,
                "submitted_at": submitted_at_str,
            }
        )

    return result


def get_user_goals(db: Session, user_id: int) -> list[dict]:
    """Return the authenticated user's goals (active and completed).

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID.

    Returns:
        List of dicts with keys: title, goal_type, platform, topic_name,
        difficulty_filter, target_value, current_value, status, deadline.
    """
    goals = (
        db.query(Goal)
        .filter(Goal.user_id == user_id)
        .order_by(Goal.created_at.desc())
        .all()
    )

    result = []
    for goal in goals:
        deadline = goal.deadline
        if deadline is not None and hasattr(deadline, "isoformat"):
            deadline_str = deadline.isoformat()
        elif deadline is not None:
            deadline_str = str(deadline)
        else:
            deadline_str = None

        goal_type = goal.goal_type
        if hasattr(goal_type, "value"):
            goal_type = goal_type.value

        status = goal.status
        if hasattr(status, "value"):
            status = status.value

        result.append(
            {
                "title": goal.title,
                "goal_type": goal_type,
                "platform": goal.platform,
                "topic_name": goal.topic_name,
                "difficulty_filter": goal.difficulty_filter,
                "target_value": goal.target_value,
                "current_value": goal.current_value,
                "status": status,
                "deadline": deadline_str,
            }
        )

    return result


def search_candidate_problems(
    db: Session,
    user_id: int,
    topic: Optional[str] = None,
    difficulty: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """Search for problems the authenticated user has NOT yet solved.

    Strategy:
    1. Find all problem IDs the user has ACCEPTED submissions for.
    2. Query the Problem table for problems NOT in that set.
    3. Apply platform filter; apply the caller's difficulty filter, or —
       when none is passed — default to the user's difficulty band derived
       from their solved count (<20 → Easy, 20-99 → Easy+Medium,
       100+ → all).
    4. Score every candidate with candidate_ranker (weak-topic fit,
       difficulty fit, staleness, solvability, recent-failure penalty) and
       select the shortlist with a greedy per-topic diversity penalty.
    5. When ``topic`` is given, topic-matching problems are selected first;
       any remaining slots are topped up with the next-best-scored
       candidates overall — never with unfiltered-by-score results.
    6. Annotate with unsolved_confidence: "confirmed" if never attempted,
       "probable" if attempted but not accepted.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID (never from model output).
        topic: Optional topic name preference (e.g. "Dynamic Programming").
               Matching problems rank first; non-matching problems may fill
               remaining slots when the catalog has too few matches.
        difficulty: Optional difficulty filter ("Easy"/"Medium"/"Hard" or
               Codeforces rating 1-5). When omitted, the user's difficulty
               band is applied automatically.
        platform: Optional platform filter ("leetcode"/"codeforces").
        limit: Max problems to return (1-20).

    Returns:
        Dict with key "problems" (list of problem dicts, each with "score"
        and "score_breakdown") and optional "catalog_limited" flag if fewer
        than 5 candidates were found.
    """
    # Validate inputs
    valid_difficulties = {
        "Easy", "Medium", "Hard", "1", "2", "3", "4", "5",
        "easy", "medium", "hard",
    }
    if difficulty is not None and difficulty not in valid_difficulties:
        return {
            "error": f"Invalid difficulty '{difficulty}'. Must be one of: Easy, Medium, Hard, or 1-5.",
            "problems": [],
        }

    valid_platforms = {"leetcode", "codeforces"}
    if platform is not None and platform.lower() not in valid_platforms:
        return {
            "error": f"Invalid platform '{platform}'. Must be 'leetcode' or 'codeforces'.",
            "problems": [],
        }

    limit = max(1, min(limit, 20))

    # Normalize inputs
    if difficulty is not None:
        difficulty = difficulty.capitalize() if difficulty.isalpha() else difficulty
    if platform is not None:
        platform = platform.lower()

    # Get the set of solved problem IDs for this user (never from model)
    solved_ids = get_solved_problem_ids(db, user_id)
    # Get all attempted problem IDs (for confidence scoring)
    attempted_ids = _get_attempted_problem_ids(db, user_id)
    # Attempted but not solved = only-attempted
    only_attempted_ids = attempted_ids - solved_ids

    # Build the per-user ranking context (topic weakness, staleness,
    # recent failures). All queries inside are scoped by user_id.
    rank_ctx = build_user_context(db, user_id, solved_ids, only_attempted_ids)

    # Build base query for unsolved problems
    query = db.query(Problem).filter(
        Problem.id.notin_(solved_ids) if solved_ids else True
    )

    # Apply platform filter
    if platform is not None:
        query = query.filter(Problem.platform == PlatformEnum(platform))

    # Apply difficulty filter: explicit caller choice wins; otherwise default
    # to the user's solved-count band so beginners are not handed Hard
    # problems (and intermediates are not handed only Easy ones).
    explicit_difficulty = difficulty is not None
    if explicit_difficulty:
        # Map numeric ratings to difficulty levels for Codeforces
        difficulty_map = {
            "1": DifficultyEnum.EASY,
            "2": DifficultyEnum.EASY,
            "3": DifficultyEnum.MEDIUM,
            "4": DifficultyEnum.MEDIUM,
            "5": DifficultyEnum.HARD,
        }
        if difficulty in difficulty_map:
            query = query.filter(Problem.difficulty == difficulty_map[difficulty])
        else:
            try:
                query = query.filter(Problem.difficulty == DifficultyEnum(difficulty))
            except ValueError:
                pass
    else:
        band = allowed_difficulty_band(len(solved_ids))
        query = query.filter(Problem.difficulty.in_(band))

    # Fetch the scoring pool. The topic filter is deliberately NOT applied
    # in SQL: matching is decided in Python so non-matching candidates can
    # still fill leftover slots by score (see selection below).
    problems_raw = (
        query.order_by(Problem.id)
        .limit(CANDIDATE_POOL_LIMIT)
        .all()
    )

    # Batch-fetch topics for the whole pool (one query, no N+1).
    pool_ids = [p.id for p in problems_raw]
    topic_rows = (
        db.query(ProblemTopic.problem_id, Topic.name)
        .join(Topic, Topic.id == ProblemTopic.topic_id)
        .filter(ProblemTopic.problem_id.in_(pool_ids))
        .all()
        if pool_ids
        else []
    )
    topics_by_problem: dict[int, list[str]] = {}
    for problem_id, topic_name in topic_rows:
        topics_by_problem.setdefault(problem_id, []).append(topic_name)

    # Score every candidate in the pool.
    scored = []
    for prob in problems_raw:
        diff_enum = prob.difficulty
        if not isinstance(diff_enum, DifficultyEnum):
            try:
                diff_enum = DifficultyEnum(diff_enum) if diff_enum else None
            except ValueError:
                diff_enum = None

        scored.append(
            score_candidate(
                problem_id=prob.id,
                topics=topics_by_problem.get(prob.id, []),
                difficulty=diff_enum,
                acceptance_rate=prob.acceptance_rate,
                ctx=rank_ctx,
                explicit_difficulty=explicit_difficulty,
            )
        )

    # Split into topic-matching and other candidates when a topic was
    # requested. Matching uses the same case-insensitive substring rule the
    # old SQL ilike filter used.
    topic_lower = topic.strip().lower() if topic is not None else None

    def _matches(cand) -> bool:
        if topic_lower is None:
            return True
        return any(topic_lower in t.lower() for t in cand.topics)

    if topic is not None:
        matching = [c for c in scored if _matches(c)]
        others = [c for c in scored if not _matches(c)]
        selected, counts = select_diverse(matching, limit)
        if len(selected) < limit:
            # Top up with the next-best-SCORED candidates (diversity-aware,
            # carrying over the topic counts from the first pass) — never
            # with unfiltered results.
            extra, _ = select_diverse(others, limit - len(selected), counts)
            selected.extend(extra)
    else:
        selected, _ = select_diverse(scored, limit)

    # Map scored ids back to Problem rows for output fields.
    prob_by_id = {p.id: p for p in problems_raw}

    problems_out = []
    for cand in selected:
        prob = prob_by_id[cand.problem_id]

        # Determine unsolved confidence
        if prob.id in only_attempted_ids:
            confidence = "probable"
        else:
            confidence = "confirmed"

        platform_val = prob.platform
        if hasattr(platform_val, "value"):
            platform_val = platform_val.value

        difficulty_val = prob.difficulty
        if hasattr(difficulty_val, "value"):
            difficulty_val = difficulty_val.value

        problems_out.append(
            {
                "id": prob.id,
                "title": prob.title,
                "platform": platform_val,
                "difficulty": difficulty_val,
                "url": prob.problem_url,
                "topics": topics_by_problem.get(prob.id, []),
                "acceptance_rate": prob.acceptance_rate,
                "likely_unsolved": True,
                "unsolved_confidence": confidence,
                "score": cand.breakdown["score"],
                "score_breakdown": cand.breakdown,
            }
        )

    result: dict = {"problems": problems_out}

    if len(problems_out) < 5:
        result["catalog_limited"] = True
        result["catalog_message"] = (
            f"Only {len(problems_out)} candidate problem(s) found in the local catalog. "
            "The database only contains problems synced from your submission history. "
            "Consider syncing more submissions to expand the catalog."
        )

    return result


def get_problem_details(db: Session, user_id: int, problem_id: int) -> dict:
    """Get details for a specific problem from the database catalog.

    Checks whether the authenticated user has solved or attempted this problem.
    Returns an error dict if the problem is not found.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID (never from model output).
        problem_id: DB primary key of the problem.

    Returns:
        Dict with problem details including user_has_solved and
        user_submission_count. Or {"error": ..., "problem_id": ...} if not found.
    """
    prob = db.query(Problem).filter(Problem.id == problem_id).first()

    if prob is None:
        return {
            "error": "Problem not found in catalog",
            "problem_id": problem_id,
        }

    # Check user's submission history for this problem (scoped by user_id)
    profile_ids_subq = select(PlatformProfile.id).where(
        PlatformProfile.user_id == user_id
    )

    submission_count = (
        db.query(func.count(Submission.id))
        .filter(
            Submission.problem_id == problem_id,
            Submission.profile_id.in_(profile_ids_subq),
        )
        .scalar() or 0
    )

    has_accepted = (
        db.query(func.count(Submission.id))
        .filter(
            Submission.problem_id == problem_id,
            Submission.profile_id.in_(profile_ids_subq),
            Submission.status == SubmissionStatus.ACCEPTED,
        )
        .scalar() or 0
    ) > 0

    # Fetch topics
    topic_rows = (
        db.query(Topic.name)
        .join(ProblemTopic, ProblemTopic.topic_id == Topic.id)
        .filter(ProblemTopic.problem_id == prob.id)
        .all()
    )
    topic_names = [t[0] for t in topic_rows]

    platform_val = prob.platform
    if hasattr(platform_val, "value"):
        platform_val = platform_val.value

    difficulty_val = prob.difficulty
    if hasattr(difficulty_val, "value"):
        difficulty_val = difficulty_val.value

    return {
        "id": prob.id,
        "title": prob.title,
        "platform": platform_val,
        "difficulty": difficulty_val,
        "url": prob.problem_url,
        "topics": topic_names,
        "acceptance_rate": prob.acceptance_rate,
        "user_has_solved": has_accepted,
        "user_submission_count": submission_count,
    }


def get_failure_patterns(
    db: Session, user_id: int, max_topics: int = 10
) -> dict:
    """Per-topic failure breakdown for the authenticated user.

    Groups the user's non-accepted submissions by verdict type
    (wrong_answer, time_limit_exceeded, memory_limit_exceeded,
    runtime_error, compile_error) per topic, and reports the 10 topics
    with the most non-accepted submissions.

    A problem tagged with multiple topics contributes its submissions to
    each of those topics, so topic totals are not mutually exclusive.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID.
        max_topics: Maximum topics returned (default 10, clamped 1-25).

    Returns:
        Dict with "topics" (list sorted by non_accepted desc), each entry
        having topic, total_attempts, non_accepted, failure_rate (0-1,
        rounded to 2 decimals) and "verdicts" (status value → count).
    """
    max_topics = max(1, min(int(max_topics), 25))

    profile_ids = select(PlatformProfile.id).where(
        PlatformProfile.user_id == user_id
    )

    rows = (
        db.query(Topic.name, Submission.status, func.count(Submission.id))
        .join(Problem, Problem.id == Submission.problem_id)
        .join(ProblemTopic, ProblemTopic.problem_id == Problem.id)
        .join(Topic, Topic.id == ProblemTopic.topic_id)
        .filter(Submission.profile_id.in_(profile_ids))
        .group_by(Topic.name, Submission.status)
        .all()
    )

    per_topic: dict[str, dict] = {}
    for topic_name, status, count in rows:
        entry = per_topic.setdefault(
            topic_name,
            {"total_attempts": 0, "accepted": 0, "verdicts": {}},
        )
        entry["total_attempts"] += count
        status_val = status.value if hasattr(status, "value") else str(status)
        if status_val == SubmissionStatus.ACCEPTED.value:
            entry["accepted"] += count
        else:
            entry["verdicts"][status_val] = (
                entry["verdicts"].get(status_val, 0) + count
            )

    topics_out = []
    for topic_name, entry in per_topic.items():
        non_accepted = entry["total_attempts"] - entry["accepted"]
        topics_out.append(
            {
                "topic": topic_name,
                "total_attempts": entry["total_attempts"],
                "non_accepted": non_accepted,
                "failure_rate": round(non_accepted / entry["total_attempts"], 2)
                if entry["total_attempts"]
                else 0.0,
                "verdicts": entry["verdicts"],
            }
        )

    topics_out.sort(
        key=lambda t: (t["non_accepted"], t["total_attempts"]), reverse=True
    )

    return {
        "topics": topics_out[:max_topics],
        "note": (
            "Problems tagged with multiple topics count toward each topic; "
            "topic totals are not mutually exclusive."
        ),
    }


def get_attempts_before_accept(db: Session, user_id: int) -> dict:
    """Per-topic average submissions needed before the first ACCEPTED.

    For every problem the user attempted that was eventually accepted,
    counts how many submissions preceded the first ACCEPTED (the accept
    itself is not counted). Problems never accepted are excluded from the
    average but reported separately.

    A problem tagged with multiple topics contributes to each topic.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID.

    Returns:
        Dict with "topics" (up to 15, sorted by problems_measured desc),
        each entry having topic, avg_attempts_before_accept (rounded to 2
        decimals, null when nothing was measured), problems_measured and
        never_accepted_problems.
    """
    profile_ids = select(PlatformProfile.id).where(
        PlatformProfile.user_id == user_id
    )

    rows = (
        db.query(
            Submission.problem_id,
            Topic.name,
            Submission.status,
            Submission.submitted_at,
        )
        .join(Problem, Problem.id == Submission.problem_id)
        .join(ProblemTopic, ProblemTopic.problem_id == Problem.id)
        .join(Topic, Topic.id == ProblemTopic.topic_id)
        .filter(Submission.profile_id.in_(profile_ids))
        .all()
    )

    # (topic, problem_id) -> list of (status_value, submitted_at)
    attempts: dict[tuple[str, int], list[tuple[str, datetime]]] = {}
    for problem_id, topic_name, status, submitted_at in rows:
        status_val = status.value if hasattr(status, "value") else str(status)
        attempts.setdefault((topic_name, problem_id), []).append(
            (status_val, _as_utc(submitted_at))
        )

    per_topic: dict[str, dict] = {}
    for (topic_name, _problem_id), subs in attempts.items():
        subs.sort(key=lambda s: s[1])
        first_accept_idx = next(
            (i for i, (st, _) in enumerate(subs) if st == SubmissionStatus.ACCEPTED.value),
            None,
        )
        entry = per_topic.setdefault(
            topic_name,
            {"attempts_sum": 0, "measured": 0, "never_accepted": 0},
        )
        if first_accept_idx is None:
            entry["never_accepted"] += 1
        else:
            entry["attempts_sum"] += first_accept_idx
            entry["measured"] += 1

    topics_out = []
    for topic_name, entry in per_topic.items():
        topics_out.append(
            {
                "topic": topic_name,
                "avg_attempts_before_accept": (
                    round(entry["attempts_sum"] / entry["measured"], 2)
                    if entry["measured"]
                    else None
                ),
                "problems_measured": entry["measured"],
                "never_accepted_problems": entry["never_accepted"],
            }
        )

    topics_out.sort(
        key=lambda t: (t["problems_measured"], t["never_accepted_problems"]),
        reverse=True,
    )

    return {
        "topics": topics_out[:15],
        "note": (
            "A problem tagged with multiple topics counts toward each topic. "
            "avg_attempts_before_accept counts submissions before the first "
            "ACCEPTED; never-accepted problems are excluded from the average."
        ),
    }


def get_stale_topics(
    db: Session, user_id: int, days: int = 30
) -> dict:
    """Topics the user has solved but not practised recently.

    A topic is stale when the user has at least one ACCEPTED problem in it
    but no submissions of any status on problems tagged with that topic
    within the last ``days`` days.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID.
        days: Inactivity window in days (default 30, clamped 7-365).

    Returns:
        Dict with "window_days" and "topics" (up to 15, sorted by
        days_since_last_activity desc), each entry having topic,
        days_since_last_activity and solved_count.
    """
    days = max(7, min(int(days), 365))
    cutoff = _utcnow() - timedelta(days=days)

    profile_ids = select(PlatformProfile.id).where(
        PlatformProfile.user_id == user_id
    )

    # Last submission timestamp per topic (any status).
    last_rows = (
        db.query(Topic.name, func.max(Submission.submitted_at))
        .join(Problem, Problem.id == Submission.problem_id)
        .join(ProblemTopic, ProblemTopic.problem_id == Problem.id)
        .join(Topic, Topic.id == ProblemTopic.topic_id)
        .filter(Submission.profile_id.in_(profile_ids))
        .group_by(Topic.name)
        .all()
    )
    last_activity = {name: _as_utc(ts) for name, ts in last_rows if ts is not None}

    # Distinct solved problems per topic.
    solved_rows = (
        db.query(Topic.name, func.count(distinct(Submission.problem_id)))
        .join(Problem, Problem.id == Submission.problem_id)
        .join(ProblemTopic, ProblemTopic.problem_id == Problem.id)
        .join(Topic, Topic.id == ProblemTopic.topic_id)
        .filter(
            Submission.profile_id.in_(profile_ids),
            Submission.status == SubmissionStatus.ACCEPTED,
        )
        .group_by(Topic.name)
        .all()
    )
    solved_counts = {name: count for name, count in solved_rows}

    now = _utcnow()
    topics_out = []
    for topic_name, solved_count in solved_counts.items():
        if solved_count <= 0:
            continue
        last = last_activity.get(topic_name)
        if last is None or last >= cutoff:
            continue
        days_since = int((now - last).total_seconds() // 86400)
        topics_out.append(
            {
                "topic": topic_name,
                "days_since_last_activity": days_since,
                "solved_count": solved_count,
            }
        )

    topics_out.sort(key=lambda t: t["days_since_last_activity"], reverse=True)

    return {"window_days": days, "topics": topics_out[:15]}


_CONTEST_POSTMORTEM_LIMITATION = (
    "Per-problem breakdowns within contests are not stored — only aggregate "
    "solved counts are available. For Codeforces participations, 'solved' "
    "is always 0 because the sync service does not populate it."
)


def get_contest_postmortem(
    db: Session, user_id: int, limit: int = 5
) -> dict:
    """Rating-change postmortem for the user's most recent contests.

    Returns the last ``limit`` contest participations (by contest start
    time) with rank, rating change and aggregate solved count.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID.
        limit: Number of contests (default 5, clamped 1-10).

    Returns:
        Dict with "contests" (most recent first) and "limitation" describing
        what per-contest data is not stored.
    """
    limit = max(1, min(int(limit), 10))

    profile_ids = select(PlatformProfile.id).where(
        PlatformProfile.user_id == user_id
    )

    rows = (
        db.query(Contest, ContestParticipation)
        .join(
            ContestParticipation,
            ContestParticipation.contest_id == Contest.id,
        )
        .filter(ContestParticipation.profile_id.in_(profile_ids))
        .order_by(Contest.start_time.desc())
        .limit(limit)
        .all()
    )

    contests_out = []
    for contest, part in rows:
        platform_val = contest.platform
        if hasattr(platform_val, "value"):
            platform_val = platform_val.value
        start_time = contest.start_time
        contests_out.append(
            {
                "title": contest.title,
                "platform": platform_val,
                "start_time": (
                    _as_utc(start_time).isoformat()
                    if start_time is not None
                    else None
                ),
                "rank": part.rank,
                "old_rating": part.old_rating,
                "new_rating": part.new_rating,
                "rating_change": part.rating_change,
                "solved": part.solved,
                "penalty": part.penalty,
            }
        )

    return {
        "contests": contests_out,
        "limitation": _CONTEST_POSTMORTEM_LIMITATION,
    }
