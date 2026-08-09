from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import GoalStatus, GoalType


class Goal(Base, TimestampMixin):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    
    description: Mapped[str | None] = mapped_column(
        Text
    )

    goal_type: Mapped[GoalType] = mapped_column(
        Enum(GoalType),
        nullable=False,
    )

    target_value: Mapped[int] = mapped_column(nullable=False)

    current_value: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus),
        default=GoalStatus.ACTIVE,
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="goals",
    )