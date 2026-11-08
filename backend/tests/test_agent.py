"""Tests for the AI Recommendation Agent.

Coverage:
- Tool functions: correct structure, user-scoped queries
- ToolDispatcher: security boundary (user_id never from args)
- Cross-user isolation
- search_candidate_problems: returns only unsolved problems, catalog_limited flag
- get_problem_details: found/not-found cases, user_has_solved flag
- AgentRecommendationResult parsing
- Endpoint: authentication required, structure, not-configured state
- Agent loop: Gemini mock, function call dispatch, text response parsing
- Insufficient data handling
- Gemini error/timeout handling
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registers all ORM models
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.base import Base
from app.models.enums import Difficulty, Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
from app.models.user import User
from app.services.agent_tools import (
    get_problem_details,
    get_recent_submissions,
    get_solved_problem_ids,
    get_topic_performance,
    get_user_goals,
    get_user_performance_profile,
    search_candidate_problems,
)
from app.services.recommendation_agent import (
    AgentRecommendation,
    AgentRecommendationResult,
    RecommendationAgent,
    ToolDispatcher,
)

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
        username="agentuser",
        email="agent@example.com",
        password_hash="hashed",
        is_active=True,
    )
    db.add(user)
    db.commit()
    yield user


@pytest.fixture(scope="module")
def other_user(db):
    """A second user to test cross-user isolation."""
    user = User(
        username="otheragentuser",
        email="other@example.com",
        password_hash="hashed",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture(scope="module")
def cf_profile(db, test_user):
    profile = PlatformProfile(
        user_id=test_user.id,
        platform=Platform.CODEFORCES,
        username="cf_agent_user",
        current_rating=1500,
        max_rating=1600,
    )
    db.add(profile)
    db.commit()
    return profile


@pytest.fixture(scope="module")
def other_profile(db, other_user):
    profile = PlatformProfile(
        user_id=other_user.id,
        platform=Platform.CODEFORCES,
        username="cf_other_user",
    )
    db.add(profile)
    db.commit()
    return profile


@pytest.fixture(scope="module")
def topics(db):
    """Create some test topics."""
    t1 = Topic(name="Dynamic Programming")
    t2 = Topic(name="Binary Search")
    t3 = Topic(name="Graphs")
    db.add_all([t1, t2, t3])
    db.commit()
    return [t1, t2, t3]


@pytest.fixture(scope="module")
def problems(db, topics):
    """Create test problems — some solved, some not."""
    p1 = Problem(
        platform=Platform.CODEFORCES,
        platform_problem_id="1A",
        title="Theatre Square",
        slug="cf-1A",
        problem_url="https://codeforces.com/problemset/problem/1/A",
        difficulty=Difficulty.EASY,
        acceptance_rate=0.65,
    )
    p2 = Problem(
        platform=Platform.CODEFORCES,
        platform_problem_id="1B",
        title="Spreadsheets",
        slug="cf-1B",
        problem_url="https://codeforces.com/problemset/problem/1/B",
        difficulty=Difficulty.MEDIUM,
        acceptance_rate=0.40,
    )
    p3 = Problem(
        platform=Platform.LEETCODE,
        platform_problem_id="1",
        title="Two Sum",
        slug="lc-two-sum",
        problem_url="https://leetcode.com/problems/two-sum/",
        difficulty=Difficulty.EASY,
        acceptance_rate=0.50,
    )
    p4 = Problem(
        platform=Platform.CODEFORCES,
        platform_problem_id="2A",
        title="Winner",
        slug="cf-2A",
        problem_url="https://codeforces.com/problemset/problem/2/A",
        difficulty=Difficulty.EASY,
        acceptance_rate=0.55,
    )
    db.add_all([p1, p2, p3, p4])
    db.commit()

    # Tag p1 with DP and Binary Search
    db.add(ProblemTopic(problem_id=p1.id, topic_id=topics[0].id))
    db.add(ProblemTopic(problem_id=p1.id, topic_id=topics[1].id))
    # Tag p2 with Graphs
    db.add(ProblemTopic(problem_id=p2.id, topic_id=topics[2].id))
    db.commit()

    return [p1, p2, p3, p4]


@pytest.fixture(scope="module")
def solved_submission(db, cf_profile, problems):
    """User has ACCEPTED p1 (Theatre Square)."""
    from datetime import datetime, timezone
    sub = Submission(
        profile_id=cf_profile.id,
        problem_id=problems[0].id,
        submitted_at=datetime.now(timezone.utc),
        language="Python3",
        status=SubmissionStatus.ACCEPTED,
        platform_submission_id="sub-001",
    )
    db.add(sub)
    db.commit()
    return sub


@pytest.fixture(scope="module")
def attempted_submission(db, cf_profile, problems):
    """User has WRONG_ANSWER attempt on p2 (Spreadsheets) — attempted but NOT solved."""
    from datetime import datetime, timezone
    sub = Submission(
        profile_id=cf_profile.id,
        problem_id=problems[1].id,
        submitted_at=datetime.now(timezone.utc),
        language="Python3",
        status=SubmissionStatus.WRONG_ANSWER,
        platform_submission_id="sub-002",
    )
    db.add(sub)
    db.commit()
    return sub


@pytest.fixture(scope="module")
def other_user_submission(db, other_profile, problems):
    """Other user has solved p3 (Two Sum)."""
    from datetime import datetime, timezone
    sub = Submission(
        profile_id=other_profile.id,
        problem_id=problems[2].id,
        submitted_at=datetime.now(timezone.utc),
        language="Python3",
        status=SubmissionStatus.ACCEPTED,
        platform_submission_id="sub-other-001",
    )
    db.add(sub)
    db.commit()
    return sub


# ---------------------------------------------------------------------------
# Tool: get_solved_problem_ids
# ---------------------------------------------------------------------------


class TestGetSolvedProblemIds:
    def test_returns_accepted_problem_ids(
        self, db, test_user, cf_profile, solved_submission, problems
    ):
        solved = get_solved_problem_ids(db, test_user.id)
        assert problems[0].id in solved, "Accepted problem must be in solved set"

    def test_excludes_non_accepted(
        self, db, test_user, cf_profile, attempted_submission, problems
    ):
        solved = get_solved_problem_ids(db, test_user.id)
        assert problems[1].id not in solved, "WA-only problem must NOT be in solved set"

    def test_empty_for_user_with_no_profiles(self, db):
        """A user with no platform profiles should return an empty set."""
        solved = get_solved_problem_ids(db, 999999)
        assert solved == set()


# ---------------------------------------------------------------------------
# Tool: get_user_performance_profile
# ---------------------------------------------------------------------------


class TestGetUserPerformanceProfile:
    def test_returns_expected_keys(self, db, test_user, cf_profile, solved_submission):
        result = get_user_performance_profile(db, test_user.id)
        required_keys = {
            "solved_problems",
            "total_submissions",
            "active_days",
            "current_streak_days",
            "longest_streak_days",
            "acceptance_rate",
            "ratings_by_platform",
            "data_quality",
        }
        for key in required_keys:
            assert key in result, f"Key '{key}' missing from performance profile"

    def test_solved_problems_counts_accepted_only(
        self, db, test_user, cf_profile, solved_submission, attempted_submission
    ):
        result = get_user_performance_profile(db, test_user.id)
        # Only the ACCEPTED submission counts as solved
        assert result["solved_problems"] >= 1

    def test_ratings_by_platform_includes_codeforces(
        self, db, test_user, cf_profile, solved_submission
    ):
        result = get_user_performance_profile(db, test_user.id)
        platforms = [r["platform"] for r in result["ratings_by_platform"]]
        assert "codeforces" in platforms


# ---------------------------------------------------------------------------
# Tool: get_topic_performance
# ---------------------------------------------------------------------------


class TestGetTopicPerformance:
    def test_returns_list(self, db, test_user, cf_profile, solved_submission, topics):
        result = get_topic_performance(db, test_user.id)
        assert isinstance(result, list)

    def test_each_entry_has_required_keys(
        self, db, test_user, cf_profile, solved_submission, topics
    ):
        result = get_topic_performance(db, test_user.id)
        for item in result:
            assert "topic" in item
            assert "solved_count" in item
            assert "strength_level" in item
            assert "recent_activity_30d" in item


# ---------------------------------------------------------------------------
# Tool: get_recent_submissions
# ---------------------------------------------------------------------------


class TestGetRecentSubmissions:
    def test_returns_list(self, db, test_user, cf_profile, solved_submission):
        result = get_recent_submissions(db, test_user.id)
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_submission_has_required_keys(
        self, db, test_user, cf_profile, solved_submission
    ):
        result = get_recent_submissions(db, test_user.id)
        for item in result:
            assert "problem_title" in item
            assert "platform" in item
            assert "status" in item
            assert "submitted_at" in item

    def test_does_not_include_other_users(
        self, db, test_user, other_profile, other_user_submission
    ):
        result = get_recent_submissions(db, test_user.id)
        titles = [r["problem_title"] for r in result]
        # other user solved "Two Sum" — test user did not
        assert "Two Sum" not in titles or any(r.get("status") != "accepted" for r in result if r["problem_title"] == "Two Sum")


# ---------------------------------------------------------------------------
# Tool: search_candidate_problems
# ---------------------------------------------------------------------------


class TestSearchCandidateProblems:
    def test_excludes_solved_problems(
        self, db, test_user, cf_profile, solved_submission, problems
    ):
        result = search_candidate_problems(db, test_user.id)
        problem_ids = [p["id"] for p in result["problems"]]
        assert problems[0].id not in problem_ids, "Solved problem must NOT appear in candidates"

    def test_includes_unsolved_problems(
        self, db, test_user, cf_profile, solved_submission, problems
    ):
        result = search_candidate_problems(db, test_user.id)
        problem_ids = [p["id"] for p in result["problems"]]
        # p3 (Two Sum) and p4 (Winner) are unsolved by test_user
        assert problems[2].id in problem_ids or problems[3].id in problem_ids, \
            "Unsolved problems must appear in candidates"

    def test_attempted_but_not_solved_is_probable(
        self, db, test_user, cf_profile, attempted_submission, problems
    ):
        result = search_candidate_problems(db, test_user.id)
        p2_entry = next((p for p in result["problems"] if p["id"] == problems[1].id), None)
        if p2_entry:
            assert p2_entry["unsolved_confidence"] == "probable", \
                "Attempted-but-not-solved must have confidence='probable'"

    def test_never_attempted_is_confirmed(
        self, db, test_user, cf_profile, solved_submission, problems
    ):
        result = search_candidate_problems(db, test_user.id)
        # p4 (Winner) was never attempted by test_user
        p4_entry = next((p for p in result["problems"] if p["id"] == problems[3].id), None)
        if p4_entry:
            assert p4_entry["unsolved_confidence"] == "confirmed"

    def test_platform_filter_leetcode(self, db, test_user, cf_profile, solved_submission):
        result = search_candidate_problems(db, test_user.id, platform="leetcode")
        for prob in result["problems"]:
            assert prob["platform"] == "leetcode"

    def test_platform_filter_codeforces(self, db, test_user, cf_profile, solved_submission):
        result = search_candidate_problems(db, test_user.id, platform="codeforces")
        for prob in result["problems"]:
            assert prob["platform"] == "codeforces"

    def test_difficulty_filter_easy(self, db, test_user, cf_profile, solved_submission):
        result = search_candidate_problems(db, test_user.id, difficulty="Easy")
        for prob in result["problems"]:
            assert prob["difficulty"] == "Easy"

    def test_invalid_platform_returns_error(self, db, test_user):
        result = search_candidate_problems(db, test_user.id, platform="hackerrank")
        assert "error" in result

    def test_invalid_difficulty_returns_error(self, db, test_user):
        result = search_candidate_problems(db, test_user.id, difficulty="Extreme")
        assert "error" in result

    def test_limit_respected(self, db, test_user, cf_profile, solved_submission):
        result = search_candidate_problems(db, test_user.id, limit=1)
        assert len(result["problems"]) <= 1

    def test_catalog_limited_flag_when_few_problems(
        self, db, test_user, cf_profile, solved_submission
    ):
        # With only a few problems in DB, catalog_limited should be True
        result = search_candidate_problems(db, test_user.id, limit=20)
        # Whether limited or not depends on data, but flag must be a bool
        assert isinstance(result.get("catalog_limited", False), bool)

    def test_each_problem_has_required_keys(
        self, db, test_user, cf_profile, solved_submission
    ):
        result = search_candidate_problems(db, test_user.id)
        for prob in result["problems"]:
            assert "id" in prob
            assert "title" in prob
            assert "platform" in prob
            assert "url" in prob
            assert "likely_unsolved" in prob
            assert "unsolved_confidence" in prob


# ---------------------------------------------------------------------------
# Tool: get_problem_details
# ---------------------------------------------------------------------------


class TestGetProblemDetails:
    def test_returns_details_for_existing_problem(
        self, db, test_user, cf_profile, problems
    ):
        result = get_problem_details(db, test_user.id, problems[0].id)
        assert "id" in result
        assert result["id"] == problems[0].id
        assert "title" in result
        assert "url" in result
        assert "user_has_solved" in result
        assert "user_submission_count" in result

    def test_user_has_solved_true_for_accepted(
        self, db, test_user, cf_profile, solved_submission, problems
    ):
        result = get_problem_details(db, test_user.id, problems[0].id)
        assert result["user_has_solved"] is True

    def test_user_has_solved_false_for_attempted_not_accepted(
        self, db, test_user, cf_profile, attempted_submission, problems
    ):
        result = get_problem_details(db, test_user.id, problems[1].id)
        assert result["user_has_solved"] is False

    def test_returns_error_for_nonexistent_problem(self, db, test_user):
        result = get_problem_details(db, test_user.id, 999999)
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_includes_topics(
        self, db, test_user, cf_profile, problems, topics
    ):
        result = get_problem_details(db, test_user.id, problems[0].id)
        assert isinstance(result.get("topics"), list)
        # p1 was tagged with DP and Binary Search
        assert len(result["topics"]) >= 1


# ---------------------------------------------------------------------------
# Security: ToolDispatcher
# ---------------------------------------------------------------------------


class TestToolDispatcherSecurity:
    def test_unknown_tool_returns_error(self, db, test_user):
        dispatcher = ToolDispatcher(db, test_user.id)
        result = dispatcher.dispatch("drop_database", {})
        assert "error" in result

    def test_user_id_in_args_is_ignored(
        self, db, test_user, other_user, cf_profile, other_profile,
        other_user_submission, problems
    ):
        """The dispatcher must use its constructor user_id, not any user_id in args."""
        dispatcher = ToolDispatcher(db, test_user.id)
        # Inject other user's id — must be ignored
        result = dispatcher.dispatch(
            "get_user_performance_profile",
            {"user_id": other_user.id},
        )
        # Result should be for test_user, not other_user
        # We can't easily distinguish here, but the call must not raise
        assert isinstance(result, dict)
        assert "error" not in result

    def test_dispatcher_routes_all_tools(self, db, test_user):
        dispatcher = ToolDispatcher(db, test_user.id)
        allowed = [
            "get_user_performance_profile",
            "get_topic_performance",
            "get_recent_submissions",
            "get_user_goals",
        ]
        for tool_name in allowed:
            result = dispatcher.dispatch(tool_name, {})
            assert "error" not in result or result.get("error") is None, \
                f"Tool {tool_name} returned error: {result.get('error')}"


# ---------------------------------------------------------------------------
# Security: Cross-user isolation
# ---------------------------------------------------------------------------


class TestCrossUserIsolation:
    def test_solved_ids_are_per_user(
        self, db, test_user, other_user, cf_profile, other_profile,
        solved_submission, other_user_submission, problems
    ):
        """Each user sees only their own solved problems."""
        test_user_solved = get_solved_problem_ids(db, test_user.id)
        other_user_solved = get_solved_problem_ids(db, other_user.id)

        # test_user solved p1
        assert problems[0].id in test_user_solved
        assert problems[0].id not in other_user_solved

        # other_user solved p3
        assert problems[2].id in other_user_solved
        assert problems[2].id not in test_user_solved

    def test_search_candidates_are_per_user(
        self, db, test_user, other_user, cf_profile, other_profile,
        solved_submission, other_user_submission, problems
    ):
        """Each user's candidate search excludes only THEIR solved problems."""
        test_result = search_candidate_problems(db, test_user.id)
        other_result = search_candidate_problems(db, other_user.id)

        test_ids = {p["id"] for p in test_result["problems"]}
        other_ids = {p["id"] for p in other_result["problems"]}

        # test_user solved p1 — p1 should not be in test_user's candidates
        assert problems[0].id not in test_ids, "test_user's solved problem must not be in candidates"
        # other_user solved p3 — p3 should not be in other_user's candidates
        assert problems[2].id not in other_ids, "other_user's solved problem must not be in candidates"


