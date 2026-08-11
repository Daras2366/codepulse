"""UserAchievement repository.

Handles persistence for the user ↔ achievement join table.
Achievement definitions are managed by AchievementRepository.
"""

from datetime import datetime, timezone
from typing import List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.achievement import Achievement
from app.models.user_achievement import UserAchievement
from app.repositories.base import BaseRepository


class UserAchievementRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_by_id(self, ua_id: int) -> UserAchievement | None:
        return (
            self.db.query(UserAchievement)
            .filter(UserAchievement.id == ua_id)
            .first()
        )

    def get_by_user(self, user_id: int) -> List[UserAchievement]:
        """Return all UserAchievement rows for a user, eager-loading Achievement."""
        return (
            self.db.query(UserAchievement)
            .options(joinedload(UserAchievement.achievement))
            .filter(UserAchievement.user_id == user_id)
            .order_by(UserAchievement.earned_at.desc())
            .all()
        )

    def get_by_user_and_achievement(
        self,
        user_id: int,
        achievement_id: int,
    ) -> UserAchievement | None:
        return (
            self.db.query(UserAchievement)
            .filter(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement_id,
            )
            .first()
        )

    def grant(self, user_id: int, achievement_id: int) -> UserAchievement | None:
        """Grant an achievement to a user.

        Returns the new UserAchievement, or None if the user already has it
        (idempotent — the DB unique constraint is the authoritative guard).
        """
        ua = UserAchievement(
            user_id=user_id,
            achievement_id=achievement_id,
            earned_at=datetime.now(tz=timezone.utc),
        )
        self.db.add(ua)
        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(ua)
            return ua
        except IntegrityError:
            self.db.rollback()
            return None
