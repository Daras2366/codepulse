from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class RatingHistory(Base):
    __tablename__ = "rating_history"
    
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "contest_id",
            name="uq_profile_rating_contest",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("platform_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    contest_id: Mapped[int | None] = mapped_column(
        ForeignKey("contests.id", ondelete="SET NULL"),
        nullable=True,
    )

    rating: Mapped[int] = mapped_column(nullable=False)

    rating_change: Mapped[int] = mapped_column(nullable=False)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    profile = relationship(
        "PlatformProfile",
        back_populates="rating_history",
    )

    contest = relationship(
        "Contest",
        back_populates="rating_history",
    )