"""Reproducible benchmark for POST /ai-coach/recommend caching (Stage 4).

IMPORTANT: Gemini is MOCKED. The agent's ``recommend()`` sleeps for a fixed
artificial delay (``ARTIFICIAL_AGENT_DELAY_SECONDS``) to simulate provider
latency. Results measure cache overhead vs. generation time only — they are
NOT real production latency measurements.

Run from the backend directory:

    DATABASE_URL=sqlite:///./t.db SECRET_KEY=x ALGORITHM=HS256 \
        python evals/benchmark_cache.py

Writes evals/results/stage4_cache_benchmark.md with the measured numbers.
"""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Settings are instantiated at import time — provide defaults first.
os.environ.setdefault("DATABASE_URL", "sqlite:///./bench_cache.db")
os.environ.setdefault("SECRET_KEY", "bench-secret")
os.environ.setdefault("ALGORITHM", "HS256")
# The benchmark issues more requests than the default per-user limit.
os.environ.setdefault("AI_COACH_RECOMMEND_RATE_LIMIT", "10000")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - registers ORM models
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.base import Base
from app.models.enums import Difficulty, Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.routers import recommendations as recommendations_router
from app.services import coach_cache
from app.services.recommendation_agent import (
    AgentRecommendation,
    AgentRecommendationResult,
)

ARTIFICIAL_AGENT_DELAY_SECONDS = 0.25
UNCACHED_REQUESTS = 20
CACHED_REQUESTS = 20  # includes 1 miss + 19 hits; hits are what's reported
RESULTS_PATH = (
    Path(__file__).resolve().parent / "results" / "stage4_cache_benchmark.md"
)


# ---------------------------------------------------------------------------
# Harness (mirrors backend/tests conventions)
# ---------------------------------------------------------------------------


def _build_app(db_session):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    def override_get_db():
        try:
            s = db_session()
            yield s
        finally:
            s.close()

    engine_holder = {"user": None}

    def override_get_current_user():
        return engine_holder["user"]

    app = FastAPI()
    app.include_router(recommendations_router.router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return app, TestClient(app), engine_holder


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, math.ceil(pct / 100 * len(ordered)) - 1)
    return ordered[idx]


def _stats(latencies_ms: list[float]) -> dict:
    return {
        "count": len(latencies_ms),
        "p50_ms": round(_percentile(latencies_ms, 50), 2),
        "p95_ms": round(_percentile(latencies_ms, 95), 2),
        "mean_ms": round(statistics.fmean(latencies_ms), 2),
        "min_ms": round(min(latencies_ms), 2),
        "max_ms": round(max(latencies_ms), 2),
    }


