"""Recommendation Service.

Generates personalized, actionable recommendations based on deterministic
analysis of user performance data from PerformanceAnalyzer.

All recommendations are calculated from actual stored data without LLM involvement.
"""

from typing import Literal

from app.schemas.analytics import (
    PerformanceProfile,
    Recommendation,
)


class RecommendationService:
    """Generates personalized study recommendations from performance data."""

    def __init__(self) -> None:
        pass

    def generate_recommendations(
        self,
        profile: PerformanceProfile,
        active_goals: list[dict] | None = None,
    ) -> list[Recommendation]:
        """Generate prioritized recommendations from performance profile.

        Args:
            profile: Performance profile from PerformanceAnalyzer
            active_goals: Optional list of the user's active goals as plain
                dicts (``title``, ``goal_type``, ``target_value``,
                ``deadline``). Used to align recommendations with stated
                user intent. Never required — ``None`` keeps behaviour
                identical to before.

        Returns:
            List of prioritized recommendations
        """
        if not self._has_sufficient_data(profile):
            return []

        recommendations: list[Recommendation] = []

        # Goal-aligned recommendations (user-configured intent)
        if active_goals:
            recommendations.extend(self._generate_goal_recommendations(profile, active_goals))

        # Topic-based recommendations (highest priority)
        topic_recs = self._generate_topic_recommendations(profile)
        recommendations.extend(topic_recs)

        # Difficulty-based recommendations
        difficulty_recs = self._generate_difficulty_recommendations(profile)
        recommendations.extend(difficulty_recs)

        # Consistency recommendations
        consistency_recs = self._generate_consistency_recommendations(profile)
        recommendations.extend(consistency_recs)

        # Contest recommendations
        contest_recs = self._generate_contest_recommendations(profile)
        recommendations.extend(contest_recs)

        # De-duplicate by title (goal recs can overlap topic recs) and sort
        # by priority (high > medium > low).
        seen_titles: set[str] = set()
        unique: list[Recommendation] = []
        for rec in recommendations:
            key = rec.title.strip().lower()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            unique.append(rec)

        priority_order = {"high": 0, "medium": 1, "low": 2}
        unique.sort(key=lambda r: priority_order[r.priority])

        return unique[:10]  # Return top 10 recommendations

    def _has_sufficient_data(self, profile: PerformanceProfile) -> bool:
        """Check if there's enough data to generate meaningful recommendations."""
        # Need at least some solved problems or recent activity
        return (
            profile.overview.solved_problems > 0
            or profile.submission_behavior.total_submissions > 0
        )

    def _generate_goal_recommendations(
        self, profile: PerformanceProfile, active_goals: list[dict]
    ) -> list[Recommendation]:
        """Align recommendations with the user's active goals.

        Only emits a recommendation when the goal is genuinely actionable
        against the performance data — e.g. a topic goal pointing at a weak
        or neglected area, or a problem-count goal that benefits from the
        weakest identified topic.
        """
        recommendations: list[Recommendation] = []

        problem_goals = [
            g for g in active_goals
            if str(g.get("goal_type", "")).lower() in {"problems", "topic", "placement"}
        ]
        if not problem_goals:
            return recommendations

        # Find the weakest topic to anchor the recommendation.
        weak = [t for t in profile.topic_performance if t.strength_level == "weak"]
        anchor = min(weak, key=lambda t: t.solved_count) if weak else None

        for goal in problem_goals[:2]:
            title = str(goal.get("title", "your goal")).strip() or "your goal"
            target = goal.get("target_value")
            target_str = f"{target} problems" if isinstance(target, int) else "your target"

            if goal.get("goal_type") == "topic" and goal.get("topic_name"):
                topic_name = str(goal["topic_name"])
                topic_perf = next(
                    (t for t in profile.topic_performance if t.topic == topic_name), None
                )
                evidence = (
                    f" ({topic_perf.solved_count} solved so far)"
                    if topic_perf
                    else " (not yet started)"
                )
                reason = (
                    f"You set a goal to practice {topic_name}{evidence}. "
                    "Consistent, focused sessions on this topic will keep you on track."
                )
            elif anchor is not None:
                reason = (
                    f"To reach \"{title}\" ({target_str}), prioritise your weakest "
                    f"area — {anchor.topic} — where targeted practice has the highest impact."
                )
            else:
                reason = (
                    f"You have an active goal \"{title}\" ({target_str}). "
                    "Steady daily practice is the most reliable way to reach it."
                )

            recommendations.append(
                Recommendation(
                    category="topic" if anchor is not None else "consistency",
                    title=f"Work toward your goal: {title}",
                    reason=reason,
                    priority="medium",
                    suggested_activity=(
                        f"Solve problems toward \"{title}\""
                        + (f" — start with {anchor.topic}" if anchor is not None else "")
                    ),
                    target_metric=target_str,
                    difficulty_suggestion=self._suggest_difficulty(profile, anchor.topic)
                    if anchor is not None
                    else "mixed",
                )
            )

        return recommendations

    def _generate_topic_recommendations(self, profile: PerformanceProfile) -> list[Recommendation]:
        """Generate topic-focused recommendations.

        Distinguishes between:
        - Weak with recent activity: highest priority (performance issue)
        - Weak without recent activity: high priority (neglected weak area)
        - Moderate without recent activity: low priority (maintenance refresher)
        - Topics with insufficient data: note the coverage gap
        """
        recommendations: list[Recommendation] = []

        # Weak topics — include regardless of recent_activity.
        # Absence of recent practice is itself a signal to address.
        weak_topics = [
            t for t in profile.topic_performance
            if t.strength_level == "weak"
        ]

        for topic in weak_topics[:3]:
            if topic.recent_activity > 0:
                # Actively practicing but underperforming.
                priority: Literal["high", "medium", "low"] = "high"
                reason = (
                    f"Your {topic.topic} performance is weak ({topic.solved_count} solved, "
                    f"{topic.percentage:.1f}% of total). You have attempted it recently "
                    f"({topic.recent_activity} in last 30 days) but results show this is "
                    f"still a gap area. Focused, deliberate practice will help."
                )
            else:
                # Weak AND no recent practice — double risk.
                priority = "high"
                reason = (
                    f"Your {topic.topic} performance is weak ({topic.solved_count} solved, "
                    f"{topic.percentage:.1f}% of total) and you have had no activity on it "
                    f"in the last 30 days. Restarting practice here is important to close this gap."
                )

            target_problems = 10 if topic.solved_count < 5 else 5
            recommendations.append(
                Recommendation(
                    category="topic",
                    title=f"Practice {topic.topic} problems",
                    reason=reason,
                    priority=priority,
                    suggested_activity=f"Solve {target_problems} {topic.topic} problems",
                    target_metric=f"{target_problems} problems solved",
                    difficulty_suggestion=self._suggest_difficulty(profile, topic.topic),
                )
            )

        # Moderate topics with no recent activity — low-priority refreshers.
        moderate_topics = [
            t for t in profile.topic_performance
            if t.strength_level == "moderate" and t.recent_activity == 0
        ]

        for topic in moderate_topics[:2]:
            recommendations.append(
                Recommendation(
                    category="topic",
                    title=f"Revise {topic.topic}",
                    reason=(
                        f"You have moderate {topic.topic} knowledge ({topic.solved_count} solved) "
                        f"but haven't practiced recently. A quick refresher will help maintain proficiency."
                    ),
                    priority="low",
                    suggested_activity="Solve 3-5 review problems",
                    target_metric="3-5 problems solved",
                    difficulty_suggestion="mixed",
                )
            )

        return recommendations

    def _generate_difficulty_recommendations(self, profile: PerformanceProfile) -> list[Recommendation]:
        """Generate difficulty-focused recommendations."""
        recommendations: list[Recommendation] = []

        # Check for rarely attempted difficulties
        rarely_attempted = [
            d for d in profile.difficulty_performance
            if d.coverage_status == "rarely_attempted" and d.solved_count > 0
        ]

        for diff in rarely_attempted[:2]:
            recommendations.append(
                Recommendation(
                    category="difficulty",
                    title=f"Practice more {diff.difficulty} problems",
                    reason=(
                        f"You rarely attempt {diff.difficulty} problems ({diff.solved_count} solved). "
                        f"Expanding your comfort zone here will improve overall problem-solving ability."
                    ),
                    priority="medium",
                    suggested_activity=f"Solve 5 {diff.difficulty} problems",
                    target_metric="5 problems solved",
                    difficulty_suggestion=diff.difficulty.lower(),
                )
            )

        # Check for not attempted difficulties with some foundation
        not_attempted = [
            d for d in profile.difficulty_performance
            if d.coverage_status == "not_attempted" and profile.overview.solved_problems > 20
        ]

        for diff in not_attempted[:1]:
            recommendations.append(
                Recommendation(
                    category="difficulty",
                    title=f"Try your first {diff.difficulty} problems",
                    reason=(
                        f"You haven't attempted {diff.difficulty} problems yet. "
                        f"With {profile.overview.solved_problems} total problems solved, "
                        f"you're ready to start exploring this difficulty level."
                    ),
                    priority="low",
                    suggested_activity=f"Start with 2-3 {diff.difficulty} problems",
                    target_metric="2-3 problems attempted",
                    difficulty_suggestion=diff.difficulty.lower(),
                )
            )

        # Check for too many easy problems
        easy_coverage = [d for d in profile.difficulty_performance if d.difficulty == "Easy"]
        if easy_coverage and profile.overview.solved_problems > 30:
            easy = easy_coverage[0]
            if easy.solved_count > profile.overview.solved_problems * 0.6:
                recommendations.append(
                    Recommendation(
                        category="difficulty",
                        title="Challenge yourself with harder problems",
                        reason=(
                            f"{easy.solved_count} of your solved problems ({easy.solved_count / profile.overview.solved_problems * 100:.0f}%) "
                            f"are Easy. Moving to Medium/Hard will accelerate your growth."
                        ),
                        priority="medium",
                        suggested_activity="Solve 5 Medium problems",
                        target_metric="5 Medium problems solved",
                        difficulty_suggestion="medium",
                    )
                )

        return recommendations

    def _generate_consistency_recommendations(self, profile: PerformanceProfile) -> list[Recommendation]:
        """Generate consistency-focused recommendations."""
        recommendations: list[Recommendation] = []

        # Low streak
        if profile.submission_behavior.current_streak_days == 0 and profile.overview.active_days > 0:
            recommendations.append(
                Recommendation(
                    category="consistency",
                    title="Build a practice streak",
                    reason=(
                        f"You're not currently on an active streak. "
                        f"Consistent daily practice is one of the most effective ways to improve."
                    ),
                    priority="high",
                    suggested_activity="Solve at least 1 problem daily for 7 days",
                    target_metric="7-day streak",
                    difficulty_suggestion="easy",
                )
            )

        # Low active days relative to solved count
        if profile.overview.active_days > 0:
            problems_per_day = profile.overview.solved_problems / profile.overview.active_days
            if problems_per_day > 10 and profile.submission_behavior.current_streak_days < 5:
                recommendations.append(
                    Recommendation(
                        category="consistency",
                        title="Spread practice across more days",
                        reason=(
                            f"You solve {problems_per_day:.1f} problems per active day on average. "
                            f"Spreading practice across more days improves retention and reduces burnout."
                        ),
                        priority="medium",
                        suggested_activity="Aim for 3-5 problems across 5-7 days per week",
                        target_metric="5-7 active days per week",
                        difficulty_suggestion="mixed",
                    )
                )

        # Low acceptance rate
        if (
            profile.submission_behavior.acceptance_rate is not None
            and profile.submission_behavior.acceptance_rate < 0.4
            and profile.submission_behavior.total_submissions > 20
        ):
            recommendations.append(
                Recommendation(
                    category="consistency",
                    title="Focus on understanding before solving",
                    reason=(
                        f"Your acceptance rate is {profile.submission_behavior.acceptance_rate * 100:.0f}%. "
                        f"Take time to understand the problem thoroughly before coding. "
                        f"Review editorial solutions after solving."
                    ),
                    priority="high",
                    suggested_activity="Practice 1-2 problems with thorough analysis",
                    target_metric="Improve acceptance rate to 50%+",
                    difficulty_suggestion="easy",
                )
            )

        return recommendations

    def _generate_contest_recommendations(self, profile: PerformanceProfile) -> list[Recommendation]:
        """Generate contest-focused recommendations."""
        recommendations: list[Recommendation] = []

        # No contest participation
        if profile.contest_performance.contests_participated == 0 and profile.overview.solved_problems > 20:
            recommendations.append(
                Recommendation(
                    category="contest",
                    title="Try your first contest",
                    reason=(
                        f"You've solved {profile.overview.solved_problems} problems but haven't participated in contests. "
                        f"Contests help you practice under time pressure and identify gaps."
                    ),
                    priority="medium",
                    suggested_activity="Register for the next available contest on your platform",
                    target_metric="1 contest participation",
                    difficulty_suggestion="mixed",
                )
            )

        # Declining participation
        if profile.contest_performance.participation_trend == "decreasing":
            recommendations.append(
                Recommendation(
                    category="contest",
                    title="Re-engage with contests",
                    reason=(
                        f"Your contest participation has been declining recently. "
                        f"Regular contest participation maintains competitive edge and motivation."
                    ),
                    priority="medium",
                    suggested_activity="Participate in 2 contests in the next month",
                    target_metric="2 contest participations",
                    difficulty_suggestion="mixed",
                )
            )

        # Rating declining
        if profile.rating_trend.trend_direction == "declining":
            recommendations.append(
                Recommendation(
                    category="contest",
                    title="Focus on fundamentals before next contest",
                    reason=(
                        f"Your rating has been declining recently. "
                        f"Focus on strengthening weak topics and practice targeted problems before the next contest."
                    ),
                    priority="high",
                    suggested_activity="Practice 10 problems in your weakest topics",
                    target_metric="Rating stabilization",
                    difficulty_suggestion="mixed",
                )
            )

        return recommendations

    def _suggest_difficulty(
        self, profile: PerformanceProfile, topic: str
    ) -> Literal["easy", "medium", "hard", "mixed"]:
        """Suggest an appropriate difficulty based on overall performance.

        Uses the stored acceptance_rate from submission_behavior to avoid
        recalculating a potentially inconsistent substitute.
        """
        # Not enough foundation yet — stay easy.
        if profile.overview.solved_problems < 20:
            return "easy"

        # Good overall acceptance rate — ready for medium.
        ar = profile.submission_behavior.acceptance_rate
        if ar is not None and ar > 0.7:
            return "medium"

        return "mixed"
