from typing import Any

import httpx

from app.integrations.base_client import BasePlatformClient


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

        try:
            response = httpx.get(
                url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CodeforcesApiError(
                f"Codeforces API request failed: {exc}"
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
        """
        return self._get(
            "user.status",
            params={
                "handle": username,
                "from": 1,
                "count": limit,
            },
        )

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
        Fetch contest metadata from both regular and gym contest lists.

        The sync service uses this as a lookup table only; it does not
        import every returned contest into the database.
        """
        regular_contests = self._get(
            "contest.list",
            params={
                "gym": "false",
            },
        )
        gym_contests = self._get(
            "contest.list",
            params={
                "gym": "true",
            },
        )

        contests_by_id: dict[int, dict[str, Any]] = {}

        for contest in regular_contests:
            contests_by_id[contest["id"]] = contest

        for contest in gym_contests:
            contests_by_id.setdefault(contest["id"], contest)

        return list(contests_by_id.values())
