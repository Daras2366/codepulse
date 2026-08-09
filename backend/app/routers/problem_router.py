from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.problem import ProblemResponse
from app.services.problem_service import ProblemService

router = APIRouter(
    prefix="/problems",
    tags=["Problems"],
)


@router.get("/", response_model=list[ProblemResponse])
def get_all_problems(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = ProblemService(db)
    return service.get_all_problems(skip, limit)


@router.get("/{problem_id}", response_model=ProblemResponse)
def get_problem(
    problem_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    service = ProblemService(db)

    problem = service.get_problem(problem_id)

    if problem is None:
        raise HTTPException(
            status_code=404,
            detail="Problem not found",
        )

    return problem
