"""LeetCode platform synchronization service."""

import logging
import re
import unicodedata
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations.leetcode_client import (
    LeetCodeClient,
    LeetCodeUserNotFoundError,
)
from app.models.enums import Difficulty, Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.submission import Submission
from app.schemas.sync import SyncResult
from app.services.base_sync_service import (
    BaseSyncService,
    PlatformSyncError,
    PlatformUsernameNotFoundError,
)

logger = logging.getLogger(__name__)


class LeetCodeSyncError(PlatformSyncError):
    """Base exception for LeetCode synchronization errors."""


class LeetCodeUsernameNotFoundError(PlatformUsernameNotFoundError):
    """Raised when a LeetCode username does not exist."""


class LeetCodeSyncService(BaseSyncService):
    """
    Synchronize a LeetCode platform profile into CodePulse.
    
    LeetCode Limitations:
    - Public API provides limited submission history (recent submissions only)
    - Contest data is per-user and not comprehensive
    - Full history requires authentication (not implemented)
    
    The synchronization is idempotent - running it multiple times
    will not create duplicate problems or submissions.
    """

    _STATUS_MAP = {
        "Accepted": SubmissionStatus.ACCEPTED,
        "Wrong Answer": SubmissionStatus.WRONG_ANSWER,
        "Time Limit Exceeded": SubmissionStatus.TIME_LIMIT,
        "Memory Limit Exceeded": SubmissionStatus.MEMORY_LIMIT,
        "Runtime Error": SubmissionStatus.RUNTIME_ERROR,
        "Compile Error": SubmissionStatus.COMPILE_ERROR,
    }

    def __init__(
        self,
        db: Session,
        client: LeetCodeClient | None = None,
    ) -> None:
        super().__init__(db)
        self.client = client or LeetCodeClient()

    def get_supported_platform(self) -> Platform:
        """Return LeetCode as the supported platform."""
        return Platform.LEETCODE

    def sync_leetcode_profile(
        self,
        profile_id: int,
        user_id: int,
    ) -> SyncResult:
        """
        Synchronize one LeetCode platform profile.
        
        All database writes are kept in the current transaction and
        committed only after the complete synchronization succeeds.
        """

        try:
            profile = self._get_platform_profile(profile_id, user_id)

            # Fetch remote data
            remote_profile = self._as_mapping(
                self._fetch_remote_profile(profile.username),
                "LeetCode profile",
            )

            remote_submissions = self._fetch_remote_submissions(profile.username)

            # Update profile information
            self._update_profile(profile, remote_profile)

            # Sync submissions
            problems_created = 0
            submissions_created = 0
            submissions_skipped = 0
            submissions_fetched = len(remote_submissions)

            for submission_data in remote_submissions:
                problem_created, submission_created, submission_skipped_flag = (
                    self._sync_submission(
                        profile=profile,
                        submission_data=submission_data,
                    )
                )

                problems_created += int(problem_created)
                submissions_created += int(submission_created)
                submissions_skipped += int(submission_skipped_flag)

            # Update aggregates
            self.db.flush()

            profile.problems_solved = self._count_solved_problems(profile.id)
            profile.contests_attended = 0  # LeetCode contests not tracked yet

            synced_at = datetime.now(timezone.utc)
            profile.last_synced_at = synced_at

            self.db.commit()

            return SyncResult(
                profile_id=profile.id,
                platform=Platform.LEETCODE,
                problems_created=problems_created,
                contests_created=0,
                submissions_created=submissions_created,
                submissions_skipped=submissions_skipped,
                submissions_fetched=submissions_fetched,
                rating_history_created=0,
                contest_participations_created=0,
                problems_solved=profile.problems_solved,
                contests_attended=0,
                synced_at=synced_at,
            )

        except Exception:
            self.db.rollback()
            raise

    def _fetch_remote_profile(self, username: str) -> Any:
        """Fetch LeetCode profile data."""
        try:
            return self._call_leetcode_api(
                self.client.fetch_profile,
                username,
            )
        except LeetCodeUserNotFoundError as exc:
            raise LeetCodeUsernameNotFoundError(
                f"LeetCode user '{username}' was not found."
            ) from exc

    def _fetch_remote_submissions(self, username: str) -> list[dict[str, Any]]:
        """Fetch recent LeetCode submissions."""
        submissions = self._call_leetcode_api(
            self.client.fetch_submissions,
            username,
            100,
        )
        return submissions if isinstance(submissions, list) else []

    @staticmethod
    def _call_leetcode_api(fetch_fn: Any, *args: Any) -> Any:
        """Call LeetCode API and handle errors."""
        try:
            return fetch_fn(*args)
        except LeetCodeUserNotFoundError:
            raise
        except RuntimeError as exc:
            logger.error(
                "LeetCode API call failed: fn=%s args=%r error=%s",
                getattr(fetch_fn, "__name__", repr(fetch_fn)),
                args,
                exc,
            )
            raise LeetCodeSyncError(str(exc)) from exc

    def _update_profile(
        self,
        profile: PlatformProfile,
        remote_profile: Mapping[str, Any],
    ) -> None:
        """Update profile with data from LeetCode API."""
        
        # Extract profile data
        profile_data = remote_profile.get("profile", {})
        contest_data = remote_profile.get("userContestRanking")
        
        # Update contest rating if available
        if contest_data:
            profile.current_rating = contest_data.get("rating")
            # LeetCode doesn't provide max rating, use current as max
            if profile.current_rating:
                profile.max_rating = max(
                    profile.max_rating or 0,
                    profile.current_rating
                )
            
            # Use global ranking as rank
            ranking = contest_data.get("globalRanking")
            if ranking:
                profile.rank = f"Rank {ranking}"
        
        # Extract problems solved from submitStats
        submit_stats = remote_profile.get("submitStats", {})
        ac_submissions = submit_stats.get("acSubmissionNum", [])
        
        # Count total accepted problems (all difficulties)
        total_solved = 0
        for difficulty_data in ac_submissions:
            if difficulty_data.get("difficulty") == "All":
                total_solved = difficulty_data.get("count", 0)
                break
        
        # Update profile URL
        profile.profile_url = f"https://leetcode.com/{profile.username}"
        profile.is_connected = True

    def _sync_submission(
        self,
        profile: PlatformProfile,
        submission_data: dict[str, Any],
    ) -> tuple[bool, bool, bool]:
        """
        Synchronize one LeetCode submission.
        
        Returns:
            (problem_created, submission_created, submission_skipped)
        """
        
        # Extract submission ID from timestamp (LeetCode doesn't provide unique ID)
        timestamp_str = str(submission_data.get("timestamp", ""))
        title_slug = submission_data.get("titleSlug", "unknown")
        platform_submission_id = f"{timestamp_str}-{title_slug}"

        # Idempotency check
        existing = self.submissions.get_by_platform_submission_id(
            profile.id,
            platform_submission_id,
        )

        if existing is not None:
            return False, False, True

        # Get or create problem
        problem, problem_created = self._get_or_create_problem(submission_data)

        # Create submission
        submission = Submission(
            profile_id=profile.id,
            problem_id=problem.id,
            contest_id=None,  # LeetCode submissions don't track contest
            platform_submission_id=platform_submission_id,
            submitted_at=self._parse_timestamp(
                submission_data.get("timestamp")
            ),
            language=submission_data.get("lang", "Unknown"),
            status=self._map_status(submission_data.get("statusDisplay")),
        )

        try:
            self._safe_add_and_flush(submission)
            return problem_created, True, False
        except IntegrityError:
            # Race condition - check if it exists now
            existing = self.submissions.get_by_platform_submission_id(
                profile.id,
                platform_submission_id,
            )
            if existing is None:
                raise LeetCodeSyncError(
                    "Failed to create submission due to database conflict."
                ) from None
            return False, False, True

    def _get_or_create_problem(
        self,
        submission_data: dict[str, Any],
    ) -> tuple[Problem, bool]:
        """Get or create a LeetCode problem."""
        
        title_slug = submission_data.get("titleSlug", "")
        if not title_slug:
            raise ValueError("LeetCode submission missing titleSlug")

        platform_problem_id = title_slug

        # Check if problem exists
        existing = self.problems.get_by_platform_problem_id(
            Platform.LEETCODE,
            platform_problem_id,
        )

        if existing is not None:
            return existing, False

        # Create new problem
        title = submission_data.get("title", title_slug)
        
        problem = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id=platform_problem_id,
            title=title,
            slug=self._generate_slug(title_slug, title),
            problem_url=f"https://leetcode.com/problems/{title_slug}/",
            difficulty=Difficulty.MEDIUM,  # Default, actual difficulty needs separate API call
            acceptance_rate=None,
        )

        try:
            self._safe_add_and_flush(problem)
            return problem, True
        except IntegrityError:
            # Race condition - fetch existing
            existing = self.problems.get_by_platform_problem_id(
                Platform.LEETCODE,
                platform_problem_id,
            )
            if existing is None:
                raise LeetCodeSyncError(
                    "Failed to create problem due to database conflict."
                ) from None
            return existing, False

    @staticmethod
    def _generate_slug(title_slug: str, title: str) -> str:
        """Generate a unique slug for a LeetCode problem."""
        normalized = unicodedata.normalize("NFKD", title)
        ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
        slugified = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
        
        return f"leetcode-{title_slug}-{slugified or 'problem'}"[:255]

    @classmethod
    def _map_status(cls, status_display: str | None) -> SubmissionStatus:
        """Map LeetCode status to CodePulse SubmissionStatus."""
        if not status_display:
            return SubmissionStatus.RUNTIME_ERROR

        return cls._STATUS_MAP.get(
            status_display,
            SubmissionStatus.RUNTIME_ERROR,
        )

    @staticmethod
    def _parse_timestamp(timestamp: Any) -> datetime:
        """Parse LeetCode timestamp (Unix timestamp as string or int)."""
        if timestamp is None:
            return datetime.now(timezone.utc)

        try:
            ts = int(timestamp)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError):
            return datetime.now(timezone.utc)
