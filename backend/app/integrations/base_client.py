from abc import ABC, abstractmethod
from typing import Any


class BasePlatformClient(ABC):
    """Base interface for coding-platform API clients."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    @abstractmethod
    def fetch_profile(self, username: str) -> dict[str, Any]:
        """Fetch public profile information."""
        raise NotImplementedError

    @abstractmethod
    def fetch_submissions(
        self,
        username: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch user submissions."""
        raise NotImplementedError

    @abstractmethod
    def fetch_rating_history(
        self,
        username: str,
    ) -> list[dict[str, Any]]:
        """Fetch rating history."""
        raise NotImplementedError

    @abstractmethod
    def fetch_contests(self) -> list[dict[str, Any]]:
        """Fetch contests."""
        raise NotImplementedError