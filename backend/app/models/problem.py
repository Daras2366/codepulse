from sqlalchemy import Enum, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.enums import Platform, Difficulty
from app.models.base import Base, TimestampMixin


class Problem(Base, TimestampMixin):
    __tablename__ = "problems"
    
    __table_args__ = (
        UniqueConstraint(
            "platform",
            "platform_problem_id",
            name="uq_platform_problem",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform),
        nullable=False,
    )

    platform_problem_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )
    
    problem_url: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
    )

    difficulty: Mapped[Difficulty] = mapped_column(
        Enum(Difficulty),
        nullable=False,
    )

    acceptance_rate: Mapped[float | None]

    submissions = relationship(
        "Submission",
        back_populates="problem",
    )

    topics = relationship(
        "ProblemTopic",
        back_populates="problem",
        cascade="all, delete-orphan",
    )