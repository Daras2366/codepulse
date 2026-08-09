from typing import List

from sqlalchemy.orm import Session

from app.models.contest_participation import ContestParticipation
from app.repositories.base import BaseRepository


class ContestParticipationRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(
        self,
        participation: ContestParticipation,
    ) -> ContestParticipation:
        self.db.add(participation)
        self.db.commit()
        self.db.refresh(participation)
        return participation

    def bulk_create(
        self,
        participations: List[ContestParticipation],
    ) -> List[ContestParticipation]:
        self.db.add_all(participations)
        self.db.commit()
        return participations

    def get_by_id(
        self,
        participation_id: int,
    ) -> ContestParticipation | None:
        return (
            self.db.query(ContestParticipation)
            .filter(ContestParticipation.id == participation_id)
            .first()
        )

    def get_by_profile(
        self,
        profile_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ContestParticipation]:
        return (
            self.db.query(ContestParticipation)
            .filter(ContestParticipation.profile_id == profile_id)
            .order_by(ContestParticipation.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_contest(
        self,
        contest_id: int,
    ) -> List[ContestParticipation]:
        return (
            self.db.query(ContestParticipation)
            .filter(ContestParticipation.contest_id == contest_id)
            .all()
        )

    def get_profile_contest(
        self,
        profile_id: int,
        contest_id: int,
    ) -> ContestParticipation | None:
        return (
            self.db.query(ContestParticipation)
            .filter(
                ContestParticipation.profile_id == profile_id,
                ContestParticipation.contest_id == contest_id,
            )
            .first()
        )

    def get_recent_by_profile(
        self,
        profile_id: int,
        limit: int = 10,
    ) -> List[ContestParticipation]:
        return (
            self.db.query(ContestParticipation)
            .filter(ContestParticipation.profile_id == profile_id)
            .order_by(ContestParticipation.created_at.desc())
            .limit(limit)
            .all()
        )

    def update(
        self,
        participation: ContestParticipation,
    ) -> ContestParticipation:
        self.db.commit()
        self.db.refresh(participation)
        return participation

    def delete(
        self,
        participation: ContestParticipation,
    ) -> None:
        self.db.delete(participation)
        self.db.commit()
