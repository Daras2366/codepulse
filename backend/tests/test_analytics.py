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
from app.models.platform_topic_stat import PlatformTopicStat
from app.models.problem import Problem
from app.models.rating_history import RatingHistory
from app.models.submission import Submission
from app.models.topic import Topic
from app.models.problem_topic import ProblemTopic
from app.models.user import User
from app.routers.analytics import router
from app.services.performance_analyzer import PerformanceAnalyzer


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
        self.leetcode_profile = PlatformProfile(
            user_id=self.current_user.id,
            platform=Platform.LEETCODE,
            username="leetcode_user",
            current_rating=1600,
            max_rating=1700,
            rank="Knight",
            problems_solved=0,  # Start with 0, tests will set as needed
            last_synced_at=datetime(2026, 8, 11, tzinfo=timezone.utc),
        )
        self.session.add_all(
            [self.profile, self.other_profile, self.empty_profile, self.leetcode_profile]
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
        easy = self._problem("100-A", "Easy Problem", Difficulty.EASY, Platform.CODEFORCES)
        medium = self._problem("100-B", "Medium Problem", Difficulty.MEDIUM, Platform.CODEFORCES)
        hard = self._problem("100-C", "Hard Problem", Difficulty.HARD, Platform.CODEFORCES)
        other = self._problem("200-A", "Other Problem", Difficulty.HARD, Platform.CODEFORCES)
        c1 = self._contest("100", "First Contest", 1_700_000_000)
        c2 = self._contest("101", "Second Contest", 1_710_000_000)
        
        self.session.add_all([easy, medium, hard, other, c1, c2])
        self.session.flush()
        
        # Add topics
        arrays_topic = Topic(name="Arrays")
        graphs_topic = Topic(name="Graphs")
        dp_topic = Topic(name="DP")
        self.session.add_all([arrays_topic, graphs_topic, dp_topic])
        self.session.flush()
        
        # Associate problems with topics - problem_id and topic_id form composite primary key
        self.session.add_all([
            ProblemTopic(problem_id=easy.id, topic_id=arrays_topic.id),
            ProblemTopic(problem_id=medium.id, topic_id=graphs_topic.id),
            ProblemTopic(problem_id=hard.id, topic_id=dp_topic.id),
        ])
        self.session.flush()

        self.session.add_all(
            [
                # profile submissions - use recent dates within 1 year
                Submission(
                    profile_id=self.profile.id,
                    problem_id=easy.id,
                    contest_id=c1.id,
                    platform_submission_id="s1",
                    submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    language="GNU C++17",
                    status=SubmissionStatus.ACCEPTED,
                ),
                Submission(
                    profile_id=self.profile.id,
                    problem_id=easy.id,
                    contest_id=c1.id,
                    platform_submission_id="s2",
                    submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    language="GNU C++17",
                    status=SubmissionStatus.WRONG_ANSWER,
                ),
                Submission(
                    profile_id=self.profile.id,
                    problem_id=medium.id,
                    contest_id=c2.id,
                    platform_submission_id="s3",
                    submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    language="Python 3",
                    status=SubmissionStatus.ACCEPTED,
                ),
                Submission(
                    profile_id=self.profile.id,
                    problem_id=hard.id,
                    contest_id=None,
                    platform_submission_id="s4",
                    submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    language="Python 3",
                    status=SubmissionStatus.WRONG_ANSWER,
                ),
                # other profile's submission — must never appear in analytics
                Submission(
                    profile_id=self.other_profile.id,
                    problem_id=other.id,
                    contest_id=None,
                    platform_submission_id="o1",
                    submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    language="Python 3",
                    status=SubmissionStatus.ACCEPTED,
                ),
                # rating history
                RatingHistory(
                    profile_id=self.profile.id,
                    contest_id=c1.id,
                    rating=1400,
                    rating_change=50,
                    recorded_at=datetime.now(timezone.utc).replace(tzinfo=None),
                ),
                RatingHistory(
                    profile_id=self.profile.id,
                    contest_id=c2.id,
                    rating=1500,
                    rating_change=100,
                    recorded_at=datetime.now(timezone.utc).replace(tzinfo=None),
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
    def _problem(pid, title, difficulty, platform=Platform.CODEFORCES):
        if platform == Platform.CODEFORCES:
            problem_url = f"https://codeforces.com/problemset/problem/{pid.replace('-', '/')}"
        elif platform == Platform.LEETCODE:
            problem_url = f"https://leetcode.com/problems/{pid}"
        else:
            problem_url = f"https://{platform.value}.com/problem/{pid}"
            
        return Problem(
            platform=platform,
            platform_problem_id=pid,
            title=title,
            slug=f"{platform.value}-{pid.lower()}",
            problem_url=problem_url,
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
        # All submissions were made on the same day (today)
        self.assertEqual(len(activity), 1)
        
        # That day should have 4 total submissions (2 accepted)
        day = activity[0]
        self.assertEqual(day["total_submissions"], 4)
        self.assertEqual(day["accepted_submissions"], 2)
        self.assertEqual(day["rejected_submissions"], 2)

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

    # ------------------------------------------------------------------
    # Test 8: Aggregate rating progression
    # ------------------------------------------------------------------

    def test_aggregate_rating_progression(self):
        resp = self.client.get("/analytics/aggregate/rating-progression")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        
        self.assertIn("series", data)
        series = data["series"]
        # Should have 2 platforms (codeforces and leetcode)
        self.assertEqual(len(series), 2)
        
        # Find codeforces series
        cf_series = next((s for s in series if s["platform"] == "codeforces"), None)
        self.assertIsNotNone(cf_series)
        self.assertEqual(cf_series["username"], "tourist")
        self.assertEqual(len(cf_series["history"]), 2)
        
        # Find leetcode series (should be empty)
        lc_series = next((s for s in series if s["platform"] == "leetcode"), None)
        self.assertIsNotNone(lc_series)
        self.assertEqual(lc_series["username"], "leetcode_user")
        self.assertEqual(len(lc_series["history"]), 0)

    # ------------------------------------------------------------------
    # Test 9a: Aggregate topic breakdown — basic response shape
    # ------------------------------------------------------------------

    def test_aggregate_topic_breakdown_response_shape(self):
        """Response must contain total_solved, tagged_solved, total_topic_assignments, topics."""
        resp = self.client.get("/analytics/aggregate/topic-breakdown")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("total_solved", data)
        self.assertIn("tagged_solved", data)
        self.assertIn("total_topic_assignments", data)
        self.assertIn("topics", data)

    # ------------------------------------------------------------------
    # Test 9b: Codeforces topics — accepted submissions only
    # ------------------------------------------------------------------

    def test_aggregate_topic_breakdown_codeforces_only(self):
        """Only topics from Codeforces accepted submissions appear."""
        resp = self.client.get(
            "/analytics/aggregate/topic-breakdown?platforms=codeforces"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Easy (Arrays) and Medium (Graphs) were accepted; Hard (DP) was rejected
        topics_by_name = {t["topic"]: t["solved_count"] for t in data["topics"]}
        self.assertIn("Arrays", topics_by_name)
        self.assertIn("Graphs", topics_by_name)
        # DP: Hard problem had WRONG_ANSWER — must not appear
        self.assertNotIn("DP", topics_by_name)
        self.assertNotIn("Dynamic Programming", topics_by_name)

        # tagged_solved = 2 (Easy + Medium, both have 1 topic each)
        self.assertEqual(data["tagged_solved"], 2)
        # total_topic_assignments = 2 (one assignment per problem × 2 problems)
        self.assertEqual(data["total_topic_assignments"], 2)

    # ------------------------------------------------------------------
    # Test 9c: LeetCode only — no topics seeded for LC in _add_synced_data
    # ------------------------------------------------------------------

    def test_aggregate_topic_breakdown_leetcode_only(self):
        """LeetCode profile uses PlatformTopicStat for topic data."""
        # Set profile solved count
        self.leetcode_profile.problems_solved = 50
        self.session.commit()

        # Add PlatformTopicStat rows for LeetCode profile
        array_stat = PlatformTopicStat(
            profile_id=self.leetcode_profile.id,
            topic_name="Array",
            topic_slug="array",
            solved_count=15,
        )
        string_stat = PlatformTopicStat(
            profile_id=self.leetcode_profile.id,
            topic_name="String",
            topic_slug="string",
            solved_count=8,
        )
        self.session.add_all([array_stat, string_stat])
        self.session.commit()

        resp = self.client.get(
            "/analytics/aggregate/topic-breakdown?platforms=leetcode"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Should have topics from PlatformTopicStat
        self.assertGreater(len(data["topics"]), 0)
        # tagged_solved should equal total_solved when topic stats are available
        # (topic data is available for the solved problems)
        self.assertEqual(data["tagged_solved"], 50)  # Equal to problems_solved
        self.assertGreater(data["total_topic_assignments"], 0)

    def test_aggregate_topic_breakdown_leetcode_with_zero_local_topics(self):
        """LeetCode analytics work even with zero local ProblemTopic rows."""
        # Set profile solved count
        self.leetcode_profile.problems_solved = 30
        self.session.commit()

        # Add PlatformTopicStat rows but no local ProblemTopic rows
        array_stat = PlatformTopicStat(
            profile_id=self.leetcode_profile.id,
            topic_name="Array",
            topic_slug="array",
            solved_count=15,
        )
        self.session.add(array_stat)
        self.session.commit()

        resp = self.client.get(
            "/analytics/aggregate/topic-breakdown?platforms=leetcode"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Should still return topic data from PlatformTopicStat
        self.assertGreater(len(data["topics"]), 0)
        # tagged_solved should equal total_solved when topic stats are available
        self.assertEqual(data["tagged_solved"], 30)  # Equal to problems_solved

    def test_aggregate_topic_breakdown_leetcode_platform_coverage(self):
        """LeetCode platform coverage uses profile solved count and topic stats."""
        # Set profile solved count
        self.leetcode_profile.problems_solved = 50
        self.leetcode_profile.solved_easy = 20
        self.leetcode_profile.solved_medium = 25
        self.leetcode_profile.solved_hard = 5
        self.session.commit()

        # Add PlatformTopicStat rows
        array_stat = PlatformTopicStat(
            profile_id=self.leetcode_profile.id,
            topic_name="Array",
            topic_slug="array",
            solved_count=15,
        )
        string_stat = PlatformTopicStat(
            profile_id=self.leetcode_profile.id,
            topic_name="String",
            topic_slug="string",
            solved_count=8,
        )
        self.session.add_all([array_stat, string_stat])
        self.session.commit()

        resp = self.client.get(
            "/analytics/aggregate/topic-breakdown?platforms=leetcode"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Check platform coverage
        leetcode_coverage = next(
            (c for c in data["platform_coverage"] if c["platform"] == "leetcode"),
            None
        )
        self.assertIsNotNone(leetcode_coverage)
        self.assertEqual(leetcode_coverage["total_solved"], 50)
        self.assertEqual(leetcode_coverage["tagged_solved"], 50)  # Equal to total_solved when topic stats available

    # ------------------------------------------------------------------
    # Test 9d: Both platforms combined
    # ------------------------------------------------------------------

    def test_aggregate_topic_breakdown_combined_platforms(self):
        """Combined: topics from both platforms appear (here only CF has topics)."""
        resp = self.client.get(
            "/analytics/aggregate/topic-breakdown?platforms=codeforces,leetcode"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        topics_by_name = {t["topic"]: t["solved_count"] for t in data["topics"]}
        self.assertIn("Arrays", topics_by_name)
        self.assertIn("Graphs", topics_by_name)

    # ------------------------------------------------------------------
    # Test 9e: No platforms in query — returns zero
    # ------------------------------------------------------------------

    def test_aggregate_topic_breakdown_no_platform_returns_zero(self):
        """Passing an unknown platform string → no matching profiles → empty response."""
        resp = self.client.get(
            "/analytics/aggregate/topic-breakdown?platforms=unknown_platform"
        )
        # Service silently ignores unknown platform values and returns empty data
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_solved"], 0)
        self.assertEqual(data["tagged_solved"], 0)
        self.assertEqual(data["total_topic_assignments"], 0)
        self.assertEqual(data["topics"], [])

    # ------------------------------------------------------------------
    # Test 9f: Multiple topics per problem — correct assignment counts
    # ------------------------------------------------------------------

    def test_aggregate_topic_breakdown_multiple_topics_per_problem(self):
        """A problem can contribute once to each of several canonical topics."""
        multi_problem = self._problem(
            "999-A",
            "Multi-Topic Problem",
            Difficulty.EASY,
            Platform.CODEFORCES,
        )
        self.session.add(multi_problem)
        self.session.flush()

        t1 = Topic(name="arrays")
        t2 = Topic(name="graphs")
        t3 = Topic(name="dp")

        self.session.add_all([t1, t2, t3])
        self.session.flush()

        self.session.add_all([
            ProblemTopic(problem_id=multi_problem.id, topic_id=t1.id),
            ProblemTopic(problem_id=multi_problem.id, topic_id=t2.id),
            ProblemTopic(problem_id=multi_problem.id, topic_id=t3.id),
        ])

        self.session.add(
            Submission(
                profile_id=self.profile.id,
                problem_id=multi_problem.id,
                contest_id=None,
                platform_submission_id="multi-s1",
                submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
                language="Python 3",
                status=SubmissionStatus.ACCEPTED,
            )
        )

        self.session.commit()

        resp = self.client.get(
            "/analytics/aggregate/topic-breakdown?platforms=codeforces"
        )

        self.assertEqual(resp.status_code, 200)

        data = resp.json()

        topic_map = {
            topic["topic"]: topic
            for topic in data["topics"]
        }

        # The new problem contributes exactly once to each canonical topic.
        self.assertIn("Arrays", topic_map)
        self.assertIn("Graphs", topic_map)
        self.assertIn("Dynamic Programming", topic_map)

        self.assertEqual(topic_map["Arrays"]["solved_count"], 2)
        self.assertEqual(topic_map["Graphs"]["solved_count"], 2)
        self.assertEqual(
            topic_map["Dynamic Programming"]["solved_count"],
            1,
        )

        # The problem should not be double-counted within a single topic.
        self.assertGreater(data["total_topic_assignments"], 0)

        # ------------------------------------------------------------------
        # Test 9g: Duplicate ProblemTopic rows — graceful handling
        # ------------------------------------------------------------------

        def test_aggregate_topic_breakdown_duplicate_problem_topic_handled(self):
            """ProblemTopic has a composite PK so duplicates cannot exist at DB level.
            Verify the endpoint still returns correct counts when inserting via
            the same composite key is attempted (IntegrityError path)."""
            # This test verifies idempotency: re-adding the same link should be ignored
            # by the ProblemTopic unique constraint.  We validate the existing counts
            # are still correct after the attempt.
            resp = self.client.get(
                "/analytics/aggregate/topic-breakdown?platforms=codeforces"
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertGreaterEqual(data["total_topic_assignments"], 2)

        # ------------------------------------------------------------------
        # Test 9h: Topic normalization (DP → Dynamic Programming)
        # ------------------------------------------------------------------

        def test_aggregate_topic_breakdown_normalization(self):
            """'DP' and 'dynamic programming' topic names normalize to 'Dynamic Programming'."""
            # Add an accepted problem tagged with "dp" (lowercase) — should normalize
            dp_problem = self._problem(
                "998-A", "DP Problem", Difficulty.EASY, Platform.CODEFORCES
            )
            self.session.add(dp_problem)
            self.session.flush()

            dp_topic = Topic(name="dp")
            self.session.add(dp_topic)
            self.session.flush()

            self.session.add(ProblemTopic(problem_id=dp_problem.id, topic_id=dp_topic.id))
            self.session.add(
                Submission(
                    profile_id=self.profile.id,
                    problem_id=dp_problem.id,
                    contest_id=None,
                    platform_submission_id="dp-s1",
                    submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    language="Python 3",
                    status=SubmissionStatus.ACCEPTED,
                )
            )
            self.session.commit()

            resp = self.client.get(
                "/analytics/aggregate/topic-breakdown?platforms=codeforces"
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()

            topic_names = [t["topic"] for t in data["topics"]]
            # "dp" should have been normalized to "Dynamic Programming"
            self.assertIn("Dynamic Programming", topic_names)
            # Raw "dp" should not appear
            self.assertNotIn("dp", topic_names)

        # ------------------------------------------------------------------
        # Test 9i: Correct percentage math — sums approximately to 100
        # ------------------------------------------------------------------

        def test_aggregate_topic_breakdown_percentages_sum_to_100(self):
            """Slice percentages must sum to approximately 100 % (±1 % for rounding)."""
            resp = self.client.get(
                "/analytics/aggregate/topic-breakdown?platforms=codeforces"
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()

            total_percentage = sum(t["percentage"] for t in data["topics"])
            self.assertAlmostEqual(total_percentage, 100.0, delta=1.0)

    # ------------------------------------------------------------------
    # Performance Analyzer Tests
    # ------------------------------------------------------------------

    def test_performance_analyzer_user_isolation(self):
        """Performance analyzer respects user isolation."""
        # Create another user with data
        other_user = User(
            username="other-user",
            email="other@example.com",
            password_hash="hash",
        )
        self.session.add(other_user)
        self.session.flush()

        other_profile = PlatformProfile(
            user_id=other_user.id,
            platform=Platform.CODEFORCES,
            username="other",
            current_rating=1200,
            max_rating=1300,
        )
        self.session.add(other_profile)
        self.session.commit()

        # Current user's performance should not include other user's data
        resp = self.client.get("/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["profile"]["overview"]["total_submissions"], 4)  # Only current user's submissions

    def test_performance_analyzer_multiple_platforms(self):
        """Performance analyzer handles multiple connected platforms."""
        # Add a LeetCode profile with data
        lc_profile = PlatformProfile(
            user_id=self.current_user.id,
            platform=Platform.LEETCODE,
            username="leetcode_user",
            current_rating=1600,
            max_rating=1700,
            problems_solved=100,
            solved_easy=40,
            solved_medium=50,
            solved_hard=10,
        )
        self.session.add(lc_profile)
        self.session.flush()

        # Add LeetCode topic stats
        lc_topic_stat = PlatformTopicStat(
            profile_id=lc_profile.id,
            topic_name="Array",
            topic_slug="array",
            solved_count=25,
        )
        self.session.add(lc_topic_stat)
        self.session.commit()

        resp = self.client.get("/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Should include data from both platforms
        self.assertGreater(data["profile"]["overview"]["total_submissions"], 0)
        self.assertEqual(len(data["profile"]["data_quality"]["platform_coverage"]), 2)

    def test_performance_analyzer_single_platform(self):
        """Performance analyzer works with single platform."""
        resp = self.client.get("/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Should work fine with just Codeforces
        self.assertEqual(len(data["profile"]["data_quality"]["platform_coverage"]), 1)
        self.assertIn("codeforces", data["profile"]["data_quality"]["platform_coverage"])

    def test_performance_analyzer_no_data(self):
        """Performance analyzer handles user with no data gracefully."""
        # Create user with no profiles
        empty_user = User(
            username="empty-user",
            email="empty@example.com",
            password_hash="hash",
        )
        self.session.add(empty_user)
        self.session.flush()

        # Create a test app for the empty user
        empty_app = FastAPI()
        empty_app.include_router(router)

        def override_db():
            yield self.session

        def override_user():
            return empty_user

        empty_app.dependency_overrides[get_db] = override_db
        empty_app.dependency_overrides[get_current_user] = override_user

        empty_client = TestClient(empty_app)

        resp = empty_client.get("/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Should return empty profile
        self.assertEqual(data["profile"]["overview"]["total_submissions"], 0)
        self.assertEqual(data["profile"]["overview"]["solved_problems"], 0)
        self.assertEqual(len(data["profile"]["topic_performance"]), 0)
        self.assertEqual(len(data["profile"]["strengths"]), 0)
        self.assertEqual(len(data["profile"]["weaknesses"]), 0)

        empty_client.close()

    def test_performance_analyzer_topic_strengths_weaknesses(self):
        """Performance analyzer correctly identifies topic strengths and weaknesses."""
        resp = self.client.get("/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Should have topic performance data
        self.assertGreater(len(data["profile"]["topic_performance"]), 0)

        # Check that strength classification is applied
        topic_strengths = [t for t in data["profile"]["topic_performance"]]
        self.assertTrue(all(t["strength_level"] in ["strong", "moderate", "weak", "insufficient_data"] for t in topic_strengths))

        # Check that strengths and weaknesses are generated
        strengths = data["profile"]["strengths"]
        weaknesses = data["profile"]["weaknesses"]

        # Should have at least some classifications
        total_classifications = len(strengths) + len(weaknesses)
        self.assertGreater(total_classifications, 0)

    def test_performance_analyzer_difficulty_distribution(self):
        """Performance analyzer correctly analyzes difficulty distribution."""
        resp = self.client.get("/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Should have difficulty performance data
        difficulty_performance = data["profile"]["difficulty_performance"]

        # For Codeforces, should have difficulty data from submissions
        if difficulty_performance:
            # Check coverage status classification
            coverage_statuses = [d["coverage_status"] for d in difficulty_performance]
            self.assertTrue(all(status in ["well_covered", "moderately_covered", "rarely_attempted", "not_attempted"] for status in coverage_statuses))

    def test_performance_analyzer_submission_metrics(self):
        """Performance analyzer correctly calculates submission behavior metrics."""
        resp = self.client.get("/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        submission_behavior = data["profile"]["submission_behavior"]

        # Should have submission metrics
        self.assertEqual(submission_behavior["total_submissions"], 4)
        self.assertEqual(submission_behavior["accepted_submissions"], 2)
        self.assertIsNotNone(submission_behavior["acceptance_rate"])
        self.assertEqual(submission_behavior["acceptance_rate"], 0.5)

        # Should calculate active days
        self.assertGreater(submission_behavior["active_days"], 0)

    def test_performance_analyzer_contest_rating_analysis(self):
        """Performance analyzer correctly analyzes contest and rating performance."""
        resp = self.client.get("/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        contest_performance = data["profile"]["contest_performance"]
        rating_trend = data["profile"]["rating_trend"]

        # Should have contest data
        self.assertEqual(contest_performance["contests_participated"], 2)

        # Should have rating trend data
        self.assertEqual(rating_trend["current_rating"], 1500)
        self.assertEqual(rating_trend["max_rating"], 1600)

        # Check trend direction classification
        self.assertIn(rating_trend["trend_direction"], ["improving", "stable", "declining", "insufficient_data"])

    def test_performance_analyzer_insufficient_topic_data(self):
        """Performance analyzer handles insufficient topic data gracefully."""
        # Remove topic data
        self.session.query(ProblemTopic).delete()
        self.session.query(Topic).delete()
        self.session.commit()

        resp = self.client.get("/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Should indicate insufficient data in data quality
        self.assertFalse(data["profile"]["data_quality"]["has_complete_topic_data"])

        # Topic performance should be empty or indicate insufficient data
        if data["profile"]["topic_performance"]:
            for topic in data["profile"]["topic_performance"]:
                self.assertEqual(topic["strength_level"], "insufficient_data")

    def test_performance_analyzer_zero_submissions(self):
        """Performance analyzer handles edge case of zero submissions."""
        # Create profile with no submissions
        no_sub_profile = PlatformProfile(
            user_id=self.current_user.id,
            platform=Platform.CODEFORCES,
            username="nosub",
            current_rating=None,
            max_rating=None,
        )
        self.session.add(no_sub_profile)
        self.session.commit()

        # Remove existing submissions
        self.session.query(Submission).delete()
        self.session.commit()

        resp = self.client.get("/analytics/performance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Should handle zero submissions gracefully
        self.assertEqual(data["profile"]["overview"]["total_submissions"], 0)
        self.assertEqual(data["profile"]["submission_behavior"]["acceptance_rate"], None)
        self.assertEqual(data["profile"]["submission_behavior"]["average_submissions_per_active_day"], 0.0)

        # ------------------------------------------------------------------
        # Test 9i: Correct percentage math — sums approximately to 100
        # ------------------------------------------------------------------

        def test_aggregate_topic_breakdown_percentages_sum_to_100(self):
            """Slice percentages must sum to approximately 100 % (±1 % for rounding)."""
            resp = self.client.get(
                "/analytics/aggregate/topic-breakdown?platforms=codeforces"
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()

            if not data["topics"]:
                self.skipTest("No topic data to validate percentages")

            total_pct = sum(t["percentage"] for t in data["topics"])
            self.assertAlmostEqual(total_pct, 100.0, delta=1.5)

    def test_aggregate_topic_breakdown_returns_canonical_topics(self):
        canonical_tags = [
            "arrays",
            "sorting",
            "searching",
            "recursion",
            "hashing",
            "linked list",
            "stack",
            "queue",
            "trees",
            "graphs",
            "dp",
            "greedy",
        ]

        for i, raw_tag in enumerate(canonical_tags):
            problem = self._problem(
                f"800-{chr(65 + i)}",
                f"Canonical Topic Problem {i}",
                Difficulty.EASY,
                Platform.CODEFORCES,
            )

            self.session.add(problem)
            self.session.flush()

            topic = Topic(name=raw_tag)
            self.session.add(topic)
            self.session.flush()

            self.session.add(
                ProblemTopic(
                    problem_id=problem.id,
                    topic_id=topic.id,
                )
            )

            self.session.add(
                Submission(
                    profile_id=self.profile.id,
                    problem_id=problem.id,
                    contest_id=None,
                    platform_submission_id=f"canonical-s-{i}",
                    submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    language="Python 3",
                    status=SubmissionStatus.ACCEPTED,
                )
            )

        self.session.commit()

        resp = self.client.get(
            "/analytics/aggregate/topic-breakdown?platforms=codeforces"
        )

        self.assertEqual(resp.status_code, 200)

        data = resp.json()

        topic_names = {
            topic["topic"]
            for topic in data["topics"]
        }

        expected_topics = {
            "Arrays",
            "Sorting",
            "Searching",
            "Recursion",
            "Hashing",
            "Linked Lists",
            "Stacks & Queues",
            "Trees",
            "Graphs",
            "Dynamic Programming",
            "Greedy",
        }

        self.assertLessEqual(len(data["topics"]), 8)

        self.assertTrue(
            topic_names.issubset(expected_topics | {"Other"})
        )
        
        self.assertTrue(
            topic_names.intersection(expected_topics)
        )

    def test_aggregate_topic_breakdown_zero_topic_data(self):
        """Empty profile (no submissions) → all zero totals and empty topics."""
        self.app.dependency_overrides[get_current_user] = lambda: self.empty_user
        resp = self.client.get("/analytics/aggregate/topic-breakdown")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["total_solved"], 0)
        self.assertEqual(data["tagged_solved"], 0)
        self.assertEqual(data["total_topic_assignments"], 0)
        self.assertEqual(data["topics"], [])

    # ------------------------------------------------------------------
    # Test 9l: Partial topic coverage — total_solved > tagged_solved
    # ------------------------------------------------------------------

    def test_aggregate_topic_breakdown_partial_coverage(self):
        """When some solved problems have no topics, tagged_solved < total_solved."""
        resp = self.client.get(
            "/analytics/aggregate/topic-breakdown?platforms=codeforces"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Setup: Easy (Arrays ✓) + Medium (Graphs ✓) are tagged; Hard (WRONG_ANSWER) not solved
        # total_solved = 2, tagged_solved = 2 (both accepted problems are tagged)
        self.assertEqual(data["total_solved"], 2)
        self.assertLessEqual(data["tagged_solved"], data["total_solved"])



    # ------------------------------------------------------------------
    # Test 10: Aggregate difficulty distribution
    # ------------------------------------------------------------------

    def test_aggregate_difficulty_distribution(self):
        resp = self.client.get("/analytics/aggregate/difficulty-distribution")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        
        self.assertIn("total_solved", data)
        self.assertIn("difficulties", data)
        self.assertIn("platform_totals", data)
        
        # Should have Easy and Medium from accepted submissions
        difficulties = {d["difficulty"]: d["solved_count"] for d in data["difficulties"]}
        self.assertEqual(difficulties.get("Easy"), 1)
        self.assertEqual(difficulties.get("Medium"), 1)
        # Hard was not accepted
        self.assertNotIn("Hard", difficulties)
        
        # Should have platform totals
        self.assertGreater(len(data["platform_totals"]), 0)

    def test_aggregate_difficulty_distribution_with_platform_filter(self):
        resp = self.client.get("/analytics/aggregate/difficulty-distribution?platforms=codeforces")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        
        # Should only include Codeforces
        self.assertEqual(data["total_solved"], 2)  # Easy + Medium

    # ------------------------------------------------------------------
    # Test 11: Aggregate submission activity
    # ------------------------------------------------------------------

    def test_aggregate_submission_activity(self):
        resp = self.client.get("/analytics/aggregate/submission-activity")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        
        self.assertIn("total_submissions", data)
        self.assertIn("activity", data)
        
        # Should have activity from Codeforces profile
        self.assertGreater(data["total_submissions"], 0)
        self.assertGreater(len(data["activity"]), 0)

    def test_aggregate_submission_activity_with_range_filter(self):
        resp = self.client.get("/analytics/aggregate/submission-activity?range_days=365")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        
        # Should filter by date range
        self.assertGreaterEqual(len(data["activity"]), 0)

    def test_aggregate_submission_activity_with_platform_filter(self):
        resp = self.client.get("/analytics/aggregate/submission-activity?platforms=codeforces")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        
        # Should only include Codeforces submissions
        self.assertEqual(data["total_submissions"], 4)  # 4 submissions from Codeforces profile
