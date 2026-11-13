"""Tests for per-user AI Coach rate limiting (Stage 4).

Coverage:
- requests within the limit succeed
- exceeding the limit returns HTTP 429 with a Retry-After header
- per-user quotas are independent
- failed provider requests still consume quota
- force_refresh does not bypass the limit
- both /ai-coach/recommend and /ai-coach/chat are limited
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
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.base import Base
from app.models.enums import Platform
from app.models.platform_profile import PlatformProfile
from app.models.user import User
from app.routers import recommendations as recommendations_router
from app.services.recommendation_agent import (
    AgentRecommendation,
    AgentRecommendationResult,
)
from app.services.gemini_service import GeminiProviderError
from app.services import coach_cache

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


def _make_user(db, tag: str) -> User:
    global _user_counter
    _user_counter += 1
    u = User(
        username=f"rl{tag}{_user_counter}",
        email=f"rl{tag}{_user_counter}@example.com",
        password_hash="hashed",
        is_active=True,
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def user(db):
    coach_cache.clear()
    u = _make_user(db, "u")
    _test_user_holder[:] = [u]
    yield u
    _test_user_holder.clear()


@pytest.fixture()
def client(user):
    return TestClient(test_app)


def _recommend_agent():
    agent = MagicMock()
    agent.is_configured.return_value = True
    agent.last_model = "gemini-test"
    agent.last_usage = None
    agent.recommend.return_value = AgentRecommendationResult(
        recommendations=[],
        agent_reasoning="nothing to recommend",
        has_sufficient_data=False,
        catalog_limited=False,
        tool_calls_made=[],
        error=None,
    )
    return agent


def _chat_service():
    svc = MagicMock()
    svc.is_configured.return_value = True
    svc.last_model = "gemini-test"
    svc.last_usage = None
    svc.generate_coach_response = AsyncMock(return_value="coach says hi")
    return svc


class TestRecommendRateLimit:
    def test_within_limit_succeeds(self, client, monkeypatch):
        monkeypatch.setattr(settings, "AI_COACH_RECOMMEND_RATE_LIMIT", 3)
        agent = _recommend_agent()
        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            for _ in range(3):
                r = client.post("/ai-coach/recommend?force_refresh=true")
                assert r.status_code == 200

    def test_exceeding_limit_returns_429_with_retry_after(
        self, client, monkeypatch
    ):
        monkeypatch.setattr(settings, "AI_COACH_RECOMMEND_RATE_LIMIT", 1)
        monkeypatch.setattr(settings, "AI_COACH_RATE_LIMIT_WINDOW_SECONDS", 120)
        agent = _recommend_agent()
        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            assert client.post("/ai-coach/recommend").status_code == 200
            r = client.post("/ai-coach/recommend")
            assert r.status_code == 429
            retry_after = r.headers.get("Retry-After")
            assert retry_after is not None
            assert 0 < int(retry_after) <= 121

    def test_failed_gemini_still_consumes_quota(self, client, monkeypatch):
        monkeypatch.setattr(settings, "AI_COACH_RECOMMEND_RATE_LIMIT", 1)
        agent = _recommend_agent()
        agent.recommend.return_value = AgentRecommendationResult(
            recommendations=[],
            error="provider down",
            error_kind="provider_unavailable",
            has_sufficient_data=False,
        )
        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            r1 = client.post("/ai-coach/recommend?force_refresh=true")
            assert r1.status_code == 200  # provider errors are 200 + error field
            r2 = client.post("/ai-coach/recommend?force_refresh=true")
            assert r2.status_code == 429

    def test_force_refresh_does_not_bypass_limit(self, client, monkeypatch):
        monkeypatch.setattr(settings, "AI_COACH_RECOMMEND_RATE_LIMIT", 1)
        agent = _recommend_agent()
        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            assert client.post("/ai-coach/recommend").status_code == 200
            r = client.post("/ai-coach/recommend?force_refresh=true")
            assert r.status_code == 429
            assert r.headers.get("Retry-After") is not None

    def test_users_have_independent_quotas(self, client, db, monkeypatch):
        monkeypatch.setattr(settings, "AI_COACH_RECOMMEND_RATE_LIMIT", 1)
        agent = _recommend_agent()
        other = _make_user(db, "other")

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            assert client.post("/ai-coach/recommend?force_refresh=true").status_code == 200
            assert client.post("/ai-coach/recommend?force_refresh=true").status_code == 429

            _test_user_holder[:] = [other]
            r = client.post("/ai-coach/recommend?force_refresh=true")
            assert r.status_code == 200


class TestChatRateLimit:
    def test_chat_within_limit(self, client, monkeypatch):
        monkeypatch.setattr(settings, "AI_COACH_CHAT_RATE_LIMIT", 2)
        svc = _chat_service()
        with patch("app.routers.recommendations.GeminiService", return_value=svc):
            for _ in range(2):
                r = client.post("/ai-coach/chat", json={"message": "hi"})
                assert r.status_code == 200

    def test_chat_exceeding_limit_429(self, client, monkeypatch):
        monkeypatch.setattr(settings, "AI_COACH_CHAT_RATE_LIMIT", 1)
        svc = _chat_service()
        with patch("app.routers.recommendations.GeminiService", return_value=svc):
            assert client.post("/ai-coach/chat", json={"message": "hi"}).status_code == 200
            r = client.post("/ai-coach/chat", json={"message": "hi again"})
            assert r.status_code == 429
            assert r.headers.get("Retry-After") is not None

    def test_chat_failed_gemini_counts(self, client, monkeypatch):
        monkeypatch.setattr(settings, "AI_COACH_CHAT_RATE_LIMIT", 1)
        svc = _chat_service()
        svc.generate_coach_response = AsyncMock(
            side_effect=GeminiProviderError("down", is_retryable=True, kind="provider_unavailable")
        )
        with patch("app.routers.recommendations.GeminiService", return_value=svc):
            r1 = client.post("/ai-coach/chat", json={"message": "hi"})
            assert r1.status_code == 503
            r2 = client.post("/ai-coach/chat", json={"message": "hi"})
            assert r2.status_code == 429

    def test_chat_and_recommend_quotas_are_independent(
        self, client, monkeypatch
    ):
        monkeypatch.setattr(settings, "AI_COACH_CHAT_RATE_LIMIT", 1)
        monkeypatch.setattr(settings, "AI_COACH_RECOMMEND_RATE_LIMIT", 1)
        svc = _chat_service()
        agent = _recommend_agent()
        with patch("app.routers.recommendations.GeminiService", return_value=svc), patch(
            "app.routers.recommendations.RecommendationAgent", return_value=agent
        ):
            assert client.post("/ai-coach/chat", json={"message": "hi"}).status_code == 200
            # Chat quota exhausted but recommend quota is separate.
            assert client.post("/ai-coach/chat", json={"message": "hi"}).status_code == 429
            assert client.post("/ai-coach/recommend?force_refresh=true").status_code == 200
