"""Analytics-specific aggregate queries.

The DashboardRepository already implements the five core analytics queries
(submission activity, difficulty distribution, rating history, contest history,
submission summary).  This repository adds only one piece that the dashboard
layer does not expose: the contests-attended scalar count broken out here so
that the analytics service does not need to instantiate DashboardRepository
solely for that scalar.

All heavy aggregation lives in DashboardRepository; this module reuses it.
"""

from datetime import datetime, timedelta
from typing import List

from sqlalchemy import func, distinct, case
from sqlalchemy.orm import Session

from app.models.enums import Difficulty, SubmissionStatus, Platform
from app.models.problem import Problem
from app.models.topic import Topic
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.repositories.dashboard_repository import DashboardRepository


class AnalyticsRepository:
    """Thin wrapper that exposes the DashboardRepository queries under the
    analytics namespace.  Having a distinct class keeps the analytics service
    decoupled from the dashboard service while avoiding query duplication."""

    def __init__(self, db: Session) -> None:
        self._dashboard = DashboardRepository(db)
        self._db = db

    # ------------------------------------------------------------------
    # Delegated queries (no duplication of SQL logic)
    # ------------------------------------------------------------------

    def get_submission_summary(self, profile_id: int):
        """Return (total_submissions, solved_count, accepted_submissions)."""
        return self._dashboard.get_submission_summary(profile_id)

    def get_contests_attended_count(self, profile_id: int) -> int:
        return self._dashboard.get_contests_attended_count(profile_id)

    def get_submission_activity(self, profile_id: int):
        """Return per-day submission rows (activity_date, total, accepted)."""
        return self._dashboard.get_submission_activity(profile_id)

    def get_solved_by_difficulty(self, profile_id: int):
        """Return (difficulty, solved_count) rows."""
        return self._dashboard.get_solved_by_difficulty(profile_id)

    def get_rating_history(self, profile_id: int):
        """Return (RatingHistory, Contest | None) rows ordered by date."""
        return self._dashboard.get_rating_history(profile_id)

    def get_contest_history(self, profile_id: int):
        """Return (ContestParticipation, Contest) rows ordered by date desc."""
        return self._dashboard.get_contest_history(profile_id)

    # ------------------------------------------------------------------
    # Aggregate queries for multi-platform analytics
    # ------------------------------------------------------------------

    def get_aggregate_topic_breakdown(self, profile_ids: List[int], platforms: List[Platform]):
        """Return topic breakdown for selected profiles and platforms.
        
        Counts distinct solved problems per topic. A problem with multiple topics
        contributes to each topic separately, but only once per topic.
        
        Also returns total solved count and tagged solved count.
        """
        # Subquery: get distinct solved problems for the selected profiles/platforms
        solved_problems_subquery = (
            self._db.query(
                Problem.id.label('problem_id'),
                Problem.platform
            )
            .join(Submission, Submission.problem_id == Problem.id)
            .filter(
                Submission.profile_id.in_(profile_ids),
                Submission.status == SubmissionStatus.ACCEPTED,
                Problem.platform.in_(platforms)
            )
            .distinct()
            .subquery()
        )
        
        # Count total solved problems
        total_solved = (
            self._db.query(func.count(distinct(solved_problems_subquery.c.problem_id)))
            .scalar()
        ) or 0
        
        # Count tagged solved problems (problems with at least one topic)
        tagged_solved = (
            self._db.query(func.count(distinct(solved_problems_subquery.c.problem_id)))
            .join(ProblemTopic, ProblemTopic.problem_id == solved_problems_subquery.c.problem_id)
            .scalar()
        ) or 0
        
        # Main query: count solved problems by topic
        topic_query = (
            self._db.query(
                Topic.name,
                func.count(distinct(solved_problems_subquery.c.problem_id)).label('solved_count')
            )
            .join(ProblemTopic, ProblemTopic.topic_id == Topic.id)
            .join(
                solved_problems_subquery, 
                solved_problems_subquery.c.problem_id == ProblemTopic.problem_id
            )
            .group_by(Topic.name)
            .all()
        )
        
        return topic_query, total_solved, tagged_solved

    def get_aggregate_difficulty_distribution(self, profile_ids: List[int], platforms: List[Platform]):
        """Return difficulty distribution for selected profiles and platforms."""
        # Query: get distinct solved problems by difficulty for selected profiles
        difficulty_query = (
            self._db.query(
                Problem.difficulty,
                func.count(distinct(Problem.id)).label('solved_count')
            )
            .join(Submission, Submission.problem_id == Problem.id)
            .filter(
                Submission.profile_id.in_(profile_ids),
                Submission.status == SubmissionStatus.ACCEPTED,
                Problem.platform.in_(platforms)
            )
            .group_by(Problem.difficulty)
            .all()
        )
        
        return difficulty_query

    def get_aggregate_submission_activity(self, profile_ids: List[int], start_date: datetime, end_date: datetime):
        """Return daily submission counts for selected profiles within date range."""
        activity_query = (
            self._db.query(
                func.date(Submission.submitted_at).label('date'),
                func.count(Submission.id).label('total'),
                func.sum(
                    case(
                        (Submission.status == SubmissionStatus.ACCEPTED, 1),
                        else_=0
                    )
                ).label('accepted')
            )
            .filter(
                Submission.profile_id.in_(profile_ids),
                func.date(Submission.submitted_at) >= start_date,
                func.date(Submission.submitted_at) <= end_date
            )
            .group_by(func.date(Submission.submitted_at))
            .order_by(func.date(Submission.submitted_at))
            .all()
        )
        
        return activity_query
