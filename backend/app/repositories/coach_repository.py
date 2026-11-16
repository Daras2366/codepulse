"""Repositories for AI Coach observability and feedback tables."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.coach import CoachFeedback, CoachRecommendation, CoachRun
from app.models.enums import CoachFeedbackAction
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.topic import Topic
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

    def get_recent_disliked_problems(
        self, user_id: int, since: datetime, limit: int = 20
    ) -> list[dict]:
        """Return only titles and topics for recently disliked recommendations."""
        rows = (
            self.db.query(CoachRecommendation.id, Problem.title)
            .join(CoachFeedback, CoachFeedback.recommendation_id == CoachRecommendation.id)
            .join(Problem, Problem.id == CoachRecommendation.problem_id)
            .filter(
                CoachRecommendation.user_id == user_id,
                CoachFeedback.action == CoachFeedbackAction.THUMBS_DOWN,
                CoachFeedback.created_at >= since,
            )
            .order_by(CoachFeedback.created_at.desc(), CoachFeedback.id.desc())
            .limit(limit)
            .all()
        )
        if not rows:
            return []
        recommendation_ids = [row.id for row in rows]
        topic_rows = (
            self.db.query(CoachRecommendation.id, Topic.name)
            .join(ProblemTopic, ProblemTopic.problem_id == CoachRecommendation.problem_id)
            .join(Topic, Topic.id == ProblemTopic.topic_id)
            .filter(CoachRecommendation.id.in_(recommendation_ids))
            .order_by(Topic.name)
            .all()
        )
        topics_by_id: dict[int, list[str]] = {rec_id: [] for rec_id in recommendation_ids}
        for rec_id, topic_name in topic_rows:
            topics_by_id[rec_id].append(topic_name)
        return [
            {"title": row.title, "topics": topics_by_id[row.id]}
            for row in rows
        ]

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
