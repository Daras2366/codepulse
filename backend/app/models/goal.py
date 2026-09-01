"""Goal model.

Supports six goal types:
  RATING      — reach a target rating on a specific platform
  PROBLEMS    — solve N problems (optionally within a date range / difficulty / platform)
  TOPIC       — solve N problems on a specific topic
  CONSISTENCY — be active on N days within a date range
  CONTEST     — participate in N contests within a date range
  PLACEMENT   — solve N problems with optional difficulty / topic filters (interview prep)

Fields:
  platform         — "leetcode" | "codeforces" | None (cross-platform goals)
  start_date       — date from which progress is counted (defaults to goal creation date)
  deadline         — target completion date (nullable = open-ended)
  start_value      — recorded value at goal creation (used for RATING progress baseline)
  topic_slug       — canonical topic slug for TOPIC goals (e.g. "dynamic-programming")
  topic_name       — human-readable topic name for TOPIC goals
  difficulty_filter — "Easy" | "Medium" | "Hard" | None (for PROBLEMS / PLACEMENT goals)
  completed_at     — timestamp when goal was first marked COMPLETED
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import GoalStatus, GoalType


class Goal(Base, TimestampMixin):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    title: Mapped[str] = mapped_column(String(200), nullable=False)

    description: Mapped[Optional[str]] = mapped_column(Text)

    goal_type: Mapped[GoalType] = mapped_column(
        Enum(GoalType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Platform / topic / difficulty scoping
    # ------------------------------------------------------------------

    platform: Mapped[Optional[str]] = mapped_column(String(30))
    """Platform slug (e.g. "codeforces", "leetcode"). NULL = cross-platform."""

    topic_slug: Mapped[Optional[str]] = mapped_column(String(150))
    """Canonical topic slug for TOPIC goals (e.g. "dynamic-programming")."""

    topic_name: Mapped[Optional[str]] = mapped_column(String(100))
    """Human-readable topic name for TOPIC goals (e.g. "Dynamic Programming")."""

    difficulty_filter: Mapped[Optional[str]] = mapped_column(String(20))
    """Optional difficulty filter for PROBLEMS / PLACEMENT goals ("Easy"/"Medium"/"Hard")."""

    # ------------------------------------------------------------------
    # Target & progress
    # ------------------------------------------------------------------

    target_value: Mapped[int] = mapped_column(nullable=False)
    """The numeric goal target (rating, problem count, active days, contest count…)."""

    start_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    """Value recorded at goal creation — used as baseline for RATING progress."""

    current_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    """Cached latest computed progress value. Refreshed on every GET /progress call."""

    # ------------------------------------------------------------------
    # Time window
    # ------------------------------------------------------------------

    start_date: Mapped[Optional[date]] = mapped_column(Date)
    """Inclusive start date for progress counting. Defaults to goal creation date."""

    deadline: Mapped[Optional[date]] = mapped_column(Date)
    """Deadline by which the goal must be completed. NULL = open-ended."""

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus, values_callable=lambda x: [e.value for e in x]),
        default=GoalStatus.ACTIVE,
        nullable=False,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    """Timestamp of first completion. Set once; not reset if progress regresses."""

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    user = relationship("User", back_populates="goals")