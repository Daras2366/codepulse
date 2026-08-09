from sqlalchemy.orm import Session

from app.models.enums import Platform
from app.models.problem import Problem
from app.repositories.problem_repository import ProblemRepository


class ProblemService:
    def __init__(self, db: Session):
        self.repository = ProblemRepository(db)

    def get_problem(self, problem_id: int) -> Problem | None:
        return self.repository.get_by_id(problem_id)

    def get_all_problems(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Problem]:
        return self.repository.get_all(skip, limit)

    def get_problem_by_platform_id(
        self,
        platform: Platform,
        platform_problem_id: str,
    ) -> Problem | None:
        return self.repository.get_by_platform_problem_id(
            platform,
            platform_problem_id,
        )

    def create_problem(self, problem: Problem) -> Problem:
        return self.repository.create(problem)

    def update_problem(self, problem: Problem) -> Problem:
        return self.repository.update(problem)

    def delete_problem(self, problem_id: int) -> bool:
        problem = self.repository.get_by_id(problem_id)

        if problem is None:
            return False

        self.repository.delete(problem)
        return True
