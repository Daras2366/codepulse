"""Performance Analyzer Service.

Analyzes user's CodePulse data to produce structured performance insights
for recommendation engines, study plans, and AI coaches.

Architecture:
    Database → PerformanceAnalyzer → PerformanceProfile → Recommendation Engine

All metrics are calculated deterministically from stored data without LLM involvement.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import func, distinct, case
from sqlalchemy.orm import Session

from app.models.enums import Difficulty, Platform, SubmissionStatus
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.contest_participation import ContestParticipation
from app.models.rating_history import RatingHistory
from app.models.platform_profile import PlatformProfile
from app.models.platform_topic_stat import PlatformTopicStat
from app.models.topic import Topic
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.platform_profile_repository import PlatformProfileRepository
from app.schemas.analytics import (
    PerformanceProfile,
    PerformanceOverview,
    TopicPerformance,
    DifficultyPerformance,
    SubmissionBehavior,
    ContestPerformance,
    RatingTrend,
    StrengthItem,
    WeaknessItem,
    DataQuality,
)


class PerformanceAnalyzer:
    """Analyzes user data to produce structured performance insights."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._profiles = PlatformProfileRepository(db)
        self._analytics = AnalyticsRepository(db)

    def analyze_user_performance(self, user_id: int) -> PerformanceProfile:
        """Generate comprehensive performance profile for a user.

        Args:
            user_id: The user to analyze

        Returns:
            PerformanceProfile with all calculated metrics
        """
        profiles = self._profiles.get_by_user_id(user_id)

        if not profiles:
            return self._empty_profile()

        # Calculate all performance dimensions
        overview = self._calculate_overview(profiles)
        topic_performance = self._calculate_topic_performance(profiles)
        difficulty_performance = self._calculate_difficulty_performance(profiles)
        submission_behavior = self._calculate_submission_behavior(profiles)
        contest_performance = self._calculate_contest_performance(profiles)
        rating_trend = self._calculate_rating_trend(profiles)
        strengths, weaknesses = self._identify_strengths_weaknesses(
            overview, topic_performance, difficulty_performance,
            submission_behavior, contest_performance, rating_trend
        )
        data_quality = self._assess_data_quality(profiles)

        return PerformanceProfile(
            overview=overview,
            topic_performance=topic_performance,
            difficulty_performance=difficulty_performance,
            submission_behavior=submission_behavior,
            contest_performance=contest_performance,
            rating_trend=rating_trend,
            strengths=strengths,
            weaknesses=weaknesses,
            data_quality=data_quality,
        )

    def _empty_profile(self) -> PerformanceProfile:
        """Return empty profile for users with no data."""
        return PerformanceProfile(
            overview=PerformanceOverview(
                total_submissions=0,
                accepted_submissions=0,
                solved_problems=0,
                contests_attended=0,
                active_days=0,
                current_rating=None,
                max_rating=None,
            ),
            topic_performance=[],
            difficulty_performance=[],
            submission_behavior=SubmissionBehavior(
                total_submissions=0,
                accepted_submissions=0,
                acceptance_rate=None,
                average_submissions_per_active_day=0.0,
                longest_streak_days=0,
                current_streak_days=0,
                repeated_attempts_count=0,
            ),
            contest_performance=ContestPerformance(
                contests_participated=0,
                current_rating=None,
                max_rating=None,
                average_rating_change=None,
                recent_participation=0,
                participation_trend="insufficient_data",
            ),
            rating_trend=RatingTrend(
                current_rating=None,
                max_rating=None,
                rating_change_30_days=None,
                rating_change_90_days=None,
                trend_direction="insufficient_data",
                volatility_score=None,
            ),
            strengths=[],
            weaknesses=[],
            data_quality=DataQuality(
                has_complete_topic_data=False,
                has_complete_submission_history=False,
                has_complete_contest_history=False,
                profile_reported_solved=0,
                locally_tagged_solved=0,
                historical_coverage_days=0,
                platform_coverage=[],
            ),
        )

    def _calculate_overview(self, profiles: list[PlatformProfile]) -> PerformanceOverview:
        """Calculate high-level performance overview."""
        profile_ids = [p.id for p in profiles]

        # Aggregate statistics across all profiles
        total_submissions = (
            self._db.query(func.count(Submission.id))
            .filter(Submission.profile_id.in_(profile_ids))
            .scalar() or 0
        )

        accepted_submissions = (
            self._db.query(func.count(Submission.id))
            .filter(
                Submission.profile_id.in_(profile_ids),
                Submission.status == SubmissionStatus.ACCEPTED,
            )
            .scalar() or 0
        )

        solved_problems = (
            self._db.query(func.count(distinct(Submission.problem_id)))
            .filter(
                Submission.profile_id.in_(profile_ids),
                Submission.status == SubmissionStatus.ACCEPTED,
            )
            .scalar() or 0
        )

        contests_attended = (
            self._db.query(func.count(ContestParticipation.id))
            .filter(ContestParticipation.profile_id.in_(profile_ids))
            .scalar() or 0
        )

        # Calculate active days
        active_days = (
            self._db.query(func.count(func.date(Submission.submitted_at)))
            .filter(Submission.profile_id.in_(profile_ids))
            .distinct()
            .scalar() or 0
        )

        # Get current and max ratings
        current_rating = None
        max_rating = None
        for profile in profiles:
            if profile.current_rating is not None:
                if current_rating is None or profile.current_rating > current_rating:
                    current_rating = profile.current_rating
            if profile.max_rating is not None:
                if max_rating is None or profile.max_rating > max_rating:
                    max_rating = profile.max_rating

        return PerformanceOverview(
            total_submissions=total_submissions,
            accepted_submissions=accepted_submissions,
            solved_problems=solved_problems,
            contests_attended=contests_attended,
            active_days=active_days,
            current_rating=current_rating,
            max_rating=max_rating,
        )

    def _calculate_topic_performance(self, profiles: list[PlatformProfile]) -> list[TopicPerformance]:
        """Calculate topic-specific performance metrics."""
        profile_ids = [p.id for p in profiles]
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        # Get all platforms to determine data source
        has_leetcode = any(p.platform == Platform.LEETCODE for p in profiles)
        non_leetcode_profiles = [p for p in profiles if p.platform != Platform.LEETCODE]

        topic_performance: list[TopicPerformance] = []

        if has_leetcode and not non_leetcode_profiles:
            # LeetCode-only: use PlatformTopicStat
            leetcode_profile_ids = [p.id for p in profiles if p.platform == Platform.LEETCODE]
            topic_stats = self._db.query(
                PlatformTopicStat.topic_name,
                PlatformTopicStat.solved_count,
            ).filter(
                PlatformTopicStat.profile_id.in_(leetcode_profile_ids)
            ).all()

            total_solved = sum(p.problems_solved or 0 for p in profiles)

            for topic_name, solved_count in topic_stats:
                percentage = (solved_count / total_solved * 100) if total_solved > 0 else 0.0
                strength_level = self._classify_topic_strength(solved_count, total_solved)
                recent_activity = 0  # PlatformTopicStat doesn't have time data

                topic_performance.append(
                    TopicPerformance(
                        topic=topic_name,
                        solved_count=solved_count,
                        percentage=round(percentage, 1),
                        strength_level=strength_level,
                        recent_activity=recent_activity,
                    )
                )

        elif non_leetcode_profiles:
            # Mixed or non-LeetCode: use ProblemTopic
            non_leetcode_ids = [p.id for p in non_leetcode_profiles]

            # Get topic performance from submissions
            topic_results = (
                self._db.query(
                    Topic.name.label("topic"),
                    func.count(distinct(Submission.problem_id)).label("solved_count"),
                )
                .join(ProblemTopic, ProblemTopic.topic_id == Topic.id)
                .join(Problem, Problem.id == ProblemTopic.problem_id)
                .join(Submission, Submission.problem_id == Problem.id)
                .filter(
                    Submission.profile_id.in_(non_leetcode_ids),
                    Submission.status == SubmissionStatus.ACCEPTED,
                )
                .group_by(Topic.name)
                .all()
            )

            total_solved = (
                self._db.query(func.count(distinct(Submission.problem_id)))
                .filter(
                    Submission.profile_id.in_(non_leetcode_ids),
                    Submission.status == SubmissionStatus.ACCEPTED,
                )
                .scalar() or 0
            )

            for topic_name, solved_count in topic_results:
                percentage = (solved_count / total_solved * 100) if total_solved > 0 else 0.0
                strength_level = self._classify_topic_strength(solved_count, total_solved)

                # Calculate recent activity for this topic
                recent_solved = (
                    self._db.query(func.count(distinct(Submission.problem_id)))
                    .join(ProblemTopic, ProblemTopic.problem_id == Submission.problem_id)
                    .join(Topic, Topic.id == ProblemTopic.topic_id)
                    .filter(
                        Submission.profile_id.in_(non_leetcode_ids),
                        Submission.status == SubmissionStatus.ACCEPTED,
                        Topic.name == topic_name,
                        Submission.submitted_at >= thirty_days_ago,
                    )
                    .scalar() or 0
                )

                topic_performance.append(
                    TopicPerformance(
                        topic=topic_name,
                        solved_count=solved_count,
                        percentage=round(percentage, 1),
                        strength_level=strength_level,
                        recent_activity=recent_solved,
                    )
                )

        # Sort by solved count descending
        topic_performance.sort(key=lambda x: x.solved_count, reverse=True)
        return topic_performance

    def _classify_topic_strength(self, solved_count: int, total_solved: int) -> Literal["strong", "moderate", "weak", "insufficient_data"]:
        """Classify topic strength based on solved count relative to total."""
        if total_solved < 10:
            return "insufficient_data"
        if solved_count >= total_solved * 0.3:
            return "strong"
        if solved_count >= total_solved * 0.15:
            return "moderate"
        if solved_count >= total_solved * 0.05:
            return "weak"
        return "insufficient_data"

    def _calculate_difficulty_performance(self, profiles: list[PlatformProfile]) -> list[DifficultyPerformance]:
        """Calculate difficulty-specific performance metrics."""
        profile_ids = [p.id for p in profiles]
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        difficulty_performance: list[DifficultyPerformance] = []

        # Check if we have LeetCode profiles
        has_leetcode = any(p.platform == Platform.LEETCODE for p in profiles)
        non_leetcode_profiles = [p for p in profiles if p.platform != Platform.LEETCODE]

        if has_leetcode and not non_leetcode_profiles:
            # LeetCode-only: use profile-level difficulty counts
            total_easy = sum(p.solved_easy or 0 for p in profiles)
            total_medium = sum(p.solved_medium or 0 for p in profiles)
            total_hard = sum(p.solved_hard or 0 for p in profiles)

            total_solved = total_easy + total_medium + total_hard

            if total_solved > 0:
                for difficulty, count in [("Easy", total_easy), ("Medium", total_medium), ("Hard", total_hard)]:
                    if count > 0:
                        percentage = count / total_solved
                        coverage_status = self._classify_difficulty_coverage(percentage, count)
                        recent_activity = 0  # No time data from profile stats

                        difficulty_performance.append(
                            DifficultyPerformance(
                                difficulty=difficulty,
                                solved_count=count,
                                attempt_count=count,  # Approximate for LeetCode
                                acceptance_rate=None,  # Not available from profile stats
                                recent_activity=recent_activity,
                                coverage_status=coverage_status,
                            )
                        )

        elif non_leetcode_profiles:
            # Mixed or non-LeetCode: use Problem difficulty from submissions
            non_leetcode_ids = [p.id for p in non_leetcode_profiles]

            difficulty_results = (
                self._db.query(
                    Problem.difficulty.label("difficulty"),
                    func.count(distinct(Submission.problem_id)).label("solved_count"),
                    func.count(Submission.id).label("attempt_count"),
                )
                .join(Submission, Submission.problem_id == Problem.id)
                .filter(
                    Submission.profile_id.in_(non_leetcode_ids),
                )
                .group_by(Problem.difficulty)
                .all()
            )

            for difficulty, solved_count, attempt_count in difficulty_results:
                acceptance_rate = (solved_count / attempt_count) if attempt_count > 0 else None
                percentage = solved_count / (sum(r.solved_count for r in difficulty_results) or 1)
                coverage_status = self._classify_difficulty_coverage(percentage, solved_count)

                # Calculate recent activity for this difficulty
                recent_solved = (
                    self._db.query(func.count(distinct(Submission.problem_id)))
                    .join(Problem, Problem.id == Submission.problem_id)
                    .filter(
                        Submission.profile_id.in_(non_leetcode_ids),
                        Submission.status == SubmissionStatus.ACCEPTED,
                        Problem.difficulty == difficulty,
                        Submission.submitted_at >= thirty_days_ago,
                    )
                    .scalar() or 0
                )

                difficulty_performance.append(
                    DifficultyPerformance(
                        difficulty=str(difficulty) if difficulty else "Unknown",
                        solved_count=solved_count,
                        attempt_count=attempt_count,
                        acceptance_rate=round(acceptance_rate, 4) if acceptance_rate else None,
                        recent_activity=recent_solved,
                        coverage_status=coverage_status,
                    )
                )

        return difficulty_performance

    def _classify_difficulty_coverage(self, percentage: float, count: int) -> Literal["well_covered", "moderately_covered", "rarely_attempted", "not_attempted"]:
        """Classify difficulty coverage based on percentage and count."""
        if count == 0:
            return "not_attempted"
        if percentage >= 0.3:
            return "well_covered"
        if percentage >= 0.15:
            return "moderately_covered"
        if percentage >= 0.05:
            return "rarely_attempted"
        return "not_attempted"

    def _calculate_submission_behavior(self, profiles: list[PlatformProfile]) -> SubmissionBehavior:
        """Calculate submission behavior patterns."""
        profile_ids = [p.id for p in profiles]

        total_submissions = (
            self._db.query(func.count(Submission.id))
            .filter(Submission.profile_id.in_(profile_ids))
            .scalar() or 0
        )

        accepted_submissions = (
            self._db.query(func.count(Submission.id))
            .filter(
                Submission.profile_id.in_(profile_ids),
                Submission.status == SubmissionStatus.ACCEPTED,
            )
            .scalar() or 0
        )

        acceptance_rate = (accepted_submissions / total_submissions) if total_submissions > 0 else None

        # Calculate active days and averages
        active_days = (
            self._db.query(func.count(func.date(Submission.submitted_at)))
            .filter(Submission.profile_id.in_(profile_ids))
            .distinct()
            .scalar() or 0
        )

        average_submissions_per_day = (total_submissions / active_days) if active_days > 0 else 0.0

        # Calculate streaks
        longest_streak, current_streak = self._calculate_streaks(profile_ids)

        # Calculate repeated attempts (problems with multiple submissions)
        repeated_attempts = (
            self._db.query(func.count(distinct(Submission.problem_id)))
            .filter(
                Submission.profile_id.in_(profile_ids),
            )
            .group_by(Submission.problem_id)
            .having(func.count(Submission.id) > 1)
            .count()
        )

        return SubmissionBehavior(
            total_submissions=total_submissions,
            accepted_submissions=accepted_submissions,
            acceptance_rate=round(acceptance_rate, 4) if acceptance_rate else None,
            average_submissions_per_active_day=round(average_submissions_per_day, 2),
            longest_streak_days=longest_streak,
            current_streak_days=current_streak,
            repeated_attempts_count=repeated_attempts,
        )

    def _calculate_streaks(self, profile_ids: list[int]) -> tuple[int, int]:
        """Calculate longest and current submission streaks."""
        # Get all submission dates
        submission_dates = (
            self._db.query(func.date(Submission.submitted_at).label("date"))
            .filter(Submission.profile_id.in_(profile_ids))
            .distinct()
            .order_by(func.date(Submission.submitted_at).desc())
            .all()
        )

        if not submission_dates:
            return 0, 0

        dates = [row.date for row in submission_dates]
        longest_streak = 0
        current_streak = 0

        # Calculate current streak (consecutive days ending today)
        today = datetime.now(timezone.utc).date()
        for i, date in enumerate(dates):
            if date == today - timedelta(days=i):
                current_streak += 1
            else:
                break

        # Calculate longest streak
        if len(dates) >= 2:
            streak = 1
            for i in range(1, len(dates)):
                if (dates[i-1] - dates[i]).days == 1:
                    streak += 1
                else:
                    longest_streak = max(longest_streak, streak)
                    streak = 1
            longest_streak = max(longest_streak, streak)
        elif dates:
            longest_streak = 1

        return longest_streak, current_streak

    def _calculate_contest_performance(self, profiles: list[PlatformProfile]) -> ContestPerformance:
        """Calculate contest participation and performance."""
        profile_ids = [p.id for p in profiles]

        contests_participated = (
            self._db.query(func.count(ContestParticipation.id))
            .filter(ContestParticipation.profile_id.in_(profile_ids))
            .scalar() or 0
        )

        # Get rating info from profiles
        current_rating = None
        max_rating = None
        for profile in profiles:
            if profile.current_rating is not None:
                if current_rating is None or profile.current_rating > current_rating:
                    current_rating = profile.current_rating
            if profile.max_rating is not None:
                if max_rating is None or profile.max_rating > max_rating:
                    max_rating = profile.max_rating

        # Calculate average rating change
        rating_changes = (
            self._db.query(ContestParticipation.rating_change)
            .filter(
                ContestParticipation.profile_id.in_(profile_ids),
                ContestParticipation.rating_change.isnot(None),
            )
            .all()
        )

        average_rating_change = None
        if rating_changes:
            average_rating_change = sum(change[0] for change in rating_changes) / len(rating_changes)

        # Calculate recent participation (last 90 days)
        ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)
        recent_participation = (
            self._db.query(func.count(ContestParticipation.id))
            .join(Contest, Contest.id == ContestParticipation.contest_id)
            .filter(
                ContestParticipation.profile_id.in_(profile_ids),
                Contest.start_time >= ninety_days_ago,
            )
            .scalar() or 0
        )

        # Determine participation trend
        participation_trend = self._classify_participation_trend(recent_participation, contests_participated)

        return ContestPerformance(
            contests_participated=contests_participated,
            current_rating=current_rating,
            max_rating=max_rating,
            average_rating_change=round(average_rating_change, 2) if average_rating_change else None,
            recent_participation=recent_participation,
            participation_trend=participation_trend,
        )

    def _classify_participation_trend(self, recent: int, total: int) -> Literal["increasing", "stable", "decreasing", "insufficient_data"]:
        """Classify contest participation trend."""
        if total < 3:
            return "insufficient_data"
        if recent >= total * 0.5:
            return "increasing"
        if recent >= total * 0.25:
            return "stable"
        return "decreasing"

    def _calculate_rating_trend(self, profiles: list[PlatformProfile]) -> RatingTrend:
        """Calculate rating progression analysis."""
        profile_ids = [p.id for p in profiles]

        # Get current and max ratings from profiles
        current_rating = None
        max_rating = None
        for profile in profiles:
            if profile.current_rating is not None:
                if current_rating is None or profile.current_rating > current_rating:
                    current_rating = profile.current_rating
            if profile.max_rating is not None:
                if max_rating is None or profile.max_rating > max_rating:
                    max_rating = profile.max_rating

        # Calculate rating changes over time
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        ninety_days_ago = datetime.now(timezone.utc) - timedelta(days=90)

        rating_change_30_days = self._calculate_rating_change(profile_ids, thirty_days_ago)
        rating_change_90_days = self._calculate_rating_change(profile_ids, ninety_days_ago)

        # Determine trend direction
        trend_direction = self._classify_rating_trend(rating_change_30_days, rating_change_90_days)

        # Calculate volatility score
        volatility_score = self._calculate_volatility(profile_ids)

        return RatingTrend(
            current_rating=current_rating,
            max_rating=max_rating,
            rating_change_30_days=rating_change_30_days,
            rating_change_90_days=rating_change_90_days,
            trend_direction=trend_direction,
            volatility_score=round(volatility_score, 2) if volatility_score else None,
        )

    def _calculate_rating_change(self, profile_ids: list[int], since: datetime) -> int | None:
        """Calculate rating change since a given date."""
        # Get oldest rating before the date and newest rating after
        old_rating = (
            self._db.query(RatingHistory.rating)
            .join(ContestParticipation, ContestParticipation.id == RatingHistory.participation_id)
            .join(Contest, Contest.id == ContestParticipation.contest_id)
            .filter(
                ContestParticipation.profile_id.in_(profile_ids),
                Contest.start_time < since,
            )
            .order_by(Contest.start_time.desc())
            .first()
        )

        new_rating = (
            self._db.query(RatingHistory.rating)
            .join(ContestParticipation, ContestParticipation.id == RatingHistory.participation_id)
            .join(Contest, Contest.id == ContestParticipation.contest_id)
            .filter(
                ContestParticipation.profile_id.in_(profile_ids),
                Contest.start_time >= since,
            )
            .order_by(Contest.start_time.asc())
            .first()
        )

        if old_rating and new_rating:
            return new_rating[0] - old_rating[0]
        return None

    def _classify_rating_trend(self, change_30: int | None, change_90: int | None) -> Literal["improving", "stable", "declining", "insufficient_data"]:
        """Classify rating trend direction."""
        if change_30 is None and change_90 is None:
            return "insufficient_data"
        if change_30 is not None:
            if change_30 > 20:
                return "improving"
            if change_30 < -20:
                return "declining"
        return "stable"

    def _calculate_volatility(self, profile_ids: list[int]) -> float | None:
        """Calculate rating volatility score (0-1 scale)."""
        rating_changes = (
            self._db.query(ContestParticipation.rating_change)
            .filter(
                ContestParticipation.profile_id.in_(profile_ids),
                ContestParticipation.rating_change.isnot(None),
            )
            .all()
        )

        if len(rating_changes) < 3:
            return None

        changes = [change[0] for change in rating_changes]
        avg_change = sum(changes) / len(changes)
        variance = sum((x - avg_change) ** 2 for x in changes) / len(changes)
        std_dev = variance ** 0.5

        # Normalize to 0-1 scale (higher = more volatile)
        max_expected_std = 50  # Assuming 50 is high volatility
        volatility_score = min(std_dev / max_expected_std, 1.0)

        return volatility_score

    def _identify_strengths_weaknesses(
        self,
        overview: PerformanceOverview,
        topic_performance: list[TopicPerformance],
        difficulty_performance: list[DifficultyPerformance],
        submission_behavior: SubmissionBehavior,
        contest_performance: ContestPerformance,
        rating_trend: RatingTrend,
    ) -> tuple[list[StrengthItem], list[WeaknessItem]]:
        """Identify structured strengths and weaknesses based on metrics."""
        strengths: list[StrengthItem] = []
        weaknesses: list[WeaknessItem] = []

        # Topic strengths/weaknesses
        strong_topics = [t for t in topic_performance if t.strength_level == "strong"]
        weak_topics = [t for t in topic_performance if t.strength_level == "weak"]

        for topic in strong_topics[:3]:  # Top 3 strong topics
            strengths.append(
                StrengthItem(
                    category="topic",
                    description=f"Strong performance in {topic.topic}",
                    supporting_metric="solved_count",
                    metric_value=topic.solved_count,
                )
            )

        for topic in weak_topics[:3]:  # Top 3 weak topics
            weaknesses.append(
                WeaknessItem(
                    category="topic",
                    description=f"Relatively weak in {topic.topic}",
                    supporting_metric="solved_count",
                    metric_value=topic.solved_count,
                    confidence="medium" if topic.solved_count > 5 else "low",
                )
            )

        # Difficulty strengths/weaknesses
        well_covered = [d for d in difficulty_performance if d.coverage_status == "well_covered"]
        rarely_attempted = [d for d in difficulty_performance if d.coverage_status == "rarely_attempted"]

        for diff in well_covered:
            strengths.append(
                StrengthItem(
                    category="difficulty",
                    description=f"Well-covered difficulty: {diff.difficulty}",
                    supporting_metric="solved_count",
                    metric_value=diff.solved_count,
                )
            )

        for diff in rarely_attempted:
            weaknesses.append(
                WeaknessItem(
                    category="difficulty",
                    description=f"Rarely attempts {diff.difficulty} problems",
                    supporting_metric="solved_count",
                    metric_value=diff.solved_count,
                    confidence="high" if diff.solved_count == 0 else "medium",
                )
            )

        # Consistency strengths/weaknesses
        if submission_behavior.current_streak_days >= 7:
            strengths.append(
                StrengthItem(
                    category="consistency",
                    description=f"Current {submission_behavior.current_streak_days}-day active streak",
                    supporting_metric="current_streak_days",
                    metric_value=submission_behavior.current_streak_days,
                )
            )

        if submission_behavior.longest_streak_days >= 14:
            strengths.append(
                StrengthItem(
                    category="consistency",
                    description=f"Strong consistency: {submission_behavior.longest_streak_days}-day longest streak",
                    supporting_metric="longest_streak_days",
                    metric_value=submission.longest_streak_days,
                )
            )

        if submission_behavior.acceptance_rate and submission_behavior.acceptance_rate < 0.3:
            weaknesses.append(
                WeaknessItem(
                    category="consistency",
                    description="Low acceptance rate indicates room for improvement",
                    supporting_metric="acceptance_rate",
                    metric_value=submission_behavior.acceptance_rate,
                    confidence="high",
                )
            )

        # Contest strengths/weaknesses
        if contest_performance.contests_participated >= 10:
            strengths.append(
                StrengthItem(
                    category="contest",
                    description=f"Active contest participation: {contest_performance.contests_participated} contests",
                    supporting_metric="contests_participated",
                    metric_value=contest_performance.contests_participated,
                )
            )

        if contest_performance.participation_trend == "decreasing":
            weaknesses.append(
                WeaknessItem(
                    category="contest",
                    description="Declining contest participation trend",
                    supporting_metric="recent_participation",
                    metric_value=contest_performance.recent_participation,
                    confidence="medium",
                )
            )

        # Rating trend strengths/weaknesses
        if rating_trend.trend_direction == "improving":
            strengths.append(
                StrengthItem(
                    category="contest",
                    description="Improving rating trend",
                    supporting_metric="rating_change_30_days",
                    metric_value=rating_trend.rating_change_30_days or 0,
                )
            )

        if rating_trend.trend_direction == "declining":
            weaknesses.append(
                WeaknessItem(
                    category="contest",
                    description="Declining rating trend",
                    supporting_metric="rating_change_30_days",
                    metric_value=rating_trend.rating_change_30_days or 0,
                    confidence="high",
                )
            )

        return strengths, weaknesses

    def _assess_data_quality(self, profiles: list[PlatformProfile]) -> DataQuality:
        """Assess data coverage and quality."""
        profile_ids = [p.id for p in profiles]

        # Check topic data coverage
        has_leetcode = any(p.platform == Platform.LEETCODE for p in profiles)
        non_leetcode_profiles = [p for p in profiles if p.platform != Platform.LEETCODE]

        has_complete_topic_data = False
        if has_leetcode:
            leetcode_topic_stats = (
                self._db.query(func.count(PlatformTopicStat.id))
                .filter(PlatformTopicStat.profile_id.in_([p.id for p in profiles if p.platform == Platform.LEETCODE]))
                .scalar() or 0
            )
            has_complete_topic_data = leetcode_topic_stats > 0
        elif non_leetcode_profiles:
            non_leetcode_ids = [p.id for p in non_leetcode_profiles]
            topic_data = (
                self._db.query(func.count(ProblemTopic.id))
                .filter(ProblemTopic.problem_id.in_(
                    self._db.query(Submission.problem_id)
                    .filter(Submission.profile_id.in_(non_leetcode_ids))
                    .distinct()
                ))
                .scalar() or 0
            )
            has_complete_topic_data = topic_data > 0

        # Check submission history completeness
        total_submissions = (
            self._db.query(func.count(Submission.id))
            .filter(Submission.profile_id.in_(profile_ids))
            .scalar() or 0
        )
        has_complete_submission_history = total_submissions > 0

        # Check contest history completeness
        total_contests = (
            self._db.query(func.count(ContestParticipation.id))
            .filter(ContestParticipation.profile_id.in_(profile_ids))
            .scalar() or 0
        )
        has_complete_contest_history = total_contests > 0

        # Calculate solved counts
        profile_reported_solved = sum(p.problems_solved or 0 for p in profiles)

        locally_tagged_solved = 0
        if has_leetcode:
            locally_tagged_solved = profile_reported_solved  # LeetCode uses PlatformTopicStat
        elif non_leetcode_profiles:
            non_leetcode_ids = [p.id for p in non_leetcode_profiles]
            locally_tagged_solved = (
                self._db.query(func.count(distinct(Submission.problem_id)))
                .filter(
                    Submission.profile_id.in_(non_leetcode_ids),
                    Submission.status == SubmissionStatus.ACCEPTED,
                )
                .scalar() or 0
            )

        # Calculate historical coverage
        earliest_submission = (
            self._db.query(func.min(Submission.submitted_at))
            .filter(Submission.profile_id.in_(profile_ids))
            .scalar()
        )

        historical_coverage_days = 0
        if earliest_submission:
            historical_coverage_days = (datetime.now(timezone.utc) - earliest_submission).days

        # Platform coverage
        platform_coverage = [p.platform.value for p in profiles]

        return DataQuality(
            has_complete_topic_data=has_complete_topic_data,
            has_complete_submission_history=has_complete_submission_history,
            has_complete_contest_history=has_complete_contest_history,
            profile_reported_solved=profile_reported_solved,
            locally_tagged_solved=locally_tagged_solved,
            historical_coverage_days=historical_coverage_days,
            platform_coverage=platform_coverage,
        )