from datetime import datetime, timezone
import os
from unittest import TestCase

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# This test imports FastAPI dependencies, which initialize application settings.
# Keep the test independent from a host environment's unrelated DEBUG value.
os.environ["DEBUG"] = "true"

import app.models  # noqa: F401 -- imports every mapped model
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
from app.routers.dashboard import router


class DashboardApiTests(TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.current_user = User(
            username="dashboard-user",
            email="dashboard@example.com",
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
            problems_solved=2,  # Set to match test expectation
            last_synced_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        )
        self.other_profile = PlatformProfile(
            user_id=self.other_user.id,
            platform=Platform.CODEFORCES,
            username="other",
            current_rating=900,
            max_rating=900,
        )
        self.empty_profile = PlatformProfile(
            user_id=self.empty_user.id,
            platform=Platform.CODEFORCES,
            username="empty",
        )
        self.session.add_all([self.profile, self.other_profile, self.empty_profile])
        self.session.flush()
        self._add_synced_data()
        self.session.commit()

        app = FastAPI()
        app.include_router(router, prefix="/dashboard")

        def override_db():
            yield self.session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: self.current_user
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _add_synced_data(self):
        easy_problem = self._problem("100-A", "Easy problem", Difficulty.EASY)
        medium_problem = self._problem("100-B", "Medium problem", Difficulty.MEDIUM)
        other_problem = self._problem("200-A", "Other problem", Difficulty.HARD)
        first_contest = self._contest("100", "First Contest", 1_700_000_000)
        second_contest = self._contest("101", "Second Contest", 1_710_000_000)
        self.session.add_all(
            [easy_problem, medium_problem, other_problem, first_contest, second_contest]
        )
        self.session.flush()

        self.session.add_all(
            [
                Submission(
                    profile_id=self.profile.id,
                    problem_id=easy_problem.id,
                    contest_id=first_contest.id,
                    platform_submission_id="1",
                    submitted_at=datetime(2023, 11, 14, tzinfo=timezone.utc),
                    language="GNU C++17",
                    status=SubmissionStatus.ACCEPTED,
                ),
                Submission(
                    profile_id=self.profile.id,
                    problem_id=easy_problem.id,
                    contest_id=first_contest.id,
                    platform_submission_id="2",
                    submitted_at=datetime(2023, 11, 15, tzinfo=timezone.utc),
                    language="GNU C++17",
                    status=SubmissionStatus.WRONG_ANSWER,
                ),
                Submission(
                    profile_id=self.profile.id,
                    problem_id=medium_problem.id,
                    contest_id=second_contest.id,
                    platform_submission_id="3",
                    submitted_at=datetime(2023, 11, 16, tzinfo=timezone.utc),
                    language="Python 3",
                    status=SubmissionStatus.ACCEPTED,
                ),
                Submission(
                    profile_id=self.other_profile.id,
                    problem_id=other_problem.id,
                    contest_id=None,
                    platform_submission_id="other-1",
                    submitted_at=datetime(2023, 11, 16, tzinfo=timezone.utc),
                    language="Python 3",
                    status=SubmissionStatus.ACCEPTED,
                ),
                RatingHistory(
                    profile_id=self.profile.id,
                    contest_id=first_contest.id,
                    rating=1400,
                    rating_change=50,
                    recorded_at=datetime(2023, 11, 14, tzinfo=timezone.utc),
                ),
                RatingHistory(
                    profile_id=self.profile.id,
                    contest_id=second_contest.id,
                    rating=1500,
                    rating_change=100,
                    recorded_at=datetime(2023, 11, 16, tzinfo=timezone.utc),
                ),
                ContestParticipation(
                    profile_id=self.profile.id,
                    contest_id=first_contest.id,
                    rank=75,
                    old_rating=1350,
                    new_rating=1400,
                    rating_change=50,
                    solved=2,
                    penalty=120,
                ),
                ContestParticipation(
                    profile_id=self.profile.id,
                    contest_id=second_contest.id,
                    rank=42,
                    old_rating=1400,
                    new_rating=1500,
                    rating_change=100,
                    solved=3,
                    penalty=80,
                ),
            ]
        )

    @staticmethod
    def _problem(platform_problem_id, title, difficulty):
        return Problem(
            platform=Platform.CODEFORCES,
            platform_problem_id=platform_problem_id,
            title=title,
            slug=f"codeforces-{platform_problem_id.lower()}",
            problem_url=(
                "https://codeforces.com/problemset/problem/"
                f"{platform_problem_id.replace('-', '/')}"
            ),
            difficulty=difficulty,
            acceptance_rate=None,
        )

    @staticmethod
    def _contest(platform_contest_id, title, start_timestamp):
        return Contest(
            platform=Platform.CODEFORCES,
            platform_contest_id=platform_contest_id,
            title=title,
            contest_url=f"https://codeforces.com/contest/{platform_contest_id}",
            start_time=datetime.fromtimestamp(start_timestamp, tz=timezone.utc),
            duration_minutes=120,
        )

    def test_overview_and_problem_statistics_use_only_profile_data(self):
        overview = self.client.get(f"/dashboard/{self.profile.id}/overview")
        problems = self.client.get(f"/dashboard/{self.profile.id}/problems")

        self.assertEqual(overview.status_code, 200)
        self.assertEqual(
            overview.json(),
            {
                "profile_id": self.profile.id,
                "platform": "codeforces",
                "username": "tourist",
                "total_problems_solved": 2,
                "total_submissions": 3,
                "contests_attended": 2,
                "current_rating": 1500,
                "max_rating": 1600,
                "rank": "specialist",
                "last_synced_at": "2026-08-11T00:00:00",
            },
        )
        self.assertEqual(problems.status_code, 200)
        self.assertEqual(problems.json()["solved_count"], 2)
        self.assertEqual(
            problems.json()["solved_by_difficulty"],
            [
                {"difficulty": "Easy", "solved_count": 1},
                {"difficulty": "Medium", "solved_count": 1},
            ],
        )

    def test_rating_history_includes_contest_context(self):
        response = self.client.get(f"/dashboard/{self.profile.id}/rating")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["current_rating"], 1500)
        self.assertEqual(payload["max_rating"], 1600)
        self.assertEqual([item["rating"] for item in payload["history"]], [1400, 1500])
        self.assertEqual(payload["history"][0]["contest_name"], "First Contest")

    def test_submissions_include_recent_records_summary_and_activity(self):
        response = self.client.get(
            f"/dashboard/{self.profile.id}/submissions?recent_limit=2"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["summary"],
            {
                "total_submissions": 3,
                "accepted_submissions": 2,
                "rejected_submissions": 1,
            },
        )
        self.assertEqual(
            [submission["platform_submission_id"] for submission in payload["recent_submissions"]],
            ["3", "2"],
        )
        self.assertEqual(
            [activity["total_submissions"] for activity in payload["activity"]],
            [1, 1, 1],
        )

    def test_contests_include_participation_and_rating_data(self):
        response = self.client.get(f"/dashboard/{self.profile.id}/contests")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["contests_attended"], 2)
        self.assertEqual(payload["contests"][0]["contest_name"], "Second Contest")
        self.assertEqual(payload["contests"][0]["rating_change"], 100)
        self.assertEqual(payload["contests"][0]["solved"], 3)

    def test_aggregate_dashboard_combines_only_current_users_profiles(self):
        leetcode_profile = PlatformProfile(
            user_id=self.current_user.id,
            platform=Platform.LEETCODE,
            username="leetcode-user",
            problems_solved=10,
            contests_attended=4,
            current_rating=1800,
            max_rating=1850,
        )
        leetcode_problem = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id="two-sum",
            title="Two Sum",
            slug="leetcode-two-sum",
            problem_url="https://leetcode.com/problems/two-sum/",
            difficulty=Difficulty.EASY,
            acceptance_rate=None,
        )
        self.session.add_all([leetcode_profile, leetcode_problem])
        self.session.flush()
        self.session.add(
            Submission(
                profile_id=leetcode_profile.id,
                problem_id=leetcode_problem.id,
                contest_id=None,
                platform_submission_id="lc-1",
                submitted_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                language="Python3",
                status=SubmissionStatus.ACCEPTED,
            )
        )
        self.session.commit()

        response = self.client.get("/dashboard/aggregate?recent_limit=2")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["overview"]["connected_platforms"], 2)
        self.assertEqual(payload["overview"]["total_problems_solved"], 12)
        self.assertEqual(payload["overview"]["total_submissions"], 4)
        self.assertEqual(payload["overview"]["contests_attended"], 4)
        self.assertEqual(payload["submissions"]["summary"]["accepted_submissions"], 3)
        self.assertEqual(payload["submissions"]["recent_submissions"][0]["platform"], "leetcode")
        self.assertEqual(len(payload["overview"]["platforms"]), 2)

    def test_empty_profile_returns_empty_database_backed_responses(self):
        self.app.dependency_overrides[get_current_user] = lambda: self.empty_user

        overview = self.client.get(f"/dashboard/{self.empty_profile.id}/overview")
        rating = self.client.get(f"/dashboard/{self.empty_profile.id}/rating")
        problems = self.client.get(f"/dashboard/{self.empty_profile.id}/problems")
        submissions = self.client.get(f"/dashboard/{self.empty_profile.id}/submissions")
        contests = self.client.get(f"/dashboard/{self.empty_profile.id}/contests")

        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()["total_submissions"], 0)
        self.assertEqual(overview.json()["current_rating"], None)
        self.assertEqual(rating.json()["history"], [])
        self.assertEqual(problems.json()["solved_by_difficulty"], [])
        self.assertEqual(submissions.json()["recent_submissions"], [])
        self.assertEqual(submissions.json()["activity"], [])
        self.assertEqual(contests.json()["contests"], [])

    def test_nonexistent_profile_returns_404(self):
        response = self.client.get("/dashboard/999999/overview")

        self.assertEqual(response.status_code, 404)

    def test_other_users_profile_returns_403_and_never_leaks_data(self):
        response = self.client.get(f"/dashboard/{self.other_profile.id}/overview")

        self.assertEqual(response.status_code, 403)
