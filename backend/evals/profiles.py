"""Synthetic profile and problem-catalog seeding for AI Coach evaluations.

Builds an in-memory SQLite database using the real SQLAlchemy models so the
existing services (agent_tools, PerformanceAnalyzer, RecommendationAgent)
run unmodified against realistic data.

Determinism: all randomness flows through ``random.Random(SEED)`` — runs are
reproducible.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registers all ORM models
from app.models.base import Base
from app.models.enums import (
    Difficulty,
    GoalStatus,
    GoalType,
    Platform,
    SubmissionStatus,
)
from app.models.goal import Goal
from app.models.platform_profile import PlatformProfile
from app.models.platform_topic_stat import PlatformTopicStat
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
from app.models.user import User

SEED = 20261110
CATALOG_SIZE = 330

TOPIC_NAMES = [
    "Arrays",
    "Strings",
    "Hash Table",
    "Two Pointers",
    "Binary Search",
    "Sorting",
    "Prefix Sums",
    "Sliding Window",
    "Greedy",
    "Dynamic Programming",
    "Graphs",
    "Trees",
    "DFS and BFS",
    "Backtracking",
    "Math",
    "Number Theory",
    "Bit Manipulation",
    "Stack",
    "Heap",
    "Trie",
    "Union Find",
    "Simulation",
]

DIFFICULTY_WEIGHTS = [
    (Difficulty.EASY, 0.40),
    (Difficulty.MEDIUM, 0.40),
    (Difficulty.HARD, 0.20),
]

PLATFORMS = [Platform.LEETCODE, Platform.CODEFORCES]
# ~40% LeetCode, ~60% Codeforces
PLATFORM_WEIGHTS = [0.40, 0.60]


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def _weighted_choice(rng: random.Random, items, weights) -> object:
    return rng.choices(items, weights=weights, k=1)[0]


def _weighted_sample_without_replacement(
    rng: random.Random, items: list, weights: list[float], n: int
) -> list:
    """Weighted sampling without replacement via exponential race keys.

    Each item gets key = -ln(u) / weight; the n smallest keys win. Higher
    weight ⇒ earlier (more likely) selection. Deterministic under SEED.
    """
    import math

    keyed = []
    for item, w in zip(items, weights):
        u = max(rng.random(), 1e-12)
        keyed.append((-math.log(u) / max(w, 1e-6), item))
    keyed.sort(key=lambda kv: kv[0])
    return [item for _, item in keyed[:n]]


@dataclass
class EvalProfile:
    """A synthetic user plus the ground truth needed to score recommendations."""

    name: str
    user_id: int
    solved_ids: set[int] = field(default_factory=set)
    attempted_unsolved_ids: set[int] = field(default_factory=set)
    platforms: list[str] = field(default_factory=list)
    last_active_days_ago: int = 0
    has_goal: bool = False


@dataclass
class ProfileSpec:
    """Declarative description of one synthetic user."""

    name: str
    platforms: list[Platform]
    n_solved: int
    # topic name → sampling weight. Strong topics get high weight, weak low.
    strong_topics: list[str] = field(default_factory=list)
    weak_topics: list[str] = field(default_factory=list)
    activity_days: int = 60          # submissions spread over this many days
    days_since_last: int = 0         # inactivity gap before "today"
    n_attempts_unsolved: int = 0     # wrong-answer attempts on unsolved problems
    extra_submissions: int = 0       # extra non-accepted attempts on solved problems
    goal_topic: Optional[str] = None
    goal_target: int = 20
    goal_days_left: int = 14


# ---------------------------------------------------------------------------
# Profile catalogue — covers the required archetypes
# ---------------------------------------------------------------------------

PROFILE_SPECS: list[ProfileSpec] = [
    # --- Beginners ---------------------------------------------------------
    ProfileSpec("beginner_cf", [Platform.CODEFORCES], 8,
                strong_topics=["Arrays", "Math"], weak_topics=["Graphs"],
                activity_days=14),
    ProfileSpec("beginner_lc", [Platform.LEETCODE], 12,
                strong_topics=["Arrays", "Hash Table"], weak_topics=["Dynamic Programming"],
                activity_days=21),
    ProfileSpec("newcomer_barely", [Platform.CODEFORCES], 3,
                strong_topics=["Math"], activity_days=5),

    # --- Topic strength / weakness ----------------------------------------
    ProfileSpec("strong_dp_weak_graphs", PLATFORMS, 120,
                strong_topics=["Dynamic Programming"],
                weak_topics=["Graphs", "Trees"],
                activity_days=90),
    ProfileSpec("strong_graphs_weak_dp", PLATFORMS, 110,
                strong_topics=["Graphs", "DFS and BFS"],
                weak_topics=["Dynamic Programming"],
                activity_days=90),
    ProfileSpec("all_round_strong", PLATFORMS, 200,
                strong_topics=[TOPIC_NAMES[0], TOPIC_NAMES[5], TOPIC_NAMES[8]],
                activity_days=120),
    ProfileSpec("dual_weak_topics", [Platform.CODEFORCES], 80,
                strong_topics=["Arrays", "Sorting"],
                weak_topics=["Greedy", "Number Theory"],
                activity_days=60),
    ProfileSpec("hard_heavy", PLATFORMS, 90,
                strong_topics=["Dynamic Programming", "Graphs"],
                weak_topics=["Strings"],
                activity_days=80),
    ProfileSpec("easy_only", [Platform.LEETCODE], 30,
                strong_topics=["Arrays", "Strings"],
                weak_topics=["Binary Search", "Heap"],
                activity_days=40),
    ProfileSpec("medium_focus", [Platform.CODEFORCES], 55,
                strong_topics=["Binary Search", "Greedy"],
                weak_topics=["Graphs"],
                activity_days=50),

    # --- Platform coverage -------------------------------------------------
    ProfileSpec("cf_only_intermediate", [Platform.CODEFORCES], 60,
                strong_topics=["Math", "Greedy"], weak_topics=["Trees"],
                activity_days=45),
    ProfileSpec("lc_only_intermediate", [Platform.LEETCODE], 70,
                strong_topics=["Arrays", "Strings"], weak_topics=["Graphs"],
                activity_days=55),
    ProfileSpec("both_platforms_balanced", PLATFORMS, 95,
                strong_topics=["Arrays", "Dynamic Programming"],
                weak_topics=["Number Theory"],
                activity_days=70),

    # --- Activity patterns -------------------------------------------------
    ProfileSpec("inactive_60d", [Platform.CODEFORCES], 60,
                strong_topics=["Math"], weak_topics=["Graphs"],
                activity_days=30, days_since_last=75),
    ProfileSpec("inactive_90d_lc", [Platform.LEETCODE], 45,
                strong_topics=["Arrays"], weak_topics=["Heap"],
                activity_days=20, days_since_last=95),
    ProfileSpec("streak_user", PLATFORMS, 40,
                strong_topics=["Arrays", "Strings"], weak_topics=["Greedy"],
                activity_days=30, days_since_last=0),
    ProfileSpec("sporadic", [Platform.CODEFORCES], 50,
                strong_topics=["Sorting", "Math"], weak_topics=["Trie"],
                activity_days=10, days_since_last=20),
    ProfileSpec("low_acceptance", [Platform.CODEFORCES], 35,
                strong_topics=["Arrays"], weak_topics=["Graphs", "Dynamic Programming"],
                activity_days=60, extra_submissions=60),

    # --- Special cases -----------------------------------------------------
    ProfileSpec("many_attempts_unsolved", PLATFORMS, 40,
                strong_topics=["Arrays", "Math"], weak_topics=["Graphs"],
                activity_days=50, n_attempts_unsolved=35),
    ProfileSpec("sparse_topic_tags", [Platform.CODEFORCES], 65,
                strong_topics=["Math"], weak_topics=["Graphs"],
                activity_days=40),
    ProfileSpec("goal_topic_user", PLATFORMS, 50,
                strong_topics=["Arrays"], weak_topics=["Dynamic Programming"],
                activity_days=45, goal_topic="Dynamic Programming"),
    ProfileSpec("veteran", PLATFORMS, 300,
                strong_topics=["Dynamic Programming", "Graphs", "Math"],
                weak_topics=["Trie", "Heap"],
                activity_days=180),
    ProfileSpec("rating_climber", PLATFORMS, 75,
                strong_topics=["Binary Search", "Greedy"], weak_topics=["Trees"],
                activity_days=60),
]

LANGUAGES = ["Python3", "C++17", "Java", "PyPy 3"]


def _topic_weights_for(spec: ProfileSpec) -> dict[str, float]:
    weights = {name: 1.0 for name in TOPIC_NAMES}
    for t in spec.strong_topics:
        weights[t] = 12.0
    for t in spec.weak_topics:
        weights[t] = 1.8
    return weights


def _problem_weight(problem: Problem, topic_weights: dict[str, float],
                    problem_topics: dict[int, list[str]]) -> float:
    """Sampling weight for a problem = max weight among its topics."""
    topics = problem_topics.get(problem.id, [])
    if not topics:
        return 0.5
    return max(topic_weights.get(t, 1.0) for t in topics)


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def create_eval_engine():
    """Create an in-memory SQLite engine with all tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


