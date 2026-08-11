"""Achievements router.

Public endpoints (no auth required):
  GET /achievements/         — list achievement catalog definitions
  GET /achievements/{id}     — get one achievement definition

Authenticated endpoints:
  GET /achievements/me       — list current user's earned achievements
  POST /achievements/evaluate — run evaluation and grant new achievements
  POST /achievements/seed     — seed the catalog (idempotent, admin utility)
"""

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.achievement import AchievementResponse
from app.schemas.user_achievement import AchievementEvalResult, UserAchievementResponse
from app.services.achievement_service import AchievementService

router = APIRouter(prefix="/achievements", tags=["Achievements"])


# ---------------------------------------------------------------------------
# Public — Achievement catalog
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[AchievementResponse])
def get_achievements(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List all achievement definitions (global reference data)."""
    return AchievementService(db).get_achievements(skip, limit)


# ---------------------------------------------------------------------------
# Authenticated — User achievements (must be before /{id})
# ---------------------------------------------------------------------------


@router.get("/me", response_model=list[UserAchievementResponse])
def get_my_achievements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all achievements earned by the authenticated user."""
    return AchievementService(db).get_user_achievements(current_user.id)


@router.post(
    "/evaluate",
    response_model=AchievementEvalResult,
    status_code=status.HTTP_200_OK,
)
def evaluate_achievements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evaluate achievement conditions and grant any newly earned ones.

    Safe to call multiple times — already-owned achievements are not
    re-granted (idempotent via DB unique constraint).
    """
    return AchievementService(db).evaluate_for_user(current_user.id)


@router.post(
    "/seed",
    status_code=status.HTTP_200_OK,
)
def seed_achievements(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seed the achievement catalog from built-in definitions (idempotent).

    Returns the number of newly inserted achievement definitions.
    """
    count = AchievementService(db).seed_catalog()
    return {"inserted": count}


# ---------------------------------------------------------------------------
# Public — Single achievement definition (must be after /me and /evaluate)
# ---------------------------------------------------------------------------


@router.get("/{achievement_id}", response_model=AchievementResponse)
def get_achievement(
    achievement_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
):
    """Get a single achievement definition by ID."""
    achievement = AchievementService(db).get_achievement(achievement_id)
    if achievement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Achievement not found"
        )
    return achievement
