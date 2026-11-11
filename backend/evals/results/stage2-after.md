# Stage 2 — candidates eval AFTER Part A (candidate ranking)

Command: `python -m evals.run_eval --mode candidates --out evals/results/stage2-after.md.json`
(same seed/profiles as stage2-before.md; raw JSON in stage2-after.md.json)

| Profile | n | Grounding | Unsolved | WeakCov | DiffFit | Diversity | CatalogLimited |
|---|---|---|---|---|---|---|---|
| beginner_cf | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.458 | 0 |
| beginner_lc | 20 | 1.000 | 1.000 | 0.900 | 1.000 | 0.478 | 0 |
| newcomer_barely | 20 | 1.000 | 1.000 | 0.000 | 1.000 | 0.537 | 0 |
| strong_dp_weak_graphs | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.447 | 0 |
| strong_graphs_weak_dp | 20 | 1.000 | 1.000 | 0.950 | 1.000 | 0.440 | 0 |
| all_round_strong | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.400 | 0 |
| dual_weak_topics | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.489 | 0 |
| hard_heavy | 20 | 1.000 | 1.000 | 0.750 | 1.000 | 0.468 | 0 |
| easy_only | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.477 | 0 |
| medium_focus | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.431 | 0 |
| cf_only_intermediate | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.367 | 0 |
| lc_only_intermediate | 20 | 1.000 | 1.000 | 0.950 | 1.000 | 0.488 | 0 |
| both_platforms_balanced | 20 | 1.000 | 1.000 | 0.900 | 1.000 | 0.489 | 0 |
| inactive_60d | 20 | 1.000 | 1.000 | 0.950 | 1.000 | 0.449 | 0 |
| inactive_90d_lc | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.553 | 0 |
| streak_user | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.439 | 0 |
| sporadic | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.318 | 0 |
| low_acceptance | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.311 | 0 |
| many_attempts_unsolved | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.477 | 0 |
| sparse_topic_tags | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.349 | 0 |
| goal_topic_user | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.326 | 0 |
| veteran | 20 | 1.000 | 1.000 | 0.500 | 1.000 | 0.436 | 0 |
| rating_climber | 20 | 1.000 | 1.000 | 1.000 | 1.000 | 0.440 | 0 |
| **Mean** | — | **1.000** | **1.000** | **0.909** | **1.000** | **0.438** | — |

## Means: before → after

| Metric | Before | After | Delta |
|---|---|---|---|
| grounding_rate | 1.000 | 1.000 | 0.000 |
| unsolved_rate | 1.000 | 1.000 | 0.000 |
| weak_topic_coverage | 0.852 | 0.909 | +0.057 |
| difficulty_fit | 0.828 | 1.000 | +0.172 |
| topic_diversity | 0.450 | 0.438 | -0.012 |

Note: run-to-run noise of ~±0.01-0.02 exists in this harness (tie-order
nondeterminism in the old acceptance_rate ordering; the new ranker is
deterministic — ties break on problem_id). topic_diversity is effectively
flat vs the committed baseline.md (0.453 → 0.438); every profile now
returns the full limit=20 candidates instead of 8-13, which mechanically
pressures the distinct/total ratio.
