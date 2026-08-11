"""User Achievement schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.achievement import AchievementResponse


class UserAchievementResponse(BaseModel):
    """A single achievement earned by a user."""

    id: int
    user_id: int
    achievement_id: int
    earned_at: datetime
    achievement: AchievementResponse

    model_config = ConfigDict(from_attributes=True)


class AchievementEvalResult(BaseModel):
    """Result of running achievement evaluation for a user."""

    newly_granted: int
    """Number of achievements granted in this evaluation run."""

    achievement_names: list[str]
    """Names of achievements newly granted (empty if none)."""
