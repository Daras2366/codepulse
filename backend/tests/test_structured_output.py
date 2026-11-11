"""Tests for the structured-output path in RecommendationAgent.

The agent now requests Gemini's JSON response schema
(response_mime_type="application/json" + response_schema) on every turn.
These tests verify:

- the schema config is sent together with the tool declarations
- a schema-conformant final response parses into recommendations
- malformed/non-JSON text still falls back to _parse_final_response
- _verify_recommendations behaviour is unchanged
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registers all ORM models
from app.models.base import Base
from app.models.enums import Difficulty, Platform
from app.models.problem import Problem
from app.models.user import User
from app.services.recommendation_agent import RecommendationAgent


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def user(db):
    u = User(username="suser", email="s@example.com", password_hash="x")
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def unsolved_problem(db):
    p = Problem(
        platform=Platform.LEETCODE,
        platform_problem_id="two-sum",
        title="Two Sum",
        slug="two-sum",
        problem_url="https://leetcode.com/problems/two-sum/",
        difficulty=Difficulty.EASY,
        acceptance_rate=0.5,
    )
    db.add(p)
    db.commit()
    return p


def _text_response(text: str) -> MagicMock:
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


def _function_call_response(name: str, args: dict) -> MagicMock:
    fc = MagicMock()
    fc.name = name
    fc.args = args
    fc.id = "call-1"
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


def _make_agent(db, user_id, mock_client):
    with patch("app.services.recommendation_agent.settings") as mock_settings:
        mock_settings.GEMINI_API_KEY = "fake-key"
        mock_settings.GEMINI_MODEL = "gemini-3.5-flash"
        mock_settings.GEMINI_TIMEOUT_SECONDS = 30
        with patch("app.services.recommendation_agent.genai.Client") as mock_cls:
            mock_cls.return_value = mock_client
            return RecommendationAgent(db, user_id)


_SCHEMA_RESPONSE = {
    "recommendations": [
        {
            "problem_id": None,  # filled per-test
            "title": "Two Sum",
            "platform": "leetcode",
            "difficulty": "Easy",
            "url": "https://leetcode.com/problems/two-sum/",
            "topics": ["Arrays"],
            "reason": "Classic starter problem.",
            "priority": 1,
            "likely_unsolved": True,
        }
    ],
    "reasoning": "User is a beginner.",
    "has_sufficient_data": True,
    "catalog_limited": False,
}


class TestStructuredOutputConfig:
    def test_schema_sent_with_tools_on_every_call(self, db, user):
        """generate_content must receive tools AND the JSON schema together."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = [
            _function_call_response("get_user_goals", {}),
            _text_response(json.dumps({"recommendations": [], "reasoning": "", "has_sufficient_data": False})),
        ]
        agent = _make_agent(db, user.id, mock_client)
        agent.recommend()

        assert mock_client.models.generate_content.call_count == 2
        for call in mock_client.models.generate_content.call_args_list:
            config = call.kwargs["config"]
            # Tools still declared (function calling preserved)…
            assert config.tools, "tool declarations must remain on the config"
            # …and structured output is requested.
            assert config.response_mime_type == "application/json"
            assert config.response_schema is not None
            assert "recommendations" in config.response_schema["properties"]

    def test_schema_shape_matches_parser_fields(self):
        from app.services.recommendation_agent import _FINAL_RESPONSE_SCHEMA

        props = _FINAL_RESPONSE_SCHEMA["properties"]
        assert set(props) >= {"recommendations", "reasoning", "has_sufficient_data"}
        rec_props = props["recommendations"]["items"]["properties"]
        for field in (
            "problem_id", "title", "platform", "difficulty",
            "url", "topics", "reason", "priority", "likely_unsolved",
        ):
            assert field in rec_props


class TestStructuredOutputParsing:
    def test_schema_conformant_response_parses(self, db, user, unsolved_problem):
        payload = dict(_SCHEMA_RESPONSE)
        payload["recommendations"] = [
            dict(_SCHEMA_RESPONSE["recommendations"][0], problem_id=unsolved_problem.id)
        ]
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _text_response(
            json.dumps(payload)
        )
        agent = _make_agent(db, user.id, mock_client)
        result = agent.recommend()

        assert result.error is None
        assert len(result.recommendations) == 1
        rec = result.recommendations[0]
        assert rec.problem_id == unsolved_problem.id
        # _verify_recommendations still overwrites with DB truth.
        assert rec.title == "Two Sum"
        assert rec.url == unsolved_problem.problem_url

    def test_embedded_json_falls_back_to_parser(self, db, user):
        """Non-schema text containing JSON still parses via the fallback."""
        payload = {
            "recommendations": [],
            "reasoning": "fallback path",
            "has_sufficient_data": False,
        }
        text = "Here is my analysis.\n" + json.dumps(payload) + "\nDone."
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _text_response(text)
        agent = _make_agent(db, user.id, mock_client)
        result = agent.recommend()

        assert result.error is None
        assert result.has_sufficient_data is False
        assert result.agent_reasoning == "fallback path"

    def test_fenced_json_falls_back_to_parser(self, db, user):
        payload = {
            "recommendations": [],
            "reasoning": "fenced",
            "has_sufficient_data": False,
        }
        text = "```json\n" + json.dumps(payload) + "\n```"
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _text_response(text)
        agent = _make_agent(db, user.id, mock_client)
        result = agent.recommend()
        assert result.error is None
        assert result.agent_reasoning == "fenced"

    def test_non_json_response_sets_error(self, db, user):
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _text_response(
            "I cannot help with that."
        )
        agent = _make_agent(db, user.id, mock_client)
        result = agent.recommend()
        assert result.error is not None
        assert len(result.recommendations) == 0
