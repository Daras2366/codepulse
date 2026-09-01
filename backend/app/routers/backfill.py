"""Codeforces topic backfill router.

This module exposes a single authenticated endpoint that safely backfills
topic tags for existing Codeforces problems using a single Codeforces API
call (problem.list).  It does NOT modify normal sync behaviour.

POST /analytics/backfill-codeforces-topics

Why this is needed
------------------
The ``_sync_problem_tags`` helper in ``sync_service.py`` only runs when a
problem is *created* for the first time.  Problems that were synced before
the tag-syncing code existed therefore have zero topic data.  This endpoint
fills that gap in a safe, one-time fashion:

1.  One call to Codeforces ``problemset.problems`` (returns ~10 000 problems
    with tags in a single HTTP response).
2.  Filter results down to problems already present in CodePulse's DB.
3.  Skip any problem that already has at least one ProblemTopic row.
4.  Insert Topic + ProblemTopic rows for the matched problems.

Complexity: O(local_problem_count) DB lookups, O(1) API calls.
This is completely safe and cannot cause the rate-limit explosion that broke
normal LeetCode sync.

POST /analytics/backfill-leetcode-topics

Why this is needed
------------------
LeetCode's public API only exposes the 20 most-recent accepted submissions.
This endpoint backfills topic tags for problems that are already stored locally
from previous syncs. It does NOT discover historical solved problems that are
not in the local database.

This endpoint:

1.  Finds all LeetCode problems the user has solved based on locally stored
    submissions (limited to recent syncs).
2.  For each problem without existing topics, fetches problem details via public
    GraphQL API using the title slug.
3.  Creates missing Topic and ProblemTopic relationships.
4.  Is idempotent - skips problems that already have topic links.

**Important Limitations**

- This is a LOCAL-DATA backfill only. It only processes problems already stored
  in CodePulse from recent syncs.
- It does NOT discover or backfill historical solved problems that are not in
  the local database.
- For complete LeetCode topic analytics, the system uses profile-level
  ``tagProblemCounts`` from the public profile API, not this backfill.
- Normal LeetCode sync is NOT affected by this endpoint.
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.enums import Platform
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.topic import Topic
from app.models.user import User
from app.services.leetcode_sync_service import (
    LeetCodeSyncError,
    LeetCodeSyncService,
)
from app.services.base_sync_service import (
    PlatformProfileNotFoundError,
    ProfileAccessDeniedError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])

_CF_PROBLEMS_URL = "https://codeforces.com/api/problemset.problems"


class BackfillResult(BaseModel):
    problems_inspected: int
    problems_already_tagged: int
    problems_tagged_now: int
    topics_created: int
    topic_links_created: int
    errors: list[str]


class LeetCodeBackfillResult(BaseModel):
    """Result of a LeetCode topic backfill run using public API."""

    problems_processed: int
    problems_skipped: int
    topics_created: int
    topic_links_created: int
    failed: int


@router.post(
    "/backfill-codeforces-topics",
    response_model=BackfillResult,
    summary="Backfill Codeforces topic tags for existing problems",
)
def backfill_codeforces_topics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BackfillResult:
    """Populate Topic / ProblemTopic rows for existing Codeforces problems.

    Fetches the full Codeforces problem list (single API request) and inserts
    tag data for any local Codeforces problem that has no topics yet.

    This is idempotent — re-running it is harmless.
    """
    # ------------------------------------------------------------------ #
    # 1. Fetch all Codeforces problems with tags (single API call)
    # ------------------------------------------------------------------ #
    try:
        response = httpx.get(_CF_PROBLEMS_URL, timeout=30.0)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
    except httpx.HTTPError as exc:
        logger.error("Codeforces API error during backfill: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Codeforces API: {exc}",
        ) from exc

    if data.get("status") != "OK":
        comment = data.get("comment", "Unknown error")
        raise HTTPException(
            status_code=502,
            detail=f"Codeforces API returned non-OK status: {comment}",
        )

    remote_problems: list[dict[str, Any]] = data.get("result", {}).get("problems", [])
    if not remote_problems:
        raise HTTPException(
            status_code=502,
            detail="Codeforces API returned an empty problem list.",
        )

    # Build a fast lookup: platform_problem_id -> tags list
    remote_tag_map: dict[str, list[str]] = {}
    for p in remote_problems:
        contest_id = p.get("contestId")
        index = p.get("index", "")
        tags: list[str] = p.get("tags", [])
        if contest_id is not None and index:
            pid = f"{contest_id}-{index}"
            remote_tag_map[pid] = tags

    # ------------------------------------------------------------------ #
    # 2. Load all existing Codeforces problems from the DB
    # ------------------------------------------------------------------ #
    local_problems: list[Problem] = (
        db.query(Problem)
        .filter(Problem.platform == Platform.CODEFORCES)
        .all()
    )

    # ------------------------------------------------------------------ #
    # 3. For each local problem, check which already have topics
    # ------------------------------------------------------------------ #
    tagged_problem_ids: set[int] = set(
        row.problem_id
        for row in db.query(ProblemTopic.problem_id)
        .filter(
            ProblemTopic.problem_id.in_([p.id for p in local_problems])
        )
        .distinct()
        .all()
    )

    # ------------------------------------------------------------------ #
    # 4. Insert Topic + ProblemTopic for problems that have no tags yet
    # ------------------------------------------------------------------ #
    problems_inspected = 0
    problems_already_tagged = 0
    problems_tagged_now = 0
    topics_created = 0
    topic_links_created = 0
    errors: list[str] = []

    # Cache topic name -> Topic ORM object to avoid redundant DB lookups
    topic_cache: dict[str, Topic] = {}

    for problem in local_problems:
        problems_inspected += 1

        if problem.id in tagged_problem_ids:
            problems_already_tagged += 1
            continue

        tags = remote_tag_map.get(problem.platform_problem_id, [])
        if not tags:
            # Problem not in Codeforces list (rare — gym/practice)
            continue

        problem_got_tags = False

        for tag_name in tags:
            if not tag_name:
                continue

            # Get or create Topic
            if tag_name in topic_cache:
                topic = topic_cache[tag_name]
            else:
                topic = db.query(Topic).filter(Topic.name == tag_name).first()
                if topic is None:
                    topic = Topic(name=tag_name)
                    db.add(topic)
                    try:
                        db.flush()
                        topics_created += 1
                    except IntegrityError:
                        db.rollback()
                        topic = db.query(Topic).filter(Topic.name == tag_name).first()
                        if topic is None:
                            errors.append(f"Could not resolve topic: {tag_name}")
                            continue
                topic_cache[tag_name] = topic

            # Create ProblemTopic link
            link = ProblemTopic(problem_id=problem.id, topic_id=topic.id)
            db.add(link)
            try:
                db.flush()
                topic_links_created += 1
                problem_got_tags = True
            except IntegrityError:
                db.rollback()
                # Link already exists — that is fine

        if problem_got_tags:
            problems_tagged_now += 1

    db.commit()

    logger.info(
        "Codeforces topic backfill complete: inspected=%d already_tagged=%d "
        "tagged_now=%d topics_created=%d links_created=%d errors=%d",
        problems_inspected,
        problems_already_tagged,
        problems_tagged_now,
        topics_created,
        topic_links_created,
        len(errors),
    )

    return BackfillResult(
        problems_inspected=problems_inspected,
        problems_already_tagged=problems_already_tagged,
        problems_tagged_now=problems_tagged_now,
        topics_created=topics_created,
        topic_links_created=topic_links_created,
        errors=errors[:50],  # Cap to avoid huge responses
    )


@router.post(
    "/backfill-leetcode-topics",
    response_model=LeetCodeBackfillResult,
    summary="Backfill LeetCode topic tags using public API (no authentication required)",
)
def backfill_leetcode_topics(
    profile_id: int = Query(..., gt=0, description="LeetCode PlatformProfile ID"),
    max_problems: int | None = Query(
        None,
        gt=0,
        description=(
            "Hard cap on problems to process. "
            "Omit for full backfill; use 10 for a smoke test."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LeetCodeBackfillResult:
    """Backfill topic tags for locally stored LeetCode problems using public API.

    **No authentication required**

    This endpoint uses LeetCode's public GraphQL API to fetch problem details
    including topic tags. It does NOT require LEETCODE_SESSION or LEETCODE_CSRFTOKEN.

    **Process**

    1. Finds all LeetCode problems the user has solved based on locally stored
       submissions (limited to recent syncs)
    2. For each problem without existing topics, fetches problem details via public API
    3. Creates missing Topic and ProblemTopic relationships
    4. Skips problems that already have topics (idempotent)

    **Important Limitations**

    - This is a LOCAL-DATA backfill only. It only processes problems already stored
      in CodePulse from recent syncs.
    - It does NOT discover or backfill historical solved problems that are not in
      the local database.
    - For complete LeetCode topic analytics, the system uses profile-level
      ``tagProblemCounts`` from the public profile API, not this backfill.
    - Normal LeetCode sync is NOT affected by this endpoint.

    **Safety**

    - Uses public unauthenticated LeetCode API
    - Existing Problem rows are reused, never duplicated
    - Problems that already have topic links are skipped (idempotent)
    - A single failed problem does not abort the entire backfill
    - Use ``max_problems=10`` for a smoke test before the full run
    """
    service = LeetCodeSyncService(db)

    try:
        raw = service.backfill_leetcode_topics(
            profile_id=profile_id,
            user_id=current_user.id,
            max_problems=max_problems,
        )
    except PlatformProfileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProfileAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LeetCodeSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return LeetCodeBackfillResult(**raw)