def seed_catalog(db: Session, rng: random.Random) -> tuple[list[Problem], dict[int, list[str]]]:
    """Seed topics and >=300 catalog problems. Returns (problems, problem_id→topics)."""
    topics = [Topic(name=name) for name in TOPIC_NAMES]
    db.add_all(topics)
    db.flush()
    topic_by_name = {t.name: t for t in topics}

    problems: list[Problem] = []
    problem_topics: dict[int, list[str]] = {}

    diff_items = [d for d, _ in DIFFICULTY_WEIGHTS]
    diff_weights = [w for _, w in DIFFICULTY_WEIGHTS]

    for i in range(CATALOG_SIZE):
        platform = _weighted_choice(rng, PLATFORMS, PLATFORM_WEIGHTS)
        difficulty = _weighted_choice(rng, diff_items, diff_weights)
        n_topics = rng.choice([1, 2, 2, 3])
        chosen = rng.sample(TOPIC_NAMES, n_topics)

        pid = f"{platform.value}-{i:04d}"
        problem = Problem(
            platform=platform,
            platform_problem_id=pid,
            title=f"{chosen[0]} Challenge {i}",
            slug=f"{platform.value}-{i}",
            problem_url=f"https://example.com/{platform.value}/problem/{i}",
            difficulty=difficulty,
            acceptance_rate=round(rng.uniform(0.05, 0.95), 3),
        )
        db.add(problem)
        problems.append(problem)
        problem_topics[i] = chosen  # keyed by index until flush assigns ids

    db.flush()

    # problem_topics was keyed by enumeration index == problems list order;
    # rebuild keyed by real id after flush.
    id_topics: dict[int, list[str]] = {}
    for idx, problem in enumerate(problems):
        names = problem_topics[idx]
        id_topics[problem.id] = names
        for name in names:
            db.add(ProblemTopic(problem_id=problem.id, topic_id=topic_by_name[name].id))

    db.commit()
    return problems, id_topics


