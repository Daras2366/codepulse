"""Achievement service.

Responsibilities:
  1. List / get Achievement catalog (global, no auth needed).
  2. Seed the Achievement catalog from definitions.
  3. List a user's earned UserAchievements (auth-scoped).
  4. Evaluate achievements for a user and grant any newly earned ones.

Architecture:
    router
        → AchievementService
            → AchievementRepository      (catalog CRUD)
            → UserAchievementRepository  (user ↔ achievement join)
            → AchievementEvalRepository  (aggregate metrics)
"""

from sqlalchemy.orm import Session

from app.models.achievement import Achievement
from app.models.user_achievement import UserAchievement
from app.repositories.achievement_eval_repository import AchievementEvalRepository
from app.repositories.achievement_repository import AchievementRepository
from app.repositories.user_achievement_repository import UserAchievementRepository
from app.schemas.user_achievement import AchievementEvalResult
from app.services.achievement_definitions import ALL_ACHIEVEMENT_DEFINITIONS


class AchievementService:
    def __init__(self, db: Session) -> None:
        self._catalog = AchievementRepository(db)
        self._user_achievements = UserAchievementRepository(db)
        self._eval = AchievementEvalRepository(db)

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def get_achievement(self, achievement_id: int) -> Achievement | None:
        return self._catalog.get_by_id(achievement_id)

    def get_achievements(self, skip: int = 0, limit: int = 100) -> list[Achievement]:
        return self._catalog.get_all(skip, limit)

    # ------------------------------------------------------------------
    # User achievements
    # ------------------------------------------------------------------

    def get_user_achievements(self, user_id: int) -> list[UserAchievement]:
        """Return all achievements earned by the given user."""
        return self._user_achievements.get_by_user(user_id)

    def get_user_achievement_by_id(
        self, ua_id: int
    ) -> UserAchievement | None:
        return self._user_achievements.get_by_id(ua_id)

    # ------------------------------------------------------------------
    # Catalog seeding
    # ------------------------------------------------------------------

    def seed_catalog(self) -> int:
        """Insert any missing achievement definitions into the DB.

        Safe to run multiple times — skips already-existing names.
        Returns the count of newly inserted rows.
        """
        inserted = 0
        for defn in ALL_ACHIEVEMENT_DEFINITIONS:
            if self._catalog.get_by_name(defn.name) is None:
                self._catalog.create(
                    Achievement(
                        name=defn.name,
                        description=defn.description,
                        icon=defn.icon,
                        category=defn.category,
                    )
                )
                inserted += 1
        return inserted

    # ------------------------------------------------------------------
    # Achievement evaluation
    # ------------------------------------------------------------------

    def evaluate_for_user(self, user_id: int) -> AchievementEvalResult:
        """Evaluate all achievement conditions for a user and grant new ones.

        Safe to call multiple times — the DB unique constraint and
        UserAchievementRepository.grant() prevent duplicates.

        Returns an AchievementEvalResult with newly granted counts.
        """
        # Collect current user metrics
        metrics = {
            "solved_problems": self._eval.get_solved_problems(user_id),
            "total_submissions": self._eval.get_total_submissions(user_id),
            "contests_attended": self._eval.get_contests_attended(user_id),
            "max_rating": self._eval.get_max_rating(user_id),
        }

        newly_granted: list[str] = []

        for defn in ALL_ACHIEVEMENT_DEFINITIONS:
            if not defn.condition(metrics):
                continue  # threshold not met

            # Look up the achievement row (must exist for grant to work)
            achievement = self._catalog.get_by_name(defn.name)
            if achievement is None:
                # Catalog not yet seeded for this definition; skip silently
                continue

            result = self._user_achievements.grant(user_id, achievement.id)
            if result is not None:
                # grant() returns None when already owned
                newly_granted.append(defn.name)

        return AchievementEvalResult(
            newly_granted=len(newly_granted),
            achievement_names=newly_granted,
        )
