"""Goal progress response schema.

GoalProgressResponse extends GoalResponse with all computed progress fields.
All calculation happens in GoalProgressCalculator — the frontend never
computes progress values.

Fields beyond GoalResponse:
  current_value       — live-computed progress value (replaces the cached one)
  progress_percentage — 0–100, rounded to 1 decimal
  remaining           — target_value - current_value (clamped to 0)
  days_remaining      — calendar days until deadline (null if no deadline)
  is_overdue          — true when past deadline and not yet completed
  is_completed        — true when current_value >= target_value
  pace                — "ahead" | "on_track" | "behind" | "completed"
                        | "overdue" | "no_deadline"
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import GoalStatus, GoalType


class GoalProgressResponse(BaseModel):
    """Goal response enriched with real-time progress from GoalProgressCalculator."""

    # ---- Identity ----
    id: int
    user_id: int
    title: str
    description: Optional[str]
    goal_type: GoalType
    status: GoalStatus

    # ---- Scoping ----
    platform: Optional[str]
    topic_slug: Optional[str]
    topic_name: Optional[str]
    difficulty_filter: Optional[str]

    # ---- Target / baseline ----
    target_value: int
    start_value: int

    # ---- Progress (computed) ----
    current_value: int
    progress_percentage: float
    remaining: int

    # ---- Time ----
    start_date: Optional[date]
    deadline: Optional[date]
    days_remaining: Optional[int]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    # ---- Insights ----
    is_overdue: bool
    is_completed: bool
    pace: str  # "ahead" | "on_track" | "behind" | "completed" | "overdue" | "no_deadline"

    model_config = ConfigDict(from_attributes=False)
