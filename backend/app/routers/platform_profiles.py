from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.platform_profile import PlatformProfileCreate, PlatformProfileResponse, PlatformProfileUpdate
from app.services.platform_profile_service import PlatformProfileService

router = APIRouter(prefix="/platform-profiles", tags=["Platform Profiles"])


@router.get("/", response_model=list[PlatformProfileResponse])
def get_profiles(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), user_id: int | None = Query(None, ge=1), db: Session = Depends(get_db)):
    return PlatformProfileService(db).get_profiles(skip, limit, user_id)


@router.get("/{profile_id}", response_model=PlatformProfileResponse)
def get_profile(profile_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    profile = PlatformProfileService(db).get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform profile not found")
    return profile


@router.post("/", response_model=PlatformProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(data: PlatformProfileCreate, db: Session = Depends(get_db)):
    return PlatformProfileService(db).create_profile(data)


@router.patch("/{profile_id}", response_model=PlatformProfileResponse)
def update_profile(data: PlatformProfileUpdate, profile_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    service = PlatformProfileService(db)
    profile = service.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform profile not found")
    return service.update_profile(profile, data)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: int = Path(..., gt=0), db: Session = Depends(get_db)) -> Response:
    service = PlatformProfileService(db)
    profile = service.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Platform profile not found")
    service.delete_profile(profile)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
