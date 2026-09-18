from sqlalchemy import case, distinct, func
from sqlalchemy.orm import Session

from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.enums import SubmissionStatus
from app.models.problem import Problem
from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.repositories.base import BaseRepository


class DashboardRepository(BaseRepository):
    """Read-only aggregate and joined queries used by the dashboard."""

    def __init__(self, db: Session):
        super().__init__(db)

    def get_submission_summary(self, profile_id: int):
        return (
            self.db.query(
                func.count(Submission.id).label("total_submissions"),
                func.count(
                    distinct(
                        case(
                            (
                                Submission.status == SubmissionStatus.ACCEPTED,
                                Submission.problem_id,
                            )
                        )
                    )
                ).label("solved_count"),
                func.coalesce(
                    func.sum(
                        case(
                            (Submission.status == SubmissionStatus.ACCEPTED, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("accepted_submissions"),
            )
            .filter(Submission.profile_id == profile_id)
            .one()
        )

    def get_contests_attended_count(self, profile_id: int) -> int:
        return (
            self.db.query(func.count(ContestParticipation.id))
            .filter(ContestParticipation.profile_id == profile_id)
            .scalar()
            or 0
        )

    def get_solved_by_difficulty(self, profile_id: int):
        return (
            self.db.query(
                Problem.difficulty.label("difficulty"),
                func.count(distinct(Submission.problem_id)).label("solved_count"),
            )
            .join(Submission, Submission.problem_id == Problem.id)
            .filter(
                Submission.profile_id == profile_id,
                Submission.status == SubmissionStatus.ACCEPTED,
            )
            .group_by(Problem.difficulty)
            .order_by(Problem.difficulty)
            .all()
        )

    def get_recent_submissions(self, profile_id: int, limit: int):
        return (
            self.db.query(Submission, Problem, Contest)
            .join(Problem, Submission.problem_id == Problem.id)
            .outerjoin(Contest, Submission.contest_id == Contest.id)
            .filter(Submission.profile_id == profile_id)
            .order_by(Submission.submitted_at.desc(), Submission.id.desc())
            .limit(limit)
            .all()
        )

    def get_submission_activity(self, profile_id: int):
        activity_date = func.date(Submission.submitted_at).label("activity_date")
        accepted = func.coalesce(
            func.sum(
                case(
                    (Submission.status == SubmissionStatus.ACCEPTED, 1),
                    else_=0,
                )
            ),
            0,
        ).label("accepted_submissions")

        return (
            self.db.query(
                activity_date,
                func.count(Submission.id).label("total_submissions"),
                accepted,
            )
            .filter(Submission.profile_id == profile_id)
            .group_by(activity_date)
            .order_by(activity_date.asc())
            .all()
        )

    def get_aggregate_submission_summary(self, profile_ids: list[int]):
        return (
            self.db.query(
                func.count(Submission.id).label("total_submissions"),
                func.coalesce(
                    func.sum(
                        case(
                            (Submission.status == SubmissionStatus.ACCEPTED, 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("accepted_submissions"),
            )
            .filter(Submission.profile_id.in_(profile_ids))
            .one()
        )

    def get_aggregate_recent_submissions(self, profile_ids: list[int], limit: int):
        return (
            self.db.query(Submission, Problem, Contest)
            .join(Problem, Submission.problem_id == Problem.id)
            .outerjoin(Contest, Submission.contest_id == Contest.id)
            .filter(Submission.profile_id.in_(profile_ids))
            .order_by(Submission.submitted_at.desc(), Submission.id.desc())
            .limit(limit)
            .all()
        )

    def get_aggregate_submission_activity(self, profile_ids: list[int]):
        activity_date = func.date(Submission.submitted_at).label("activity_date")
        accepted = func.coalesce(
            func.sum(
                case(
                    (Submission.status == SubmissionStatus.ACCEPTED, 1),
                    else_=0,
                )
            ),
            0,
        ).label("accepted_submissions")

        return (
            self.db.query(
                activity_date,
                func.count(Submission.id).label("total_submissions"),
                accepted,
            )
            .filter(Submission.profile_id.in_(profile_ids))
            .group_by(activity_date)
            .order_by(activity_date.asc())
            .all()
        )

    def get_rating_history(self, profile_id: int):
        return (
            self.db.query(RatingHistory, Contest)
            .outerjoin(Contest, RatingHistory.contest_id == Contest.id)
            .filter(RatingHistory.profile_id == profile_id)
            .order_by(RatingHistory.recorded_at.asc(), RatingHistory.id.asc())
            .all()
        )

    def get_contest_history(self, profile_id: int):
        return (
            self.db.query(ContestParticipation, Contest)
            .join(Contest, ContestParticipation.contest_id == Contest.id)
            .filter(ContestParticipation.profile_id == profile_id)
            .order_by(Contest.start_time.desc(), Contest.id.desc())
            .all()
        )

    def get_aggregate_contest_history(self, profile_ids: list[int]):
        return (
            self.db.query(ContestParticipation, Contest)
            .join(Contest, ContestParticipation.contest_id == Contest.id)
            .filter(ContestParticipation.profile_id.in_(profile_ids))
            .order_by(Contest.start_time.desc(), Contest.id.desc())
            .all()
        )
