"""Pydantic schemas for the personalized study plan endpoint."""

from datetime import datetime

from pydantic import BaseModel


class StudyPlanProblem(BaseModel):
    """A real, unsolved problem selected for today's study plan."""

    id: int
    title: str
    platform: str
    difficulty: str | None
    url: str
    topics: list[str]
    estimated_minutes: int
    acceptance_rate: float | None = None


class StudyPlanDailyTarget(BaseModel):
    """Daily goal derived from a real user-configured goal.

    ``daily_target`` is ``None`` when the user has no active goal with a
    deadline — the UI must prompt the user to create a goal rather than
    inventing a number.
    """

    solved_today: int
    daily_target: int | None
    target_label: str | None = None
    target_source: str | None = None  # e.g. "goal" — never fabricated
    timezone: str


class StudyPlanContest(BaseModel):
    """The next upcoming contest (start_time strictly in the future)."""

    id: int
    title: str
    platform: str
    contest_url: str
    start_time: datetime
    duration_minutes: int


class StudyPlanResponse(BaseModel):
    """Personalized daily study plan built entirely from real user data."""

    has_sufficient_data: bool
    focus_topic: str | None
    focus_reason: str | None
    problems: list[StudyPlanProblem]
    problems_planned: int
    total_estimated_minutes: int
    estimate_note: str
    daily: StudyPlanDailyTarget
    upcoming_contest: StudyPlanContest | None
    catalog_size: int
    limitations: list[str]
