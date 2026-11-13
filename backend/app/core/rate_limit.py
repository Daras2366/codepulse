"""Per-key rate limiter.

Small abstraction used by the AI Coach endpoints. The default implementation
is an in-process fixed-window counter keyed by an arbitrary string (we use
``"<endpoint>:<user_id>"``).

NOTE: in-process limiting is per application worker. With N workers the
effective global limit is approximately ``limit * N``. A distributed
implementation (e.g. Redis) can be substituted later behind the same
``check``/``reset`` interface without changing callers.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a rate-limit check."""

    allowed: bool
    retry_after_seconds: int
    remaining: int


class InProcessRateLimiter:
    """Fixed-window per-key rate limiter."""

    def __init__(self) -> None:
        # key -> (window_start_monotonic, count)
        self._buckets: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> RateLimitResult:
        """Consume one unit for ``key``.

        Returns whether the request is allowed, how many requests remain in
        the current window, and seconds until the window resets (for the
        ``Retry-After`` header when denied).
        """
        if limit <= 0:
            # A non-positive limit means "unlimited" for defensive settings.
            return RateLimitResult(allowed=True, retry_after_seconds=0, remaining=limit)

        now = time.monotonic()
        window = max(1, window_seconds)

        with self._lock:
            window_start, count = self._buckets.get(key, (now, 0))
            if now - window_start >= window:
                window_start, count = now, 0

            if count >= limit:
                retry_after = max(1, int(window - (now - window_start)) + 1)
                return RateLimitResult(
                    allowed=False,
                    retry_after_seconds=retry_after,
                    remaining=0,
                )

            self._buckets[key] = (window_start, count + 1)
            return RateLimitResult(
                allowed=True,
                retry_after_seconds=0,
                remaining=limit - count - 1,
            )

    def reset(self) -> None:
        """Clear all buckets (mainly for tests)."""
        with self._lock:
            self._buckets.clear()


rate_limiter = InProcessRateLimiter()
