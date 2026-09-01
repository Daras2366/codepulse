"""Analytics service.

Architecture:
    router
        → AnalyticsService          (this module)
            → AnalyticsRepository   (delegates to DashboardRepository)
            → PlatformProfileRepository (ownership check)

All methods follow the same ownership guard pattern used by DashboardService:
1. Look up the PlatformProfile.
2. Raise a typed exception if the profile does not belong to the current user.
3. Call the repository layer.
4. Map raw rows to typed Pydantic schemas.

No raw SQLAlchemy queries inside this service.
"""

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.enums import Difficulty, SubmissionStatus, Platform

from app.models.platform_profile import PlatformProfile
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.platform_profile_repository import PlatformProfileRepository
from app.schemas.analytics import (
    AggregateActivityDay,
    AggregateDifficultyDistributionResponse,
    AggregateDifficultyPoint,
    AggregatePlatformDifficulty,
    AggregateRatingPoint,
    AggregateRatingProgressionResponse,
    AggregateRatingSeries,
    AggregateSubmissionActivityResponse,
    AggregateTopicBreakdownResponse,
    AggregateTopicPoint,
    AnalyticsActivityDay,
    AnalyticsContestEntry,
    AnalyticsContestPerformanceResponse,
    AnalyticsDifficultyBucket,
    AnalyticsDifficultyDistributionResponse,
    AnalyticsRatingPoint,
    AnalyticsRatingProgressionResponse,
    AnalyticsSubmissionActivityResponse,
    AnalyticsSummaryResponse,
    PlatformSolvedCoverage,
)

from app.models.enums import Platform


# ---------------------------------------------------------------------------
# Typed service exceptions
# ---------------------------------------------------------------------------


class AnalyticsProfileNotFoundError(ValueError):
    """Raised when the requested platform profile does not exist."""


