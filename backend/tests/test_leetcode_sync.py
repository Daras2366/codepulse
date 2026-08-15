from datetime import datetime, timezone
from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 -- imports every mapped model
from app.models.base import Base
from app.models.enums import Platform, Difficulty, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.user import User
from app.services.leetcode_sync_service import (
    LeetCodeSyncError,
    LeetCodeSyncService,
    LeetCodeUsernameNotFoundError,
)


class FakeLeetCodeClient:
    def __init__(self, profile, submissions, profile_exception=None):
        self.profile = profile
        self.submissions = submissions
        self.profile_exception = profile_exception

    def fetch_profile(self, username):
        if self.profile_exception:
            raise self.profile_exception
        return self.profile

    def fetch_submissions(self, username, limit=100):
        return self.submissions
    
    def fetch_rating_history(self, username):
        return []
    
    def fetch_contests(self):
        return []


class LeetCodeSyncServiceTests(TestCase):
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
            platform=Platform.LEETCODE,
            username="testuser",
            current_rating=1500,
            max_rating=1600,
            rank="Knight",
            problems_solved=100,
            contests_attended=10,
        )
        self.session.add(self.profile)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_nonexistent_username_raises_specific_error(self):
        """Non-existent LeetCode username should raise LeetCodeUsernameNotFoundError."""
        from app.integrations.leetcode_client import LeetCodeUserNotFoundError

        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(
                None,
                [],
                profile_exception=LeetCodeUserNotFoundError("User not found"),
            ),
        )

        with self.assertRaises(LeetCodeUsernameNotFoundError):
            service.sync_leetcode_profile(self.profile.id, self.user.id)

        # Verify last_synced_at was not updated
        self.assertIsNone(
            self.session.get(PlatformProfile, self.profile.id).last_synced_at
        )

    def test_successful_sync_updates_profile_and_creates_submissions(self):
        """Successful sync should update profile stats and create submissions."""
        profile_data = {
            "profile": {},
            "userContestRanking": {
                "rating": 1800.5,
                "globalRanking": 5000,
            },
            "submitStats": {
                "acSubmissionNum": [
                    {"difficulty": "All", "count": 250}
                ]
            },
        }
        submissions_data = [
            {
                "timestamp": 1700000000,
                "statusDisplay": "Accepted",
                "lang": "Python3",
                "titleSlug": "two-sum",
                "title": "Two Sum",
            },
            {
                "timestamp": 1700001000,
                "statusDisplay": "Accepted",
                "lang": "C++",
                "titleSlug": "add-two-numbers",
                "title": "Add Two Numbers",
            },
        ]

        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(profile_data, submissions_data),
        )

        result = service.sync_leetcode_profile(self.profile.id, self.user.id)

        # Verify sync result
        self.assertEqual(result.platform, "leetcode")
        self.assertEqual(result.profile_id, self.profile.id)
        self.assertEqual(result.problems_created, 2)
        self.assertEqual(result.submissions_created, 2)
        self.assertEqual(result.submissions_fetched, 2)
        self.assertEqual(result.problems_solved, 2)
        self.assertEqual(result.contests_attended, 0)

        # Verify profile was updated
        self.session.refresh(self.profile)
        self.assertEqual(self.profile.problems_solved, 2)
        self.assertEqual(self.profile.current_rating, 1800.5)
        self.assertIsNotNone(self.profile.last_synced_at)

        # Verify submissions were created
        submissions = self.session.query(Submission).order_by(Submission.submitted_at).all()
        self.assertEqual(len(submissions), 2)
        
        self.assertEqual(submissions[0].platform_submission_id, "1700000000-two-sum")
        self.assertEqual(submissions[0].status, SubmissionStatus.ACCEPTED)
        self.assertEqual(submissions[0].language, "Python3")
        
        self.assertEqual(submissions[1].platform_submission_id, "1700001000-add-two-numbers")
        self.assertEqual(submissions[1].status, SubmissionStatus.ACCEPTED)
        self.assertEqual(submissions[1].language, "C++")

        # Verify problems were created
        problems = self.session.query(Problem).order_by(Problem.platform_problem_id).all()
        self.assertEqual(len(problems), 2)
        
        self.assertEqual(problems[0].platform_problem_id, "add-two-numbers")
        self.assertEqual(problems[0].title, "Add Two Numbers")
        self.assertEqual(problems[0].difficulty, Difficulty.MEDIUM)
        
        self.assertEqual(problems[1].platform_problem_id, "two-sum")
        self.assertEqual(problems[1].title, "Two Sum")
        self.assertEqual(problems[1].difficulty, Difficulty.MEDIUM)

    def test_duplicate_submissions_are_skipped(self):
        """Duplicate submissions should be skipped on re-sync (idempotency)."""
        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 1}]},
        }
        submission_data = {
            "timestamp": 1700000000,
            "statusDisplay": "Accepted",
            "lang": "Python3",
            "titleSlug": "two-sum",
            "title": "Two Sum",
        }

        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(profile_data, [submission_data]),
        )

        # First sync
        result1 = service.sync_leetcode_profile(self.profile.id, self.user.id)
        self.assertEqual(result1.submissions_created, 1)
        self.assertEqual(result1.submissions_skipped, 0)

        # Second sync with same data
        result2 = service.sync_leetcode_profile(self.profile.id, self.user.id)
        self.assertEqual(result2.submissions_created, 0)
        self.assertEqual(result2.submissions_skipped, 1)

        # Verify only one submission exists
        self.assertEqual(self.session.query(Submission).count(), 1)

    def test_malformed_submission_data_rolls_back_transaction(self):
        """Malformed submission data should roll back the entire transaction."""
        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 100}]},
        }
        valid_submission = {
            "timestamp": 1700000000,
            "statusDisplay": "Accepted",
            "lang": "Python3",
            "titleSlug": "two-sum",
            "title": "Two Sum",
        }
        malformed_submission = {
            "timestamp": 1700001000,
            "statusDisplay": "Accepted",
            # Missing titleSlug field
            "title": "Broken Problem",
        }

        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(profile_data, [valid_submission, malformed_submission]),
        )

        with self.assertRaises((KeyError, ValueError)):
            service.sync_leetcode_profile(self.profile.id, self.user.id)

        # Verify rollback: profile stats unchanged, no submissions created
        self.session.refresh(self.profile)
        self.assertEqual(self.profile.problems_solved, 100)
        self.assertIsNone(self.profile.last_synced_at)
        self.assertEqual(self.session.query(Submission).count(), 0)
        self.assertEqual(self.session.query(Problem).count(), 0)

    def test_api_failure_raises_sync_error(self):
        """Generic API failures should be normalized to LeetCodeSyncError."""
        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(
                None,
                [],
                profile_exception=RuntimeError("Network timeout"),
            ),
        )

        with self.assertRaises(LeetCodeSyncError):
            service.sync_leetcode_profile(self.profile.id, self.user.id)

    def test_sync_updates_existing_problems(self):
        """Sync should not duplicate existing problems."""
        # Create existing problem
        existing_problem = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id="two-sum",
            title="Two Sum",
            slug="leetcode-two-sum-two-sum",
            problem_url="https://leetcode.com/problems/two-sum/",
            difficulty=Difficulty.EASY,
        )
        self.session.add(existing_problem)
        self.session.commit()

        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 1}]},
        }
        submission_data = {
            "timestamp": 1700000000,
            "statusDisplay": "Accepted",
            "lang": "Python3",
            "titleSlug": "two-sum",
            "title": "Two Sum",
        }

        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(profile_data, [submission_data]),
        )

        result = service.sync_leetcode_profile(self.profile.id, self.user.id)

        # Verify problem was not duplicated
        self.assertEqual(result.problems_created, 0)
        self.assertEqual(self.session.query(Problem).count(), 1)
        
        # Verify submission was linked to existing problem
        self.assertEqual(result.submissions_created, 1)
        submission = self.session.query(Submission).one()
        self.assertEqual(submission.problem_id, existing_problem.id)

    def test_only_accepted_submissions_count_as_solved(self):
        """Only accepted submissions should count toward problems_solved."""
        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 1}]},
        }
        submissions_data = [
            {
                "timestamp": 1700000000,
                "statusDisplay": "Accepted",
                "lang": "Python3",
                "titleSlug": "two-sum",
                "title": "Two Sum",
            },
            {
                "timestamp": 1700001000,
                "statusDisplay": "Wrong Answer",
                "lang": "Python3",
                "titleSlug": "add-two-numbers",
                "title": "Add Two Numbers",
            },
            {
                "timestamp": 1700002000,
                "statusDisplay": "Time Limit Exceeded",
                "lang": "Python3",
                "titleSlug": "longest-substring",
                "title": "Longest Substring",
            },
        ]

        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(profile_data, submissions_data),
        )

        result = service.sync_leetcode_profile(self.profile.id, self.user.id)

        # Only 1 accepted submission
        self.assertEqual(result.problems_solved, 1)
        self.assertEqual(result.submissions_created, 3)
        
        # Verify profile updated correctly
        self.session.refresh(self.profile)
        self.assertEqual(self.profile.problems_solved, 1)

    def test_empty_submissions_list_updates_profile(self):
        """Sync with no submissions should still update profile data."""
        profile_data = {
            "profile": {},
            "userContestRanking": {
                "rating": 1500.0,
                "globalRanking": 99999,
            },
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 0}]},
        }

        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(profile_data, []),
        )

        result = service.sync_leetcode_profile(self.profile.id, self.user.id)

        # Verify sync completed
        self.assertEqual(result.submissions_created, 0)
        self.assertEqual(result.problems_created, 0)
        self.assertEqual(result.problems_solved, 0)

        # Verify profile was updated
        self.session.refresh(self.profile)
        self.assertEqual(self.profile.current_rating, 1500.0)
        self.assertEqual(self.profile.problems_solved, 0)
        self.assertIsNotNone(self.profile.last_synced_at)

    def test_profile_ownership_is_validated(self):
        """Sync should fail if profile doesn't belong to the user."""
        from app.services.base_sync_service import ProfileAccessDeniedError

        # Create a different user
        other_user = User(
            username="other-user",
            email="other@example.com",
            password_hash="hash",
        )
        self.session.add(other_user)
        self.session.flush()

        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 100}]},
        }

        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(profile_data, []),
        )

        # Try to sync profile with wrong user_id
        with self.assertRaises(ProfileAccessDeniedError):
            service.sync_leetcode_profile(self.profile.id, other_user.id)

    def test_nonexistent_profile_raises_not_found_error(self):
        """Sync should fail if profile doesn't exist."""
        from app.services.base_sync_service import PlatformProfileNotFoundError

        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 100}]},
        }

        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(profile_data, []),
        )

        # Try to sync non-existent profile
        with self.assertRaises(PlatformProfileNotFoundError):
            service.sync_leetcode_profile(99999, self.user.id)

    def test_sync_result_contains_accurate_counts(self):
        """SyncResult should contain accurate counts of all operations."""
        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 2}]},
        }
        
        # First, insert one submission
        existing_problem = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id="two-sum",
            title="Two Sum",
            slug="leetcode-two-sum-two-sum",
            problem_url="https://leetcode.com/problems/two-sum/",
            difficulty=Difficulty.EASY,
        )
        self.session.add(existing_problem)
        self.session.flush()
        
        existing_submission = Submission(
            profile_id=self.profile.id,
            problem_id=existing_problem.id,
            platform_submission_id="1700000000-two-sum",
            submitted_at=datetime.fromtimestamp(1700000000, tz=timezone.utc),
            status=SubmissionStatus.ACCEPTED,
            language="Python3",
        )
        self.session.add(existing_submission)
        self.session.commit()

        submissions_data = [
            {
                "timestamp": 1700000000,
                "statusDisplay": "Accepted",
                "lang": "Python3",
                "titleSlug": "two-sum",
                "title": "Two Sum",
            },
            {
                "timestamp": 1700001000,
                "statusDisplay": "Accepted",
                "lang": "C++",
                "titleSlug": "add-two-numbers",
                "title": "Add Two Numbers",
            },
        ]

        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(profile_data, submissions_data),
        )

        result = service.sync_leetcode_profile(self.profile.id, self.user.id)

        # Verify counts
        self.assertEqual(result.submissions_fetched, 2)
        self.assertEqual(result.submissions_created, 1)  # Only the new one
        self.assertEqual(result.submissions_skipped, 1)  # The duplicate
        self.assertEqual(result.problems_created, 1)  # Only add-two-numbers
        self.assertEqual(result.problems_solved, 2)  # Both are accepted
