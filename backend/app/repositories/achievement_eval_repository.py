"""Achievement evaluation repository.

Calculates per-user metrics used to decide which achievements to grant.
All queries are user-scoped via PlatformProfile.user_id.

Metrics supported:
  - total distinct problems solved (across all user profiles)
  - total submissions (across all user profiles)
  - total contests attended (across all user profiles)
  - max rating achieved (max across all user profiles)
"""

from sqlalchemy import case, distinct, func
from sqlalchemy.orm import Session

from app.models.contest_participation import ContestParticipation
from app.models.enums import SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.submission import Submission
from app.repositories.base import BaseRepository


class AchievementEvalRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_solved_problems(self, user_id: int) -> int:
        """Count distinct problems solved (accepted) across all profiles."""
        result = (
            self.db.query(func.count(distinct(Submission.problem_id)))
            .join(PlatformProfile, Submission.profile_id == PlatformProfile.id)
            .filter(
                PlatformProfile.user_id == user_id,
                Submission.status == SubmissionStatus.ACCEPTED,
            )
            .scalar()
        ) or 0
        return int(result)

    def get_total_submissions(self, user_id: int) -> int:
        """Count total submissions across all profiles."""
        result = (
            self.db.query(func.count(Submission.id))
            .join(PlatformProfile, Submission.profile_id == PlatformProfile.id)
            .filter(PlatformProfile.user_id == user_id)
            .scalar()
        ) or 0
        return int(result)

    def get_contests_attended(self, user_id: int) -> int:
        """Count total contest participations across all profiles."""
        result = (
            self.db.query(func.count(ContestParticipation.id))
            .join(
                PlatformProfile,
                ContestParticipation.profile_id == PlatformProfile.id,
            )
            .filter(PlatformProfile.user_id == user_id)
            .scalar()
        ) or 0
        return int(result)

    def get_max_rating(self, user_id: int) -> int:
        """Return the highest max_rating across all of a user's profiles."""
        result = (
            self.db.query(func.max(PlatformProfile.max_rating))
            .filter(PlatformProfile.user_id == user_id)
            .scalar()
        )
        return int(result) if result is not None else 0
