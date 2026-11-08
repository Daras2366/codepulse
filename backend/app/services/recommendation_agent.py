"""AI Recommendation Agent using Gemini function calling.

Uses client.models.generate_content with manual tool dispatch (not automatic).
This gives us full control over tool execution and argument validation.

Security contract:
  - user_id is ALWAYS taken from the ToolDispatcher constructor (set at request time
    from the authenticated session). It is NEVER accepted from model tool call arguments.
  - The ToolDispatcher validates all tool names before dispatching.
  - All tool functions enforce their own user_id-scoped DB queries.
"""

from __future__ import annotations

import json
import logging
import signal
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from google import genai
from google.genai import types

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.agent_tools import (
    get_user_performance_profile,
    get_topic_performance,
    get_recent_submissions,
    get_user_goals,
    search_candidate_problems,
    get_problem_details,
)
from app.services.gemini_service import GeminiNotConfiguredError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Return types
# ---------------------------------------------------------------------------


@dataclass
class AgentRecommendation:
    """A single problem recommendation from the AI agent."""

    problem_id: Optional[int]  # DB primary key; None if catalog limited
    title: str
    platform: str
    difficulty: Optional[str]
    url: str
    topics: list[str]
    reason: str
    priority: int  # 1 = highest priority
    likely_unsolved: bool


@dataclass
class AgentRecommendationResult:
    """Full result of one agent recommendation run."""

    recommendations: list[AgentRecommendation] = field(default_factory=list)
    agent_reasoning: str = ""
    has_sufficient_data: bool = False
    catalog_limited: bool = False
    tool_calls_made: list[str] = field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

_ALLOWED_TOOLS = {
    "get_user_performance_profile",
    "get_topic_performance",
    "get_recent_submissions",
    "get_user_goals",
    "search_candidate_problems",
    "get_problem_details",
}


class ToolDispatcher:
    """Dispatches agent tool calls to Python functions.

    Security: user_id is set at construction time from the authenticated session.
    It is NEVER accepted from model-supplied tool call arguments.
    """

    def __init__(self, db: Session, user_id: int) -> None:
        """Initialise the dispatcher.

        Args:
            db: SQLAlchemy session.
            user_id: Authenticated user's ID. Must come from the HTTP session,
                     never from model output.
        """
        self._db = db
        self._user_id = user_id  # immutable after construction

    def dispatch(self, tool_name: str, tool_args: dict) -> dict:
        """Dispatch a tool call and return the result as a dict.

        Args:
            tool_name: Name of the tool to call.
            tool_args: Arguments from the model (user_id is NEVER accepted here).

        Returns:
            Result dict from the tool function.

        Raises:
            ValueError: If the tool_name is not in the allowed set.
        """
        if tool_name not in _ALLOWED_TOOLS:
            return {"error": f"Unknown tool: {tool_name}"}

        # Strip any user_id or db that the model might try to inject (security)
        clean_args = {
            k: v for k, v in tool_args.items()
            if k not in ("user_id", "db", "user", "session")
        }

        try:
            if tool_name == "get_user_performance_profile":
                return get_user_performance_profile(self._db, self._user_id)

            elif tool_name == "get_topic_performance":
                return {"topics": get_topic_performance(self._db, self._user_id)}

            elif tool_name == "get_recent_submissions":
                limit = int(clean_args.get("limit", 20))
                return {
                    "submissions": get_recent_submissions(
                        self._db, self._user_id, limit=limit
                    )
                }

            elif tool_name == "get_user_goals":
                return {"goals": get_user_goals(self._db, self._user_id)}

            elif tool_name == "search_candidate_problems":
                return search_candidate_problems(
                    self._db,
                    self._user_id,
                    topic=clean_args.get("topic"),
                    difficulty=clean_args.get("difficulty"),
                    platform=clean_args.get("platform"),
                    limit=int(clean_args.get("limit", 10)),
                )

            elif tool_name == "get_problem_details":
                problem_id = clean_args.get("problem_id")
                if problem_id is None:
                    return {"error": "problem_id is required"}
                return get_problem_details(self._db, self._user_id, int(problem_id))

        except Exception as exc:
            logger.warning(
                "ToolDispatcher: tool=%s raised %s: %s",
                tool_name,
                type(exc).__name__,
                exc,
            )
            return {"error": str(exc), "tool": tool_name}

        return {"error": f"Tool not implemented: {tool_name}"}


