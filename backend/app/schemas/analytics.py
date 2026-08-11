"""Pydantic response schemas for the Analytics API."""

from datetime import date, datetime

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
