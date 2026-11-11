"""Scored candidate ranking for AI Coach problem recommendations.

Replaces the old ``acceptance_rate DESC`` ordering with an explicit,
documented scoring function. Every weight is a named constant below and
each scoring term is documented next to its weight.

Scoring terms (all in [0, 1] unless noted):

- ``topic_fit``      — how weak the problem's topics are for THIS user,
                       measured by per-topic solved_count relative to the
                       user's own distribution (not just the
                       strong/moderate/weak label).
- ``difficulty_fit`` — proximity to the user's target difficulty, derived
                       from the same solved-count bands the eval harness
                       uses (<20 → Easy, 20-99 → Easy+Medium, 100+ → all).
- ``staleness``      — bonus for topics the user has not submitted to in
                       30+ days (or ever).
- ``solvability``    — small prior from the problem's acceptance_rate so
                       roughly-equal candidates prefer more-solvable ones.
- ``recent_failure`` — PENALTY (subtracted) for problems the user attempted
                       but did not solve recently. They stay eligible;
                       recency of the last failed attempt scales the penalty.

A greedy diversity pass then selects the final shortlist so the top N does
not collapse onto a single topic.

Security contract (inherited from agent_tools):
  - ``user_id`` is always the authenticated user's ID, supplied by the
    caller — never from model output.
  - All queries are scoped by that user_id.
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models.enums import Difficulty, Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
from app.services.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scoring weights — named constants, each term documented
# ---------------------------------------------------------------------------

# Weak-topic fit: dominant term. Rewards problems tagged with topics the
# user has solved relatively few of compared to their own per-topic
# distribution. Range [0, 1].
W_TOPIC_FIT = 0.70

# Difficulty fit: prefers problems at (or just below) the user's target
# difficulty band. Range [0, 1].
W_DIFFICULTY_FIT = 0.20

# Staleness: rewards topics with no submissions in STALE_TOPIC_DAYS+ days.
# Range [0, 1].
W_STALENESS = 0.15

# Solvability: small acceptance_rate prior so ties break toward problems
# more users solve. Range [0, 1].
W_SOLVABILITY = 0.10

# Recent-failure penalty: SUBTRACTED from the score for problems the user
# attempted but did not solve. Scaled by how recent the last attempt was:
#   <= RECENT_FAILURE_FULL_DAYS  → full penalty
#   <= RECENT_FAILURE_PARTIAL_DAYS → half penalty
#   older / never attempted      → no penalty
# The problem remains eligible — this only re-orders it.
W_RECENT_FAILURE_PENALTY = 0.15

# Diversity pass: during greedy selection, a candidate's effective score is
# reduced by DIVERSITY_PENALTY times the fraction of its topics that have
# already been selected (capped count > 0). A problem whose tags are all
# fresh pays nothing; a single-topic problem repeating a picked topic pays
# the full penalty; a 3-topic problem repeating one tag pays only a third —
# it still adds two new topics. Prevents the shortlist collapsing onto one
# topic without punishing broadly-tagged problems.
DIVERSITY_PENALTY = 0.3

# Within the topic-fit term, how much the coarse strength label
# (weak/moderate/insufficient_data/strong from PerformanceAnalyzer) counts
# versus the raw relative solved_count deficiency. The label captures "is
# this area actually under-practised for this user"; the deficiency keeps
# finer gradation inside each band so this is not *only* the label.
LABEL_FIT_WEIGHT = 0.6
RELATIVE_FIT_WEIGHT = 0.4

# Thresholds
STALE_TOPIC_DAYS = 30
RECENT_FAILURE_FULL_DAYS = 7
RECENT_FAILURE_PARTIAL_DAYS = 30

# Safety cap on the candidate pool scored per call.
CANDIDATE_POOL_LIMIT = 500

# Difficulty bands — same level notion as evals/metrics.allowed_difficulties
# (solved < 20 → Easy only; 20-99 → Easy+Medium; 100+ → all). Duplicated here
# so production code does not import the eval package.
BAND_EASY_ONLY_MAX_SOLVED = 20
BAND_INTERMEDIATE_MAX_SOLVED = 100

_DIFFICULTY_ORDER = {Difficulty.EASY: 0, Difficulty.MEDIUM: 1, Difficulty.HARD: 2}


# ---------------------------------------------------------------------------
# User context
# ---------------------------------------------------------------------------


@dataclass
class UserRankingContext:
    """Precomputed per-user signals used by the scorer.

    All maps are keyed by normalised topic name (lowercase, collapsed
    whitespace) unless noted otherwise.
    """

    solved_count: int = 0
    # topic name → distinct solved problems in that topic (PerformanceAnalyzer).
    topic_solved: dict[str, int] = field(default_factory=dict)
    # topic name → PerformanceAnalyzer strength_level
    # ("strong"/"moderate"/"weak"/"insufficient_data").
    topic_strength: dict[str, str] = field(default_factory=dict)
    # topic name → most recent submission timestamp (ANY status).
    topic_last_submission: dict[str, datetime] = field(default_factory=dict)
    # problem_id → most recent NON-accepted submission timestamp, for
    # problems the user attempted but never solved.
    problem_last_failed_attempt: dict[int, datetime] = field(default_factory=dict)
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def max_topic_solved(self) -> int:
        return max(self.topic_solved.values(), default=0)


def _norm_topic(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _norm_datetime(value: Optional[datetime]) -> Optional[datetime]:
    """Normalise datetimes to UTC-aware for safe subtraction."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def build_user_context(
    db: Session,
    user_id: int,
    solved_ids: set[int],
    attempted_unsolved_ids: set[int],
) -> UserRankingContext:
    """Gather the per-user signals the ranker needs.

    Args:
        db: SQLAlchemy session.
        user_id: Authenticated user's ID (never from model output).
        solved_ids: Problem IDs with an ACCEPTED submission (from
            agent_tools.get_solved_problem_ids).
        attempted_unsolved_ids: Problem IDs attempted but not solved.

    Returns:
        UserRankingContext with topic solved counts (via
        PerformanceAnalyzer, the same source get_topic_performance uses),
        per-topic last-submission times, and per-problem last failed-attempt
        times.
    """
    ctx = UserRankingContext(solved_count=len(solved_ids))

    # --- Per-topic solved counts via PerformanceAnalyzer -------------------
    try:
        profile = PerformanceAnalyzer(db).analyze_user_performance(user_id)
        for t in profile.topic_performance:
            key = _norm_topic(t.topic)
            ctx.topic_solved[key] = int(t.solved_count)
            ctx.topic_strength[key] = str(t.strength_level)
    except Exception as exc:  # ranking must never break the tool
        logger.warning(
            "candidate_ranker: topic performance failed user_id=%d: %s",
            user_id, exc,
        )

    profile_ids = select(PlatformProfile.id).where(
        PlatformProfile.user_id == user_id
    )

    # --- Last submission (any status) per topic -----------------------------
    topic_last_rows = (
        db.query(Topic.name, func.max(Submission.submitted_at))
        .join(ProblemTopic, ProblemTopic.topic_id == Topic.id)
        .join(Submission, Submission.problem_id == ProblemTopic.problem_id)
        .filter(Submission.profile_id.in_(profile_ids))
        .group_by(Topic.name)
        .all()
    )
    for name, last_at in topic_last_rows:
        ctx.topic_last_submission[_norm_topic(name)] = _norm_datetime(last_at)

    # --- Last failed attempt per attempted-but-unsolved problem ------------
    if attempted_unsolved_ids:
        rows = (
            db.query(
                Submission.problem_id,
                func.max(Submission.submitted_at),
            )
            .filter(
                Submission.profile_id.in_(profile_ids),
                Submission.problem_id.in_(attempted_unsolved_ids),
                Submission.status != SubmissionStatus.ACCEPTED,
            )
            .group_by(Submission.problem_id)
            .all()
        )
        for problem_id, last_at in rows:
            ctx.problem_last_failed_attempt[problem_id] = _norm_datetime(last_at)

    return ctx


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def allowed_difficulty_band(solved_count: int) -> set[Difficulty]:
    """Difficulty band for a user with ``solved_count`` distinct solves.

    Mirrors evals.metrics.allowed_difficulties:
        < 20  → {Easy}
        20-99 → {Easy, Medium}
        100+  → {Easy, Medium, Hard}
    """
    if solved_count < BAND_EASY_ONLY_MAX_SOLVED:
        return {Difficulty.EASY}
    if solved_count < BAND_INTERMEDIATE_MAX_SOLVED:
        return {Difficulty.EASY, Difficulty.MEDIUM}
    return {Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD}


