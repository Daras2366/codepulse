"""Regression tests for enum loading after fixing SQLAlchemy Enum mapping.

Tests that existing goals with all goal types can be loaded correctly
from the database after fixing the values_callable configuration.
"""
import os
from datetime import date
from unittest import TestCase

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DEBUG", "true")

import app.models  # noqa: F401
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.base import Base
from app.models.enums import GoalStatus, GoalType
from app.models.goal import Goal
from app.models.user import User
from app.routers import goals as goals_router


class TestEnumLoading(TestCase):
    """Test that all GoalType and GoalStatus enum values load correctly."""

    def setUp(self):
        """Create a test database and user."""
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        Base.metadata.create_all(self.engine)

        # Create test user
        self.user = User(
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            password_hash="hashed",
        )
        self.session.add(self.user)
        self.session.commit()

        # Create test goals with all types
        self.goals = []
        goal_types = [
            GoalType.RATING,
            GoalType.PROBLEMS,
            GoalType.TOPIC,
            GoalType.CONSISTENCY,
            GoalType.CONTEST,
            GoalType.PLACEMENT,
        ]
        
        for goal_type in goal_types:
            goal = Goal(
                user_id=self.user.id,
                title=f"Test {goal_type.value} goal",
                goal_type=goal_type,
                target_value=10,
                status=GoalStatus.ACTIVE,
            )
            self.session.add(goal)
            self.goals.append(goal)
        
        self.session.commit()

        # Setup FastAPI test client
        def override_get_db():
            try:
                yield self.session
            finally:
                pass

        def override_get_current_user():
            return self.user

        _app = FastAPI()
        _app.include_router(goals_router.router)
        _app.dependency_overrides[get_db] = override_get_db
        _app.dependency_overrides[get_current_user] = override_get_current_user
        self.client = TestClient(_app)

    def tearDown(self):
        """Clean up test database."""
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_load_all_goal_types(self):
        """Test that goals with all GoalType values can be loaded from database."""
        # Reload goals from database
        loaded_goals = self.session.query(Goal).filter_by(user_id=self.user.id).all()
        
        # Verify all goals were loaded
        self.assertEqual(len(loaded_goals), 6, "Should load all 6 goal types")
        
        # Verify each goal type is correctly loaded
        loaded_types = {goal.goal_type for goal in loaded_goals}
        expected_types = {
            GoalType.RATING,
            GoalType.PROBLEMS,
            GoalType.TOPIC,
            GoalType.CONSISTENCY,
            GoalType.CONTEST,
            GoalType.PLACEMENT,
        }
        self.assertEqual(loaded_types, expected_types, "All goal types should be loaded")
        
        # Verify enum values are correct (lowercase strings)
        for goal in loaded_goals:
            self.assertIsInstance(goal.goal_type, GoalType)
            self.assertIn(goal.goal_type.value, ["rating", "problems", "topic", "consistency", "contest", "placement"])

    def test_load_all_goal_statuses(self):
        """Test that goals with all GoalStatus values can be loaded from database."""
        # Update goals to have different statuses
        statuses = [
            GoalStatus.ACTIVE,
            GoalStatus.COMPLETED,
            GoalStatus.OVERDUE,
            GoalStatus.PAUSED,
        ]
        
        for i, goal in enumerate(self.goals[:4]):
            goal.status = statuses[i]
        
        self.session.commit()
        
        # Reload goals from database
        loaded_goals = self.session.query(Goal).filter_by(user_id=self.user.id).all()
        
        # Verify statuses are correctly loaded
        loaded_statuses = {goal.status for goal in loaded_goals}
        expected_statuses = set(statuses)
        self.assertEqual(loaded_statuses, expected_statuses, "All statuses should be loaded")
        
        # Verify enum values are correct (lowercase strings)
        for goal in loaded_goals:
            self.assertIsInstance(goal.status, GoalStatus)
            self.assertIn(goal.status.value, ["active", "completed", "overdue", "paused"])

    def test_create_and_load_goal(self):
        """Test that newly created goals can be loaded correctly."""
        new_goal = Goal(
            user_id=self.user.id,
            title="New test goal",
            goal_type=GoalType.PROBLEMS,
            target_value=20,
            status=GoalStatus.ACTIVE,
        )
        self.session.add(new_goal)
        self.session.commit()
        
        # Load the new goal
        loaded_goal = self.session.query(Goal).filter_by(id=new_goal.id).first()
        
        self.assertIsNotNone(loaded_goal)
        self.assertEqual(loaded_goal.goal_type, GoalType.PROBLEMS)
        self.assertEqual(loaded_goal.goal_type.value, "problems")
        self.assertEqual(loaded_goal.status, GoalStatus.ACTIVE)
        self.assertEqual(loaded_goal.status.value, "active")

    def test_api_returns_goals_with_correct_enums(self):
        """Test that API endpoint returns goals with correct enum values."""
        resp = self.client.get("/goals/")
        self.assertEqual(resp.status_code, 200)
        
        goals = resp.json()
        self.assertEqual(len(goals), 6)
        
        # Verify all goal types are present in API response
        goal_types = {goal["goal_type"] for goal in goals}
        expected_types = {"rating", "problems", "topic", "consistency", "contest", "placement"}
        self.assertEqual(goal_types, expected_types)
        
        # Verify all are lowercase strings
        for goal in goals:
            self.assertIsInstance(goal["goal_type"], str)
            self.assertEqual(goal["goal_type"], goal["goal_type"].lower())
            self.assertIsInstance(goal["status"], str)
            self.assertEqual(goal["status"], goal["status"].lower())


if __name__ == "__main__":
    import unittest
    unittest.main()