from typing import List

from sqlalchemy.orm import Session

from app.models.enums import SubmissionStatus
from app.models.submission import Submission
from app.repositories.base import BaseRepository


class SubmissionRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, submission: Submission) -> Submission:
        self.db.add(submission)
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def bulk_create(
        self,
        submissions: List[Submission],
    ) -> List[Submission]:
        self.db.add_all(submissions)
        self.db.commit()
        return submissions

    def get_by_id(
        self,
        submission_id: int,
    ) -> Submission | None:
        return (
            self.db.query(Submission)
            .filter(Submission.id == submission_id)
            .first()
        )

    def get_by_profile(
        self,
        profile_id: int,
    ) -> List[Submission]:
        return (
            self.db.query(Submission)
            .filter(Submission.profile_id == profile_id)
            .all()
        )

    def get_by_problem(
        self,
        problem_id: int,
    ) -> List[Submission]:
        return (
            self.db.query(Submission)
            .filter(Submission.problem_id == problem_id)
            .all()
        )

    def get_profile_problem(
        self,
        profile_id: int,
        problem_id: int,
    ) -> List[Submission]:
        return (
            self.db.query(Submission)
            .filter(
                Submission.profile_id == profile_id,
                Submission.problem_id == problem_id,
            )
            .all()
        )

    def get_recent_by_profile(
        self,
        profile_id: int,
        limit: int = 20,
    ) -> List[Submission]:
        return (
            self.db.query(Submission)
            .filter(Submission.profile_id == profile_id)
            .order_by(Submission.submitted_at.desc())
            .limit(limit)
            .all()
        )

    def count_by_profile(
        self,
        profile_id: int,
    ) -> int:
        return (
            self.db.query(Submission)
            .filter(Submission.profile_id == profile_id)
            .count()
        )

    def count_accepted(
        self,
        profile_id: int,
    ) -> int:
        return (
            self.db.query(Submission)
            .filter(
                Submission.profile_id == profile_id,
                Submission.status == SubmissionStatus.ACCEPTED
            )
            .count()
        )

    def update(
        self,
        submission: Submission,
    ) -> Submission:
        self.db.commit()
        self.db.refresh(submission)
        return submission

    def delete(
        self,
        submission: Submission,
    ) -> None:
        self.db.delete(submission)
        self.db.commit()
