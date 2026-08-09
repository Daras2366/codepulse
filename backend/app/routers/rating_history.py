from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.rating_history import RatingHistoryResponse
from app.services.rating_history_service import RatingHistoryService

router = APIRouter(prefix="/rating-history", tags=["Rating History"])


@router.get("/", response_model=list[RatingHistoryResponse])
def get_rating_history(profile_id: int = Query(..., ge=1), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), db: Session = Depends(get_db)):
    return RatingHistoryService(db).get_rating_history_for_profile(profile_id, skip, limit)


@router.get("/{rating_id}", response_model=RatingHistoryResponse)
def get_rating(rating_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    rating = RatingHistoryService(db).get_rating_history(rating_id)
    if rating is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating history record not found")
    return rating
