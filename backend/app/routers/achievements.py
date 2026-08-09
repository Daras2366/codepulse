from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.achievement import AchievementResponse
from app.services.achievement_service import AchievementService

router = APIRouter(prefix="/achievements", tags=["Achievements"])


@router.get("/", response_model=list[AchievementResponse])
def get_achievements(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), db: Session = Depends(get_db)):
    return AchievementService(db).get_achievements(skip, limit)


@router.get("/{achievement_id}", response_model=AchievementResponse)
def get_achievement(achievement_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    achievement = AchievementService(db).get_achievement(achievement_id)
    if achievement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement not found")
    return achievement
