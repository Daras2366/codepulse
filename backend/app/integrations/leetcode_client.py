import logging
import time as _time
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
    - Only public profile data is accessible without session cookies
    - ``submissionList`` (paginated, all statuses) is attempted first; if it
      is blocked for a given username the client falls back to
      ``recentAcSubmissionList`` (≤ 100 accepted-only, no pagination)
    - Contest details may be limited without authentication
    """

    BASE_URL = "https://leetcode.com"
    GRAPHQL_URL = "https://leetcode.com/graphql"

    #: Maximum pages fetched by the paginated method.
    #: 20 submissions × 50 pages = 1 000 submissions max.
    _PAGINATED_PAGE_SIZE = 20
    _MAX_PAGES = 50

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

                tagProblemCounts {
                    advanced {
                        tagName
                        tagSlug
                        problemsSolved
                    }
                    intermediate {
                        tagName
                        tagSlug
                        problemsSolved
                    }
                    fundamental {
                        tagName
                        tagSlug
                        problemsSolved
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

    # ------------------------------------------------------------------
    # Submission history — paginated (primary) + recent-AC (fallback)
    # ------------------------------------------------------------------

    def fetch_submissions_paginated(
        self,
        username: str,
    ) -> list[dict[str, Any]]:
        """
        Attempt to retrieve full submission history via the ``submissionList``
        GraphQL query, which supports ``offset`` / ``limit`` pagination and
        returns **all** submission statuses (not just Accepted).

        If the endpoint is unavailable or returns an error on the first page,
        the method falls back to ``_fetch_recent_ac_submissions()`` so the
        sync never breaks.

        Pagination strategy
        -------------------
        *  Fetch pages of ``_PAGINATED_PAGE_SIZE`` submissions starting at
           offset 0.
        *  Stop when ``hasNext`` is False, the page is empty, or
           ``_MAX_PAGES`` pages have been fetched.
        *  A 0.3 s inter-page delay is applied to avoid rate-limiting.

        Returns a normalised list compatible with the sync service.
        """
        query = """
        query getSubmissions($username: String!, $limit: Int!, $offset: Int!) {
            submissionList(username: $username, limit: $limit, offset: $offset) {
                hasNext
                submissions {
                    id
                    title
                    titleSlug
                    timestamp
                    statusDisplay
                    lang
                }
            }
        }
        """

        all_raw: list[dict[str, Any]] = []
        offset = 0
        pages_fetched = 0

        while pages_fetched < self._MAX_PAGES:
            variables: dict[str, Any] = {
                "username": username,
                "limit": self._PAGINATED_PAGE_SIZE,
                "offset": offset,
            }

            try:
                result = self._graphql_query(query, variables)
            except LeetCodeApiError as exc:
                if pages_fetched == 0:
                    # The endpoint may not be accessible for this username —
                    # fall back to the public recent-AC endpoint.
                    logger.warning(
                        "submissionList paginated fetch failed for %s (page 0): %s. "
                        "Falling back to recentAcSubmissionList.",
                        username,
                        exc,
                    )
                    return self._fetch_recent_ac_submissions(username)
                # Subsequent pages: stop safely with what we have already.
                logger.warning(
                    "submissionList paginated fetch error at offset=%d for %s: %s. "
                    "Stopping pagination early with %d submissions collected.",
                    offset,
                    username,
                    exc,
                    len(all_raw),
                )
                break

            submission_list = result.get("submissionList") or {}
            page_submissions: list[dict[str, Any]] = submission_list.get("submissions") or []
            has_next = bool(submission_list.get("hasNext"))

            pages_fetched += 1

            if not page_submissions:
                logger.info(
                    "submissionList page %d returned 0 items for %s — stopping.",
                    pages_fetched,
                    username,
                )
                break

            logger.info(
                "submissionList page %d: offset=%d fetched=%d hasNext=%s",
                pages_fetched,
                offset,
                len(page_submissions),
                has_next,
            )

            all_raw.extend(page_submissions)
            offset += len(page_submissions)

            if not has_next:
                break

            # Polite inter-page delay to avoid rate-limiting.
            _time.sleep(0.3)

        logger.info(
            "submissionList paginated fetch complete for %s: "
            "pages=%d total_submissions=%d",
            username,
            pages_fetched,
            len(all_raw),
        )

        return self._normalise_submission_list(all_raw)

    def fetch_submissions(
        self,
        username: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Fetch recent *accepted* submissions via ``recentAcSubmissionList``.

        This endpoint is the public fallback — it is bounded (≤ 100 items,
        accepted-only) and does not support pagination.  Prefer
        ``fetch_submissions_paginated()`` for complete history.
        """
        return self._fetch_recent_ac_submissions(username, limit=limit)

    def _fetch_recent_ac_submissions(
        self,
        username: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Internal: fetch recentAcSubmissionList (accepted-only, bounded ≤ 100).
        """
        query = """
        query recentAcSubmissions($username: String!, $limit: Int!) {
            recentAcSubmissionList(username: $username, limit: $limit) {
                id
                title
                titleSlug
                timestamp
            }
        }
        """

        variables = {
            "username": username,
            "limit": min(limit, 100),
        }

        try:
            result = self._graphql_query(query, variables)
        except LeetCodeApiError:
            logger.warning(
                "Failed to fetch recent accepted submissions for user %s",
                username,
            )
            return []

        submissions: list[dict[str, Any]] = result.get("recentAcSubmissionList") or []

        # recentAcSubmissionList returns accepted submissions only.
        # Add the statusDisplay field so the normaliser works uniformly.
        for sub in submissions:
            sub.setdefault("statusDisplay", "Accepted")
            sub.setdefault("lang", "Unknown")

        return self._normalise_submission_list(submissions)

    @staticmethod
    def _normalise_submission_list(
        submissions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Convert raw GraphQL submission dicts into the normalised format
        consumed by :class:`LeetCodeSyncService`.

        Guaranteed output fields per entry:
            id, title, titleSlug, timestamp, statusDisplay, lang, difficulty
        """
        normalised: list[dict[str, Any]] = []
        for sub in submissions:
            normalised.append(
                {
                    "id": sub.get("id"),
                    "title": sub.get("title"),
                    "titleSlug": sub.get("titleSlug"),
                    "timestamp": sub.get("timestamp"),
                    "statusDisplay": sub.get("statusDisplay") or "Accepted",
                    "lang": sub.get("lang") or "Unknown",
                    "difficulty": None,
                }
            )
        return normalised

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

    # ------------------------------------------------------------------
    # DEPRECATED: Authenticated helpers (no longer used - replaced by public API)
    # ------------------------------------------------------------------
    # These methods are kept for backwards compatibility but are deprecated.
    # The new backfill_leetcode_topics() method uses the public API instead.

    def _graphql_query_authenticated(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        *,
        session: str,
        csrf_token: str,
    ) -> Any:
        """
        DEPRECATED: Execute a LeetCode GraphQL query with session-cookie authentication.

        This method is deprecated. Use the public _graphql_query() method instead.
        """
        logger.warning(
            "Authenticated GraphQL query is deprecated. "
            "Use public API methods instead."
        )

        payload = {
            "query": query,
            "variables": variables or {},
        }

        cookie_header = f"LEETCODE_SESSION={session}; csrftoken={csrf_token}"

        skip_val = (variables or {}).get("skip", "?")
        limit_val = (variables or {}).get("limit", "?")
        logger.info(
            "LeetCode authenticated GraphQL request: skip=%s limit=%s",
            skip_val,
            limit_val,
        )

        _timeout = httpx.Timeout(
            connect=10.0,
            read=30.0,
            write=10.0,
            pool=5.0,
        )

        t0 = _time.monotonic()
        try:
            response = httpx.post(
                self.GRAPHQL_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Referer": "https://leetcode.com",
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Cookie": cookie_header,
                    "x-csrftoken": csrf_token,
                },
                timeout=_timeout,
                follow_redirects=False,
            )
            elapsed = _time.monotonic() - t0
            logger.info(
                "LeetCode authenticated response: status=%s elapsed=%.2fs",
                response.status_code,
                elapsed,
            )

            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location", "unknown")
                raise LeetCodeApiError(
                    f"LeetCode redirected the authenticated request to {location!r}. "
                    "This typically means the session cookies are invalid or expired."
                )

            response.raise_for_status()
            data = response.json()
        except httpx.ConnectTimeout as exc:
            elapsed = _time.monotonic() - t0
            raise LeetCodeApiError(
                f"LeetCode authenticated API connection timed out after {elapsed:.1f}s"
            ) from exc
        except httpx.ReadTimeout as exc:
            elapsed = _time.monotonic() - t0
            raise LeetCodeApiError(
                f"LeetCode authenticated API read timed out after {elapsed:.1f}s"
            ) from exc
        except httpx.TimeoutException as exc:
            elapsed = _time.monotonic() - t0
            raise LeetCodeApiError(
                f"LeetCode authenticated API request timed out after {elapsed:.1f}s: {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise LeetCodeApiError(
                f"LeetCode authenticated API HTTP {exc.response.status_code}: {exc}"
            ) from exc
        except LeetCodeApiError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise LeetCodeApiError(
                f"LeetCode authenticated API request failed: {exc}"
            ) from exc

        if "errors" in data:
            errors = data["errors"]
            error_msgs = [
                err.get("message", "Unknown error")
                for err in (errors if errors else [])
            ]
            logger.error(
                "LeetCode authenticated GraphQL errors: %s",
                error_msgs,
            )
            first_msg = error_msgs[0] if error_msgs else "Unknown error"
            raise LeetCodeApiError(f"LeetCode GraphQL error: {first_msg}")

        if "data" not in data:
            raise LeetCodeApiError(
                "LeetCode authenticated API returned malformed response (no 'data' key)"
            )

        return data["data"]

    def fetch_solved_problem_topics_authenticated(
        self,
        session: str,
        csrf_token: str,
        batch_size: int = 100,
        max_problems: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        DEPRECATED: Fetch all solved LeetCode problems with topic tags (authenticated).

        This method is deprecated. Use backfill_leetcode_topics() in the sync service
        which uses the public API instead.
        """
        logger.warning(
            "fetch_solved_problem_topics_authenticated is deprecated. "
            "Use public API backfill methods instead."
        )

        query = """
        query problemsetQuestionListV2(
            $filters: QuestionFilterInput
            $limit: Int
            $skip: Int
            $categorySlug: String
        ) {
            problemsetQuestionListV2(
                filters: $filters
                limit: $limit
                skip: $skip
                categorySlug: $categorySlug
            ) {
                questions {
                    title
                    titleSlug
                    questionFrontendId
                    difficulty
                    status
                    topicTags {
                        name
                        slug
                    }
                }
                totalLength
                hasMore
            }
        }
        """

        _FILTER_TEMPLATE: dict[str, Any] = {
            "filterCombineType": "ALL",
            "statusFilter": {"questionStatuses": [], "operator": "IS"},
            "difficultyFilter": {"difficulties": [], "operator": "IS"},
            "languageFilter": {"languageSlugs": [], "operator": "IS"},
            "topicFilter": {"topicSlugs": [], "operator": "IS"},
            "acceptanceFilter": {},
            "frequencyFilter": {},
            "frontendIdFilter": {},
            "lastSubmittedFilter": {},
            "publishedFilter": {},
            "companyFilter": {"companySlugs": [], "operator": "IS"},
            "positionFilter": {"positionSlugs": [], "operator": "IS"},
            "positionLevelFilter": {"positionLevelSlugs": [], "operator": "IS"},
            "contestPointFilter": {"contestPoints": [], "operator": "IS"},
            "premiumFilter": {"premiumStatus": [], "operator": "IS"},
        }

        solved: list[dict[str, Any]] = []
        skip = 0
        pages_fetched = 0

        while True:
            limit = batch_size

            variables: dict[str, Any] = {
                "categorySlug": "",
                "skip": skip,
                "limit": limit,
                "filters": _FILTER_TEMPLATE,
            }

            try:
                result = self._graphql_query_authenticated(
                    query,
                    variables,
                    session=session,
                    csrf_token=csrf_token,
                )
            except LeetCodeApiError:
                logger.exception(
                    "Authenticated LeetCode problemset fetch failed at skip=%s",
                    skip,
                )
                raise

            pages_fetched += 1
            problemset = result.get("problemsetQuestionListV2") or {}
            questions = problemset.get("questions") or []
            total_length = int(problemset.get("totalLength") or 0)
            has_more = bool(problemset.get("hasMore"))

            if not questions:
                logger.info(
                    "Authenticated problemset page returned 0 questions at skip=%s — stopping.",
                    skip,
                )
                break

            if pages_fetched == 1:
                from collections import Counter as _Counter
                status_dist = dict(_Counter(
                    (q.get("status") or "null") for q in questions
                ))
                ac_on_page = sum(
                    1 for q in questions
                    if (q.get("status") or "").upper() == "SOLVED"
                )
                logger.info(
                    "First page status distribution: %s (AC on this page: %d)",
                    status_dist,
                    ac_on_page,
                )
                print(
                    f"First page: {len(questions)} questions returned, "
                    f"totalLength={total_length}, "
                    f"status distribution={status_dist}"
                )
                if ac_on_page == 0 and status_dist.get("TO_DO", 0) == len(questions):
                    logger.warning(
                        "All questions have status='TO_DO' on the first page. "
                        "Session cookies may be invalid or expired. "
                        "Continuing to collect data, but the result may be empty."
                    )
                    print(
                        "[WARNING] All statuses are TO_DO — cookies may not be "
                        "recognised by LeetCode. Result will likely be empty."
                    )

            for question in questions:
                status = (question.get("status") or "").upper()
                if status == "SOLVED":
                    solved.append(question)
                    if max_problems is not None and len(solved) >= max_problems:
                        logger.info(
                            "Reached max_problems=%d after %d page(s), stopping early.",
                            max_problems,
                            pages_fetched,
                        )
                        return solved[:max_problems]

            logger.info(
                "Authenticated problemset page %d: skip=%d, page_size=%d, "
                "solved_so_far=%d, total_problemset=%d, has_more=%s",
                pages_fetched,
                skip,
                len(questions),
                len(solved),
                total_length,
                has_more,
            )

            if not has_more:
                break

            skip += len(questions)

        logger.info(
            "fetch_solved_problem_topics_authenticated complete: "
            "pages=%d solved=%d",
            pages_fetched,
            len(solved),
        )
        return solved
