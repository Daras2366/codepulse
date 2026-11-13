"""AI Coach feedback: user-submitted feedback and automatic "solved" marking.

Feedback policy (documented, consistent):
- ``(recommendation_id, action)`` is unique — submitting the same action twice
  is idempotent and returns the existing row without creating a duplicate.
- Different actions on the same recommendation may coexist (e.g. an automatic
  ``solved`` plus a manual ``thumbs_up``).
- Feedback ownership is enforced via ``coach_recommendations.user_id``.

Automatic solved marking:
- Called from platform sync paths when an ACCEPTED submission is imported.
- Matches recommendations of the SAME user on the SAME canonical problem id
  (``problems.id`` == ``submissions.problem_id``).
- Only recommendations created within the previous 14 days qualify.
- A submission older than the recommendation never marks it solved
  (``submission.submitted_at >= recommendation.created_at`` required).
- Runs inside a nested transaction so a failure cannot corrupt the sync
  transaction; it never commits on its own.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.coach import CoachFeedback, CoachRecommendation
from app.models.enums import CoachFeedbackAction
from app.repositories.coach_repository import (
    CoachFeedbackRepository,
    CoachRecommendationRepository,
)

logger = logging.getLogger(__name__)

SOLVED_MATCH_WINDOW_DAYS = 14


class FeedbackNotFoundError(LookupError):
    """Raised when the recommendation does not exist or belongs to another user."""


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normalise a possibly-naive datetime to aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def submit_feedback(
    db: Session,
    *,
    user_id: int,
    recommendation_id: int,
    action: CoachFeedbackAction,
) -> tuple[CoachFeedback, bool]:
    """Record user feedback on a recommendation.

    Returns ``(feedback_row, created)`` where ``created`` is False when an
    identical feedback event already existed (idempotent retry).

    Raises:
        FeedbackNotFoundError: recommendation missing or owned by another user.
    """
    recs = CoachRecommendationRepository(db)
    feedback_repo = CoachFeedbackRepository(db)

    recommendation = recs.get_by_id(recommendation_id)
    if recommendation is None or recommendation.user_id != user_id:
        raise FeedbackNotFoundError(
            f"Recommendation {recommendation_id} was not found."
        )

    existing = feedback_repo.get_by_recommendation_and_action(
        recommendation_id, action
    )
    if existing is not None:
        return existing, False

    feedback = CoachFeedback(
        recommendation_id=recommendation_id,
        action=action,
    )
    try:
        with db.begin_nested():
            feedback_repo.add(feedback)
        db.commit()
        return feedback, True
    except IntegrityError:
        # Concurrent duplicate — the unique constraint fired. Treat as
        # idempotent and return the row that won the race.
        db.rollback()
        existing = feedback_repo.get_by_recommendation_and_action(
            recommendation_id, action
        )
        if existing is not None:
            return existing, False
        raise


def record_solved_for_submission(
    db: Session,
    *,
    user_id: int,
    problem_id: int,
    submitted_at: datetime,
) -> int:
    """Mark matching recommendations as solved after an ACCEPTED submission.

    Called from platform sync paths. Never commits — the caller's transaction
    owns persistence. Failures are logged and swallowed so sync is never
    broken by feedback bookkeeping.

    Returns the number of new ``solved`` feedback rows created.
    """
    try:
        return _record_solved_for_submission(
            db,
            user_id=user_id,
            problem_id=problem_id,
            submitted_at=submitted_at,
        )
    except Exception as exc:
        # The nested savepoint inside _record_solved_for_submission already
        # restored the session — do NOT call db.rollback() here or the
        # caller's (sync) transaction would be discarded.
        logger.warning(
            "coach_feedback: failed to record solved feedback "
            "user_id=%d problem_id=%d: %s",
            user_id,
            problem_id,
            exc,
        )
        return 0


def _record_solved_for_submission(
    db: Session,
    *,
    user_id: int,
    problem_id: int,
    submitted_at: datetime,
) -> int:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=SOLVED_MATCH_WINDOW_DAYS)
    submitted_utc = _as_utc(submitted_at)

    recs = CoachRecommendationRepository(db)
    feedback_repo = CoachFeedbackRepository(db)

    created = 0
    # Everything — including the candidate query — runs inside a savepoint so
    # a failure rolls back only the feedback writes, never the sync work.
    with db.begin_nested():
        # Recommendations created within the last 14 days AND no later than
        # the submission timestamp (a submission older than the
        # recommendation must not mark it solved).
        candidates = recs.get_matching_for_problem(
            user_id=user_id,
            problem_id=problem_id,
            created_after=window_start,
            created_before=submitted_utc,
        )
        # created_at may be naive on SQLite — re-check the upper bound in
        # Python to be safe against driver-specific timestamp handling.
        candidates = [
            rec
            for rec in candidates
            if (_as_utc(rec.created_at) or now) <= (submitted_utc or now)
        ]

        for rec in candidates:
            existing = feedback_repo.get_by_recommendation_and_action(
                rec.id, CoachFeedbackAction.SOLVED
            )
            if existing is not None:
                continue
            feedback_repo.add(
                CoachFeedback(
                    recommendation_id=rec.id,
                    action=CoachFeedbackAction.SOLVED,
                )
            )
            created += 1
    return created
