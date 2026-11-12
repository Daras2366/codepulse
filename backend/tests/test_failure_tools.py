"""Tests for the Stage 3 failure-pattern agent tools.

Coverage:
- get_failure_patterns: verdict grouping, sorting, empty data
- get_attempts_before_accept: average before first ACCEPTED, never-accepted
- get_stale_topics: inactivity window, clamping, solved-count reporting
- get_contest_postmortem: rating changes, clamping, limitation field
- Cross-user isolation for every new tool
- ToolDispatcher: new tools allowed, model-supplied user_id ignored,
  unknown tools still rejected
- Tool-call cap: loop terminates at _MAX_TOOL_CALLS and still finalises
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registers all ORM models
from app.models.base import Base
from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.enums import Difficulty, Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
from app.models.user import User
from app.services.agent_tools import (
    get_attempts_before_accept,
    get_contest_postmortem,
    get_failure_patterns,
    get_stale_topics,
)
from app.services.recommendation_agent import (
    RecommendationAgent,
    ToolDispatcher,
    _MAX_TOOL_CALLS,
)

# ---------------------------------------------------------------------------
# Test database setup (same in-memory style as test_agent.py)
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

NOW = datetime.now(timezone.utc)


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
def user_a(db):
    user = User(
        username="failure_a",
        email="failure_a@example.com",
        password_hash="hashed",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture(scope="module")
def user_b(db):
    """Second user with minimal data — for isolation and empty-ish cases."""
    user = User(
        username="failure_b",
        email="failure_b@example.com",
        password_hash="hashed",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture(scope="module")
def user_c(db):
    """User with no platform profile or submissions at all."""
    user = User(
        username="failure_c",
        email="failure_c@example.com",
        password_hash="hashed",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture(scope="module")
def profile_a(db, user_a):
    profile = PlatformProfile(
        user_id=user_a.id,
        platform=Platform.CODEFORCES,
        username="cf_failure_a",
        current_rating=1500,
        max_rating=1600,
    )
    db.add(profile)
    db.commit()
    return profile


@pytest.fixture(scope="module")
def profile_b(db, user_b):
    profile = PlatformProfile(
        user_id=user_b.id,
        platform=Platform.CODEFORCES,
        username="cf_failure_b",
        current_rating=1400,
        max_rating=1500,
    )
    db.add(profile)
    db.commit()
    return profile


@pytest.fixture(scope="module")
def topics(db):
    names = ["Graphs", "Dynamic Programming", "Arrays", "Math"]
    objs = [Topic(name=n) for n in names]
    db.add_all(objs)
    db.commit()
    return {t.name: t for t in objs}


@pytest.fixture(scope="module")
def problems(db, topics):
    """One problem per topic (plus a second Graphs problem)."""
    specs = [
        ("cf-fp-g1", "Graph Problem 1", "Graphs"),
        ("cf-fp-g2", "Graph Problem 2", "Graphs"),
        ("cf-fp-dp1", "DP Problem 1", "Dynamic Programming"),
        ("cf-fp-dp2", "DP Problem 2", "Dynamic Programming"),
        ("cf-fp-arr", "Array Problem", "Arrays"),
        ("cf-fp-math", "Math Problem", "Math"),
    ]
    objs = []
    for slug, title, topic_name in specs:
        p = Problem(
            platform=Platform.CODEFORCES,
            platform_problem_id=slug,
            title=title,
            slug=slug,
            problem_url=f"https://codeforces.com/problemset/problem/{slug}",
            difficulty=Difficulty.MEDIUM,
            acceptance_rate=0.4,
        )
        db.add(p)
        objs.append((p, topics[topic_name]))
    db.flush()
    for p, topic in objs:
        db.add(ProblemTopic(problem_id=p.id, topic_id=topic.id))
    db.commit()
    return {slug: p for (p, _), (slug, *_rest) in zip(objs, specs)}


def _sub(profile_id, problem_id, status, when, tag):
    return Submission(
        profile_id=profile_id,
        problem_id=problem_id,
        submitted_at=when,
        language="Python3",
        status=status,
        platform_submission_id=tag,
    )


@pytest.fixture(scope="module")
def seeded_submissions(db, profile_a, profile_b, problems):
    """Distinct failure patterns for user_a; minimal history for user_b."""
    p = problems
    subs = [
        # DP problem 1: two failures then accept → 2 attempts before accept.
        _sub(profile_a.id, p["cf-fp-dp1"].id, SubmissionStatus.WRONG_ANSWER,
             NOW - timedelta(days=3), "a-dp1-wa1"),
        _sub(profile_a.id, p["cf-fp-dp1"].id, SubmissionStatus.COMPILE_ERROR,
             NOW - timedelta(days=3) + timedelta(hours=1), "a-dp1-ce"),
        _sub(profile_a.id, p["cf-fp-dp1"].id, SubmissionStatus.ACCEPTED,
             NOW - timedelta(days=1), "a-dp1-ac"),
        # DP problem 2: never accepted.
        _sub(profile_a.id, p["cf-fp-dp2"].id, SubmissionStatus.WRONG_ANSWER,
             NOW - timedelta(days=2), "a-dp2-wa"),
        _sub(profile_a.id, p["cf-fp-dp2"].id, SubmissionStatus.TIME_LIMIT,
             NOW - timedelta(days=1) + timedelta(hours=2), "a-dp2-tle"),
        # Graphs: TLE + runtime error, never accepted.
        _sub(profile_a.id, p["cf-fp-g1"].id, SubmissionStatus.TIME_LIMIT,
             NOW - timedelta(days=5), "a-g1-tle"),
        _sub(profile_a.id, p["cf-fp-g1"].id, SubmissionStatus.RUNTIME_ERROR,
             NOW - timedelta(days=4), "a-g1-re"),
        _sub(profile_a.id, p["cf-fp-g2"].id, SubmissionStatus.MEMORY_LIMIT,
             NOW - timedelta(days=3), "a-g2-mle"),
        # Arrays: solved once, 40 days ago → stale under default window.
        _sub(profile_a.id, p["cf-fp-arr"].id, SubmissionStatus.ACCEPTED,
             NOW - timedelta(days=40), "a-arr-ac"),
        # Math: solved recently → not stale.
        _sub(profile_a.id, p["cf-fp-math"].id, SubmissionStatus.ACCEPTED,
             NOW - timedelta(days=5), "a-math-ac"),
        # user_b: one clean accept on Math, 2 days ago.
        _sub(profile_b.id, p["cf-fp-math"].id, SubmissionStatus.ACCEPTED,
             NOW - timedelta(days=2), "b-math-ac"),
    ]
    db.add_all(subs)
    db.commit()
    return subs


@pytest.fixture(scope="module")
def contests(db, profile_a, profile_b):
    c_recent = Contest(
        platform_contest_id="ct-recent",
        title="Recent Contest",
        platform=Platform.CODEFORCES,
        contest_url="https://codeforces.com/contest/1",
        start_time=NOW - timedelta(days=10),
        duration_minutes=120,
    )
    c_old = Contest(
        platform_contest_id="ct-old",
        title="Old Contest",
        platform=Platform.CODEFORCES,
        contest_url="https://codeforces.com/contest/2",
        start_time=NOW - timedelta(days=30),
        duration_minutes=120,
    )
    db.add_all([c_recent, c_old])
    db.flush()

    parts = [
        ContestParticipation(
            profile_id=profile_a.id,
            contest_id=c_recent.id,
            rank=100,
            old_rating=1500,
            new_rating=1560,
            rating_change=60,
            solved=3,
            penalty=10,
        ),
        ContestParticipation(
            profile_id=profile_a.id,
            contest_id=c_old.id,
            rank=200,
            old_rating=1400,
            new_rating=1440,
            rating_change=40,
            solved=2,
            penalty=None,
        ),
        ContestParticipation(
            profile_id=profile_b.id,
            contest_id=c_recent.id,
            rank=500,
            old_rating=1400,
            new_rating=1380,
            rating_change=-20,
            solved=1,
            penalty=30,
        ),
    ]
    db.add_all(parts)
    db.commit()
    return {"recent": c_recent, "old": c_old}


# ---------------------------------------------------------------------------
# get_failure_patterns
# ---------------------------------------------------------------------------


class TestGetFailurePatterns:
    def test_normal_case(self, db, user_a, seeded_submissions):
        result = get_failure_patterns(db, user_a.id)
        by_topic = {t["topic"]: t for t in result["topics"]}

        dp = by_topic["Dynamic Programming"]
        assert dp["total_attempts"] == 5
        assert dp["non_accepted"] == 4
        assert dp["failure_rate"] == round(4 / 5, 2)
        assert dp["verdicts"] == {
            "wrong_answer": 2,
            "compile_error": 1,
            "time_limit_exceeded": 1,
        }

        graphs = by_topic["Graphs"]
        assert graphs["non_accepted"] == 3
        assert graphs["verdicts"] == {
            "time_limit_exceeded": 1,
            "runtime_error": 1,
            "memory_limit_exceeded": 1,
        }

        # Sorted by non_accepted desc: DP (4) before Graphs (3).
        assert result["topics"][0]["topic"] == "Dynamic Programming"
        assert result["topics"][1]["topic"] == "Graphs"

    def test_empty_user(self, db, user_c):
        result = get_failure_patterns(db, user_c.id)
        assert result["topics"] == []

    def test_only_accepted_submissions(self, db, user_b, seeded_submissions):
        result = get_failure_patterns(db, user_b.id)
        assert all(t["non_accepted"] == 0 for t in result["topics"])
        assert all(t["verdicts"] == {} for t in result["topics"])


# ---------------------------------------------------------------------------
# get_attempts_before_accept
# ---------------------------------------------------------------------------


class TestGetAttemptsBeforeAccept:
    def test_normal_case(self, db, user_a, seeded_submissions):
        result = get_attempts_before_accept(db, user_a.id)
        by_topic = {t["topic"]: t for t in result["topics"]}

        dp = by_topic["Dynamic Programming"]
        # dp1: WA, CE, then AC → 2 attempts before accept.
        # dp2: never accepted → excluded from average, counted separately.
        assert dp["avg_attempts_before_accept"] == 2.0
        assert dp["problems_measured"] == 1
        assert dp["never_accepted_problems"] == 1

        graphs = by_topic["Graphs"]
        assert graphs["avg_attempts_before_accept"] is None
        assert graphs["problems_measured"] == 0
        assert graphs["never_accepted_problems"] == 2

        arrays = by_topic["Arrays"]
        assert arrays["avg_attempts_before_accept"] == 0.0
        assert arrays["problems_measured"] == 1
        assert arrays["never_accepted_problems"] == 0

    def test_empty_user(self, db, user_c):
        result = get_attempts_before_accept(db, user_c.id)
        assert result["topics"] == []


# ---------------------------------------------------------------------------
# get_stale_topics
# ---------------------------------------------------------------------------


class TestGetStaleTopics:
    def test_normal_case(self, db, user_a, seeded_submissions):
        result = get_stale_topics(db, user_a.id)
        assert result["window_days"] == 30
        assert len(result["topics"]) == 1

        stale = result["topics"][0]
        assert stale["topic"] == "Arrays"
        assert stale["solved_count"] == 1
        assert 35 <= stale["days_since_last_activity"] <= 45

        # Math (5d), DP (1d) are fresh; Graphs was never solved.
        names = {t["topic"] for t in result["topics"]}
        assert "Math" not in names
        assert "Dynamic Programming" not in names
        assert "Graphs" not in names

    def test_clamping(self, db, user_a, seeded_submissions):
        assert get_stale_topics(db, user_a.id, days=1)["window_days"] == 7
        assert get_stale_topics(db, user_a.id, days=5000)["window_days"] == 365
        # With a 365-day window nothing is stale for this user.
        assert get_stale_topics(db, user_a.id, days=365)["topics"] == []

    def test_empty_user(self, db, user_c):
        result = get_stale_topics(db, user_c.id)
        assert result["topics"] == []
        assert result["window_days"] == 30


# ---------------------------------------------------------------------------
# get_contest_postmortem
# ---------------------------------------------------------------------------


class TestGetContestPostmortem:
    def test_normal_case(self, db, user_a, contests):
        result = get_contest_postmortem(db, user_a.id)
        assert "limitation" in result and result["limitation"]
        assert len(result["contests"]) == 2

        # Most recent first.
        first, second = result["contests"]
        assert first["title"] == "Recent Contest"
        assert first["rating_change"] == 60
        assert first["old_rating"] == 1500
        assert first["new_rating"] == 1560
        assert first["solved"] == 3
        assert first["rank"] == 100
        assert first["platform"] == "codeforces"

        assert second["title"] == "Old Contest"
        assert second["rating_change"] == 40

    def test_clamping(self, db, user_a, contests):
        assert len(get_contest_postmortem(db, user_a.id, limit=0)["contests"]) == 1
        # limit=99 clamps to 10; user only has 2 contests.
        assert len(get_contest_postmortem(db, user_a.id, limit=99)["contests"]) == 2

    def test_empty_user(self, db, user_c):
        result = get_contest_postmortem(db, user_c.id)
        assert result["contests"] == []
        assert result["limitation"]


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


class TestCrossUserIsolation:
    """user_b must never see user_a's failure/stale/contest data."""

    def test_failure_patterns_isolation(self, db, user_a, user_b, seeded_submissions):
        a_topics = {t["topic"] for t in get_failure_patterns(db, user_a.id)["topics"]}
        b_topics = {t["topic"] for t in get_failure_patterns(db, user_b.id)["topics"]}
        # user_b only solved Math cleanly — none of user_a's failing topics.
        assert "Graphs" not in b_topics
        assert "Dynamic Programming" not in b_topics
        assert b_topics == {"Math"}

    def test_attempts_isolation(self, db, user_a, user_b, seeded_submissions):
        b_topics = {
            t["topic"]
            for t in get_attempts_before_accept(db, user_b.id)["topics"]
        }
        assert b_topics == {"Math"}

    def test_stale_isolation(self, db, user_a, user_b, seeded_submissions):
        assert get_stale_topics(db, user_b.id)["topics"] == []
        a_names = {t["topic"] for t in get_stale_topics(db, user_a.id)["topics"]}
        assert a_names == {"Arrays"}

    def test_postmortem_isolation(self, db, user_a, user_b, contests):
        b_result = get_contest_postmortem(db, user_b.id)
        assert len(b_result["contests"]) == 1
        assert b_result["contests"][0]["title"] == "Recent Contest"
        assert b_result["contests"][0]["rating_change"] == -20


