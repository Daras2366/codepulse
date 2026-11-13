# Stage 4 — Recommendation Cache Benchmark

Generated: 2026-11-13T08:11:51.074687+00:00

> **Mocked-Gemini measurement.** The agent's ``recommend()`` was replaced with
a mock that sleeps 0.25s to simulate provider
latency. These numbers measure cache overhead vs. simulated generation time —
they are **not** real production latency measurements.

## Setup

- Endpoint: `POST /ai-coach/recommend`
- Uncached phase: 20 requests with `force_refresh=true`
- Cached phase: 20 requests without
  `force_refresh` (1 miss + 19 hits)
- In-process SQLite test database, FastAPI TestClient

## Results

| Metric | Uncached (forced refresh) | Cached (hits only) |
|---|---:|---:|
| Requests | 20 | 19 |
| p50 latency (ms) | 268.13 | 8.78 |
| p95 latency (ms) | 271.85 | 14.75 |
| mean latency (ms) | 269.94 | 9.41 |
| min latency (ms) | 264.71 | 6.3 |
| max latency (ms) | 300.85 | 14.75 |
| Gemini/agent calls | 20 | 1 |

- Cache hit rate (cached phase): 95.0%
- Agent calls avoided by cache: 19

## Notes

- Cache-hit latency is dominated by fingerprint computation (a handful of
  indexed SQL queries) plus coach_runs bookkeeping — typically single-digit
  to low-double-digit milliseconds on SQLite.
- The uncached latency floor is the artificial 0.25s
  delay plus the same bookkeeping overhead.