# ---------------------------------------------------------------------------
# Function declarations for Gemini
# ---------------------------------------------------------------------------

_TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_user_performance_profile",
        description=(
            "Get the authenticated user's performance profile including solved counts, "
            "streaks, acceptance rate, and per-platform ratings. Call this first to "
            "understand the user's overall level."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="get_topic_performance",
        description=(
            "Get per-topic performance breakdown for the user. Returns up to 20 topics "
            "with solved count and strength level (strong/moderate/weak). Call this to "
            "identify weak areas that need practice."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="get_recent_submissions",
        description=(
            "Get the user's most recent submissions with problem info. Useful to see "
            "what they have been practising recently."
        ),
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of recent submissions to return (default 20, max 50)",
                }
            },
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="get_user_goals",
        description=(
            "Get the user's active and completed practice goals. Useful to align "
            "recommendations with what the user is trying to achieve."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="search_candidate_problems",
        description=(
            "Search for problems the user has NOT yet solved. Returns real problems "
            "from the database catalog — do NOT invent problem titles or URLs. "
            "Call this to find specific practice problems to recommend."
        ),
        parameters={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": (
                        "Filter by topic/tag name (e.g. 'Dynamic Programming', "
                        "'Binary Search', 'Graphs'). Case-insensitive substring match."
                    ),
                },
                "difficulty": {
                    "type": "string",
                    "description": (
                        "Filter by difficulty: 'Easy', 'Medium', 'Hard' for LeetCode. "
                        "Omit for Codeforces or when any difficulty is acceptable."
                    ),
                },
                "platform": {
                    "type": "string",
                    "enum": ["leetcode", "codeforces"],
                    "description": "Filter by platform. Omit to search all platforms.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of candidate problems to return (1-20, default 10).",
                },
            },
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="get_problem_details",
        description=(
            "Get detailed information about a specific problem by its database ID. "
            "Use this to verify a problem's details before recommending it. "
            "Only call with IDs returned by search_candidate_problems."
        ),
        parameters={
            "type": "object",
            "properties": {
                "problem_id": {
                    "type": "integer",
                    "description": "Database ID of the problem (from search_candidate_problems results).",
                }
            },
            "required": ["problem_id"],
        },
    ),
]

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are CodePulse's AI Problem Recommendation Agent. Your task is to recommend 3-5 specific, \
real practice problems to the user based on their actual performance data.

## Workflow

1. ALWAYS start by calling `get_user_performance_profile` AND `get_topic_performance` in your first turn.
2. Optionally call `get_user_goals` to align with the user's stated goals.
3. Call `search_candidate_problems` to find real, unsolved problems — use weak topic areas, \
   appropriate difficulty, and relevant platform filters.
4. Optionally call `get_problem_details` on 1-3 promising candidates to verify details.
5. Select 3-5 problems and prepare your final JSON response.

## Rules

- NEVER invent problem titles, URLs, or IDs. Only use problems returned by search_candidate_problems.
- NEVER compare ratings across platforms (LeetCode and Codeforces use different scales).
- If the problem catalog has fewer than 5 candidates, acknowledge catalog limitations honestly.
- If the user has insufficient data (fewer than 5 submissions), say so explicitly.
- Prioritise problems in topics where the user is "weak" or "moderate" strength.
- Match difficulty to the user's level (do not recommend Hard problems to beginners).

## Final Response Format

