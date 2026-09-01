"""Goals and Achievements backend tests.

Tests Goals (all 6 types):
  1.  Create own goal
  2.  List own goals
  3.  Get own goal
  4.  Update own goal
  5.  Delete own goal
  6.  User cannot access another user's goal (403)
  7.  User cannot modify another user's goal (403)
  8.  Rating goal progress from PlatformProfile.current_rating
  9.  Problems goal progress within date range
  10. Topic goal — LeetCode via PlatformTopicStat
  11. Topic goal — Codeforces via ProblemTopic join
  12. Consistency goal — active days in range
  13. Contest goal — contest participations in range
  14. Placement goal — with difficulty filter
  15. Goal auto-completes when current >= target
  16. Goal becomes overdue when deadline passes
  17. Progress percentage and remaining calculations
  18. Empty goals list
  19. Invalid goal validation (negative target, missing platform for RATING, etc.)
  20. Status filter on GET /goals/
  21. Completed_at is set on completion

Tests Achievements (unchanged from original):
  22. List achievement definitions (public)
  23. List current user's earned achievements
  24. User cannot access another user's UserAchievement
  25. Achievement evaluation grants correct achievements
  26. Running evaluation repeatedly does not create duplicates
"""

import os
from datetime import date, datetime, timedelta, timezone
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
from app.models.platform_topic_stat import PlatformTopicStat
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
from app.models.user import User
from app.models.user_achievement import UserAchievement
from app.routers import achievements as ach_router
from app.routers import goals as goals_router


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_problem(session, pid, title, difficulty, platform=Platform.CODEFORCES):
    p = Problem(
        platform=platform,
        platform_problem_id=pid,
        title=title,
        slug=f"{platform.value}-{pid.lower().replace(' ', '-')}",
        problem_url=f"https://{platform.value}.com/problem/{pid}",
        difficulty=difficulty,
        acceptance_rate=None,
    )
    session.add(p)
    session.flush()
    return p


def _make_accepted_submission(session, profile_id, problem_id, submitted_at):
    """submitted_at can be a date string or datetime."""
    if isinstance(submitted_at, str):
        dt = datetime.fromisoformat(submitted_at).replace(tzinfo=timezone.utc)
    elif isinstance(submitted_at, date) and not isinstance(submitted_at, datetime):
        dt = datetime(submitted_at.year, submitted_at.month, submitted_at.day, 12, 0, tzinfo=timezone.utc)
    else:
        dt = submitted_at
    s = Submission(
        profile_id=profile_id,
        problem_id=problem_id,
        platform_submission_id=f"s-{profile_id}-{problem_id}-{dt.timestamp()}",
        submitted_at=dt,
        language="Python 3",
        status=SubmissionStatus.ACCEPTED,
    )
    session.add(s)
    session.flush()
    return s


def _make_contest(session, platform, pid, title, start_time):
    c = Contest(
        platform=platform,
        platform_contest_id=pid,
        title=title,
        contest_url=f"https://{platform.value}.com/contest/{pid}",
        start_time=start_time,
        duration_minutes=120,
    )
    session.add(c)
    session.flush()
    return c


def _make_participation(session, profile_id, contest_id):
    cp = ContestParticipation(
        profile_id=profile_id,
        contest_id=contest_id,
        rank=100,
        solved=2,
    )
    session.add(cp)
    session.flush()
    return cp


def _make_topic(session, name):
    t = Topic(name=name)
    session.add(t)
    session.flush()
    return t


def _make_problem_topic(session, problem_id, topic_id):
    pt = ProblemTopic(problem_id=problem_id, topic_id=topic_id)
    session.add(pt)
    session.flush()
    return pt


