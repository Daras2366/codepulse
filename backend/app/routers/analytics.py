"""Analytics router.

All endpoints require authentication via get_current_user.
Ownership is enforced inside AnalyticsService (403 on mismatch, 404 if absent).
"""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.analytics import (
    AggregateRatingProgressionResponse,
    AnalyticsContestPerformanceResponse,
    AnalyticsDifficultyDistributionResponse,
    AnalyticsRatingProgressionResponse,
    AnalyticsSubmissionActivityResponse,
    AnalyticsSummaryResponse,
)
from app.services.analytics_service import (
    AnalyticsProfileAccessDeniedError,
    AnalyticsProfileNotFoundError,
    AnalyticsService,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _get_service(db: Session) -> AnalyticsService:
    return AnalyticsService(db)


def _raise_analytics_error(error: Exception) -> None:
    if isinstance(error, AnalyticsProfileNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, AnalyticsProfileAccessDeniedError):
        raise HTTPException(status_code=403, detail=str(error)) from error
    raise error


@router.get("/{profile_id}/summary", response_model=AnalyticsSummaryResponse)
def get_summary(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregate statistics for the profile."""
    try:
        return _get_service(db).get_summary(profile_id, current_user.id)
    except (AnalyticsProfileNotFoundError, AnalyticsProfileAccessDeniedError) as exc:
        _raise_analytics_error(exc)


@router.get(
    "/{profile_id}/submission-activity",
    response_model=AnalyticsSubmissionActivityResponse,
)
def get_submission_activity(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return daily submission counts for charting activity over time."""
    try:
        return _get_service(db).get_submission_activity(profile_id, current_user.id)
    except (AnalyticsProfileNotFoundError, AnalyticsProfileAccessDeniedError) as exc:
        _raise_analytics_error(exc)


@router.get(
    "/{profile_id}/difficulty-distribution",
    response_model=AnalyticsDifficultyDistributionResponse,
)
def get_difficulty_distribution(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return solved problem counts grouped by difficulty."""
    try:
        return _get_service(db).get_difficulty_distribution(profile_id, current_user.id)
    except (AnalyticsProfileNotFoundError, AnalyticsProfileAccessDeniedError) as exc:
        _raise_analytics_error(exc)


@router.get(
    "/{profile_id}/rating-progression",
    response_model=AnalyticsRatingProgressionResponse,
)
def get_rating_progression(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return rating history suitable for a frontend rating chart."""
    try:
        return _get_service(db).get_rating_progression(profile_id, current_user.id)
    except (AnalyticsProfileNotFoundError, AnalyticsProfileAccessDeniedError) as exc:
        _raise_analytics_error(exc)


@router.get(
    "/{profile_id}/contest-performance",
    response_model=AnalyticsContestPerformanceResponse,
)
def get_contest_performance(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return contest participation history with rank and rating data."""
    try:
        return _get_service(db).get_contest_performance(profile_id, current_user.id)
    except (AnalyticsProfileNotFoundError, AnalyticsProfileAccessDeniedError) as exc:
        _raise_analytics_error(exc)


@router.get("/aggregate/rating-progression", response_model=AggregateRatingProgressionResponse)
def get_aggregate_rating_progression(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return rating history for all connected platforms for the authenticated user."""
    return _get_service(db).get_aggregate_rating_progression(current_user.id)
