"""Goal Historical Progress Tests.

Tests that new goals start at 0% progress despite historical activity,
ensuring only activity after the goal's effective start date counts.

Coverage:
  1. New Problems goal starts at 0 despite historical solved problems
  2. Problems before goal start date are ignored
  3. Problems after goal start date count
  4. Difficulty filter is respected in date-filtered progress
  5. Platform filter is respected in date-filtered progress
  6. New Topic goal (LeetCode) starts at 0 despite historical topic progress
  7. Topic activity after goal start increases progress (LeetCode baseline)
  8. Consistency goal ignores active days before start
  9. Contest goal ignores contests before start
 10. Rating goal establishes appropriate starting value (baseline)
 11. Goal reaches 100% only when target is achieved within goal period
 12. Existing goal with explicit start_date calculates correctly
 13. Existing goal with no start_date uses created_at as effective start
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
from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.enums import Difficulty, GoalStatus, GoalType, Platform, SubmissionStatus
from app.models.goal import Goal
from app.models.platform_profile import PlatformProfile
from app.models.platform_topic_stat import PlatformTopicStat
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
from app.models.user import User
from app.routers import goals as goals_router


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
    """submitted_at can be a date or datetime."""
    if isinstance(submitted_at, date) and not isinstance(submitted_at, datetime):
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


class GoalHistoricalProgressTests(TestCase):
    """Tests for preventing historical activity from immediately completing new goals."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

        self.user = User(username="history-user", email="history@example.com", password_hash="h")
        self.session.add(self.user)
        self.session.flush()

        self.cf_profile = PlatformProfile(
            user_id=self.user.id,
            platform=Platform.CODEFORCES,
            username="historycf",
            current_rating=1500,
            max_rating=1550,
        )
        self.lc_profile = PlatformProfile(
            user_id=self.user.id,
            platform=Platform.LEETCODE,
            username="historylc",
            current_rating=1700,
            problems_solved=150,
            solved_easy=60,
            solved_medium=70,
            solved_hard=20,
        )
        self.session.add_all([self.cf_profile, self.lc_profile])
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

    # ---- Test 1: New Problems goal starts at 0 despite historical activity ----

    def test_new_problems_goal_starts_at_zero(self):
        """New Problems goal should start at 0% even if user has historical solved problems."""
        # Create historical problems solved BEFORE goal creation
        p1 = _make_problem(self.session, "H1", "Historical 1", Difficulty.MEDIUM)
        p2 = _make_problem(self.session, "H2", "Historical 2", Difficulty.MEDIUM)
        p3 = _make_problem(self.session, "H3", "Historical 3", Difficulty.MEDIUM)

        # Solve problems 30 days ago (well before goal start)
        old_date = date.today() - timedelta(days=30)
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, old_date)
        _make_accepted_submission(self.session, self.cf_profile.id, p2.id, old_date)
        _make_accepted_submission(self.session, self.cf_profile.id, p3.id, old_date)
        self.session.commit()

        # Create goal TODAY (start_date defaults to today)
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Solve 10 new problems",
                "goal_type": "problems",
                "target_value": 10,
                "deadline": str(date.today() + timedelta(days=30)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        # Goal should start at 0/10, not 3/10
        self.assertEqual(data["current_value"], 0)
        self.assertEqual(data["target_value"], 10)
        self.assertEqual(data["progress_percentage"], 0.0)
        self.assertEqual(data["remaining"], 10)
        self.assertEqual(data["status"], "active")
        self.assertFalse(data["is_completed"])

    # ---- Test 2: Problems before goal start date are ignored ----

    def test_problems_before_start_date_ignored(self):
        """Problems solved before the goal's start_date must not count."""
        p1 = _make_problem(self.session, "B1", "Before 1", Difficulty.EASY)
        p2 = _make_problem(self.session, "B2", "Before 2", Difficulty.EASY)

        # Solve 2 problems 10 days ago
        before = date.today() - timedelta(days=10)
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, before)
        _make_accepted_submission(self.session, self.cf_profile.id, p2.id, before)
        self.session.commit()

        # Create goal with start_date = 5 days ago (so the 2 old problems don't count)
        start = date.today() - timedelta(days=5)
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Recent problems only",
                "goal_type": "problems",
                "target_value": 5,
                "start_date": str(start),
                "deadline": str(date.today() + timedelta(days=25)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertEqual(data["current_value"], 0)

    # ---- Test 3: Problems after goal start date count ----

    def test_problems_after_start_date_count(self):
        """Problems solved after the goal's start_date must count toward progress."""
        p1 = _make_problem(self.session, "A1", "After 1", Difficulty.MEDIUM)
        p2 = _make_problem(self.session, "A2", "After 2", Difficulty.MEDIUM)
        p3 = _make_problem(self.session, "A3", "After 3", Difficulty.MEDIUM)

        # Start goal 5 days ago
        start = date.today() - timedelta(days=5)

        # Solve p1 and p2 AFTER start date
        yesterday = date.today() - timedelta(days=1)
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, yesterday)
        _make_accepted_submission(self.session, self.cf_profile.id, p2.id, date.today())

        # Solve p3 BEFORE start date (should NOT count)
        before = date.today() - timedelta(days=10)
        _make_accepted_submission(self.session, self.cf_profile.id, p3.id, before)
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={
                "title": "Count after start",
                "goal_type": "problems",
                "target_value": 5,
                "start_date": str(start),
                "deadline": str(date.today() + timedelta(days=25)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Only p1 and p2 (submitted after start_date)
        self.assertEqual(data["current_value"], 2)
        self.assertEqual(data["remaining"], 3)

    # ---- Test 4: Difficulty filter is respected ----

    def test_difficulty_filter_respected(self):
        """Only problems matching the difficulty filter should count."""
        p_easy = _make_problem(self.session, "DE1", "Diff Easy", Difficulty.EASY)
        p_medium = _make_problem(self.session, "DM1", "Diff Medium", Difficulty.MEDIUM)
        p_hard = _make_problem(self.session, "DH1", "Diff Hard", Difficulty.HARD)

        today = date.today()
        _make_accepted_submission(self.session, self.cf_profile.id, p_easy.id, today)
        _make_accepted_submission(self.session, self.cf_profile.id, p_medium.id, today)
        _make_accepted_submission(self.session, self.cf_profile.id, p_hard.id, today)
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={
                "title": "Medium problems only",
                "goal_type": "problems",
                "target_value": 5,
                "difficulty_filter": "Medium",
                "deadline": str(today + timedelta(days=30)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Only p_medium counts
        self.assertEqual(data["current_value"], 1)

    # ---- Test 5: Platform filter is respected ----

    def test_platform_filter_respected(self):
        """Only problems from the specified platform should count."""
        p_cf = _make_problem(self.session, "PF1", "CF Problem", Difficulty.MEDIUM, Platform.CODEFORCES)
        p_lc = _make_problem(self.session, "PF2", "LC Problem", Difficulty.MEDIUM, Platform.LEETCODE)

        today = date.today()
        _make_accepted_submission(self.session, self.cf_profile.id, p_cf.id, today)
        _make_accepted_submission(self.session, self.lc_profile.id, p_lc.id, today)
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={
                "title": "Codeforces only",
                "goal_type": "problems",
                "target_value": 5,
                "platform": "codeforces",
                "deadline": str(today + timedelta(days=30)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Only p_cf counts
        self.assertEqual(data["current_value"], 1)

    # ---- Test 6: New Topic goal (LeetCode) starts at 0 despite historical progress ----

    def test_new_topic_goal_leetcode_starts_at_zero(self):
        """New Topic goal (LeetCode) should start at 0 despite historical topic count."""
        # User already has 35 DP problems solved historically
        _make_platform_topic_stat(
            self.session, self.lc_profile.id,
            "dynamic-programming", "Dynamic Programming", 35
        )
        self.session.commit()

        # Create new goal for 10 DP problems
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Solve 10 new DP problems",
                "goal_type": "topic",
                "target_value": 10,
                "platform": "leetcode",
                "topic_slug": "dynamic-programming",
                "topic_name": "Dynamic Programming",
                "deadline": str(date.today() + timedelta(days=60)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        # Goal should start at 0/10, not 35/10 (which would be 100% immediately)
        self.assertEqual(data["current_value"], 0)
        self.assertEqual(data["target_value"], 10)
        self.assertEqual(data["progress_percentage"], 0.0)
        self.assertEqual(data["remaining"], 10)
        self.assertFalse(data["is_completed"])
        # Baseline (start_value) should be recorded as 35
        self.assertEqual(data["start_value"], 35)

    # ---- Test 7: Topic progress increases after goal creation (LeetCode baseline) ----

    def test_topic_progress_increases_leetcode(self):
        """After goal creation, solving more topic problems increases progress."""
        # User has 35 DP problems solved
        topic_stat = _make_platform_topic_stat(
            self.session, self.lc_profile.id,
            "dynamic-programming", "Dynamic Programming", 35
        )
        self.session.commit()

        # Create goal
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Solve 10 new DP",
                "goal_type": "topic",
                "target_value": 10,
                "platform": "leetcode",
                "topic_slug": "dynamic-programming",
                "topic_name": "Dynamic Programming",
            },
        )
        goal_id = resp.json()["id"]

        # Simulate solving 5 more DP problems (update stat to 40)
        topic_stat.solved_count = 40
        self.session.commit()

        # Check progress
        resp = self.client.get(f"/goals/{goal_id}/progress")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # Progress = 40 - 35 = 5
        self.assertEqual(data["current_value"], 5)
        self.assertEqual(data["remaining"], 5)
        self.assertAlmostEqual(data["progress_percentage"], 50.0)

    # ---- Test 8: Consistency goal ignores active days before start ----

    def test_consistency_ignores_days_before_start(self):
        """Active days before the goal's start_date must not count."""
        p1 = _make_problem(self.session, "CO1", "Cons 1", Difficulty.EASY)
        p2 = _make_problem(self.session, "CO2", "Cons 2", Difficulty.EASY)

        # Active days BEFORE goal start (20 days ago, 19 days ago)
        old1 = date.today() - timedelta(days=20)
        old2 = date.today() - timedelta(days=19)
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, old1)
        _make_accepted_submission(self.session, self.cf_profile.id, p2.id, old2)

        # Active day AFTER goal start (today)
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, date.today())
        self.session.commit()

        # Goal starts 7 days ago
        start = date.today() - timedelta(days=7)
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Code 10 days",
                "goal_type": "consistency",
                "target_value": 10,
                "start_date": str(start),
                "deadline": str(date.today() + timedelta(days=23)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Only today counts (old1 and old2 are before start_date)
        self.assertEqual(data["current_value"], 1)

    # ---- Test 9: Contest goal ignores contests before start ----

    def test_contest_ignores_before_start(self):
        """Contests before the goal's start_date must not count."""
        today = date.today()
        start = date.today() - timedelta(days=10)

        # Contest BEFORE start
        c_old = _make_contest(
            self.session, Platform.CODEFORCES, "C-OLD", "Old Contest",
            datetime(today.year, today.month, today.day, 12, tzinfo=timezone.utc) - timedelta(days=60)
        )
        # Contest AFTER start (today)
        c_new = _make_contest(
            self.session, Platform.CODEFORCES, "C-NEW", "New Contest",
            datetime(today.year, today.month, today.day, 12, tzinfo=timezone.utc)
        )
        _make_participation(self.session, self.cf_profile.id, c_old.id)
        _make_participation(self.session, self.cf_profile.id, c_new.id)
        self.session.commit()

        resp = self.client.post(
            "/goals/",
            json={
                "title": "Attend 5 contests",
                "goal_type": "contest",
                "target_value": 5,
                "platform": "codeforces",
                "start_date": str(start),
                "deadline": str(today + timedelta(days=20)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        # Only c_new counts
        self.assertEqual(data["current_value"], 1)

    # ---- Test 10: Rating goal establishes starting baseline ----

    def test_rating_goal_baseline(self):
        """Rating goal should record current rating as start_value."""
        # User's current CF rating is 1500
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

        # start_value should be 1500, current_value = 1500, target = 1700
        self.assertEqual(data["start_value"], 1500)
        self.assertEqual(data["current_value"], 1500)
        self.assertEqual(data["target_value"], 1700)
        self.assertEqual(data["remaining"], 200)
        self.assertFalse(data["is_completed"])

    # ---- Test 11: Goal reaches 100% only when target achieved within period ----

    def test_goal_completes_only_when_target_reached(self):
        """Goal should become 'completed' only when current_value >= target_value."""
        p1 = _make_problem(self.session, "T1", "Target 1", Difficulty.EASY)
        p2 = _make_problem(self.session, "T2", "Target 2", Difficulty.EASY)

        today = date.today()
        # Historical problems (before goal)
        old = today - timedelta(days=40)
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, old)

        # Only 1 problem solved after goal creation
        _make_accepted_submission(self.session, self.cf_profile.id, p2.id, today)
        self.session.commit()

        # Goal = solve 3 problems
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Solve 3",
                "goal_type": "problems",
                "target_value": 3,
                "deadline": str(today + timedelta(days=30)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        # Only 1 problem (p2) solved after goal start, target is 3
        self.assertEqual(data["current_value"], 1)
        self.assertEqual(data["status"], "active")
        self.assertFalse(data["is_completed"])
        self.assertLess(data["progress_percentage"], 100.0)

    # ---- Test 12: Existing goal with explicit start_date calculates correctly ----

    def test_existing_goal_explicit_start_date(self):
        """Existing goal with explicit start_date uses that date for progress."""
        p1 = _make_problem(self.session, "EX1", "Exist 1", Difficulty.MEDIUM)
        p2 = _make_problem(self.session, "EX2", "Exist 2", Difficulty.MEDIUM)

        start = date.today() - timedelta(days=10)
        before = date.today() - timedelta(days=15)
        after = date.today() - timedelta(days=5)

        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, before)
        _make_accepted_submission(self.session, self.cf_profile.id, p2.id, after)
        self.session.commit()

        # Create goal with explicit start_date
        resp = self.client.post(
            "/goals/",
            json={
                "title": "Existing goal test",
                "goal_type": "problems",
                "target_value": 5,
                "start_date": str(start),
                "deadline": str(date.today() + timedelta(days=20)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        # Only p2 (submitted AFTER start_date) should count
        self.assertEqual(data["current_value"], 1)

    # ---- Test 13: Existing goal without start_date uses created_at ----

    def test_existing_goal_no_start_date_uses_created_at(self):
        """Goal without explicit start_date defaults to goal creation date."""
        # This is already tested implicitly, but let's be explicit
        p1 = _make_problem(self.session, "NO1", "No start 1", Difficulty.EASY)

        # Solve problem yesterday (before goal creation)
        yesterday = date.today() - timedelta(days=1)
        _make_accepted_submission(self.session, self.cf_profile.id, p1.id, yesterday)
        self.session.commit()

        # Create goal WITHOUT explicit start_date (defaults to today)
        resp = self.client.post(
            "/goals/",
            json={
                "title": "No explicit start",
                "goal_type": "problems",
                "target_value": 5,
                "deadline": str(date.today() + timedelta(days=30)),
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()

        # start_date defaults to today, so yesterday's problem doesn't count
        self.assertEqual(data["start_date"], str(date.today()))
        self.assertEqual(data["current_value"], 0)
