"""Base synchronization service for platform integrations."""

import logging
from abc import ABC, abstractmethod
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import distinct, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.contest_participation import ContestParticipation
from app.models.enums import Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
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


class PlatformSyncError(RuntimeError):
    """Base exception for platform synchronization errors."""


class PlatformProfileNotFoundError(PlatformSyncError):
    """Raised when the requested platform profile does not exist."""


class UnsupportedPlatformError(PlatformSyncError):
    """Raised when the profile platform is not supported."""


class PlatformUsernameNotFoundError(PlatformSyncError):
    """Raised when a platform username no longer exists."""


class ProfileAccessDeniedError(PlatformSyncError):
    """Raised when the authenticated user does not own the profile."""


class BaseSyncService(BaseService, ABC):
    """
    Base service for synchronizing platform profiles.
    
    Provides common synchronization logic that can be reused
    across different platform integrations (Codeforces, LeetCode, etc.).
    """

    def __init__(self, db: Session):
        super().__init__(db)
        self.platform_profiles = PlatformProfileRepository(db)
        self.problems = ProblemRepository(db)
        self.contests = ContestRepository(db)
        self.submissions = SubmissionRepository(db)
        self.rating_history = RatingHistoryRepository(db)
        self.contest_participations = ContestParticipationRepository(db)

    @abstractmethod
    def get_supported_platform(self) -> Platform:
        """Return the platform this service supports."""
        raise NotImplementedError

    def _get_platform_profile(
        self,
        profile_id: int,
        user_id: int,
    ) -> PlatformProfile:
        """
        Retrieve and validate a platform profile.
        
        Checks:
        - Profile exists
        - User owns the profile
        - Profile is for the correct platform
        """
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

        expected_platform = self.get_supported_platform()
        if profile.platform != expected_platform:
            raise UnsupportedPlatformError(
                f"Platform profile {profile_id} is not a "
                f"{expected_platform.value} profile."
            )

        return profile

    def _safe_add_and_flush(self, entity: Any) -> None:
        """
        Insert one entity inside a savepoint.

        This lets the sync recover from unique-constraint races
        without aborting the whole synchronization transaction.
        """
        with self.db.begin_nested():
            self.db.add(entity)
            self.db.flush()

    def _count_solved_problems(self, profile_id: int) -> int:
        """
        Count distinct problems with at least one accepted
        submission for this profile.
        """
        result = (
            self.db.query(
                func.count(distinct(Submission.problem_id))
            )
            .filter(
                Submission.profile_id == profile_id,
                Submission.status == SubmissionStatus.ACCEPTED,
            )
            .scalar()
        )

        return int(result or 0)

    def _count_contests_attended(self, profile_id: int) -> int:
        """Count distinct contests in which the profile participated."""
        result = (
            self.db.query(
                func.count(distinct(ContestParticipation.contest_id))
            )
            .filter(ContestParticipation.profile_id == profile_id)
            .scalar()
        )

        return int(result or 0)

    # ========================================================
    # Data validation helpers
    # ========================================================

    @staticmethod
    def _as_mapping(
        data: Any,
        context: str,
    ) -> Mapping[str, Any]:
        """Validate that data is a mapping (dict-like)."""
        if not isinstance(data, Mapping):
            raise ValueError(
                f"{context} must be a mapping, got {type(data).__name__}"
            )
        return data

    @staticmethod
    def _as_sequence(
        data: Any,
        context: str,
    ) -> list[Any]:
        """Validate that data is a sequence (list-like)."""
        if not isinstance(data, list):
            raise ValueError(
                f"{context} must be a sequence, got {type(data).__name__}"
            )
        return data

    @staticmethod
    def _required_text(
        value: Any,
        field_name: str,
    ) -> str:
        """Extract required text field."""
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"{field_name} is required and must be a non-empty string"
            )
        return value

    @staticmethod
    def _optional_text(
        value: Any,
        field_name: str,
    ) -> str | None:
        """Extract optional text field."""
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(
                f"{field_name} must be a string if provided"
            )
        return value if value else None

    @staticmethod
    def _required_int(
        value: Any,
        field_name: str,
    ) -> int:
        """Extract required integer field."""
        if not isinstance(value, int):
            raise ValueError(
                f"{field_name} is required and must be an integer"
            )
        return value

    @staticmethod
    def _optional_int(
        value: Any,
        field_name: str,
    ) -> int | None:
        """Extract optional integer field."""
        if value is None:
            return None
        if not isinstance(value, int):
            raise ValueError(
                f"{field_name} must be an integer if provided"
            )
        return value

    @staticmethod
    def _utc_datetime(
        timestamp: Any,
        field_name: str,
    ) -> datetime:
        """Convert Unix timestamp to UTC datetime."""
        if not isinstance(timestamp, (int, str)):
            raise ValueError(
                f"{field_name} must be a Unix timestamp"
            )

        try:
            ts = int(timestamp)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError) as exc:
            raise ValueError(
                f"{field_name} is not a valid Unix timestamp"
            ) from exc
