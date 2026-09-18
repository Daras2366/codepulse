from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.dashboard import (
    DashboardAggregateResponse,
    DashboardContestsResponse,
    DashboardOverviewResponse,
    DashboardProblemsResponse,
    DashboardRatingResponse,
    DashboardSubmissionsResponse,
)
from app.services.dashboard_service import (
    DashboardProfileAccessDeniedError,
    DashboardProfileNotFoundError,
    DashboardService,
)

router = APIRouter()


def _get_service(db: Session) -> DashboardService:
    return DashboardService(db)


def _raise_dashboard_error(error: Exception) -> None:
    if isinstance(error, DashboardProfileNotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error

    if isinstance(error, DashboardProfileAccessDeniedError):
        raise HTTPException(status_code=403, detail=str(error)) from error

    raise error


@router.get("/aggregate", response_model=DashboardAggregateResponse)
def get_aggregate_dashboard(
    recent_limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the centralized dashboard across every connected platform."""
    return _get_service(db).get_aggregate_dashboard(current_user.id, recent_limit)


@router.get("/{profile_id}/overview", response_model=DashboardOverviewResponse)
def get_overview(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _get_service(db).get_overview(profile_id, current_user.id)
    except (DashboardProfileNotFoundError, DashboardProfileAccessDeniedError) as error:
        _raise_dashboard_error(error)


@router.get("/{profile_id}/rating", response_model=DashboardRatingResponse)
def get_rating(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _get_service(db).get_rating(profile_id, current_user.id)
    except (DashboardProfileNotFoundError, DashboardProfileAccessDeniedError) as error:
        _raise_dashboard_error(error)


@router.get("/{profile_id}/problems", response_model=DashboardProblemsResponse)
def get_problems(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _get_service(db).get_problems(profile_id, current_user.id)
    except (DashboardProfileNotFoundError, DashboardProfileAccessDeniedError) as error:
        _raise_dashboard_error(error)


@router.get("/{profile_id}/submissions", response_model=DashboardSubmissionsResponse)
def get_submissions(
    profile_id: int = Path(..., gt=0),
    recent_limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _get_service(db).get_submissions(
            profile_id,
            current_user.id,
            recent_limit,
        )
    except (DashboardProfileNotFoundError, DashboardProfileAccessDeniedError) as error:
        _raise_dashboard_error(error)


@router.get("/{profile_id}/contests", response_model=DashboardContestsResponse)
def get_contests(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _get_service(db).get_contests(profile_id, current_user.id)
    except (DashboardProfileNotFoundError, DashboardProfileAccessDeniedError) as error:
        _raise_dashboard_error(error)
