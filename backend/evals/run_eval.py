"""CLI for the AI Coach offline evaluation harness.

Usage (from backend/):

    python -m evals.run_eval --mode candidates --out evals/results/run.json
    python -m evals.run_eval --mode agent --out evals/results/run.json

Modes:
    candidates — deterministic candidate search in agent_tools only.
                 No LLM calls; always runnable.
    agent      — full RecommendationAgent loop per profile. Requires
                 GEMINI_API_KEY in the environment; calls the real Gemini
                 API (function calling). Records latency, tool calls and
                 token usage when the provider returns it.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from evals.metrics import (
    METRIC_NAMES,
    allowed_difficulties,
    compute_metrics,
    mean_metrics,
)
from evals.profiles import (
    SEED,
    EvalProfile,
    Problem,
    seed_eval_db,
)

logger = logging.getLogger("evals.run_eval")

RESULTS_DIR = Path(__file__).resolve().parent / "results"


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------


def build_catalog_index(
    problems: list[Problem], problem_topics: dict[int, list[str]]
) -> dict[int, dict]:
    """Build the catalog mapping consumed by evals.metrics."""
    catalog: dict[int, dict] = {}
    for p in problems:
        difficulty = p.difficulty
        catalog[p.id] = {
            "title": p.title,
            "url": p.problem_url,
            "topics": list(problem_topics.get(p.id, [])),
            "difficulty": difficulty.value if hasattr(difficulty, "value") else str(difficulty),
        }
    return catalog


def profile_focus_topics(db: Session, user_id: int) -> tuple[set[str], Optional[str]]:
    """Return (weak+moderate topic names, weakest topic name) for a user.

    Uses agent_tools.get_topic_performance → PerformanceAnalyzer, i.e. the
    same topic classification the real agent sees.
    """
    from app.services.agent_tools import get_topic_performance

    topics = get_topic_performance(db, user_id)
    focus: set[str] = set()
    weakest: Optional[str] = None
    for t in topics:
        if t["strength_level"] in ("weak", "moderate"):
            focus.add(t["topic"])
        if weakest is None and t["strength_level"] == "weak":
            weakest = t["topic"]
    if weakest is None:
        for t in topics:
            if t["strength_level"] == "moderate":
                weakest = t["topic"]
                break
    return focus, weakest


def profile_context(
    db: Session, ep: EvalProfile, catalog: dict[int, dict]
) -> dict:
    focus_topics, weakest = profile_focus_topics(db, ep.user_id)
    return {
        "eval_profile": ep,
        "catalog": catalog,
        "solved_ids": ep.solved_ids,
        "focus_topics": focus_topics,
        "weakest_topic": weakest,
        "allowed": allowed_difficulties(len(ep.solved_ids)),
    }


# ---------------------------------------------------------------------------
# Mode: candidates (deterministic — no LLM)
# ---------------------------------------------------------------------------


def eval_candidates_for_profile(db: Session, ctx: dict) -> dict:
    """Score search_candidate_problems output for one profile.

    Mirrors what the agent's search tool returns: when the user has a weak
    topic we search within it first, falling back to an unfiltered search
    when the catalog has too few matches.
    """
    from app.services.agent_tools import search_candidate_problems

    ep: EvalProfile = ctx["eval_profile"]
    topic = ctx["weakest_topic"]

    result = search_candidate_problems(db, ep.user_id, topic=topic, limit=20)
    problems = result.get("problems", [])
    catalog_limited = bool(result.get("catalog_limited", False))

    if topic and len(problems) < 5:
        # Top up with unfiltered candidates so the set is large enough to
        # score meaningfully.
        extra = search_candidate_problems(db, ep.user_id, topic=None, limit=20)
        seen = {p["id"] for p in problems}
        for p in extra.get("problems", []):
            if p["id"] not in seen:
                problems.append(p)
                seen.add(p["id"])
            if len(problems) >= 10:
                break

    recs = [
        {
            "problem_id": p["id"],
            "title": p["title"],
            "platform": p["platform"],
            "difficulty": p.get("difficulty"),
            "url": p["url"],
            "topics": p.get("topics", []),
        }
        for p in problems
    ]

    metrics = compute_metrics(
        recs,
        catalog=ctx["catalog"],
        solved_ids=ctx["solved_ids"],
        focus_topics=ctx["focus_topics"],
        allowed=ctx["allowed"],
    )
    metrics["catalog_limited"] = float(catalog_limited)
    metrics["focus_topic"] = topic or ""
    return metrics


# ---------------------------------------------------------------------------
# Mode: agent (real Gemini calls)
# ---------------------------------------------------------------------------


def eval_agent_for_profile(db: Session, ctx: dict) -> dict:
    """Run RecommendationAgent end-to-end for one profile."""
    from app.services.recommendation_agent import RecommendationAgent

    ep: EvalProfile = ctx["eval_profile"]
    agent = RecommendationAgent(db, ep.user_id)

    start = time.monotonic()
    result = agent.recommend()
    latency_s = time.monotonic() - start

    recs = [
        {
            "problem_id": r.problem_id,
            "title": r.title,
            "platform": r.platform,
            "difficulty": r.difficulty,
            "url": r.url,
            "topics": r.topics,
        }
        for r in result.recommendations
    ]

    metrics = compute_metrics(
        recs,
        catalog=ctx["catalog"],
        solved_ids=ctx["solved_ids"],
        focus_topics=ctx["focus_topics"],
        allowed=ctx["allowed"],
    )
    metrics["latency_s"] = round(latency_s, 3)
    metrics["tool_calls"] = float(len(result.tool_calls_made))
    metrics["tool_call_names"] = ",".join(result.tool_calls_made)
    metrics["agent_error"] = result.error or ""
    metrics["error_kind"] = result.error_kind or ""
    usage = getattr(agent, "last_usage", None) or {}
    metrics["prompt_tokens"] = float(usage.get("prompt_token_count", 0) or 0)
    metrics["output_tokens"] = float(usage.get("candidates_token_count", 0) or 0)
    metrics["total_tokens"] = float(usage.get("total_token_count", 0) or 0)
    return metrics


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _fmt(v: float) -> str:
    return f"{v:.3f}"


def print_markdown_table(rows: list[dict], mode: str) -> None:
    agent_cols = mode == "agent"
    header = (
        "| Profile | n | Grounding | Unsolved | WeakCov | DiffFit | Diversity |"
        + (" Latency(s) | Tools | Tokens |" if agent_cols else "")
        + " CatalogLimited |"
    )
    sep = "|" + "---|" * (7 + (3 if agent_cols else 0) + 1)
    print(header)
    print(sep)
    for r in rows:
        line = (
            f"| {r['name']} | {int(r['n_recommendations'])} "
            f"| {_fmt(r['grounding_rate'])} | {_fmt(r['unsolved_rate'])} "
            f"| {_fmt(r['weak_topic_coverage'])} | {_fmt(r['difficulty_fit'])} "
            f"| {_fmt(r['topic_diversity'])} |"
        )
        if agent_cols:
            line += (
                f" {r.get('latency_s', 0):.1f} | {int(r.get('tool_calls', 0))} "
                f"| {int(r.get('total_tokens', 0))} |"
            )
        line += f" {int(r.get('catalog_limited', 0))} |"
        print(line)

    mean = mean_metrics(rows)
    mean_line = (
        f"| **Mean** | — "
        f"| **{_fmt(mean['grounding_rate'])}** | **{_fmt(mean['unsolved_rate'])}** "
        f"| **{_fmt(mean['weak_topic_coverage'])}** | **{_fmt(mean['difficulty_fit'])}** "
        f"| **{_fmt(mean['topic_diversity'])}** |"
    )
    if agent_cols:
        lat = sum(r.get("latency_s", 0) for r in rows) / max(len(rows), 1)
        toks = sum(r.get("total_tokens", 0) for r in rows) / max(len(rows), 1)
        mean_line += f" {lat:.1f} | — | {toks:.0f} |"
    mean_line += " — |"
    print(mean_line)


def run(mode: str) -> dict:
    db, eval_profiles, problems, problem_topics = seed_eval_db()
    catalog = build_catalog_index(problems, problem_topics)

    rows: list[dict] = []
    for ep in eval_profiles:
        ctx = profile_context(db, ep, catalog)
        if mode == "candidates":
            metrics = eval_candidates_for_profile(db, ctx)
        else:
            metrics = eval_agent_for_profile(db, ctx)
        metrics["name"] = ep.name
        metrics["user_id"] = ep.user_id
        metrics["solved_count"] = len(ep.solved_ids)
        metrics["platforms"] = ",".join(ep.platforms)
        rows.append(metrics)
        logger.info("eval %s %s done: %s", mode, ep.name, metrics)

    means = mean_metrics(rows)
    return {
        "mode": mode,
        "seed": SEED,
        "catalog_size": len(catalog),
        "n_profiles": len(rows),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "means": means,
        "profiles": rows,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="AI Coach offline evaluation harness")
    parser.add_argument("--mode", choices=["candidates", "agent"], required=True)
    parser.add_argument(
        "--out",
        default=None,
        help="JSON output path (default: evals/results/<timestamp>.json)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    result = run(args.mode)

    print_markdown_table(result["profiles"], args.mode)

    out_path = (
        Path(args.out)
        if args.out
        else RESULTS_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
