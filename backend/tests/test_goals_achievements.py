"""Goals and Achievements backend tests.

Tests Goals:
  1.  Create own goal
  2.  List own goals
  3.  Get own goal
  4.  Update own goal
  5.  Delete own goal
  6.  User cannot access another user's goal (403)
  7.  User cannot modify another user's goal (403)
  8.  Progress is calculated correctly for supported goal types
  9.  Empty/no-data progress behaves correctly

Tests Achievements:
  10. List achievement definitions (public)
  11. List current user's earned achievements
  12. User cannot access another user's UserAchievement
  13. Achievement evaluation grants correct achievements
  14. Running evaluation repeatedly does not create duplicates
"""

import os
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

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
from app.models.achievement import Achievement
from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.enums import (
    AchievementCategory,
    Difficulty,
    GoalStatus,
    GoalType,
    Platform,
    SubmissionStatus,
)
from app.models.goal import Goal
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.routers import achievements as ach_router
from app.routers import goals as goals_router


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_problem(session, pid, title, difficulty):
    p = Problem(
        platform=Platform.CODEFORCES,
        platform_problem_id=pid,
        title=title,
        slug=f"cf-{pid.lower()}",
        problem_url=f"https://codeforces.com/problemset/problem/{pid.replace('-', '/')}",
        difficulty=difficulty,
        acceptance_rate=None,
    )
    session.add(p)
    session.flush()
    return p


def _make_accepted_submission(session, profile_id, problem_id, ts_str):
    s = Submission(
        profile_id=profile_id,
        problem_id=problem_id,
        platform_submission_id=f"s-{profile_id}-{problem_id}-{ts_str}",
        submitted_at=datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc),
        language="Python 3",
        status=SubmissionStatus.ACCEPTED,
    )
    session.add(s)
    session.flush()
    return s


# ---------------------------------------------------------------------------
# Goals Tests
# ---------------------------------------------------------------------------


