from sqlalchemy.orm import Session

from app.models.contest import Contest
from app.models.enums import Platform
from app.repositories.contest_repository import ContestRepository


class ContestService:
    def __init__(self, db: Session):
        self.repository = ContestRepository(db)

    def get_contest(self, contest_id: int) -> Contest | None:
        return self.repository.get_by_id(contest_id)

    def get_contests(
        self,
        skip: int,
        limit: int,
        platform: Platform | None = None,
    ) -> list[Contest]:
        if platform is not None:
            return self.repository.get_by_platform(platform, skip, limit)
        return self.repository.get_all(skip, limit)