def target_difficulty(solved_count: int) -> Difficulty:
    """The difficulty the ranker aims for: the top of the user's reliable
    band ('slightly above' what they already solve consistently)."""
    if solved_count < BAND_EASY_ONLY_MAX_SOLVED:
        return Difficulty.EASY
    if solved_count < BAND_INTERMEDIATE_MAX_SOLVED:
        return Difficulty.MEDIUM
    return Difficulty.HARD


def _difficulty_enum(value) -> Optional[Difficulty]:
    if value is None:
        return None
    if isinstance(value, Difficulty):
        return value
    try:
        return Difficulty(str(value))
    except ValueError:
        return None


def _topic_deficiency(topic_name: str, ctx: UserRankingContext) -> float:
    """Weakness of one topic relative to the user's own distribution.

    ``1 - solved_t / (max_solved + 1)``: a topic the user has never solved
    scores ~1.0 (when anyone has solves), their most-solved topic scores
    near 0, and everything else interpolates. Topics absent from the user's
    profile count as solved_t = 0.
    """
    solved_t = ctx.topic_solved.get(_norm_topic(topic_name), 0)
    denom = ctx.max_topic_solved + 1
    return max(0.0, min(1.0, 1.0 - solved_t / denom))


# Strength-label → base fit. Mirrors the weak/moderate focus notion the
# agent already uses, but blended with the relative deficiency below so the
# term is driven by solved_count, not the label alone.
_STRENGTH_BASE = {
    "weak": 1.0,
    "moderate": 0.8,
    "insufficient_data": 0.35,  # barely/never touched — unknown, not proven weak
    "strong": 0.10,
}
_UNKNOWN_TOPIC_BASE = 0.35  # topic absent from the user's profile entirely