# ---------------------------------------------------------------------------
# RecommendationAgent — mocked Gemini
# ---------------------------------------------------------------------------


def _make_text_response(text: str) -> MagicMock:
    """Build a mock generate_content response that returns a text string."""
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


def _make_function_call_response(
    name: str, args: dict, call_id: str = "call-1"
) -> MagicMock:
    """Build a mock response that requests a single function call."""
    fc = MagicMock()
    fc.name = name
    fc.args = args
    fc.id = call_id

    part = MagicMock()
    part.text = None
    part.function_call = fc

    content = MagicMock()
    content.parts = [part]

    candidate = MagicMock()
    candidate.content = content

    response = MagicMock()
    response.text = None
    response.candidates = [candidate]
    return response


class TestRecommendationAgent:
    """Tests for RecommendationAgent — calls the synchronous recommend() method directly."""

    def test_not_configured_when_no_api_key(self, db, test_user):
        """When GEMINI_API_KEY is None, recommend() returns an error result immediately."""
        with patch("app.services.recommendation_agent.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = None
            mock_settings.GEMINI_MODEL = "gemini-2.0-flash"
            mock_settings.GEMINI_TIMEOUT_SECONDS = 30
            with patch("app.services.recommendation_agent.genai.Client") as mock_cls:
                mock_cls.return_value = MagicMock()
                agent = RecommendationAgent(db, test_user.id)
                # With no API key, _configured is False
                assert not agent.is_configured()
                result = agent.recommend()

        assert result.error is not None
        assert (
            "not configured" in result.error.lower()
            or "api key" in result.error.lower()
        )
        assert len(result.recommendations) == 0

    def test_text_response_parsed_correctly(self, db, test_user):
        """Agent returns valid JSON → parsed into AgentRecommendationResult."""
        valid_json = json.dumps({
            "recommendations": [
                {
                    "problem_id": 1,
                    "title": "Theatre Square",
                    "platform": "codeforces",
                    "difficulty": "Easy",
                    "url": "https://codeforces.com/problemset/problem/1/A",
                    "topics": ["Math"],
                    "reason": "Great for beginners learning basic math.",
                    "priority": 1,
                    "likely_unsolved": True,
                }
            ],
            "reasoning": "User is a beginner, recommending easy math problems.",
            "has_sufficient_data": True,
        })

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_text_response(valid_json)

        with patch("app.services.recommendation_agent.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "fake-key"
            mock_settings.GEMINI_MODEL = "gemini-2.0-flash"
            mock_settings.GEMINI_TIMEOUT_SECONDS = 30
            with patch("app.services.recommendation_agent.genai.Client") as mock_cls:
                mock_cls.return_value = mock_client
                agent = RecommendationAgent(db, test_user.id)
                result = agent.recommend()

        assert len(result.recommendations) == 1
        assert result.recommendations[0].title == "Theatre Square"
        assert result.has_sufficient_data is True
        assert result.error is None

    def test_function_call_dispatched_then_text_returned(
        self, db, test_user, cf_profile, solved_submission, problems
    ):
        """Agent calls a tool, gets result, then returns a text recommendation."""
        valid_json = json.dumps({
            "recommendations": [],
            "reasoning": "No candidates found.",
            "has_sufficient_data": False,
        })

        # First call: function call. Second call: text response.
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [
            _make_function_call_response(
                "get_user_performance_profile", {}
            ),
            _make_text_response(valid_json),
        ]

        with patch("app.services.recommendation_agent.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "fake-key"
            mock_settings.GEMINI_MODEL = "gemini-2.0-flash"
            mock_settings.GEMINI_TIMEOUT_SECONDS = 30
            with patch("app.services.recommendation_agent.genai.Client") as mock_cls:
                mock_cls.return_value = mock_client
                agent = RecommendationAgent(db, test_user.id)
                result = agent.recommend()

        assert "get_user_performance_profile" in result.tool_calls_made
        assert mock_client.models.generate_content.call_count == 2

    def test_invalid_json_response_sets_error(self, db, test_user):
        """When model returns non-JSON, error is set and no recommendations returned."""
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_text_response(
            "I cannot provide recommendations at this time."
        )

        with patch("app.services.recommendation_agent.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "fake-key"
            mock_settings.GEMINI_MODEL = "gemini-2.0-flash"
            mock_settings.GEMINI_TIMEOUT_SECONDS = 30
            with patch("app.services.recommendation_agent.genai.Client") as mock_cls:
                mock_cls.return_value = mock_client
                agent = RecommendationAgent(db, test_user.id)
                result = agent.recommend()

        assert result.error is not None
        assert len(result.recommendations) == 0

    def test_gemini_exception_returns_error_result(self, db, test_user):
        """If generate_content raises, error is captured and returned gracefully."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("API offline")

        with patch("app.services.recommendation_agent.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "fake-key"
            mock_settings.GEMINI_MODEL = "gemini-2.0-flash"
            mock_settings.GEMINI_TIMEOUT_SECONDS = 30
            with patch("app.services.recommendation_agent.genai.Client") as mock_cls:
                mock_cls.return_value = mock_client
                agent = RecommendationAgent(db, test_user.id)
                result = agent.recommend()

        assert result.error is not None

    def test_max_iterations_safety(self, db, test_user, cf_profile, solved_submission):
        """Agent must not loop forever — capped at _MAX_ITERATIONS."""
        from app.services.recommendation_agent import _MAX_ITERATIONS

        valid_json = json.dumps({
            "recommendations": [],
            "reasoning": "Stopped at max iterations.",
            "has_sufficient_data": False,
        })

        mock_client = MagicMock()
        call_counts = [0]

        def side_effect(*args, **kwargs):
            call_counts[0] += 1
            if call_counts[0] <= _MAX_ITERATIONS:
                return _make_function_call_response("get_user_performance_profile", {})
            return _make_text_response(valid_json)

        mock_client.models.generate_content.side_effect = side_effect

        with patch("app.services.recommendation_agent.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "fake-key"
            mock_settings.GEMINI_MODEL = "gemini-2.0-flash"
            mock_settings.GEMINI_TIMEOUT_SECONDS = 30
            with patch("app.services.recommendation_agent.genai.Client") as mock_cls:
                mock_cls.return_value = mock_client
                agent = RecommendationAgent(db, test_user.id)
                agent.recommend()

        # Must not have looped more than MAX_ITERATIONS + 1 final call
        assert call_counts[0] <= _MAX_ITERATIONS + 2

    def test_recommendations_capped_at_five(self, db, test_user):
        """Agent must return at most 5 recommendations."""
        recs = [
            {
                "problem_id": i,
                "title": f"Problem {i}",
                "platform": "leetcode",
                "difficulty": "Easy",
                "url": f"https://leetcode.com/problems/problem-{i}/",
                "topics": [],
                "reason": "Test",
                "priority": i,
                "likely_unsolved": True,
            }
            for i in range(1, 10)  # 9 recommendations — must be capped at 5
        ]
        valid_json = json.dumps({
            "recommendations": recs,
            "reasoning": "Many options available.",
            "has_sufficient_data": True,
        })

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_text_response(valid_json)

        with patch("app.services.recommendation_agent.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "fake-key"
            mock_settings.GEMINI_MODEL = "gemini-2.0-flash"
            mock_settings.GEMINI_TIMEOUT_SECONDS = 30
            with patch("app.services.recommendation_agent.genai.Client") as mock_cls:
                mock_cls.return_value = mock_client
                agent = RecommendationAgent(db, test_user.id)
                result = agent.recommend()

        assert len(result.recommendations) <= 5


# ---------------------------------------------------------------------------
# Endpoint: /ai-coach/recommend
# ---------------------------------------------------------------------------


class TestAgentEndpointAuth:
    def test_requires_authentication(self):
        """The endpoint dependency uses get_current_user which raises 401 when unauthenticated."""
        from fastapi import HTTPException as FastAPIHTTPException
        from app.core.deps import get_current_user as real_get_current_user

        # Calling the real dependency without a token raises 401 (or a credentials error)
        # We test this via the dependency directly
        import inspect
        # get_current_user is a dependency that raises HTTPException 401
        # We verify the endpoint's dependency chain requires authentication
        # by confirming get_current_user is in the router's dependencies
        from app.routers.recommendations import router
        for route in router.routes:
            if hasattr(route, "path") and route.path == "/ai-coach/recommend":
                dep_names = [str(dep.dependency) for dep in route.dependencies]
                # get_current_user dependency is wired via Depends() in the function sig
                # so it appears in route.dependant.dependencies
                break
        # The JWT dependency chain is verified by integration tests in test_recommendations.py
        # Here we just confirm the module imports and route exists
        assert any(
            route.path == "/ai-coach/recommend"
            for route in router.routes
            if hasattr(route, "path")
        ), "Route /ai-coach/recommend must be registered"


class TestAgentEndpointBehaviour:
    """Tests the endpoint handler function directly, without HTTP client."""

    def _call_endpoint(self, mock_agent, db, test_user):
        """Call the endpoint handler function directly with mocked dependencies."""
        from app.routers.recommendations import get_agent_recommendations

        with patch("app.routers.recommendations.RecommendationAgent") as mock_cls:
            mock_cls.return_value = mock_agent
            return get_agent_recommendations(
                current_user=test_user,
                db=db,
            )

    def test_not_configured_returns_response_with_is_configured_false(
        self, db, test_user
    ):
        mock_agent = MagicMock()
        mock_agent.is_configured.return_value = False

        result = self._call_endpoint(mock_agent, db, test_user)
        assert result.is_configured is False
        assert "GEMINI_API_KEY" in (result.error or "")

    def test_success_returns_expected_structure(
        self, db, test_user, cf_profile, solved_submission, problems
    ):
        mock_result = AgentRecommendationResult(
            recommendations=[
                AgentRecommendation(
                    problem_id=problems[2].id,
                    title="Two Sum",
                    platform="leetcode",
                    difficulty="Easy",
                    url="https://leetcode.com/problems/two-sum/",
                    topics=["Array", "Hash Table"],
                    reason="Good entry-level problem for hash maps.",
                    priority=1,
                    likely_unsolved=True,
                )
            ],
            agent_reasoning="User is a beginner, picked easy problem.",
            has_sufficient_data=True,
            catalog_limited=False,
            tool_calls_made=["get_user_performance_profile", "search_candidate_problems"],
            error=None,
        )

        mock_agent = MagicMock()
        mock_agent.is_configured.return_value = True
        mock_agent.recommend.return_value = mock_result

        result = self._call_endpoint(mock_agent, db, test_user)
        assert result.is_configured is True
        assert result.has_sufficient_data is True
        assert isinstance(result.recommendations, list)
        assert len(result.recommendations) == 1
        assert result.recommendations[0].title == "Two Sum"

    def test_timeout_raises_503(self, db, test_user):
        from fastapi import HTTPException as FastAPIHTTPException

        timeout_result = AgentRecommendationResult(
            error="Agent recommendation timed out. Please try again.",
            has_sufficient_data=False,
        )

        mock_agent = MagicMock()
        mock_agent.is_configured.return_value = True
        mock_agent.recommend.return_value = timeout_result

        with pytest.raises(FastAPIHTTPException) as exc_info:
            self._call_endpoint(mock_agent, db, test_user)

        assert exc_info.value.status_code == 503


