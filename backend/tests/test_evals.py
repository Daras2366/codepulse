"""Tests for the AI Coach offline evaluation harness.

Coverage:
- evals.metrics: known inputs -> known outputs for every metric
- evals.profiles: seeded catalog/profile counts and determinism
- evals.run_eval: --mode candidates smoke test on seeded profiles
"""

import pytest
from sqlalchemy.orm import Session

from evals import metrics
from evals.profiles import (
    CATALOG_SIZE,
    PROFILE_SPECS,
    seed_eval_db,
)
from evals.run_eval import (
    build_catalog_index,
    eval_candidates_for_profile,
    profile_context,
    run,
)


# ---------------------------------------------------------------------------
# Fixtures — one seeded eval world shared across the module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def eval_world():
    db, profiles, problems, problem_topics = seed_eval_db()
    try:
        yield db, profiles, problems, problem_topics
    finally:
        db.close()


# ---------------------------------------------------------------------------
# metrics.py unit tests — known inputs -> known outputs
# ---------------------------------------------------------------------------


def _catalog():
    return {
        1: {"title": "Alpha", "url": "https://x/1", "topics": ["Graphs"], "difficulty": "Easy"},
        2: {"title": "Beta", "url": "https://x/2", "topics": ["Dynamic Programming"], "difficulty": "Medium"},
        3: {"title": "Gamma", "url": "https://x/3", "topics": ["Math"], "difficulty": "Hard"},
    }


class TestAllowedDifficulties:
    def test_beginner_band(self):
        assert metrics.allowed_difficulties(0) == {"Easy"}
        assert metrics.allowed_difficulties(19) == {"Easy"}

    def test_intermediate_band(self):
        assert metrics.allowed_difficulties(20) == {"Easy", "Medium"}
        assert metrics.allowed_difficulties(99) == {"Easy", "Medium"}

    def test_advanced_band(self):
        assert metrics.allowed_difficulties(100) == {"Easy", "Medium", "Hard"}
        assert metrics.allowed_difficulties(500) == {"Easy", "Medium", "Hard"}


class TestGroundingRate:
    def test_all_grounded(self):
        recs = [
            {"problem_id": 1, "title": "Alpha", "url": "https://x/1"},
            {"problem_id": 2, "title": "Beta", "url": "https://x/2"},
        ]
        assert metrics.grounding_rate(recs, _catalog()) == 1.0

    def test_unknown_id_and_url_ungrounded(self):
        recs = [
            {"problem_id": 999, "title": "Ghost", "url": "https://x/ghost"},
            {"problem_id": 1, "title": "Alpha", "url": "https://x/1"},
        ]
        assert metrics.grounding_rate(recs, _catalog()) == 0.5

    def test_url_fallback_match(self):
        recs = [{"problem_id": None, "title": "Beta", "url": "https://x/2"}]
        assert metrics.grounding_rate(recs, _catalog()) == 1.0

    def test_invented_title_with_real_id_not_grounded(self):
        recs = [{"problem_id": 1, "title": "Made Up Title", "url": "https://x/1"}]
        assert metrics.grounding_rate(recs, _catalog()) == 0.0

    def test_empty(self):
        assert metrics.grounding_rate([], _catalog()) == 0.0


class TestUnsolvedRate:
    def test_excludes_solved(self):
        recs = [
            {"problem_id": 1, "title": "Alpha", "url": "https://x/1"},
            {"problem_id": 2, "title": "Beta", "url": "https://x/2"},
        ]
        # User solved problem 1.
        assert metrics.unsolved_rate(recs, _catalog(), {1}) == 0.5

    def test_unverifiable_not_counted(self):
        recs = [{"problem_id": 999, "title": "Ghost", "url": "https://x/ghost"}]
        assert metrics.unsolved_rate(recs, _catalog(), set()) == 0.0

    def test_empty(self):
        assert metrics.unsolved_rate([], _catalog(), set()) == 0.0


class TestWeakTopicCoverage:
    def test_partial_coverage(self):
        recs = [
            {"problem_id": 1, "title": "Alpha", "url": "u", "topics": ["Graphs"]},
            {"problem_id": 2, "title": "Beta", "url": "u", "topics": ["Math"]},
        ]
        # Only "Graphs" is a focus topic.
        assert metrics.weak_topic_coverage(recs, {"graphs"}) == 0.5

    def test_case_insensitive(self):
        recs = [{"problem_id": 1, "title": "A", "url": "u", "topics": ["Dynamic Programming"]}]
        assert metrics.weak_topic_coverage(recs, {"dynamic programming"}) == 1.0

    def test_empty_focus_set(self):
        recs = [{"problem_id": 1, "title": "A", "url": "u", "topics": ["Graphs"]}]
        assert metrics.weak_topic_coverage(recs, set()) == 0.0

    def test_empty_recs(self):
        assert metrics.weak_topic_coverage([], {"graphs"}) == 0.0


class TestDifficultyFit:
    def test_fit_within_band(self):
        recs = [
            {"problem_id": 1, "title": "A", "url": "u", "difficulty": "Easy"},
            {"problem_id": 2, "title": "B", "url": "u", "difficulty": "Medium"},
        ]
        assert metrics.difficulty_fit(recs, {"Easy", "Medium"}) == 1.0
        assert metrics.difficulty_fit(recs, {"Easy"}) == 0.5

    def test_missing_difficulty_fails(self):
        recs = [{"problem_id": 1, "title": "A", "url": "u", "difficulty": None}]
        assert metrics.difficulty_fit(recs, {"Easy"}) == 0.0

    def test_case_normalisation(self):
        recs = [{"problem_id": 1, "title": "A", "url": "u", "difficulty": "easy"}]
        assert metrics.difficulty_fit(recs, {"Easy"}) == 1.0

    def test_empty(self):
        assert metrics.difficulty_fit([], {"Easy"}) == 0.0


