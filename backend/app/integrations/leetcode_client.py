import logging
from typing import Any

import httpx

from app.integrations.base_client import BasePlatformClient

logger = logging.getLogger(__name__)


class LeetCodeApiError(RuntimeError):
    """Raised when LeetCode returns an unusable API response."""


class LeetCodeUserNotFoundError(LeetCodeApiError):
    """Raised when a requested LeetCode username does not exist."""


class LeetCodeClient(BasePlatformClient):
    """
    LeetCode public GraphQL API client.
    
    Uses LeetCode's public GraphQL endpoint to fetch user profile and
    submission data. Does NOT require authentication for basic public stats.
    
    Limitations:
    - Only public profile data is accessible
    - Submission history may be limited to recent submissions
    - Contest details may be limited without authentication
    """
    
    BASE_URL = "https://leetcode.com"
    GRAPHQL_URL = "https://leetcode.com/graphql"

    def __init__(self, timeout: float = 10.0):
        super().__init__(self.BASE_URL)
        self.timeout = timeout

    def _graphql_query(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> Any:
        """Execute a GraphQL query against LeetCode's public API."""
        
        payload = {
            "query": query,
            "variables": variables or {},
        }
        
        logger.debug(
            "LeetCode GraphQL request: query=%s variables=%r",
            query[:100],
            variables,
        )

        try:
            response = httpx.post(
                self.GRAPHQL_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Referer": "https://leetcode.com",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            logger.error(
                "LeetCode API timeout: error=%s",
                exc,
            )
            raise LeetCodeApiError(
                f"LeetCode API request timed out: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "LeetCode API HTTP error: status=%s error=%s",
                exc.response.status_code,
                exc,
            )
            raise LeetCodeApiError(
                f"LeetCode API HTTP {exc.response.status_code}: {exc}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.error(
                "LeetCode API error: error=%s",
                exc,
            )
            raise LeetCodeApiError(
                f"LeetCode API request failed: {exc}"
            ) from exc

        # Check for GraphQL errors
        if "errors" in data:
            errors = data["errors"]
            error_msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
            logger.error("LeetCode GraphQL error: %s", error_msg)
            raise LeetCodeApiError(f"LeetCode GraphQL error: {error_msg}")

        if "data" not in data:
            raise LeetCodeApiError("LeetCode API returned malformed response")

        return data["data"]

    def fetch_profile(self, username: str) -> dict[str, Any]:
        """
        Fetch public profile data for a LeetCode user.
        
        Returns profile information including:
        - username
        - ranking
        - problems solved by difficulty
        - contest rating (if available)
        """
        
        # First, fetch basic profile and submit stats
        query = """
        query getUserProfile($username: String!) {
            matchedUser(username: $username) {
                username
                profile {
                    ranking
                }
                submitStats {
                    acSubmissionNum {
                        difficulty
                        count
                    }
                }
            }
        }
        """
        
        variables = {"username": username}
        
        try:
            result = self._graphql_query(query, variables)
        except LeetCodeApiError as exc:
            # Check if user not found
            if "user" in str(exc).lower() and "not" in str(exc).lower():
                raise LeetCodeUserNotFoundError(
                    f"LeetCode user '{username}' not found."
                ) from exc
            raise

        matched_user = result.get("matchedUser")
        
        if matched_user is None:
            raise LeetCodeUserNotFoundError(
                f"LeetCode user '{username}' not found."
            )

        # Try to fetch contest ranking separately (may not exist for all users)
        try:
            contest_query = """
            query getUserContestRanking($username: String!) {
                userContestRanking(username: $username) {
                    rating
                    globalRanking
                    attendedContestsCount
                }
            }
            """
            contest_result = self._graphql_query(contest_query, variables)
            matched_user["userContestRanking"] = contest_result.get("userContestRanking")
        except LeetCodeApiError:
            # Contest data not available - this is fine
            logger.info("Contest ranking not available for user %s", username)
            matched_user["userContestRanking"] = None

        return matched_user

    def fetch_submissions(
        self,
        username: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Fetch recent submissions for a LeetCode user.
        
        Note: LeetCode's public API provides limited submission history.
        Full history requires authentication.
        
        Returns list of recent submissions with:
        - timestamp
        - problem title/slug
        - status (Accepted, Wrong Answer, etc.)
        - language
        """
        
        query = """
        query getRecentSubmissions($username: String!, $limit: Int!) {
            recentSubmissionList(username: $username, limit: $limit) {
                title
                titleSlug
                timestamp
                statusDisplay
                lang
                difficulty
            }
        }
        """
        
        variables = {
            "username": username,
            "limit": limit,
        }
        
        try:
            result = self._graphql_query(query, variables)
        except LeetCodeApiError:
            # If submissions fetch fails, return empty list
            # User might have private profile or no submissions
            logger.warning(
                "Failed to fetch submissions for user %s, returning empty list",
                username,
            )
            return []

        submissions = result.get("recentSubmissionList")
        
        if submissions is None:
            return []

        return submissions

    def fetch_rating_history(self, username: str) -> list[dict[str, Any]]:
        """
        Fetch contest rating history for a LeetCode user.
        
        Note: Only available if user has participated in contests.
        Returns empty list if no contest history.
        """
        
        query = """
        query getUserContestHistory($username: String!) {
            userContestRankingHistory(username: $username) {
                attended
                rating
                ranking
                trendDirection
                problemsSolved
                totalProblems
                finishTimeInSeconds
                contest {
                    title
                    startTime
                }
            }
        }
        """
        
        variables = {"username": username}
        
        try:
            result = self._graphql_query(query, variables)
        except LeetCodeApiError:
            # Contest history might not be available
            logger.info(
                "Contest history not available for user %s",
                username,
            )
            return []

        history = result.get("userContestRankingHistory")
        
        if history is None:
            return []

        return history

    def fetch_contests(self) -> list[dict[str, Any]]:
        """
        Fetch LeetCode contest list.
        
        Note: LeetCode's public API does not provide a comprehensive
        contest list endpoint. This returns an empty list as contests
        are fetched per-user through rating history.
        """
        
        # LeetCode doesn't provide a public contest list API
        # Contests are retrieved through user-specific contest history
        logger.info("LeetCode contest list not available via public API")
        return []

    def fetch_problem_details(self, title_slug: str) -> dict[str, Any] | None:
        """
        Fetch detailed information about a specific LeetCode problem.
        
        Returns problem details including difficulty if available.
        Returns None if the problem cannot be found.
        """
        
        query = """
        query getProblemDetails($titleSlug: String!) {
            question(titleSlug: $titleSlug) {
                title
                difficulty
                topicTags {
                    name
                }
            }
        }
        """
        
        variables = {"titleSlug": title_slug}
        
        try:
            result = self._graphql_query(query, variables)
            question = result.get("question")
            return question
        except LeetCodeApiError:
            logger.warning("Failed to fetch problem details for %s", title_slug)
            return None
