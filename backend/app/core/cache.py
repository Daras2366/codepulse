"""In-process TTL cache.

Small cache interface used by the AI Coach recommendation endpoint. The
interface (``get`` / ``set`` / ``clear``) is deliberately storage-agnostic so
a Redis-backed implementation can be substituted later without changing
callers.

NOTE: this is a per-process cache. Entries are not shared across application
workers — each worker keeps its own copy.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Optional


class InProcessTTLCache:
    """Thread-safe in-memory cache with per-entry TTL."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Return the value for ``key`` or None when missing/expired."""
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if now >= expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        """Store ``value`` under ``key`` for ``ttl_seconds``."""
        if ttl_seconds <= 0:
            return
        expires_at = time.monotonic() + ttl_seconds
        with self._lock:
            self._store[key] = (expires_at, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
