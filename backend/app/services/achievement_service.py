from sqlalchemy.orm import Session

from app.models.achievement import Achievement
from app.repositories.achievement_repository import AchievementRepository


class AchievementService:
    def __init__(self, db: Session):
        self.repository = AchievementRepository(db)

    def get_achievement(self, achievement_id: int) -> Achievement | None:
        return self.repository.get_by_id(achievement_id)

    def get_achievements(self, skip: int, limit: int) -> list[Achievement]:
        return self.repository.get_all(skip, limit)
