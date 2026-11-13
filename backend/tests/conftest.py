"""Shared pytest fixtures for the backend test suite.

Provides an autouse fixture that resets the in-process AI Coach caches and
rate limiter before every test so module-level singletons cannot leak state
between tests (each test file uses its own in-memory database, so user ids
can collide across files).
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_coach_singletons():
    from app.core.rate_limit import rate_limiter
    from app.services import coach_cache

    coach_cache.clear()
    rate_limiter.reset()
    yield
    coach_cache.clear()
    rate_limiter.reset()
