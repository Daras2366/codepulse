"""Goals router — all endpoints require authentication.

Ownership rules:
  GET /                    — lists only the authenticated user's goals
  GET /{id}                — goal must belong to the authenticated user
  GET /{id}/progress       — goal must belong to the authenticated user
  POST /                   — user_id is derived from the authenticated user
  PATCH /{id}              — goal must belong to the authenticated user
  DELETE /{id}             — goal must belong to the authenticated user
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.goal import Goal
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalResponse, GoalUpdate
from app.schemas.goal_progress import GoalProgressResponse
from app.services.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["Goals"])


def _require_goal_ownership(goal: Goal, current_user: User) -> None:
    if goal.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this goal",
        )


@router.get("/", response_model=list[GoalResponse])
def get_goals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all goals belonging to the authenticated user."""
    return GoalService(db).get_goals(current_user.id, skip, limit)


@router.get("/{goal_id}/progress", response_model=GoalProgressResponse)
def get_goal_progress(
    goal_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the goal enriched with real-time progress from the database."""
    service = GoalService(db)
    goal = service.get_goal(goal_id)
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found"
        )
    _require_goal_ownership(goal, current_user)
    return service.get_goal_progress(goal)


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = GoalService(db).get_goal(goal_id)
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found"
        )
    _require_goal_ownership(goal, current_user)
    return goal


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(
    data: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a goal owned by the authenticated user."""
    return GoalService(db).create_goal(data, user_id=current_user.id)


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(
    data: GoalUpdate,
    goal_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GoalService(db)
    goal = service.get_goal(goal_id)
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found"
        )
    _require_goal_ownership(goal, current_user)
    return service.update_goal(goal, data)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    service = GoalService(db)
    goal = service.get_goal(goal_id)
    if goal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found"
        )
    _require_goal_ownership(goal, current_user)
    service.delete_goal(goal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
