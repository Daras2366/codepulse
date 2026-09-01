"""Goal service.

Provides CRUD operations and real-time progress calculation.

Architecture:
  router → GoalService → GoalProgressCalculator → GoalProgressRepository

Progress is always computed live — the cached current_value on the Goal
model is refreshed after each progress calculation so subsequent GET /goals
calls (which return GoalProgressResponse) show accurate values.

Status management:
  After each progress calculation the goal's status is updated:
    current >= target   → COMPLETED (sets completed_at once)
    past deadline       → OVERDUE
    otherwise           → ACTIVE (unless PAUSED)
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.enums import GoalStatus, GoalType
from app.models.goal import Goal
from app.repositories.goal_repository import GoalRepository
from app.schemas.goal import GoalCreate, GoalUpdate
from app.schemas.goal_progress import GoalProgressResponse
from app.services.goal_progress_calculator import GoalProgressCalculator


class GoalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = GoalRepository(db)
        self._calculator = GoalProgressCalculator(db)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_goal(self, goal_id: int) -> Optional[Goal]:
        return self.repository.get_by_id(goal_id)

    def get_goals(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None,
    ) -> list[Goal]:
        goals = self.repository.get_by_user(user_id, skip, limit)
        if status_filter:
            goals = [g for g in goals if g.status.value == status_filter.lower()]
        return goals

    def create_goal(self, data: GoalCreate, user_id: int) -> Goal:
        """Create a goal and record start_value for RATING baseline.
        
        The effective start date is used to ensure only activity from that point
        forward contributes to progress, preventing historical data from immediately
        completing new goals.
        
        For TOPIC goals on LeetCode, we record the current topic count as start_value
        so we can calculate progress as (current_count - start_value).
        """
        goal_data = data.model_dump()

        # Record the start value for baseline-based progress tracking
        start_value = 0
        if data.goal_type == GoalType.RATING and data.platform:
            from app.repositories.goal_progress_repository import GoalProgressRepository
            repo = GoalProgressRepository(self.db)
            start_value = repo.get_rating_for_platform(user_id, data.platform)
        elif data.goal_type == GoalType.TOPIC and data.platform == "leetcode" and data.topic_slug:
            # For LeetCode topics, record current count as baseline
            from app.repositories.goal_progress_repository import GoalProgressRepository
            repo = GoalProgressRepository(self.db)
            start_value = repo.get_topic_solved_count_leetcode(user_id, data.topic_slug)

        # Default start_date to today if not provided - this is the effective start
        # date from which progress counting begins
        if goal_data.get("start_date") is None:
            goal_data["start_date"] = date.today()

        goal = Goal(
            **goal_data,
            user_id=user_id,
            start_value=start_value,
            current_value=0,
            status=GoalStatus.ACTIVE,
        )
        return self.repository.create(goal)

    def update_goal(self, goal: Goal, data: GoalUpdate) -> Goal:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(goal, field, value)
        return self.repository.update(goal)

    def delete_goal(self, goal: Goal) -> None:
        self.repository.delete(goal)

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def get_goal_progress(self, goal: Goal) -> GoalProgressResponse:
        """Compute live progress, update status/current_value, return response."""
        result = self._calculator.calculate(goal)

        # Persist updated status + current_value back to the goal row
        changed = False
        if goal.current_value != result.current_value:
            goal.current_value = result.current_value
            changed = True
        if goal.status != result.status:
            goal.status = result.status
            changed = True
        if result.is_completed and goal.completed_at is None and result.completed_at:
            goal.completed_at = result.completed_at
            changed = True
        if changed:
            self.repository.update(goal)

        return GoalProgressResponse(
            id=goal.id,
            user_id=goal.user_id,
            title=goal.title,
            description=goal.description,
            goal_type=goal.goal_type,
            status=result.status,
            platform=goal.platform,
            topic_slug=goal.topic_slug,
            topic_name=goal.topic_name,
            difficulty_filter=goal.difficulty_filter,
            target_value=goal.target_value,
            start_value=goal.start_value,
            current_value=result.current_value,
            progress_percentage=result.progress_percentage,
            remaining=result.remaining,
            start_date=goal.start_date,
            deadline=goal.deadline,
            days_remaining=result.days_remaining,
            completed_at=result.completed_at,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
            is_overdue=result.is_overdue,
            is_completed=result.is_completed,
            pace=result.pace,
        )

    def get_all_goals_with_progress(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None,
    ) -> list[GoalProgressResponse]:
        """Return all goals with live progress data.

        Applies status_filter AFTER computing progress so newly-completed /
        overdue goals are filtered correctly even if their DB status is stale.
        """
        goals = self.repository.get_by_user(user_id, skip, limit)
        results: list[GoalProgressResponse] = []
        for goal in goals:
            progress = self.get_goal_progress(goal)
            if status_filter and progress.status.value != status_filter.lower():
                continue
            results.append(progress)
        return results
