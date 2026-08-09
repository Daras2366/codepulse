from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.contest_participation import ContestParticipationResponse
from app.services.contest_participation_service import ContestParticipationService

router = APIRouter(prefix="/contest-participations", tags=["Contest Participations"])


@router.get("/", response_model=list[ContestParticipationResponse])
def get_participations(profile_id: int = Query(..., ge=1), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), db: Session = Depends(get_db)):
    return ContestParticipationService(db).get_participations(profile_id, skip, limit)


@router.get("/{participation_id}", response_model=ContestParticipationResponse)
def get_participation(participation_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    participation = ContestParticipationService(db).get_participation(participation_id)
    if participation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest participation not found")
    return participation
