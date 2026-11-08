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

from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from app.models.enums import SubmissionStatus
from app.models.goal import Goal
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
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
    profile_ids = (
        db.query(PlatformProfile.id)
        .filter(PlatformProfile.user_id == user_id)
        .subquery()
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
    profile_ids = (
        db.query(PlatformProfile.id)
        .filter(PlatformProfile.user_id == user_id)
        .subquery()
    )

    rows = (
        db.query(distinct(Submission.problem_id))
        .filter(Submission.profile_id.in_(profile_ids))
        .all()
    )
    return {row[0] for row in rows}


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

    profile_ids_subq = (
        db.query(PlatformProfile.id)
        .filter(PlatformProfile.user_id == user_id)
        .subquery()
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
    3. Optionally filter by topic, difficulty, and platform.
    4. Order by acceptance_rate DESC (more solvable problems first).
    5. Annotate with unsolved_confidence: "confirmed" if never attempted,
       "probable" if attempted but not accepted.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID (never from model output).
        topic: Optional topic name filter (e.g. "Dynamic Programming").
        difficulty: Optional difficulty filter ("Easy"/"Medium"/"Hard").
        platform: Optional platform filter ("leetcode"/"codeforces").
        limit: Max problems to return (1-20).

    Returns:
        Dict with key "problems" (list of problem dicts) and optional
        "catalog_limited" flag if fewer than 5 candidates were found.
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

    # Build base query for unsolved problems
    query = db.query(Problem).filter(
        Problem.id.notin_(solved_ids) if solved_ids else True
    )

    # Apply platform filter
    if platform is not None:
        from app.models.enums import Platform as PlatformEnum
        try:
            platform_enum = PlatformEnum(platform)
            query = query.filter(Problem.platform == platform_enum)
        except ValueError:
            pass

    # Apply difficulty filter
    if difficulty is not None:
        from app.models.enums import Difficulty as DifficultyEnum
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
                diff_enum = DifficultyEnum(difficulty)
                query = query.filter(Problem.difficulty == diff_enum)
            except ValueError:
                pass

    # Apply topic filter via join
    if topic is not None:
        query = (
            query
            .join(ProblemTopic, ProblemTopic.problem_id == Problem.id)
            .join(Topic, Topic.id == ProblemTopic.topic_id)
            .filter(Topic.name.ilike(f"%{topic}%"))
        )

    # Order by acceptance rate descending (more solvable first), None last
    query = query.order_by(
        Problem.acceptance_rate.desc().nullslast()
        if hasattr(Problem.acceptance_rate, "desc")
        else Problem.acceptance_rate.desc()
    )

    problems_raw = query.limit(limit).all()
    catalog_limited = len(problems_raw) < 5

    # For each problem, fetch its topics
    problems_out = []
    for prob in problems_raw:
        # Fetch topics
        topic_rows = (
            db.query(Topic.name)
            .join(ProblemTopic, ProblemTopic.topic_id == Topic.id)
            .filter(ProblemTopic.problem_id == prob.id)
            .all()
        )
        topic_names = [t[0] for t in topic_rows]

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
                "topics": topic_names,
                "acceptance_rate": prob.acceptance_rate,
                "likely_unsolved": True,
                "unsolved_confidence": confidence,
            }
        )

    result: dict = {"problems": problems_out}

    if catalog_limited:
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
    profile_ids_subq = (
        db.query(PlatformProfile.id)
        .filter(PlatformProfile.user_id == user_id)
        .subquery()
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
