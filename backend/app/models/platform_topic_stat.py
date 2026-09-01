from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PlatformTopicStat(Base, TimestampMixin):
    __tablename__ = "platform_topic_stats"

    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "topic_slug",
            name="uq_profile_topic_stat",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("platform_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    topic_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    topic_slug: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    solved_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    profile = relationship(
        "PlatformProfile",
        back_populates="topic_stats",
    )