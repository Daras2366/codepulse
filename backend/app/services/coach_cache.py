"""Recommendation response cache for POST /ai-coach/recommend.

The cache key fingerprint incorporates everything that can change the agent's
output for a user:

- authenticated user id
- total submission count, latest submission id and latest submitted_at
- active goal ids and their updated_at values
- GEMINI_MODEL
- a prompt-version constant (bump when _SYSTEM_PROMPT or the response
  contract changes)

Only successful, validated results are stored (enforced by the caller).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.cache import InProcessTTLCache
from app.core.config import settings
from app.models.enums import GoalStatus
from app.models.goal import Goal
from app.models.platform_profile import PlatformProfile
from app.models.submission import Submission

logger = logging.getLogger(__name__)

# Bump when the agent system prompt, tool set, or response schema changes so
# stale cached recommendations are invalidated automatically.
RECOMMENDATION_PROMPT_VERSION = "recommendation-agent-v1"

_cache = InProcessTTLCache()

# Per-key locks so concurrent requests for the same fingerprint don't run the
# (expensive) agent loop in parallel and race to populate the cache.
_generation_locks: dict[str, threading.Lock] = {}
_generation_locks_guard = threading.Lock()


def _setting_float(name: str, default: float) -> float:
    value = getattr(settings, name, default)
    return float(value) if isinstance(value, (int, float)) else default


def cache_ttl_seconds() -> float:
    return _setting_float("AI_COACH_RECOMMEND_CACHE_TTL_SECONDS", 6 * 60 * 60)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def compute_fingerprint(db: Session, user_id: int) -> str:
    """Build the deterministic cache fingerprint for a user's recommendations."""
    sub_stats = (
        db.query(
            func.count(Submission.id),
            func.max(Submission.id),
            func.max(Submission.submitted_at),
        )
        .join(PlatformProfile, Submission.profile_id == PlatformProfile.id)
        .filter(PlatformProfile.user_id == user_id)
        .one()
    )
    submission_count, latest_submission_id, latest_submitted_at = sub_stats

    goal_rows = (
        db.query(Goal.id, Goal.updated_at)
        .filter(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE)
        .order_by(Goal.id)
        .all()
    )

    model = getattr(settings, "GEMINI_MODEL", "")
    model_name = model if isinstance(model, str) else ""

    payload = {
        "user_id": user_id,
        "submission_count": int(submission_count or 0),
        "latest_submission_id": int(latest_submission_id) if latest_submission_id else None,
        "latest_submitted_at": (
            latest_submitted_at.isoformat() if latest_submitted_at else None
        ),
        "active_goals": [
            [int(goal_id), updated_at.isoformat() if updated_at else None]
            for goal_id, updated_at in goal_rows
        ],
        "model": model_name,
        "prompt_version": RECOMMENDATION_PROMPT_VERSION,
    }

    serialized = json.dumps(payload, sort_keys=True, default=_json_default)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def cache_key(user_id: int, fingerprint: str) -> str:
    return f"coach:recommend:{user_id}:{fingerprint}"


def get_cached(user_id: int, fingerprint: str) -> Optional[dict]:
    """Return the cached entry ``{"refreshed_at": ..., "payload": {...}}``."""
    return _cache.get(cache_key(user_id, fingerprint))


def set_cached(
    user_id: int,
    fingerprint: str,
    payload: dict,
    refreshed_at: Optional[datetime] = None,
) -> None:
    ts = refreshed_at or datetime.now(timezone.utc)
    entry = {
        "refreshed_at": ts.isoformat(),
        "payload": payload,
    }
    _cache.set(cache_key(user_id, fingerprint), entry, cache_ttl_seconds())


@contextmanager
def generation_lock(user_id: int, fingerprint: str) -> Iterator[None]:
    """Hold a per-fingerprint lock while generating + storing a result."""
    key = cache_key(user_id, fingerprint)
    with _generation_locks_guard:
        lock = _generation_locks.setdefault(key, threading.Lock())
    with lock:
        yield


def clear() -> None:
    """Clear all cached entries and generation locks (mainly for tests)."""
    _cache.clear()
    with _generation_locks_guard:
        _generation_locks.clear()
