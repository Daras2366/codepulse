from typing import List

from sqlalchemy.orm import Session

from app.models.enums import GoalStatus
from app.models.goal import Goal
from app.repositories.base import BaseRepository


class GoalRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, goal: Goal) -> Goal:
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def get_by_id(self, goal_id: int) -> Goal | None:
        return (
            self.db.query(Goal)
            .filter(Goal.id == goal_id)
            .first()
        )

    def get_by_user(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Goal]:
        return (
            self.db.query(Goal)
            .filter(Goal.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active_goals(self, user_id: int) -> List[Goal]:
        return (
            self.db.query(Goal)
            .filter(
                Goal.user_id == user_id,
                Goal.status == GoalStatus.ACTIVE,
            )
            .all()
        )

    def get_completed_goals(self, user_id: int) -> List[Goal]:
        return (
            self.db.query(Goal)
            .filter(
                Goal.user_id == user_id,
                Goal.status == GoalStatus.COMPLETED,
            )
            .all()
        )

    def update(self, goal: Goal) -> Goal:
        self.db.commit()
        self.db.refresh(goal)
        return goal

    def delete(self, goal: Goal) -> None:
        self.db.delete(goal)
        self.db.commit()

    def exists(self, goal_id: int) -> bool:
        return (
            self.db.query(Goal)
            .filter(Goal.id == goal_id)
            .first()
            is not None
        )
