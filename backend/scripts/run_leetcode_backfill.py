"""
LeetCode topic backfill — standalone CLI script.

Run from the ``backend/`` directory:

    # Smoke test (10 problems):
    python scripts/run_leetcode_backfill.py --max-problems 10

    # Full backfill:
    python scripts/run_leetcode_backfill.py

    # Target a specific profile ID (use --profile-id if you have more than one):
    python scripts/run_leetcode_backfill.py --profile-id 9

This script uses LeetCode's public GraphQL API - no authentication required.
It fetches problem details including topic tags for locally stored solved problems.

**Important Limitations**

- This is a LOCAL-DATA backfill only. It only processes problems already stored
  in CodePulse from recent syncs.
- It does NOT discover or backfill historical solved problems that are not in
  the local database.
- For complete LeetCode topic analytics, the system uses profile-level
  ``tagProblemCounts`` from the public profile API, not this backfill.
"""

import argparse
import os
import sys

# Make the ``app`` package importable when running from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.enums import Platform
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.services.leetcode_sync_service import LeetCodeSyncError, LeetCodeSyncService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill LeetCode topic tags for all solved problems.",
    )
    parser.add_argument(
        "--profile-id",
        type=int,
        default=None,
        help=(
            "CodePulse LeetCode PlatformProfile.id.  "
            "Defaults to the first LeetCode profile found in the DB."
        ),
    )
    parser.add_argument(
        "--max-problems",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Process at most N solved problems (useful for smoke-testing).  "
            "Omit to run the full backfill."
        ),
    )
    return parser.parse_args()


def pick_profile(db, profile_id: int | None) -> PlatformProfile:
    """Return the target LeetCode PlatformProfile."""
    if profile_id is not None:
        profile = (
            db.query(PlatformProfile)
            .filter(
                PlatformProfile.id == profile_id,
                PlatformProfile.platform == Platform.LEETCODE,
            )
            .first()
        )
        if profile is None:
            print(
                f"[ERROR] No LeetCode profile with id={profile_id} found in DB.",
                file=sys.stderr,
            )
            sys.exit(1)
        return profile

    # Auto-select: use the first (and usually only) LeetCode profile.
    profiles = (
        db.query(PlatformProfile)
        .filter(PlatformProfile.platform == Platform.LEETCODE)
        .all()
    )

    if not profiles:
        print(
            "[ERROR] No LeetCode profiles found in the database.  "
            "Sync a LeetCode profile first.",
            file=sys.stderr,
        )
        sys.exit(1)

    if len(profiles) > 1:
        print(
            "Multiple LeetCode profiles found.  "
            "Pass --profile-id to select one:",
        )
        for p in profiles:
            print(f"  id={p.id}  username={p.username}")
        sys.exit(1)

    return profiles[0]


def print_db_summary(db) -> None:
    """Print a post-backfill summary of LeetCode problem and topic counts."""
    print()
    print("=" * 60)
    print("  Post-backfill DB summary")
    print("=" * 60)

    total_lc = (
        db.query(Problem)
        .filter(Problem.platform == Platform.LEETCODE)
        .count()
    )
    print(f"  LeetCode Problem rows           : {total_lc}")

    with_topics = (
        db.query(ProblemTopic.problem_id)
        .join(Problem, Problem.id == ProblemTopic.problem_id)
        .filter(Problem.platform == Platform.LEETCODE)
        .distinct()
        .count()
    )
    print(f"  LeetCode problems with topics   : {with_topics}")

    total_links = (
        db.query(ProblemTopic)
        .join(Problem, Problem.id == ProblemTopic.problem_id)
        .filter(Problem.platform == Platform.LEETCODE)
        .count()
    )
    print(f"  LeetCode ProblemTopic links     : {total_links}")
    print("=" * 60)


def main() -> None:
    args = parse_args()

    db = SessionLocal()

    try:
        profile = pick_profile(db, args.profile_id)
        print(
            f"Target profile: id={profile.id}  "
            f"username={profile.username}  "
            f"problems_solved={profile.problems_solved}"
        )

        if args.max_problems:
            print(f"Smoke-test mode: processing at most {args.max_problems} problems.")

        # Use user_id = profile.user_id so the ownership check in
        # _get_platform_profile() passes (CLI bypasses HTTP auth).
        service = LeetCodeSyncService(db)
        result = service.backfill_leetcode_topics(
            profile_id=profile.id,
            user_id=profile.user_id,
            max_problems=args.max_problems,
        )

        # Print results
        print()
        print("=" * 60)
        print("  Backfill Results")
        print("=" * 60)
        print(f"  Problems processed      : {result['problems_processed']}")
        print(f"  Problems skipped        : {result['problems_skipped']}")
        print(f"  Topics created          : {result['topics_created']}")
        print(f"  Topic links created     : {result['topic_links_created']}")
        print(f"  Failed                  : {result['failed']}")
        print("=" * 60)

        # Print DB-level verification.
        print_db_summary(db)

        # Exit 0 only if we actually processed something useful.
        if result["failed"] > 0 and result["problems_processed"] == 0:
            sys.exit(1)

    except LeetCodeSyncError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Backfill cancelled by user.", file=sys.stderr)
        db.rollback()
        sys.exit(130)
    finally:
        db.close()


if __name__ == "__main__":
    main()
