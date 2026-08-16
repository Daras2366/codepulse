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

from sqlalchemy.orm import Session

from app.models.enums import Difficulty

from app.models.platform_profile import PlatformProfile
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.platform_profile_repository import PlatformProfileRepository
from app.schemas.analytics import (
    AnalyticsActivityDay,
    AnalyticsContestEntry,
    AnalyticsContestPerformanceResponse,
    AnalyticsDifficultyBucket,
    AnalyticsDifficultyDistributionResponse,
    AggregateRatingPoint,
    AggregateRatingProgressionResponse,
    AggregateRatingSeries,
    AnalyticsRatingPoint,
    AnalyticsRatingProgressionResponse,
    AnalyticsSubmissionActivityResponse,
    AnalyticsSummaryResponse,
)


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

    def get_aggregate_rating_progression(self, user_id: int) -> AggregateRatingProgressionResponse:
        """Return rating history for all connected platforms for the user."""
        from app.models.enums import Platform
        
        # Get all profiles for the user
        profiles = self._profiles.get_by_user_id(user_id)
        
        series = []
        for profile in profiles:
            rows = self._repo.get_rating_history(profile.id)
            history = [
                AggregateRatingPoint(
                    date=rating.recorded_at.isoformat() if rating.recorded_at else None,
                    rating=rating.rating,
                    platform=profile.platform.value,
                )
                for rating, contest in rows
            ]
            series.append(AggregateRatingSeries(
                platform=profile.platform.value,
                username=profile.username,
                history=history,
            ))
        
        return AggregateRatingProgressionResponse(series=series)

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
