# Stage 2 — candidates eval BEFORE changes

Command: `python -m evals.run_eval --mode candidates --out evals/results/stage2-before.md.json`
(seed 20261110, 22 profiles, run on branch feat/coach-ranking-structured-output before any code change)

| Profile | n | Grounding | Unsolved | WeakCov | DiffFit | Diversity | CatalogLimited |
|---|---|---|---|---|---|---|---|
| beginner_cf | 20 | 1.000 | 1.000 | 1.000 | 0.500 | 0.348 | 0 |
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
| sparse_topic_tags | 20 | 1.000 | 1.000 | 1.000 | 0.900 | 0.341 | 0 |
| goal_topic_user | 20 | 1.000 | 1.000 | 1.000 | 0.800 | 0.310 | 0 |
| veteran | 10 | 1.000 | 1.000 | 0.400 | 1.000 | 0.632 | 1 |
| rating_climber | 10 | 1.000 | 1.000 | 1.000 | 0.600 | 0.519 | 0 |
| **Mean** | — | **1.000** | **1.000** | **0.852** | **0.828** | **0.450** | — |

Note: committed baseline.md reports DiffFit 0.826 / Diversity 0.453; this run shows
0.828 / 0.450 — a single-profile difference in `sparse_topic_tags` (0.900/0.341 vs
0.750/0.395), consistent with tie-order nondeterminism in the old
`acceptance_rate DESC` ordering. All other profiles are identical.