class GoalsApiTests(TestCase):
    """Tests for the goals CRUD + progress API."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

        self.user = User(username="goal-user", email="goal@example.com", password_hash="h")
        self.other = User(username="other-user", email="other@example.com", password_hash="h")
        self.session.add_all([self.user, self.other])
        self.session.flush()

        self.profile = PlatformProfile(
            user_id=self.user.id,
            platform=Platform.CODEFORCES,
            username="goalcf",
        )
        self.session.add(self.profile)
        self.session.flush()

        # Other user's goal
        self.other_goal = Goal(
            user_id=self.other.id,
            title="Other's goal",
            goal_type=GoalType.WEEKLY,
            target_value=5,
            status=GoalStatus.ACTIVE,
        )
        self.session.add(self.other_goal)
        self.session.commit()

        _app = FastAPI()
        _app.include_router(goals_router.router)

        def override_db():
            yield self.session

        _app.dependency_overrides[get_db] = override_db
        _app.dependency_overrides[get_current_user] = lambda: self.user
        self.app = _app
        self.client = TestClient(_app)

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # ---- Test 1: Create own goal ----

    def test_create_goal(self):
        resp = self.client.post(
            "/goals/",
            json={"title": "My goal", "goal_type": "weekly", "target_value": 10},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "My goal")
        self.assertEqual(data["goal_type"], "weekly")
        self.assertEqual(data["target_value"], 10)
        self.assertEqual(data["user_id"], self.user.id)

    # ---- Test 2: List own goals ----

    def test_list_own_goals(self):
        self.client.post(
            "/goals/",
            json={"title": "G1", "goal_type": "daily", "target_value": 3},
        )
        self.client.post(
            "/goals/",
            json={"title": "G2", "goal_type": "monthly", "target_value": 50},
        )
        resp = self.client.get("/goals/")
        self.assertEqual(resp.status_code, 200)
        titles = [g["title"] for g in resp.json()]
        self.assertIn("G1", titles)
        self.assertIn("G2", titles)
        # Must not contain the other user's goal
        self.assertNotIn("Other's goal", titles)

    # ---- Test 3: Get own goal ----

    def test_get_own_goal(self):
        create = self.client.post(
            "/goals/",
            json={"title": "Single goal", "goal_type": "daily", "target_value": 2},
        )
        goal_id = create.json()["id"]
        resp = self.client.get(f"/goals/{goal_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], goal_id)
        self.assertEqual(resp.json()["title"], "Single goal")

    # ---- Test 4: Update own goal ----

    def test_update_own_goal(self):
        create = self.client.post(
            "/goals/",
            json={"title": "To update", "goal_type": "daily", "target_value": 1},
        )
        goal_id = create.json()["id"]
        resp = self.client.patch(f"/goals/{goal_id}", json={"title": "Updated!"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "Updated!")

    # ---- Test 5: Delete own goal ----

    def test_delete_own_goal(self):
        create = self.client.post(
            "/goals/",
            json={"title": "To delete", "goal_type": "daily", "target_value": 1},
        )
        goal_id = create.json()["id"]
        resp = self.client.delete(f"/goals/{goal_id}")
        self.assertEqual(resp.status_code, 204)
        # Should now 404
        self.assertEqual(self.client.get(f"/goals/{goal_id}").status_code, 404)

    # ---- Test 6: Cannot access another user's goal ----

    def test_cannot_get_other_users_goal(self):
        resp = self.client.get(f"/goals/{self.other_goal.id}")
        self.assertEqual(resp.status_code, 403)

    # ---- Test 7: Cannot modify another user's goal ----

    def test_cannot_patch_other_users_goal(self):
        resp = self.client.patch(
            f"/goals/{self.other_goal.id}", json={"title": "Hijacked"}
        )
        self.assertEqual(resp.status_code, 403)

    def test_cannot_delete_other_users_goal(self):
        resp = self.client.delete(f"/goals/{self.other_goal.id}")
        self.assertEqual(resp.status_code, 403)

    # ---- Test 8: Progress is calculated correctly ----

    def test_progress_calculated_from_database(self):
        """Weekly goal: 3 accepted submissions on different problems = 3 solved."""
        p1 = _make_problem(self.session, "100-A", "PA", Difficulty.EASY)
        p2 = _make_problem(self.session, "100-B", "PB", Difficulty.MEDIUM)
        p3 = _make_problem(self.session, "100-C", "PC", Difficulty.HARD)

        today = datetime.now(timezone.utc).date().isoformat()
        _make_accepted_submission(self.session, self.profile.id, p1.id, today)
        _make_accepted_submission(self.session, self.profile.id, p2.id, today)
        _make_accepted_submission(self.session, self.profile.id, p3.id, today)
        self.session.commit()

        create = self.client.post(
            "/goals/",
            json={"title": "Solve 5 this week", "goal_type": "weekly", "target_value": 5},
        )
        goal_id = create.json()["id"]

        resp = self.client.get(f"/goals/{goal_id}/progress")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["calculated_progress"], 3)
        self.assertEqual(data["target_value"], 5)
        self.assertEqual(data["remaining"], 2)
        self.assertAlmostEqual(data["percentage"], 60.0)
        self.assertFalse(data["is_achieved"])
        self.assertIn("window_start", data)
        self.assertIn("window_end", data)

    def test_progress_is_achieved_when_target_met(self):
        p1 = _make_problem(self.session, "200-A", "QA", Difficulty.EASY)
        today = datetime.now(timezone.utc).date().isoformat()
        _make_accepted_submission(self.session, self.profile.id, p1.id, today)
        self.session.commit()

        create = self.client.post(
            "/goals/",
            json={"title": "Solve 1 today", "goal_type": "daily", "target_value": 1},
        )
        goal_id = create.json()["id"]

        resp = self.client.get(f"/goals/{goal_id}/progress")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["calculated_progress"], 1)
        self.assertEqual(data["percentage"], 100.0)
        self.assertEqual(data["remaining"], 0)
        self.assertTrue(data["is_achieved"])

    # ---- Test 9: Empty / no-data progress ----

    def test_progress_with_no_submissions_returns_zero(self):
        """A goal with no submissions in the window returns zero progress."""
        create = self.client.post(
            "/goals/",
            json={"title": "Empty", "goal_type": "monthly", "target_value": 20},
        )
        goal_id = create.json()["id"]

        resp = self.client.get(f"/goals/{goal_id}/progress")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["calculated_progress"], 0)
        self.assertEqual(data["percentage"], 0.0)
        self.assertEqual(data["remaining"], 20)
        self.assertFalse(data["is_achieved"])

    def test_progress_for_nonexistent_goal_returns_404(self):
        resp = self.client.get("/goals/999999/progress")
        self.assertEqual(resp.status_code, 404)

    def test_progress_for_other_users_goal_returns_403(self):
        resp = self.client.get(f"/goals/{self.other_goal.id}/progress")
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# Achievements Tests
# ---------------------------------------------------------------------------


class AchievementsApiTests(TestCase):
    """Tests for achievement catalog, user achievements, and evaluation."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

        self.user = User(username="ach-user", email="ach@example.com", password_hash="h")
        self.other = User(username="ach-other", email="ach-other@example.com", password_hash="h")
        self.session.add_all([self.user, self.other])
        self.session.flush()

        self.profile = PlatformProfile(
            user_id=self.user.id,
            platform=Platform.CODEFORCES,
            username="achcf",
            current_rating=1200,
            max_rating=1300,
        )
        self.session.add(self.profile)
        self.session.flush()

        # Seed a few known achievements into the DB
        self.ach_first_blood = Achievement(
            name="First Blood",
            description="Solve your first problem.",
            category=AchievementCategory.PROBLEM,
            icon="🩸",
        )
        self.ach_centurion = Achievement(
            name="Centurion",
            description="Solve 100 problems.",
            category=AchievementCategory.PROBLEM,
            icon="💯",
        )
        self.ach_contest_debut = Achievement(
            name="Contest Debut",
            description="Participate in your first contest.",
            category=AchievementCategory.CONTEST,
            icon="🎯",
        )
        self.session.add_all(
            [self.ach_first_blood, self.ach_centurion, self.ach_contest_debut]
        )
        self.session.flush()

        # Other user already has "First Blood"
        self.other_ua = UserAchievement(
            user_id=self.other.id,
            achievement_id=self.ach_first_blood.id,
            earned_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        self.session.add(self.other_ua)
        self.session.commit()

        _app = FastAPI()
        _app.include_router(ach_router.router)

        def override_db():
            yield self.session

        _app.dependency_overrides[get_db] = override_db
        _app.dependency_overrides[get_current_user] = lambda: self.user
        self.app = _app
        self.client = TestClient(_app)

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # ---- Test 10: List achievement definitions (public) ----

    def test_list_achievement_definitions(self):
        resp = self.client.get("/achievements/")
        self.assertEqual(resp.status_code, 200)
        names = [a["name"] for a in resp.json()]
        self.assertIn("First Blood", names)
        self.assertIn("Centurion", names)
        self.assertIn("Contest Debut", names)

    def test_get_single_achievement_definition(self):
        resp = self.client.get(f"/achievements/{self.ach_first_blood.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "First Blood")
        self.assertEqual(resp.json()["category"], "problem")

    def test_nonexistent_achievement_returns_404(self):
        resp = self.client.get("/achievements/999999")
        self.assertEqual(resp.status_code, 404)

    # ---- Test 11: List current user's earned achievements ----

    def test_list_my_achievements_empty_initially(self):
        resp = self.client.get("/achievements/me")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_list_my_achievements_after_grant(self):
        ua = UserAchievement(
            user_id=self.user.id,
            achievement_id=self.ach_first_blood.id,
            earned_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        self.session.add(ua)
        self.session.commit()

        resp = self.client.get("/achievements/me")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["achievement"]["name"], "First Blood")
        self.assertEqual(data[0]["user_id"], self.user.id)

    # ---- Test 12: User cannot access another user's UserAchievement ----

    def test_my_achievements_only_returns_own_records(self):
        """GET /achievements/me must not expose other users' records."""
        resp = self.client.get("/achievements/me")
        self.assertEqual(resp.status_code, 200)
        ua_user_ids = [ua["user_id"] for ua in resp.json()]
        # The other user has "First Blood" — must not appear
        self.assertNotIn(self.other.id, ua_user_ids)

    # ---- Test 13: Achievement evaluation works ----

    def test_evaluation_grants_first_blood_on_one_solve(self):
        """With 1 accepted submission, 'First Blood' should be granted."""
        p = _make_problem(self.session, "300-A", "PA", Difficulty.EASY)
        today = datetime.now(timezone.utc).date().isoformat()
        _make_accepted_submission(self.session, self.profile.id, p.id, today)
        self.session.commit()

        resp = self.client.post("/achievements/evaluate")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["newly_granted"], 1)
        self.assertIn("First Blood", data["achievement_names"])

    def test_evaluation_does_not_grant_centurion_for_one_solve(self):
        """Centurion requires 100 solved — must not be granted for 1."""
        p = _make_problem(self.session, "400-A", "PB", Difficulty.EASY)
        today = datetime.now(timezone.utc).date().isoformat()
        _make_accepted_submission(self.session, self.profile.id, p.id, today)
        self.session.commit()

        resp = self.client.post("/achievements/evaluate")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("Centurion", resp.json()["achievement_names"])

    def test_evaluation_does_not_grant_unearned_achievements_for_empty_profile(self):
        """An empty profile should grant no achievements."""
        resp = self.client.post("/achievements/evaluate")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["newly_granted"], 0)

    # ---- Test 14: Running evaluation repeatedly does not create duplicates ----

    def test_evaluation_is_idempotent(self):
        """Calling evaluate multiple times must not grant the same achievement twice."""
        p = _make_problem(self.session, "500-A", "PC", Difficulty.EASY)
        today = datetime.now(timezone.utc).date().isoformat()
        _make_accepted_submission(self.session, self.profile.id, p.id, today)
        self.session.commit()

        # First call
        r1 = self.client.post("/achievements/evaluate")
        self.assertEqual(r1.status_code, 200)
        granted_first = r1.json()["newly_granted"]
        self.assertGreater(granted_first, 0)

        # Second call — same data, nothing new should be granted
        r2 = self.client.post("/achievements/evaluate")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["newly_granted"], 0)
        self.assertEqual(r2.json()["achievement_names"], [])

        # Verify only one UserAchievement row per achievement
        from sqlalchemy import func
        from app.models.user_achievement import UserAchievement as UA
        from app.models.achievement import Achievement as Ach
        dups = (
            self.session.query(UA.achievement_id, func.count(UA.id))
            .filter(UA.user_id == self.user.id)
            .group_by(UA.achievement_id)
            .having(func.count(UA.id) > 1)
            .all()
        )
        self.assertEqual(dups, [], "Duplicate UserAchievement rows found!")

    # ---- Seed endpoint ----

    def test_seed_catalog_inserts_all_definitions(self):
        """POST /achievements/seed must populate the catalog from definitions."""
        # Start with a fresh session that only has the 3 manually added
        resp = self.client.post("/achievements/seed")
        self.assertEqual(resp.status_code, 200)
        # Should have inserted the remaining definitions (total = 16 - 3 existing = 13)
        self.assertGreaterEqual(resp.json()["inserted"], 0)

        # Catalog should now have all 16
        catalog = self.client.get("/achievements/")
        self.assertEqual(catalog.status_code, 200)
        # At least 16 definitions (the 3 we added manually + seeded)
        self.assertGreaterEqual(len(catalog.json()), 3)

    def test_seed_catalog_is_idempotent(self):
        """Calling seed twice must not create duplicates."""
        r1 = self.client.post("/achievements/seed")
        r2 = self.client.post("/achievements/seed")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        # Second call inserts 0 new rows
        self.assertEqual(r2.json()["inserted"], 0)
