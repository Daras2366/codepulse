"""Contest participations router — all endpoints require authentication.

Ownership rules:
  GET /       — profile_id must belong to the authenticated user
  GET /{id}   — the participation's profile must belong to the authenticated user
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.repositories.platform_profile_repository import PlatformProfileRepository
from app.schemas.contest_participation import ContestParticipationResponse
from app.services.contest_participation_service import ContestParticipationService

router = APIRouter(prefix="/contest-participations", tags=["Contest Participations"])


def _require_profile_ownership(
    profile_id: int,
    current_user: User,
    db: Session,
) -> None:
    profile = PlatformProfileRepository(db).get_by_id(profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform profile not found",
        )
    if profile.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have permission to access this profile's "
                "contest participations"
            ),
        )


@router.get("/", response_model=list[ContestParticipationResponse])
def get_participations(
    profile_id: int = Query(..., ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_profile_ownership(profile_id, current_user, db)
    return ContestParticipationService(db).get_participations(profile_id, skip, limit)


@router.get("/{participation_id}", response_model=ContestParticipationResponse)
def get_participation(
    participation_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    participation = ContestParticipationService(db).get_participation(participation_id)
    if participation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contest participation not found",
        )
    _require_profile_ownership(participation.profile_id, current_user, db)
    return participation