class TestTopicDiversity:
    def test_all_unique(self):
        recs = [
            {"problem_id": 1, "title": "A", "url": "u", "topics": ["Graphs"]},
            {"problem_id": 2, "title": "B", "url": "u", "topics": ["Math"]},
        ]
        assert metrics.topic_diversity(recs) == 1.0

    def test_repeated_topics(self):
        recs = [
            {"problem_id": 1, "title": "A", "url": "u", "topics": ["Graphs", "Math"]},
            {"problem_id": 2, "title": "B", "url": "u", "topics": ["Graphs"]},
        ]
        # 3 slots, 2 distinct → 2/3
        assert metrics.topic_diversity(recs) == pytest.approx(2 / 3)

    def test_no_topics(self):
        recs = [{"problem_id": 1, "title": "A", "url": "u", "topics": []}]
        assert metrics.topic_diversity(recs) == 0.0


class TestComputeMetricsAndMean:
    def test_compute_metrics_keys(self):
        recs = [{"problem_id": 1, "title": "Alpha", "url": "https://x/1",
                 "topics": ["Graphs"], "difficulty": "Easy"}]
        out = metrics.compute_metrics(
            recs,
            catalog=_catalog(),
            solved_ids=set(),
            focus_topics={"graphs"},
            allowed={"Easy"},
        )
        for name in metrics.METRIC_NAMES:
            assert name in out
        assert out["n_recommendations"] == 1.0
        assert out["grounding_rate"] == 1.0

    def test_mean_metrics(self):
        rows = [
            {"grounding_rate": 1.0, "unsolved_rate": 1.0,
             "weak_topic_coverage": 0.0, "difficulty_fit": 1.0,
             "topic_diversity": 1.0},
            {"grounding_rate": 0.0, "unsolved_rate": 0.0,
             "weak_topic_coverage": 1.0, "difficulty_fit": 0.0,
             "topic_diversity": 0.0},
        ]
        mean = metrics.mean_metrics(rows)
        assert mean["grounding_rate"] == 0.5
        assert mean["weak_topic_coverage"] == 0.5
        assert mean["topic_diversity"] == 0.5


# ---------------------------------------------------------------------------
# profiles.py — seeded world sanity
# ---------------------------------------------------------------------------


class TestSeededWorld:
    def test_catalog_size_and_topics(self, eval_world):
        db, profiles, problems, problem_topics = eval_world
        assert len(problems) >= CATALOG_SIZE
        assert len(problem_topics) == len(problems)
        # Every problem has at least one topic.
        assert all(len(t) >= 1 for t in problem_topics.values())

    def test_profile_count_and_archetypes(self, eval_world):
        db, profiles, problems, problem_topics = eval_world
        assert len(profiles) == len(PROFILE_SPECS)
        assert len(profiles) >= 20
        names = {p.name for p in profiles}
        for required in (
            "beginner_cf", "strong_dp_weak_graphs", "inactive_60d",
            "cf_only_intermediate", "lc_only_intermediate",
            "both_platforms_balanced", "goal_topic_user",
            "many_attempts_unsolved",
        ):
            assert required in names

    def test_profiles_have_real_solved_ids(self, eval_world):
        db, profiles, problems, problem_topics = eval_world
        all_ids = {p.id for p in problems}
        for prof in profiles:
            assert prof.solved_ids <= all_ids
            assert len(prof.solved_ids) > 0

    def test_seeding_is_deterministic(self):
        db1, p1, prob1, _ = seed_eval_db()
        db2, p2, prob2, _ = seed_eval_db()
        try:
            assert [p.name for p in p1] == [p.name for p in p2]
            assert [pr.title for pr in prob1] == [pr.title for pr in prob2]
            assert p1[0].solved_ids == p2[0].solved_ids
        finally:
            db1.close()
            db2.close()


# ---------------------------------------------------------------------------
# run_eval.py — candidates-mode smoke test
# ---------------------------------------------------------------------------


class TestCandidatesMode:
    def test_eval_candidates_produces_scored_rows(self, eval_world):
        db, profiles, problems, problem_topics = eval_world
        catalog = build_catalog_index(problems, problem_topics)

        rows = []
        for ep in profiles[:5]:
            ctx = profile_context(db, ep, catalog)
            rows.append(eval_candidates_for_profile(db, ctx))

        assert len(rows) == 5
        for row in rows:
            for name in metrics.METRIC_NAMES:
                assert name in row
                assert 0.0 <= row[name] <= 1.0
            assert row["n_recommendations"] > 0
            # Candidates come straight from the DB → always grounded.
            assert row["grounding_rate"] == 1.0

    def test_full_candidates_run(self, eval_world):
        """Smoke: run(mode='candidates') completes over all seeded profiles."""
        result = run("candidates")
        assert result["mode"] == "candidates"
        assert result["catalog_size"] >= CATALOG_SIZE
        assert result["n_profiles"] == len(PROFILE_SPECS)
        for name in metrics.METRIC_NAMES:
            assert name in result["means"]
            assert 0.0 <= result["means"][name] <= 1.0
        # Mean grounding must be perfect — candidates are DB rows.
        assert result["means"]["grounding_rate"] == 1.0
