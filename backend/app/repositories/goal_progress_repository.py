"""Goal progress repository.

Per-type database queries used by GoalProgressCalculator.

All queries are user-scoped via PlatformProfile.user_id so a user with
multiple profiles on the same platform gets the correct aggregate.

Methods
-------
get_rating_for_platform(user_id, platform)
    Current rating from PlatformProfile for the given platform.

get_problems_solved_in_range(user_id, start_date, end_date, platform, difficulty)
    Distinct accepted problems in the date range, with optional platform /
    difficulty filters.

get_topic_solved_count_leetcode(user_id, topic_slug)
    LeetCode profile-level topic solved count from PlatformTopicStat.
    NOTE: These counts overlap — they are NOT unique solved problems.

get_topic_solved_count_codeforces(user_id, topic_slug, start_date, end_date)
    Count distinct problems solved with the given canonical topic tag
    on Codeforces, via ProblemTopic + Submission joins.

get_active_days_in_range(user_id, start_date, end_date, platform)
    Distinct submission days with at least one accepted submission.

get_contests_in_range(user_id, start_date, end_date, platform)
    Count of contest participations (via ContestParticipation JOIN Contest)
    in the date range.
"""

from datetime import date
from typing import Optional

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.enums import Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.platform_topic_stat import PlatformTopicStat
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
from app.repositories.base import BaseRepository


class GoalProgressRepository(BaseRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)

    # ------------------------------------------------------------------
    # RATING
    # ------------------------------------------------------------------

    def get_rating_for_platform(
        self,
        user_id: int,
        platform: str,
    ) -> int:
        """Return the user's current rating on the given platform.

        Returns 0 if no profile or no rating is stored.
        """
        profile = (
            self.db.query(PlatformProfile)
            .filter(
                PlatformProfile.user_id == user_id,
                PlatformProfile.platform == platform,
            )
            .first()
        )
        if profile is None or profile.current_rating is None:
            return 0
        return int(profile.current_rating)

    # ------------------------------------------------------------------
    # PROBLEMS / PLACEMENT
    # ------------------------------------------------------------------

    def get_problems_solved_in_range(
        self,
        user_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
        platform: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> int:
        """Count distinct accepted problems within the optional date range.

        Parameters
        ----------
        user_id:    CodePulse user id.
        start_date: Inclusive lower bound (None = no lower bound).
        end_date:   Inclusive upper bound (None = no upper bound).
        platform:   Optional platform slug to restrict the count.
        difficulty: Optional difficulty ("Easy", "Medium", "Hard") to restrict.
        """
        query = (
            self.db.query(func.count(distinct(Submission.problem_id)))
            .join(PlatformProfile, Submission.profile_id == PlatformProfile.id)
            .join(Problem, Submission.problem_id == Problem.id)
            .filter(
                PlatformProfile.user_id == user_id,
                Submission.status == SubmissionStatus.ACCEPTED,
            )
        )
        if start_date is not None:
            query = query.filter(func.date(Submission.submitted_at) >= start_date)
        if end_date is not None:
            query = query.filter(func.date(Submission.submitted_at) <= end_date)
        if platform is not None:
            query = query.filter(Problem.platform == platform)
        if difficulty is not None:
            query = query.filter(Problem.difficulty == difficulty)

        return int(query.scalar() or 0)

    # ------------------------------------------------------------------
    # TOPIC
    # ------------------------------------------------------------------

    def get_topic_solved_count_leetcode(
        self,
        user_id: int,
        topic_slug: str,
    ) -> int:
        """Return LeetCode profile-level solved count for the given topic slug.

        Uses PlatformTopicStat which is populated from LeetCode's
        tagProblemCounts API.  These counts are NOT unique problems — they
        are the number of accepted problems associated with that tag on the
        user's LeetCode account.
        """
        result = (
            self.db.query(func.sum(PlatformTopicStat.solved_count))
            .join(PlatformProfile, PlatformTopicStat.profile_id == PlatformProfile.id)
            .filter(
                PlatformProfile.user_id == user_id,
                PlatformProfile.platform == Platform.LEETCODE,
                PlatformTopicStat.topic_slug == topic_slug,
            )
            .scalar()
        )
        return int(result or 0)

    def get_topic_solved_count_codeforces(
        self,
        user_id: int,
        topic_slug: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        """Count distinct Codeforces problems solved with the given topic.

        Uses the ProblemTopic → Topic join to find tagged problems.
        The topic_slug is matched against Topic.name (lowercased, hyphenated)
        for Codeforces since CF topics are stored differently.
        """
        # Convert slug to possible topic name forms
        topic_name_from_slug = topic_slug.replace("-", " ")

        query = (
            self.db.query(func.count(distinct(Submission.problem_id)))
            .join(PlatformProfile, Submission.profile_id == PlatformProfile.id)
            .join(Problem, Submission.problem_id == Problem.id)
            .join(ProblemTopic, ProblemTopic.problem_id == Problem.id)
            .join(Topic, Topic.id == ProblemTopic.topic_id)
            .filter(
                PlatformProfile.user_id == user_id,
                PlatformProfile.platform == Platform.CODEFORCES,
                Submission.status == SubmissionStatus.ACCEPTED,
                func.lower(Topic.name) == func.lower(topic_name_from_slug),
            )
        )
        if start_date is not None:
            query = query.filter(func.date(Submission.submitted_at) >= start_date)
        if end_date is not None:
            query = query.filter(func.date(Submission.submitted_at) <= end_date)

        return int(query.scalar() or 0)

    # ------------------------------------------------------------------
    # CONSISTENCY
    # ------------------------------------------------------------------

    def get_active_days_in_range(
        self,
        user_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
        platform: Optional[str] = None,
    ) -> int:
        """Count distinct days with at least one accepted submission.

        A "coding day" = any calendar day with ≥1 accepted submission.
        Multiple accepted submissions on the same day count as one day.
        """
        query = (
            self.db.query(func.count(distinct(func.date(Submission.submitted_at))))
            .join(PlatformProfile, Submission.profile_id == PlatformProfile.id)
            .filter(
                PlatformProfile.user_id == user_id,
                Submission.status == SubmissionStatus.ACCEPTED,
            )
        )
        if start_date is not None:
            query = query.filter(func.date(Submission.submitted_at) >= start_date)
        if end_date is not None:
            query = query.filter(func.date(Submission.submitted_at) <= end_date)
        if platform is not None:
            query = query.join(Problem, Submission.problem_id == Problem.id).filter(
                Problem.platform == platform
            )

        return int(query.scalar() or 0)

    # ------------------------------------------------------------------
    # CONTEST
    # ------------------------------------------------------------------

    def get_contests_in_range(
        self,
        user_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
        platform: Optional[str] = None,
    ) -> int:
        """Count contest participations within the date range.

        Joins ContestParticipation → Contest to filter by contest start_time.
        """
        query = (
            self.db.query(func.count(ContestParticipation.id))
            .join(PlatformProfile, ContestParticipation.profile_id == PlatformProfile.id)
            .join(Contest, ContestParticipation.contest_id == Contest.id)
            .filter(PlatformProfile.user_id == user_id)
        )
        if start_date is not None:
            query = query.filter(func.date(Contest.start_time) >= start_date)
        if end_date is not None:
            query = query.filter(func.date(Contest.start_time) <= end_date)
        if platform is not None:
            query = query.filter(Contest.platform == platform)

        return int(query.scalar() or 0)
