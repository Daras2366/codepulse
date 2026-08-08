from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ProblemTopic(Base):
    __tablename__ = "problem_topics"

    __table_args__ = (
        UniqueConstraint(
            "problem_id",
            "topic_id",
            name="uq_problem_topic",
        ),
    )

    problem_id: Mapped[int] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"),
        primary_key=True,
    )

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"),
        primary_key=True,
    )

    problem = relationship(
        "Problem",
        back_populates="topics",
    )

    topic = relationship(
        "Topic",
        back_populates="problems",
    )