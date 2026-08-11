"""Goal service.

Provides CRUD operations and real-time progress calculation.

Progress is calculated from the database via GoalProgressRepository:
  - GoalType.DAILY   → distinct problems solved today (UTC)
  - GoalType.WEEKLY  → distinct problems solved this ISO week
  - GoalType.MONTHLY → distinct problems solved this calendar month

"Solved" means at least one ACCEPTED submission for the problem within
the window, across all of the user's platform profiles.
"""

from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.repositories.goal_progress_repository import GoalProgressRepository
from app.repositories.goal_repository import GoalRepository
from app.schemas.goal import GoalCreate, GoalUpdate
from app.schemas.goal_progress import GoalProgressResponse


class GoalService:
    def __init__(self, db: Session) -> None:
        self.repository = GoalRepository(db)
        self._progress_repo = GoalProgressRepository(db)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_goal(self, goal_id: int) -> Goal | None:
        return self.repository.get_by_id(goal_id)

    def get_goals(self, user_id: int, skip: int, limit: int) -> list[Goal]:
        return self.repository.get_by_user(user_id, skip, limit)

    def create_goal(self, data: GoalCreate, user_id: int) -> Goal:
        """Create a goal owned by the given user."""
        return self.repository.create(
            Goal(**data.model_dump(), user_id=user_id)
        )

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
        """Return a goal enriched with real-time progress from the database."""
        calculated = self._progress_repo.get_solved_in_window(
            user_id=goal.user_id,
            goal_type=goal.goal_type,
        )
        start, end = self._progress_repo.get_window_dates(goal.goal_type)
        return GoalProgressResponse(
            id=goal.id,
            user_id=goal.user_id,
            title=goal.title,
            description=goal.description,
            goal_type=goal.goal_type,
            target_value=goal.target_value,
            current_value=goal.current_value,
            status=goal.status,
            created_at=goal.created_at,
            updated_at=goal.updated_at,
            window_start=start,
            window_end=end,
            calculated_progress=calculated,
        )
