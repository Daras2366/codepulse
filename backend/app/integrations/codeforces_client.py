from typing import Any

import httpx

from app.integrations.base_client import BasePlatformClient


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
        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Codeforces API request failed: {exc}"
            ) from exc

        data = response.json()

        if data.get("status") != "OK":
            comment = data.get(
                "comment",
                "Unknown Codeforces API error",
            )
            raise RuntimeError(
                f"Codeforces API error: {comment}"
            )

        return data["result"]

    def fetch_profile(
        self,
        username: str,
    ) -> dict[str, Any]:
        users = self._get(
            "user.info",
            params={
                "handles": username,
            },
        )

        if not users:
            raise ValueError(
                f"Codeforces user '{username}' not found."
            )

        return users[0]

    def fetch_submissions(
        self,
        username: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
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
        return self._get(
            "contest.list",
            params={
                "gym": "false",
            },
        )