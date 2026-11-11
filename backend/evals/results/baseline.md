# Baseline — `--mode candidates` (deterministic search, no LLM)

Seed: `20261110` · Catalog: 330 problems · Profiles: 22
Generated: see `baseline-candidates.json` for the full per-profile JSON.

| Profile | n | Grounding | Unsolved | WeakCov | DiffFit | Diversity | CatalogLimited |
|---|---|---|---|---|---|---|---|
| beginner_cf | 20 | 1.000 | 1.000 | 1.000 | 0.600 | 0.360 | 0 |
| beginner_lc | 20 | 1.000 | 1.000 | 1.000 | 0.550 | 0.386 | 0 |
| newcomer_barely | 20 | 1.000 | 1.000 | 0.000 | 0.350 | 0.442 | 0 |
| strong_dp_weak_graphs | 10 | 1.000 | 1.000 | 0.600 | 1.000 | 0.619 | 1 |
| strong_graphs_weak_dp | 10 | 1.000 | 1.000 | 0.500 | 1.000 | 0.591 | 1 |
| all_round_strong | 10 | 1.000 | 1.000 | 0.100 | 1.000 | 0.722 | 1 |
| dual_weak_topics | 13 | 1.000 | 1.000 | 1.000 | 0.769 | 0.414 | 0 |
| hard_heavy | 8 | 1.000 | 1.000 | 1.000 | 0.875 | 0.450 | 0 |
| easy_only | 19 | 1.000 | 1.000 | 1.000 | 0.895 | 0.415 | 0 |
| medium_focus | 16 | 1.000 | 1.000 | 1.000 | 0.875 | 0.415 | 0 |
| cf_only_intermediate | 20 | 1.000 | 1.000 | 1.000 | 0.900 | 0.354 | 0 |
| lc_only_intermediate | 20 | 1.000 | 1.000 | 1.000 | 0.750 | 0.349 | 0 |
| both_platforms_balanced | 9 | 1.000 | 1.000 | 1.000 | 0.889 | 0.550 | 0 |
| inactive_60d | 11 | 1.000 | 1.000 | 1.000 | 1.000 | 0.444 | 0 |
| inactive_90d_lc | 17 | 1.000 | 1.000 | 1.000 | 0.882 | 0.389 | 0 |
| streak_user | 20 | 1.000 | 1.000 | 1.000 | 0.800 | 0.357 | 0 |
| sporadic | 13 | 1.000 | 1.000 | 1.000 | 1.000 | 0.469 | 0 |
| low_acceptance | 20 | 1.000 | 1.000 | 1.000 | 0.900 | 0.372 | 0 |
| many_attempts_unsolved | 16 | 1.000 | 1.000 | 1.000 | 0.812 | 0.474 | 0 |
| sparse_topic_tags | 20 | 1.000 | 1.000 | 1.000 | 0.750 | 0.395 | 0 |
| goal_topic_user | 20 | 1.000 | 1.000 | 1.000 | 0.800 | 0.310 | 0 |
| veteran | 10 | 1.000 | 1.000 | 0.400 | 1.000 | 0.632 | 1 |
| rating_climber | 10 | 1.000 | 1.000 | 1.000 | 0.600 | 0.519 | 0 |
| **Mean** | — | **1.000** | **1.000** | **0.852** | **0.826** | **0.453** | — |

## Observations

- Grounding and unsolved rates are perfect (1.000) — expected, since
  candidates come straight from `search_candidate_problems` DB queries.
- `weak_topic_coverage` mean 0.852 — the topic-filtered search helps, but
  `all_round_strong` (0.100) and `veteran` (0.400) show the filter only
  applies to the first few candidates before the unfiltered top-up.
- `difficulty_fit` mean 0.826 — beginners score low (0.35–0.60) because the
  candidate search does not filter by difficulty at all; it only orders by
  acceptance rate.
- `topic_diversity` mean 0.453 — candidate sets are topically repetitive,
  a known limitation of ordering by `acceptance_rate` alone.
