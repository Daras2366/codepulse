"""AI Coach run observability and recommendation persistence.

Records one ``coach_runs`` row per recommendation/chat execution and
persists verified recommendations into ``coach_recommendations``.

Safety contract:
- Persistence failures are logged and swallowed — they must NEVER break the
  actual API request.
- ``tool_calls`` stores tool NAMES only (no arguments, no payloads).
- No raw prompts, chat messages, or tool-result payloads are stored.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.coach import CoachRecommendation, CoachRun
from app.repositories.coach_repository import (
    CoachRecommendationRepository,
    CoachRunRepository,
)
from app.services.recommendation_agent import AgentRecommendation

logger = logging.getLogger(__name__)

ENDPOINT_RECOMMEND = "ai-coach/recommend"
ENDPOINT_CHAT = "ai-coach/chat"


def _usage_tokens(usage: Optional[dict]) -> tuple[Optional[int], Optional[int]]:
    """Extract (prompt_tokens, completion_tokens) from a usage dict."""
    if not usage:
        return None, None
    prompt = usage.get("prompt_token_count") or usage.get("input_tokens")
    completion = (
        usage.get("candidates_token_count")
        or usage.get("output_tokens")
    )
    try:
        prompt_i = int(prompt) if prompt is not None else None
    except (TypeError, ValueError):
        prompt_i = None
    try:
        completion_i = int(completion) if completion is not None else None
    except (TypeError, ValueError):
        completion_i = None
    return prompt_i, completion_i


class CoachObservabilityService:
    """Repository-facing service for coach_runs / coach_recommendations."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.runs = CoachRunRepository(db)
        self.recommendations = CoachRecommendationRepository(db)

    # ------------------------------------------------------------------
    # Run recording
    # ------------------------------------------------------------------

    def record_run(
        self,
        *,
        user_id: int,
        endpoint: str,
        model: Optional[str] = None,
        latency_ms: Optional[int] = None,
        tool_calls: Optional[list[str]] = None,
        usage: Optional[dict] = None,
        cache_hit: bool = False,
        error_kind: Optional[str] = None,
    ) -> Optional[CoachRun]:
        """Insert and commit a coach_runs row. Returns the run or None on failure."""
        prompt_tokens, completion_tokens = _usage_tokens(usage)
        try:
            run = CoachRun(
                user_id=user_id,
                endpoint=endpoint,
                model=model,
                latency_ms=latency_ms,
                tool_calls=list(tool_calls) if tool_calls else None,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cache_hit=cache_hit,
                error_kind=error_kind,
            )
            self.runs.add(run)
            self.db.commit()
            return run
        except Exception as exc:
            logger.warning(
                "coach_observability: failed to record run endpoint=%s user_id=%d: %s",
                endpoint,
                user_id,
                exc,
            )
            try:
                self.db.rollback()
            except SQLAlchemyError:
                pass
            return None

    # ------------------------------------------------------------------
    # Recommendation persistence
    # ------------------------------------------------------------------

    def persist_recommendations(
        self,
        *,
        run_id: int,
        user_id: int,
        recommendations: list[AgentRecommendation],
    ) -> dict[int, int]:
        """Persist verified recommendations for a run.

        Returns ``{problem_id: coach_recommendations.id}`` so the API response
        can expose stable recommendation ids for feedback.
        """
        mapping: dict[int, int] = {}
        try:
            rows: list[CoachRecommendation] = []
            seen: set[int] = set()
            for index, rec in enumerate(recommendations, start=1):
                # Only persist recommendations bound to a canonical problem id.
                if rec.problem_id is None or rec.problem_id in seen:
                    continue
                seen.add(rec.problem_id)
                rows.append(
                    CoachRecommendation(
                        run_id=run_id,
                        user_id=user_id,
                        problem_id=rec.problem_id,
                        rank=index,
                    )
                )
            if rows:
                self.recommendations.add_all(rows)
                self.db.commit()
                for row in rows:
                    mapping[row.problem_id] = row.id
        except Exception as exc:
            logger.warning(
                "coach_observability: failed to persist recommendations "
                "run_id=%d user_id=%d: %s",
                run_id,
                user_id,
                exc,
            )
            try:
                self.db.rollback()
            except SQLAlchemyError:
                pass
        return mapping