def seed_profiles(
    db: Session, rng: random.Random
) -> tuple[list[EvalProfile], list[Problem], dict[int, list[str]]]:
    """Seed the catalog plus all synthetic users. Returns (profiles, problems, problem_topics)."""
    problems, problem_topics = seed_catalog(db, rng)
    now = datetime.now(timezone.utc)

    # Index problems by platform for per-profile pools.
    by_platform: dict[Platform, list[Problem]] = {p: [] for p in PLATFORMS}
    for prob in problems:
        by_platform[prob.platform].append(prob)

    eval_profiles: list[EvalProfile] = []

    for spec in PROFILE_SPECS:
        eval_attempted_ids: set[int] = set()
        user = User(
            username=f"eval_{spec.name}",
            email=f"eval_{spec.name}@example.com",
            password_hash="eval",
            is_active=True,
        )
        db.add(user)
        db.flush()

        # Pool of catalog problems on the user's platforms.
        pool: list[Problem] = []
        for plat in spec.platforms:
            pool.extend(by_platform[plat])
        topic_weights = _topic_weights_for(spec)
        weights = [_problem_weight(p, topic_weights, problem_topics) for p in pool]

        n_solved = min(spec.n_solved, len(pool))
        solved_problems = _weighted_sample_without_replacement(
            rng, pool, weights, n_solved
        )
        solved_ids = {p.id for p in solved_problems}

        # Activity window: submissions spread over activity_days ending
        # days_since_last ago.
        window_start = now - timedelta(days=spec.days_since_last + spec.activity_days)
        window_end = now - timedelta(days=spec.days_since_last)
        span = max((window_end - window_start).total_seconds(), 1.0)

        for plat in spec.platforms:
            profile = PlatformProfile(
                user_id=user.id,
                platform=plat,
                username=f"{plat.value}_{spec.name}",
                current_rating=rng.choice([1200, 1400, 1600, 1800, 2000]),
                max_rating=2100,
                problems_solved=0,  # set after plat_solved is known
            )
            db.add(profile)
            db.flush()

            # Distribute solved submissions across the user's profiles on
            # this platform only.
            plat_solved = [p for p in solved_problems if p.platform == plat]
            profile.problems_solved = len(plat_solved)
            for j, prob in enumerate(plat_solved):
                offset = rng.random() * span
                submitted = window_start + timedelta(seconds=offset)
                db.add(
                    Submission(
                        profile_id=profile.id,
                        problem_id=prob.id,
                        submitted_at=submitted,
                        language=rng.choice(LANGUAGES),
                        status=SubmissionStatus.ACCEPTED,
                        platform_submission_id=f"{spec.name}-{plat.value}-{j}",
                    )
                )
                # A few extra failed attempts on already-solved problems.
                if spec.extra_submissions and rng.random() < 0.3:
                    db.add(
                        Submission(
                            profile_id=profile.id,
                            problem_id=prob.id,
                            submitted_at=submitted + timedelta(minutes=5),
                            language=rng.choice(LANGUAGES),
                            status=rng.choice(
                                [
                                    SubmissionStatus.WRONG_ANSWER,
                                    SubmissionStatus.TIME_LIMIT,
                                    SubmissionStatus.RUNTIME_ERROR,
                                ]
                            ),
                            platform_submission_id=f"{spec.name}-{plat.value}-{j}-x",
                        )
                    )

            # Wrong-answer attempts on problems the user has NOT solved.
            unsolved_pool = [p for p in by_platform[plat] if p.id not in solved_ids]
            for prob in rng.sample(
                unsolved_pool, min(spec.n_attempts_unsolved, len(unsolved_pool))
            ):
                offset = rng.random() * span
                db.add(
                    Submission(
                        profile_id=profile.id,
                        problem_id=prob.id,
                        submitted_at=window_start + timedelta(seconds=offset),
                        language=rng.choice(LANGUAGES),
                        status=rng.choice(
                            [
                                SubmissionStatus.WRONG_ANSWER,
                                SubmissionStatus.TIME_LIMIT,
                                SubmissionStatus.RUNTIME_ERROR,
                            ]
                        ),
                        platform_submission_id=f"{spec.name}-{plat.value}-u{prob.id}",
                    )
                )
                eval_attempted_ids.add(prob.id)

            # LeetCode topic stats (PerformanceAnalyzer reads these for LC).
            if plat == Platform.LEETCODE:
                topic_counts: dict[str, int] = {}
                for prob in plat_solved:
                    for name in problem_topics.get(prob.id, []):
                        topic_counts[name] = topic_counts.get(name, 0) + 1
                for name, count in topic_counts.items():
                    db.add(
                        PlatformTopicStat(
                            profile_id=profile.id,
                            topic_name=name,
                            topic_slug=_slug(name),
                            solved_count=count,
                        )
                    )

        # Active topic goal.
        if spec.goal_topic:
            db.add(
                Goal(
                    user_id=user.id,
                    title=f"Master {spec.goal_topic}",
                    goal_type=GoalType.TOPIC,
                    topic_name=spec.goal_topic,
                    topic_slug=_slug(spec.goal_topic),
                    target_value=spec.goal_target,
                    deadline=(now + timedelta(days=spec.goal_days_left)).date(),
                    status=GoalStatus.ACTIVE,
                )
            )

        eval_profiles.append(
            EvalProfile(
                name=spec.name,
                user_id=user.id,
                solved_ids=solved_ids,
                attempted_unsolved_ids=eval_attempted_ids,
                platforms=[p.value for p in spec.platforms],
                last_active_days_ago=spec.days_since_last,
                has_goal=spec.goal_topic is not None,
            )
        )

    db.commit()
    return eval_profiles, problems, problem_topics


def seed_eval_db() -> tuple[Session, list[EvalProfile], list[Problem], dict[int, list[str]]]:
    """Convenience: engine + session + fully seeded eval world."""
    engine = create_eval_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    rng = random.Random(SEED)
    profiles, problems, problem_topics = seed_profiles(db, rng)
    return db, profiles, problems, problem_topics
