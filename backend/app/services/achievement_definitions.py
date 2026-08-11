"""Achievement definitions catalogue.

These are the seed definitions for the Achievement table.
Each entry maps to one row in the achievements table.

Thresholds are defined here (in code) because the Achievement model does
not have a threshold column — the name acts as the stable identifier.

Supported categories (from AchievementCategory enum):
  PROBLEM, CONTEST, RATING, STREAK, TOPIC, SPECIAL

Only PROBLEM, CONTEST, and RATING are calculable from the current DB.
STREAK, TOPIC, and SPECIAL require data not yet available.
"""

from dataclasses import dataclass
from typing import Callable

from app.models.enums import AchievementCategory


@dataclass(frozen=True)
class AchievementDefinition:
    name: str
    description: str
    category: AchievementCategory
    icon: str | None
    # Callable(metrics_dict) -> bool
    condition: Callable[[dict], bool]


# ---------------------------------------------------------------------------
# Problem-solving achievements
# ---------------------------------------------------------------------------

PROBLEM_ACHIEVEMENTS: list[AchievementDefinition] = [
    AchievementDefinition(
        name="First Blood",
        description="Solve your first problem.",
        category=AchievementCategory.PROBLEM,
        icon="🩸",
        condition=lambda m: m["solved_problems"] >= 1,
    ),
    AchievementDefinition(
        name="Problem Solver",
        description="Solve 10 problems.",
        category=AchievementCategory.PROBLEM,
        icon="⚡",
        condition=lambda m: m["solved_problems"] >= 10,
    ),
    AchievementDefinition(
        name="Centurion",
        description="Solve 100 problems.",
        category=AchievementCategory.PROBLEM,
        icon="💯",
        condition=lambda m: m["solved_problems"] >= 100,
    ),
    AchievementDefinition(
        name="Problem Master",
        description="Solve 250 problems.",
        category=AchievementCategory.PROBLEM,
        icon="🏅",
        condition=lambda m: m["solved_problems"] >= 250,
    ),
    AchievementDefinition(
        name="Elite Solver",
        description="Solve 500 problems.",
        category=AchievementCategory.PROBLEM,
        icon="🏆",
        condition=lambda m: m["solved_problems"] >= 500,
    ),
]

# ---------------------------------------------------------------------------
# Submission achievements
# ---------------------------------------------------------------------------

SUBMISSION_ACHIEVEMENTS: list[AchievementDefinition] = [
    AchievementDefinition(
        name="First Submission",
        description="Submit your first solution.",
        category=AchievementCategory.PROBLEM,
        icon="📤",
        condition=lambda m: m["total_submissions"] >= 1,
    ),
    AchievementDefinition(
        name="Persistent",
        description="Make 50 submissions.",
        category=AchievementCategory.PROBLEM,
        icon="🔄",
        condition=lambda m: m["total_submissions"] >= 50,
    ),
    AchievementDefinition(
        name="Dedicated",
        description="Make 200 submissions.",
        category=AchievementCategory.PROBLEM,
        icon="📚",
        condition=lambda m: m["total_submissions"] >= 200,
    ),
]

# ---------------------------------------------------------------------------
# Contest achievements
# ---------------------------------------------------------------------------

CONTEST_ACHIEVEMENTS: list[AchievementDefinition] = [
    AchievementDefinition(
        name="Contest Debut",
        description="Participate in your first contest.",
        category=AchievementCategory.CONTEST,
        icon="🎯",
        condition=lambda m: m["contests_attended"] >= 1,
    ),
    AchievementDefinition(
        name="Regular Contestant",
        description="Participate in 10 contests.",
        category=AchievementCategory.CONTEST,
        icon="🎖️",
        condition=lambda m: m["contests_attended"] >= 10,
    ),
    AchievementDefinition(
        name="Contest Veteran",
        description="Participate in 50 contests.",
        category=AchievementCategory.CONTEST,
        icon="🎗️",
        condition=lambda m: m["contests_attended"] >= 50,
    ),
]

# ---------------------------------------------------------------------------
# Rating achievements
# ---------------------------------------------------------------------------

RATING_ACHIEVEMENTS: list[AchievementDefinition] = [
    AchievementDefinition(
        name="Rated Player",
        description="Achieve a rating of 1000 or above.",
        category=AchievementCategory.RATING,
        icon="⭐",
        condition=lambda m: m["max_rating"] >= 1000,
    ),
    AchievementDefinition(
        name="Rising Star",
        description="Achieve a rating of 1200 or above.",
        category=AchievementCategory.RATING,
        icon="🌟",
        condition=lambda m: m["max_rating"] >= 1200,
    ),
    AchievementDefinition(
        name="Expert",
        description="Achieve a rating of 1600 or above.",
        category=AchievementCategory.RATING,
        icon="💎",
        condition=lambda m: m["max_rating"] >= 1600,
    ),
    AchievementDefinition(
        name="Candidate Master",
        description="Achieve a rating of 1900 or above.",
        category=AchievementCategory.RATING,
        icon="🔮",
        condition=lambda m: m["max_rating"] >= 1900,
    ),
    AchievementDefinition(
        name="Master",
        description="Achieve a rating of 2100 or above.",
        category=AchievementCategory.RATING,
        icon="👑",
        condition=lambda m: m["max_rating"] >= 2100,
    ),
    AchievementDefinition(
        name="Grandmaster",
        description="Achieve a rating of 2400 or above.",
        category=AchievementCategory.RATING,
        icon="🌌",
        condition=lambda m: m["max_rating"] >= 2400,
    ),
]

# ---------------------------------------------------------------------------
# All definitions (ordered for consistent seeding)
# ---------------------------------------------------------------------------

ALL_ACHIEVEMENT_DEFINITIONS: list[AchievementDefinition] = (
    PROBLEM_ACHIEVEMENTS
    + SUBMISSION_ACHIEVEMENTS
    + CONTEST_ACHIEVEMENTS
    + RATING_ACHIEVEMENTS
)