Respond with ONLY valid JSON in this exact structure (no markdown fences, no extra text):
{
  "recommendations": [
    {
      "problem_id": <int or null>,
      "title": "<exact title from DB>",
      "platform": "<platform>",
      "difficulty": "<difficulty or null>",
      "url": "<exact URL from DB>",
      "topics": ["<topic1>", "<topic2>"],
      "reason": "<2-3 sentence explanation of why this problem is recommended>",
      "priority": <1-5, 1=highest>,
      "likely_unsolved": true
    }
  ],
  "reasoning": "<brief paragraph summarising what you found about the user's profile and why these problems were chosen>",
  "has_sufficient_data": <true or false>
}
"""


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

_MAX_ITERATIONS = 6


class RecommendationAgent:
    """AI Recommendation Agent using Gemini function calling.

    Uses client.models.generate_content with manual tool dispatch, giving full
    control over tool execution, argument validation, and the agent loop.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID. NEVER comes from model output.
    """

    def __init__(self, db: Session, user_id: int) -> None:
        self._db = db
        self._user_id = user_id
        self._model = settings.GEMINI_MODEL
        self._timeout = settings.GEMINI_TIMEOUT_SECONDS

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            self._client = None
            self._configured = False
        else:
            self._client = genai.Client(api_key=api_key)
            self._configured = True

        self._dispatcher = ToolDispatcher(db, user_id)

    def is_configured(self) -> bool:
        """Return True when an API key is present and the client is ready."""
        return self._configured

    def recommend(self) -> AgentRecommendationResult:
        """Run the agent and return recommendations.

        Synchronous — runs the agent loop directly (blocking).
        Call from a background thread or FastAPI sync route so as not to
        block the event loop in production.

        Returns:
            AgentRecommendationResult with recommendations, reasoning, and metadata.
        """
        if not self._configured or self._client is None:
            return AgentRecommendationResult(
                error=(
                    "Gemini API key not configured. "
                    "Set GEMINI_API_KEY in the backend .env file."
                ),
                has_sufficient_data=False,
            )

        try:
            return self._run_agent_loop()

        except Exception as exc:
            logger.error(
                "RecommendationAgent: unexpected error type=%s user_id=%d: %s",
                type(exc).__name__,
                self._user_id,
                exc,
            )
            return AgentRecommendationResult(
                error=f"Agent error: {type(exc).__name__}: {exc}",
                has_sufficient_data=False,
            )

    def _run_agent_loop(self) -> AgentRecommendationResult:
        """Synchronous agent loop — runs generate_content repeatedly until text response.

        Returns:
            AgentRecommendationResult.
        """
        tool_calls_made: list[str] = []

        # Initial user message to trigger the agent workflow
        contents: list[types.Content] = [
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=(
                            "Please analyse my practice profile and recommend 3-5 specific "
                            "problems I should solve next to improve my skills."
                        )
                    )
                ],
            )
        ]

        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=2500,
            tools=[types.Tool(function_declarations=_TOOL_DECLARATIONS)],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

        for iteration in range(_MAX_ITERATIONS):
            logger.debug(
                "RecommendationAgent: iteration=%d user_id=%d",
                iteration,
                self._user_id,
            )

            response = self._client.models.generate_content(  # type: ignore[union-attr]
                model=self._model,
                contents=contents,
                config=config,
            )

            # Append the model's response to the conversation
            if response.candidates and response.candidates[0].content:
                contents.append(response.candidates[0].content)

            # Check for function calls in the response parts
            function_calls_in_response: list[Any] = []
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        function_calls_in_response.append(part.function_call)

            if not function_calls_in_response:
                # No function calls — extract text and return
                text = self._extract_text(response)
                return self._parse_final_response(text, tool_calls_made)

            # Dispatch all function calls and build a tool-result content block
            tool_result_parts: list[types.Part] = []
            for fc in function_calls_in_response:
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}

                logger.debug(
                    "RecommendationAgent: calling tool=%s args=%s",
                    tool_name,
                    list(tool_args.keys()),
                )
                tool_calls_made.append(tool_name)

                tool_result = self._dispatcher.dispatch(tool_name, tool_args)

                tool_result_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=getattr(fc, "id", None),
                            name=tool_name,
                            response={"result": tool_result},
                        )
                    )
                )

            # Append tool results as a "user" role content block
            contents.append(
                types.Content(role="user", parts=tool_result_parts)
            )

        # Exceeded max iterations — try to get a final response
        logger.warning(
            "RecommendationAgent: exceeded max_iterations=%d for user_id=%d",
            _MAX_ITERATIONS,
            self._user_id,
        )

        # Try one more generate without tools to force a text response
        try:
            final_config = types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                temperature=0.4,
                max_output_tokens=2000,
            )
            final_response = self._client.models.generate_content(  # type: ignore[union-attr]
                model=self._model,
                contents=contents,
                config=final_config,
            )
            text = self._extract_text(final_response)
            result = self._parse_final_response(text, tool_calls_made)
            result.error = (
                (result.error or "") +
                " (Warning: agent reached max tool call iterations)"
            ).strip()
            return result
        except Exception as exc:
            return AgentRecommendationResult(
                tool_calls_made=tool_calls_made,
                error=f"Agent exceeded max iterations and failed to produce a response: {exc}",
                has_sufficient_data=False,
            )

    def _extract_text(self, response: Any) -> str:
        """Extract text from a generate_content response.

        Args:
            response: Response from client.models.generate_content.

        Returns:
            Text content of the response, or empty string.
        """
        try:
            # Try the convenience .text attribute first
            if hasattr(response, "text") and response.text:
                return response.text
        except Exception:
            pass

        # Fallback: iterate over parts
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    return part.text

        return ""

    def _parse_final_response(
        self, text: str, tool_calls_made: list[str]
    ) -> AgentRecommendationResult:
        """Parse the model's final JSON text response into an AgentRecommendationResult.

        Args:
            text: Raw text from the model.
            tool_calls_made: List of tool names called during this run.

        Returns:
            AgentRecommendationResult.
        """
        if not text.strip():
            return AgentRecommendationResult(
                tool_calls_made=tool_calls_made,
                error="Agent produced an empty response.",
                has_sufficient_data=False,
            )

        # Try to parse JSON
        json_text = text.strip()

        # Strip markdown code fences if present
        if json_text.startswith("```"):
            lines = json_text.split("\n")
            # Remove first and last fence lines
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            json_text = "\n".join(lines)

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError:
            # Try to find JSON within the text
            start = json_text.find("{")
            end = json_text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(json_text[start:end])
                except json.JSONDecodeError:
                    return AgentRecommendationResult(
                        tool_calls_made=tool_calls_made,
                        agent_reasoning=text[:500],
                        error="Agent response could not be parsed as JSON.",
                        has_sufficient_data=False,
                    )
            else:
                return AgentRecommendationResult(
                    tool_calls_made=tool_calls_made,
                    agent_reasoning=text[:500],
                    error="Agent response did not contain valid JSON.",
                    has_sufficient_data=False,
                )

        # Extract fields
        has_sufficient_data = bool(data.get("has_sufficient_data", False))
        reasoning = str(data.get("reasoning", data.get("agent_reasoning", "")))

        raw_recs = data.get("recommendations", [])
        recommendations: list[AgentRecommendation] = []
        catalog_limited = False

        for raw in raw_recs[:5]:
            if not isinstance(raw, dict):
                continue

            problem_id = raw.get("problem_id")
            if problem_id is not None:
                try:
                    problem_id = int(problem_id)
                except (TypeError, ValueError):
                    problem_id = None

            topics = raw.get("topics", [])
            if not isinstance(topics, list):
                topics = []

            priority = raw.get("priority", len(recommendations) + 1)
            try:
                priority = int(priority)
            except (TypeError, ValueError):
                priority = len(recommendations) + 1

            recommendations.append(
                AgentRecommendation(
                    problem_id=problem_id,
                    title=str(raw.get("title", "Unknown")),
                    platform=str(raw.get("platform", "unknown")),
                    difficulty=raw.get("difficulty"),
                    url=str(raw.get("url", "")),
                    topics=[str(t) for t in topics],
                    reason=str(raw.get("reason", "")),
                    priority=priority,
                    likely_unsolved=bool(raw.get("likely_unsolved", True)),
                )
            )

        if data.get("catalog_limited"):
            catalog_limited = True

        return AgentRecommendationResult(
            recommendations=recommendations,
            agent_reasoning=reasoning,
            has_sufficient_data=has_sufficient_data,
            catalog_limited=catalog_limited,
            tool_calls_made=tool_calls_made,
            error=None,
        )
