"""Recommendations and AI Coach Router.

Provides endpoints for:
- Personalized recommendations based on performance analysis
- AI Coach chat interface powered by Gemini
- AI Agent problem recommendations using Gemini function calling
"""

import asyncio
import json
import logging
import queue
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session
from typing import Optional

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import rate_limiter
from app.models.enums import CoachFeedbackAction, GoalStatus
from app.models.goal import Goal
from app.models.user import User
from app.schemas.analytics import (
    PerformanceProfile,
    RecommendationsResponse,
)
from app.schemas.study_plan import StudyPlanContest, StudyPlanResponse
from app.services import coach_cache
from app.services.coach_feedback_service import (
    FeedbackNotFoundError,
    submit_feedback,
)
from app.services.coach_observability_service import (
    ENDPOINT_CHAT,
    ENDPOINT_CHAT_STREAM,
    ENDPOINT_RECOMMEND,
    CoachObservabilityService,
)
from app.services.performance_analyzer import PerformanceAnalyzer
from app.services.recommendation_service import RecommendationService
from app.services.study_plan_service import StudyPlanService
from app.services.gemini_service import (
    GeminiService,
    GeminiNotConfiguredError,
    GeminiProviderError,
)
from app.services.recommendation_agent import (
    CoachChatAgent,
    RecommendationAgent,
    AgentRecommendationResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_ROLES = {"user", "assistant"}
_MAX_MESSAGE_LEN = 1000
_MAX_HISTORY_MESSAGES = 10


def _setting_int(name: str, default: int) -> int:
    """Read an int setting defensively (tests may patch ``settings``)."""
    value = getattr(settings, name, default)
    return int(value) if isinstance(value, (int, float)) else default


def _enforce_rate_limit(user_id: int, scope: str) -> None:
    """Apply the per-user rate limit for an AI Coach endpoint.

    ``scope`` is "RECOMMEND" or "CHAT". Every authenticated request consumes
    quota — including requests that later fail at the provider — and
    ``force_refresh`` does not bypass this check.
    """
    default_limit = 20 if scope == "RECOMMEND" else 60
    limit = _setting_int(f"AI_COACH_{scope}_RATE_LIMIT", default_limit)
    window = _setting_int("AI_COACH_RATE_LIMIT_WINDOW_SECONDS", 3600)
    result = rate_limiter.check(f"{scope.lower()}:{user_id}", limit, window)
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "AI Coach rate limit reached. "
                "Please try again later."
            ),
            headers={"Retry-After": str(result.retry_after_seconds)},
        )


def _model_name() -> Optional[str]:
    model = getattr(settings, "GEMINI_MODEL", None)
    return model if isinstance(model, str) and model else None


class ChatMessage(BaseModel):
    """A single turn in the conversation history."""

    role: str
    content: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in _VALID_ROLES:
            raise ValueError(f"role must be one of {_VALID_ROLES}")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        if len(v) > _MAX_MESSAGE_LEN:
            raise ValueError(
                f"Message in history too long (max {_MAX_MESSAGE_LEN} characters)"
            )
        return v


class ChatRequest(BaseModel):
    """Request for AI Coach chat."""

    message: str
    conversation_history: list[ChatMessage] | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message cannot be empty")
        if len(stripped) > _MAX_MESSAGE_LEN:
            raise ValueError(
                f"Message too long (max {_MAX_MESSAGE_LEN} characters)"
            )
        return stripped

    @field_validator("conversation_history")
    @classmethod
    def validate_history(
        cls, v: list[ChatMessage] | None
    ) -> list[ChatMessage] | None:
        if v is not None and len(v) > _MAX_HISTORY_MESSAGES:
            raise ValueError(
                f"Conversation history too long (max {_MAX_HISTORY_MESSAGES} messages)"
            )
        return v


class ChatResponse(BaseModel):
    """Response from AI Coach."""

    response: str
    is_configured: bool
    tool_calls_made: list[str] = Field(default_factory=list)


