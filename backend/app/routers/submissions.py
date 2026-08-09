from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.submission import SubmissionResponse
from app.services.submission_service import SubmissionService

router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.get("/", response_model=list[SubmissionResponse])
def get_submissions(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), profile_id: int | None = Query(None, ge=1), problem_id: int | None = Query(None, ge=1), db: Session = Depends(get_db)):
    try:
        return SubmissionService(db).get_submissions(skip, limit, profile_id, problem_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(submission_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    submission = SubmissionService(db).get_submission(submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission
