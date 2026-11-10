"""Tests for the personalized study plan and upcoming-contests endpoints.

Coverage:
- Study plan contains only real, unsolved Problem records
- Daily progress counts distinct ACCEPTED problems for the user's local day
- Daily target derives only from an active goal with a deadline (never invented)
- Focus topic comes from an active TOPIC goal or weak performance topic
- Upcoming contests exclude past events
- Insufficient-data state is honest (no fabricated plan)
- User isolation: solved problems of other users do not affect this user
"""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - registers all ORM models
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.base import Base
from app.models.contest import Contest
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
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
from app.models.user import User
from app.routers import recommendations as recommendations_router

# ---------------------------------------------------------------------------
# Test database — in-memory SQLite
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


_test_user_holder: list = []


def override_get_current_user():
    return _test_user_holder[0]


test_app = FastAPI()
test_app.include_router(recommendations_router.router)
test_app.dependency_overrides[get_db] = override_get_db
test_app.dependency_overrides[get_current_user] = override_get_current_user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def test_user(db):
    user = User(
        username="planuser",
        email="plan@example.com",
        password_hash="hashed",
        is_active=True,
    )
    db.add(user)
    db.commit()
    _test_user_holder.append(user)
    yield user
    _test_user_holder.clear()


@pytest.fixture(scope="module")
def client(test_user):
    return TestClient(test_app)


@pytest.fixture(scope="module")
def cf_profile(db, test_user):
    profile = PlatformProfile(
        user_id=test_user.id,
        platform=Platform.CODEFORCES,
        username="cf_plan_user",
        current_rating=1500,
    )
    db.add(profile)
    db.commit()
    return profile


@pytest.fixture(scope="module")
def topics(db):
    t1 = Topic(name="Dynamic Programming")
    t2 = Topic(name="Graphs")
    db.add_all([t1, t2])
    db.commit()
    return [t1, t2]


@pytest.fixture(scope="module")
def problems(db, topics):
    """Five catalog problems; p1 will be solved by the test user."""
    made = []
    for i, (pid, title, diff, url) in enumerate([
        ("10A", "Solved Today", Difficulty.EASY,
         "https://codeforces.com/problemset/problem/10/A"),
        ("10B", "DP Problem One", Difficulty.MEDIUM,
         "https://codeforces.com/problemset/problem/10/B"),
        ("10C", "DP Problem Two", Difficulty.MEDIUM,
         "https://codeforces.com/problemset/problem/10/C"),
        ("10D", "Graph Problem", Difficulty.HARD,
         "https://codeforces.com/problemset/problem/10/D"),
        ("10E", "Another Easy", Difficulty.EASY,
         "https://codeforces.com/problemset/problem/10/E"),
    ]):
        p = Problem(
            platform=Platform.CODEFORCES,
            platform_problem_id=pid,
            title=title,
            slug=f"cf-{pid.lower()}",
            problem_url=url,
            difficulty=diff,
            acceptance_rate=0.5,
        )
        db.add(p)
        made.append(p)
    db.commit()

    db.add(ProblemTopic(problem_id=made[1].id, topic_id=topics[0].id))
    db.add(ProblemTopic(problem_id=made[2].id, topic_id=topics[0].id))
    db.add(ProblemTopic(problem_id=made[3].id, topic_id=topics[1].id))
    db.commit()
    return made


@pytest.fixture(scope="module")
def submissions(db, cf_profile, problems):
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=3)
    rows = [
        # Accepted today (local day, UTC) — counts toward solved_today
        Submission(
            profile_id=cf_profile.id, problem_id=problems[0].id,
            submitted_at=now, language="Python3",
            status=SubmissionStatus.ACCEPTED,
            platform_submission_id="sp-1",
        ),
        # Accepted 3 days ago — solved but NOT today
        Submission(
            profile_id=cf_profile.id, problem_id=problems[4].id,
            submitted_at=old, language="Python3",
            status=SubmissionStatus.ACCEPTED,
            platform_submission_id="sp-2",
        ),
        # Wrong answer today — must NOT count as solved
        Submission(
            profile_id=cf_profile.id, problem_id=problems[1].id,
            submitted_at=now, language="Python3",
            status=SubmissionStatus.WRONG_ANSWER,
            platform_submission_id="sp-3",
        ),
    ]
    db.add_all(rows)
    db.commit()
    return rows


@pytest.fixture(scope="module")
def contests(db):
    now = datetime.now(timezone.utc)
    past = Contest(
        platform_contest_id="past-1", title="Past Contest",
        platform=Platform.CODEFORCES,
        contest_url="https://codeforces.com/contest/1",
        start_time=now - timedelta(days=2), duration_minutes=120,
    )
    future = Contest(
        platform_contest_id="future-1", title="Future Contest",
        platform=Platform.CODEFORCES,
        contest_url="https://codeforces.com/contest/2",
        start_time=now + timedelta(days=5), duration_minutes=150,
    )
    db.add_all([past, future])
    db.commit()
    return [past, future]


