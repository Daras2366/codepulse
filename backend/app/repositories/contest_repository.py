from typing import List

from sqlalchemy.orm import Session

from app.models.contest import Contest
from app.models.enums import Platform
from app.repositories.base import BaseRepository


class ContestRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, contest: Contest) -> Contest:
        self.db.add(contest)
        self.db.commit()
        self.db.refresh(contest)
        return contest

    def get_by_id(self, contest_id: int) -> Contest | None:
        return (
            self.db.query(Contest)
            .filter(Contest.id == contest_id)
            .first()
        )

    def get_by_platform_contest_id(
        self,
        platform: Platform,
        platform_contest_id: str,
    ) -> Contest | None:
        return (
            self.db.query(Contest)
            .filter(
                Contest.platform == platform,
                Contest.platform_contest_id == platform_contest_id,
            )
            .first()
        )

    def get_by_platform(
        self,
        platform: Platform,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Contest]:
        return (
            self.db.query(Contest)
            .filter(Contest.platform == platform)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Contest]:
        return (
            self.db.query(Contest)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(self, contest: Contest) -> Contest:
        self.db.commit()
        self.db.refresh(contest)
        return contest

    def delete(self, contest: Contest) -> None:
        self.db.delete(contest)
        self.db.commit()

    def exists(self, contest_id: int) -> bool:
        return (
            self.db.query(Contest)
            .filter(Contest.id == contest_id)
            .first()
            is not None
        )
