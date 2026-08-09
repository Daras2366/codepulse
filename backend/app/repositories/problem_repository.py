from typing import List

from sqlalchemy.orm import Session

from app.models.enums import Platform
from app.models.problem import Problem
from app.repositories.base import BaseRepository


class ProblemRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, problem: Problem) -> Problem:
        self.db.add(problem)
        self.db.commit()
        self.db.refresh(problem)
        return problem

    def get_by_id(self, problem_id: int) -> Problem | None:
        return (
            self.db.query(Problem)
            .filter(Problem.id == problem_id)
            .first()
        )

    def get_by_platform_problem_id(
        self,
        platform: Platform,
        platform_problem_id: str,
    ) -> Problem | None:
        return (
            self.db.query(Problem)
            .filter(
                Problem.platform == platform,
                Problem.platform_problem_id == platform_problem_id,
            )
            .first()
        )

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Problem]:
        return (
            self.db.query(Problem)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update(self, problem: Problem) -> Problem:
        self.db.commit()
        self.db.refresh(problem)
        return problem

    def delete(self, problem: Problem) -> None:
        self.db.delete(problem)
        self.db.commit()

    def exists(self, problem_id: int) -> bool:
        return (
            self.db.query(Problem)
            .filter(Problem.id == problem_id)
            .first()
            is not None
        )
