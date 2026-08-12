import logging
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import distinct, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations.codeforces_client import (
    CodeforcesClient,
    CodeforcesUserNotFoundError,
)
from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.enums import Difficulty, Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.repositories.contest_participation_repository import (
    ContestParticipationRepository,
)
from app.repositories.contest_repository import ContestRepository
from app.repositories.platform_profile_repository import (
    PlatformProfileRepository,
)
from app.repositories.problem_repository import ProblemRepository
from app.repositories.rating_history_repository import RatingHistoryRepository
from app.repositories.submission_repository import SubmissionRepository
from app.schemas.sync import SyncResult
from app.services.base import BaseService

logger = logging.getLogger(__name__)


class CodeforcesSyncError(RuntimeError):
    """Base exception for Codeforces synchronization errors."""


class PlatformProfileNotFoundError(CodeforcesSyncError):
    """Raised when the requested platform profile does not exist."""


class UnsupportedPlatformError(CodeforcesSyncError):
    """Raised when the profile is not a Codeforces profile."""


class CodeforcesUsernameNotFoundError(CodeforcesSyncError):
    """Raised when a connected Codeforces handle no longer exists."""


class ProfileAccessDeniedError(CodeforcesSyncError):
    """Raised when the authenticated user does not own the profile."""


class CodeforcesSyncService(BaseService):
    """
    Synchronize a Codeforces platform profile into CodePulse.

    The synchronization is designed to be idempotent:
    running it multiple times should not create duplicate
    problems, contests, submissions, rating history, or
    contest participation records.
    """

    _VERDICT_TO_STATUS = {
        "OK": SubmissionStatus.ACCEPTED,
        "WRONG_ANSWER": SubmissionStatus.WRONG_ANSWER,
        "TIME_LIMIT_EXCEEDED": SubmissionStatus.TIME_LIMIT,
        "MEMORY_LIMIT_EXCEEDED": SubmissionStatus.MEMORY_LIMIT,
        "RUNTIME_ERROR": SubmissionStatus.RUNTIME_ERROR,
        "COMPILATION_ERROR": SubmissionStatus.COMPILE_ERROR,
    }

    def __init__(
        self,
        db: Session,
        client: CodeforcesClient | None = None,
    ) -> None:
        super().__init__(db)

        self.client = client or CodeforcesClient()

        self.platform_profiles = PlatformProfileRepository(db)
        self.problems = ProblemRepository(db)
        self.contests = ContestRepository(db)
        self.submissions = SubmissionRepository(db)
        self.rating_history = RatingHistoryRepository(db)
        self.contest_participations = ContestParticipationRepository(db)

    # ============================================================
    # PUBLIC API
    # ============================================================

    def sync_codeforces_profile(
        self,
        profile_id: int,
        user_id: int,
    ) -> SyncResult:
        """
        Synchronize one Codeforces platform profile.

        All database writes are kept in the current transaction and
        committed only after the complete synchronization succeeds.
        """

        try:
            profile = self._get_codeforces_profile(
                profile_id,
                user_id,
            )

            remote_profile = self._as_mapping(
                self._fetch_remote_profile(profile.username),
                "Codeforces profile",
            )

            remote_submissions = self._as_sequence(
                self._fetch_remote_submissions(profile.username),
                "Codeforces submissions",
            )

            remote_ratings = self._as_sequence(
                self._fetch_remote_rating_history(profile.username),
                "Codeforces rating history",
            )

            remote_contests = self._as_sequence(
                self._fetch_remote_contests(),
                "Codeforces contests",
            )

            contests_by_platform_id: dict[str, Mapping[str, Any]] = {}

            for contest_data in remote_contests:
                contest = self._as_mapping(
                    contest_data,
                    "Codeforces contest",
                )

                contest_id = self._required_int(
                    contest.get("id"),
                    "contest.id",
                )

                contests_by_platform_id[str(contest_id)] = contest

            self._update_profile(
                profile,
                remote_profile,
            )

            # Cache of contests encountered during this sync.
            #
            # Key:
            #     Codeforces contest ID as string
            #
            # Value:
            #     CodePulse Contest object
            contests_cache: dict[str, Contest] = {}

            problems_created = 0
            contests_created = 0
            submissions_created = 0
            submissions_skipped = 0
            rating_history_created = 0
            participations_created = 0

            # ----------------------------------------------------
            # Synchronize submissions
            # ----------------------------------------------------

            for submission_data in remote_submissions:
                (
                    problem_created,
                    contest_created,
                    submission_created,
                    submission_skipped,
                ) = self._sync_submission(
                    profile=profile,
                    submission_data=self._as_mapping(
                        submission_data,
                        "Codeforces submission",
                    ),
                    contests_by_platform_id=contests_by_platform_id,
                    contests_cache=contests_cache,
                )

                problems_created += int(problem_created)
                contests_created += int(contest_created)
                submissions_created += int(submission_created)
                submissions_skipped += int(submission_skipped)

            # ----------------------------------------------------
            # Synchronize rating history and contest participation
            # ----------------------------------------------------

            for rating_data in remote_ratings:
                (
                    contest_created,
                    rating_created,
                    participation_created,
                ) = self._sync_rating_event(
                    profile=profile,
                    rating_data=self._as_mapping(
                        rating_data,
                        "Codeforces rating event",
                    ),
                    contests_by_platform_id=contests_by_platform_id,
                    contests_cache=contests_cache,
                )

                contests_created += int(contest_created)
                rating_history_created += int(rating_created)
                participations_created += int(
                    participation_created
                )

            # Make sure all pending inserts are visible to the
            # aggregate queries below.
            self.db.flush()

            profile.problems_solved = self._count_solved_problems(
                profile.id
            )

            profile.contests_attended = self._count_contests_attended(
                profile.id
            )

            synced_at = datetime.now(timezone.utc)
            profile.last_synced_at = synced_at

            self.db.commit()

            return SyncResult(
                profile_id=profile.id,
                platform=Platform.CODEFORCES,
                problems_created=problems_created,
                contests_created=contests_created,
                submissions_created=submissions_created,
                submissions_skipped=submissions_skipped,
                rating_history_created=rating_history_created,
                contest_participations_created=participations_created,
                problems_solved=profile.problems_solved,
                contests_attended=profile.contests_attended,
                synced_at=synced_at,
            )

        except Exception:
            # All synchronization writes use this shared transaction.
            # If anything fails, discard the complete synchronization.
            self.db.rollback()
            raise

    # ============================================================
    # PROFILE
    # ============================================================

    def _get_codeforces_profile(
        self,
        profile_id: int,
        user_id: int,
    ) -> PlatformProfile:
        profile = self.platform_profiles.get_by_id(profile_id)

        if profile is None:
            raise PlatformProfileNotFoundError(
                f"Platform profile {profile_id} was not found."
            )

        if profile.user_id != user_id:
            raise ProfileAccessDeniedError(
                "You do not have permission to synchronize "
                f"platform profile {profile_id}."
            )

        if profile.platform != Platform.CODEFORCES:
            raise UnsupportedPlatformError(
                f"Platform profile {profile_id} is not a Codeforces profile."
            )

        return profile

    def _fetch_remote_profile(
        self,
        username: str,
    ) -> Any:
        try:
            return self._call_codeforces_api(
                self.client.fetch_profile,
                username,
            )
        except CodeforcesUserNotFoundError as exc:
            raise CodeforcesUsernameNotFoundError(
                f"Codeforces user '{username}' was not found."
            ) from exc

    def _fetch_remote_submissions(
        self,
        username: str,
    ) -> Any:
        return self._call_codeforces_api(
            self.client.fetch_submissions,
            username,
        )

    def _fetch_remote_rating_history(
        self,
        username: str,
    ) -> Any:
        return self._call_codeforces_api(
            self.client.fetch_rating_history,
            username,
        )

    def _fetch_remote_contests(self) -> Any:
        return self._call_codeforces_api(
            self.client.fetch_contests,
        )

    @staticmethod
    def _call_codeforces_api(
        fetch_fn: Any,
        *args: Any,
    ) -> Any:
        try:
            return fetch_fn(*args)
        except CodeforcesUserNotFoundError:
            raise
        except RuntimeError as exc:
            # Log the real cause so it is visible in the backend terminal.
            # The exc detail is safe (no credentials) — it is the upstream
            # Codeforces error message or an httpx transport message.
            logger.error(
                "Codeforces API call failed: fn=%s args=%r error=%s",
                getattr(fetch_fn, "__name__", repr(fetch_fn)),
                args,
                exc,
            )
            raise CodeforcesSyncError(str(exc)) from exc

    def _update_profile(
        self,
        profile: PlatformProfile,
        remote_profile: Mapping[str, Any],
    ) -> None:
        profile.current_rating = self._optional_int(
            remote_profile.get("rating"),
            "profile.rating",
        )

        profile.max_rating = self._optional_int(
            remote_profile.get("maxRating"),
            "profile.maxRating",
        )

        profile.rank = self._optional_text(
            remote_profile.get("rank"),
            "profile.rank",
        )

        profile.is_connected = True

    def _safe_add_and_flush(self, entity: Any) -> None:
        """
        Insert one entity inside a savepoint.

        This lets the sync recover from unique-constraint races
        without aborting the whole synchronization transaction.
        """

        with self.db.begin_nested():
            self.db.add(entity)
            self.db.flush()

    # ============================================================
    # SUBMISSIONS
    # ============================================================

    def _sync_submission(
        self,
        profile: PlatformProfile,
        submission_data: Mapping[str, Any],
        contests_by_platform_id: dict[str, Mapping[str, Any]],
        contests_cache: dict[str, Contest],
    ) -> tuple[bool, bool, bool, bool]:
        """
        Synchronize one submission.

        Returns:
            (
                problem_created,
                contest_created,
                submission_created,
                submission_skipped,
            )
        """

        platform_submission_id = str(
            self._required_int(
                submission_data.get("id"),
                "submission.id",
            )
        )

        # Idempotency check.
        existing_submission = (
            self.submissions.get_by_platform_submission_id(
                profile.id,
                platform_submission_id,
            )
        )

        if existing_submission is not None:
            return False, False, False, True

        # --------------------------------------------------------
        # Problem
        # --------------------------------------------------------

        problem_data = self._as_mapping(
            submission_data.get("problem"),
            "submission.problem",
        )

        problem, problem_created = self._get_or_create_problem(
            problem_data
        )

        # --------------------------------------------------------
        # Contest
        # --------------------------------------------------------

        contest_created = False
        contest_id: int | None = None

        external_contest_id = submission_data.get("contestId")

        if external_contest_id is not None:
            contest, contest_created = self._get_or_create_contest(
                external_contest_id,
                contests_by_platform_id,
                contests_cache,
            )

            contest_id = contest.id

        # --------------------------------------------------------
        # Submission
        # --------------------------------------------------------

        submission = Submission(
            profile_id=profile.id,
            problem_id=problem.id,
            contest_id=contest_id,
            platform_submission_id=platform_submission_id,
            submitted_at=self._utc_datetime(
                submission_data.get("creationTimeSeconds"),
                "submission.creationTimeSeconds",
            ),
            language=self._required_text(
                submission_data.get("programmingLanguage"),
                "submission.programmingLanguage",
            ),
            status=self._submission_status(
                submission_data.get("verdict")
            ),
        )

        try:
            self._safe_add_and_flush(submission)
        except IntegrityError:
            existing_submission = (
                self.submissions.get_by_platform_submission_id(
                    profile.id,
                    platform_submission_id,
                )
            )
            if existing_submission is None:
                raise CodeforcesSyncError(
                    "Failed to create submission due to a "
                    "database conflict."
                ) from None
            return False, False, False, True

        return (
            problem_created,
            contest_created,
            True,
            False,
        )

    # ============================================================
    # PROBLEMS
    # ============================================================

    def _get_or_create_problem(
        self,
        problem_data: Mapping[str, Any],
    ) -> tuple[Problem, bool]:
        contest_id = self._required_int(
            problem_data.get("contestId"),
            "problem.contestId",
        )

        index = self._required_text(
            problem_data.get("index"),
            "problem.index",
        )

        platform_problem_id = f"{contest_id}-{index}"

        existing_problem = (
            self.problems.get_by_platform_problem_id(
                Platform.CODEFORCES,
                platform_problem_id,
            )
        )

        if existing_problem is not None:
            return existing_problem, False

        title = self._required_text(
            problem_data.get("name"),
            "problem.name",
        )

        problem = Problem(
            platform=Platform.CODEFORCES,
            platform_problem_id=platform_problem_id,
            title=title,
            slug=self._problem_slug(
                contest_id,
                index,
                title,
            ),
            problem_url=(
                "https://codeforces.com/problemset/problem/"
                f"{contest_id}/{index}"
            ),
            difficulty=self._difficulty(
                problem_data.get("rating")
            ),
            acceptance_rate=None,
        )

        try:
            self._safe_add_and_flush(problem)
        except IntegrityError:
            existing_problem = (
                self.problems.get_by_platform_problem_id(
                    Platform.CODEFORCES,
                    platform_problem_id,
                )
            )
            if existing_problem is None:
                raise CodeforcesSyncError(
                    "Failed to create problem due to a "
                    "database conflict."
                ) from None
            return existing_problem, False

        return problem, True

    # ============================================================
    # CONTESTS
    # ============================================================

    def _get_or_create_contest(
        self,
        external_contest_id: Any,
        contests_by_platform_id: dict[str, Mapping[str, Any]],
        contests_cache: dict[str, Contest],
    ) -> tuple[Contest, bool]:
        """
        Get or create a contest referenced by submissions/rating history.

        Lookup order:

        1. Current sync cache (Contest objects)
        2. Database
        3. Preloaded contest.list metadata mapping

        Only contests referenced by this user's data are inserted.
        """

        contest_id = self._required_int(
            external_contest_id,
            "contestId",
        )

        platform_contest_id = str(contest_id)

        # 1. Current synchronization cache
        cached_contest = contests_cache.get(
            platform_contest_id
        )

        if cached_contest is not None:
            return cached_contest, False

        # 2. Existing database record
        existing_contest = (
            self.contests.get_by_platform_contest_id(
                Platform.CODEFORCES,
                platform_contest_id,
            )
        )

        if existing_contest is not None:
            contests_cache[platform_contest_id] = (
                existing_contest
            )
            return existing_contest, False

        # 3. Metadata from contest.list (fetched once per sync)
        remote_contest = contests_by_platform_id.get(
            platform_contest_id
        )

        if remote_contest is None:
            raise CodeforcesSyncError(
                "Contest metadata for Codeforces contest "
                f"{platform_contest_id} was not returned by "
                "contest.list."
            )

        contest = Contest(
            platform_contest_id=platform_contest_id,
            title=self._required_text(
                remote_contest.get("name"),
                "contest.name",
            ),
            platform=Platform.CODEFORCES,
            contest_url=(
                f"https://codeforces.com/contest/"
                f"{platform_contest_id}"
            ),
            start_time=self._utc_datetime(
                remote_contest.get("startTimeSeconds"),
                "contest.startTimeSeconds",
            ),
            duration_minutes=(
                self._required_int(
                    remote_contest.get("durationSeconds"),
                    "contest.durationSeconds",
                )
                // 60
            ),
        )

        try:
            self._safe_add_and_flush(contest)
        except IntegrityError:
            existing_contest = (
                self.contests.get_by_platform_contest_id(
                    Platform.CODEFORCES,
                    platform_contest_id,
                )
            )
            if existing_contest is None:
                raise CodeforcesSyncError(
                    "Failed to create contest due to a "
                    "database conflict."
                ) from None
            contests_cache[platform_contest_id] = (
                existing_contest
            )
            return existing_contest, False

        contests_cache[platform_contest_id] = contest

        return contest, True

    # ============================================================
    # RATING HISTORY
    # ============================================================

    def _sync_rating_event(
        self,
        profile: PlatformProfile,
        rating_data: Mapping[str, Any],
        contests_by_platform_id: dict[str, Mapping[str, Any]],
        contests_cache: dict[str, Contest],
    ) -> tuple[bool, bool, bool]:
        """
        Synchronize one rating event.

        Returns:
            (
                contest_created,
                rating_history_created,
                participation_created,
            )
        """

        contest, contest_created = self._get_or_create_contest(
            rating_data.get("contestId"),
            contests_by_platform_id,
            contests_cache,
        )

        old_rating = self._required_int(
            rating_data.get("oldRating"),
            "rating.oldRating",
        )

        new_rating = self._required_int(
            rating_data.get("newRating"),
            "rating.newRating",
        )

        rating_change = new_rating - old_rating

        # --------------------------------------------------------
        # Rating history
        # --------------------------------------------------------

        rating_created = False

        existing_rating = (
            self.rating_history.get_by_profile_contest(
                profile.id,
                contest.id,
            )
        )

        recorded_at = self._utc_datetime(
            rating_data.get(
                "ratingUpdateTimeSeconds"
            ),
            "rating.ratingUpdateTimeSeconds",
        )

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
            except IntegrityError:
                existing_rating = (
                    self.rating_history.get_by_profile_contest(
                        profile.id,
                        contest.id,
                    )
                )
                if existing_rating is None:
                    raise CodeforcesSyncError(
                        "Failed to create rating history due to a "
                        "database conflict."
                    ) from None
            else:
                rating_created = True

        if existing_rating is not None:
            existing_rating.rating = new_rating
            existing_rating.rating_change = rating_change
            existing_rating.recorded_at = recorded_at

        # --------------------------------------------------------
        # Contest participation
        # --------------------------------------------------------

        participation = (
            self.contest_participations.get_profile_contest(
                profile.id,
                contest.id,
            )
        )

        participation_created = participation is None

        rank = self._required_int(
            rating_data.get("rank"),
            "rating.rank",
        )

        if participation is None:
            participation = ContestParticipation(
                profile_id=profile.id,
                contest_id=contest.id,
                rank=rank,
                old_rating=old_rating,
                new_rating=new_rating,
                rating_change=rating_change,
                solved=0,
                penalty=None,
            )

            try:
                self._safe_add_and_flush(participation)
            except IntegrityError:
                participation = (
                    self.contest_participations.get_profile_contest(
                        profile.id,
                        contest.id,
                    )
                )
                if participation is None:
                    raise CodeforcesSyncError(
                        "Failed to create contest participation due to a "
                        "database conflict."
                    ) from None
                participation_created = False
                participation.rank = rank
                participation.old_rating = old_rating
                participation.new_rating = new_rating
                participation.rating_change = rating_change

        else:
            # Keep existing participation synchronized.
            participation.rank = rank
            participation.old_rating = old_rating
            participation.new_rating = new_rating
            participation.rating_change = rating_change

        return (
            contest_created,
            rating_created,
            participation_created,
        )

    # ============================================================
    # AGGREGATES
    # ============================================================

    def _count_solved_problems(
        self,
        profile_id: int,
    ) -> int:
        """
        Count distinct problems with at least one accepted
        submission for this profile.
        """

        result = (
            self.db.query(
                func.count(
                    distinct(Submission.problem_id)
                )
            )
            .filter(
                Submission.profile_id == profile_id,
                Submission.status
                == SubmissionStatus.ACCEPTED,
            )
            .scalar()
        )

        return int(result or 0)

    def _count_contests_attended(
        self,
        profile_id: int,
    ) -> int:
        """Count distinct contests in which the profile participated."""

        result = (
            self.db.query(
                func.count(
                    distinct(
                        ContestParticipation.contest_id
                    )
                )
            )
            .filter(
                ContestParticipation.profile_id
                == profile_id
            )
            .scalar()
        )

        return int(result or 0)

    # ============================================================
    # MAPPINGS
    # ============================================================

    @classmethod
    def _difficulty(
        cls,
        rating: Any,
    ) -> Difficulty:
        numeric_rating = cls._optional_int(
            rating,
            "problem.rating",
        )

        if numeric_rating is None:
            return Difficulty.MEDIUM

        if numeric_rating < 1200:
            return Difficulty.EASY

        if numeric_rating < 2000:
            return Difficulty.MEDIUM

        return Difficulty.HARD

    @classmethod
    def _submission_status(
        cls,
        verdict: Any,
    ) -> SubmissionStatus:
        """
        Convert Codeforces verdict to CodePulse status.

        Codeforces has more verdict types than our current enum.
        Unknown verdicts are currently mapped to RUNTIME_ERROR
        because SubmissionStatus has no UNKNOWN value.
        """

        if not isinstance(verdict, str):
            return SubmissionStatus.RUNTIME_ERROR

        return cls._VERDICT_TO_STATUS.get(
            verdict,
            SubmissionStatus.RUNTIME_ERROR,
        )

    # ============================================================
    # SLUG
    # ============================================================

    @staticmethod
    def _problem_slug(
        contest_id: int,
        index: str,
        title: str,
    ) -> str:
        normalized = unicodedata.normalize(
            "NFKD",
            title,
        )

        ascii_title = normalized.encode(
            "ascii",
            "ignore",
        ).decode("ascii")

        slugified_title = re.sub(
            r"[^a-z0-9]+",
            "-",
            ascii_title.lower(),
        ).strip("-")

        return (
            f"codeforces-{contest_id}-"
            f"{index.lower()}-"
            f"{slugified_title or 'problem'}"
        )[:255]

    # ============================================================
    # VALIDATION HELPERS
    # ============================================================

    @staticmethod
    def _as_mapping(
        value: Any,
        description: str,
    ) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError(
                f"Malformed {description}: expected an object."
            )

        return value

    @staticmethod
    def _as_sequence(
        value: Any,
        description: str,
    ) -> Sequence[Any]:
        if isinstance(value, (str, bytes)):
            raise ValueError(
                f"Malformed {description}: expected a list."
            )

        if not isinstance(value, Sequence):
            raise ValueError(
                f"Malformed {description}: expected a list."
            )

        return value

    @staticmethod
    def _required_text(
        value: Any,
        field: str,
    ) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"Malformed Codeforces data: "
                f"{field} is required."
            )

        return value.strip()

    @staticmethod
    def _optional_text(
        value: Any,
        field: str,
    ) -> str | None:
        if value is None:
            return None

        return CodeforcesSyncService._required_text(
            value,
            field,
        )

    @staticmethod
    def _required_int(
        value: Any,
        field: str,
    ) -> int:
        if isinstance(value, bool):
            raise ValueError(
                f"Malformed Codeforces data: "
                f"{field} must be an integer."
            )

        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Malformed Codeforces data: "
                f"{field} must be an integer."
            ) from exc

    @staticmethod
    def _optional_int(
        value: Any,
        field: str,
    ) -> int | None:
        if value is None:
            return None

        return CodeforcesSyncService._required_int(
            value,
            field,
        )

    @classmethod
    def _utc_datetime(
        cls,
        timestamp: Any,
        field: str,
    ) -> datetime:
        return datetime.fromtimestamp(
            cls._required_int(timestamp, field),
            tz=timezone.utc,
        )