def _get_active_goals(db: Session, user_id: int) -> list[dict]:
    """Return the user's active goals as plain dicts for the recommendation engine."""
    goals = (
        db.query(Goal)
        .filter(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE)
        .order_by(Goal.created_at.desc())
        .all()
    )
    return [
        {
            "title": g.title,
            "goal_type": g.goal_type.value if hasattr(g.goal_type, "value") else str(g.goal_type),
            "target_value": g.target_value,
            "topic_name": g.topic_name,
            "deadline": g.deadline.isoformat() if g.deadline else None,
        }
        for g in goals
    ]


@router.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationsResponse:
    """Get personalized recommendations based on performance analysis.

    Returns prioritized, actionable recommendations for improving DSA skills.
    """
    analyzer = PerformanceAnalyzer(db)
    profile = analyzer.analyze_user_performance(current_user.id)

    recommendation_service = RecommendationService()
    recommendations = recommendation_service.generate_recommendations(
        profile, active_goals=_get_active_goals(db, current_user.id)
    )

    has_sufficient_data = (
        profile.overview.solved_problems > 0
        or profile.submission_behavior.total_submissions > 0
    )

    return RecommendationsResponse(
        recommendations=recommendations,
        data_quality=profile.data_quality,
        has_sufficient_data=has_sufficient_data,
    )


