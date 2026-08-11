"""Goal progress schema.

Extends the existing GoalResponse with calculated progress fields.
The base GoalResponse already provides id, user_id, title, goal_type,
target_value, current_value, status, created_at, updated_at.
"""

from datetime import date

from pydantic import BaseModel, computed_field, ConfigDict

from app.models.enums import GoalStatus, GoalType
from app.schemas.goal import GoalResponse


class GoalProgressResponse(GoalResponse):
    """Goal response enriched with real-time progress from the database."""

    window_start: date
    window_end: date
    calculated_progress: int
    """Actual count from the database for the current window."""

    @computed_field  # type: ignore[misc]
    @property
    def percentage(self) -> float:
        """Progress as a percentage capped at 100."""
        if self.target_value <= 0:
            return 0.0
        return round(min(self.calculated_progress / self.target_value * 100, 100), 1)

    @computed_field  # type: ignore[misc]
    @property
    def remaining(self) -> int:
        """How many more items needed to reach the target."""
        return max(0, self.target_value - self.calculated_progress)

    @computed_field  # type: ignore[misc]
    @property
    def is_achieved(self) -> bool:
        return self.calculated_progress >= self.target_value

    model_config = ConfigDict(from_attributes=True)