def _topic_fit_value(topic_name: str, ctx: UserRankingContext) -> float:
    """Fit of one topic: blend of strength label and relative deficiency.

    ``LABEL_FIT_WEIGHT * label_base + RELATIVE_FIT_WEIGHT * deficiency``
    where ``deficiency = 1 - solved_t / (max_solved + 1)`` measures the
    topic's solved_count against the user's own distribution.
    """
    key = _norm_topic(topic_name)
    label = ctx.topic_strength.get(key)
    base = _STRENGTH_BASE.get(label, _UNKNOWN_TOPIC_BASE) if label else _UNKNOWN_TOPIC_BASE
    deficiency = _topic_deficiency(topic_name, ctx)
    return LABEL_FIT_WEIGHT * base + RELATIVE_FIT_WEIGHT * deficiency


def _score_topic_fit(topics: list[str], ctx: UserRankingContext) -> float:
    """Best (max) per-topic fit across the problem's tags.

    Using the max means a problem tagged [weak, strong] still counts as a
    weak-topic candidate; a problem with no tags scores 0 — it cannot be
    matched to a weak area.
    """
    if not topics:
        return 0.0
    return max(_topic_fit_value(t, ctx) for t in topics)


def _score_difficulty(
    difficulty: Optional[Difficulty],
    ctx: UserRankingContext,
    explicit_difficulty: bool,
) -> float:
    """Proximity to the user's target difficulty.

    When the caller passed an explicit difficulty filter, the SQL query
    already constrains the pool, so every candidate scores 1.0 (constant —
    it cannot affect ordering). Otherwise score by distance from the
    target:

        same as target      → 1.00
        one step below      → 0.75   (safe, reliable)
        two steps below     → 0.50
        one step above      → 0.60   (stretch — allowed but not preferred)
        two steps above     → 0.30
    """
    if explicit_difficulty:
        return 1.0
    if difficulty is None:
        return 0.5  # unknown difficulty: neutral

    target_idx = _DIFFICULTY_ORDER[target_difficulty(ctx.solved_count)]
    diff_idx = _DIFFICULTY_ORDER[difficulty]
    delta = diff_idx - target_idx

    if delta == 0:
        return 1.0
    if delta == -1:
        return 0.75
    if delta == -2:
        return 0.50
    if delta == 1:
        return 0.60
    return 0.30  # delta == -? handled above; delta == 2 → two above


def _score_staleness(topics: list[str], ctx: UserRankingContext) -> float:
    """Bonus for topics with no submissions in STALE_TOPIC_DAYS+ days.

    Per topic: ``min(days_since_last_submission / 30, 1.0)``; a topic never
    submitted to scores 1.0. The problem takes the max across its tags —
    touching one stale area is enough. No tags → 0.0.
    """
    if not topics:
        return 0.0
    best = 0.0
    for t in topics:
        last = ctx.topic_last_submission.get(_norm_topic(t))
        if last is None:
            best = max(best, 1.0)
            continue
        days = max(0.0, (ctx.now - last).total_seconds() / 86400.0)
        best = max(best, min(days / STALE_TOPIC_DAYS, 1.0))
    return best


