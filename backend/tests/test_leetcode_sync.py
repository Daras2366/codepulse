from datetime import datetime, timezone
from unittest import TestCase

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 -- imports every mapped model
from app.models.base import Base
from app.models.contest import Contest
from app.models.contest_participation import ContestParticipation
from app.models.rating_history import RatingHistory
from app.models.enums import Platform, Difficulty, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.platform_topic_stat import PlatformTopicStat
from app.models.problem import Problem
from app.models.submission import Submission
from app.models.topic import Topic
from app.models.problem_topic import ProblemTopic
from app.models.user import User
from app.services.leetcode_sync_service import (
    LeetCodeSyncError,
    LeetCodeSyncService,
    LeetCodeUsernameNotFoundError,
)


class FakeLeetCodeClient:
    def __init__(self, profile, submissions, rating_history=None, profile_exception=None):
        self.profile = profile
        self.submissions = submissions
        self.rating_history = rating_history or []
        self.profile_exception = profile_exception

    def fetch_profile(self, username):
        if self.profile_exception:
            raise self.profile_exception
        return self.profile

    def fetch_submissions(self, username, limit=100):
        return self.submissions

    def fetch_submissions_paginated(self, username):
        # For testing, return the same submissions as the old method
        # This simulates the new paginated API behavior
        return self.submissions

    def fetch_rating_history(self, username):
        return self.rating_history

    def fetch_contests(self):
        return []

    def fetch_problem_details(self, title_slug):
        # Return mock problem details with topic tags
        mock_details = {
            "two-sum": {
                "title": "Two Sum",
                "difficulty": "Easy",
                "topicTags": [{"name": "Array"}, {"name": "Hash Table"}]
            },
            "add-two-numbers": {
                "title": "Add Two Numbers",
                "difficulty": "Medium",
                "topicTags": [{"name": "Linked List"}, {"name": "Math"}]
            }
        }
        return mock_details.get(title_slug)


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
            contests_attended=0,  # Start with 0 to test API updates
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
            service.sync_profile(self.profile.id, self.user.id)

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
                    {"difficulty": "All", "count": 2}
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

        result = service.sync_profile(self.profile.id, self.user.id)

        # Verify sync result
        self.assertEqual(result.platform, "leetcode")
        self.assertEqual(result.profile_id, self.profile.id)
        self.assertEqual(result.problems_created, 2)
        self.assertEqual(result.submissions_created, 2)
        self.assertEqual(result.submissions_fetched, 2)
        self.assertEqual(result.problems_solved, 2)  # Should use API total
        # contests_attended should be 0 since no contest data was provided in the mock
        self.assertEqual(result.contests_attended, 0)

        # Verify profile was updated
        self.session.refresh(self.profile)
        self.assertEqual(self.profile.problems_solved, 2)  # Should use API total
        self.assertEqual(self.profile.current_rating, 1800)  # Should be converted to int
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
        self.assertEqual(problems[1].difficulty, Difficulty.EASY)

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
        result1 = service.sync_profile(self.profile.id, self.user.id)
        self.assertEqual(result1.submissions_created, 1)
        self.assertEqual(result1.submissions_skipped, 0)

        # Second sync with same data
        result2 = service.sync_profile(self.profile.id, self.user.id)
        self.assertEqual(result2.submissions_created, 0)
        self.assertEqual(result2.submissions_skipped, 1)

        # Verify only one submission exists
        self.assertEqual(self.session.query(Submission).count(), 1)

    def test_remote_submission_ids_prevent_timestamp_slug_collisions(self):
        """Distinct LeetCode IDs must remain distinct attempts in activity."""
        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 1}]},
        }
        submissions_data = [
            {
                "id": "first-attempt",
                "timestamp": 1700000000,
                "statusDisplay": "Accepted",
                "lang": "Python3",
                "titleSlug": "two-sum",
                "title": "Two Sum",
            },
            {
                "id": "second-attempt",
                "timestamp": 1700000000,
                "statusDisplay": "Accepted",
                "lang": "Python3",
                "titleSlug": "two-sum",
                "title": "Two Sum",
            },
        ]

        result = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(profile_data, submissions_data),
        ).sync_profile(self.profile.id, self.user.id)

        self.assertEqual(result.submissions_created, 2)
        self.assertEqual(
            {
                submission.platform_submission_id
                for submission in self.session.query(Submission).all()
            },
            {"first-attempt", "second-attempt"},
        )

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
            service.sync_profile(self.profile.id, self.user.id)

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
            service.sync_profile(self.profile.id, self.user.id)

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

        result = service.sync_profile(self.profile.id, self.user.id)

        # Verify problem was not duplicated
        self.assertEqual(result.problems_created, 0)
        self.assertEqual(self.session.query(Problem).count(), 1)
        
        # Verify submission was linked to existing problem
        self.assertEqual(result.submissions_created, 1)
        submission = self.session.query(Submission).one()
        self.assertEqual(submission.problem_id, existing_problem.id)

    def test_problem_topics_are_synced_for_new_problems(self):
        """New problems should have their topics synced from public API."""
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

        result = service.sync_profile(self.profile.id, self.user.id)

        # Verify problem was created
        self.assertEqual(result.problems_created, 1)
        problem = self.session.query(Problem).one()
        self.assertEqual(problem.platform_problem_id, "two-sum")

        # Verify topics were created
        topics = self.session.query(Topic).all()
        self.assertEqual(len(topics), 2)
        topic_names = {t.name for t in topics}
        self.assertIn("Array", topic_names)
        self.assertIn("Hash Table", topic_names)

        # Verify problem-topic relationships were created
        problem_topics = self.session.query(ProblemTopic).all()
        self.assertEqual(len(problem_topics), 2)

    def test_problem_topics_are_backfilled_for_existing_problems(self):
        """Existing problems should have topics backfilled when encountered again."""
        # Create an existing problem without topics
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

        result = service.sync_profile(self.profile.id, self.user.id)

        # Verify problem was not duplicated
        self.assertEqual(result.problems_created, 0)
        self.assertEqual(self.session.query(Problem).count(), 1)

        # Verify topics were created via backfill
        topics = self.session.query(Topic).all()
        self.assertEqual(len(topics), 2)
        topic_names = {t.name for t in topics}
        self.assertIn("Array", topic_names)
        self.assertIn("Hash Table", topic_names)

        # Verify problem-topic relationships were created
        problem_topics = self.session.query(ProblemTopic).all()
        self.assertEqual(len(problem_topics), 2)

    def test_backfill_leetcode_topics_public_api(self):
        """Backfill method should use public API to fetch topics for existing problems."""
        # Create existing problems without topics
        problem1 = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id="two-sum",
            title="Two Sum",
            slug="leetcode-two-sum-two-sum",
            problem_url="https://leetcode.com/problems/two-sum/",
            difficulty=Difficulty.EASY,
        )
        problem2 = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id="add-two-numbers",
            title="Add Two Numbers",
            slug="leetcode-add-two-numbers-add-two-numbers",
            problem_url="https://leetcode.com/problems/add-two-numbers/",
            difficulty=Difficulty.MEDIUM,
        )
        self.session.add_all([problem1, problem2])
        self.session.flush()

        # Create submissions for these problems
        submission1 = Submission(
            profile_id=self.profile.id,
            problem_id=problem1.id,
            platform_submission_id="s1",
            submitted_at=datetime.now(timezone.utc),
            status=SubmissionStatus.ACCEPTED,
            language="Python3",
        )
        submission2 = Submission(
            profile_id=self.profile.id,
            problem_id=problem2.id,
            platform_submission_id="s2",
            submitted_at=datetime.now(timezone.utc),
            status=SubmissionStatus.ACCEPTED,
            language="Python3",
        )
        self.session.add_all([submission1, submission2])
        self.session.commit()

        # Mock client that returns topic data
        client = FakeLeetCodeClient(None, [])
        service = LeetCodeSyncService(self.session, client)

        # Run backfill
        result = service.backfill_leetcode_topics(
            profile_id=self.profile.id,
            user_id=self.user.id,
        )

        # Verify results - should process 2 problems and create topics
        self.assertEqual(result["problems_processed"], 2)
        self.assertEqual(result["problems_skipped"], 0)
        self.assertGreater(result["topics_created"], 0)
        self.assertGreater(result["topic_links_created"], 0)
        self.assertEqual(result["failed"], 0)

    def test_backfill_leetcode_topics_idempotent(self):
        """Backfill should be idempotent - running twice should not create duplicates."""
        # Create existing problem with submission
        problem = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id="two-sum",
            title="Two Sum",
            slug="leetcode-two-sum-two-sum",
            problem_url="https://leetcode.com/problems/two-sum/",
            difficulty=Difficulty.EASY,
        )
        self.session.add(problem)
        self.session.flush()

        submission = Submission(
            profile_id=self.profile.id,
            problem_id=problem.id,
            platform_submission_id="s1",
            submitted_at=datetime.now(timezone.utc),
            status=SubmissionStatus.ACCEPTED,
            language="Python3",
        )
        self.session.add(submission)
        self.session.commit()

        client = FakeLeetCodeClient(None, [])
        service = LeetCodeSyncService(self.session, client)

        # First backfill
        result1 = service.backfill_leetcode_topics(
            profile_id=self.profile.id,
            user_id=self.user.id,
        )
        self.assertEqual(result1["problems_processed"], 1)
        self.assertEqual(result1["topics_created"], 2)
        self.assertEqual(result1["topic_links_created"], 2)

        # Second backfill (should skip already-tagged problem)
        result2 = service.backfill_leetcode_topics(
            profile_id=self.profile.id,
            user_id=self.user.id,
        )
        self.assertEqual(result2["problems_processed"], 0)
        self.assertEqual(result2["problems_skipped"], 1)
        self.assertEqual(result2["topics_created"], 0)
        self.assertEqual(result2["topic_links_created"], 0)

        # Verify no duplicates were created
        self.assertEqual(self.session.query(Topic).count(), 2)
        self.assertEqual(self.session.query(ProblemTopic).count(), 2)

    def test_sync_creates_platform_topic_stats(self):
        """Sync should create PlatformTopicStat rows from tagProblemCounts."""
        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 1}]},
            "tagProblemCounts": {
                "advanced": [
                    {"tagName": "Dynamic Programming", "tagSlug": "dynamic-programming", "problemsSolved": 5}
                ],
                "intermediate": [
                    {"tagName": "Array", "tagSlug": "array", "problemsSolved": 10}
                ],
                "fundamental": [
                    {"tagName": "String", "tagSlug": "string", "problemsSolved": 3}
                ]
            }
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

        result = service.sync_profile(self.profile.id, self.user.id)

        # Verify PlatformTopicStat rows were created
        topic_stats = self.session.query(PlatformTopicStat).all()
        self.assertEqual(len(topic_stats), 3)

        # Verify specific stats
        stat_by_slug = {stat.topic_slug: stat for stat in topic_stats}
        self.assertEqual(stat_by_slug["dynamic-programming"].solved_count, 5)
        self.assertEqual(stat_by_slug["array"].solved_count, 10)
        self.assertEqual(stat_by_slug["string"].solved_count, 3)

    def test_sync_updates_existing_platform_topic_stats(self):
        """Sync should update existing PlatformTopicStat rows."""
        # Create existing topic stat
        existing_stat = PlatformTopicStat(
            profile_id=self.profile.id,
            topic_name="Array",
            topic_slug="array",
            solved_count=5,
        )
        self.session.add(existing_stat)
        self.session.commit()

        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 1}]},
            "tagProblemCounts": {
                "advanced": [],
                "intermediate": [
                    {"tagName": "Array", "tagSlug": "array", "problemsSolved": 15}
                ],
                "fundamental": []
            }
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

        result = service.sync_profile(self.profile.id, self.user.id)

        # Verify stat was updated, not duplicated
        topic_stats = self.session.query(PlatformTopicStat).all()
        self.assertEqual(len(topic_stats), 1)
        self.assertEqual(topic_stats[0].solved_count, 15)  # Updated from 5 to 15

    def test_sync_removes_stale_platform_topic_stats(self):
        """Sync should remove topic stats that are no longer in the API response."""
        # Create existing topic stats
        stat1 = PlatformTopicStat(
            profile_id=self.profile.id,
            topic_name="Array",
            topic_slug="array",
            solved_count=10,
        )
        stat2 = PlatformTopicStat(
            profile_id=self.profile.id,
            topic_name="Old Topic",
            topic_slug="old-topic",
            solved_count=5,
        )
        self.session.add_all([stat1, stat2])
        self.session.commit()

        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 1}]},
            "tagProblemCounts": {
                "advanced": [],
                "intermediate": [
                    {"tagName": "Array", "tagSlug": "array", "problemsSolved": 10}
                ],
                "fundamental": []
            }
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

        result = service.sync_profile(self.profile.id, self.user.id)

        # Verify stale stat was removed
        topic_stats = self.session.query(PlatformTopicStat).all()
        self.assertEqual(len(topic_stats), 1)
        self.assertEqual(topic_stats[0].topic_slug, "array")

    def test_sync_handles_missing_tag_problem_counts(self):
        """Sync should handle missing or null tagProblemCounts gracefully."""
        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 1}]},
            # No tagProblemCounts field
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

        # Should not raise an error
        result = service.sync_profile(self.profile.id, self.user.id)

        # Verify no topic stats were created
        topic_stats = self.session.query(PlatformTopicStat).all()
        self.assertEqual(len(topic_stats), 0)

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

        result = service.sync_profile(self.profile.id, self.user.id)

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

        result = service.sync_profile(self.profile.id, self.user.id)

        # Verify sync completed
        self.assertEqual(result.submissions_created, 0)
        self.assertEqual(result.problems_created, 0)
        self.assertEqual(result.problems_solved, 0)

        # Verify profile was updated
        self.session.refresh(self.profile)
        self.assertEqual(self.profile.current_rating, 1500)  # Should be converted to int
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
            service.sync_profile(self.profile.id, other_user.id)

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
            service.sync_profile(99999, self.user.id)

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

        result = service.sync_profile(self.profile.id, self.user.id)

        # Verify counts
        self.assertEqual(result.submissions_fetched, 2)
        self.assertEqual(result.submissions_created, 1)  # Only the new one
        self.assertEqual(result.submissions_skipped, 1)  # The duplicate
        self.assertEqual(result.problems_created, 1)  # Only add-two-numbers
        self.assertEqual(result.problems_solved, 2)  # Should use API total

    def test_leetcode_solved_count_from_api(self):
        """LeetCode solved count should come from API submitStats, not submission count."""
        profile_data = {
            "profile": {},
            "userContestRanking": None,
            "submitStats": {
                "acSubmissionNum": [
                    {"difficulty": "All", "count": 500}
                ]
            },
        }
        # Only 2 recent submissions, but API says 500 solved
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

        result = service.sync_profile(self.profile.id, self.user.id)

        # Should use API total (500), not submission count (2)
        self.assertEqual(result.problems_solved, 500)
        
        # Verify profile was updated with API total
        self.session.refresh(self.profile)
        self.assertEqual(self.profile.problems_solved, 500)

    def test_leetcode_contest_history_persistence(self):
        """LeetCode contest history should be persisted correctly."""
        rating_history_data = [
            {
                "attended": True,
                "rating": 1600,
                "ranking": 1000,
                "trendDirection": "UP",
                "problemsSolved": 3,
                "totalProblems": 4,
                "finishTimeInSeconds": 1700000000,
                "contest": {
                    "title": "Weekly Contest 300",
                    "startTime": 1699980000,
                }
            },
            {
                "attended": True,
                "rating": 1650,
                "ranking": 800,
                "trendDirection": "UP",
                "problemsSolved": 2,
                "totalProblems": 4,
                "finishTimeInSeconds": 1700086400,
                "contest": {
                    "title": "Weekly Contest 301",
                    "startTime": 1700070000,
                }
            }
        ]

        profile_data = {
            "profile": {},
            "userContestRanking": {
                "rating": 1650,
                "globalRanking": 800,
                "attendedContestsCount": 2,
            },
            "submitStats": {"acSubmissionNum": [{"difficulty": "All", "count": 100}]},
        }

        service = LeetCodeSyncService(
            self.session,
            FakeLeetCodeClient(profile_data, [], rating_history_data),
        )

        result = service.sync_profile(self.profile.id, self.user.id)

        # Verify contest participation was created
        self.assertEqual(result.contest_participations_created, 2)
        self.assertEqual(result.rating_history_created, 2)
        self.assertEqual(result.contests_created, 2)

        # Verify contests exist in database
        contests = self.session.query(Contest).filter(
            Contest.platform == Platform.LEETCODE
        ).all()
        self.assertEqual(len(contests), 2)

        # Verify contest participations exist
        participations = self.session.query(ContestParticipation).filter(
            ContestParticipation.profile_id == self.profile.id
        ).all()
        self.assertEqual(len(participations), 2)

        # Verify rating history exists
        rating_histories = self.session.query(RatingHistory).filter(
            RatingHistory.profile_id == self.profile.id
        ).all()
        self.assertEqual(len(rating_histories), 2)

        # Verify idempotency - sync again should not create duplicates
        result2 = service.sync_profile(self.profile.id, self.user.id)
        self.assertEqual(result2.contest_participations_created, 0)
        self.assertEqual(result2.rating_history_created, 0)
        self.assertEqual(result2.contests_created, 0)

        # Verify no duplicates were created
        self.assertEqual(self.session.query(Contest).filter(
            Contest.platform == Platform.LEETCODE
        ).count(), 2)
        self.assertEqual(self.session.query(ContestParticipation).filter(
            ContestParticipation.profile_id == self.profile.id
        ).count(), 2)

if __name__ == "__main__":
    import unittest
    unittest.main()
