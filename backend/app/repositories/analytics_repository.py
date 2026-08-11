"""Analytics-specific aggregate queries.

The DashboardRepository already implements the five core analytics queries
(submission activity, difficulty distribution, rating history, contest history,
submission summary).  This repository adds only one piece that the dashboard
layer does not expose: the contests-attended scalar count broken out here so
that the analytics service does not need to instantiate DashboardRepository
solely for that scalar.

All heavy aggregation lives in DashboardRepository; this module reuses it.
"""

from sqlalchemy.orm import Session

from app.repositories.dashboard_repository import DashboardRepository


class AnalyticsRepository:
    """Thin wrapper that exposes the DashboardRepository queries under the
    analytics namespace.  Having a distinct class keeps the analytics service
    decoupled from the dashboard service while avoiding query duplication."""

    def __init__(self, db: Session) -> None:
        self._dashboard = DashboardRepository(db)

    # ------------------------------------------------------------------
    # Delegated queries (no duplication of SQL logic)
    # ------------------------------------------------------------------

    def get_submission_summary(self, profile_id: int):
        """Return (total_submissions, solved_count, accepted_submissions)."""
        return self._dashboard.get_submission_summary(profile_id)

    def get_contests_attended_count(self, profile_id: int) -> int:
        return self._dashboard.get_contests_attended_count(profile_id)

    def get_submission_activity(self, profile_id: int):
        """Return per-day submission rows (activity_date, total, accepted)."""
        return self._dashboard.get_submission_activity(profile_id)

    def get_solved_by_difficulty(self, profile_id: int):
        """Return (difficulty, solved_count) rows."""
        return self._dashboard.get_solved_by_difficulty(profile_id)

    def get_rating_history(self, profile_id: int):
        """Return (RatingHistory, Contest | None) rows ordered by date."""
        return self._dashboard.get_rating_history(profile_id)

    def get_contest_history(self, profile_id: int):
        """Return (ContestParticipation, Contest) rows ordered by date desc."""
        return self._dashboard.get_contest_history(profile_id)
