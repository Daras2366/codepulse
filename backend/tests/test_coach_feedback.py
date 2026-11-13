"""Tests for recommendation persistence and POST /ai-coach/feedback (Stage 4).

Coverage:
- recommendations persisted per successful uncached run (run_id, rank, user)
- no persistence on failed/cached runs
- feedback validation (invalid action → 422)
- feedback ownership / cross-user isolation (404)
- idempotent duplicate submissions
- multiple distinct actions allowed
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

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
from app.models.coach import CoachFeedback, CoachRecommendation, CoachRun
from app.models.enums import CoachFeedbackAction, Difficulty, Platform
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.enums import SubmissionStatus
from app.models.user import User
from app.routers import recommendations as recommendations_router
from app.services import coach_cache
from app.services.recommendation_agent import (
    AgentRecommendation,
    AgentRecommendationResult,
)

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
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


_user_counter = 0


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def user(db):
    global _user_counter
    _user_counter += 1
    coach_cache.clear()
    u = User(
        username=f"fb{_user_counter}",
        email=f"fb{_user_counter}@example.com",
        password_hash="hashed",
        is_active=True,
    )
    db.add(u)
    db.commit()
    _test_user_holder[:] = [u]
    yield u
    _test_user_holder.clear()


@pytest.fixture()
def client(user):
    return TestClient(test_app)


@pytest.fixture()
def seeded(db, user):
    profile = PlatformProfile(
        user_id=user.id, platform=Platform.LEETCODE, username="lc_fb"
    )
    problems = []
    for i, slug in enumerate([f"fb-one-{user.id}", f"fb-two-{user.id}"]):
        p = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id=slug,
            title=f"FB Problem {i}",
            slug=f"fb-prob-{user.id}-{i}",
            problem_url=f"https://leetcode.com/problems/{slug}/",
            difficulty=Difficulty.EASY,
        )
        problems.append(p)
    db.add(profile)
    db.add_all(problems)
    db.flush()
    db.add(
        Submission(
            profile_id=profile.id,
            problem_id=problems[0].id,
            submitted_at=datetime.now(timezone.utc),
            language="Python3",
            status=SubmissionStatus.ACCEPTED,
            platform_submission_id=f"fb-sub-{user.id}",
        )
    )
    db.commit()
    return profile, problems


def _agent_for(problems):
    agent = MagicMock()
    agent.is_configured.return_value = True
    agent.last_model = "gemini-test"
    agent.last_usage = None
    agent.recommend.return_value = AgentRecommendationResult(
        recommendations=[
            AgentRecommendation(
                problem_id=p.id,
                title=p.title,
                platform="leetcode",
                difficulty="Easy",
                url=p.problem_url,
                topics=[],
                reason="r",
                priority=i + 1,
                likely_unsolved=True,
            )
            for i, p in enumerate(problems)
        ],
        agent_reasoning="picked",
        has_sufficient_data=True,
        tool_calls_made=[],
    )
    return agent


def _generate_recommendations(client, db, problems):
    """Run one uncached recommend and return the response JSON."""
    agent = _agent_for(problems)
    with patch(
        "app.routers.recommendations.RecommendationAgent", return_value=agent
    ):
        r = client.post("/ai-coach/recommend?force_refresh=true")
        assert r.status_code == 200
        return r.json()


class TestRecommendationPersistence:
    def test_recommendations_persisted_with_rank_and_run(
        self, client, db, user, seeded
    ):
        _, problems = seeded
        data = _generate_recommendations(client, db, problems)

        recs = (
            db.query(CoachRecommendation)
            .filter(CoachRecommendation.user_id == user.id)
            .order_by(CoachRecommendation.rank)
            .all()
        )
        assert len(recs) == 2
        assert [r.problem_id for r in recs] == [p.id for p in problems]
        assert [r.rank for r in recs] == [1, 2]

        run = db.query(CoachRun).filter(CoachRun.id == recs[0].run_id).one()
        assert run.endpoint == "ai-coach/recommend"
        assert run.user_id == user.id

        # Response exposes stable recommendation ids.
        resp_ids = [r["recommendation_id"] for r in data["recommendations"]]
        assert resp_ids == [r.id for r in recs]

    def test_cached_run_does_not_duplicate_recommendations(
        self, client, db, user, seeded
    ):
        _, problems = seeded
        _generate_recommendations(client, db, problems)
        # Second (cached) call must not create new recommendation rows.
        client.post("/ai-coach/recommend")
        count = (
            db.query(CoachRecommendation)
            .filter(CoachRecommendation.user_id == user.id)
            .count()
        )
        assert count == 2

    def test_failed_run_persists_nothing(self, client, db, user, seeded):
        result = AgentRecommendationResult(
            recommendations=[],
            error="boom",
            error_kind="provider_unavailable",
            has_sufficient_data=False,
        )
        agent = MagicMock()
        agent.is_configured.return_value = True
        agent.last_model = None
        agent.last_usage = None
        agent.recommend.return_value = result
        with patch(
            "app.routers.recommendations.RecommendationAgent", return_value=agent
        ):
            client.post("/ai-coach/recommend?force_refresh=true")

        assert (
            db.query(CoachRecommendation)
            .filter(CoachRecommendation.user_id == user.id)
            .count()
            == 0
        )


class TestFeedbackEndpoint:
    def _rec_id(self, client, db, problems):
        data = _generate_recommendations(client, db, problems)
        return data["recommendations"][0]["recommendation_id"]

    def test_thumbs_up_recorded(self, client, db, user, seeded):
        _, problems = seeded
        rec_id = self._rec_id(client, db, problems)
        r = client.post(
            "/ai-coach/feedback",
            json={"recommendation_id": rec_id, "action": "thumbs_up"},
        )
        assert r.status_code == 200
        assert r.json()["recorded"] is True
        assert r.json()["action"] == "thumbs_up"

        fb = (
            db.query(CoachFeedback)
            .filter(CoachFeedback.recommendation_id == rec_id)
            .one()
        )
        assert fb.action == CoachFeedbackAction.THUMBS_UP

    def test_duplicate_feedback_idempotent(self, client, db, user, seeded):
        _, problems = seeded
        rec_id = self._rec_id(client, db, problems)
        payload = {"recommendation_id": rec_id, "action": "thumbs_down"}

        r1 = client.post("/ai-coach/feedback", json=payload)
        r2 = client.post("/ai-coach/feedback", json=payload)
        assert r1.json()["recorded"] is True
        assert r2.json()["recorded"] is False

        count = (
            db.query(CoachFeedback)
            .filter(CoachFeedback.recommendation_id == rec_id)
            .count()
        )
        assert count == 1

    def test_different_actions_coexist(self, client, db, user, seeded):
        _, problems = seeded
        rec_id = self._rec_id(client, db, problems)
        client.post(
            "/ai-coach/feedback",
            json={"recommendation_id": rec_id, "action": "thumbs_up"},
        )
        client.post(
            "/ai-coach/feedback",
            json={"recommendation_id": rec_id, "action": "skipped"},
        )
        actions = {
            fb.action
            for fb in db.query(CoachFeedback)
            .filter(CoachFeedback.recommendation_id == rec_id)
            .all()
        }
        assert actions == {CoachFeedbackAction.THUMBS_UP, CoachFeedbackAction.SKIPPED}

    def test_invalid_action_rejected(self, client, db, user, seeded):
        _, problems = seeded
        rec_id = self._rec_id(client, db, problems)
        r = client.post(
            "/ai-coach/feedback",
            json={"recommendation_id": rec_id, "action": "bogus"},
        )
        assert r.status_code == 422

    def test_nonexistent_recommendation_404(self, client, user):
        r = client.post(
            "/ai-coach/feedback",
            json={"recommendation_id": 999999, "action": "thumbs_up"},
        )
        assert r.status_code == 404

    def test_cross_user_feedback_rejected(self, client, db, user, seeded):
        _, problems = seeded
        rec_id = self._rec_id(client, db, problems)

        other = User(
            username="fbother",
            email="fbother@example.com",
            password_hash="hashed",
            is_active=True,
        )
        db.add(other)
        db.commit()
        _test_user_holder[:] = [other]

        r = client.post(
            "/ai-coach/feedback",
            json={"recommendation_id": rec_id, "action": "thumbs_up"},
        )
        assert r.status_code == 404

    def test_feedback_requires_auth(self, client):
        saved = test_app.dependency_overrides.pop(get_current_user)
        try:
            r = client.post(
                "/ai-coach/feedback",
                json={"recommendation_id": 1, "action": "thumbs_up"},
            )
            assert r.status_code == 401
        finally:
            test_app.dependency_overrides[get_current_user] = saved
