"""Goal progress repository.

Calculates per-user aggregate metrics needed to determine goal progress.

All queries are user-scoped (via PlatformProfile.user_id JOIN), so a
single user with multiple Codeforces profiles gets correct aggregate
counts across all their profiles.

GoalType mapping:
  DAILY   — solved problems submitted today (UTC)
  WEEKLY  — solved problems submitted this ISO week (Mon-Sun UTC)
  MONTHLY — solved problems submitted this calendar month (UTC)

"Solved problems" = distinct problem_ids with status = ACCEPTED within
the time window, across all of the user's platform profiles.
"""

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import case, distinct, func
from sqlalchemy.orm import Session

from app.models.enums import GoalType, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.submission import Submission
from app.repositories.base import BaseRepository


class GoalProgressRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # Date-window helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _window_for_type(goal_type: GoalType) -> tuple[date, date]:
        """Return (start_date, end_date) inclusive for the current window."""
        today = date.today()
        if goal_type == GoalType.DAILY:
            return today, today
        if goal_type == GoalType.WEEKLY:
            monday = today - timedelta(days=today.weekday())
            sunday = monday + timedelta(days=6)
            return monday, sunday
        # MONTHLY
        first = today.replace(day=1)
        # last day of month: first day of next month minus one day
        if first.month == 12:
            last = date(first.year + 1, 1, 1) - timedelta(days=1)
        else:
            last = date(first.year, first.month + 1, 1) - timedelta(days=1)
        return first, last

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_solved_in_window(
        self,
        user_id: int,
        goal_type: GoalType,
    ) -> int:
        """Count distinct problems solved by the user within the current window."""
        start, end = self._window_for_type(goal_type)
        result = (
            self.db.query(
                func.count(distinct(Submission.problem_id))
            )
            .join(
                PlatformProfile,
                Submission.profile_id == PlatformProfile.id,
            )
            .filter(
                PlatformProfile.user_id == user_id,
                Submission.status == SubmissionStatus.ACCEPTED,
                func.date(Submission.submitted_at) >= start,
                func.date(Submission.submitted_at) <= end,
            )
            .scalar()
        ) or 0
        return int(result)

    def get_window_dates(
        self, goal_type: GoalType
    ) -> tuple[date, date]:
        return self._window_for_type(goal_type)
