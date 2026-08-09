from sqlalchemy.orm import Session

from app.models.goal import Goal
from app.repositories.goal_repository import GoalRepository
from app.schemas.goal import GoalCreate, GoalUpdate


class GoalService:
    def __init__(self, db: Session):
        self.repository = GoalRepository(db)

    def get_goal(self, goal_id: int) -> Goal | None:
        return self.repository.get_by_id(goal_id)

    def get_goals(self, user_id: int, skip: int, limit: int) -> list[Goal]:
        return self.repository.get_by_user(user_id, skip, limit)

    def create_goal(self, data: GoalCreate) -> Goal:
        return self.repository.create(Goal(**data.model_dump()))

    def update_goal(self, goal: Goal, data: GoalUpdate) -> Goal:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(goal, field, value)
        return self.repository.update(goal)

    def delete_goal(self, goal: Goal) -> None:
        self.repository.delete(goal)
