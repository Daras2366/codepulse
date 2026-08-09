from sqlalchemy.orm import Session

from app.models.contest_participation import ContestParticipation
from app.repositories.contest_participation_repository import ContestParticipationRepository


class ContestParticipationService:
    def __init__(self, db: Session):
        self.repository = ContestParticipationRepository(db)

    def get_participation(self, participation_id: int) -> ContestParticipation | None:
        return self.repository.get_by_id(participation_id)

    def get_participations(
        self,
        profile_id: int,
        skip: int,
        limit: int,
    ) -> list[ContestParticipation]:
        return self.repository.get_by_profile(profile_id, skip, limit)
