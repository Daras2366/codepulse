"""Repositories for AI Coach observability and feedback tables."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.coach import CoachFeedback, CoachRecommendation, CoachRun
from app.models.enums import CoachFeedbackAction
from app.repositories.base import BaseRepository


class CoachRunRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def add(self, run: CoachRun) -> CoachRun:
        """Stage a run for insertion (flush only — caller commits)."""
        self.db.add(run)
        self.db.flush()
        return run

    def get_by_id(self, run_id: int) -> Optional[CoachRun]:
        return self.db.query(CoachRun).filter(CoachRun.id == run_id).first()


class CoachRecommendationRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def add_all(self, recommendations: List[CoachRecommendation]) -> List[CoachRecommendation]:
        """Stage recommendations for insertion (flush only — caller commits)."""
        self.db.add_all(recommendations)
        self.db.flush()
        return recommendations

    def get_by_id(self, recommendation_id: int) -> Optional[CoachRecommendation]:
        return (
            self.db.query(CoachRecommendation)
            .filter(CoachRecommendation.id == recommendation_id)
            .first()
        )

    def get_for_run(self, run_id: int) -> List[CoachRecommendation]:
        return (
            self.db.query(CoachRecommendation)
            .filter(CoachRecommendation.run_id == run_id)
            .order_by(CoachRecommendation.rank.asc())
            .all()
        )

    def get_matching_for_problem(
        self,
        user_id: int,
        problem_id: int,
        created_after: datetime,
        created_before: Optional[datetime] = None,
    ) -> List[CoachRecommendation]:
        """Recommendations for ``user_id`` on ``problem_id`` inside a window."""
        query = self.db.query(CoachRecommendation).filter(
            CoachRecommendation.user_id == user_id,
            CoachRecommendation.problem_id == problem_id,
            CoachRecommendation.created_at >= created_after,
        )
        if created_before is not None:
            query = query.filter(CoachRecommendation.created_at <= created_before)
        return query.all()


class CoachFeedbackRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_recommendation_and_action(
        self,
        recommendation_id: int,
        action: CoachFeedbackAction,
    ) -> Optional[CoachFeedback]:
        return (
            self.db.query(CoachFeedback)
            .filter(
                CoachFeedback.recommendation_id == recommendation_id,
                CoachFeedback.action == action,
            )
            .first()
        )

    def get_actions_for_recommendation(
        self,
        recommendation_id: int,
    ) -> List[CoachFeedbackAction]:
        rows = (
            self.db.query(CoachFeedback.action)
            .filter(CoachFeedback.recommendation_id == recommendation_id)
            .all()
        )
        return [row[0] for row in rows]

    def count_for_recommendations(
        self,
        recommendation_ids: List[int],
        action: CoachFeedbackAction,
    ) -> int:
        if not recommendation_ids:
            return 0
        return (
            self.db.query(func.count(CoachFeedback.id))
            .filter(
                CoachFeedback.recommendation_id.in_(recommendation_ids),
                CoachFeedback.action == action,
            )
            .scalar()
            or 0
        )

    def add(self, feedback: CoachFeedback) -> CoachFeedback:
        """Stage feedback for insertion (flush only — caller commits)."""
        self.db.add(feedback)
        self.db.flush()
        return feedback
