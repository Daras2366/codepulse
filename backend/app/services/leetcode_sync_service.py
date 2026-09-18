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
from app.models.topic import Topic
from app.models.problem_topic import ProblemTopic
from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.schemas.sync import SyncResult
from app.services.base_sync_service import (
    BaseSyncService,
    PlatformSyncError,
    PlatformUsernameNotFoundError,
)
from app.repositories.topic_repository import TopicRepository
from app.models.platform_topic_stat import PlatformTopicStat

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

            # Sync rating history and contest participation.
            # LeetCode may not return contest history in chronological order,
            # so sort by contest start time before calculating rating changes.
            remote_rating_history = sorted(
                remote_rating_history,
                key=lambda item: int(
                    (item.get("contest") or {}).get("startTime") or 0
                ),
            )

            previous_rating: int | None = None

            for rating_data in remote_rating_history:
                # Only include contests the user actually attended.
                if rating_data.get("attended") is False:
                    continue

                new_rating = rating_data.get("rating")

                if new_rating is None:
                    continue

                new_rating = int(new_rating)

                rating_change = (
                    0
                    if previous_rating is None
                    else new_rating - previous_rating
                )

                (
                    contest_created,
                    rating_created,
                    participation_created,
                ) = self._sync_rating_event(
                    profile=profile,
                    rating_data=rating_data,
                    old_rating=previous_rating,
                    rating_change=rating_change,
                )

                contests_created += int(contest_created)
                rating_history_created += int(rating_created)
                participations_created += int(participation_created)

                previous_rating = new_rating

            # Update aggregates
            self.db.flush()

            # problems_solved is already set in _update_profile from API data
            # Do NOT override with database count since we only sync recent submissions
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
        
    def _sync_topic_stats(
        self,
        profile: PlatformProfile,
        tag_problem_counts: dict,
    ) -> None:
        """Persist LeetCode's user-level solved counts by topic."""

        levels = (
            "advanced",
            "intermediate",
            "fundamental",
        )

        seen_slugs: set[str] = set()

        for level in levels:
            for tag in tag_problem_counts.get(level, []):
                topic_name = tag.get("tagName")
                topic_slug = tag.get("tagSlug")
                solved_count = tag.get("problemsSolved", 0)

                if not topic_name or not topic_slug:
                    continue

                seen_slugs.add(topic_slug)

                existing = (
                    self.db.query(PlatformTopicStat)
                    .filter(
                        PlatformTopicStat.profile_id == profile.id,
                        PlatformTopicStat.topic_slug == topic_slug,
                    )
                    .first()
                )

                if existing:
                    existing.topic_name = topic_name
                    existing.solved_count = int(solved_count or 0)
                else:
                    self.db.add(
                        PlatformTopicStat(
                            profile_id=profile.id,
                            topic_name=topic_name,
                            topic_slug=topic_slug,
                            solved_count=int(solved_count or 0),
                        )
                    )

        # Remove stale tags if LeetCode no longer reports them.
        (
            self.db.query(PlatformTopicStat)
            .filter(
                PlatformTopicStat.profile_id == profile.id,
                ~PlatformTopicStat.topic_slug.in_(seen_slugs),
            )
            .delete(synchronize_session=False)
        )

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
        """Fetch LeetCode submission history using the paginated endpoint.

        Attempts ``submissionList`` with offset/limit pagination first (up to
        1 000 submissions across all statuses).  Falls back to the bounded
        ``recentAcSubmissionList`` (≤ 100 accepted-only) if paginated access
        is blocked for the given username.
        """
        submissions = self._call_leetcode_api(
            self.client.fetch_submissions_paginated,
            username,
        )
        result = submissions if isinstance(submissions, list) else []
        logger.info(
            "Fetched %d submissions for %s (paginated or fallback)",
            len(result),
            username,
        )
        return result

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
        
        # Extract solved problem counts from LeetCode submitStats.
        #
        # LeetCode returns something like:
        # [
        #     {"difficulty": "All", "count": 362},
        #     {"difficulty": "Easy", "count": 120},
        #     {"difficulty": "Medium", "count": 210},
        #     {"difficulty": "Hard", "count": 32},
        # ]
        #
        # These are profile-level totals and are more reliable than
        # counting our locally stored submissions because LeetCode's
        # public recentSubmissionList is not the user's full history.

        submit_stats = remote_profile.get("submitStats", {})
        ac_submissions = submit_stats.get("acSubmissionNum", [])

        solved_counts = {
            "All": 0,
            "Easy": 0,
            "Medium": 0,
            "Hard": 0,
        }

        for difficulty_data in ac_submissions:
            difficulty = difficulty_data.get("difficulty")
            count = difficulty_data.get("count", 0)

            if difficulty in solved_counts:
                solved_counts[difficulty] = int(count or 0)

        profile.problems_solved = solved_counts["All"]
        profile.solved_easy = solved_counts["Easy"]
        profile.solved_medium = solved_counts["Medium"]
        profile.solved_hard = solved_counts["Hard"]
        
        self._sync_topic_stats(
            profile,
            remote_profile.get("tagProblemCounts", {}),
        )
        
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

        # Extract submission ID - use actual ID from paginated API if available, otherwise fallback to timestamp+slug
        submission_id = submission_data.get("id")
        if submission_id:
            # Use the actual ID from LeetCode's paginated API
            platform_submission_id = str(submission_id)
        else:
            # Fallback for old API or cases where ID is not available
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
            # Backfill topics for existing problems using public API
            # This is safe because fetch_problem_details uses public unauthenticated endpoint
            self._sync_problem_topics(existing, title_slug)
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
            
            # Persist LeetCode problem topics only for new problems
            # This avoids API request explosion during backfill
            self._sync_problem_topics(problem, title_slug)
            
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

        return problem, True

    def _sync_problem_topics(
        self,
        problem: Problem,
        title_slug: str,
    ) -> None:
        """Sync LeetCode problem topics to Topic and ProblemTopic tables.
        
        Uses the public LeetCode GraphQL API - no authentication required.
        This method is idempotent and can be called for both new and existing problems.
        """
        try:
            problem_details = self.client.fetch_problem_details(title_slug)
            if not problem_details:
                logger.debug("No problem details returned for %s", title_slug)
                return
            
            topic_tags = problem_details.get("topicTags", [])
            if not topic_tags:
                logger.debug("No topic tags returned for %s", title_slug)
                return
            
            topics_added = 0
            for tag_data in topic_tags:
                tag_name = tag_data.get("name")
                if not tag_name:
                    continue
                
                # Get or create topic
                topic = self.topics.get_by_name(tag_name)
                if topic is None:
                    topic = Topic(name=tag_name)
                    try:
                        self._safe_add_and_flush(topic)
                        logger.debug("Created new topic: %s", tag_name)
                    except IntegrityError:
                        # Topic might have been created by another process
                        topic = self.topics.get_by_name(tag_name)
                        if topic is None:
                            continue  # Skip this tag if we can't resolve the conflict
                
                # Create ProblemTopic relationship
                problem_topic = ProblemTopic(
                    problem_id=problem.id,
                    topic_id=topic.id,
                )
                try:
                    self._safe_add_and_flush(problem_topic)
                    topics_added += 1
                except IntegrityError:
                    # Relationship already exists, which is fine
                    pass
            
            if topics_added > 0:
                logger.info("Added %d topic(s) for problem %s", topics_added, title_slug)
                
        except Exception as e:
            logger.warning("Failed to sync topics for %s: %s", title_slug, e)

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
        old_rating: int | None = None,
        rating_change: int = 0,
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

        # Rating history
        rating_created = False
        existing_rating = self.rating_history.get_by_profile_contest(
            profile.id,
            contest.id,
        )

        # finishTimeInSeconds is the contest duration/finish offset,
        # NOT a Unix timestamp. Use the contest start time for the
        # rating-history date.
        recorded_at = contest.start_time

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
                old_rating=old_rating,
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
            participation.old_rating = old_rating
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
    
    
    def fetch_all_solved_problems_with_topics(
        self,
        profile_id: int,
        user_id: int,
        max_problems: int | None = None,
        batch_delay: float = 0.3,
    ) -> dict[str, int]:
        """
        DEPRECATED: Enumerate ALL solved LeetCode problems and persist their topic tags.
        
        This method is deprecated. Use backfill_leetcode_topics() instead, which uses
        the public API and does not require authentication.
        
        This is kept for backwards compatibility but will be removed in a future version.
        """
        logger.warning(
            "fetch_all_solved_problems_with_topics is deprecated. "
            "Use backfill_leetcode_topics() instead."
        )
        
        # Map the old result format to the new one for backwards compatibility
        new_result = self.backfill_leetcode_topics(profile_id, user_id, max_problems)
        
        return {
            "solved_discovered": new_result["problems_processed"] + new_result["problems_skipped"],
            "problems_created": 0,  # New method doesn't create problems, only backfills topics
            "problems_found": new_result["problems_processed"] + new_result["problems_skipped"],
            "topics_created": new_result["topics_created"],
            "topic_links_created": new_result["topic_links_created"],
            "already_tagged": new_result["problems_skipped"],
            "no_topics": 0,  # Not tracked in new method
            "failed": new_result["failed"],
        }

    def backfill_leetcode_topics(
        self,
        profile_id: int,
        user_id: int,
        max_problems: int | None = None,
    ) -> dict[str, int]:
        """
        Backfill topic tags for locally stored LeetCode problems using public API.

        This method finds all LeetCode problems that the user has solved
        based on locally stored submissions (limited to recent syncs) and
        fetches topic tags using the public LeetCode GraphQL API - no
        authentication required.

        **Important Limitations**

        - This is a LOCAL-DATA backfill only. It only processes problems already
          stored in CodePulse from recent syncs.
        - It does NOT discover or backfill historical solved problems that are
          not in the local database.
        - For complete LeetCode topic analytics, the system uses profile-level
          ``tagProblemCounts`` from the public profile API, not this backfill.

        Algorithm:
        1. Get the user's LeetCode profile
        2. Find all LeetCode problems the user has solved (from local submissions)
        3. For each problem without topics, fetch details using public API
        4. Create missing Topic and ProblemTopic relationships
        5. Return statistics about the backfill operation

        This is safe to run multiple times (idempotent).

        Args:
            profile_id: CodePulse LeetCode PlatformProfile.id
            user_id: Authenticated CodePulse user ID (ownership check)
            max_problems: Optional hard cap on problems to process for testing

        Returns:
            dict with keys:
            problems_processed, problems_skipped (already had topics),
            topics_created, topic_links_created, failed
        """
        import time
        
        # Verify profile ownership
        profile = self._get_platform_profile(profile_id, user_id)
        
        if profile.platform != Platform.LEETCODE:
            raise LeetCodeSyncError(
                "The selected profile is not a LeetCode profile."
            )
        
        logger.info("Starting LeetCode topic backfill for profile %s", profile.username)
        
        # Find all LeetCode problems this user has solved
        solved_problems = (
            self.db.query(Problem)
            .join(Submission, Problem.id == Submission.problem_id)
            .filter(
                Submission.profile_id == profile_id,
                Submission.status == SubmissionStatus.ACCEPTED,
                Problem.platform == Platform.LEETCODE,
            )
            .distinct()
            .all()
        )
        
        if max_problems:
            solved_problems = solved_problems[:max_problems]
        
        total_problems = len(solved_problems)
        logger.info("Found %d solved LeetCode problems to process", total_problems)
        
        if total_problems == 0:
            return {
                "problems_processed": 0,
                "problems_skipped": 0,
                "topics_created": 0,
                "topic_links_created": 0,
                "failed": 0,
            }
        
        # Find problems that already have topics
        problems_with_topics = set(
            row.problem_id
            for row in self.db.query(ProblemTopic.problem_id)
            .filter(
                ProblemTopic.problem_id.in_([p.id for p in solved_problems])
            )
            .distinct()
            .all()
        )
        
        result = {
            "problems_processed": 0,
            "problems_skipped": 0,
            "topics_created": 0,
            "topic_links_created": 0,
            "failed": 0,
        }
        
        # Process each problem
        for idx, problem in enumerate(solved_problems, start=1):
            # Log progress every 10 problems
            if idx % 10 == 0 or idx == total_problems:
                logger.info("Processing %d/%d problems", idx, total_problems)
            
            # Skip if already has topics
            if problem.id in problems_with_topics:
                result["problems_skipped"] += 1
                continue
            
            try:
                # Fetch problem details using public API
                title_slug = problem.platform_problem_id
                problem_details = self.client.fetch_problem_details(title_slug)
                
                if not problem_details:
                    logger.debug("No details returned for problem %s", title_slug)
                    result["failed"] += 1
                    continue
                
                topic_tags = problem_details.get("topicTags", [])
                if not topic_tags:
                    logger.debug("No topic tags for problem %s", title_slug)
                    result["problems_processed"] += 1
                    continue
                
                # Process each topic tag
                topics_added_for_problem = 0
                for tag_data in topic_tags:
                    tag_name = tag_data.get("name")
                    if not tag_name:
                        continue
                    
                    # Get or create topic
                    topic = self.topics.get_by_name(tag_name)
                    if topic is None:
                        topic = Topic(name=tag_name)
                        try:
                            self._safe_add_and_flush(topic)
                            result["topics_created"] += 1
                        except IntegrityError:
                            # Topic might have been created concurrently
                            topic = self.topics.get_by_name(tag_name)
                            if topic is None:
                                continue
                    
                    # Create ProblemTopic relationship
                    problem_topic = ProblemTopic(
                        problem_id=problem.id,
                        topic_id=topic.id,
                    )
                    try:
                        self._safe_add_and_flush(problem_topic)
                        result["topic_links_created"] += 1
                        topics_added_for_problem += 1
                    except IntegrityError:
                        # Relationship already exists
                        pass
                
                if topics_added_for_problem > 0:
                    result["problems_processed"] += 1
                    # Add to set so we don't process again if there are duplicates
                    problems_with_topics.add(problem.id)
                
                # Small delay to avoid rate limiting
                if idx % 10 == 0:
                    time.sleep(0.1)
                    
            except Exception as exc:
                logger.warning("Failed to backfill topics for problem %s: %s", 
                             problem.platform_problem_id, exc)
                result["failed"] += 1
        
        self.db.commit()
        
        logger.info(
            "LeetCode topic backfill completed: processed=%d skipped=%d "
            "topics_created=%d links_created=%d failed=%d",
            result["problems_processed"],
            result["problems_skipped"],
            result["topics_created"],
            result["topic_links_created"],
            result["failed"],
        )
        
        return result
