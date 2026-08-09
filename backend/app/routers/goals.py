from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.goal import GoalCreate, GoalResponse, GoalUpdate
from app.services.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["Goals"])


@router.get("/", response_model=list[GoalResponse])
def get_goals(user_id: int = Query(..., ge=1), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100), db: Session = Depends(get_db)):
    return GoalService(db).get_goals(user_id, skip, limit)


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(goal_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    goal = GoalService(db).get_goal(goal_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(data: GoalCreate, db: Session = Depends(get_db)):
    return GoalService(db).create_goal(data)


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(data: GoalUpdate, goal_id: int = Path(..., gt=0), db: Session = Depends(get_db)):
    service = GoalService(db)
    goal = service.get_goal(goal_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return service.update_goal(goal, data)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int = Path(..., gt=0), db: Session = Depends(get_db)) -> Response:
    service = GoalService(db)
    goal = service.get_goal(goal_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    service.delete_goal(goal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
