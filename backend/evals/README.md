# AI Coach Evaluation Harness

Offline evaluation for the AI Coach recommendation pipeline. Everything runs
against an in-memory SQLite database seeded with synthetic users, problems,
topics and submissions — no production data is touched.

## Layout

- `profiles.py` — seeds ≥330 catalog problems (realistic topics,
  difficulties, acceptance rates) and 22 synthetic user profiles covering
  beginners, topic-strength/weakness archetypes, single/both-platform users,
  inactive users, goal holders and many-attempts users. All randomness uses
  `random.Random(SEED)` — runs are reproducible. **Frozen: do not modify.**
- `profiles_failure.py` — 3 additional failure-pattern profiles (TLE-heavy
  graphs, high attempts-before-accept on DP, a topic stale for 70+ days),
  seeded only via `--include-failure-profiles`. Uses the same `SEED`.
- `metrics.py` — pure scoring functions (no DB, no I/O). **Frozen.**
- `metrics_advice.py` — `advice_specificity` metric (see below).
- `run_eval.py` — CLI entry point.
- `results/` — JSON outputs and committed baselines.

## Running

From `backend/` (env vars required because `app.core.config` loads settings):

```bash
# Deterministic candidate search — no LLM, always runnable
DATABASE_URL=sqlite:///./t.db SECRET_KEY=x ALGORITHM=HS256 \
    python -m evals.run_eval --mode candidates --out evals/results/run.json

# Full Gemini agent — requires a real GEMINI_API_KEY
DATABASE_URL=sqlite:///./t.db SECRET_KEY=x ALGORITHM=HS256 \
    GEMINI_API_KEY=... python -m evals.run_eval --mode agent --out evals/results/run.json

# Include the 3 Stage 3 failure-pattern profiles (either mode)
... python -m evals.run_eval --mode candidates --include-failure-profiles
```

The CLI prints a markdown table (one row per profile + a mean row) and writes
the full JSON result to `--out` (default `evals/results/<timestamp>.json`).
When `--include-failure-profiles` is used, the JSON also contains
`means_baseline` — the mean over the original 22 profiles only, so Stage 2
numbers remain comparable (`means` covers all rows).

## Modes

- `candidates` — evaluates only `agent_tools.search_candidate_problems`
  (the deterministic candidate search/ranking the agent uses). For each
  profile it searches within the user's weakest topic first, topping up
  with unfiltered candidates when fewer than 5 matches exist.
- `agent` — runs `RecommendationAgent.recommend()` end-to-end per profile
  against the real Gemini API. Records latency, `tool_calls_made`, agent
  errors, and token usage when the provider returns it
  (`agent.last_usage`).

## Metrics

All metrics are fractions in `[0, 1]` computed per recommendation set by
`evals.metrics.compute_metrics`:

| Metric                | Definition                                                                                                                                                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `grounding_rate`      | Fraction of recommendations matching a real `Problem` row — by `problem_id`, falling back to `problem_url`. When an id matches and the model supplied a title, the title must equal the catalog title (invented titles don't count). |
| `unsolved_rate`       | Fraction the user has not already solved (no ACCEPTED submission). Unverifiable recommendations conservatively count as solved/unknown → excluded from the numerator.                                                                |
| `weak_topic_coverage` | Fraction touching ≥1 of the user's weak **or** moderate topics (from `PerformanceAnalyzer` via `agent_tools.get_topic_performance`). Case-insensitive, whitespace-normalised.                                                        |
| `difficulty_fit`      | Fraction inside the user's allowed difficulty band (below). Missing/unrecognised difficulty counts as a failure.                                                                                                                     |
| `topic_diversity`     | Distinct normalised topics across the set ÷ total topic slots. 1.0 = no repeated topics.                                                                                                                                             |

### Difficulty bands (`allowed_difficulties`)

Explicit rule based on distinct solved problems:

| Solved  | Allowed difficulties     |
| ------- | ------------------------ |
| `< 20`  | `Easy`                   |
| `20–99` | `Easy`, `Medium`         |
| `≥ 100` | `Easy`, `Medium`, `Hard` |

Rationale: Hard problems have near-zero success probability for beginners and
would pollute the metric; the bands widen as demonstrated ability grows.

## advice_specificity (agent mode only)

`evals.metrics_advice.advice_specificity` measures whether each
recommendation's `reason` cites a fact that actually appeared in that run's
tool outputs — a topic name (keys `topic`/`topics`/`topic_name`/
`focus_topic`) or a verdict/status (keys `status`/`verdict`, dict keys under
`verdicts`, expanded via a fixed alias table such as
`time_limit_exceeded` → "time limit"/"TLE"). Matching is
case-insensitive, word-boundaried, and treats whitespace/hyphens/
underscores as equivalent. It is the fraction of reasons containing ≥1 such
fact; 0.0 when there are no reasons or no citable facts. It checks grounding
of the stated reasoning only — not advice quality. See the module docstring
for the exact definition.

## Tests

```bash
python -m pytest tests/test_evals.py -v
```

Covers known-input→known-output cases for every metric, seeding sanity and
determinism, and a smoke test that `run(mode="candidates")` completes over
all 22 seeded profiles.
