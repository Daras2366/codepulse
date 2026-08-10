from typing import List

from sqlalchemy.orm import Session

from app.models.rating_history import RatingHistory
from app.repositories.base import BaseRepository


class RatingHistoryRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, rating: RatingHistory) -> RatingHistory:
        self.db.add(rating)
        self.db.commit()
        self.db.refresh(rating)
        return rating

    def bulk_create(
        self,
        ratings: List[RatingHistory],
    ) -> List[RatingHistory]:
        self.db.add_all(ratings)
        self.db.commit()
        return ratings

    def get_by_id(self, rating_id: int) -> RatingHistory | None:
        return (
            self.db.query(RatingHistory)
            .filter(RatingHistory.id == rating_id)
            .first()
        )

    def get_by_profile(
        self,
        profile_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[RatingHistory]:
        return (
            self.db.query(RatingHistory)
            .filter(RatingHistory.profile_id == profile_id)
            .order_by(RatingHistory.recorded_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_latest(self, profile_id: int) -> RatingHistory | None:
        return (
            self.db.query(RatingHistory)
            .filter(RatingHistory.profile_id == profile_id)
            .order_by(RatingHistory.recorded_at.desc())
            .first()
        )

    def update(self, rating: RatingHistory) -> RatingHistory:
        self.db.commit()
        self.db.refresh(rating)
        return rating

    def delete(self, rating: RatingHistory) -> None:
        self.db.delete(rating)
        self.db.commit()

    def exists(self, rating_id: int) -> bool:
        return (
            self.db.query(RatingHistory)
            .filter(RatingHistory.id == rating_id)
            .first()
            is not None
        )

    def get_by_profile_contest(
        self,
        profile_id: int,
        contest_id: int,
    ) -> RatingHistory | None:
        return (
            self.db.query(RatingHistory)
            .filter(
                RatingHistory.profile_id == profile_id,
                RatingHistory.contest_id == contest_id,
            )
            .first()
        )