@pytest.fixture(scope="module")
def topic_goal(db, test_user):
    goal = Goal(
        user_id=test_user.id,
        title="Master Dynamic Programming",
        goal_type=GoalType.TOPIC,
        topic_name="Dynamic Programming",
        target_value=20,
        deadline=date.today() + timedelta(days=10),
        status=GoalStatus.ACTIVE,
    )
    db.add(goal)
    db.commit()
    return goal


# ---------------------------------------------------------------------------
# Study plan endpoint
# ---------------------------------------------------------------------------


class TestStudyPlan:
    def test_requires_data_and_returns_real_problems(
        self, client, submissions, problems, topic_goal
    ):
        resp = client.get("/ai-coach/study-plan?timezone=UTC")
        assert resp.status_code == 200
        data = resp.json()

        assert data["has_sufficient_data"] is True
        # Focus comes from the active TOPIC goal.
        assert data["focus_topic"] == "Dynamic Programming"
        assert data["focus_reason"] is not None

        # Every recommended problem is a real catalog row, unsolved by user.
        solved_ids = {problems[0].id, problems[4].id}
        returned_ids = [p["id"] for p in data["problems"]]
        assert len(returned_ids) == len(set(returned_ids))
        for pid in returned_ids:
            assert pid not in solved_ids, "Solved problem must not be planned"
            assert pid in {p.id for p in problems}

        # Problems carry real metadata.
        for p in data["problems"]:
            assert p["title"]
            assert p["url"].startswith("http")
            assert p["platform"] == "codeforces"
            assert p["estimated_minutes"] > 0

        assert data["problems_planned"] == len(data["problems"])
        assert data["total_estimated_minutes"] == sum(
            p["estimated_minutes"] for p in data["problems"]
        )
        assert data["estimate_note"]

    def test_daily_progress_counts_distinct_accepted_today(
        self, client, submissions
    ):
        resp = client.get("/ai-coach/study-plan?timezone=UTC")
        data = resp.json()
        # Exactly one ACCEPTED submission today (the WA one must not count,
        # and the accepted-3-days-ago must not count).
        assert data["daily"]["solved_today"] == 1
        assert data["daily"]["timezone"] == "UTC"

    def test_daily_target_derived_from_goal(self, client, topic_goal):
        resp = client.get("/ai-coach/study-plan?timezone=UTC")
        daily = resp.json()["daily"]
        # TOPIC goal counts problems → daily target must be a positive int
        # derived from remaining work / days left.
        assert daily["daily_target"] is not None
        assert daily["daily_target"] >= 1
        assert daily["target_source"] == "goal"
        assert "Master Dynamic Programming" in (daily["target_label"] or "")

    def test_upcoming_contest_is_future_only(self, client, contests):
        resp = client.get("/ai-coach/study-plan?timezone=UTC")
        contest = resp.json()["upcoming_contest"]
        assert contest is not None
        assert contest["title"] == "Future Contest"
        assert contest["contest_url"].startswith("http")
        start = datetime.fromisoformat(contest["start_time"].replace("Z", "+00:00"))
        assert start > datetime.now(timezone.utc)

    def test_invalid_timezone_falls_back_to_utc(self, client, submissions):
        resp = client.get("/ai-coach/study-plan?timezone=Not/AZone")
        assert resp.status_code == 200
        assert resp.json()["daily"]["timezone"] == "UTC"


# ---------------------------------------------------------------------------
# Upcoming contests endpoint
# ---------------------------------------------------------------------------


class TestUpcomingContests:
    def test_returns_only_future_contests(self, client, contests):
        resp = client.get("/ai-coach/upcoming-contests")
        assert resp.status_code == 200
        data = resp.json()
        titles = [c["title"] for c in data]
        assert "Past Contest" not in titles
        assert "Future Contest" in titles
        for c in data:
            start = datetime.fromisoformat(c["start_time"].replace("Z", "+00:00"))
            assert start > datetime.now(timezone.utc)

    def test_limit_is_clamped(self, client, contests):
        resp = client.get("/ai-coach/upcoming-contests?limit=100")
        assert resp.status_code == 200
        assert len(resp.json()) <= 20


# ---------------------------------------------------------------------------
# Insufficient data
# ---------------------------------------------------------------------------


class TestStudyPlanInsufficientData:
    def test_user_without_profiles_gets_honest_empty_plan(self, db):
        """A fresh user with no submissions gets an honest empty state."""
        from app.services.study_plan_service import StudyPlanService

        lonely = User(
            username="lonely", email="lonely@example.com",
            password_hash="x", is_active=True,
        )
        db.add(lonely)
        db.commit()
        try:
            plan = StudyPlanService(db).build_plan(lonely.id, tz_name="UTC")
            assert plan.has_sufficient_data is False
            assert plan.problems == []
            assert plan.daily.daily_target is None
            assert plan.daily.solved_today == 0
            assert plan.upcoming_contest is not None  # global contest data still real
            assert any("sync" in lim.lower() or "data" in lim.lower() for lim in plan.limitations)
        finally:
            db.delete(lonely)
            db.commit()
