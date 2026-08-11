"""Submissions router — all endpoints require authentication.

Ownership rules:
  GET /           — profile_id must belong to the authenticated user
  GET /{id}       — the submission's profile must belong to the authenticated user
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.repositories.platform_profile_repository import PlatformProfileRepository
from app.schemas.submission import SubmissionResponse
from app.services.submission_service import SubmissionService

router = APIRouter(prefix="/submissions", tags=["Submissions"])


def _require_profile_ownership(
    profile_id: int,
    current_user: User,
    db: Session,
) -> None:
    """Raise 403 if the profile does not belong to the current user."""
    profile = PlatformProfileRepository(db).get_by_id(profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform profile not found",
        )
    if profile.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this profile's submissions",
        )


@router.get("/", response_model=list[SubmissionResponse])
def get_submissions(
    profile_id: int = Query(..., ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    problem_id: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_profile_ownership(profile_id, current_user, db)
    try:
        return SubmissionService(db).get_submissions(skip, limit, profile_id, problem_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = SubmissionService(db).get_submission(submission_id)
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
        )
    # Verify the submission's profile belongs to the current user.
    _require_profile_ownership(submission.profile_id, current_user, db)
    return submission