def _recent_failure_factor(
    problem_id: int, ctx: UserRankingContext
) -> float:
    """Penalty factor in [0, 1] for attempted-but-unsolved problems.

    Explicit rule:
      - last failed attempt <= 7 days ago  → 1.0 (full penalty)
      - last failed attempt <= 30 days ago → 0.5 (half penalty)
      - older than 30 days, or problem never attempted → 0.0
    """
    last = ctx.problem_last_failed_attempt.get(problem_id)
    if last is None:
        return 0.0
    days = max(0.0, (ctx.now - last).total_seconds() / 86400.0)
    if days <= RECENT_FAILURE_FULL_DAYS:
        return 1.0
    if days <= RECENT_FAILURE_PARTIAL_DAYS:
        return 0.5
    return 0.0


def _score_solvability(acceptance_rate) -> float:
    """Small prior from acceptance_rate in [0, 1]; None → 0.5 neutral."""
    if acceptance_rate is None:
        return 0.5
    try:
        return max(0.0, min(1.0, float(acceptance_rate)))
    except (TypeError, ValueError):
        return 0.5


@dataclass
class ScoredCandidate:
    """A candidate problem plus its score and per-term breakdown."""

    problem_id: int
    topics: list[str]
    difficulty: Optional[Difficulty]
    acceptance_rate: float
    score: float
    breakdown: dict[str, float] = field(default_factory=dict)


def score_candidate(
    problem_id: int,
    topics: list[str],
    difficulty: Optional[Difficulty],
    acceptance_rate,
    ctx: UserRankingContext,
    explicit_difficulty: bool = False,
) -> ScoredCandidate:
    """Score one candidate problem. See module docstring for the terms."""
    topic_fit = _score_topic_fit(topics, ctx)
    diff_fit = _score_difficulty(difficulty, ctx, explicit_difficulty)
    staleness = _score_staleness(topics, ctx)
    solvability = _score_solvability(acceptance_rate)
    failure_factor = _recent_failure_factor(problem_id, ctx)

    score = (
        W_TOPIC_FIT * topic_fit
        + W_DIFFICULTY_FIT * diff_fit
        + W_STALENESS * staleness
        + W_SOLVABILITY * solvability
        - W_RECENT_FAILURE_PENALTY * failure_factor
    )

    breakdown = {
        "topic_fit": round(topic_fit, 4),
        "difficulty_fit": round(diff_fit, 4),
        "staleness": round(staleness, 4),
        "solvability": round(solvability, 4),
        "recent_failure_penalty": round(
            W_RECENT_FAILURE_PENALTY * failure_factor, 4
        ),
        "score": round(score, 4),
    }

    return ScoredCandidate(
        problem_id=problem_id,
        topics=list(topics),
        difficulty=difficulty,
        acceptance_rate=acceptance_rate,
        score=score,
        breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# Diversity-aware selection
# ---------------------------------------------------------------------------


def _sort_key(candidate: ScoredCandidate):
    """Deterministic ordering: score desc, then problem_id asc (stable ties)."""
    return (-candidate.score, candidate.problem_id)


def select_diverse(
    candidates: list[ScoredCandidate],
    limit: int,
    topic_counts: Optional[Counter] = None,
) -> tuple[list[ScoredCandidate], Counter]:
    """Greedy diversity selection.

    At each step picks the remaining candidate maximising
    ``score - DIVERSITY_PENALTY * repeated_fraction`` where
    ``repeated_fraction`` is the share of the candidate's topics that
    already appear in ``topic_counts`` (topics selected by earlier picks or
    a previous pass). Candidates with no topics pay no penalty.

    Args:
        candidates: Scored candidates (any order; sorted internally).
        limit: Max number to select.
        topic_counts: Optional Counter of topics already selected by a
            previous pass — used when topping up a topic-filtered search so
            the combined set stays diverse.

    Returns:
        (selected, updated topic_counts)
    """
    counts: Counter = Counter(topic_counts or {})
    remaining = sorted(candidates, key=_sort_key)
    selected: list[ScoredCandidate] = []

    while remaining and len(selected) < limit:
        best_idx = 0
        best_eff = -math.inf
        for i, cand in enumerate(remaining):
            if cand.topics:
                repeated = sum(1 for t in cand.topics if counts[_norm_topic(t)] > 0)
                repeated_fraction = repeated / len(cand.topics)
            else:
                repeated_fraction = 0.0
            eff = cand.score - DIVERSITY_PENALTY * repeated_fraction
            if eff > best_eff:
                best_eff = eff
                best_idx = i

        chosen = remaining.pop(best_idx)
        selected.append(chosen)
        for t in chosen.topics:
            counts[_norm_topic(t)] += 1

    return selected, counts