def main() -> int:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    user = User(
        username="benchuser",
        email="bench@example.com",
        password_hash="hashed",
        is_active=True,
    )
    db.add(user)
    db.flush()
    profile = PlatformProfile(
        user_id=user.id, platform=Platform.CODEFORCES, username="bench_cf"
    )
    problem = Problem(
        platform=Platform.CODEFORCES,
        platform_problem_id="4242-A",
        title="Benchmark Problem",
        slug="bench-4242-a",
        problem_url="https://codeforces.com/problemset/problem/4242/A",
        difficulty=Difficulty.EASY,
    )
    db.add_all([profile, problem])
    db.flush()
    db.add(
        Submission(
            profile_id=profile.id,
            problem_id=problem.id,
            submitted_at=datetime.now(timezone.utc),
            language="Python3",
            status=SubmissionStatus.ACCEPTED,
            platform_submission_id="bench-sub-1",
        )
    )
    db.commit()

    app, client, holder = _build_app(SessionLocal)
    holder["user"] = user

    call_count = {"n": 0}

    def fake_recommend():
        call_count["n"] += 1
        time.sleep(ARTIFICIAL_AGENT_DELAY_SECONDS)
        return AgentRecommendationResult(
            recommendations=[
                AgentRecommendation(
                    problem_id=problem.id,
                    title=problem.title,
                    platform="codeforces",
                    difficulty="Easy",
                    url=problem.problem_url,
                    topics=["Arrays"],
                    reason="benchmark",
                    priority=1,
                    likely_unsolved=True,
                )
            ],
            agent_reasoning="bench",
            has_sufficient_data=True,
            tool_calls_made=["get_user_performance_profile"],
        )

    coach_cache.clear()

    def timed_post(force: bool) -> tuple[float, dict]:
        url = "/ai-coach/recommend" + ("?force_refresh=true" if force else "")
        start = time.perf_counter()
        resp = client.post(url)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200, resp.text
        return elapsed_ms, resp.json()

    with patch(
        "app.routers.recommendations.RecommendationAgent"
    ) as mock_cls:
        agent = MagicMock()
        agent.is_configured.return_value = True
        agent.last_model = "gemini-bench-mock"
        agent.last_usage = None
        agent.recommend.side_effect = fake_recommend
        mock_cls.return_value = agent

        # --- Uncached path: every request force-refreshes -------------------
        uncached_latencies: list[float] = []
        for _ in range(UNCACHED_REQUESTS):
            ms, data = timed_post(force=True)
            assert data["from_cache"] is False
            uncached_latencies.append(ms)
        uncached_calls = call_count["n"]

        # --- Cached path: 1 miss + hits -------------------------------------
        coach_cache.clear()
        call_count["n"] = 0
        hit_latencies: list[float] = []
        miss_count = 0
        for _ in range(CACHED_REQUESTS):
            ms, data = timed_post(force=False)
            if data["from_cache"]:
                hit_latencies.append(ms)
            else:
                miss_count += 1
        cached_calls = call_count["n"]

    uncached_stats = _stats(uncached_latencies)
    hit_stats = _stats(hit_latencies)
    total_cached_requests = UNCACHED_REQUESTS  # placeholder, recomputed below

    hit_rate = (
        len(hit_latencies) / CACHED_REQUESTS if CACHED_REQUESTS else 0.0
    )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artificial_agent_delay_seconds": ARTIFICIAL_AGENT_DELAY_SECONDS,
        "uncached": uncached_stats,
        "cached_hit": hit_stats,
        "cache_misses_in_cached_phase": miss_count,
        "gemini_calls_uncached_phase": uncached_calls,
        "gemini_calls_cached_phase": cached_calls,
        "cache_hit_rate": round(hit_rate, 4),
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(_render_markdown(report), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nWrote {RESULTS_PATH}")
    db.close()
    return 0


def _render_markdown(r: dict) -> str:
    u = r["uncached"]
    h = r["cached_hit"]
    return f"""# Stage 4 — Recommendation Cache Benchmark

Generated: {r["generated_at"]}

> **Mocked-Gemini measurement.** The agent's ``recommend()`` was replaced with
a mock that sleeps {r["artificial_agent_delay_seconds"]}s to simulate provider
latency. These numbers measure cache overhead vs. simulated generation time —
they are **not** real production latency measurements.

## Setup

- Endpoint: `POST /ai-coach/recommend`
- Uncached phase: {u["count"]} requests with `force_refresh=true`
- Cached phase: {h["count"] + r["cache_misses_in_cached_phase"]} requests without
  `force_refresh` ({r["cache_misses_in_cached_phase"]} miss + {h["count"]} hits)
- In-process SQLite test database, FastAPI TestClient

## Results

| Metric | Uncached (forced refresh) | Cached (hits only) |
|---|---:|---:|
| Requests | {u["count"]} | {h["count"]} |
| p50 latency (ms) | {u["p50_ms"]} | {h["p50_ms"]} |
| p95 latency (ms) | {u["p95_ms"]} | {h["p95_ms"]} |
| mean latency (ms) | {u["mean_ms"]} | {h["mean_ms"]} |
| min latency (ms) | {u["min_ms"]} | {h["min_ms"]} |
| max latency (ms) | {u["max_ms"]} | {h["max_ms"]} |
| Gemini/agent calls | {r["gemini_calls_uncached_phase"]} | {r["gemini_calls_cached_phase"]} |

- Cache hit rate (cached phase): {r["cache_hit_rate"] * 100:.1f}%
- Agent calls avoided by cache: {r["gemini_calls_uncached_phase"] - r["gemini_calls_cached_phase"]}

## Notes

- Cache-hit latency is dominated by fingerprint computation (a handful of
  indexed SQL queries) plus coach_runs bookkeeping — typically single-digit
  to low-double-digit milliseconds on SQLite.
- The uncached latency floor is the artificial {r["artificial_agent_delay_seconds"]}s
  delay plus the same bookkeeping overhead.
"""


if __name__ == "__main__":
    sys.exit(main())
