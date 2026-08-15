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
from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.enums import Difficulty, Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.rating_history import RatingHistory
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
        # Cache for problem difficulties to avoid repeated API calls
        self._difficulty_cache: dict[str, Difficulty] = {}

    def get_supported_platform(self) -> Platform:
        """Return LeetCode as the supported platform."""
        return Platform.LEETCODE

    def sync_profile(
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
            remote_rating_history = self._fetch_remote_rating_history(profile.username)

            # Update profile information
            self._update_profile(profile, remote_profile)

            # Sync submissions
            problems_created = 0
            submissions_created = 0
            submissions_skipped = 0
            submissions_fetched = len(remote_submissions)
            rating_history_created = 0
            participations_created = 0
            contests_created = 0

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

            # Sync rating history and contest participation
            for rating_data in remote_rating_history:
                (
                    contest_created,
                    rating_created,
                    participation_created,
                ) = self._sync_rating_event(
                    profile=profile,
                    rating_data=rating_data,
                )

                contests_created += int(contest_created)
                rating_history_created += int(rating_created)
                participations_created += int(participation_created)

            # Update aggregates
            self.db.flush()

            profile.problems_solved = self._count_solved_problems(profile.id)
            # contests_attended is already set in _update_profile from API data
            
            # Calculate max rating from history if available
            if rating_history_created > 0:
                max_rating = self._calculate_max_rating(profile.id)
                if max_rating and max_rating > (profile.max_rating or 0):
                    profile.max_rating = max_rating

            synced_at = datetime.now(timezone.utc)
            profile.last_synced_at = synced_at

            self.db.commit()

            return SyncResult(
                profile_id=profile.id,
                platform=Platform.LEETCODE,
                problems_created=problems_created,
                contests_created=contests_created,
                submissions_created=submissions_created,
                submissions_skipped=submissions_skipped,
                submissions_fetched=submissions_fetched,
                rating_history_created=rating_history_created,
                contest_participations_created=participations_created,
                problems_solved=profile.problems_solved,
                contests_attended=profile.contests_attended,
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

    def _fetch_remote_rating_history(self, username: str) -> list[dict[str, Any]]:
        """Fetch LeetCode contest rating history."""
        rating_history = self._call_leetcode_api(
            self.client.fetch_rating_history,
            username,
        )
        return rating_history if isinstance(rating_history, list) else []

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
            rating = contest_data.get("rating")
            # Convert float rating to int for database compatibility
            if rating is not None:
                profile.current_rating = int(rating)
            
            # Use global ranking as rank
            ranking = contest_data.get("globalRanking")
            if ranking is not None:
                profile.rank = f"Rank {ranking}"
            
            # Use attended contests count
            attended_count = contest_data.get("attendedContestsCount")
            if attended_count is not None:
                profile.contests_attended = int(attended_count)
        
        # Extract problems solved from submitStats
        submit_stats = remote_profile.get("submitStats", {})
        ac_submissions = submit_stats.get("acSubmissionNum", [])
        
        # Count total accepted problems (all difficulties)
        total_solved = 0
        for difficulty_data in ac_submissions:
            if difficulty_data.get("difficulty") == "All":
                total_solved = difficulty_data.get("count", 0)
                break
        
        # Assign the calculated solved count to profile
        profile.problems_solved = total_solved
        
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
        
        # Try to get difficulty from submission data first
        difficulty = self._get_difficulty_from_submission(submission_data, title_slug)
        
        problem = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id=platform_problem_id,
            title=title,
            slug=self._generate_slug(title_slug, title),
            problem_url=f"https://leetcode.com/problems/{title_slug}/",
            difficulty=difficulty,
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

    def _get_difficulty_from_submission(
        self,
        submission_data: dict[str, Any],
        title_slug: str,
    ) -> Difficulty:
        """
        Get problem difficulty from submission data or fetch it.
        
        Uses a cache to avoid repeated API calls for the same problem.
        """
        # Check cache first
        if title_slug in self._difficulty_cache:
            return self._difficulty_cache[title_slug]
        
        # Try to get difficulty from submission data
        submission_difficulty = submission_data.get("difficulty")
        if submission_difficulty:
            difficulty = self._map_leetcode_difficulty(submission_difficulty)
            self._difficulty_cache[title_slug] = difficulty
            return difficulty
        
        # If not in submission data, try to fetch from problem details API
        try:
            problem_details = self.client.fetch_problem_details(title_slug)
            if problem_details:
                api_difficulty = problem_details.get("difficulty")
                if api_difficulty:
                    difficulty = self._map_leetcode_difficulty(api_difficulty)
                    self._difficulty_cache[title_slug] = difficulty
                    return difficulty
        except Exception as e:
            logger.warning("Failed to fetch difficulty for %s: %s", title_slug, e)
        
        # Default fallback if we can't determine difficulty
        logger.info("Could not determine difficulty for %s, using MEDIUM as fallback", title_slug)
        self._difficulty_cache[title_slug] = Difficulty.MEDIUM
        return Difficulty.MEDIUM

    @staticmethod
    def _map_leetcode_difficulty(leetcode_difficulty: str) -> Difficulty:
        """Map LeetCode difficulty string to CodePulse Difficulty enum."""
        difficulty_map = {
            "Easy": Difficulty.EASY,
            "Medium": Difficulty.MEDIUM,
            "Hard": Difficulty.HARD,
        }
        return difficulty_map.get(leetcode_difficulty, Difficulty.MEDIUM)

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

    def _calculate_max_rating(self, profile_id: int) -> int | None:
        """Calculate maximum rating from rating history."""
        from sqlalchemy import func
        
        max_rating = self.db.query(
            func.max(RatingHistory.rating)
        ).filter(
            RatingHistory.profile_id == profile_id
        ).scalar()
        
        return int(max_rating) if max_rating else None

    def _sync_rating_event(
        self,
        profile: PlatformProfile,
        rating_data: dict[str, Any],
    ) -> tuple[bool, bool, bool]:
        """
        Synchronize one LeetCode rating event.

        Returns:
            (contest_created, rating_history_created, participation_created)
        """
        contest_info = rating_data.get("contest", {})
        if not contest_info:
            # No contest info, skip this rating event
            return False, False, False

        # Generate a deterministic contest ID from title + start time
        contest_title = contest_info.get("title", "Unknown")
        start_time = contest_info.get("startTime", 0)
        platform_contest_id = f"lc-{contest_title}-{start_time}"

        # Get or create contest
        contest, contest_created = self._get_or_create_contest(
            platform_contest_id,
            contest_info,
        )

        if contest is None:
            return False, False, False

        # Extract rating data
        rating = rating_data.get("rating")
        if rating is None:
            return False, False, False

        # Convert to int for database compatibility
        new_rating = int(rating)
        
        # Calculate rating change (we don't have old rating, so estimate from previous)
        # For LeetCode, we'll set rating_change to 0 if we can't determine it
        rating_change = 0

        # Rating history
        rating_created = False
        existing_rating = self.rating_history.get_by_profile_contest(
            profile.id,
            contest.id,
        )

        recorded_at = self._parse_timestamp(rating_data.get("finishTimeInSeconds"))

        if existing_rating is None:
            rating = RatingHistory(
                profile_id=profile.id,
                contest_id=contest.id,
                rating=new_rating,
                rating_change=rating_change,
                recorded_at=recorded_at,
            )

            try:
                self._safe_add_and_flush(rating)
                rating_created = True
            except IntegrityError:
                existing_rating = self.rating_history.get_by_profile_contest(
                    profile.id,
                    contest.id,
                )
                if existing_rating is None:
                    raise LeetCodeSyncError(
                        "Failed to create rating history due to database conflict."
                    ) from None
        else:
            existing_rating.rating = new_rating
            existing_rating.rating_change = rating_change
            existing_rating.recorded_at = recorded_at

        # Contest participation
        participation = self.contest_participations.get_profile_contest(
            profile.id,
            contest.id,
        )

        participation_created = participation is None
        rank = rating_data.get("ranking")
        problems_solved = rating_data.get("problemsSolved", 0)

        if participation is None:
            participation = ContestParticipation(
                profile_id=profile.id,
                contest_id=contest.id,
                rank=int(rank) if rank else None,
                old_rating=None,  # LeetCode doesn't provide old rating
                new_rating=new_rating,
                rating_change=rating_change,
                solved=int(problems_solved) if problems_solved else 0,
                penalty=None,
            )

            try:
                self._safe_add_and_flush(participation)
            except IntegrityError:
                participation = self.contest_participations.get_profile_contest(
                    profile.id,
                    contest.id,
                )
                if participation is None:
                    raise LeetCodeSyncError(
                        "Failed to create contest participation due to database conflict."
                    ) from None
                participation_created = False
                participation.rank = int(rank) if rank else None
                participation.new_rating = new_rating
                participation.rating_change = rating_change
                participation.solved = int(problems_solved) if problems_solved else 0
        else:
            participation.rank = int(rank) if rank else None
            participation.new_rating = new_rating
            participation.rating_change = rating_change
            participation.solved = int(problems_solved) if problems_solved else 0

        return contest_created, rating_created, participation_created

    def _get_or_create_contest(
        self,
        platform_contest_id: str,
        contest_info: dict[str, Any],
    ) -> tuple[Contest | None, bool]:
        """Get or create a LeetCode contest."""
        # Check cache first
        existing = self.contests.get_by_platform_contest_id(
            Platform.LEETCODE,
            platform_contest_id,
        )

        if existing is not None:
            return existing, False

        # Create new contest
        title = contest_info.get("title", "Unknown Contest")
        start_time = contest_info.get("startTime")

        contest = Contest(
            platform=Platform.LEETCODE,
            platform_contest_id=platform_contest_id,
            title=title,
            contest_url=f"https://leetcode.com/contest/",  # LeetCode contest URLs vary
            start_time=self._parse_timestamp(start_time) if start_time else datetime.now(timezone.utc),
            duration_minutes=90,  # Default duration for LeetCode contests (API doesn't provide this)
        )

        try:
            self._safe_add_and_flush(contest)
            return contest, True
        except IntegrityError:
            existing = self.contests.get_by_platform_contest_id(
                Platform.LEETCODE,
                platform_contest_id,
            )
            if existing is None:
                raise LeetCodeSyncError(
                    "Failed to create contest due to database conflict."
                ) from None
            return existing, False

    @staticmethod
    def _generate_contest_slug(title: str, platform_contest_id: str) -> str:
        """Generate a unique slug for a LeetCode contest."""
        normalized = unicodedata.normalize("NFKD", title)
        ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
        slugified = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")
        
        return f"leetcode-{slugified or 'contest'}"[:255]
