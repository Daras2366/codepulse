from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import SubmissionStatus


class Submission(Base, TimestampMixin):
    __tablename__ = "submissions"
    
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "platform_submission_id",
            name="uq_profile_platform_submission",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("platform_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    language: Mapped[str] = mapped_column(nullable=False)

    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus),
        nullable=False,
    )
    
    platform_submission_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    
    contest_id: Mapped[int | None] = mapped_column(
        ForeignKey("contests.id", ondelete="SET NULL"),
        index=True
    )

    profile = relationship(
        "PlatformProfile",
        back_populates="submissions",
    )

    problem = relationship(
        "Problem",
        back_populates="submissions",
    )
    
    contest = relationship(
        "Contest",
        back_populates="submissions",
    )