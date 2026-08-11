"""Tests for the Analytics API.

Uses SQLite in-memory database and FastAPI TestClient.
Does NOT call the real Codeforces API.

Test cases:
 1. Summary statistics for a synced profile
 2. Submission activity data
 3. Difficulty distribution
 4. Rating progression
 5. Contest performance
 6. Empty profile returns empty/zero data
 7. Non-existent profile returns 404
"""

import os
from datetime import datetime, timezone
from unittest import TestCase

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DEBUG", "true")

import app.models  # noqa: F401
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.base import Base
from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.enums import Difficulty, Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.models.user import User
from app.routers.analytics import router


class AnalyticsApiTests(TestCase):
    """Full analytics API test suite using in-memory SQLite."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

        self.current_user = User(
            username="analytics-user",
            email="analytics@example.com",
            password_hash="hash",
        )
        self.other_user = User(
            username="other-user",
            email="other@example.com",
            password_hash="hash",
        )
        self.empty_user = User(
            username="empty-user",
            email="empty@example.com",
            password_hash="hash",
        )
        self.session.add_all([self.current_user, self.other_user, self.empty_user])
        self.session.flush()

        self.profile = PlatformProfile(
            user_id=self.current_user.id,
            platform=Platform.CODEFORCES,
            username="tourist",
            current_rating=1500,
            max_rating=1600,
            rank="specialist",
            last_synced_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        )
        self.other_profile = PlatformProfile(
            user_id=self.other_user.id,
            platform=Platform.CODEFORCES,
            username="other",
            current_rating=900,
            max_rating=950,
        )
        self.empty_profile = PlatformProfile(
            user_id=self.empty_user.id,
            platform=Platform.CODEFORCES,
            username="empty",
        )
        self.session.add_all(
            [self.profile, self.other_profile, self.empty_profile]
        )
        self.session.flush()
        self._add_synced_data()
        self.session.commit()

        _app = FastAPI()
        _app.include_router(router)

        def override_db():
            yield self.session

        _app.dependency_overrides[get_db] = override_db
        _app.dependency_overrides[get_current_user] = lambda: self.current_user

        self.app = _app
        self.client = TestClient(_app)

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _add_synced_data(self):
        easy = self._problem("100-A", "Easy Problem", Difficulty.EASY)
        medium = self._problem("100-B", "Medium Problem", Difficulty.MEDIUM)
        hard = self._problem("100-C", "Hard Problem", Difficulty.HARD)
        other = self._problem("200-A", "Other Problem", Difficulty.HARD)
        c1 = self._contest("100", "First Contest", 1_700_000_000)
        c2 = self._contest("101", "Second Contest", 1_710_000_000)
        self.session.add_all([easy, medium, hard, other, c1, c2])
        self.session.flush()

        self.session.add_all(
            [
                # profile submissions
                Submission(
                    profile_id=self.profile.id,
                    problem_id=easy.id,
                    contest_id=c1.id,
                    platform_submission_id="s1",
                    submitted_at=datetime(2023, 11, 14, tzinfo=timezone.utc),
                    language="GNU C++17",
                    status=SubmissionStatus.ACCEPTED,
                ),
                Submission(
                    profile_id=self.profile.id,
                    problem_id=easy.id,
                    contest_id=c1.id,
                    platform_submission_id="s2",
                    submitted_at=datetime(2023, 11, 15, tzinfo=timezone.utc),
                    language="GNU C++17",
                    status=SubmissionStatus.WRONG_ANSWER,
                ),
                Submission(
                    profile_id=self.profile.id,
                    problem_id=medium.id,
                    contest_id=c2.id,
                    platform_submission_id="s3",
                    submitted_at=datetime(2023, 11, 16, tzinfo=timezone.utc),
                    language="Python 3",
                    status=SubmissionStatus.ACCEPTED,
                ),
                Submission(
                    profile_id=self.profile.id,
                    problem_id=hard.id,
                    contest_id=None,
                    platform_submission_id="s4",
                    submitted_at=datetime(2023, 11, 16, tzinfo=timezone.utc),
                    language="Python 3",
                    status=SubmissionStatus.WRONG_ANSWER,
                ),
                # other profile's submission — must never appear in analytics
                Submission(
                    profile_id=self.other_profile.id,
                    problem_id=other.id,
                    contest_id=None,
                    platform_submission_id="o1",
                    submitted_at=datetime(2023, 11, 16, tzinfo=timezone.utc),
                    language="Python 3",
                    status=SubmissionStatus.ACCEPTED,
                ),
                # rating history
                RatingHistory(
                    profile_id=self.profile.id,
                    contest_id=c1.id,
                    rating=1400,
                    rating_change=50,
                    recorded_at=datetime(2023, 11, 14, tzinfo=timezone.utc),
                ),
                RatingHistory(
                    profile_id=self.profile.id,
                    contest_id=c2.id,
                    rating=1500,
                    rating_change=100,
                    recorded_at=datetime(2023, 11, 16, tzinfo=timezone.utc),
                ),
                # contest participations
                ContestParticipation(
                    profile_id=self.profile.id,
                    contest_id=c1.id,
                    rank=75,
                    old_rating=1350,
                    new_rating=1400,
                    rating_change=50,
                    solved=2,
                    penalty=120,
                ),
                ContestParticipation(
                    profile_id=self.profile.id,
                    contest_id=c2.id,
                    rank=42,
                    old_rating=1400,
                    new_rating=1500,
                    rating_change=100,
                    solved=3,
                    penalty=80,
                ),
            ]
        )

    # ------------------------------------------------------------------
    # Helper factories
    # ------------------------------------------------------------------

    @staticmethod
    def _problem(pid, title, difficulty):
        return Problem(
            platform=Platform.CODEFORCES,
            platform_problem_id=pid,
            title=title,
            slug=f"cf-{pid.lower()}",
            problem_url=f"https://codeforces.com/problemset/problem/{pid.replace('-', '/')}",
            difficulty=difficulty,
            acceptance_rate=None,
        )

    @staticmethod
    def _contest(cid, title, ts):
        return Contest(
            platform=Platform.CODEFORCES,
            platform_contest_id=cid,
            title=title,
            contest_url=f"https://codeforces.com/contest/{cid}",
            start_time=datetime.fromtimestamp(ts, tz=timezone.utc),
            duration_minutes=120,
        )

    # ------------------------------------------------------------------
    # Test 1: Summary statistics
    # ------------------------------------------------------------------

    def test_summary_statistics(self):
        resp = self.client.get(f"/analytics/{self.profile.id}/summary")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["profile_id"], self.profile.id)
        self.assertEqual(data["platform"], "codeforces")
        self.assertEqual(data["username"], "tourist")
        self.assertEqual(data["total_submissions"], 4)
        self.assertEqual(data["accepted_submissions"], 2)
        self.assertEqual(data["rejected_submissions"], 2)
        # 2 distinct problems solved (easy + medium via accepted submissions)
        self.assertEqual(data["solved_problems"], 2)
        self.assertEqual(data["contests_attended"], 2)
        self.assertEqual(data["current_rating"], 1500)
        self.assertEqual(data["max_rating"], 1600)
        self.assertEqual(data["rank"], "specialist")
        # acceptance_rate = 2/4 = 0.5
        self.assertAlmostEqual(data["acceptance_rate"], 0.5, places=4)

    # ------------------------------------------------------------------
    # Test 2: Submission activity
    # ------------------------------------------------------------------

    def test_submission_activity(self):
        resp = self.client.get(
            f"/analytics/{self.profile.id}/submission-activity"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["profile_id"], self.profile.id)
        activity = data["activity"]
        # 3 distinct calendar days: Nov 14, 15, 16
        self.assertEqual(len(activity), 3)
        dates = [a["date"] for a in activity]
        self.assertIn("2023-11-14", dates)
        self.assertIn("2023-11-15", dates)
        self.assertIn("2023-11-16", dates)

        day14 = next(a for a in activity if a["date"] == "2023-11-14")
        self.assertEqual(day14["total_submissions"], 1)
        self.assertEqual(day14["accepted_submissions"], 1)
        self.assertEqual(day14["rejected_submissions"], 0)

        day16 = next(a for a in activity if a["date"] == "2023-11-16")
        self.assertEqual(day16["total_submissions"], 2)
        self.assertEqual(day16["accepted_submissions"], 1)
        self.assertEqual(day16["rejected_submissions"], 1)

    # ------------------------------------------------------------------
    # Test 3: Difficulty distribution
    # ------------------------------------------------------------------

    def test_difficulty_distribution(self):
        resp = self.client.get(
            f"/analytics/{self.profile.id}/difficulty-distribution"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["profile_id"], self.profile.id)
        buckets = {b["difficulty"]: b["solved_count"] for b in data["solved_by_difficulty"]}
        # Only Easy and Medium have accepted submissions
        self.assertEqual(buckets.get("Easy"), 1)
        self.assertEqual(buckets.get("Medium"), 1)
        # Hard problem was wrong_answer — should not appear
        self.assertNotIn("Hard", buckets)

    # ------------------------------------------------------------------
    # Test 4: Rating progression
    # ------------------------------------------------------------------

    def test_rating_progression(self):
        resp = self.client.get(
            f"/analytics/{self.profile.id}/rating-progression"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["profile_id"], self.profile.id)
        self.assertEqual(data["current_rating"], 1500)
        self.assertEqual(data["max_rating"], 1600)
        history = data["history"]
        self.assertEqual(len(history), 2)
        self.assertEqual([h["rating"] for h in history], [1400, 1500])
        self.assertEqual(history[0]["contest_name"], "First Contest")
        self.assertEqual(history[0]["rating_change"], 50)
        self.assertEqual(history[1]["contest_name"], "Second Contest")
        self.assertEqual(history[1]["rating_change"], 100)

    # ------------------------------------------------------------------
    # Test 5: Contest performance
    # ------------------------------------------------------------------

    def test_contest_performance(self):
        resp = self.client.get(
            f"/analytics/{self.profile.id}/contest-performance"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["profile_id"], self.profile.id)
        self.assertEqual(data["contests_attended"], 2)
        contests = data["contests"]
        self.assertEqual(len(contests), 2)
        # Ordered by start_time desc — Second Contest first
        self.assertEqual(contests[0]["contest_name"], "Second Contest")
        self.assertEqual(contests[0]["rank"], 42)
        self.assertEqual(contests[0]["rating_change"], 100)
        self.assertEqual(contests[0]["solved"], 3)

        self.assertEqual(contests[1]["contest_name"], "First Contest")
        self.assertEqual(contests[1]["rank"], 75)
        self.assertEqual(contests[1]["solved"], 2)
        self.assertEqual(contests[1]["penalty"], 120)

    # ------------------------------------------------------------------
    # Test 6: Empty profile returns empty / zero data
    # ------------------------------------------------------------------

    def test_empty_profile_returns_zero_data(self):
        self.app.dependency_overrides[get_current_user] = lambda: self.empty_user

        summary = self.client.get(f"/analytics/{self.empty_profile.id}/summary")
        activity = self.client.get(
            f"/analytics/{self.empty_profile.id}/submission-activity"
        )
        difficulty = self.client.get(
            f"/analytics/{self.empty_profile.id}/difficulty-distribution"
        )
        rating = self.client.get(
            f"/analytics/{self.empty_profile.id}/rating-progression"
        )
        contests = self.client.get(
            f"/analytics/{self.empty_profile.id}/contest-performance"
        )

        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["total_submissions"], 0)
        self.assertEqual(summary.json()["solved_problems"], 0)
        self.assertEqual(summary.json()["contests_attended"], 0)
        self.assertIsNone(summary.json()["acceptance_rate"])

        self.assertEqual(activity.status_code, 200)
        self.assertEqual(activity.json()["activity"], [])

        self.assertEqual(difficulty.status_code, 200)
        self.assertEqual(difficulty.json()["solved_by_difficulty"], [])

        self.assertEqual(rating.status_code, 200)
        self.assertEqual(rating.json()["history"], [])

        self.assertEqual(contests.status_code, 200)
        self.assertEqual(contests.json()["contests_attended"], 0)
        self.assertEqual(contests.json()["contests"], [])

    # ------------------------------------------------------------------
    # Test 7: Non-existent profile returns 404
    # ------------------------------------------------------------------

    def test_nonexistent_profile_returns_404(self):
        resp = self.client.get("/analytics/999999/summary")
        self.assertEqual(resp.status_code, 404)
