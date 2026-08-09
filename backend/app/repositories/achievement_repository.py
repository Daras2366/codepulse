from typing import List

from sqlalchemy.orm import Session

from app.models.achievement import Achievement
from app.repositories.base import BaseRepository


class AchievementRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, achievement: Achievement) -> Achievement:
        self.db.add(achievement)
        self.db.commit()
        self.db.refresh(achievement)
        return achievement

    def get_by_id(self, achievement_id: int) -> Achievement | None:
        return (
            self.db.query(Achievement)
            .filter(Achievement.id == achievement_id)
            .first()
        )

    def get_by_name(self, name: str) -> Achievement | None:
        return (
            self.db.query(Achievement)
            .filter(Achievement.name == name)
            .first()
        )

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Achievement]:
        return (
            self.db.query(Achievement)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(self, achievement: Achievement) -> Achievement:
        self.db.commit()
        self.db.refresh(achievement)
        return achievement

    def delete(self, achievement: Achievement) -> None:
        self.db.delete(achievement)
        self.db.commit()

    def exists(self, achievement_id: int) -> bool:
        return (
            self.db.query(Achievement)
            .filter(Achievement.id == achievement_id)
            .first()
            is not None
        )
