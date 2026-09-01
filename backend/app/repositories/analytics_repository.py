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
from app.models.platform_topic_stat import PlatformTopicStat
from app.models.platform_profile import PlatformProfile


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
        """Return raw (problem_id, topic_name) pairs for all solved tagged problems.

        Returns per-problem rows rather than pre-grouped counts so the service
        layer can:
          1. Canonicalise each raw tag via the taxonomy.
          2. Deduplicate canonical topics *per problem* before counting.

        This prevents a single problem from being counted multiple times for the
        same canonical category when it carries several raw tags that all map to
        that category (e.g. "graphs", "dfs and similar", "shortest paths" → Graphs ×1).

        Returns
        -------
        tuple[list[Row], int, int]
            (topic_rows, total_solved, raw_tagged_solved)

            * topic_rows        – list of rows with .problem_id and .topic_name
            * total_solved      – distinct solved problems matching the filter
            * raw_tagged_solved – distinct solved problems with ≥1 raw topic tag
        """
        # Subquery: distinct solved problem IDs for the selected profiles/platforms
        solved_problems_subquery = (
            self._db.query(
                Problem.id.label("problem_id"),
            )
            .join(Submission, Submission.problem_id == Problem.id)
            .filter(
                Submission.profile_id.in_(profile_ids),
                Submission.status == SubmissionStatus.ACCEPTED,
                Problem.platform.in_(platforms),
            )
            .distinct()
            .subquery()
        )

        # Total distinct solved problems
        total_solved = (
            self._db.query(func.count(solved_problems_subquery.c.problem_id)).scalar()
        ) or 0

        # Distinct solved problems that have ≥1 raw topic tag
        raw_tagged_solved = (
            self._db.query(
                func.count(distinct(solved_problems_subquery.c.problem_id))
            )
            .join(
                ProblemTopic,
                ProblemTopic.problem_id == solved_problems_subquery.c.problem_id,
            )
            .scalar()
        ) or 0

        # Per-problem topic rows: one row per (solved_problem, raw_tag) pair.
        # The service layer groups + canonicalises these.
        topic_rows = (
            self._db.query(
                solved_problems_subquery.c.problem_id.label("problem_id"),
                Topic.name.label("topic_name"),
            )
            .join(
                ProblemTopic,
                ProblemTopic.problem_id == solved_problems_subquery.c.problem_id,
            )
            .join(Topic, Topic.id == ProblemTopic.topic_id)
            .all()
        )

        return topic_rows, total_solved, raw_tagged_solved

    def get_solved_count_by_platform(
        self,
        profile_ids: List[int],
        platforms: List[Platform],
    ) -> dict:
        """Return {platform_name: distinct_solved_count} for each platform.

        Used to build the platform_coverage list in the topic breakdown
        response, so the frontend can accurately report which platforms
        have topic data and which do not.
        """
        rows = (
            self._db.query(
                Problem.platform.label("platform"),
                func.count(distinct(Problem.id)).label("solved_count"),
            )
            .join(Submission, Submission.problem_id == Problem.id)
            .filter(
                Submission.profile_id.in_(profile_ids),
                Submission.status == SubmissionStatus.ACCEPTED,
                Problem.platform.in_(platforms),
            )
            .group_by(Problem.platform)
            .all()
        )

        return {row.platform: int(row.solved_count) for row in rows}
    
    def get_tagged_solved_count_by_platform(
        self,
        profile_ids: List[int],
        platform: Platform,
        tagged_problem_ids: set[int],
    ) -> int:

        if not tagged_problem_ids:
            return 0

        count = (
            self._db.query(func.count(distinct(Problem.id)))
            .join(
                Submission,
                Submission.problem_id == Problem.id,
            )
            .filter(
                Submission.profile_id.in_(profile_ids),
                Submission.status == SubmissionStatus.ACCEPTED,
                Problem.platform == platform,
                Problem.id.in_(tagged_problem_ids),
            )
            .scalar()
        )

        return int(count or 0)

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

    def get_leetcode_topic_stats(
        self,
        profile_ids: list[int],
    ):
        return (
            self._db.query(
                PlatformTopicStat.topic_name,
                PlatformTopicStat.solved_count,
            )
            .join(
                PlatformProfile,
                PlatformProfile.id == PlatformTopicStat.profile_id,
            )
            .filter(
                PlatformTopicStat.profile_id.in_(profile_ids),
                PlatformProfile.platform == Platform.LEETCODE,
            )
            .all()
        )