from sqlalchemy.orm import Session

from app.models.rating_history import RatingHistory
from app.repositories.rating_history_repository import RatingHistoryRepository


class RatingHistoryService:
    def __init__(self, db: Session):
        self.repository = RatingHistoryRepository(db)

    def get_rating_history(self, rating_id: int) -> RatingHistory | None:
        return self.repository.get_by_id(rating_id)

    def get_rating_history_for_profile(
        self,
        profile_id: int,
        skip: int,
        limit: int,
    ) -> list[RatingHistory]:
        return self.repository.get_by_profile(profile_id, skip, limit)