@router.post("/ai-coach/chat", response_model=ChatResponse)
async def chat_with_coach(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Chat with the AI Coach about your performance.

    The AI Coach has access to your performance data and can answer questions
    about strengths, weaknesses, rating trends, and help create study plans.

    The user identity is always derived from the authenticated JWT — never from
    the request body.  Performance context is rebuilt on every call from the
    database, so client-supplied data cannot manipulate the AI response.
    """
    # Validation is handled by Pydantic validators on ChatRequest.
    # Re-raise validation errors as 400.
    from pydantic import ValidationError  # local to avoid circular imports

    _enforce_rate_limit(current_user.id, "CHAT")
    started_at = time.monotonic()
    observability = CoachObservabilityService(db)

    gemini_service = GeminiService()

    # Convert validated ChatMessage objects back to plain dicts for the service.
    history: list[dict[str, str]] | None = None
    if request.conversation_history:
        history = [
            {"role": m.role, "content": m.content}
            for m in request.conversation_history
        ]

    # Primary path: the tool-using chat agent fetches the user's real data
    # through the shared ToolDispatcher (user_id always comes from the
    # authenticated session, never from model arguments) instead of relying on
    # an injected text summary. It runs synchronously, so it is offloaded to a
    # worker thread to avoid blocking the event loop.
    if gemini_service.is_configured():
        agent = CoachChatAgent(
            db, user_id=current_user.id, client=gemini_service.genai_client
        )
        result = await asyncio.to_thread(
            agent.chat, request.message, history
        )
        latency_ms = int((time.monotonic() - started_at) * 1000)

        if result.error is None and result.text:
            observability.record_run(
                user_id=current_user.id,
                endpoint=ENDPOINT_CHAT,
                model=getattr(agent, "last_model", None) or _model_name(),
                latency_ms=latency_ms,
                tool_calls=result.tool_calls_made,
                usage=getattr(agent, "last_usage", None),
                cache_hit=False,
            )
            return ChatResponse(
                response=result.text,
                is_configured=True,
                tool_calls_made=result.tool_calls_made,
            )

        if result.error is not None:
            observability.record_run(
                user_id=current_user.id,
                endpoint=ENDPOINT_CHAT,
                model=getattr(agent, "last_model", None) or _model_name(),
                latency_ms=latency_ms,
                tool_calls=result.tool_calls_made,
                usage=getattr(agent, "last_usage", None),
                cache_hit=False,
                error_kind=result.error_kind or "unknown",
            )
            http_status = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if result.error_retryable
                else status.HTTP_502_BAD_GATEWAY
            )
            raise HTTPException(
                status_code=http_status,
                detail=f"AI Coach unavailable: {result.error}",
            )

        # The agent produced no usable text — fall through to the legacy
        # single-shot path below.

    # Get authenticated user's performance data from the database.
    # This is rebuilt on every request — client cannot influence it.
    analyzer = PerformanceAnalyzer(db)
    profile = analyzer.analyze_user_performance(current_user.id)

    recommendation_service = RecommendationService()
    active_goals = _get_active_goals(db, current_user.id)
    recommendations = recommendation_service.generate_recommendations(
        profile, active_goals=active_goals
    )

    performance_summary = _build_performance_summary(profile)
    recommendations_summary = _build_recommendations_summary(recommendations)
    if active_goals:
        goal_lines = ", ".join(g["title"] for g in active_goals[:3])
        recommendations_summary += f"\n\nActive user goals: {goal_lines}"

    if not gemini_service.is_configured():
        observability.record_run(
            user_id=current_user.id,
            endpoint=ENDPOINT_CHAT,
            model=_model_name(),
            latency_ms=int((time.monotonic() - started_at) * 1000),
            cache_hit=False,
            error_kind="not_configured",
        )
        return ChatResponse(
            response=(
                "AI Coach is not configured. "
                "Please set GEMINI_API_KEY in the backend environment."
            ),
            is_configured=False,
        )

    try:
        response = await gemini_service.generate_coach_response(
            user_message=request.message,
            performance_summary=performance_summary,
            recommendations_summary=recommendations_summary,
            conversation_history=history,
        )
        observability.record_run(
            user_id=current_user.id,
            endpoint=ENDPOINT_CHAT,
            model=getattr(gemini_service, "last_model", None) or _model_name(),
            latency_ms=int((time.monotonic() - started_at) * 1000),
            usage=getattr(gemini_service, "last_usage", None),
            cache_hit=False,
        )
        return ChatResponse(response=response, is_configured=True)

    except GeminiNotConfiguredError:
        observability.record_run(
            user_id=current_user.id,
            endpoint=ENDPOINT_CHAT,
            model=_model_name(),
            latency_ms=int((time.monotonic() - started_at) * 1000),
            cache_hit=False,
            error_kind="not_configured",
        )
        return ChatResponse(
            response=(
                "AI Coach is not configured. "
                "Please set GEMINI_API_KEY in the backend environment."
            ),
            is_configured=False,
        )

    except GeminiProviderError as exc:
        observability.record_run(
            user_id=current_user.id,
            endpoint=ENDPOINT_CHAT,
            model=getattr(gemini_service, "last_model", None) or _model_name(),
            latency_ms=int((time.monotonic() - started_at) * 1000),
            cache_hit=False,
            error_kind=exc.kind,
        )
        http_status = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.is_retryable
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(
            status_code=http_status,
            detail=f"AI Coach unavailable: {str(exc)}",
        ) from exc

    except Exception:
        observability.record_run(
            user_id=current_user.id,
            endpoint=ENDPOINT_CHAT,
            model=getattr(gemini_service, "last_model", None) or _model_name(),
            latency_ms=int((time.monotonic() - started_at) * 1000),
            cache_hit=False,
            error_kind="unknown",
        )
        raise


def _sse_event(event: str, data: dict) -> str:
    """Format one Server-Sent Events frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/ai-coach/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Streaming AI Coach chat over Server-Sent Events.

    Event order: zero or more ``tool_call`` (tool name only — never arguments
    or results), then ``token`` (answer text chunks), then exactly one ``done``
    (``tool_calls_made`` + ``model``) or one ``error`` (``error_kind``).

    The CHAT rate limit is applied before the stream starts, so a 429 is a
    normal HTTP response — never an SSE event. The synchronous agent loop
    runs in a worker thread; client disconnects cancel it via a threading
    event and the DB session is released by the ``get_db`` dependency once
    the response finishes.
    """
    _enforce_rate_limit(current_user.id, "CHAT")
    started_at = time.monotonic()
    observability = CoachObservabilityService(db)

    gemini_service = GeminiService()
    agent = CoachChatAgent(
        db, user_id=current_user.id, client=gemini_service.genai_client
    )
    history: list[dict[str, str]] | None = None
    if request.conversation_history:
        history = [
            {"role": m.role, "content": m.content}
            for m in request.conversation_history
        ]

    async def event_stream():
        events: "queue.Queue" = queue.Queue()
        cancel = threading.Event()
        sentinel = object()
        tool_calls_made: list[str] = []
        done_meta: dict = {}
        error_kind: Optional[str] = None

        def worker() -> None:
            try:
                for event in agent.stream_chat(request.message, history):
                    if cancel.is_set():
                        break
                    events.put(event)
            except Exception as exc:  # defensive — stream_chat handles its own
                logger.warning(
                    "chat_stream worker failed user_id=%d: %s",
                    current_user.id,
                    exc,
                )
                events.put(
                    {
                        "type": "error",
                        "error_kind": "unknown",
                        "error": "stream_failed",
                    }
                )
            finally:
                events.put(sentinel)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            while True:
                event = await asyncio.to_thread(events.get)
                if event is sentinel:
                    break
                event_type = event.get("type")
                if event_type == "tool_call":
                    tool_calls_made.append(str(event.get("name", "")))
                    yield _sse_event(
                        "tool_call", {"tool": event.get("name", "")}
                    )
                elif event_type == "token":
                    yield _sse_event("token", {"text": event.get("text", "")})
                elif event_type == "done":
                    done_meta = event
                    yield _sse_event(
                        "done",
                        {
                            "tool_calls_made": event.get(
                                "tool_calls_made", tool_calls_made
                            ),
                            "model": event.get("model")
                            or getattr(agent, "last_model", None),
                        },
                    )
                elif event_type == "error":
                    error_kind = event.get("error_kind") or "unknown"
                    yield _sse_event("error", {"error_kind": error_kind})
        finally:
            cancel.set()
            await asyncio.to_thread(thread.join, 2.0)
            observability.record_run(
                user_id=current_user.id,
                endpoint=ENDPOINT_CHAT_STREAM,
                model=(
                    done_meta.get("model")
                    or getattr(agent, "last_model", None)
                    or _model_name()
                ),
                latency_ms=int((time.monotonic() - started_at) * 1000),
                tool_calls=tool_calls_made,
                usage=getattr(agent, "last_usage", None),
                cache_hit=False,
                error_kind=error_kind,
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _build_performance_summary(profile: PerformanceProfile) -> str:
    """Build a compact performance summary for the LLM.

    Uses the stored acceptance_rate field and per-platform ratings to avoid
    cross-platform rating misrepresentation.
    """
    lines: list[str] = [
        f"Total solved: {profile.overview.solved_problems}",
        f"Total submissions: {profile.overview.total_submissions}",
        f"Active days: {profile.overview.active_days}",
        f"Current streak: {profile.submission_behavior.current_streak_days} days",
        f"Longest streak: {profile.submission_behavior.longest_streak_days} days",
    ]

    # Use stored acceptance rate — do not recompute.
    ar = profile.submission_behavior.acceptance_rate
    if ar is not None:
        lines.append(f"Acceptance rate: {ar * 100:.1f}%")
    else:
        lines.append("Acceptance rate: insufficient data")

    # Per-platform ratings — never merge across platforms.
    if profile.overview.ratings_by_platform:
        lines.append("")
        lines.append("Ratings by platform (scales differ — do not compare):")
        for pr in profile.overview.ratings_by_platform:
            parts_r = [f"  {pr.platform}:"]
            if pr.current_rating is not None:
                parts_r.append(f"current={pr.current_rating}")
            if pr.max_rating is not None:
                parts_r.append(f"max={pr.max_rating}")
            if len(parts_r) == 1:
                parts_r.append("no rating data")
            lines.append(" ".join(parts_r))
    else:
        lines.append("Ratings: no rating data available")

    # Topic performance.
    if profile.topic_performance:
        lines.append("")
        lines.append("Topic performance (top 5):")
        for topic in profile.topic_performance[:5]:
            recent = (
                f", {topic.recent_activity} solved in last 30d"
                if topic.recent_activity > 0
                else ", no recent activity"
            )
            lines.append(
                f"  {topic.topic}: {topic.solved_count} solved "
                f"({topic.strength_level}{recent})"
            )

    weak_topics = [t for t in profile.topic_performance if t.strength_level == "weak"]
    if weak_topics:
        lines.append("")
        lines.append("Weak topics:")
        for topic in weak_topics[:3]:
            lines.append(f"  {topic.topic}: {topic.solved_count} solved")

    # Difficulty coverage.
    if profile.difficulty_performance:
        lines.append("")
        lines.append("Difficulty coverage:")
        for diff in profile.difficulty_performance:
            lines.append(
                f"  {diff.difficulty}: {diff.solved_count} solved "
                f"({diff.coverage_status})"
            )

    # Contest performance.
    cp = profile.contest_performance
    if cp.contests_participated > 0:
        lines.append("")
        lines.append(f"Contests: {cp.contests_participated} participated")
        if cp.recent_participation > 0:
            lines.append(f"  Recent (90d): {cp.recent_participation}")
        if cp.participation_trend != "insufficient_data":
            lines.append(f"  Trend: {cp.participation_trend}")

    # Rating trend.
    rt = profile.rating_trend
    if rt.trend_direction != "insufficient_data":
        lines.append(f"Rating trend: {rt.trend_direction}")
        if rt.rating_change_30_days is not None:
            lines.append(f"  30d change: {rt.rating_change_30_days:+d}")

    # Data quality notice.
    dq = profile.data_quality
    coverage_notes: list[str] = []
    if not dq.has_topic_data:
        coverage_notes.append("no topic data")
    if not dq.has_contest_data:
        coverage_notes.append("no contest data")
    if dq.profile_reported_solved > 0 and dq.locally_tagged_solved < dq.profile_reported_solved:
        coverage_notes.append(
            f"only {dq.locally_tagged_solved}/{dq.profile_reported_solved} "
            "solved problems have topic tags"
        )
    if coverage_notes:
        lines.append("")
        lines.append(f"Data limitations: {'; '.join(coverage_notes)}")

    return "\n".join(lines)


def _build_recommendations_summary(recommendations: list) -> str:
    """Build a compact recommendations summary for the LLM."""
    if not recommendations:
        return "No recommendations available (insufficient data)."

    lines = ["Top recommendations:"]
    for i, rec in enumerate(recommendations[:5], 1):
        lines.append(f"{i}. [{rec.priority.upper()}] {rec.title}")
        lines.append(f"   Reason: {rec.reason}")
        lines.append(f"   Action: {rec.suggested_activity}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI Agent recommendation schemas
# ---------------------------------------------------------------------------


class AgentProblemRecommendation(BaseModel):
    """A single problem recommendation from the AI agent."""

    problem_id: Optional[int] = None
    title: str
    platform: str
    difficulty: Optional[str] = None
    url: str
    topics: list[str]
    reason: str
    priority: int
    likely_unsolved: bool
    recommendation_id: Optional[int] = None
    """Stable id of the persisted coach_recommendations row (for feedback)."""


class AgentRecommendationResponse(BaseModel):
    """Response schema for the AI agent recommendation endpoint."""

    recommendations: list[AgentProblemRecommendation]
    agent_reasoning: str
    has_sufficient_data: bool
    catalog_limited: bool
    is_configured: bool
    tool_calls_made: list[str]
    error: Optional[str] = None
    error_kind: Optional[str] = None
    from_cache: bool = False
    """True when this response was served from the recommendation cache."""
    refreshed_at: Optional[str] = None
    """ISO timestamp of the latest actual (non-cached) generation."""


class FeedbackRequest(BaseModel):
    """Request body for POST /ai-coach/feedback."""

    recommendation_id: int
    action: CoachFeedbackAction


class FeedbackResponse(BaseModel):
    """Response for POST /ai-coach/feedback."""

    recommendation_id: int
    action: str
    recorded: bool
    """False when identical feedback already existed (idempotent retry)."""


# ---------------------------------------------------------------------------
# AI Agent recommendation endpoint
# ---------------------------------------------------------------------------


@router.post("/ai-coach/recommend", response_model=AgentRecommendationResponse)
def get_agent_recommendations(
    force_refresh: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRecommendationResponse:
    """Get AI-powered problem recommendations using Gemini function calling.

    The agent analyses the authenticated user's performance profile and
    searches the problem catalog for real, unsolved practice problems.

    The user identity is ALWAYS derived from the authenticated JWT — the
    agent loop never accepts user_id from model-generated arguments.

    Returns a structured response with up to 5 problem recommendations,
    the agent's reasoning, and observability metadata (tool calls made).

    Caching: successful results are cached per user for
    ``AI_COACH_RECOMMEND_CACHE_TTL_SECONDS`` (default 6h). The cache key
    covers the user's submission state, active goals, model, and prompt
    version. Pass ``force_refresh=true`` to bypass the cache (still subject
    to the per-user rate limit).
    """
    _enforce_rate_limit(current_user.id, "RECOMMEND")

    fingerprint = coach_cache.compute_fingerprint(db, current_user.id)

    if not force_refresh:
        cached = coach_cache.get_cached(current_user.id, fingerprint)
        if cached is not None:
            CoachObservabilityService(db).record_run(
                user_id=current_user.id,
                endpoint=ENDPOINT_RECOMMEND,
                model=_model_name(),
                cache_hit=True,
            )
            payload = dict(cached["payload"])
            return AgentRecommendationResponse(
                **payload,
                from_cache=True,
                refreshed_at=cached.get("refreshed_at"),
            )

    # Serialize generation per fingerprint so concurrent identical requests
    # don't run the agent loop in parallel; re-check the cache inside the
    # lock in case another request just populated it.
    with coach_cache.generation_lock(current_user.id, fingerprint):
        if not force_refresh:
            cached = coach_cache.get_cached(current_user.id, fingerprint)
            if cached is not None:
                CoachObservabilityService(db).record_run(
                    user_id=current_user.id,
                    endpoint=ENDPOINT_RECOMMEND,
                    model=_model_name(),
                    cache_hit=True,
                )
                payload = dict(cached["payload"])
                return AgentRecommendationResponse(
                    **payload,
                    from_cache=True,
                    refreshed_at=cached.get("refreshed_at"),
                )

        return _generate_agent_recommendations(
            current_user=current_user,
            db=db,
            fingerprint=fingerprint,
        )


def _generate_agent_recommendations(
    *,
    current_user: User,
    db: Session,
    fingerprint: str,
) -> AgentRecommendationResponse:
    """Run the agent, record observability, persist + cache on success."""
    started_at = time.monotonic()
    observability = CoachObservabilityService(db)
    agent = RecommendationAgent(db, user_id=current_user.id)

    if not agent.is_configured():
        observability.record_run(
            user_id=current_user.id,
            endpoint=ENDPOINT_RECOMMEND,
            model=_model_name(),
            latency_ms=int((time.monotonic() - started_at) * 1000),
            cache_hit=False,
            error_kind="not_configured",
        )
        return AgentRecommendationResponse(
            recommendations=[],
            agent_reasoning="",
            has_sufficient_data=False,
            catalog_limited=False,
            is_configured=False,
            tool_calls_made=[],
            error=(
                "AI recommendations are not configured. "
                "Please set GEMINI_API_KEY in the backend environment."
            ),
        )

    try:
        result: AgentRecommendationResult = agent.recommend()
    except Exception as exc:
        observability.record_run(
            user_id=current_user.id,
            endpoint=ENDPOINT_RECOMMEND,
            model=getattr(agent, "last_model", None) or _model_name(),
            latency_ms=int((time.monotonic() - started_at) * 1000),
            cache_hit=False,
            error_kind="unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI recommendation agent error: {type(exc).__name__}",
        ) from exc

    latency_ms = int((time.monotonic() - started_at) * 1000)
    is_timeout = bool(result.error) and (
        "timed out" in result.error.lower()
        or "timeout" in result.error.lower()
    )
    error_kind = result.error_kind or ("timeout" if is_timeout else None)
    recorded_error_kind = (
        error_kind or ("agent_error" if result.error else None)
    )

    run = observability.record_run(
        user_id=current_user.id,
        endpoint=ENDPOINT_RECOMMEND,
        model=getattr(agent, "last_model", None) or _model_name(),
        latency_ms=latency_ms,
        tool_calls=result.tool_calls_made,
        usage=getattr(agent, "last_usage", None),
        cache_hit=False,
        error_kind=recorded_error_kind,
    )

    # Check for timeout-style errors
    if result.error and is_timeout:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.error,
        )

    # Only successful, validated results are persisted and cached. A result
    # counts as successful when there is no provider error_kind and either no
    # error at all or recommendations survived verification (e.g. the
    # max-iterations warning path still yields usable recommendations).
    is_success = (
        result.error_kind is None
        and (result.error is None or bool(result.recommendations))
    )

    rec_id_map: dict[int, int] = {}
    if is_success and run is not None:
        rec_id_map = observability.persist_recommendations(
            run_id=run.id,
            user_id=current_user.id,
            recommendations=result.recommendations,
        )

    refreshed_at = datetime.now(timezone.utc)
    response_recs = [
        AgentProblemRecommendation(
            problem_id=rec.problem_id,
            title=rec.title,
            platform=rec.platform,
            difficulty=rec.difficulty,
            url=rec.url,
            topics=rec.topics,
            reason=rec.reason,
            priority=rec.priority,
            likely_unsolved=rec.likely_unsolved,
            recommendation_id=(
                rec_id_map.get(rec.problem_id) if rec.problem_id is not None else None
            ),
        )
        for rec in result.recommendations
    ]

    response = AgentRecommendationResponse(
        recommendations=response_recs,
        agent_reasoning=result.agent_reasoning,
        has_sufficient_data=result.has_sufficient_data,
        catalog_limited=result.catalog_limited,
        is_configured=True,
        tool_calls_made=result.tool_calls_made,
        error=result.error,
        error_kind=result.error_kind,
        from_cache=False,
        refreshed_at=refreshed_at.isoformat(),
    )

    if is_success:
        coach_cache.set_cached(
            current_user.id,
            fingerprint,
            response.model_dump(exclude={"from_cache", "refreshed_at"}),
            refreshed_at=refreshed_at,
        )

    return response


@router.post("/ai-coach/feedback", response_model=FeedbackResponse)
def submit_coach_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """Submit feedback on an AI problem recommendation.

    The recommendation must belong to the authenticated user. Feedback is
    idempotent: resubmitting the same ``(recommendation_id, action)`` pair
    returns the existing record without creating a duplicate.
    """
    try:
        feedback, created = submit_feedback(
            db,
            user_id=current_user.id,
            recommendation_id=request.recommendation_id,
            action=request.action,
        )
    except FeedbackNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return FeedbackResponse(
        recommendation_id=feedback.recommendation_id,
        action=feedback.action.value,
        recorded=created,
    )


# ---------------------------------------------------------------------------
# Personalized study plan & upcoming contests
# ---------------------------------------------------------------------------


@router.get("/ai-coach/study-plan", response_model=StudyPlanResponse)
def get_study_plan(
    timezone: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StudyPlanResponse:
    """Get today's personalized study plan.

    Everything returned is derived from the authenticated user's real data:
    focus topic from the performance profile (or an active topic goal),
    problems are unsolved ``Problem`` catalog rows, the daily target comes
    only from an active user goal with a deadline, and the contest is the
    next future ``Contest`` record. No value is fabricated.

    ``timezone`` is an optional IANA name (e.g. "Asia/Kolkata") used only to
    compute the user's local calendar day for daily progress; invalid values
    fall back to UTC.
    """
    return StudyPlanService(db).build_plan(current_user.id, tz_name=timezone)


@router.get("/ai-coach/upcoming-contests", response_model=list[StudyPlanContest])
def get_upcoming_contests(
    limit: int = 5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[StudyPlanContest]:
    """List upcoming contests (start_time strictly in the future).

    Past contests are never returned. Contest data is global (not
    user-specific) but the endpoint still requires authentication.
    """
    limit = max(1, min(limit, 20))
    return StudyPlanService(db).upcoming_contests(limit=limit)
