from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    full_name: Mapped[str | None] = mapped_column(
        String(100)
    )
    
    country: Mapped[str | None] = mapped_column(
        String(100)
    )

    profile_picture: Mapped[str | None] = mapped_column(
        String(500)
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # ---------------- Relationships ---------------- #

    platform_profiles = relationship(
        "PlatformProfile",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    goals = relationship(
        "Goal",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    achievements = relationship(
        "UserAchievement",
        back_populates="user",
        cascade="all, delete-orphan",
    )