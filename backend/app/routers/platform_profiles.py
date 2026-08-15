"""Platform profiles router.

Ownership rules:
  GET /me           — authenticated, returns own profiles (unchanged)
  GET /             — authenticated, scoped to current_user only
  GET /{id}         — authenticated, must be own profile
  POST /            — authenticated, user_id derived from token
  PATCH /{id}       — authenticated, must be own profile
  DELETE /{id}      — authenticated, must be own profile
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.platform_profile import PlatformProfile
from app.models.user import User
from app.schemas.platform_profile import (
    PlatformProfileCreate,
    PlatformProfileResponse,
    PlatformProfileUpdate,
)
from app.services.platform_profile_service import PlatformProfileService

router = APIRouter(prefix="/platform-profiles", tags=["Platform Profiles"])


def _require_profile_ownership(
    profile: PlatformProfile,
    current_user: User,
) -> None:
    if profile.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this platform profile",
        )


@router.get("/me", response_model=list[PlatformProfileResponse])
def get_my_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return PlatformProfileService(db).get_profiles(
        skip=0,
        limit=100,
        user_id=current_user.id,
    )


@router.get("/", response_model=list[PlatformProfileResponse])
def get_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return platform profiles for the authenticated user."""
    return PlatformProfileService(db).get_profiles(
        skip=0,
        limit=100,
        user_id=current_user.id,
    )


@router.get("/{profile_id}", response_model=PlatformProfileResponse)
def get_profile(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = PlatformProfileService(db).get_profile(profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform profile not found",
        )
    _require_profile_ownership(profile, current_user)
    return profile


@router.post(
    "/", response_model=PlatformProfileResponse, status_code=status.HTTP_201_CREATED
)
def create_profile(
    data: PlatformProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a platform profile owned by the authenticated user."""
    # Enforce ownership: always use the authenticated user's id.
    return PlatformProfileService(db).create_profile(data, current_user.id)


@router.patch("/{profile_id}", response_model=PlatformProfileResponse)
def update_profile(
    data: PlatformProfileUpdate,
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PlatformProfileService(db)
    profile = service.get_profile(profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform profile not found",
        )
    _require_profile_ownership(profile, current_user)
    return service.update_profile(profile, data)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    service = PlatformProfileService(db)
    profile = service.get_profile(profile_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform profile not found",
        )
    _require_profile_ownership(profile, current_user)
    service.delete_profile(profile)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
