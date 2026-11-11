"""Pure metric functions for scoring AI Coach recommendation sets.

Every function takes plain data (no DB, no I/O) so it is trivially
testable and reusable for both the deterministic candidate search and the
Gemini agent.

A "recommendation" is any mapping with at least:
    problem_id (int | None), title (str), url (str), topics (list[str]),
    difficulty (str | None)

The catalog is ``dict[int, dict]`` keyed by Problem.id with keys:
    title, url, topics (list[str]), difficulty (str | None)
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

# ---------------------------------------------------------------------------
# Difficulty bands
# ---------------------------------------------------------------------------
#
# The "allowed difficulty band" is derived from the user's demonstrated
# level (distinct solved problems). This is an explicit, documented rule —
# not a hidden heuristic:
#
#     solved < 20    → {"Easy"}            (beginners: build fundamentals)
#     20 ≤ solved < 100 → {"Easy", "Medium"} (intermediate: stretch slightly)
#     solved ≥ 100   → {"Easy", "Medium", "Hard"} (advanced: full range)
#
# Rationale: recommending Hard problems to a user with <20 solves has a
# near-zero success probability and pollutes the difficulty_fit metric.

EASY_ONLY_MAX_SOLVED = 20
INTERMEDIATE_MAX_SOLVED = 100


def allowed_difficulties(solved_count: int) -> set[str]:
    """Return the difficulty band allowed for a user with ``solved_count``
    distinct solved problems. See module docstring for the rule."""
    if solved_count < EASY_ONLY_MAX_SOLVED:
        return {"Easy"}
    if solved_count < INTERMEDIATE_MAX_SOLVED:
        return {"Easy", "Medium"}
    return {"Easy", "Medium", "Hard"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm_difficulty(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    # Accept "easy"/"Easy"/"EASY" and numeric CF-style ratings loosely.
    low = v.lower()
    if low in ("easy", "e"):
        return "Easy"
    if low in ("medium", "med", "m"):
        return "Medium"
    if low in ("hard", "h"):
        return "Hard"
    return v


def _norm_topic(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _rec_problem_id(rec: dict) -> Optional[int]:
    pid = rec.get("problem_id")
    if pid is None:
        return None
    try:
        return int(pid)
    except (TypeError, ValueError):
        return None


def _catalog_entry(rec: dict, catalog: dict[int, dict],
                   catalog_by_url: dict[str, int]) -> Optional[dict]:
    """Find the catalog entry for a recommendation.

    Matches by problem_id first, then by URL. Returns the authoritative
    catalog dict or None.
    """
    pid = _rec_problem_id(rec)
    if pid is not None and pid in catalog:
        return catalog[pid]
    url = rec.get("url")
    if url:
        url_id = catalog_by_url.get(str(url))
        if url_id is not None:
            return catalog[url_id]
    return None


def _rec_topics(rec: dict) -> list[str]:
    topics = rec.get("topics") or []
    return [str(t) for t in topics]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def grounding_rate(
    recommendations: Iterable[dict],
    catalog: dict[int, dict],
) -> float:
    """Fraction of recommendations that match a real Problem row.

    A rec is grounded when its problem_id exists in the catalog, or (when
    problem_id is absent/invalid) its URL matches a catalog problem_url.
    When both an id and a title are present and the id matches, the title
    must also match the catalog title — model-invented titles do not count
    as grounded.
    """
    recs = list(recommendations)
    if not recs:
        return 0.0
    catalog_by_url = {entry["url"]: pid for pid, entry in catalog.items()}

    grounded = 0
    for rec in recs:
        entry = _catalog_entry(rec, catalog, catalog_by_url)
        if entry is None:
            continue
        pid = _rec_problem_id(rec)
        title = rec.get("title")
        # If an id matched, verify the title when the model supplied one.
        if pid is not None and pid in catalog and title:
            if str(title).strip() != entry["title"]:
                continue
        grounded += 1
    return grounded / len(recs)


def unsolved_rate(
    recommendations: Iterable[dict],
    catalog: dict[int, dict],
    solved_ids: set[int],
) -> float:
    """Fraction of recommendations the user has NOT already solved.

    Unverifiable recommendations (no catalog match) count as unsolved=0 —
    we cannot prove they are new, so they are conservatively excluded.
    """
    recs = list(recommendations)
    if not recs:
        return 0.0
    catalog_by_url = {entry["url"]: pid for pid, entry in catalog.items()}

    unsolved = 0
    for rec in recs:
        entry = _catalog_entry(rec, catalog, catalog_by_url)
        if entry is None:
            continue
        pid = _rec_problem_id(rec)
        if pid is None:
            url_id = catalog_by_url.get(str(rec.get("url", "")))
            pid = url_id
        if pid is not None and pid not in solved_ids:
            unsolved += 1
    return unsolved / len(recs)


def weak_topic_coverage(
    recommendations: Iterable[dict],
    focus_topics: set[str],
) -> float:
    """Fraction of recommendations touching at least one focus topic.

    ``focus_topics`` should contain the user's weak and moderate topic
    names (any case); matching is case-insensitive and whitespace-normalised.
    An empty focus set yields 0.0 — coverage is meaningless without a
    defined target.
    """
    recs = list(recommendations)
    if not recs or not focus_topics:
        return 0.0
    targets = {_norm_topic(t) for t in focus_topics}

    hits = 0
    for rec in recs:
        rec_topics_norm = {_norm_topic(t) for t in _rec_topics(rec)}
        if rec_topics_norm & targets:
            hits += 1
    return hits / len(recs)


def difficulty_fit(
    recommendations: Iterable[dict],
    allowed: set[str],
) -> float:
    """Fraction of recommendations whose difficulty is inside ``allowed``.

    Recommendations with missing/unrecognised difficulty count as failures
    (conservative — we cannot prove they fit the user's level).
    """
    recs = list(recommendations)
    if not recs:
        return 0.0
    allowed_norm = {_norm_difficulty(d) for d in allowed}

    fits = 0
    for rec in recs:
        d = _norm_difficulty(rec.get("difficulty"))
        if d is not None and d in allowed_norm:
            fits += 1
    return fits / len(recs)


def topic_diversity(recommendations: Iterable[dict]) -> float:
    """Distinct topics across the set / total topic slots.

    1.0 = every topic tag is unique; lower values mean the set is topically
    repetitive. Recommendations with no topics contribute 0 slots.
    """
    recs = list(recommendations)
    all_topics: list[str] = []
    for rec in recs:
        all_topics.extend(_norm_topic(t) for t in _rec_topics(rec))
    if not all_topics:
        return 0.0
    return len(set(all_topics)) / len(all_topics)


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

METRIC_NAMES = [
    "grounding_rate",
    "unsolved_rate",
    "weak_topic_coverage",
    "difficulty_fit",
    "topic_diversity",
]


def compute_metrics(
    recommendations: Iterable[dict],
    *,
    catalog: dict[int, dict],
    solved_ids: set[int],
    focus_topics: set[str],
    allowed: set[str],
) -> dict[str, float]:
    """Compute all five metrics for one recommendation set."""
    recs = list(recommendations)
    return {
        "grounding_rate": grounding_rate(recs, catalog),
        "unsolved_rate": unsolved_rate(recs, catalog, solved_ids),
        "weak_topic_coverage": weak_topic_coverage(recs, focus_topics),
        "difficulty_fit": difficulty_fit(recs, allowed),
        "topic_diversity": topic_diversity(recs),
        "n_recommendations": float(len(recs)),
    }


def mean_metrics(rows: list[dict[str, float]]) -> dict[str, float]:
    """Mean of each metric across rows (ignores n_recommendations)."""
    if not rows:
        return {name: 0.0 for name in METRIC_NAMES}
    return {
        name: sum(row[name] for row in rows) / len(rows)
        for name in METRIC_NAMES
    }
