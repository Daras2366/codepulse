from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ContestParticipation(Base, TimestampMixin):
    __tablename__ = "contest_participations"

    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "contest_id",
            name="uq_profile_contest",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("platform_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    contest_id: Mapped[int] = mapped_column(
        ForeignKey("contests.id", ondelete="CASCADE"),
        nullable=False,
    )

    rank: Mapped[int | None] = mapped_column(Integer)

    old_rating: Mapped[int | None] = mapped_column(Integer)

    new_rating: Mapped[int | None] = mapped_column(Integer)

    rating_change: Mapped[int | None] = mapped_column(Integer)

    solved: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    penalty: Mapped[int | None] = mapped_column(Integer)

    profile = relationship(
        "PlatformProfile",
        back_populates="contest_participations",
    )

    contest = relationship(
        "Contest",
        back_populates="participations",
    )