from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 -- imports every mapped model
from app.integrations.codeforces_client import (
    CodeforcesApiError,
    CodeforcesClient,
    CodeforcesUserNotFoundError,
)
from app.models.base import Base
from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.enums import Platform
from app.models.platform_profile import PlatformProfile
from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.models.user import User
from app.services.sync_service import (
    CodeforcesSyncError,
    CodeforcesSyncService,
    CodeforcesUsernameNotFoundError,
)


class FakeCodeforcesClient:
    def __init__(self, profile, submissions, ratings, contests):
        self.profile = profile
        self.submissions = submissions
        self.ratings = ratings
        self.contests = contests

    def fetch_profile(self, username):
        if isinstance(self.profile, Exception):
            raise self.profile
        return self.profile

    def fetch_submissions(self, username):
        return self.submissions

    def fetch_submissions_paginated(self, username, max_count=1000, page_size=100):
        """Delegates to the static submissions list for backward-compatible tests."""
        return self.submissions[:max_count]

    def fetch_rating_history(self, username):
        return self.ratings

    def fetch_contests(self):
        return self.contests


class CodeforcesSyncServiceTests(TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.user = User(
            username="sync-user",
            email="sync@example.com",
            password_hash="hash",
        )
        self.session.add(self.user)
        self.session.flush()
        self.profile = PlatformProfile(
            user_id=self.user.id,
            platform=Platform.CODEFORCES,
            username="tourist",
            current_rating=900,
            max_rating=900,
            rank="pupil",
            problems_solved=7,
            contests_attended=3,
        )
        self.session.add(self.profile)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_nonexistent_handle_is_a_specific_service_error(self):
        service = CodeforcesSyncService(
            self.session,
            FakeCodeforcesClient(
                CodeforcesUserNotFoundError("not found"), [], [], []
            ),
        )

        with self.assertRaises(CodeforcesUsernameNotFoundError):
            service.sync_codeforces_profile(self.profile.id, self.user.id)

        self.assertIsNone(
            self.session.get(PlatformProfile, self.profile.id).last_synced_at
        )

    def test_malformed_data_after_an_insert_rolls_back_everything(self):
        valid_submission = {
            "id": 1,
            "contestId": 100,
            "creationTimeSeconds": 1_700_000_000,
            "programmingLanguage": "GNU C++17",
            "verdict": "OK",
            "problem": {
                "contestId": 100,
                "index": "A",
                "name": "Valid problem",
                "rating": 800,
            },
        }
        malformed_submission = {
            **valid_submission,
            "id": 2,
            "problem": {"contestId": 100, "index": "B"},
        }
        service = CodeforcesSyncService(
            self.session,
            FakeCodeforcesClient(
                {"rating": 1500, "maxRating": 1600, "rank": "specialist"},
                [valid_submission, malformed_submission],
                [],
                [self._contest_payload(100)],
            ),
        )

        with self.assertRaises(ValueError):
            service.sync_codeforces_profile(self.profile.id, self.user.id)

        profile = self.session.get(PlatformProfile, self.profile.id)
        self.assertEqual(profile.current_rating, 900)
        self.assertEqual(profile.max_rating, 900)
        self.assertEqual(profile.rank, "pupil")
        self.assertIsNone(profile.last_synced_at)
        self.assertEqual(self.session.query(Submission).count(), 0)
        self.assertEqual(self.session.query(Contest).count(), 0)

    def test_existing_rating_and_participation_are_updated_with_aggregates(self):
        contest = Contest(
            platform=Platform.CODEFORCES,
            platform_contest_id="100",
            title="Old title",
            contest_url="https://codeforces.com/contest/100",
            start_time=datetime(2023, 1, 1, tzinfo=timezone.utc),
            duration_minutes=120,
        )
        self.session.add(contest)
        self.session.flush()
        self.session.add_all(
            [
                RatingHistory(
                    profile_id=self.profile.id,
                    contest_id=contest.id,
                    rating=1200,
                    rating_change=100,
                    recorded_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
                ),
                ContestParticipation(
                    profile_id=self.profile.id,
                    contest_id=contest.id,
                    rank=999,
                    old_rating=1100,
                    new_rating=1200,
                    rating_change=100,
                    solved=0,
                    penalty=None,
                ),
            ]
        )
        self.session.commit()

        service = CodeforcesSyncService(
            self.session,
            FakeCodeforcesClient(
                {"rating": 1600, "maxRating": 1700, "rank": "expert"},
                [],
                [
                    {
                        "contestId": 100,
                        "oldRating": 1500,
                        "newRating": 1600,
                        "rank": 42,
                        "ratingUpdateTimeSeconds": 1_700_000_000,
                    }
                ],
                [self._contest_payload(100)],
            ),
        )

        result = service.sync_codeforces_profile(self.profile.id, self.user.id)

        self.session.refresh(self.profile)
        rating = self.session.query(RatingHistory).one()
        participation = self.session.query(ContestParticipation).one()
        self.assertEqual(result.rating_history_created, 0)
        self.assertEqual(result.contest_participations_created, 0)
        self.assertEqual(self.profile.current_rating, 1600)
        self.assertEqual(self.profile.max_rating, 1700)
        self.assertEqual(self.profile.rank, "expert")
        self.assertEqual(self.profile.problems_solved, 0)
        self.assertEqual(self.profile.contests_attended, 1)
        self.assertIsNotNone(self.profile.last_synced_at)
        self.assertEqual(rating.rating, 1600)
        self.assertEqual(rating.rating_change, 100)
        self.assertEqual(participation.rank, 42)
        self.assertEqual(participation.old_rating, 1500)
        self.assertEqual(participation.new_rating, 1600)
        self.assertEqual(participation.rating_change, 100)

    def test_api_failure_is_normalized_to_sync_error(self):
        service = CodeforcesSyncService(
            self.session,
            FakeCodeforcesClient(RuntimeError("timeout"), [], [], []),
        )

        with self.assertRaises(CodeforcesSyncError):
            service.sync_codeforces_profile(self.profile.id, self.user.id)

    @staticmethod
    def _contest_payload(contest_id):
        return {
            "id": contest_id,
            "name": "Contest 100",
            "startTimeSeconds": 1_700_000_000,
            "durationSeconds": 7_200,
        }


class CodeforcesClientTests(TestCase):
    def test_non_json_api_response_is_normalized_to_api_error(self):
        class NonJsonResponse:
            def raise_for_status(self):
                return None

            def json(self):
                raise ValueError("invalid JSON")

        with patch(
            "app.integrations.codeforces_client.httpx.get",
            return_value=NonJsonResponse(),
        ):
            with self.assertRaises(CodeforcesApiError):
                CodeforcesClient().fetch_profile("tourist")

    # ------------------------------------------------------------------
    # Regression tests for the gym=true timeout bug (502 on sync)
    #
    # Root cause: fetch_contests() was calling contest.list?gym=true which
    # consistently times out under the default 10-second read timeout,
    # producing an opaque 502 Bad Gateway on POST /sync/codeforces/{id}.
    # Fix: fetch_contests() now only calls contest.list?gym=false.
    # ------------------------------------------------------------------

    def test_fetch_contests_does_not_call_gym_endpoint(self):
        """fetch_contests must never request gym=true (it times out)."""
        captured_params = []

        class OkResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"status": "OK", "result": []}

        def fake_get(url, params=None, timeout=None):
            captured_params.append(dict(params or {}))
            return OkResponse()

        with patch("app.integrations.codeforces_client.httpx.get", side_effect=fake_get):
            CodeforcesClient().fetch_contests()

        gym_calls = [p for p in captured_params if p.get("gym") == "true"]
        self.assertEqual(
            gym_calls,
            [],
            "fetch_contests must not call contest.list?gym=true — "
            "that endpoint times out and caused a 502 on sync.",
        )

    def test_fetch_contests_calls_contest_list_exactly_once(self):
        """fetch_contests must issue exactly one HTTP request after the fix."""
        call_count = [0]

        class OkResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"status": "OK", "result": []}

        def fake_get(url, params=None, timeout=None):
            call_count[0] += 1
            return OkResponse()

        with patch("app.integrations.codeforces_client.httpx.get", side_effect=fake_get):
            CodeforcesClient().fetch_contests()

        self.assertEqual(
            call_count[0],
            1,
            "fetch_contests should make exactly 1 HTTP request (gym=false only).",
        )

    def test_timeout_raises_api_error_with_endpoint_name(self):
        """A read timeout must raise CodeforcesApiError mentioning the endpoint."""
        import httpx as _httpx

        with patch(
            "app.integrations.codeforces_client.httpx.get",
            side_effect=_httpx.ReadTimeout("timed out"),
        ):
            with self.assertRaises(CodeforcesApiError) as ctx:
                CodeforcesClient().fetch_contests()

        self.assertIn(
            "contest.list",
            str(ctx.exception),
            "The CodeforcesApiError message should name the failing endpoint.",
        )

    def test_sync_error_propagates_underlying_message(self):
        """_call_codeforces_api must raise CodeforcesSyncError with the
        original exception message rather than a generic placeholder."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        import app.models  # noqa: F401
        from app.models.base import Base
        from app.models.enums import Platform
        from app.models.platform_profile import PlatformProfile
        from app.models.user import User
        from app.services.sync_service import CodeforcesSyncError, CodeforcesSyncService

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        try:
            user = User(username="u", email="u@x.com", password_hash="h")
            session.add(user)
            session.flush()
            profile = PlatformProfile(
                user_id=user.id,
                platform=Platform.CODEFORCES,
                username="handle",
            )
            session.add(profile)
            session.commit()

            specific_message = "Codeforces API request timed out (contest.list): The read operation timed out"

            class TimingOutClient:
                def fetch_profile(self, username):
                    return {"rating": 1000, "maxRating": 1100, "rank": "pupil"}

                def fetch_submissions(self, username):
                    return []

                def fetch_submissions_paginated(self, username, max_count=1000, page_size=100):
                    return []

                def fetch_rating_history(self, username):
                    return []

                def fetch_contests(self):
                    raise RuntimeError(specific_message)

            service = CodeforcesSyncService(session, TimingOutClient())

            with self.assertRaises(CodeforcesSyncError) as ctx:
                service.sync_codeforces_profile(profile.id, user.id)

            self.assertIn(
                "timed out",
                str(ctx.exception).lower(),
                "CodeforcesSyncError should include the underlying timeout message.",
            )
        finally:
            session.close()
            Base.metadata.drop_all(engine)
            engine.dispose()

    def test_gym_contest_submission_skips_contest_association(self):
        """
        Regression test: submissions referencing gym contests (not in
        contest.list?gym=false) should be imported with contest_id=None
        rather than failing with a 502 Bad Gateway.

        Before the fix, sync raised CodeforcesSyncError:
        'Contest metadata for Codeforces contest 104857 was not returned by contest.list.'

        After the fix, the submission is imported successfully with
        contest_id=None and the sync completes.
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        import app.models  # noqa: F401
        from app.models.base import Base
        from app.models.enums import Platform
        from app.models.platform_profile import PlatformProfile
        from app.models.submission import Submission
        from app.models.user import User
        from app.services.sync_service import CodeforcesSyncService

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        try:
            user = User(username="u", email="u@x.com", password_hash="h")
            session.add(user)
            session.flush()
            profile = PlatformProfile(
                user_id=user.id,
                platform=Platform.CODEFORCES,
                username="handle",
            )
            session.add(profile)
            session.commit()

            # Submission from gym contest 104857 (not in regular contest list)
            gym_submission = {
                "id": 332146912,
                "contestId": 104857,  # Gym contest ID
                "creationTimeSeconds": 1754162939,
                "programmingLanguage": "C++23",
                "verdict": "OK",
                "problem": {
                    "contestId": 104857,
                    "index": "J",
                    "name": "Takeout Delivering",
                },
            }

            class GymContestClient:
                def fetch_profile(self, username):
                    return {"rating": 1500, "maxRating": 1600, "rank": "specialist"}

                def fetch_submissions_paginated(self, username, max_count=1000, page_size=100):
                    return [gym_submission]

                def fetch_rating_history(self, username):
                    return []

                def fetch_contests(self):
                    # Returns empty — gym contest 104857 is not in gym=false list
                    return []

            service = CodeforcesSyncService(session, GymContestClient())

            # Before fix: raises CodeforcesSyncError
            # After fix: succeeds
            result = service.sync_codeforces_profile(profile.id, user.id)

            # Verify sync succeeded
            self.assertEqual(result.submissions_created, 1)
            self.assertEqual(result.submissions_fetched, 1)
            self.assertEqual(result.problems_created, 1)
            self.assertEqual(result.contests_created, 0)

            # Verify submission was created with contest_id=None
            submission = session.query(Submission).one()
            self.assertIsNone(
                submission.contest_id,
                "Gym contest submission should have contest_id=None"
            )
            self.assertEqual(submission.platform_submission_id, "332146912")

        finally:
            session.close()
            Base.metadata.drop_all(engine)
            engine.dispose()

