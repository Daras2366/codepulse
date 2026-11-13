"""AI Coach observability and feedback models (Stage 4).

Tables:
  coach_runs               — one row per recommendation/chat execution
  coach_recommendations    — persisted problem recommendations per run
  coach_feedback           — user/auto feedback events on recommendations
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import CoachFeedbackAction


class CoachRun(Base, TimestampMixin):
    """Observability record for a single AI Coach execution.

    Never stores raw prompts, chat messages, or tool-result payloads —
    ``tool_calls`` holds tool NAMES only.
    """

    __tablename__ = "coach_runs"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    endpoint: Mapped[str] = mapped_column(String(50), nullable=False)
    """e.g. "ai-coach/recommend" or "ai-coach/chat"."""

    model: Mapped[Optional[str]] = mapped_column(String(100))
    """Model that produced the response, when known."""

    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)

    tool_calls: Mapped[Optional[list]] = mapped_column(JSON)
    """Tool names invoked during the run (no arguments, no payloads)."""

    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer)

    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    error_kind: Mapped[Optional[str]] = mapped_column(String(50))
    """Classified error kind (provider_unavailable, rate_limited, ...) or NULL."""


class CoachRecommendation(Base, TimestampMixin):
    """A persisted AI problem recommendation belonging to a coach run.

    ``problem_id`` is the canonical ``problems.id`` primary key — the same id
    used by ``submissions.problem_id``, so accepted submissions can be matched
    directly.
    """

    __tablename__ = "coach_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)

    run_id: Mapped[int] = mapped_column(
        ForeignKey("coach_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    """1-based ordering within the run (1 = highest priority)."""


class CoachFeedback(Base, TimestampMixin):
    """Feedback event on a persisted recommendation.

    ``(recommendation_id, action)`` is unique so retries/repeated frontend
    submissions cannot create duplicate events.
    """

    __tablename__ = "coach_feedback"

    __table_args__ = (
        UniqueConstraint(
            "recommendation_id",
            "action",
            name="uq_coach_feedback_rec_action",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("coach_recommendations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    action: Mapped[CoachFeedbackAction] = mapped_column(
        Enum(
            CoachFeedbackAction,
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
    )
