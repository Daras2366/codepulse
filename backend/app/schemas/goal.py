"""Goal schemas.

GoalCreate no longer accepts user_id in the request body.
The authenticated user's id is injected by the router.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import GoalStatus, GoalType


class GoalBase(BaseModel):
    title: str
    description: str | None = None
    goal_type: GoalType
    target_value: int
    current_value: int = 0
    status: GoalStatus = GoalStatus.ACTIVE


class GoalCreate(GoalBase):
    pass


class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    goal_type: GoalType | None = None
    target_value: int | None = None
    current_value: int | None = None
    status: GoalStatus | None = None


class GoalResponse(GoalBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
