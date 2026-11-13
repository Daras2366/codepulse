"""Tests for automatic 'solved' feedback on AI recommendations (Stage 4).

Coverage:
- ACCEPTED submission after a recommendation → solved feedback recorded
- submission older than the recommendation → not recorded
- recommendation outside the 14-day window → not recorded
- different user's submission → not recorded
- duplicate ACCEPTED submissions → single solved feedback
- multiple recommendations for the same problem → each marked
- LeetCode sync path and Codeforces sync path integration
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - registers all ORM models
from app.models.base import Base
from app.models.coach import CoachFeedback, CoachRecommendation, CoachRun
from app.models.enums import (
    CoachFeedbackAction,
    Difficulty,
    Platform,
)
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.user import User
from app.services.coach_feedback_service import record_solved_for_submission
from app.services.coach_feedback_service import SOLVED_MATCH_WINDOW_DAYS

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


_user_counter = 0


@pytest.fixture()
def user(db):
    global _user_counter
    _user_counter += 1
    u = User(
        username=f"syncfb{_user_counter}",
        email=f"syncfb{_user_counter}@example.com",
        password_hash="hashed",
        is_active=True,
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture()
def problem(db, user):
    p = Problem(
        platform=Platform.CODEFORCES,
        platform_problem_id=f"777-A-{user.id}",
        title="Sync Feedback Problem",
        slug=f"syncfb-{user.id}",
        problem_url=f"https://codeforces.com/problemset/problem/777/A?u={user.id}",
        difficulty=Difficulty.EASY,
    )
    db.add(p)
    db.commit()
    return p


def _make_recommendation(db, user, problem, created_at=None, rank=1):
    run = CoachRun(
        user_id=user.id,
        endpoint="ai-coach/recommend",
        cache_hit=False,
    )
    db.add(run)
    db.flush()
    rec = CoachRecommendation(
        run_id=run.id,
        user_id=user.id,
        problem_id=problem.id,
        rank=rank,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(rec)
    db.commit()
    return rec


def _solved_feedback_count(db, rec_id):
    return (
        db.query(CoachFeedback)
        .filter(
            CoachFeedback.recommendation_id == rec_id,
            CoachFeedback.action == CoachFeedbackAction.SOLVED,
        )
        .count()
    )


class TestRecordSolvedForSubmission:
    def test_accepted_after_recommendation_marks_solved(self, db, user, problem):
        rec = _make_recommendation(db, user, problem)
        submitted_at = datetime.now(timezone.utc)

        created = record_solved_for_submission(
            db,
            user_id=user.id,
            problem_id=problem.id,
            submitted_at=submitted_at,
        )
        db.commit()

        assert created == 1
        assert _solved_feedback_count(db, rec.id) == 1

    def test_submission_older_than_recommendation_ignored(self, db, user, problem):
        rec_at = datetime.now(timezone.utc)
        rec = _make_recommendation(db, user, problem, created_at=rec_at)
        # Submission happened BEFORE the recommendation was created.
        submitted_at = rec_at - timedelta(hours=1)

        created = record_solved_for_submission(
            db,
            user_id=user.id,
            problem_id=problem.id,
            submitted_at=submitted_at,
        )
        db.commit()

        assert created == 0
        assert _solved_feedback_count(db, rec.id) == 0

    def test_recommendation_outside_14_day_window_ignored(self, db, user, problem):
        old = datetime.now(timezone.utc) - timedelta(
            days=SOLVED_MATCH_WINDOW_DAYS + 1
        )
        rec = _make_recommendation(db, user, problem, created_at=old)

        created = record_solved_for_submission(
            db,
            user_id=user.id,
            problem_id=problem.id,
            submitted_at=datetime.now(timezone.utc),
        )
        db.commit()

        assert created == 0
        assert _solved_feedback_count(db, rec.id) == 0

    def test_different_user_not_matched(self, db, user, problem):
        other = User(
            username="syncfb-other",
            email="syncfb-other@example.com",
            password_hash="hashed",
            is_active=True,
        )
        db.add(other)
        db.commit()
        rec = _make_recommendation(db, other, problem)

        created = record_solved_for_submission(
            db,
            user_id=user.id,  # submission belongs to `user`, rec to `other`
            problem_id=problem.id,
            submitted_at=datetime.now(timezone.utc),
        )
        db.commit()

        assert created == 0
        assert _solved_feedback_count(db, rec.id) == 0

    def test_duplicate_accepted_submissions_single_feedback(self, db, user, problem):
        rec = _make_recommendation(db, user, problem)
        submitted_at = datetime.now(timezone.utc)

        for _ in range(2):
            record_solved_for_submission(
                db,
                user_id=user.id,
                problem_id=problem.id,
                submitted_at=submitted_at,
            )
            db.commit()

        assert _solved_feedback_count(db, rec.id) == 1

    def test_multiple_recommendations_same_problem_all_marked(
        self, db, user, problem
    ):
        rec1 = _make_recommendation(db, user, problem, rank=1)
        rec2 = _make_recommendation(db, user, problem, rank=2)

        created = record_solved_for_submission(
            db,
            user_id=user.id,
            problem_id=problem.id,
            submitted_at=datetime.now(timezone.utc),
        )
        db.commit()

        assert created == 2
        assert _solved_feedback_count(db, rec1.id) == 1
        assert _solved_feedback_count(db, rec2.id) == 1

    def test_existing_solved_feedback_not_duplicated(self, db, user, problem):
        rec = _make_recommendation(db, user, problem)
        db.add(
            CoachFeedback(
                recommendation_id=rec.id,
                action=CoachFeedbackAction.SOLVED,
            )
        )
        db.commit()

        created = record_solved_for_submission(
            db,
            user_id=user.id,
            problem_id=problem.id,
            submitted_at=datetime.now(timezone.utc),
        )
        db.commit()

        assert created == 0
        assert _solved_feedback_count(db, rec.id) == 1

    def test_non_matching_problem_ignored(self, db, user, problem):
        other_problem = Problem(
            platform=Platform.CODEFORCES,
            platform_problem_id="777-B",
            title="Other Problem",
            slug="syncfb-other-problem",
            problem_url="https://codeforces.com/problemset/problem/777/B",
            difficulty=Difficulty.MEDIUM,
        )
        db.add(other_problem)
        db.commit()
        rec = _make_recommendation(db, user, problem)

        created = record_solved_for_submission(
            db,
            user_id=user.id,
            problem_id=other_problem.id,
            submitted_at=datetime.now(timezone.utc),
        )
        db.commit()

        assert created == 0
        assert _solved_feedback_count(db, rec.id) == 0


# ---------------------------------------------------------------------------
# Sync-path integration
# ---------------------------------------------------------------------------


class _FakeLeetCodeClient:
    def __init__(self, profile, submissions):
        self.profile = profile
        self.submissions = submissions

    def fetch_profile(self, username):
        return self.profile

    def fetch_submissions(self, username, limit=100):
        return self.submissions

    def fetch_submissions_paginated(self, username):
        return self.submissions

    def fetch_rating_history(self, username):
        return []

    def fetch_contests(self):
        return []

    def fetch_problem_details(self, title_slug):
        return None


class _FakeCodeforcesClient:
    def __init__(self, profile, submissions, contests):
        self.profile = profile
        self.submissions = submissions
        self.contests = contests

    def fetch_profile(self, username):
        return self.profile

    def fetch_submissions(self, username):
        return self.submissions

    def fetch_submissions_paginated(self, username, max_count=1000, page_size=100):
        return self.submissions[:max_count]

    def fetch_rating_history(self, username):
        return []

    def fetch_contests(self):
        return self.contests


class TestSyncIntegration:
    def test_leetcode_sync_records_solved_feedback(self, db, user):
        from app.services.leetcode_sync_service import LeetCodeSyncService

        slug = "sync-fb-lc"
        problem = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id=slug,
            title="LC Sync FB",
            slug="lc-sync-fb",
            problem_url=f"https://leetcode.com/problems/{slug}/",
            difficulty=Difficulty.EASY,
        )
        profile = PlatformProfile(
            user_id=user.id, platform=Platform.LEETCODE, username="lc_sync_fb"
        )
        db.add_all([problem, profile])
        db.flush()
        rec = _make_recommendation(
            db, user, problem, created_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )

        profile_data = {
            "profile": {},
            "userContestRanking": {"rating": 1500, "globalRanking": 1},
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 1}]},
        }
        submissions_data = [
            {
                "id": 424242,
                "timestamp": int(time.time()),
                "statusDisplay": "Accepted",
                "lang": "Python3",
                "titleSlug": slug,
                "title": "LC Sync FB",
            }
        ]
        service = LeetCodeSyncService(
            db, _FakeLeetCodeClient(profile_data, submissions_data)
        )
        service.sync_profile(profile.id, user.id)

        assert _solved_feedback_count(db, rec.id) == 1

    def test_leetcode_sync_older_submission_not_counted(self, db, user):
        from app.services.leetcode_sync_service import LeetCodeSyncService

        slug = "sync-fb-lc-old"
        problem = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id=slug,
            title="LC Sync FB Old",
            slug="lc-sync-fb-old",
            problem_url=f"https://leetcode.com/problems/{slug}/",
            difficulty=Difficulty.EASY,
        )
        profile = PlatformProfile(
            user_id=user.id, platform=Platform.LEETCODE, username="lc_sync_fb_old"
        )
        db.add_all([problem, profile])
        db.flush()
        # Recommendation created AFTER the (old) submission timestamp.
        rec = _make_recommendation(db, user, problem)

        old_ts = int(time.time()) - 7200
        profile_data = {
            "profile": {},
            "userContestRanking": {"rating": 1500, "globalRanking": 1},
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 1}]},
        }
        submissions_data = [
            {
                "id": 424243,
                "timestamp": old_ts,
                "statusDisplay": "Accepted",
                "lang": "Python3",
                "titleSlug": slug,
                "title": "LC Sync FB Old",
            }
        ]
        service = LeetCodeSyncService(
            db, _FakeLeetCodeClient(profile_data, submissions_data)
        )
        service.sync_profile(profile.id, user.id)

        assert _solved_feedback_count(db, rec.id) == 0

    def test_codeforces_sync_records_solved_feedback(self, db, user):
        from app.services.sync_service import CodeforcesSyncService

        problem = Problem(
            platform=Platform.CODEFORCES,
            platform_problem_id="100-A",
            title="CF Sync FB",
            slug="cf-sync-fb",
            problem_url="https://codeforces.com/problemset/problem/100/A",
            difficulty=Difficulty.EASY,
        )
        profile = PlatformProfile(
            user_id=user.id, platform=Platform.CODEFORCES, username="cf_sync_fb"
        )
        db.add_all([problem, profile])
        db.flush()
        rec = _make_recommendation(
            db, user, problem, created_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )

        profile_data = {"rating": 1500, "maxRating": 1600, "rank": "specialist"}
        submissions_data = [
            {
                "id": 777001,
                "contestId": 100,
                "creationTimeSeconds": int(time.time()),
                "programmingLanguage": "GNU C++17",
                "verdict": "OK",
                "problem": {
                    "contestId": 100,
                    "index": "A",
                    "name": "CF Sync FB",
                    "rating": 800,
                },
            }
        ]
        contests = [
            {
                "id": 100,
                "name": "Contest 100",
                "startTimeSeconds": 1_700_000_000,
                "durationSeconds": 7_200,
            }
        ]
        service = CodeforcesSyncService(
            db, _FakeCodeforcesClient(profile_data, submissions_data, contests)
        )
        service.sync_codeforces_profile(profile.id, user.id)

        assert _solved_feedback_count(db, rec.id) == 1

    def test_codeforces_sync_non_accepted_no_feedback(self, db, user):
        from app.services.sync_service import CodeforcesSyncService

        problem = Problem(
            platform=Platform.CODEFORCES,
            platform_problem_id="200-A",
            title="CF Sync FB WA",
            slug="cf-sync-fb-wa",
            problem_url="https://codeforces.com/problemset/problem/200/A",
            difficulty=Difficulty.EASY,
        )
        profile = PlatformProfile(
            user_id=user.id, platform=Platform.CODEFORCES, username="cf_sync_fb_wa"
        )
        db.add_all([problem, profile])
        db.flush()
        rec = _make_recommendation(
            db, user, problem, created_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )

        profile_data = {"rating": 1500, "maxRating": 1600, "rank": "specialist"}
        submissions_data = [
            {
                "id": 777002,
                "contestId": 200,
                "creationTimeSeconds": int(time.time()),
                "programmingLanguage": "GNU C++17",
                "verdict": "WRONG_ANSWER",
                "problem": {
                    "contestId": 200,
                    "index": "A",
                    "name": "CF Sync FB WA",
                    "rating": 800,
                },
            }
        ]
        contests = [
            {
                "id": 200,
                "name": "Contest 200",
                "startTimeSeconds": 1_700_000_000,
                "durationSeconds": 7_200,
            }
        ]
        service = CodeforcesSyncService(
            db, _FakeCodeforcesClient(profile_data, submissions_data, contests)
        )
        service.sync_codeforces_profile(profile.id, user.id)

        assert _solved_feedback_count(db, rec.id) == 0
