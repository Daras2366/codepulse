from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import GoalStatus, GoalType


class GoalBase(BaseModel):
    user_id: int
    title: str
    description: str | None = None
    goal_type: GoalType
    target_value: int
    current_value: int = 0
    status: GoalStatus = GoalStatus.ACTIVE


class GoalCreate(GoalBase):
    pass


class GoalUpdate(BaseModel):
    user_id: int | None = None
    title: str | None = None
    description: str | None = None
    goal_type: GoalType | None = None
    target_value: int | None = None
    current_value: int | None = None
    status: GoalStatus | None = None


class GoalResponse(GoalBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
