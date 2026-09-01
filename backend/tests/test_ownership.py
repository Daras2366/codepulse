"""Ownership and security tests.

Verifies that authenticated users cannot access or modify data belonging
to other users, regardless of resource IDs.

Test cases:
  8.  Authenticated user can access their own profile data (analytics)
  9.  User cannot access another user's profile via analytics (403)
  10. User cannot access another user's submissions (403)
  11. User cannot access another user's contest participation / rating data (403)
  12. User cannot modify another user's goal (403)
  13. User cannot access another user's user-specific achievements (N/A — see note)

Additionally covers:
  - Goal creation always uses the authenticated user's id
  - Goal list is scoped to the authenticated user only
  - Platform profile GET/PATCH/DELETE is scoped to the owner
"""

import os
from datetime import datetime, timezone
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
from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.enums import (
    Difficulty,
    GoalStatus,
    GoalType,
    Platform,
    SubmissionStatus,
)
from app.models.goal import Goal
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.models.user import User
from app.routers import analytics as analytics_router
from app.routers import contest_participations as cp_router
from app.routers import goals as goals_router
from app.routers import platform_profiles as pp_router
from app.routers import rating_history as rh_router
from app.routers import submissions as sub_router


class OwnershipTests(TestCase):
    """Security tests for user-scoped endpoints."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

        # Two distinct users
        self.user_a = User(
            username="user-a",
            email="a@example.com",
            password_hash="hash",
        )
        self.user_b = User(
            username="user-b",
            email="b@example.com",
            password_hash="hash",
        )
        self.session.add_all([self.user_a, self.user_b])
        self.session.flush()

        # Profiles
        self.profile_a = PlatformProfile(
            user_id=self.user_a.id,
            platform=Platform.CODEFORCES,
            username="user_a_cf",
            current_rating=1500,
            max_rating=1600,
        )
        self.profile_b = PlatformProfile(
            user_id=self.user_b.id,
            platform=Platform.CODEFORCES,
            username="user_b_cf",
            current_rating=800,
            max_rating=900,
        )
        self.session.add_all([self.profile_a, self.profile_b])
        self.session.flush()

        # Shared problem + contest for test data
        self.problem = Problem(
            platform=Platform.CODEFORCES,
            platform_problem_id="100-A",
            title="Problem A",
            slug="cf-100-a",
            problem_url="https://codeforces.com/problemset/problem/100/A",
            difficulty=Difficulty.EASY,
            acceptance_rate=None,
        )
        self.contest = Contest(
            platform=Platform.CODEFORCES,
            platform_contest_id="100",
            title="Contest 100",
            contest_url="https://codeforces.com/contest/100",
            start_time=datetime(2023, 11, 14, tzinfo=timezone.utc),
            duration_minutes=120,
        )
        self.session.add_all([self.problem, self.contest])
        self.session.flush()

        # User B's submission
        self.sub_b = Submission(
            profile_id=self.profile_b.id,
            problem_id=self.problem.id,
            contest_id=self.contest.id,
            platform_submission_id="b1",
            submitted_at=datetime(2023, 11, 14, tzinfo=timezone.utc),
            language="Python 3",
            status=SubmissionStatus.ACCEPTED,
        )
        # User B's rating history
        self.rating_b = RatingHistory(
            profile_id=self.profile_b.id,
            contest_id=self.contest.id,
            rating=800,
            rating_change=50,
            recorded_at=datetime(2023, 11, 14, tzinfo=timezone.utc),
        )
        # User B's contest participation
        self.participation_b = ContestParticipation(
            profile_id=self.profile_b.id,
            contest_id=self.contest.id,
            rank=500,
            old_rating=750,
            new_rating=800,
            rating_change=50,
            solved=1,
            penalty=None,
        )
        # User B's goal
        self.goal_b = Goal(
            user_id=self.user_b.id,
            title="B's goal",
            goal_type=GoalType.PROBLEMS,
            target_value=10,
            status=GoalStatus.ACTIVE,
        )
        self.session.add_all(
            [self.sub_b, self.rating_b, self.participation_b, self.goal_b]
        )
        self.session.commit()

        # Build the FastAPI test app with user A as the authenticated user
        _app = FastAPI()
        _app.include_router(analytics_router.router)
        _app.include_router(sub_router.router)
        _app.include_router(rh_router.router)
        _app.include_router(cp_router.router)
        _app.include_router(goals_router.router)
        _app.include_router(pp_router.router)

        def override_db():
            yield self.session

        _app.dependency_overrides[get_db] = override_db
        # By default, user A is authenticated
        _app.dependency_overrides[get_current_user] = lambda: self.user_a

        self.app = _app
        self.client = TestClient(_app)

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # ------------------------------------------------------------------
    # Test 8: Authenticated user can access their own profile via analytics
    # ------------------------------------------------------------------

    def test_user_can_access_own_analytics(self):
        resp = self.client.get(f"/analytics/{self.profile_a.id}/summary")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["profile_id"], self.profile_a.id)

    # ------------------------------------------------------------------
    # Test 9: User cannot access another user's profile via analytics (403)
    # ------------------------------------------------------------------

    def test_user_cannot_access_other_users_analytics(self):
        resp = self.client.get(f"/analytics/{self.profile_b.id}/summary")
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_access_other_users_submission_activity(self):
        resp = self.client.get(
            f"/analytics/{self.profile_b.id}/submission-activity"
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_access_other_users_difficulty_distribution(self):
        resp = self.client.get(
            f"/analytics/{self.profile_b.id}/difficulty-distribution"
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_access_other_users_rating_progression(self):
        resp = self.client.get(
            f"/analytics/{self.profile_b.id}/rating-progression"
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_access_other_users_contest_performance(self):
        resp = self.client.get(
            f"/analytics/{self.profile_b.id}/contest-performance"
        )
        self.assertEqual(resp.status_code, 403)

    # ------------------------------------------------------------------
    # Test 10: User cannot access another user's submissions
    # ------------------------------------------------------------------

    def test_user_cannot_list_other_users_submissions(self):
        resp = self.client.get(
            f"/submissions/?profile_id={self.profile_b.id}"
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_get_other_users_submission_by_id(self):
        resp = self.client.get(f"/submissions/{self.sub_b.id}")
        self.assertEqual(resp.status_code, 403)

    # ------------------------------------------------------------------
    # Test 11: User cannot access another user's contest participation /
    #          rating history
    # ------------------------------------------------------------------

    def test_user_cannot_list_other_users_rating_history(self):
        resp = self.client.get(
            f"/rating-history/?profile_id={self.profile_b.id}"
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_get_other_users_rating_by_id(self):
        resp = self.client.get(f"/rating-history/{self.rating_b.id}")
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_list_other_users_contest_participations(self):
        resp = self.client.get(
            f"/contest-participations/?profile_id={self.profile_b.id}"
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_get_other_users_participation_by_id(self):
        resp = self.client.get(
            f"/contest-participations/{self.participation_b.id}"
        )
        self.assertEqual(resp.status_code, 403)

    # ------------------------------------------------------------------
    # Test 12: User cannot modify another user's goal
    # ------------------------------------------------------------------

    def test_user_cannot_get_other_users_goal(self):
        resp = self.client.get(f"/goals/{self.goal_b.id}")
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_patch_other_users_goal(self):
        resp = self.client.patch(
            f"/goals/{self.goal_b.id}",
            json={"title": "Hijacked"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_delete_other_users_goal(self):
        resp = self.client.delete(f"/goals/{self.goal_b.id}")
        self.assertEqual(resp.status_code, 403)

    def test_goal_list_is_scoped_to_current_user(self):
        """GET /goals/ must return only user A's goals, not user B's."""
        # Create a goal for user A
        resp = self.client.post(
            "/goals/",
            json={
                "title": "A's goal",
                "goal_type": "problems",
                "target_value": 5,
            },
        )
        self.assertEqual(resp.status_code, 201)

        resp = self.client.get("/goals/")
        self.assertEqual(resp.status_code, 200)
        goal_ids = [g["id"] for g in resp.json()]
        # Must not include user B's goal
        self.assertNotIn(self.goal_b.id, goal_ids)

    def test_goal_create_uses_authenticated_user_id(self):
        """POST /goals/ must assign the authenticated user's id."""
        resp = self.client.post(
            "/goals/",
            json={
                "title": "New goal",
                "goal_type": "problems",
                "target_value": 3,
            },
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["user_id"], self.user_a.id)

    # ------------------------------------------------------------------
    # Test 13: Platform profile ownership
    # ------------------------------------------------------------------

    def test_user_cannot_get_other_users_platform_profile(self):
        resp = self.client.get(f"/platform-profiles/{self.profile_b.id}")
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_patch_other_users_platform_profile(self):
        resp = self.client.patch(
            f"/platform-profiles/{self.profile_b.id}",
            json={"username": "hacked"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_user_cannot_delete_other_users_platform_profile(self):
        resp = self.client.delete(f"/platform-profiles/{self.profile_b.id}")
        self.assertEqual(resp.status_code, 403)

    def test_platform_profiles_list_is_scoped_to_current_user(self):
        resp = self.client.get("/platform-profiles/")
        self.assertEqual(resp.status_code, 200)
        profile_ids = [p["id"] for p in resp.json()]
        self.assertIn(self.profile_a.id, profile_ids)
        self.assertNotIn(self.profile_b.id, profile_ids)
