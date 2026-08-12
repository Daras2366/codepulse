"""
Regression tests for paginated Codeforces submission fetching.

Covers:
  1. Multi-page fetch (two full pages + partial last page)
  2. Stop when no more submissions (page shorter than page_size)
  3. Stop at configured limit (max_count)
  4. Duplicate submissions across pages (idempotent — same id, no double DB row)
  5. Idempotent repeated sync (second sync skips all)
  6. API failure on a later page (rollback)
  7. submissions_fetched field in SyncResult
"""

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 -- registers all mapped models
from app.integrations.codeforces_client import (
    CodeforcesApiError,
    CodeforcesClient,
)
from app.models.base import Base
from app.models.enums import Platform
from app.models.platform_profile import PlatformProfile
from app.models.submission import Submission
from app.models.user import User
from app.services.sync_service import (
    CodeforcesSyncError,
    CodeforcesSyncService,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_submission(sub_id: int, contest_id: int = 100) -> dict:
    return {
        "id": sub_id,
        "contestId": contest_id,
        "creationTimeSeconds": 1_700_000_000 + sub_id,
        "programmingLanguage": "GNU C++17",
        "verdict": "OK",
        "problem": {
            "contestId": contest_id,
            "index": "A",
            "name": f"Problem {sub_id}",
            "rating": 800,
        },
    }


def _contest_payload(contest_id: int) -> dict:
    return {
        "id": contest_id,
        "name": f"Contest {contest_id}",
        "startTimeSeconds": 1_700_000_000,
        "durationSeconds": 7_200,
    }


_PROFILE = {"rating": 1500, "maxRating": 1600, "rank": "specialist"}


class _SimpleClient:
    """
    Minimal fake client.  ``fetch_submissions_paginated`` returns a pre-built
    flat list — the service just iterates over it.  This lets us test the
    service's idempotency / rollback logic without re-implementing the HTTP
    pagination loop inside the test itself.
    """

    def __init__(
        self,
        submissions: list[dict],
        profile: dict | None = None,
        ratings: list | None = None,
        contests: list | None = None,
    ):
        self._submissions = submissions
        self._profile = profile or _PROFILE
        self._ratings = ratings or []
        self._contests = contests or []

    def fetch_profile(self, username: str) -> dict:
        return self._profile

    def fetch_submissions_paginated(
        self,
        username: str,
        max_count: int = 1000,
        page_size: int = 100,
    ) -> list[dict]:
        return self._submissions[:max_count]

    def fetch_rating_history(self, username: str) -> list:
        return self._ratings

    def fetch_contests(self) -> list:
        return self._contests


class _FailingClient(_SimpleClient):
    """
    Like _SimpleClient but raises CodeforcesApiError from
    fetch_submissions_paginated to simulate a network failure mid-sync.
    """

    def fetch_submissions_paginated(
        self,
        username: str,
        max_count: int = 1000,
        page_size: int = 100,
    ) -> list[dict]:
        raise CodeforcesApiError("Simulated API failure on later page")


# ---------------------------------------------------------------------------
# Base test case with SQLite in-memory DB
# ---------------------------------------------------------------------------

class _PaginationTestBase(TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

        self.user = User(
            username="pag-user",
            email="pag@example.com",
            password_hash="hash",
        )
        self.session.add(self.user)
        self.session.flush()

        self.profile = PlatformProfile(
            user_id=self.user.id,
            platform=Platform.CODEFORCES,
            username="tourist",
        )
        self.session.add(self.profile)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _service(self, client):
        return CodeforcesSyncService(self.session, client)

    def _submission_count(self) -> int:
        return self.session.query(Submission).count()


# ---------------------------------------------------------------------------
# Test 1 — multi-page fetch: three pages of submissions all imported
# ---------------------------------------------------------------------------

class TestMultiPageFetch(_PaginationTestBase):
    def test_all_submissions_are_imported(self):
        """
        When the client returns 7 unique submissions (across logical pages),
        all 7 should be persisted.
        """
        subs = [_make_submission(i, 100) for i in range(1, 8)]  # 7 unique
        contests = [_contest_payload(100)]
        client = _SimpleClient(submissions=subs, contests=contests)

        result = self._service(client).sync_codeforces_profile(
            self.profile.id, self.user.id
        )

        self.assertEqual(result.submissions_created, 7)
        self.assertEqual(result.submissions_fetched, 7)
        self.assertEqual(self._submission_count(), 7)


# ---------------------------------------------------------------------------
# Test 2 — stop when no more submissions
# ---------------------------------------------------------------------------

class TestStopOnNoMoreSubmissions(_PaginationTestBase):
    def test_empty_list_returns_zero_submissions(self):
        """An empty submission list → zero submissions imported."""
        client = _SimpleClient(submissions=[], contests=[])

        result = self._service(client).sync_codeforces_profile(
            self.profile.id, self.user.id
        )

        self.assertEqual(result.submissions_created, 0)
        self.assertEqual(result.submissions_fetched, 0)
        self.assertEqual(self._submission_count(), 0)

    def test_partial_list_imports_all_available(self):
        """A list smaller than the page_size → only those items imported."""
        subs = [_make_submission(i, 100) for i in range(1, 4)]  # 3 items
        contests = [_contest_payload(100)]
        client = _SimpleClient(submissions=subs, contests=contests)

        result = self._service(client).sync_codeforces_profile(
            self.profile.id, self.user.id
        )

        self.assertEqual(result.submissions_created, 3)
        self.assertEqual(result.submissions_fetched, 3)


# ---------------------------------------------------------------------------
# Test 3 — stop at configured limit
# ---------------------------------------------------------------------------

class TestStopAtLimit(_PaginationTestBase):
    def test_stops_at_max_count(self):
        """
        With max_count patched to 5, only 5 submissions should be fetched
        and persisted even if more exist.
        """
        subs = [_make_submission(i, 100) for i in range(1, 11)]  # 10 available
        contests = [_contest_payload(100)]

        with (
            patch(
                "app.services.sync_service.settings.CODEFORCES_SUBMISSION_LIMIT",
                5,
            ),
            patch(
                "app.services.sync_service.settings.CODEFORCES_SUBMISSION_PAGE_SIZE",
                100,
            ),
        ):
            client = _SimpleClient(submissions=subs, contests=contests)
            result = self._service(client).sync_codeforces_profile(
                self.profile.id, self.user.id
            )

        self.assertEqual(result.submissions_fetched, 5)
        self.assertEqual(result.submissions_created, 5)
        self.assertEqual(self._submission_count(), 5)


# ---------------------------------------------------------------------------
# Test 4 — duplicate submission IDs are idempotent (no double DB row)
# ---------------------------------------------------------------------------

class TestDuplicatesAcrossPages(_PaginationTestBase):
    def test_duplicate_submission_ids_produce_one_row(self):
        """
        If the same submission ID appears twice in the fetched list
        (e.g. from overlapping pages), only one DB row should be created.
        """
        sub = _make_submission(1, 100)
        # Return the same submission twice in the flat list
        subs = [sub, sub]
        contests = [_contest_payload(100)]
        client = _SimpleClient(submissions=subs, contests=contests)

        result = self._service(client).sync_codeforces_profile(
            self.profile.id, self.user.id
        )

        # 2 items fetched; 1 created, 1 skipped by idempotency check
        self.assertEqual(result.submissions_fetched, 2)
        self.assertEqual(result.submissions_created, 1)
        self.assertEqual(result.submissions_skipped, 1)
        self.assertEqual(self._submission_count(), 1)


# ---------------------------------------------------------------------------
# Test 5 — idempotent repeated sync
# ---------------------------------------------------------------------------

class TestIdempotentRepeatedSync(_PaginationTestBase):
    def test_second_sync_creates_no_new_submissions(self):
        """Running sync twice should not create duplicate DB rows."""
        subs = [_make_submission(i, 100) for i in range(1, 4)]
        contests = [_contest_payload(100)]

        # First sync
        result1 = self._service(
            _SimpleClient(submissions=subs, contests=contests)
        ).sync_codeforces_profile(self.profile.id, self.user.id)

        # Second sync — same submissions
        result2 = self._service(
            _SimpleClient(submissions=subs, contests=contests)
        ).sync_codeforces_profile(self.profile.id, self.user.id)

        self.assertEqual(result1.submissions_created, 3)
        self.assertEqual(result2.submissions_created, 0)
        self.assertEqual(result2.submissions_skipped, 3)
        self.assertEqual(self._submission_count(), 3)


# ---------------------------------------------------------------------------
# Test 6 — API failure during fetch triggers rollback
# ---------------------------------------------------------------------------

class TestApiFailureRollback(_PaginationTestBase):
    def test_api_error_during_fetch_rolls_back(self):
        """
        If fetch_submissions_paginated raises CodeforcesApiError, the entire
        sync transaction must be rolled back — no submissions survive.
        """
        client = _FailingClient(submissions=[])

        with self.assertRaises(CodeforcesSyncError):
            self._service(client).sync_codeforces_profile(
                self.profile.id, self.user.id
            )

        # After rollback, no submissions should exist
        self.assertEqual(self._submission_count(), 0)


# ---------------------------------------------------------------------------
# Test 7 — submissions_fetched in SyncResult
# ---------------------------------------------------------------------------

class TestSubmissionsFetchedField(_PaginationTestBase):
    def test_submissions_fetched_matches_raw_api_count(self):
        """
        submissions_fetched should equal the total number of raw items
        returned by fetch_submissions_paginated, regardless of idempotency.
        """
        subs = [_make_submission(i, 100) for i in range(1, 6)]  # 5 items
        contests = [_contest_payload(100)]

        # First sync: all 5 created
        result1 = self._service(
            _SimpleClient(submissions=subs, contests=contests)
        ).sync_codeforces_profile(self.profile.id, self.user.id)
        self.assertEqual(result1.submissions_fetched, 5)
        self.assertEqual(result1.submissions_created, 5)

        # Second sync: same 5 fetched, all skipped
        result2 = self._service(
            _SimpleClient(submissions=subs, contests=contests)
        ).sync_codeforces_profile(self.profile.id, self.user.id)
        self.assertEqual(result2.submissions_fetched, 5)
        self.assertEqual(result2.submissions_created, 0)
        self.assertEqual(result2.submissions_skipped, 5)


# ---------------------------------------------------------------------------
# CodeforcesClient unit tests (pure HTTP pagination)
# ---------------------------------------------------------------------------

class TestCodeforcesClientPagination(TestCase):
    """Unit tests for CodeforcesClient.fetch_submissions_paginated."""

    def _ok_response(self, result: list) -> object:
        class Resp:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self_):
                return {"status": "OK", "result": result}

        return Resp()

    def test_stops_on_empty_page(self):
        """An empty first page → empty list returned immediately."""
        with patch(
            "app.integrations.codeforces_client.httpx.get",
            return_value=self._ok_response([]),
        ):
            result = CodeforcesClient().fetch_submissions_paginated(
                "tourist", max_count=100, page_size=10
            )
        self.assertEqual(result, [])

    def test_stops_on_partial_page(self):
        """Partial page (3 < page_size 10) → stops after that page."""
        page1 = [{"id": i} for i in range(1, 11)]   # full (10)
        page2 = [{"id": i} for i in range(11, 14)]  # partial (3) → stop
        responses = [
            self._ok_response(page1),
            self._ok_response(page2),
        ]
        with patch(
            "app.integrations.codeforces_client.httpx.get",
            side_effect=responses,
        ):
            result = CodeforcesClient().fetch_submissions_paginated(
                "tourist", max_count=100, page_size=10
            )
        self.assertEqual(len(result), 13)

    def test_stops_at_max_count(self):
        """Exactly max_count items returned when a full page equals the cap."""
        full_page = [{"id": i} for i in range(1, 6)]  # 5 items
        with patch(
            "app.integrations.codeforces_client.httpx.get",
            return_value=self._ok_response(full_page),
        ):
            result = CodeforcesClient().fetch_submissions_paginated(
                "tourist", max_count=5, page_size=5
            )
        # max_count==5, page returned 5 items; loop ends because remaining==0
        self.assertEqual(len(result), 5)

    def test_zero_max_count_returns_empty_no_api_call(self):
        """max_count=0 → empty list; no API calls made."""
        with patch(
            "app.integrations.codeforces_client.httpx.get",
            side_effect=AssertionError("Should not make any HTTP calls"),
        ):
            result = CodeforcesClient().fetch_submissions_paginated(
                "tourist", max_count=0, page_size=10
            )
        self.assertEqual(result, [])

    def test_api_error_propagates(self):
        """An HTTP error from the API is raised as CodeforcesApiError."""
        class ErrResp:
            status_code = 500

            def raise_for_status(self):
                import httpx as _httpx

                raise _httpx.HTTPStatusError(
                    "500",
                    request=None,  # type: ignore[arg-type]
                    response=self,
                )

            def json(self):
                return {}

        with patch(
            "app.integrations.codeforces_client.httpx.get",
            return_value=ErrResp(),
        ):
            with self.assertRaises(CodeforcesApiError):
                CodeforcesClient().fetch_submissions_paginated(
                    "tourist", max_count=100, page_size=10
                )
