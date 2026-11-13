# AI Coach — Stage 4: Cache, Rate Limiting, Observability & Feedback

## Recommendation caching (`POST /ai-coach/recommend`)

- Successful, validated results are cached **per authenticated user** for
  `AI_COACH_RECOMMEND_CACHE_TTL_SECONDS` (default 6h).
- Cache key = SHA-256 over a deterministic JSON payload containing:
  user id, total submission count, latest submission id + `submitted_at`,
  active goal ids + `updated_at`, `GEMINI_MODEL`, and
  `RECOMMENDATION_PROMPT_VERSION` (bump it when the agent prompt/tool set/
  response contract changes).
- `?force_refresh=true` bypasses cache reads, still consumes rate-limit
  quota, and replaces the cached entry after a successful run.
- Only successful results are cached — provider errors, parse failures and
  not-configured responses are never stored.
- Implementation: `app/core/cache.py` (`InProcessTTLCache`) behind
  `app/services/coach_cache.py`. A Redis-backed store can replace the
  in-process cache without changing the endpoint.

**Limitation:** the cache is per-process. Multiple app workers each keep
their own copy — a user may get a cache miss on a different worker. This is
acceptable for cost reduction, not a correctness mechanism.

## Rate limiting

- Per-user fixed-window limits on `POST /ai-coach/recommend`
  (`AI_COACH_RECOMMEND_RATE_LIMIT`, default 20) and `POST /ai-coach/chat`
  (`AI_COACH_CHAT_RATE_LIMIT`, default 60), window
  `AI_COACH_RATE_LIMIT_WINDOW_SECONDS` (default 3600).
- Keyed by authenticated user id + endpoint; exceeded → HTTP 429 with a
  valid `Retry-After` header.
- Every authenticated request consumes quota, including failed Gemini calls
  and `force_refresh` requests.

**Limitation:** `app/core/rate_limit.py` (`InProcessRateLimiter`) is
in-process. With N workers the effective global limit is roughly
`limit * N`. It does **not** provide globally shared limits — a distributed
store is required for that.

## Observability (`coach_runs`)

One row per recommendation/chat execution: endpoint, model, latency_ms,
tool names (never arguments/payloads), prompt/completion token usage
(nullable when the provider doesn't return it), cache_hit, error_kind.
Cached recommendation requests are recorded with `cache_hit=true` and no
token usage — no Gemini call is pretended.

Persistence is best-effort: failures are logged and never break the API.

## Feedback (`coach_recommendations`, `coach_feedback`)

- Successful uncached runs persist verified recommendations with
  `run_id`, `user_id`, canonical `problem_id` (`problems.id`) and `rank`.
- `POST /ai-coach/feedback` accepts `{recommendation_id, action}` where
  action ∈ `solved | skipped | thumbs_up | thumbs_down`.
- Ownership is enforced via `coach_recommendations.user_id`; foreign or
  missing recommendations → 404. Invalid actions → 422.
- **Idempotent:** `(recommendation_id, action)` is unique — retries return
  `recorded=false` without duplicating. Different actions may coexist.

## Automatic solved marking

When LeetCode or Codeforces sync imports an ACCEPTED submission, matching
recommendations (same user, same `problems.id`, created within the last
14 days, not newer than the submission) get a `solved` feedback row.
Runs inside a nested savepoint — it can never corrupt or commit the sync
transaction early, and failures are logged and swallowed.
