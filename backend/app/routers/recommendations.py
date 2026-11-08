"""Recommendations and AI Coach Router.

Provides endpoints for:
- Personalized recommendations based on performance analysis
- AI Coach chat interface powered by Gemini
- AI Agent problem recommendations using Gemini function calling
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.orm import Session
from typing import Optional

from app.core.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.analytics import (
    PerformanceProfile,
    RecommendationsResponse,
)
from app.services.performance_analyzer import PerformanceAnalyzer
from app.services.recommendation_service import RecommendationService
from app.services.gemini_service import (
    GeminiService,
    GeminiNotConfiguredError,
    GeminiProviderError,
)
from app.services.recommendation_agent import (
    RecommendationAgent,
    AgentRecommendationResult,
)

router = APIRouter()

_VALID_ROLES = {"user", "assistant"}
_MAX_MESSAGE_LEN = 1000
_MAX_HISTORY_MESSAGES = 10


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
    recommendations = recommendation_service.generate_recommendations(profile)

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

    # Get authenticated user's performance data from the database.
    # This is rebuilt on every request — client cannot influence it.
    analyzer = PerformanceAnalyzer(db)
    profile = analyzer.analyze_user_performance(current_user.id)

    recommendation_service = RecommendationService()
    recommendations = recommendation_service.generate_recommendations(profile)

    performance_summary = _build_performance_summary(profile)
    recommendations_summary = _build_recommendations_summary(recommendations)

    # Convert validated ChatMessage objects back to plain dicts for the service.
    history: list[dict[str, str]] | None = None
    if request.conversation_history:
        history = [
            {"role": m.role, "content": m.content}
            for m in request.conversation_history
        ]

    gemini_service = GeminiService()

    if not gemini_service.is_configured():
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
        return ChatResponse(response=response, is_configured=True)

    except GeminiNotConfiguredError:
        return ChatResponse(
            response=(
                "AI Coach is not configured. "
                "Please set GEMINI_API_KEY in the backend environment."
            ),
            is_configured=False,
        )

    except GeminiProviderError as exc:
        http_status = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.is_retryable
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(
            status_code=http_status,
            detail=f"AI Coach unavailable: {str(exc)}",
        ) from exc


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


class AgentRecommendationResponse(BaseModel):
    """Response schema for the AI agent recommendation endpoint."""

    recommendations: list[AgentProblemRecommendation]
    agent_reasoning: str
    has_sufficient_data: bool
    catalog_limited: bool
    is_configured: bool
    tool_calls_made: list[str]
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# AI Agent recommendation endpoint
# ---------------------------------------------------------------------------


@router.post("/ai-coach/recommend", response_model=AgentRecommendationResponse)
def get_agent_recommendations(
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
    """
    agent = RecommendationAgent(db, user_id=current_user.id)

    if not agent.is_configured():
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

        # Check for timeout-style errors
        if result.error and (
            "timed out" in result.error.lower()
            or "timeout" in result.error.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=result.error,
            )

        return AgentRecommendationResponse(
            recommendations=[
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
                )
                for rec in result.recommendations
            ],
            agent_reasoning=result.agent_reasoning,
            has_sufficient_data=result.has_sufficient_data,
            catalog_limited=result.catalog_limited,
            is_configured=True,
            tool_calls_made=result.tool_calls_made,
            error=result.error,
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI recommendation agent error: {type(exc).__name__}",
        ) from exc
