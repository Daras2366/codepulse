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

        All platforms (including LeetCode) use locally stored ProblemTopic
        records so that counting semantics are consistent:

        * ``tagged_solved``         — distinct solved problems with ≥1
                                      canonical DSA topic tag in the local DB.
        * ``topic_counts[topic]``   — distinct solved problems assigned to
                                      that canonical topic (a problem tagged
                                      Arrays + DP contributes 1 to each).
        * ``total_topic_assignments`` — sum of all topic_counts values.

        Coverage note
        -------------
        LeetCode coverage is limited to locally synced submissions.  The
        frontend displays an honest "Topic data available for X of Y solved
        problems" note when X < Y.
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
        # 2. Fetch per-problem topic rows for ALL platforms via ProblemTopic
        #
        # Single, unified path for every platform including LeetCode.
        # Returns (problem_id, topic_name) pairs for every locally-stored
        # solved problem that has ≥1 topic tag.
        # --------------------------------------------------------------

        all_profile_ids = [p.id for p in profiles]
        all_platform_enums = [p.platform for p in profiles]

        # Check if we have LeetCode profiles
        has_leetcode = any(p.platform == Platform.LEETCODE for p in profiles)
        non_leetcode_profiles = [p for p in profiles if p.platform != Platform.LEETCODE]

        if has_leetcode and not non_leetcode_profiles:
            # LeetCode-only case: use PlatformTopicStat directly
            leetcode_profile_ids = [p.id for p in profiles if p.platform == Platform.LEETCODE]
            leetcode_topic_stats = self._repo.get_leetcode_topic_stats(leetcode_profile_ids)

            # Convert PlatformTopicStat rows to topic_counts format
            topic_counts: dict[str, int] = {}
            for topic_name, solved_count in leetcode_topic_stats:
                canonical_topic = canonicalize_topic(topic_name)
                if canonical_topic:
                    topic_counts[canonical_topic] = topic_counts.get(canonical_topic, 0) + solved_count

            # Get total solved from profile for LeetCode
            total_solved = sum(p.problems_solved or 0 for p in profiles if p.platform == Platform.LEETCODE)
            tagged_solved = total_solved  # For LeetCode, PlatformTopicStat represents all solved problems

            return self._build_topic_breakdown_from_counts(
                topic_counts, total_solved, tagged_solved, profiles
            )

        if has_leetcode and non_leetcode_profiles:
            # Mixed platforms: need to combine LeetCode PlatformTopicStat with other platforms' ProblemTopic
            leetcode_profile_ids = [p.id for p in profiles if p.platform == Platform.LEETCODE]
            leetcode_topic_stats = self._repo.get_leetcode_topic_stats(leetcode_profile_ids)

            # Convert LeetCode PlatformTopicStat to topic_counts
            topic_counts: dict[str, int] = {}
            for topic_name, solved_count in leetcode_topic_stats:
                canonical_topic = canonicalize_topic(topic_name)
                if canonical_topic:
                    topic_counts[canonical_topic] = topic_counts.get(canonical_topic, 0) + solved_count

            # Get other platforms' topics via ProblemTopic
            non_leetcode_profile_ids = [p.id for p in non_leetcode_profiles]
            non_leetcode_platforms = [p.platform for p in non_leetcode_profiles]

            topic_rows, repo_total_solved, _raw_tagged = self._repo.get_aggregate_topic_breakdown(
                non_leetcode_profile_ids,
                non_leetcode_platforms,
            )

            # Process other platforms' topics
            problem_topics: dict[int, set[str]] = {}
            for row in topic_rows:
                canonical_topic = canonicalize_topic(row.topic_name)
                if canonical_topic is None:
                    continue
                problem_id = int(row.problem_id)
                if problem_id not in problem_topics:
                    problem_topics[problem_id] = set()
                problem_topics[problem_id].add(canonical_topic)

            # Merge other platforms' topics into topic_counts
            for canonical_topics_set in problem_topics.values():
                for topic in canonical_topics_set:
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1

            # Calculate totals
            leetcode_total_solved = sum(p.problems_solved or 0 for p in profiles if p.platform == Platform.LEETCODE)
            other_total_solved = int(repo_total_solved or 0)
            total_solved = leetcode_total_solved + other_total_solved
            tagged_solved = leetcode_total_solved + len(problem_topics)  # LeetCode fully tagged + other platforms' tagged

            return self._build_topic_breakdown_from_counts(
                topic_counts, total_solved, tagged_solved, profiles
            )

        (
            topic_rows,
            repo_total_solved,
            _raw_tagged,
        ) = self._repo.get_aggregate_topic_breakdown(
            all_profile_ids,
            all_platform_enums,
        )

        # --------------------------------------------------------------
        # 3. Canonicalise tags and build per-problem topic sets
        # --------------------------------------------------------------

        topic_counts: dict[str, int] = {}
        problem_topics: dict[int, set[str]] = {}

        for row in topic_rows:
            canonical_topic = canonicalize_topic(row.topic_name)

            if canonical_topic is None:
                continue

            problem_id = int(row.problem_id)

            if problem_id not in problem_topics:
                problem_topics[problem_id] = set()

            problem_topics[problem_id].add(canonical_topic)

        # Count distinct solved problems per canonical topic.
        for canonical_topics_set in problem_topics.values():
            for topic in canonical_topics_set:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1

        # --------------------------------------------------------------
        # 4. Compute aggregate totals
        # --------------------------------------------------------------

        # total_solved: distinct solved problems in DB across all platforms
        total_solved = int(repo_total_solved or 0)
        # tagged_solved: problems with ≥1 canonical DSA topic tag
        tagged_solved = len(problem_topics)

        return self._build_topic_breakdown_from_counts(
            topic_counts, total_solved, tagged_solved, profiles
        )

    def _build_topic_breakdown_from_counts(
        self,
        topic_counts: dict[str, int],
        total_solved: int,
        tagged_solved: int,
        profiles: list[PlatformProfile],
    ) -> AggregateTopicBreakdownResponse:
        """Build topic breakdown response from pre-computed topic counts."""
        from app.models.enums import Platform

        # --------------------------------------------------------------
        # 5. Build final response
        # --------------------------------------------------------------

        if not topic_counts:
            return AggregateTopicBreakdownResponse(
                total_solved=total_solved,
                tagged_solved=tagged_solved,
                total_topic_assignments=0,
                topics=[],
                platform_coverage=self._build_platform_coverage(
                    profiles,
                    {},  # Empty problem_topics for LeetCode-only case
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
            total_solved=total_solved,
            tagged_solved=tagged_solved,
            total_topic_assignments=total_topic_assignments,
            topics=topics,
            platform_coverage=self._build_platform_coverage(
                profiles,
                {},  # Empty problem_topics for LeetCode-only case
            ),
        )

        # --------------------------------------------------------------
        # 5. Build final response
        # --------------------------------------------------------------

        if not topic_counts:
            return AggregateTopicBreakdownResponse(
                total_solved=total_solved,
                tagged_solved=tagged_solved,
                total_topic_assignments=0,
                topics=[],
                platform_coverage=self._build_platform_coverage(
                    profiles,
                    problem_topics,
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
            total_solved=total_solved,
            tagged_solved=tagged_solved,
            total_topic_assignments=total_topic_assignments,
            topics=topics,
            platform_coverage=self._build_platform_coverage(
                profiles,
                problem_topics,
            ),
        )

    def _build_platform_coverage(
        self,
        profiles: list[PlatformProfile],
        problem_topics: dict[int, set[str]],
    ) -> list[PlatformSolvedCoverage]:
        """Return per-platform solved and canonical-topic coverage.

        Uses repository queries for all platforms (including LeetCode) so
        that coverage numbers reflect locally-stored data consistently.

        For LeetCode ``total_solved`` comes from ``profile.problems_solved``
        (the upstream API total) so the user can see the full gap between
        their actual solved count and the locally tagged subset.
        """
        from app.models.enums import Platform

        tagged_problem_ids = set(problem_topics.keys())

        # Group profiles by platform
        profiles_by_platform: dict[Platform, list[PlatformProfile]] = {}
        for profile in profiles:
            if profile.platform not in profiles_by_platform:
                profiles_by_platform[profile.platform] = []
            profiles_by_platform[profile.platform].append(profile)

        coverage: list[PlatformSolvedCoverage] = []

        for platform_enum, platform_profiles in profiles_by_platform.items():
            platform_profile_ids = [p.id for p in platform_profiles]

            if platform_enum == Platform.LEETCODE:
                # For LeetCode use the profile API total so the coverage note
                # shows the full 378 solved vs e.g. 23 locally tagged.
                total_solved = sum(p.problems_solved or 0 for p in platform_profiles)
                # For LeetCode with PlatformTopicStat, tagged_solved equals total_solved
                # Check if we have PlatformTopicStat data by querying it
                leetcode_topic_stats = self._repo.get_leetcode_topic_stats(platform_profile_ids)
                if leetcode_topic_stats:
                    # We have PlatformTopicStat data, so tagged_solved equals total_solved
                    tagged_solved = total_solved
                else:
                    # No PlatformTopicStat data, fall back to local problem topics
                    tagged_solved = self._repo.get_tagged_solved_count_by_platform(
                        platform_profile_ids,
                        platform_enum,
                        tagged_problem_ids,
                    )
            else:
                platform_enums_list = [platform_enum]
                solved_by_platform = self._repo.get_solved_count_by_platform(
                    platform_profile_ids,
                    platform_enums_list,
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
        from datetime import datetime, timedelta, timezone
        
        # Get user's profiles filtered by selected platforms
        profiles = self._profiles.get_by_user_id(user_id)
        if platforms:
            platforms_enums = [Platform(p) for p in platforms]
            profiles = [p for p in profiles if p.platform in platforms_enums]
        
        profile_ids = [p.id for p in profiles]
        
        if not profile_ids:
            return AggregateSubmissionActivityResponse(total_submissions=0, activity=[])
        
        # Calculate date range
        end_date = datetime.now(timezone.utc).date()
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
