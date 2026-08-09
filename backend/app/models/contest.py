from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import Platform


class Contest(Base, TimestampMixin):
    __tablename__ = "contests"
    
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "platform_contest_id",
            name="uq_platform_contest",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    platform_contest_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    platform: Mapped[str] = mapped_column(
        Enum(Platform),
        nullable=False,
    )
    
    contest_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    participations = relationship(
        "ContestParticipation",
        back_populates="contest",
        cascade="all, delete-orphan",
    )
    
    rating_history = relationship(
        "RatingHistory",
        back_populates="contest",
    )
    
    submissions = relationship(
        "Submission",
        back_populates="contest",
    )