# ---------------------------------------------------------------------------
# ToolDispatcher — new tools, user_id stripping, unknown rejection
# ---------------------------------------------------------------------------


class TestDispatcherNewTools:
    NEW_TOOLS = [
        "get_failure_patterns",
        "get_attempts_before_accept",
        "get_stale_topics",
        "get_contest_postmortem",
    ]

    def test_new_tools_are_allowed(self, db, user_a, seeded_submissions, contests):
        dispatcher = ToolDispatcher(db, user_a.id)
        for name in self.NEW_TOOLS:
            result = dispatcher.dispatch(name, {})
            assert "error" not in result or "Unknown tool" not in result.get("error", "")

    def test_model_supplied_user_id_ignored(self, db, user_a, user_b, seeded_submissions):
        """Dispatching as user_a with user_id=user_b.id must return user_a's data."""
        dispatcher = ToolDispatcher(db, user_a.id)
        result = dispatcher.dispatch(
            "get_stale_topics", {"user_id": user_b.id, "days": 30}
        )
        names = {t["topic"] for t in result["topics"]}
        assert names == {"Arrays"}  # user_a's stale topic, not user_b's (none)

        result_b = ToolDispatcher(db, user_b.id).dispatch(
            "get_stale_topics", {"user_id": user_a.id}
        )
        assert result_b["topics"] == []

    def test_unknown_tool_still_rejected(self, db, user_a):
        dispatcher = ToolDispatcher(db, user_a.id)
        result = dispatcher.dispatch("drop_all_tables", {})
        assert "Unknown tool" in result["error"]


