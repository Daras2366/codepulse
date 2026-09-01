"""Goal schemas.

GoalCreate never accepts user_id — the authenticated user's id is always
injected by the router.

Validation rules enforced at schema level:
  - target_value must be > 0
  - deadline, if provided, must be today or in the future
  - start_date must be <= deadline when both are provided
  - RATING goals require a platform
  - TOPIC goals require topic_slug AND topic_name
  - RATING goals with platform must use a rating-capable platform (leetcode/codeforces)
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import GoalStatus, GoalType

# Platforms that support rating
RATING_PLATFORMS = {"leetcode", "codeforces"}


class GoalBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    goal_type: GoalType
    target_value: int = Field(..., gt=0, description="Must be a positive integer")
    platform: Optional[str] = None
    topic_slug: Optional[str] = None
    topic_name: Optional[str] = None
    difficulty_filter: Optional[str] = None
    start_date: Optional[date] = None
    deadline: Optional[date] = None


class GoalCreate(GoalBase):
    """Schema for creating a new goal.  user_id is injected by the router."""

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Title must not be blank")
        return v.strip()

    @field_validator("platform")
    @classmethod
    def platform_lowercase(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.lower()
        return v

    @field_validator("difficulty_filter")
    @classmethod
    def validate_difficulty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("Easy", "Medium", "Hard"):
            raise ValueError("difficulty_filter must be 'Easy', 'Medium', or 'Hard'")
        return v

    @model_validator(mode="after")
    def cross_field_validation(self) -> "GoalCreate":
        # RATING requires platform
        if self.goal_type == GoalType.RATING:
            if not self.platform:
                raise ValueError("RATING goals require a platform (leetcode or codeforces)")
            if self.platform not in RATING_PLATFORMS:
                raise ValueError(
                    f"Platform '{self.platform}' does not support ratings. "
                    f"Use one of: {', '.join(RATING_PLATFORMS)}"
                )

        # TOPIC requires topic_slug and topic_name
        if self.goal_type == GoalType.TOPIC:
            if not self.topic_slug:
                raise ValueError("TOPIC goals require a topic_slug")
            if not self.topic_name:
                raise ValueError("TOPIC goals require a topic_name")

        # Deadline validation
        today = date.today()
        if self.deadline is not None and self.deadline < today:
            raise ValueError("deadline must be today or in the future")

        # start_date <= deadline
        if self.start_date is not None and self.deadline is not None:
            if self.start_date > self.deadline:
                raise ValueError("start_date must be on or before the deadline")

        return self


class GoalUpdate(BaseModel):
    """Partial update — all fields optional."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    target_value: Optional[int] = Field(None, gt=0)
    platform: Optional[str] = None
    topic_slug: Optional[str] = None
    topic_name: Optional[str] = None
    difficulty_filter: Optional[str] = None
    start_date: Optional[date] = None
    deadline: Optional[date] = None
    status: Optional[GoalStatus] = None

    @field_validator("difficulty_filter")
    @classmethod
    def validate_difficulty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("Easy", "Medium", "Hard"):
            raise ValueError("difficulty_filter must be 'Easy', 'Medium', or 'Hard'")
        return v


class GoalResponse(BaseModel):
    """Full goal data returned from any goal endpoint."""

    id: int
    user_id: int
    title: str
    description: Optional[str]
    goal_type: GoalType
    platform: Optional[str]
    topic_slug: Optional[str]
    topic_name: Optional[str]
    difficulty_filter: Optional[str]
    target_value: int
    start_value: int
    current_value: int
    start_date: Optional[date]
    deadline: Optional[date]
    status: GoalStatus
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
