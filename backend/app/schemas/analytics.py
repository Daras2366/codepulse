"""Pydantic response schemas for the Analytics API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, computed_field

from app.models.enums import Difficulty, Platform


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------


class AnalyticsSummaryResponse(BaseModel):
    """Aggregate statistics for a platform profile."""

    profile_id: int
    platform: Platform
    username: str
    total_submissions: int
    accepted_submissions: int
    rejected_submissions: int
    solved_problems: int
    contests_attended: int
    current_rating: int | None
    max_rating: int | None
    rank: str | None

    @computed_field  # type: ignore[misc]
    @property
    def acceptance_rate(self) -> float | None:
        """Acceptance rate as a fraction [0, 1], or None if no submissions."""
        if self.total_submissions == 0:
            return None
        return round(self.accepted_submissions / self.total_submissions, 4)


# ---------------------------------------------------------------------------
# Submission activity
# ---------------------------------------------------------------------------


class AnalyticsActivityDay(BaseModel):
    """Submission counts for a single calendar day."""

    date: date
    total_submissions: int
    accepted_submissions: int
    rejected_submissions: int


class AnalyticsSubmissionActivityResponse(BaseModel):
    profile_id: int
    activity: list[AnalyticsActivityDay]


# ---------------------------------------------------------------------------
# Difficulty distribution
# ---------------------------------------------------------------------------


class AnalyticsDifficultyBucket(BaseModel):
    difficulty: Difficulty
    solved_count: int


class AnalyticsDifficultyDistributionResponse(BaseModel):
    profile_id: int
    solved_by_difficulty: list[AnalyticsDifficultyBucket]


# ---------------------------------------------------------------------------
# Rating progression
# ---------------------------------------------------------------------------


class AnalyticsRatingPoint(BaseModel):
    """A single point on the rating chart."""

    contest_id: int | None
    contest_name: str | None
    date: datetime
    rating: int
    rating_change: int


class AnalyticsRatingProgressionResponse(BaseModel):
    profile_id: int
    current_rating: int | None
    max_rating: int | None
    history: list[AnalyticsRatingPoint]


# ---------------------------------------------------------------------------
# Contest performance
# ---------------------------------------------------------------------------


class AnalyticsContestEntry(BaseModel):
    """A single contest participation record."""

    contest_id: int
    contest_name: str
    contest_url: str
    date: datetime
    rank: int | None
    old_rating: int | None
    new_rating: int | None
    rating_change: int | None
    solved: int
    penalty: int | None


class AnalyticsContestPerformanceResponse(BaseModel):
    profile_id: int
    contests_attended: int
    contests: list[AnalyticsContestEntry]


# ---------------------------------------------------------------------------
# Aggregate rating progression
# ---------------------------------------------------------------------------


class AggregateRatingPoint(BaseModel):
    """A single rating point for aggregate view."""
    date: str
    rating: int
    platform: str


class AggregateRatingSeries(BaseModel):
    """Rating history for one platform."""
    platform: str
    username: str
    history: list[AggregateRatingPoint]


class AggregateRatingProgressionResponse(BaseModel):
    """Rating history for all connected platforms."""
    series: list[AggregateRatingSeries]


# ---------------------------------------------------------------------------
# Aggregate topic breakdown
# ---------------------------------------------------------------------------


class AggregateTopicPoint(BaseModel):
    """Topic count for aggregate view."""
    topic: str
    solved_count: int
    percentage: float


class PlatformSolvedCoverage(BaseModel):
    """Per-platform solved count and topic coverage.

    Used by the frontend to communicate which platforms have topic data
    and which do not.
    """
    platform: str
    total_solved: int
    tagged_solved: int


class AggregateTopicBreakdownResponse(BaseModel):
    """Topic breakdown for selected platforms.

    Fields:
        total_solved:
            Total distinct solved problems across the selected platforms.

        tagged_solved:
            Distinct solved problems that have at least one meaningful
            canonical DSA topic.

        total_topic_assignments:
            Total number of canonical topic assignments.

            A single problem can belong to multiple topics. For example,
            a problem mapped to Arrays, Binary Search, and Sorting contributes
            three topic assignments.

            This is the denominator used for donut percentages.

        topics:
            All canonical DSA topics with available data, sorted by
            assignment count in descending order.

        platform_coverage:
            Per-platform breakdown of total solved count and how many of
            those problems have canonical topic data. Used by the frontend
            to accurately communicate coverage limitations (e.g. LeetCode
            problems currently have no topic metadata).
    """

    total_solved: int
    tagged_solved: int
    total_topic_assignments: int
    topics: list[AggregateTopicPoint]
    platform_coverage: list[PlatformSolvedCoverage] = []


# ---------------------------------------------------------------------------
# Aggregate difficulty distribution
# ---------------------------------------------------------------------------


class AggregateDifficultyPoint(BaseModel):
    """Difficulty count for aggregate view."""
    difficulty: str
    solved_count: int
    percentage: float


class AggregatePlatformDifficulty(BaseModel):
    """Per-platform difficulty counts."""
    platform: str
    easy: int
    medium: int
    hard: int


class AggregateDifficultyDistributionResponse(BaseModel):
    """Difficulty distribution for selected platforms."""
    total_solved: int
    difficulties: list[AggregateDifficultyPoint]
    platform_totals: list[AggregatePlatformDifficulty]


# ---------------------------------------------------------------------------
# Aggregate submission activity
# ---------------------------------------------------------------------------


class AggregateActivityDay(BaseModel):
    """Submission counts for a single calendar day (aggregate)."""
    date: date
    total_submissions: int
    accepted_submissions: int


class AggregateSubmissionActivityResponse(BaseModel):
    """Submission activity for selected platforms."""
    total_submissions: int
    activity: list[AggregateActivityDay]


# ---------------------------------------------------------------------------
# Performance Analyzer
# ---------------------------------------------------------------------------


class PlatformRating(BaseModel):
    """Rating for a single platform.

    Ratings across different platforms (e.g. Codeforces, LeetCode) are on
    incompatible scales and must never be combined into a single number.
    """

    platform: str
    current_rating: int | None
    max_rating: int | None


class PerformanceOverview(BaseModel):
    """High-level performance summary.

    ``current_rating`` / ``max_rating`` are the highest values seen across all
    connected platforms.  Because rating scales differ per platform (Codeforces
    vs LeetCode vs others), use ``ratings_by_platform`` for accurate
    per-platform information.
    """
    total_submissions: int
    accepted_submissions: int
    solved_problems: int
    contests_attended: int
    active_days: int
    current_rating: int | None  # max across platforms — do not compare cross-platform
    max_rating: int | None      # max across platforms — do not compare cross-platform
    ratings_by_platform: list["PlatformRating"] = []  # per-platform, scale-safe


class TopicPerformance(BaseModel):
    """Topic-specific performance analysis."""
    topic: str
    solved_count: int
    percentage: float
    strength_level: Literal["strong", "moderate", "weak", "insufficient_data"]
    recent_activity: int  # Problems solved in last 30 days


class DifficultyPerformance(BaseModel):
    """Difficulty-specific performance analysis.

    ``attempt_count`` is the total number of submission attempts for this
    difficulty level.  It is ``None`` when the source data does not contain
    per-submission records (e.g. LeetCode profile-level difficulty counts).
    Do not substitute the solved count for the attempt count.
    """
    difficulty: str
    solved_count: int
    attempt_count: int | None  # None when source data is unavailable
    acceptance_rate: float | None
    recent_activity: int  # Problems solved in last 30 days
    coverage_status: Literal["well_covered", "moderately_covered", "rarely_attempted", "not_attempted"]
    platform: str | None = None  # Set when returning per-platform breakdowns


class SubmissionBehavior(BaseModel):
    """Submission behavior patterns."""
    total_submissions: int
    accepted_submissions: int
    acceptance_rate: float | None
    average_submissions_per_active_day: float
    longest_streak_days: int
    current_streak_days: int
    repeated_attempts_count: int  # Problems with multiple submissions


class ContestPerformance(BaseModel):
    """Contest participation and performance.

    ``current_rating`` / ``max_rating`` are the highest values seen across all
    platforms.  Use ``ratings_by_platform`` for scale-accurate per-platform data.
    """
    contests_participated: int
    current_rating: int | None  # max across platforms
    max_rating: int | None      # max across platforms
    average_rating_change: float | None
    recent_participation: int  # Contests in last 90 days
    participation_trend: Literal["increasing", "stable", "decreasing", "insufficient_data"]
    ratings_by_platform: list["PlatformRating"] = []


class RatingTrend(BaseModel):
    """Rating progression analysis.

    ``current_rating`` / ``max_rating`` are the highest values seen across all
    platforms and must not be interpreted as a universal cross-platform rating.
    Use ``ratings_by_platform`` for scale-accurate per-platform data.
    """
    current_rating: int | None  # max across platforms
    max_rating: int | None      # max across platforms
    rating_change_30_days: int | None
    rating_change_90_days: int | None
    trend_direction: Literal["improving", "stable", "declining", "insufficient_data"]
    volatility_score: float | None  # 0-1 scale of rating stability
    ratings_by_platform: list["PlatformRating"] = []


class StrengthItem(BaseModel):
    """A specific strength identified."""
    category: Literal["topic", "difficulty", "contest", "consistency"]
    description: str
    supporting_metric: str
    metric_value: float | int


class WeaknessItem(BaseModel):
    """A specific weakness identified."""
    category: Literal["topic", "difficulty", "contest", "consistency"]
    description: str
    supporting_metric: str
    metric_value: float | int
    confidence: Literal["high", "medium", "low"]



class DataQuality(BaseModel):
    """Data coverage and quality assessment.

    Fields named ``has_*_data`` indicate whether *any* records of that type
    exist locally.  They do not guarantee that the history is complete — that
    cannot be determined from local data alone.
    """
    has_topic_data: bool
    has_submission_data: bool
    has_contest_data: bool
    profile_reported_solved: int
    locally_tagged_solved: int
    historical_coverage_days: int
    platform_coverage: list[str]


class PerformanceProfile(BaseModel):
    """Comprehensive performance analysis for a user.

    This is the structured output of the PerformanceAnalyzer, designed to be
    consumed by future recommendation engines, study plans, and AI coaches.
    All metrics are calculated deterministically from stored data without LLM involvement.
    """

    overview: PerformanceOverview
    topic_performance: list[TopicPerformance]
    difficulty_performance: list[DifficultyPerformance]
    submission_behavior: SubmissionBehavior
    contest_performance: ContestPerformance
    rating_trend: RatingTrend
    strengths: list[StrengthItem]
    weaknesses: list[WeaknessItem]
    data_quality: DataQuality


class PerformanceProfileResponse(BaseModel):
    """API response wrapper for performance profile."""
    profile: PerformanceProfile
