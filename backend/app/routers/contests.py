from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import Platform
from app.schemas.contest import ContestResponse
from app.services.contest_service import ContestService

router = APIRouter(prefix="/contests", tags=["Contests"])


@router.get("/", response_model=list[ContestResponse])
def get_contests(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), platform: Platform | None = None, db: Session = Depends(get_db)):
    return ContestService(db).get_contests(skip, limit, platform)


@router.get("/{contest_id}", response_model=ContestResponse)
def get_contest(contest_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    contest = ContestService(db).get_contest(contest_id)
    if contest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found")
    return contest
