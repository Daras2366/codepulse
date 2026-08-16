from sqlalchemy import (
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    DateTime
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from datetime import datetime

from app.models.base import Base, TimestampMixin
from app.models.enums import Platform


class PlatformProfile(Base, TimestampMixin):
    __tablename__ = "platform_profiles"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "platform",
            name="uq_user_platform",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True
    )

    platform: Mapped[Platform] = mapped_column(
        Enum(
            Platform,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )

    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    current_rating: Mapped[int | None] = mapped_column(Integer)

    max_rating: Mapped[int | None] = mapped_column(Integer)

    rank: Mapped[str | None] = mapped_column(
        String(100)
    )

    problems_solved: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    solved_easy: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    solved_medium: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    solved_hard: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    contests_attended: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    profile_url: Mapped[str | None] = mapped_column(
        String(500)
    )

    is_connected: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    user = relationship(
        "User",
        back_populates="platform_profiles",
    )
    
    submissions = relationship(
        "Submission",
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    
    contest_participations = relationship(
        "ContestParticipation",
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    
    rating_history = relationship(
        "RatingHistory",
        back_populates="profile",
        cascade="all, delete-orphan",
    )