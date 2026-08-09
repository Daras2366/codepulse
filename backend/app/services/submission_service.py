from sqlalchemy.orm import Session

from app.models.submission import Submission
from app.repositories.submission_repository import SubmissionRepository


class SubmissionService:
    def __init__(self, db: Session):
        self.repository = SubmissionRepository(db)

    def get_submission(self, submission_id: int) -> Submission | None:
        return self.repository.get_by_id(submission_id)

    def get_submissions(
        self,
        skip: int,
        limit: int,
        profile_id: int | None = None,
        problem_id: int | None = None,
    ) -> list[Submission]:
        if profile_id is not None and problem_id is not None:
            return self.repository.get_profile_problem(
                profile_id,
                problem_id,
                skip,
                limit,
            )
        elif profile_id is not None:
            return self.repository.get_by_profile(profile_id, skip, limit)
        elif problem_id is not None:
            return self.repository.get_by_problem(problem_id, skip, limit)
        else:
            # TODO: Replace ValueError when the project defines application exceptions.
            raise ValueError("profile_id or problem_id is required")
