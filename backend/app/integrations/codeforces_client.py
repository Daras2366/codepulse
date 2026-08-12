import logging
from typing import Any

import httpx

from app.integrations.base_client import BasePlatformClient

logger = logging.getLogger(__name__)


class CodeforcesApiError(RuntimeError):
    """Raised when Codeforces returns an unusable API response."""


class CodeforcesUserNotFoundError(CodeforcesApiError):
    """Raised when a requested Codeforces handle does not exist."""


class CodeforcesClient(BasePlatformClient):
    BASE_URL = "https://codeforces.com/api"

    def __init__(self, timeout: float = 10.0):
        super().__init__(self.BASE_URL)
        self.timeout = timeout

    def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{endpoint}"
        logger.debug("Codeforces API request: %s params=%r", url, params)

        try:
            response = httpx.get(
                url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            logger.error(
                "Codeforces API timeout: endpoint=%s params=%r error=%s",
                endpoint, params, exc,
            )
            raise CodeforcesApiError(
                f"Codeforces API request timed out ({endpoint}): {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Codeforces API HTTP error: endpoint=%s status=%s error=%s",
                endpoint, exc.response.status_code, exc,
            )
            raise CodeforcesApiError(
                f"Codeforces API HTTP {exc.response.status_code} ({endpoint}): {exc}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.error(
                "Codeforces API error: endpoint=%s error=%s",
                endpoint, exc,
            )
            raise CodeforcesApiError(
                f"Codeforces API request failed ({endpoint}): {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise CodeforcesApiError(
                "Codeforces API returned a malformed response."
            )

        if data.get("status") != "OK":
            comment = data.get(
                "comment",
                "Unknown Codeforces API error",
            )
            raise CodeforcesApiError(
                f"Codeforces API error: {comment}"
            )

        return data["result"]

    def fetch_profile(
        self,
        username: str,
    ) -> dict[str, Any]:
        try:
            users = self._get(
                "user.info",
                params={
                    "handles": username,
                },
            )
        except CodeforcesApiError as exc:
            message = str(exc).lower()
            if "user with handle" in message and "not found" in message:
                raise CodeforcesUserNotFoundError(
                    f"Codeforces user '{username}' not found."
                ) from exc
            raise

        if not users:
            raise CodeforcesUserNotFoundError(
                f"Codeforces user '{username}' not found."
            )

        return users[0]

    def fetch_submissions(
        self,
        username: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Fetch recent Codeforces submissions for a handle.

        Codeforces returns submissions in descending ID order.
        This client intentionally synchronizes only the most recent
        `limit` submissions (default 100) per sync call.

        Preserved for backward compatibility with existing tests.
        New code should prefer fetch_submissions_paginated.
        """
        return self._get(
            "user.status",
            params={
                "handle": username,
                "from": 1,
                "count": limit,
            },
        )

    def fetch_submissions_paginated(
        self,
        username: str,
        max_count: int = 1000,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Fetch submissions page-by-page up to *max_count*.

        Codeforces ``user.status`` uses 1-indexed ``from`` offsets and
        returns up to ``count`` submissions per page, sorted by
        submission-ID descending (newest first).

        Stopping conditions (whichever comes first):
          • A page returns fewer items than ``page_size`` — no more data.
          • The running total of fetched items reaches ``max_count``.

        This keeps HTTP requests bounded and proportional to the actual
        amount of history that exists, rather than issuing fixed-count
        requests regardless of reality.

        Returns a flat list with at most *max_count* submissions; order
        is preserved (newest first) as returned by the API.
        """
        if max_count <= 0 or page_size <= 0:
            return []

        all_submissions: list[dict[str, Any]] = []
        offset = 1  # Codeforces uses 1-indexed "from"

        while len(all_submissions) < max_count:
            remaining = max_count - len(all_submissions)
            fetch = min(page_size, remaining)

            logger.debug(
                "Fetching submissions page: handle=%s from=%d count=%d",
                username,
                offset,
                fetch,
            )

            page: list[dict[str, Any]] = self._get(
                "user.status",
                params={
                    "handle": username,
                    "from": offset,
                    "count": fetch,
                },
            )

            if not page:
                # API returned an empty page — nothing more to fetch.
                break

            all_submissions.extend(page)
            offset += len(page)

            if len(page) < fetch:
                # Partial page — we have reached the end of the history.
                break

        return all_submissions

    def fetch_rating_history(
        self,
        username: str,
    ) -> list[dict[str, Any]]:
        return self._get(
            "user.rating",
            params={
                "handle": username,
            },
        )

    def fetch_contests(self) -> list[dict[str, Any]]:
        """
        Fetch regular rated contest metadata from Codeforces.

        Only regular (non-gym) contests are fetched because:

        * Regular contests account for all rated participations.
        * The gym=true endpoint returns tens of thousands of entries and
          consistently times out under the default 10-second read timeout.

        The sync service uses the returned list as a lookup table; it does
        not import every contest into the database.
        """
        regular_contests = self._get(
            "contest.list",
            params={"gym": "false"},
        )

        contests_by_id: dict[int, dict[str, Any]] = {}

        for contest in regular_contests:
            contests_by_id[contest["id"]] = contest

        return list(contests_by_id.values())
