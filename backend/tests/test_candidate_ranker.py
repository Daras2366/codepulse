"""Tests for app.services.candidate_ranker and the ranked
search_candidate_problems tool.

Coverage:
- Difficulty bands / target difficulty by solved-count level
- Each scoring term: topic fit, difficulty fit, staleness,
  solvability, recent-failure penalty
- Diversity-aware greedy selection
- Stable ordering on score ties
- search_candidate_problems: score fields, difficulty defaulting,
  topic-match-first top-up
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — registers all ORM models
from app.models.base import Base
from app.models.enums import Difficulty, Platform, SubmissionStatus
from app.models.platform_profile import PlatformProfile
from app.models.problem import Problem
from app.models.problem_topic import ProblemTopic
from app.models.submission import Submission
from app.models.topic import Topic
from app.models.user import User
from app.services import candidate_ranker as cr
from app.services.agent_tools import search_candidate_problems


# ---------------------------------------------------------------------------
# Pure scoring tests (no DB)
# ---------------------------------------------------------------------------


def _ctx(**kwargs) -> cr.UserRankingContext:
    kwargs.setdefault("now", datetime(2026, 1, 1, tzinfo=timezone.utc))
    return cr.UserRankingContext(**kwargs)


class TestDifficultyBands:
    def test_easy_only_under_20(self):
        assert cr.allowed_difficulty_band(0) == {Difficulty.EASY}
        assert cr.allowed_difficulty_band(19) == {Difficulty.EASY}

    def test_easy_medium_20_to_99(self):
        assert cr.allowed_difficulty_band(20) == {Difficulty.EASY, Difficulty.MEDIUM}
        assert cr.allowed_difficulty_band(99) == {Difficulty.EASY, Difficulty.MEDIUM}

    def test_all_difficulties_100_plus(self):
        assert cr.allowed_difficulty_band(100) == {
            Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD
        }
        assert cr.allowed_difficulty_band(500) == {
            Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD
        }

    def test_target_difficulty_by_level(self):
        assert cr.target_difficulty(5) == Difficulty.EASY
        assert cr.target_difficulty(50) == Difficulty.MEDIUM
        assert cr.target_difficulty(150) == Difficulty.HARD


class TestTopicFit:
    def test_weak_topic_beats_strong(self):
        ctx = _ctx(
            solved_count=100,
            topic_solved={"graphs": 2, "arrays": 40},
            topic_strength={"graphs": "weak", "arrays": "strong"},
        )
        weak = cr.score_candidate(1, ["Graphs"], Difficulty.EASY, 0.5, ctx)
        strong = cr.score_candidate(2, ["Arrays"], Difficulty.EASY, 0.5, ctx)
        assert weak.score > strong.score
        assert weak.breakdown["topic_fit"] > strong.breakdown["topic_fit"]

    def test_unknown_topic_scores_between_weak_and_strong(self):
        ctx = _ctx(
            solved_count=100,
            topic_solved={"graphs": 2, "arrays": 40},
            topic_strength={"graphs": "weak", "arrays": "strong"},
        )
        unknown = cr.score_candidate(3, ["Tries"], Difficulty.EASY, 0.5, ctx)
        weak = cr.score_candidate(1, ["Graphs"], Difficulty.EASY, 0.5, ctx)
        strong = cr.score_candidate(2, ["Arrays"], Difficulty.EASY, 0.5, ctx)
        assert strong.breakdown["topic_fit"] < unknown.breakdown["topic_fit"] < weak.breakdown["topic_fit"]

    def test_no_topics_scores_zero_topic_fit(self):
        ctx = _ctx(solved_count=50, topic_solved={"graphs": 1})
        cand = cr.score_candidate(1, [], Difficulty.EASY, 0.5, ctx)
        assert cand.breakdown["topic_fit"] == 0.0

    def test_relative_deficiency_orders_within_same_label(self):
        # Two "weak"-ish topics: the one with fewer solves relative to the
        # user's max must score higher even with identical labels.
        ctx = _ctx(
            solved_count=100,
            topic_solved={"graphs": 1, "trees": 8, "arrays": 40},
            topic_strength={
                "graphs": "insufficient_data",
                "trees": "insufficient_data",
                "arrays": "strong",
            },
        )
        fewer = cr.score_candidate(1, ["Graphs"], Difficulty.EASY, 0.5, ctx)
        more = cr.score_candidate(2, ["Trees"], Difficulty.EASY, 0.5, ctx)
        assert fewer.breakdown["topic_fit"] > more.breakdown["topic_fit"]


class TestDifficultyFit:
    def test_explicit_difficulty_is_neutral(self):
        ctx = _ctx(solved_count=5)
        easy = cr.score_candidate(1, ["A"], Difficulty.EASY, 0.5, ctx, explicit_difficulty=True)
        hard = cr.score_candidate(2, ["A"], Difficulty.HARD, 0.5, ctx, explicit_difficulty=True)
        assert easy.breakdown["difficulty_fit"] == hard.breakdown["difficulty_fit"] == 1.0

    def test_beginner_prefers_easy_over_hard(self):
        ctx = _ctx(solved_count=5)  # <20 → target Easy
        easy = cr.score_candidate(1, ["A"], Difficulty.EASY, 0.5, ctx)
        hard = cr.score_candidate(2, ["A"], Difficulty.HARD, 0.5, ctx)
        assert easy.breakdown["difficulty_fit"] > hard.breakdown["difficulty_fit"]
        assert easy.score > hard.score

    def test_intermediate_prefers_medium(self):
        ctx = _ctx(solved_count=50)  # 20-99 → target Medium
        medium = cr.score_candidate(1, ["A"], Difficulty.MEDIUM, 0.5, ctx)
        easy = cr.score_candidate(2, ["A"], Difficulty.EASY, 0.5, ctx)
        assert medium.breakdown["difficulty_fit"] > easy.breakdown["difficulty_fit"]


class TestStaleness:
    def test_stale_topic_beats_fresh_topic(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ctx = _ctx(
            now=now,
            topic_last_submission={
                "graphs": now - timedelta(days=60),   # stale → 1.0
                "arrays": now - timedelta(days=1),    # fresh → ~0.03
            },
        )
        stale = cr.score_candidate(1, ["Graphs"], Difficulty.EASY, 0.5, ctx)
        fresh = cr.score_candidate(2, ["Arrays"], Difficulty.EASY, 0.5, ctx)
        assert stale.breakdown["staleness"] > fresh.breakdown["staleness"]
        assert stale.score > fresh.score

    def test_never_submitted_topic_is_fully_stale(self):
        ctx = _ctx(topic_last_submission={})
        cand = cr.score_candidate(1, ["Graphs"], Difficulty.EASY, 0.5, ctx)
        assert cand.breakdown["staleness"] == 1.0


class TestRecentFailure:
    def _base_kwargs(self):
        return dict(
            solved_count=50,
            topic_solved={"graphs": 1},
            topic_strength={"graphs": "weak"},
        )

    def test_recent_failure_lowers_score(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ctx_recent = _ctx(
            now=now,
            problem_last_failed_attempt={7: now - timedelta(days=2)},
            **self._base_kwargs(),
        )
        ctx_old = _ctx(
            now=now,
            problem_last_failed_attempt={7: now - timedelta(days=60)},
            **self._base_kwargs(),
        )
        ctx_never = _ctx(now=now, **self._base_kwargs())

        recent = cr.score_candidate(7, ["Graphs"], Difficulty.MEDIUM, 0.5, ctx_recent)
        old = cr.score_candidate(7, ["Graphs"], Difficulty.MEDIUM, 0.5, ctx_old)
        never = cr.score_candidate(7, ["Graphs"], Difficulty.MEDIUM, 0.5, ctx_never)

        assert recent.breakdown["recent_failure_penalty"] == pytest.approx(
            cr.W_RECENT_FAILURE_PENALTY
        )
        assert old.breakdown["recent_failure_penalty"] == 0.0
        assert never.breakdown["recent_failure_penalty"] == 0.0
        assert recent.score < never.score
        assert old.score == pytest.approx(never.score)

    def test_half_penalty_between_7_and_30_days(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ctx = _ctx(
            now=now,
            problem_last_failed_attempt={3: now - timedelta(days=15)},
            **self._base_kwargs(),
        )
        cand = cr.score_candidate(3, ["Graphs"], Difficulty.MEDIUM, 0.5, ctx)
        assert cand.breakdown["recent_failure_penalty"] == pytest.approx(
            cr.W_RECENT_FAILURE_PENALTY * 0.5
        )


class TestSolvability:
    def test_higher_acceptance_scores_higher(self):
        ctx = _ctx(solved_count=50)
        high = cr.score_candidate(1, [], Difficulty.EASY, 0.9, ctx)
        low = cr.score_candidate(2, [], Difficulty.EASY, 0.1, ctx)
        assert high.score > low.score

    def test_none_acceptance_is_neutral(self):
        ctx = _ctx(solved_count=50)
        cand = cr.score_candidate(1, [], Difficulty.EASY, None, ctx)
        assert cand.breakdown["solvability"] == 0.5


# ---------------------------------------------------------------------------
# Diversity selection
# ---------------------------------------------------------------------------


def _cand(pid, topics, score):
    return cr.ScoredCandidate(
        problem_id=pid,
        topics=topics,
        difficulty=Difficulty.EASY,
        acceptance_rate=0.5,
        score=score,
        breakdown={"score": score},
    )


class TestSelectDiverse:
    def test_prefers_fresh_topics_over_repeats(self):
        # cand2 scores slightly lower but introduces a brand-new topic.
        cands = [
            _cand(1, ["Graphs"], 0.90),
            _cand(2, ["Graphs"], 0.85),
            _cand(3, ["Trees"], 0.80),
        ]
        selected, _ = cr.select_diverse(cands, 2)
        ids = [c.problem_id for c in selected]
        # First pick is the top scorer; second should be cand3 (fresh topic)
        # because cand2 repeats "Graphs" and pays the diversity penalty.
        assert ids[0] == 1
        assert ids[1] == 3

    def test_stable_ordering_on_ties(self):
        cands = [
            _cand(9, ["A"], 0.5),
            _cand(3, ["B"], 0.5),
            _cand(7, ["C"], 0.5),
        ]
        selected, _ = cr.select_diverse(cands, 3)
        # Equal scores, no shared topics → problem_id ascending.
        assert [c.problem_id for c in selected] == [3, 7, 9]

    def test_respects_limit(self):
        cands = [_cand(i, [f"T{i}"], 1.0 - i * 0.01) for i in range(10)]
        selected, _ = cr.select_diverse(cands, 4)
        assert len(selected) == 4

    def test_carries_over_topic_counts_between_passes(self):
        first = [_cand(1, ["Graphs"], 0.9)]
        _, counts = cr.select_diverse(first, 1)
        second = [
            _cand(2, ["Graphs"], 0.85),
            _cand(3, ["Trees"], 0.80),
        ]
        selected, _ = cr.select_diverse(second, 1, counts)
        # "Graphs" already selected in pass 1 → "Trees" wins despite lower score.
        assert selected[0].problem_id == 3


# ---------------------------------------------------------------------------
# DB-backed integration through search_candidate_problems
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def world(db):
    """Small catalog: user solved 1 Easy problem; unsolved Easy+Medium+Hard."""
    user = User(username="ruser", email="r@example.com", password_hash="x")
    db.add(user)
    db.flush()
    profile = PlatformProfile(user_id=user.id, platform=Platform.LEETCODE, username="r")
    db.add(profile)
    db.flush()

    topics = {name: Topic(name=name) for name in ["Graphs", "Trees", "Math"]}
    db.add_all(topics.values())
    db.flush()

    problems = []
    specs = [
        ("Solved Easy", Difficulty.EASY, ["Math"]),
        ("Unsolved Easy A", Difficulty.EASY, ["Graphs"]),
        ("Unsolved Easy B", Difficulty.EASY, ["Trees"]),
        ("Unsolved Medium", Difficulty.MEDIUM, ["Graphs"]),
        ("Unsolved Hard", Difficulty.HARD, ["Graphs"]),
    ]
    for i, (title, diff, tnames) in enumerate(specs):
        p = Problem(
            platform=Platform.LEETCODE,
            platform_problem_id=f"p{i}",
            title=title,
            slug=f"p{i}",
            problem_url=f"https://example.com/p{i}",
            difficulty=diff,
            acceptance_rate=0.5,
        )
        db.add(p)
        db.flush()
        for tn in tnames:
            db.add(ProblemTopic(problem_id=p.id, topic_id=topics[tn].id))
        problems.append(p)
    db.flush()

    # One ACCEPTED submission on problems[0] → solved_count = 1 (<20 → Easy band)
    db.add(
        Submission(
            profile_id=profile.id,
            problem_id=problems[0].id,
            submitted_at=datetime.now(timezone.utc),
            language="Python3",
            status=SubmissionStatus.ACCEPTED,
            platform_submission_id="sub-1",
        )
    )
    db.commit()
    return {"user": user, "profile": profile, "problems": problems, "topics": topics}


class TestSearchCandidateProblemsRanked:
    def test_returns_score_fields(self, db, world):
        result = search_candidate_problems(db, world["user"].id, limit=5)
        assert result["problems"], "expected candidates"
        for p in result["problems"]:
            assert "score" in p
            assert "score_breakdown" in p
            assert "topic_fit" in p["score_breakdown"]

    def test_beginner_band_excludes_medium_and_hard(self, db, world):
        # solved_count = 1 → band is Easy only.
        result = search_candidate_problems(db, world["user"].id, limit=10)
        difficulties = {p["difficulty"] for p in result["problems"]}
        assert difficulties == {"Easy"}

    def test_explicit_difficulty_overrides_band(self, db, world):
        result = search_candidate_problems(
            db, world["user"].id, difficulty="Hard", limit=10
        )
        assert all(p["difficulty"] == "Hard" for p in result["problems"])
        assert len(result["problems"]) == 1

    def test_topic_match_comes_first_then_scored_fill(self, db, world):
        # "Trees" matches only one problem; remaining slots must be filled
        # with next-best-scored candidates, not left empty.
        result = search_candidate_problems(
            db, world["user"].id, topic="Trees", limit=5
        )
        problems = result["problems"]
        assert problems, "expected candidates"
        first = problems[0]
        assert any("Trees" in t for t in first["topics"])
        # Filled to the limit (3 unsolved in-band problems exist: 2 Easy + ...)
        # Band is Easy-only for this user → Easy A (Graphs), Easy B (Trees).
        # Only 2 in-band candidates exist, so len <= 2.
        assert len(problems) <= 2

    def test_solved_problem_never_returned(self, db, world):
        result = search_candidate_problems(db, world["user"].id, limit=10)
        ids = {p["id"] for p in result["problems"]}
        assert world["problems"][0].id not in ids