class AnalyticsProfileAccessDeniedError(PermissionError):
    """Raised when the authenticated user requests another user's profile."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AnalyticsService:
    def __init__(self, db: Session) -> None:
        self._profiles = PlatformProfileRepository(db)
        self._repo = AnalyticsRepository(db)

    # ------------------------------------------------------------------
    # Topic breakdown (canonical DSA taxonomy)
    # ------------------------------------------------------------------

    def get_aggregate_topic_breakdown(
        self,
        user_id: int,
        platforms: list[str] | None = None,
    ) -> AggregateTopicBreakdownResponse:
        """Return canonical DSA topic breakdown for selected platforms.

        Raw platform tags are converted into CodePulse's canonical taxonomy.
        Each problem is counted at most once per canonical topic.

        For LeetCode: uses PlatformProfile.problems_solved and PlatformTopicStat.
        For Codeforces: uses local ProblemTopic data from submissions.
        """

        from app.models.enums import Platform
        from app.services.topic_taxonomy import canonicalize_topic

        # --------------------------------------------------------------
        # 1. Resolve user's profiles
        # --------------------------------------------------------------

        profiles = self._profiles.get_by_user_id(user_id)

        if platforms:
            valid_platforms: list[Platform] = []

            for platform in platforms:
                try:
                    valid_platforms.append(Platform(platform))
                except ValueError:
                    continue

            profiles = [
                profile
                for profile in profiles
                if profile.platform in valid_platforms
            ]

        if not profiles:
            return AggregateTopicBreakdownResponse(
                total_solved=0,
                tagged_solved=0,
                total_topic_assignments=0,
                topics=[],
                platform_coverage=[],
            )

        # --------------------------------------------------------------
        # 2. Separate LeetCode and other platforms
        # --------------------------------------------------------------

        leetcode_profiles = [
            profile
            for profile in profiles
            if profile.platform == Platform.LEETCODE
        ]

        other_profiles = [
            profile
            for profile in profiles
            if profile.platform != Platform.LEETCODE
        ]

        # --------------------------------------------------------------
        # 3. Get problem-level topic data for non-LeetCode platforms
        # --------------------------------------------------------------

        topic_counts: dict[str, int] = {}
        problem_topics: dict[int, set[str]] = {}

        if other_profiles:
            other_profile_ids = [p.id for p in other_profiles]
            other_platform_enums = [p.platform for p in other_profiles]

            (
                topic_rows,
                _,
                raw_tagged_solved,
            ) = self._repo.get_aggregate_topic_breakdown(
                other_profile_ids,
                other_platform_enums,
            )

            for row in topic_rows:
                canonical_topic = canonicalize_topic(row.topic_name)

                if canonical_topic is None:
                    continue

                problem_id = int(row.problem_id)

                if problem_id not in problem_topics:
                    problem_topics[problem_id] = set()

                problem_topics[problem_id].add(canonical_topic)

            for canonical_topics in problem_topics.values():
                for topic in canonical_topics:
                    topic_counts[topic] = (
                        topic_counts.get(topic, 0) + 1
                    )

        # --------------------------------------------------------------
        # 4. Add LeetCode profile-level topic statistics
        # --------------------------------------------------------------

        leetcode_profile_ids = [p.id for p in leetcode_profiles]
        leetcode_profiles_with_topic_stats = set()

        if leetcode_profile_ids:
            leetcode_rows = self._repo.get_leetcode_topic_stats(
                leetcode_profile_ids
            )

            for row in leetcode_rows:
                canonical_topic = canonicalize_topic(row.topic_name)

                if canonical_topic is None:
                    continue

                topic_counts[canonical_topic] = (
                    topic_counts.get(canonical_topic, 0)
                    + int(row.solved_count)
                )

            if leetcode_rows:
                leetcode_profiles_with_topic_stats.update(leetcode_profile_ids)

        # --------------------------------------------------------------
        # 5. Calculate total_solved from profile data
        # --------------------------------------------------------------

        # For LeetCode, use profile.problems_solved directly
        # For other platforms, use repository query
        total_solved = 0

        if leetcode_profiles:
            total_solved += sum(p.problems_solved or 0 for p in leetcode_profiles)

        if other_profiles:
            other_profile_ids = [p.id for p in other_profiles]
            other_platform_enums = [p.platform for p in other_profiles]
            _, repo_total_solved, _ = self._repo.get_aggregate_topic_breakdown(
                other_profile_ids,
                other_platform_enums,
            )
            total_solved += int(repo_total_solved or 0)

        # --------------------------------------------------------------
        # 6. Calculate tagged_solved
        # --------------------------------------------------------------

        # For LeetCode: if topic stats exist, tagged_solved = total_solved
        # (topic data is available for the complete solved population)
        # For other platforms: use local problem-topic data
        tagged_solved = 0

        if leetcode_profiles:
            for profile in leetcode_profiles:
                if profile.id in leetcode_profiles_with_topic_stats:
                    tagged_solved += int(profile.problems_solved or 0)

        if other_profiles:
            tagged_solved += raw_tagged_solved

        # --------------------------------------------------------------
        # 7. Build final response
        # --------------------------------------------------------------

        if not topic_counts:
            return AggregateTopicBreakdownResponse(
                total_solved=int(total_solved),
                tagged_solved=tagged_solved,
                total_topic_assignments=0,
                topics=[],
                platform_coverage=self._build_platform_coverage(
                    profiles,
                    problem_topics,
                    leetcode_profiles_with_topic_stats,
                ),
            )

        # --------------------------------------------------------------
        # 8. Aggregate canonical topics
        # --------------------------------------------------------------

        total_topic_assignments = sum(topic_counts.values())

        # --------------------------------------------------------------
        # 9. Sort topics by frequency
        # --------------------------------------------------------------

        sorted_topics = sorted(
            topic_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )

        # --------------------------------------------------------------
        # 10. Keep only the top 7 topics
        # --------------------------------------------------------------

        TOP_TOPIC_LIMIT = 7

        top_topics = sorted_topics[:TOP_TOPIC_LIMIT]
        remaining_topics = sorted_topics[TOP_TOPIC_LIMIT:]

        topics: list[AggregateTopicPoint] = []

        for topic_name, count in top_topics:
            percentage = (
                round((count / total_topic_assignments) * 100, 1)
                if total_topic_assignments > 0
                else 0.0
            )

            topics.append(
                AggregateTopicPoint(
                    topic=topic_name,
                    solved_count=count,
                    percentage=percentage,
                )
            )

        # --------------------------------------------------------------
        # 11. Combine remaining topics into "Other"
        # --------------------------------------------------------------

        if remaining_topics:
            other_count = sum(
                count
                for _, count in remaining_topics
            )

            other_percentage = (
                round((other_count / total_topic_assignments) * 100, 1)
                if total_topic_assignments > 0
                else 0.0
            )

            topics.append(
                AggregateTopicPoint(
                    topic="Other",
                    solved_count=other_count,
                    percentage=other_percentage,
                )
            )

        return AggregateTopicBreakdownResponse(
            total_solved=int(total_solved),
            tagged_solved=tagged_solved,
            total_topic_assignments=total_topic_assignments,
            topics=topics,
            platform_coverage=self._build_platform_coverage(
                profiles,
                problem_topics,
                leetcode_profiles_with_topic_stats,
            ),
        )

    def _build_platform_coverage(
        self,
        profiles: list[PlatformProfile],
        problem_topics: dict[int, set[str]],
        leetcode_profiles_with_topic_stats: set[int],
    ) -> list[PlatformSolvedCoverage]:
        """Return per-platform solved and canonical-topic coverage.

        For LeetCode: uses PlatformProfile.problems_solved directly.
        For other platforms: uses repository queries based on local problem-topic data.
        """

        tagged_problem_ids = set(problem_topics.keys())

        # Group profiles by platform
        profiles_by_platform: dict[Platform, list[PlatformProfile]] = {}
        for profile in profiles:
            if profile.platform not in profiles_by_platform:
                profiles_by_platform[profile.platform] = []
            profiles_by_platform[profile.platform].append(profile)

        coverage: list[PlatformSolvedCoverage] = []

        for platform_enum, platform_profiles in profiles_by_platform.items():
            if platform_enum == Platform.LEETCODE:
                # LeetCode: sum profile.problems_solved across all LeetCode profiles
                total_solved = sum(p.problems_solved or 0 for p in platform_profiles)

                # If any profile has topic stats, tagged_solved = total_solved
                has_topic_stats = any(
                    p.id in leetcode_profiles_with_topic_stats
                    for p in platform_profiles
                )
                tagged_solved = total_solved if has_topic_stats else 0
            else:
                # Other platforms: use repository queries
                platform_profile_ids = [p.id for p in platform_profiles]
                platform_enums = [platform_enum]

                solved_by_platform = self._repo.get_solved_count_by_platform(
                    platform_profile_ids,
                    platform_enums,
                )

                total_solved = int(solved_by_platform.get(platform_enum, 0))
                tagged_solved = self._repo.get_tagged_solved_count_by_platform(
                    platform_profile_ids,
                    platform_enum,
                    tagged_problem_ids,
                )

            coverage.append(
                PlatformSolvedCoverage(
                    platform=platform_enum.value,
                    total_solved=total_solved,
                    tagged_solved=tagged_solved,
                )
            )

        return coverage

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_summary(
        self,
        profile_id: int,
        user_id: int,
    ) -> AnalyticsSummaryResponse:
        profile = self._get_profile(profile_id, user_id)
        summary = self._repo.get_submission_summary(profile.id)
        total = int(summary.total_submissions)
        accepted = int(summary.accepted_submissions)

        return AnalyticsSummaryResponse(
            profile_id=profile.id,
            platform=profile.platform,
            username=profile.username,
            total_submissions=total,
            accepted_submissions=accepted,
            rejected_submissions=total - accepted,
            solved_problems=int(summary.solved_count),
            contests_attended=self._repo.get_contests_attended_count(profile.id),
            current_rating=profile.current_rating,
            max_rating=profile.max_rating,
            rank=profile.rank,
        )

    def get_submission_activity(
        self,
        profile_id: int,
        user_id: int,
    ) -> AnalyticsSubmissionActivityResponse:
        profile = self._get_profile(profile_id, user_id)
        rows = self._repo.get_submission_activity(profile.id)
        activity = [
            AnalyticsActivityDay(
                date=row.activity_date,
                total_submissions=int(row.total_submissions),
                accepted_submissions=int(row.accepted_submissions),
                rejected_submissions=(
                    int(row.total_submissions) - int(row.accepted_submissions)
                ),
            )
            for row in rows
        ]
        return AnalyticsSubmissionActivityResponse(
            profile_id=profile.id,
            activity=activity,
        )

    def get_difficulty_distribution(
        self,
        profile_id: int,
        user_id: int,
    ) -> AnalyticsDifficultyDistributionResponse:
        profile = self._get_profile(profile_id, user_id)

        if profile.platform.value == "leetcode":
            buckets = [
                AnalyticsDifficultyBucket(
                    difficulty=Difficulty.EASY,
                    solved_count=int(profile.solved_easy),
                ),
                AnalyticsDifficultyBucket(
                    difficulty=Difficulty.MEDIUM,
                    solved_count=int(profile.solved_medium),
                ),
                AnalyticsDifficultyBucket(
                    difficulty=Difficulty.HARD,
                    solved_count=int(profile.solved_hard),
                ),
            ]
        else:
            rows = self._repo.get_solved_by_difficulty(profile.id)
            buckets = [
                AnalyticsDifficultyBucket(
                    difficulty=row.difficulty,
                    solved_count=int(row.solved_count),
                )
                for row in rows
            ]

        return AnalyticsDifficultyDistributionResponse(
            profile_id=profile.id,
            solved_by_difficulty=buckets,
        )

    def get_rating_progression(
        self,
        profile_id: int,
        user_id: int,
    ) -> AnalyticsRatingProgressionResponse:
        profile = self._get_profile(profile_id, user_id)
        rows = self._repo.get_rating_history(profile.id)
        history = [
            AnalyticsRatingPoint(
                contest_id=rating.contest_id,
                contest_name=contest.title if contest is not None else None,
                date=rating.recorded_at,
                rating=rating.rating,
                rating_change=rating.rating_change,
            )
            for rating, contest in rows
        ]
        return AnalyticsRatingProgressionResponse(
            profile_id=profile.id,
            current_rating=profile.current_rating,
            max_rating=profile.max_rating,
            history=history,
        )

    def get_contest_performance(
        self,
        profile_id: int,
        user_id: int,
    ) -> AnalyticsContestPerformanceResponse:
        profile = self._get_profile(profile_id, user_id)
        rows = self._repo.get_contest_history(profile.id)
        contests = [
            AnalyticsContestEntry(
                contest_id=contest.id,
                contest_name=contest.title,
                contest_url=contest.contest_url,
                date=contest.start_time,
                rank=participation.rank,
                old_rating=participation.old_rating,
                new_rating=participation.new_rating,
                rating_change=participation.rating_change,
                solved=participation.solved,
                penalty=participation.penalty,
            )
            for participation, contest in rows
        ]
        return AnalyticsContestPerformanceResponse(
            profile_id=profile.id,
            contests_attended=len(contests),
            contests=contests,
        )

    def get_aggregate_rating_progression(self, user_id: int, platforms: list[str] | None = None) -> AggregateRatingProgressionResponse:
        """Return rating history for selected platforms for the user."""
        from app.models.enums import Platform
        
        # Get user's profiles filtered by selected platforms
        profiles = self._profiles.get_by_user_id(user_id)
        if platforms:
            platforms_enums = [Platform(p) for p in platforms]
            profiles = [p for p in profiles if p.platform in platforms_enums]
        
        series = []
        for profile in profiles:
            rows = self._repo.get_rating_history(profile.id)
            # Sort chronologically by recorded_at
            sorted_rows = sorted(rows, key=lambda x: x[0].recorded_at if x[0].recorded_at else datetime.min)
            
            history = [
                AggregateRatingPoint(
                    date=rating.recorded_at.isoformat() if rating.recorded_at else None,
                    rating=rating.rating,
                    platform=profile.platform.value,
                )
                for rating, contest in sorted_rows
            ]
            series.append(AggregateRatingSeries(
                platform=profile.platform.value,
                username=profile.username,
                history=history,
            ))
        
        # Sort series chronologically within each series (already done above)
        # and ensure the overall response has proper timestamps
        return AggregateRatingProgressionResponse(series=series)


    def get_aggregate_difficulty_distribution(
        self, 
        user_id: int, 
        platforms: list[str] | None = None
    ) -> AggregateDifficultyDistributionResponse:
        """Return difficulty distribution for selected platforms."""
        from app.models.enums import Platform, Difficulty
        
        # Get user's profiles filtered by selected platforms
        profiles = self._profiles.get_by_user_id(user_id)
        if platforms:
            platforms_enums = [Platform(p) for p in platforms]
            profiles = [p for p in profiles if p.platform in platforms_enums]
        
        if not profiles:
            return AggregateDifficultyDistributionResponse(
                total_solved=0, 
                difficulties=[], 
                platform_totals=[]
            )
        
        # Aggregate difficulty counts across platforms
        # For LeetCode, use profile-level solved_easy/solved_medium/solved_hard
        # For Codeforces, use problem/submission data
        platform_totals = []
        total_easy = 0
        total_medium = 0
        total_hard = 0
        
        for profile in profiles:
            if profile.platform == Platform.LEETCODE:
                # LeetCode uses profile-level difficulty counts
                easy = getattr(profile, 'solved_easy', 0) or 0
                medium = getattr(profile, 'solved_medium', 0) or 0
                hard = getattr(profile, 'solved_hard', 0) or 0
                
                total_easy += easy
                total_medium += medium
                total_hard += hard
                
                platform_totals.append(AggregatePlatformDifficulty(
                    platform=profile.platform.value,
                    easy=easy,
                    medium=medium,
                    hard=hard
                ))
            else:
                # Codeforces and other platforms use problem/submission data
                platform_difficulty = (
                    self._repo.get_aggregate_difficulty_distribution([profile.id], [profile.platform])
                )
                
                easy = sum(row.solved_count for row in platform_difficulty if row.difficulty == Difficulty.EASY)
                medium = sum(row.solved_count for row in platform_difficulty if row.difficulty == Difficulty.MEDIUM)
                hard = sum(row.solved_count for row in platform_difficulty if row.difficulty == Difficulty.HARD)
                
                total_easy += easy
                total_medium += medium
                total_hard += hard
                
                platform_totals.append(AggregatePlatformDifficulty(
                    platform=profile.platform.value,
                    easy=easy,
                    medium=medium,
                    hard=hard
                ))
        
        total_solved = total_easy + total_medium + total_hard
        
        difficulties = []
        if total_solved > 0:
            if total_easy > 0:
                difficulties.append(AggregateDifficultyPoint(
                    difficulty="Easy",
                    solved_count=total_easy,
                    percentage=round((total_easy / total_solved) * 100, 1)
                ))
            if total_medium > 0:
                difficulties.append(AggregateDifficultyPoint(
                    difficulty="Medium",
                    solved_count=total_medium,
                    percentage=round((total_medium / total_solved) * 100, 1)
                ))
            if total_hard > 0:
                difficulties.append(AggregateDifficultyPoint(
                    difficulty="Hard",
                    solved_count=total_hard,
                    percentage=round((total_hard / total_solved) * 100, 1)
                ))
        
        return AggregateDifficultyDistributionResponse(
            total_solved=total_solved,
            difficulties=difficulties,
            platform_totals=platform_totals
        )

    def get_aggregate_submission_activity(
        self, 
        user_id: int, 
        platforms: list[str] | None = None,
        range_days: int | None = None
    ) -> AggregateSubmissionActivityResponse:
        """Return submission activity for selected platforms, optionally filtered by time range."""
        from app.models.enums import Platform
        from datetime import datetime, timedelta, date
        
        # Get user's profiles filtered by selected platforms
        profiles = self._profiles.get_by_user_id(user_id)
        if platforms:
            platforms_enums = [Platform(p) for p in platforms]
            profiles = [p for p in profiles if p.platform in platforms_enums]
        
        profile_ids = [p.id for p in profiles]
        
        if not profile_ids:
            return AggregateSubmissionActivityResponse(total_submissions=0, activity=[])
        
        # Calculate date range
        end_date = datetime.now().date()
        if range_days:
            start_date = end_date - timedelta(days=range_days)
        else:
            # Default to 1 year
            start_date = end_date - timedelta(days=365)
        
        # Call repository to get activity data
        activity_rows = self._repo.get_aggregate_submission_activity(profile_ids, start_date, end_date)
        
        total_submissions = sum(row.total for row in activity_rows)
        
        activity = [
            AggregateActivityDay(
                date=row.date,
                total_submissions=row.total,
                accepted_submissions=int(row.accepted or 0)
            )
            for row in activity_rows
        ]
        
        return AggregateSubmissionActivityResponse(total_submissions=total_submissions, activity=activity)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_profile(self, profile_id: int, user_id: int) -> PlatformProfile:
        profile = self._profiles.get_by_id(profile_id)
        if profile is None:
            raise AnalyticsProfileNotFoundError(
                f"Platform profile {profile_id} was not found."
            )
        if profile.user_id != user_id:
            raise AnalyticsProfileAccessDeniedError(
                f"You do not have permission to access platform profile {profile_id}."
            )
        return profile
