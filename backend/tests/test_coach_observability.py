"""Tests for coach_runs observability (Stage 4).

Coverage:
- successful recommendation run logging (model, latency, tool names, tokens)
- cache-hit runs logged without pretending a Gemini call occurred
- failed runs logged with error_kind
- nullable token usage
- chat run logging
- persistence failures never break the API request
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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
from app.models.coach import CoachRun
from app.models.enums import Platform
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.enums import Difficulty, SubmissionStatus
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
        username=f"obs{_user_counter}",
        email=f"obs{_user_counter}@example.com",
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
    """Profile + problem + one submission so fingerprint is stable."""
    profile = PlatformProfile(
        user_id=user.id, platform=Platform.CODEFORCES, username="cf_obs"
    )
    problem = Problem(
        platform=Platform.CODEFORCES,
        platform_problem_id=f"555A-{user.id}",
        title="Obs Problem",
        slug=f"obs-{user.id}",
        problem_url=f"https://codeforces.com/problemset/problem/555/A?u={user.id}",
        difficulty=Difficulty.EASY,
    )
    db.add_all([profile, problem])
    db.flush()
    db.add(
        Submission(
            profile_id=profile.id,
            problem_id=problem.id,
            submitted_at=datetime.now(timezone.utc),
            language="Python3",
            status=SubmissionStatus.ACCEPTED,
            platform_submission_id=f"obs-sub-{user.id}",
        )
    )
    db.commit()
    return profile, problem


def _agent(result, usage=None, model="gemini-test"):
    agent = MagicMock()
    agent.is_configured.return_value = True
    agent.last_model = model
    agent.last_usage = usage
    agent.recommend.return_value = result
    return agent


def _result(problem):
    return AgentRecommendationResult(
        recommendations=[
            AgentRecommendation(
                problem_id=problem.id,
                title=problem.title,
                platform="codeforces",
                difficulty="Easy",
                url=problem.problem_url,
                topics=[],
                reason="r",
                priority=1,
                likely_unsolved=True,
            )
        ],
        agent_reasoning="why",
        has_sufficient_data=True,
        tool_calls_made=["get_user_performance_profile", "search_candidate_problems"],
    )


class TestRunObservability:
    def test_successful_run_logged(self, client, db, user, seeded):
        _, problem = seeded
        agent = _agent(
            _result(problem),
            usage={"prompt_token_count": 123, "candidates_token_count": 45},
        )
        with patch(
            "app.routers.recommendations.RecommendationAgent", return_value=agent
        ):
            r = client.post("/ai-coach/recommend?force_refresh=true")
            assert r.status_code == 200

        run = db.query(CoachRun).filter(CoachRun.user_id == user.id).one()
        assert run.endpoint == "ai-coach/recommend"
        assert run.model == "gemini-test"
        assert run.latency_ms is not None and run.latency_ms >= 0
        assert run.tool_calls == [
            "get_user_performance_profile",
            "search_candidate_problems",
        ]
        assert run.prompt_tokens == 123
        assert run.completion_tokens == 45
        assert run.cache_hit is False
        assert run.error_kind is None

    def test_cache_hit_run_logged_without_gemini(self, client, db, user, seeded):
        _, problem = seeded
        agent = _agent(_result(problem))
        with patch(
            "app.routers.recommendations.RecommendationAgent", return_value=agent
        ):
            assert client.post("/ai-coach/recommend").status_code == 200
            assert client.post("/ai-coach/recommend").status_code == 200

        runs = (
            db.query(CoachRun)
            .filter(CoachRun.user_id == user.id)
            .order_by(CoachRun.id)
            .all()
        )
        assert len(runs) == 2
        miss, hit = runs
        assert miss.cache_hit is False
        assert hit.cache_hit is True
        # The cache-hit run must not pretend tokens were consumed.
        assert hit.prompt_tokens is None
        assert hit.completion_tokens is None

    def test_failed_run_logged_with_error_kind(self, client, db, user, seeded):
        result = AgentRecommendationResult(
            recommendations=[],
            error="rate limited",
            error_kind="rate_limited",
            has_sufficient_data=False,
        )
        agent = _agent(result)
        with patch(
            "app.routers.recommendations.RecommendationAgent", return_value=agent
        ):
            r = client.post("/ai-coach/recommend?force_refresh=true")
            assert r.status_code == 200

        run = db.query(CoachRun).filter(CoachRun.user_id == user.id).one()
        assert run.error_kind == "rate_limited"
        assert run.cache_hit is False

    def test_nullable_token_usage(self, client, db, user, seeded):
        _, problem = seeded
        agent = _agent(_result(problem), usage=None)
        with patch(
            "app.routers.recommendations.RecommendationAgent", return_value=agent
        ):
            assert client.post("/ai-coach/recommend?force_refresh=true").status_code == 200

        run = db.query(CoachRun).filter(CoachRun.user_id == user.id).one()
        assert run.prompt_tokens is None
        assert run.completion_tokens is None

    def test_chat_run_logged(self, client, db, user):
        svc = MagicMock()
        svc.is_configured.return_value = True
        svc.last_model = "gemini-chat-model"
        svc.last_usage = {"prompt_token_count": 50, "candidates_token_count": 20}
        svc.generate_coach_response = AsyncMock(return_value="hello")

        with patch("app.routers.recommendations.GeminiService", return_value=svc):
            r = client.post("/ai-coach/chat", json={"message": "hi"})
            assert r.status_code == 200

        run = db.query(CoachRun).filter(CoachRun.user_id == user.id).one()
        assert run.endpoint == "ai-coach/chat"
        assert run.model == "gemini-chat-model"
        assert run.prompt_tokens == 50
        assert run.completion_tokens == 20
        assert run.tool_calls is None
        assert run.cache_hit is False
        assert run.error_kind is None

    def test_chat_failure_logged(self, client, db, user):
        from app.services.gemini_service import GeminiProviderError

        svc = MagicMock()
        svc.is_configured.return_value = True
        svc.last_model = None
        svc.last_usage = None
        svc.generate_coach_response = AsyncMock(
            side_effect=GeminiProviderError("down", is_retryable=True, kind="provider_unavailable")
        )

        with patch("app.routers.recommendations.GeminiService", return_value=svc):
            r = client.post("/ai-coach/chat", json={"message": "hi"})
            assert r.status_code == 503

        run = db.query(CoachRun).filter(CoachRun.user_id == user.id).one()
        assert run.endpoint == "ai-coach/chat"
        assert run.error_kind == "provider_unavailable"

    def test_observability_failure_does_not_break_request(
        self, client, db, user, seeded
    ):
        _, problem = seeded
        agent = _agent(_result(problem))
        with patch(
            "app.routers.recommendations.RecommendationAgent", return_value=agent
        ), patch(
            "app.services.coach_observability_service.CoachRunRepository.add",
            side_effect=RuntimeError("db exploded"),
        ):
            r = client.post("/ai-coach/recommend?force_refresh=true")
            assert r.status_code == 200
            assert r.json()["is_configured"] is True
