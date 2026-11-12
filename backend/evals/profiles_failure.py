"""Failure-pattern synthetic profiles for AI Coach evaluations (Stage 3).

These profiles are seeded IN ADDITION to the 22 baseline profiles in
``evals.profiles`` — they never modify them. They exist to exercise the
Stage 3 failure-pattern tools (get_failure_patterns,
get_attempts_before_accept, get_stale_topics) with clearly distinct,
deliberate failure signatures:

- ``failure_tle_graphs``    — heavy TIME_LIMIT/RUNTIME_ERROR failures on
  Graphs problems; clean solves elsewhere.
- ``failure_dp_attempts``   — Dynamic Programming solves that each needed
  many WRONG_ANSWER attempts first, plus never-accepted DP problems.
- ``failure_stale_arrays``  — strong Arrays history, but every Arrays
  submission is 70+ days old while other topics stay fresh.

Verdict granularity note: the Submission model DOES store granular
verdicts (SubmissionStatus: wrong_answer, time_limit_exceeded,
memory_limit_exceeded, runtime_error, compile_error) for both
Codeforces and LeetCode, so these profiles use real verdict distinctions.

Determinism: all randomness flows through ``random.Random(SEED)`` with the
same seed constant as profiles.py — runs are reproducible and independent
of the baseline seeding order (this module is only invoked via
``run_eval --include-failure-profiles``, after the baseline seed commits).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.enums import Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.platform_topic_stat import PlatformTopicStat
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User

from evals.profiles import SEED, EvalProfile, _slug

# Failure verdict pools — weighted to create distinct signatures.
TLE_HEAVY_STATUSES = [
    (SubmissionStatus.TIME_LIMIT, 0.60),
    (SubmissionStatus.WRONG_ANSWER, 0.20),
    (SubmissionStatus.RUNTIME_ERROR, 0.20),
]
WA_HEAVY_STATUSES = [
    (SubmissionStatus.WRONG_ANSWER, 0.85),
    (SubmissionStatus.COMPILE_ERROR, 0.15),
]


def _weighted_choice(rng: random.Random, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def _problems_with_topic(
    problems: list[Problem],
    problem_topics: dict[int, list[str]],
    platform: Platform,
    topic: str,
    exclude: set[int] | None = None,
) -> list[Problem]:
    exclude = exclude or set()
    return [
        p
        for p in problems
        if p.platform == platform
        and p.id not in exclude
        and topic in problem_topics.get(p.id, [])
    ]


def _problems_without_topic(
    problems: list[Problem],
    problem_topics: dict[int, list[str]],
    platform: Platform,
    topic: str,
) -> list[Problem]:
    return [
        p
        for p in problems
        if p.platform == platform and topic not in problem_topics.get(p.id, [])
    ]


def _make_user(db: Session, name: str) -> User:
    user = User(
        username=f"eval_{name}",
        email=f"eval_{name}@example.com",
        password_hash="eval",
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _make_profile(db: Session, user: User, platform: Platform, name: str) -> PlatformProfile:
    profile = PlatformProfile(
        user_id=user.id,
        platform=platform,
        username=f"{platform.value}_{name}",
        current_rating=1600,
        max_rating=1900,
    )
    db.add(profile)
    db.flush()
    return profile


def _add_submission(
    db: Session,
    profile_id: int,
    problem: Problem,
    status: SubmissionStatus,
    when: datetime,
    tag: str,
) -> None:
    db.add(
        Submission(
            profile_id=profile_id,
            problem_id=problem.id,
            submitted_at=when,
            language="Python3",
            status=status,
            platform_submission_id=tag,
        )
    )


def _sample_weighted(
    rng: random.Random, items: list[Problem], weight_fn, n: int
) -> list[Problem]:
    """Weighted sample without replacement (exponential race keys)."""
    import math

    keyed = []
    for p in items:
        w = max(weight_fn(p), 1e-6)
        u = max(rng.random(), 1e-12)
        keyed.append((-math.log(u) / w, p))
    keyed.sort(key=lambda kv: kv[0])
    return [p for _, p in keyed[:n]]


def _seed_failure_tle_graphs(
    db: Session,
    rng: random.Random,
    problems: list[Problem],
    problem_topics: dict[int, list[str]],
    now: datetime,
) -> EvalProfile:
    """CF user: clean solves on non-Graph topics, TLE-heavy Graph failures."""
    name = "failure_tle_graphs"
    platform = Platform.CODEFORCES
    user = _make_user(db, name)
    profile = _make_profile(db, user, platform, name)

    solved_pool = _problems_without_topic(
        problems, problem_topics, platform, "Graphs"
    )
    solved = _sample_weighted(
        rng,
        solved_pool,
        lambda p: 4.0
        if any(t in ("Arrays", "Math") for t in problem_topics.get(p.id, []))
        else 1.0,
        30,
    )
    solved_ids = {p.id for p in solved}

    # Solved submissions spread over the last 30 days.
    for j, prob in enumerate(solved):
        when = now - timedelta(days=rng.uniform(1, 30))
        _add_submission(db, profile.id, prob, SubmissionStatus.ACCEPTED, when, f"{name}-s{j}")

    # Graphs problems: repeated failures, never accepted.
    graph_pool = _problems_with_topic(
        problems, problem_topics, platform, "Graphs", exclude=solved_ids
    )
    failed_graphs = rng.sample(graph_pool, min(8, len(graph_pool)))
    attempted_unsolved: set[int] = set()
    for j, prob in enumerate(failed_graphs):
        n_fail = rng.randint(2, 3)
        for k in range(n_fail):
            status = _weighted_choice(rng, *zip(*TLE_HEAVY_STATUSES))
            when = now - timedelta(days=rng.uniform(1, 30))
            _add_submission(
                db, profile.id, prob, status, when, f"{name}-g{j}-{k}"
            )
        attempted_unsolved.add(prob.id)

    profile.problems_solved = len(solved)
    db.flush()

    return EvalProfile(
        name=name,
        user_id=user.id,
        solved_ids=solved_ids,
        attempted_unsolved_ids=attempted_unsolved,
        platforms=[platform.value],
        last_active_days_ago=0,
    )


def _seed_failure_dp_attempts(
    db: Session,
    rng: random.Random,
    problems: list[Problem],
    problem_topics: dict[int, list[str]],
    now: datetime,
) -> EvalProfile:
    """LC user: DP solves each needing many WA attempts; some DP never solved."""
    name = "failure_dp_attempts"
    platform = Platform.LEETCODE
    user = _make_user(db, name)
    profile = _make_profile(db, user, platform, name)

    solved_pool = [
        p for p in problems if p.platform == platform
    ]
    solved = _sample_weighted(
        rng,
        solved_pool,
        lambda p: 4.0 if "Dynamic Programming" in problem_topics.get(p.id, []) else 1.0,
        25,
    )
    solved_ids = {p.id for p in solved}

    topic_counts: dict[str, int] = {}
    for prob in solved:
        for t in problem_topics.get(prob.id, []):
            topic_counts[t] = topic_counts.get(t, 0) + 1

    attempted_unsolved: set[int] = set()
    for j, prob in enumerate(solved):
        day = now - timedelta(days=rng.uniform(1, 40))
        # Problems tagged DP need many attempts before the accept.
        is_dp = "Dynamic Programming" in problem_topics.get(prob.id, [])
        n_fail = rng.randint(3, 6) if is_dp else rng.randint(0, 1)
        for k in range(n_fail):
            status = _weighted_choice(rng, *zip(*WA_HEAVY_STATUSES))
            _add_submission(
                db,
                profile.id,
                prob,
                status,
                day - timedelta(hours=k + 1),
                f"{name}-s{j}-f{k}",
            )
        _add_submission(
            db, profile.id, prob, SubmissionStatus.ACCEPTED, day, f"{name}-s{j}-ac"
        )

    # Never-accepted DP problems with WA-only histories.
    unsolved_dp = _problems_with_topic(
        problems, problem_topics, platform, "Dynamic Programming", exclude=solved_ids
    )
    for j, prob in enumerate(rng.sample(unsolved_dp, min(6, len(unsolved_dp)))):
        for k in range(rng.randint(1, 3)):
            status = _weighted_choice(rng, *zip(*WA_HEAVY_STATUSES))
            when = now - timedelta(days=rng.uniform(1, 40))
            _add_submission(db, profile.id, prob, status, when, f"{name}-u{j}-{k}")
        attempted_unsolved.add(prob.id)

    # LeetCode topic stats — PerformanceAnalyzer reads these for LC.
    for tname, count in topic_counts.items():
        db.add(
            PlatformTopicStat(
                profile_id=profile.id,
                topic_name=tname,
                topic_slug=_slug(tname),
                solved_count=count,
            )
        )

    profile.problems_solved = len(solved)
    db.flush()

    return EvalProfile(
        name=name,
        user_id=user.id,
        solved_ids=solved_ids,
        attempted_unsolved_ids=attempted_unsolved,
        platforms=[platform.value],
        last_active_days_ago=0,
    )


def _seed_failure_stale_arrays(
    db: Session,
    rng: random.Random,
    problems: list[Problem],
    problem_topics: dict[int, list[str]],
    now: datetime,
) -> EvalProfile:
    """CF user: strong recent Math/Sorting practice, Arrays untouched 70+ days."""
    name = "failure_stale_arrays"
    platform = Platform.CODEFORCES
    user = _make_user(db, name)
    profile = _make_profile(db, user, platform, name)

    arrays_pool = _problems_with_topic(
        problems, problem_topics, platform, "Arrays"
    )
    other_pool = [
        p
        for p in problems
        if p.platform == platform
        and "Arrays" not in problem_topics.get(p.id, [])
    ]

    stale_solved = rng.sample(arrays_pool, min(8, len(arrays_pool)))
    fresh_solved = _sample_weighted(
        rng,
        other_pool,
        lambda p: 3.0
        if any(t in ("Math", "Sorting") for t in problem_topics.get(p.id, []))
        else 1.0,
        22,
    )
    solved = stale_solved + fresh_solved
    solved_ids = {p.id for p in solved}

    # Arrays solves: all activity 70-90 days ago.
    for j, prob in enumerate(stale_solved):
        when = now - timedelta(days=rng.uniform(70, 90))
        _add_submission(db, profile.id, prob, SubmissionStatus.ACCEPTED, when, f"{name}-old{j}")

    # Other solves: recent activity within the last 10 days.
    for j, prob in enumerate(fresh_solved):
        when = now - timedelta(days=rng.uniform(0.5, 10))
        _add_submission(db, profile.id, prob, SubmissionStatus.ACCEPTED, when, f"{name}-new{j}")

    profile.problems_solved = len(solved)
    db.flush()

    return EvalProfile(
        name=name,
        user_id=user.id,
        solved_ids=solved_ids,
        attempted_unsolved_ids=set(),
        platforms=[platform.value],
        last_active_days_ago=0,
    )


def seed_failure_profiles(
    db: Session,
    problems: list[Problem],
    problem_topics: dict[int, list[str]],
) -> list[EvalProfile]:
    """Seed the failure-pattern profiles on top of an already-seeded world.

    Must be called AFTER ``seed_eval_db`` (the catalog and baseline profiles
    must exist first). Uses a fresh ``random.Random(SEED)`` so results are
    deterministic and independent of baseline rng consumption.

    Args:
        db: Session with catalog + baseline profiles already committed.
        problems: Catalog problems returned by ``seed_eval_db``.
        problem_topics: problem_id → topic names mapping.

    Returns:
        List of EvalProfile for the new failure-pattern users.
    """
    rng = random.Random(SEED)
    now = datetime.now(timezone.utc)

    profiles: list[EvalProfile] = []
    for seeder in (
        _seed_failure_tle_graphs,
        _seed_failure_dp_attempts,
        _seed_failure_stale_arrays,
    ):
        profiles.append(seeder(db, rng, problems, problem_topics, now))

    db.commit()
    return profiles