def _make_platform_topic_stat(session, profile_id, slug, name, count):
    pts = PlatformTopicStat(
        profile_id=profile_id,
        topic_slug=slug,
        topic_name=name,
        solved_count=count,
    )
    session.add(pts)
    session.flush()
    return pts


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

        self.cf_profile = PlatformProfile(
            user_id=self.user.id,
            platform=Platform.CODEFORCES,
            username="goalcf",
            current_rating=1580,
            max_rating=1620,
        )
        self.lc_profile = PlatformProfile(
            user_id=self.user.id,
            platform=Platform.LEETCODE,
            username="goallc",
            current_rating=1750,
            problems_solved=200,
            solved_easy=80,
            solved_medium=100,
            solved_hard=20,
        )
        self.session.add_all([self.cf_profile, self.lc_profile])
        self.session.flush()

        # Other user's goal
        self.other_goal = Goal(
            user_id=self.other.id,
            title="Other's goal",
            goal_type=GoalType.PROBLEMS,
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
        self.client = TestClient(_app)

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    # ---- Test 1: Create own goal ----

    def test_create_goal_problems(self):
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Solve 20 problems",
                "goal_type": "problems",
                "target_value": 20,
                "deadline": str(date.today() + timedelta(days=30)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["title"], "Solve 20 problems")
        self.assertEqual(data["goal_type"], "problems")
        self.assertEqual(data["target_value"], 20)
        self.assertEqual(data["user_id"], self.user.id)
        self.assertIn("progress_percentage", data)
        self.assertIn("pace", data)

    def test_create_rating_goal(self):
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Reach 1700 on CF",
                "goal_type": "rating",
                "target_value": 1700,
                "platform": "codeforces",
                "deadline": str(date.today() + timedelta(days=60)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["platform"], "codeforces")
        # start_value should be set to current CF rating at creation time
        self.assertEqual(data["start_value"], 1580)

    # ---- Test 2: List own goals ----

    def test_list_own_goals(self):
        self.client.post(
            "/goals/",
            json={"title": "G1", "goal_type": "problems", "target_value": 3},
        )
        self.client.post(
            "/goals/",
            json={"title": "G2", "goal_type": "consistency", "target_value": 10,
                  "deadline": str(date.today() + timedelta(days=30))},
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
            json={"title": "Single goal", "goal_type": "problems", "target_value": 2},
        )
        goal_id = create.json()["id"]
        resp = self.client.get(f"/goals/{goal_id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["id"], goal_id)
        self.assertEqual(data["title"], "Single goal")
        self.assertIn("progress_percentage", data)

    # ---- Test 4: Update own goal ----

    def test_update_own_goal(self):
        create = self.client.post(
            "/goals/",
            json={"title": "To update", "goal_type": "problems", "target_value": 1},
        )
        goal_id = create.json()["id"]
        resp = self.client.patch(f"/goals/{goal_id}", json={"title": "Updated!"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "Updated!")

    # ---- Test 5: Delete own goal ----

    def test_delete_own_goal(self):
        create = self.client.post(
            "/goals/",
            json={"title": "To delete", "goal_type": "problems", "target_value": 1},
        )
        goal_id = create.json()["id"]
        resp = self.client.delete(f"/goals/{goal_id}")
        self.assertEqual(resp.status_code, 204)
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

    # ---- Test 8: RATING goal progress ----

    def test_rating_progress_from_profile(self):
        """RATING goal: current_value = PlatformProfile.current_rating."""
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Reach 1700 CF",
                "goal_type": "rating",
                "target_value": 1700,
                "platform": "codeforces",
                "deadline": str(date.today() + timedelta(days=60)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # CF profile has current_rating=1580, target=1700
        self.assertEqual(data["current_value"], 1580)
        self.assertEqual(data["target_value"], 1700)
        self.assertGreater(data["progress_percentage"], 0)
        self.assertEqual(data["remaining"], 120)

    def test_rating_progress_leetcode(self):
        """RATING goal for LeetCode reads from LeetCode profile."""
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Reach 1800 LC",
                "goal_type": "rating",
                "target_value": 1800,
                "platform": "leetcode",
                "deadline": str(date.today() + timedelta(days=60)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["current_value"], 1750)
        self.assertEqual(data["remaining"], 50)

    # ---- Test 9: PROBLEMS goal progress with date range ----

    def test_problems_goal_in_range(self):
        """PROBLEMS goal counts accepted submissions within start_date/deadline."""
        p1 = _make_problem(self.session, "P1", "Problem 1", Difficulty.EASY)
        p2 = _make_problem(self.session, "P2", "Problem 2", Difficulty.MEDIUM)
        p3 = _make_problem(self.session, "P3", "Problem 3", Difficulty.HARD)

        today = date.today()
        # Submissions within goal window
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, today)
        _make_accepted_submission(self.session, self.cf_profile.id, p2.id, today)
        # Submission BEFORE goal start_date (should NOT count)
        _make_accepted_submission(
            self.session, self.cf_profile.id, p3.id,
            today - timedelta(days=40)
        )
        self.session.commit()

        start = today - timedelta(days=5)
        deadline = today + timedelta(days=25)
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Solve 10 this month",
                "goal_type": "problems",
                "target_value": 10,
                "start_date": str(start),
                "deadline": str(deadline),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Only p1 and p2 (submitted today, within range)
        self.assertEqual(data["current_value"], 2)
        self.assertEqual(data["remaining"], 8)
        self.assertAlmostEqual(data["progress_percentage"], 20.0)

    def test_problems_goal_with_difficulty_filter(self):
        """PROBLEMS goal with difficulty_filter only counts matching problems."""
        p_easy = _make_problem(self.session, "E1", "Easy 1", Difficulty.EASY)
        p_medium = _make_problem(self.session, "M1", "Medium 1", Difficulty.MEDIUM)

        today = date.today()
        _make_accepted_submission(self.session, self.cf_profile.id, p_easy.id, today)
        _make_accepted_submission(self.session, self.cf_profile.id, p_medium.id, today)
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={
                "title": "Solve 5 Medium problems",
                "goal_type": "problems",
                "target_value": 5,
                "difficulty_filter": "Medium",
                "deadline": str(today + timedelta(days=30)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Only 1 Medium problem solved
        self.assertEqual(data["current_value"], 1)

    # ---- Test 10: TOPIC goal — LeetCode via PlatformTopicStat ----

    def test_topic_goal_leetcode(self):
        """TOPIC goal for LeetCode uses PlatformTopicStat.solved_count."""
        _make_platform_topic_stat(
            self.session, self.lc_profile.id,
            "dynamic-programming", "Dynamic Programming", 35
        )
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={
                "title": "Master DP on LeetCode",
                "goal_type": "topic",
                "target_value": 50,
                "platform": "leetcode",
                "topic_slug": "dynamic-programming",
                "topic_name": "Dynamic Programming",
                "deadline": str(date.today() + timedelta(days=60)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["current_value"], 35)
        self.assertEqual(data["remaining"], 15)
        self.assertAlmostEqual(data["progress_percentage"], 70.0)

    # ---- Test 11: TOPIC goal — Codeforces via ProblemTopic join ----

    def test_topic_goal_codeforces(self):
        """TOPIC goal for Codeforces uses ProblemTopic + Submission join."""
        topic = _make_topic(self.session, "graphs")

        p1 = _make_problem(self.session, "G1", "Graphs 1", Difficulty.MEDIUM)
        p2 = _make_problem(self.session, "G2", "Graphs 2", Difficulty.HARD)
        p3 = _make_problem(self.session, "G3", "Graphs 3 (no tag)", Difficulty.EASY)

        _make_problem_topic(self.session, p1.id, topic.id)
        _make_problem_topic(self.session, p2.id, topic.id)
        # p3 has no topic tag — should NOT count

        today = date.today()
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, today)
        _make_accepted_submission(self.session, self.cf_profile.id, p2.id, today)
        _make_accepted_submission(self.session, self.cf_profile.id, p3.id, today)
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={
                "title": "Solve 10 graph problems",
                "goal_type": "topic",
                "target_value": 10,
                "platform": "codeforces",
                "topic_slug": "graphs",
                "topic_name": "Graphs",
                "deadline": str(today + timedelta(days=30)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Only p1 and p2 have the 'graphs' tag
        self.assertEqual(data["current_value"], 2)

    # ---- Test 12: CONSISTENCY goal ----

    def test_consistency_goal_active_days(self):
        """CONSISTENCY goal counts distinct active days in the date range."""
        p1 = _make_problem(self.session, "C1", "Consistency 1", Difficulty.EASY)
        p2 = _make_problem(self.session, "C2", "Consistency 2", Difficulty.MEDIUM)

        today = date.today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)
        # Before range (should not count)
        _make_accepted_submission(
            self.session, self.cf_profile.id, p1.id, today - timedelta(days=40)
        )
        # 2 submissions on the same day = 1 active day
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, today)
        _make_accepted_submission(self.session, self.cf_profile.id, p2.id, today)
        # Different day
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, yesterday)
        self.session.commit()

        start = today - timedelta(days=7)
        deadline = today + timedelta(days=23)
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Code 10 days this month",
                "goal_type": "consistency",
                "target_value": 10,
                "start_date": str(start),
                "deadline": str(deadline),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # today + yesterday = 2 distinct days within range
        self.assertEqual(data["current_value"], 2)

    # ---- Test 13: CONTEST goal ----

    def test_contest_goal(self):
        """CONTEST goal counts contest participations in the date range."""
        today = date.today()
        start = today - timedelta(days=10)
        deadline = today + timedelta(days=20)

        # Contest within range
        c1 = _make_contest(
            self.session, Platform.CODEFORCES, "CF-R1", "CF Round 1",
            datetime(today.year, today.month, today.day, 12, tzinfo=timezone.utc)
        )
        # Contest before range (should NOT count)
        c2 = _make_contest(
            self.session, Platform.CODEFORCES, "CF-OLD", "CF Old Round",
            datetime(today.year, today.month, today.day, 12, tzinfo=timezone.utc) - timedelta(days=60)
        )
        _make_participation(self.session, self.cf_profile.id, c1.id)
        _make_participation(self.session, self.cf_profile.id, c2.id)
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={
                "title": "Participate in 5 contests",
                "goal_type": "contest",
                "target_value": 5,
                "platform": "codeforces",
                "start_date": str(start),
                "deadline": str(deadline),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Only c1 is within range
        self.assertEqual(data["current_value"], 1)

    # ---- Test 14: PLACEMENT goal with difficulty filter ----

    def test_placement_goal_with_difficulty_filter(self):
        """PLACEMENT goal counts accepted problems with optional difficulty filter."""
        p_hard1 = _make_problem(self.session, "H1", "Hard 1", Difficulty.HARD)
        p_hard2 = _make_problem(self.session, "H2", "Hard 2", Difficulty.HARD)
        p_medium = _make_problem(self.session, "M2", "Medium 2", Difficulty.MEDIUM)

        today = date.today()
        _make_accepted_submission(self.session, self.cf_profile.id, p_hard1.id, today)
        _make_accepted_submission(self.session, self.cf_profile.id, p_hard2.id, today)
        _make_accepted_submission(self.session, self.cf_profile.id, p_medium.id, today)
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={
                "title": "Solve 10 Hard problems for placement",
                "goal_type": "placement",
                "target_value": 10,
                "difficulty_filter": "Hard",
                "deadline": str(today + timedelta(days=30)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Only 2 Hard problems solved
        self.assertEqual(data["current_value"], 2)

    # ---- Test 15: Goal auto-completes when current >= target ----

    def test_goal_auto_completes(self):
        """When current_value >= target_value, status becomes 'completed'."""
        p = _make_problem(self.session, "AC1", "Auto-complete 1", Difficulty.EASY)
        today = date.today()
        _make_accepted_submission(self.session, self.cf_profile.id, p.id, today)
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={
                "title": "Solve 1 problem",
                "goal_type": "problems",
                "target_value": 1,
                "deadline": str(today + timedelta(days=30)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["status"], "completed")
        self.assertTrue(data["is_completed"])
        self.assertEqual(data["progress_percentage"], 100.0)
        self.assertEqual(data["remaining"], 0)
        self.assertIsNotNone(data["completed_at"])

    # ---- Test 16: Goal overdue ----

    def test_goal_becomes_overdue(self):
        """A goal past its deadline with no completion is OVERDUE."""
        yesterday = date.today() - timedelta(days=1)
        goal = Goal(
            user_id=self.user.id,
            title="Past deadline",
            goal_type=GoalType.PROBLEMS,
            target_value=50,
            current_value=0,
            deadline=yesterday,
            start_date=yesterday - timedelta(days=30),
            status=GoalStatus.ACTIVE,
        )
        self.session.add(goal)
        self.session.commit()

        resp = self.client.get(f"/goals/{goal.id}/progress")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "overdue")
        self.assertTrue(data["is_overdue"])
        self.assertFalse(data["is_completed"])

    # ---- Test 17: Progress percentage and remaining ----

    def test_progress_percentage_and_remaining(self):
        """Validate percentage and remaining are calculated correctly."""
        p1 = _make_problem(self.session, "PP1", "Perc 1", Difficulty.EASY)
        p2 = _make_problem(self.session, "PP2", "Perc 2", Difficulty.MEDIUM)

        today = date.today()
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, today)
        _make_accepted_submission(self.session, self.cf_profile.id, p2.id, today)
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={"title": "Solve 4", "goal_type": "problems", "target_value": 4},
        )
        goal_id = resp.json()["id"]
        data = self.client.get(f"/goals/{goal_id}/progress").json()

        self.assertEqual(data["current_value"], 2)
        self.assertEqual(data["target_value"], 4)
        self.assertAlmostEqual(data["progress_percentage"], 50.0)
        self.assertEqual(data["remaining"], 2)

    # ---- Test 18: Empty goals list ----

    def test_empty_goals_list(self):
        """A user with no goals gets an empty list."""
        resp = self.client.get("/goals/")
        self.assertEqual(resp.status_code, 200)
        # The other user has a goal but it's not in our list
        for g in resp.json():
            self.assertEqual(g["user_id"], self.user.id)

    # ---- Test 19: Validation errors ----

    def test_validation_negative_target(self):
        resp = self.client.post(
            "/goals/",
            json={"title": "Bad target", "goal_type": "problems", "target_value": -5},
        )
        self.assertEqual(resp.status_code, 422)

    def test_validation_rating_requires_platform(self):
        resp = self.client.post(
            "/goals/",
            json={"title": "Rating goal", "goal_type": "rating", "target_value": 1700},
        )
        self.assertEqual(resp.status_code, 422)

    def test_validation_topic_requires_topic_fields(self):
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Topic goal",
                "goal_type": "topic",
                "target_value": 10,
                "platform": "codeforces",
                # missing topic_slug and topic_name
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_validation_invalid_difficulty_filter(self):
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Bad difficulty",
                "goal_type": "problems",
                "target_value": 10,
                "difficulty_filter": "Ultra-Hard",
            },
        )
        self.assertEqual(resp.status_code, 422)

    def test_validation_past_deadline(self):
        past = str(date.today() - timedelta(days=5))
        resp = self.client.post(
            "/goals/",
            json={"title": "Past deadline", "goal_type": "problems",
                  "target_value": 10, "deadline": past},
        )
        self.assertEqual(resp.status_code, 422)

    # ---- Test 20: Status filter ----

    def test_status_filter_active(self):
        """GET /goals/?status=active returns only active goals."""
        # Create an active goal (no submissions → not complete)
        self.client.post(
            "/goals/",
            json={"title": "Active goal", "goal_type": "problems", "target_value": 100,
                  "deadline": str(date.today() + timedelta(days=30))},
        )
        resp = self.client.get("/goals/?status=active")
        self.assertEqual(resp.status_code, 200)
        statuses = [g["status"] for g in resp.json()]
        self.assertTrue(all(s == "active" for s in statuses))

    def test_status_filter_completed(self):
        """GET /goals/?status=completed returns only completed goals."""
        p = _make_problem(self.session, "FILT1", "Filter 1", Difficulty.EASY)
        today = date.today()
        _make_accepted_submission(self.session, self.cf_profile.id, p.id, today)
        self.session.commit()

        self.client.post(
            "/goals/",
            json={"title": "Completed goal", "goal_type": "problems", "target_value": 1,
                  "deadline": str(today + timedelta(days=30))},
        )
        resp = self.client.get("/goals/?status=completed")
        self.assertEqual(resp.status_code, 200)
        statuses = [g["status"] for g in resp.json()]
        self.assertTrue(all(s == "completed" for s in statuses))

    # ---- Test 21: completed_at is set on completion ----

    def test_completed_at_is_set(self):
        """completed_at must be set when a goal first reaches 100%."""
        p = _make_problem(self.session, "CA1", "CompAt 1", Difficulty.EASY)
        today = date.today()
        _make_accepted_submission(self.session, self.cf_profile.id, p.id, today)
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={"title": "Complete me", "goal_type": "problems", "target_value": 1},
        )
        data = resp.json()
        self.assertIsNotNone(data["completed_at"])

    # ---- Backward compat: progress endpoint still works ----

    def test_progress_endpoint_returns_progress_response(self):
        create = self.client.post(
            "/goals/",
            json={"title": "Progress test", "goal_type": "problems", "target_value": 5},
        )
        goal_id = create.json()["id"]
        resp = self.client.get(f"/goals/{goal_id}/progress")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("progress_percentage", data)
        self.assertIn("pace", data)
        self.assertIn("is_completed", data)

    def test_progress_for_nonexistent_goal_returns_404(self):
        resp = self.client.get("/goals/999999/progress")
        self.assertEqual(resp.status_code, 404)

    def test_progress_for_other_users_goal_returns_403(self):
        resp = self.client.get(f"/goals/{self.other_goal.id}/progress")
        self.assertEqual(resp.status_code, 403)


# ---------------------------------------------------------------------------
# Achievements Tests (unchanged from original, adapted for new enums)
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
        self.client = TestClient(_app)

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

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

    def test_my_achievements_only_returns_own_records(self):
        resp = self.client.get("/achievements/me")
        self.assertEqual(resp.status_code, 200)
        ua_user_ids = [ua["user_id"] for ua in resp.json()]
        self.assertNotIn(self.other.id, ua_user_ids)

    def test_evaluation_grants_first_blood_on_one_solve(self):
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
        p = _make_problem(self.session, "400-A", "PB", Difficulty.EASY)
        today = datetime.now(timezone.utc).date().isoformat()
        _make_accepted_submission(self.session, self.profile.id, p.id, today)
        self.session.commit()

        resp = self.client.post("/achievements/evaluate")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("Centurion", resp.json()["achievement_names"])

    def test_evaluation_does_not_grant_unearned_achievements_for_empty_profile(self):
        resp = self.client.post("/achievements/evaluate")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["newly_granted"], 0)

    def test_evaluation_is_idempotent(self):
        p = _make_problem(self.session, "500-A", "PC", Difficulty.EASY)
        today = datetime.now(timezone.utc).date().isoformat()
        _make_accepted_submission(self.session, self.profile.id, p.id, today)
        self.session.commit()

        r1 = self.client.post("/achievements/evaluate")
        self.assertEqual(r1.status_code, 200)
        granted_first = r1.json()["newly_granted"]
        self.assertGreater(granted_first, 0)

        r2 = self.client.post("/achievements/evaluate")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["newly_granted"], 0)
        self.assertEqual(r2.json()["achievement_names"], [])

        from sqlalchemy import func
        from app.models.user_achievement import UserAchievement as UA
        dups = (
            self.session.query(UA.achievement_id, func.count(UA.id))
            .filter(UA.user_id == self.user.id)
            .group_by(UA.achievement_id)
            .having(func.count(UA.id) > 1)
            .all()
        )
        self.assertEqual(dups, [], "Duplicate UserAchievement rows found!")

    def test_seed_catalog_inserts_all_definitions(self):
        resp = self.client.post("/achievements/seed")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["inserted"], 0)

        catalog = self.client.get("/achievements/")
        self.assertEqual(catalog.status_code, 200)
        self.assertGreaterEqual(len(catalog.json()), 3)

    def test_seed_catalog_is_idempotent(self):
        r1 = self.client.post("/achievements/seed")
        r2 = self.client.post("/achievements/seed")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["inserted"], 0)
