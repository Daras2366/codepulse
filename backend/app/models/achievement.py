from sqlalchemy import String, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import AchievementCategory


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    icon: Mapped[str | None] = mapped_column(
        String(255)
    )
    
    category: Mapped[AchievementCategory] = mapped_column(
        Enum(AchievementCategory),
        nullable=False,
    )

    users = relationship(
        "UserAchievement",
        back_populates="achievement",
        cascade="all, delete-orphan",
    )