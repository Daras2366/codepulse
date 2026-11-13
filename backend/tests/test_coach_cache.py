"""Tests for POST /ai-coach/recommend caching (Stage 4).

Coverage:
- cache miss → generation, cache hit → no regeneration
- TTL expiration
- submission-based, goal-based, model-based and prompt-version invalidation
- force_refresh bypass + cache replacement
- cross-user isolation
- failed generations are never cached
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

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
from app.models.submission import Submission
from app.models.user import User
from app.routers import recommendations as recommendations_router
from app.services.recommendation_agent import (
    AgentRecommendation,
    AgentRecommendationResult,
)
from app.services import coach_cache

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


_user_counter = 0


@pytest.fixture()
def user(db):
    """Function-scoped user so each test gets a clean fingerprint."""
    global _user_counter
    _user_counter += 1
    coach_cache.clear()
    u = User(
        username=f"cacheuser{_user_counter}",
        email=f"cache{_user_counter}@example.com",
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
def profile(db, user):
    p = PlatformProfile(
        user_id=user.id,
        platform=Platform.CODEFORCES,
        username="cf_cache_user",
    )
    db.add(p)
    db.commit()
    return p


@pytest.fixture()
def problem(db, user):
    p = Problem(
        platform=Platform.CODEFORCES,
        platform_problem_id=f"999A-{user.id}",
        title="Cache Test Problem",
        slug=f"cache-test-{user.id}",
        problem_url=f"https://codeforces.com/problemset/problem/999/A?u={user.id}",
        difficulty=Difficulty.EASY,
    )
    db.add(p)
    db.commit()
    return p


def _add_submission(db, profile, problem, when=None, status=SubmissionStatus.ACCEPTED):
    sub = Submission(
        profile_id=profile.id,
        problem_id=problem.id,
        submitted_at=when or datetime.now(timezone.utc),
        language="Python3",
        status=status,
        platform_submission_id=f"sub-{datetime.now().microsecond}-{problem.id}",
    )
    db.add(sub)
    db.commit()
    return sub


def _mock_agent(result=None, configured=True):
    agent = MagicMock()
    agent.is_configured.return_value = configured
    agent.last_model = "gemini-test"
    agent.last_usage = {"prompt_token_count": 10, "candidates_token_count": 5}
    if result is not None:
        agent.recommend.return_value = result
    return agent


def _success_result(problem):
    return AgentRecommendationResult(
        recommendations=[
            AgentRecommendation(
                problem_id=problem.id,
                title=problem.title,
                platform="codeforces",
                difficulty="Easy",
                url=problem.problem_url,
                topics=["Arrays"],
                reason="Weak area coverage.",
                priority=1,
                likely_unsolved=True,
            )
        ],
        agent_reasoning="Picked a problem.",
        has_sufficient_data=True,
        catalog_limited=False,
        tool_calls_made=["get_user_performance_profile"],
        error=None,
    )


def _post(client, force=False):
    url = "/ai-coach/recommend"
    if force:
        url += "?force_refresh=true"
    return client.post(url)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecommendationCache:
    def test_cache_miss_then_hit(self, client, db, user, profile, problem):
        _add_submission(db, profile, problem)
        agent = _mock_agent(_success_result(problem))

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            r1 = _post(client)
            assert r1.status_code == 200
            d1 = r1.json()
            assert d1["from_cache"] is False
            assert d1["refreshed_at"] is not None
            assert agent.recommend.call_count == 1

            r2 = _post(client)
            assert r2.status_code == 200
            d2 = r2.json()
            assert d2["from_cache"] is True
            # Same recommendations, same stable recommendation ids.
            assert [r["recommendation_id"] for r in d2["recommendations"]] == [
                r["recommendation_id"] for r in d1["recommendations"]
            ]
            assert agent.recommend.call_count == 1

    def test_ttl_expiration(self, client, db, user, profile, problem, monkeypatch):
        _add_submission(db, profile, problem)
        monkeypatch.setattr(settings, "AI_COACH_RECOMMEND_CACHE_TTL_SECONDS", 0.05)
        agent = _mock_agent(_success_result(problem))

        import time as _time

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            assert _post(client).json()["from_cache"] is False
            assert _post(client).json()["from_cache"] is True
            _time.sleep(0.1)
            assert _post(client).json()["from_cache"] is False
            assert agent.recommend.call_count == 2

    def test_submission_change_invalidates(self, client, db, user, profile, problem):
        _add_submission(db, profile, problem)
        agent = _mock_agent(_success_result(problem))

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            assert _post(client).json()["from_cache"] is False
            assert _post(client).json()["from_cache"] is True
            # A new submission changes the fingerprint → cache miss.
            _add_submission(db, profile, problem, status=SubmissionStatus.WRONG_ANSWER)
            assert _post(client).json()["from_cache"] is False
            assert agent.recommend.call_count == 2

    def test_goal_change_invalidates(self, client, db, user, profile, problem):
        _add_submission(db, profile, problem)
        agent = _mock_agent(_success_result(problem))

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            assert _post(client).json()["from_cache"] is False
            assert _post(client).json()["from_cache"] is True
            db.add(
                Goal(
                    user_id=user.id,
                    title="Solve 10 DP problems",
                    goal_type=GoalType.PROBLEMS,
                    target_value=10,
                )
            )
            db.commit()
            assert _post(client).json()["from_cache"] is False
            assert agent.recommend.call_count == 2

    def test_model_change_invalidates(self, client, db, user, profile, problem, monkeypatch):
        _add_submission(db, profile, problem)
        agent = _mock_agent(_success_result(problem))

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            assert _post(client).json()["from_cache"] is False
            assert _post(client).json()["from_cache"] is True
            monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-other-model")
            assert _post(client).json()["from_cache"] is False
            assert agent.recommend.call_count == 2

    def test_prompt_version_change_invalidates(
        self, client, db, user, profile, problem, monkeypatch
    ):
        _add_submission(db, profile, problem)
        agent = _mock_agent(_success_result(problem))

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            assert _post(client).json()["from_cache"] is False
            assert _post(client).json()["from_cache"] is True
            monkeypatch.setattr(
                coach_cache, "RECOMMENDATION_PROMPT_VERSION", "recommendation-agent-v2"
            )
            assert _post(client).json()["from_cache"] is False
            assert agent.recommend.call_count == 2

    def test_force_refresh_bypasses_and_replaces_cache(
        self, client, db, user, profile, problem
    ):
        _add_submission(db, profile, problem)
        agent = _mock_agent(_success_result(problem))

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            assert _post(client).json()["from_cache"] is False
            # Force refresh generates fresh even though cache is warm.
            r = _post(client, force=True)
            assert r.status_code == 200
            assert r.json()["from_cache"] is False
            assert agent.recommend.call_count == 2
            # The fresh result replaced the cache entry.
            assert _post(client).json()["from_cache"] is True
            assert agent.recommend.call_count == 2

    def test_cross_user_isolation(self, client, db, user, profile, problem):
        _add_submission(db, profile, problem)
        other = User(
            username="othercache",
            email="othercache@example.com",
            password_hash="hashed",
            is_active=True,
        )
        db.add(other)
        db.commit()
        agent = _mock_agent(_success_result(problem))

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            assert _post(client).json()["from_cache"] is False
            # Switch to the other user — must NOT see user1's cached result.
            _test_user_holder[:] = [other]
            r = _post(client)
            assert r.status_code == 200
            assert r.json()["from_cache"] is False
            assert agent.recommend.call_count == 2

    def test_failed_generation_not_cached(self, client, db, user, profile, problem):
        _add_submission(db, profile, problem)
        error_result = AgentRecommendationResult(
            recommendations=[],
            error="provider exploded",
            error_kind="provider_unavailable",
            has_sufficient_data=False,
        )
        agent = _mock_agent(error_result)

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            r1 = _post(client)
            assert r1.status_code == 200
            assert r1.json()["error_kind"] == "provider_unavailable"
            r2 = _post(client)
            assert r2.json()["from_cache"] is False
            assert agent.recommend.call_count == 2

    def test_unparseable_result_not_cached(self, client, db, user, profile, problem):
        """A result with an error and no recommendations is not cached."""
        _add_submission(db, profile, problem)
        bad_result = AgentRecommendationResult(
            recommendations=[],
            agent_reasoning="garbage",
            error="Agent response could not be parsed as JSON.",
            has_sufficient_data=False,
        )
        agent = _mock_agent(bad_result)

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            assert _post(client).json()["error"] is not None
            assert _post(client).json()["from_cache"] is False
            assert agent.recommend.call_count == 2

    def test_not_configured_not_cached(self, client, db, user, profile, problem):
        _add_submission(db, profile, problem)
        agent = _mock_agent(configured=False)

        with patch(
            "app.routers.recommendations.RecommendationAgent",
            return_value=agent,
        ):
            r1 = _post(client)
            assert r1.json()["is_configured"] is False
            r2 = _post(client)
            assert r2.json()["is_configured"] is False
            assert agent.recommend.call_count == 0