# ---------------------------------------------------------------------------
# Tool-call cap
# ---------------------------------------------------------------------------


def _make_text_response(text: str) -> MagicMock:
    part = MagicMock()
    part.text = text
    part.function_call = None
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    response = MagicMock()
    response.text = text
    response.candidates = [candidate]
    return response


def _make_multi_function_call_response(n_calls: int, call_prefix: str) -> MagicMock:
    """Mock response whose content has ``n_calls`` function_call parts."""
    parts = []
    for i in range(n_calls):
        fc = MagicMock()
        fc.name = "get_user_performance_profile"
        fc.args = {}
        fc.id = f"{call_prefix}-{i}"
        part = MagicMock()
        part.text = None
        part.function_call = fc
        parts.append(part)
    content = MagicMock()
    content.parts = parts
    candidate = MagicMock()
    candidate.content = content
    response = MagicMock()
    response.text = None
    response.candidates = [candidate]
    return response


class TestToolCallCap:
    def test_loop_terminates_at_cap_and_finalises(self, db, user_a):
        """A model that keeps calling tools must stop at _MAX_TOOL_CALLS
        and still produce a final parsed response."""
        final_json = json.dumps(
            {
                "recommendations": [],
                "reasoning": "Stopped after tool cap.",
                "has_sufficient_data": False,
            }
        )

        # Each turn requests 3 tool calls; 4 turns exceed the cap of 10,
        # then the loop forces one final no-tools generation.
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [
            _make_multi_function_call_response(3, "t1"),
            _make_multi_function_call_response(3, "t2"),
            _make_multi_function_call_response(3, "t3"),
            _make_multi_function_call_response(3, "t4"),
            _make_text_response(final_json),
        ]

        with patch("app.services.recommendation_agent.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "fake-key"
            mock_settings.GEMINI_MODEL = "gemini-3.5-flash"
            mock_settings.GEMINI_TIMEOUT_SECONDS = 30
            with patch("app.services.recommendation_agent.genai.Client") as mock_cls:
                mock_cls.return_value = mock_client
                agent = RecommendationAgent(db, user_a.id)
                result = agent.recommend()

        # Exactly _MAX_TOOL_CALLS were dispatched; the rest got finalize msgs.
        assert len(result.tool_calls_made) == _MAX_TOOL_CALLS
        assert len(agent._dispatcher.tool_results) == _MAX_TOOL_CALLS
        # 4 tool-call turns + 1 forced final generation.
        assert mock_client.models.generate_content.call_count == 5
        # A final response was still produced and parsed. The post-loop
        # path annotates result.error with a warning — parsing succeeded.
        assert result.error is not None and "Warning" in result.error
        assert result.agent_reasoning == "Stopped after tool cap."
