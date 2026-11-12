"""One-off Stage 3 agent-mode eval over ONLY the failure profiles.

Reuses evals.run_eval helpers; not part of the standard CLI. Writes
results to evals/results/stage3_failure_agent.json.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from evals.profiles import SEED, seed_eval_db
from evals.profiles_failure import seed_failure_profiles
from evals.run_eval import (
    build_catalog_index,
    eval_agent_for_profile,
    profile_context,
)


def main() -> int:
    db, eval_profiles, problems, problem_topics = seed_eval_db()
    catalog = build_catalog_index(problems, problem_topics)
    failure_profiles = seed_failure_profiles(db, problems, problem_topics)

    rows = []
    for ep in failure_profiles:
        ctx = profile_context(db, ep, catalog)
        metrics = eval_agent_for_profile(db, ctx)
        metrics["name"] = ep.name
        metrics["is_failure_profile"] = True
        rows.append(metrics)
        print(ep.name, "->", {k: metrics[k] for k in (
            "grounding_rate", "unsolved_rate", "weak_topic_coverage",
            "difficulty_fit", "topic_diversity", "advice_specificity",
            "tool_calls", "latency_s", "agent_error", "tool_call_names",
        )}, flush=True)

    out = Path(__file__).resolve().parent / "results" / "stage3_failure_agent.json"
    out.write_text(json.dumps({
        "mode": "agent",
        "seed": SEED,
        "scope": "failure_profiles_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profiles": rows,
    }, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
