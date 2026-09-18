from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import Difficulty, Platform, SubmissionStatus


class DashboardOverviewResponse(BaseModel):
    profile_id: int
    platform: Platform
    username: str
    total_problems_solved: int
    total_submissions: int
    contests_attended: int
    current_rating: int | None
    max_rating: int | None
    rank: str | None
    last_synced_at: datetime | None


class DashboardRatingHistoryItem(BaseModel):
    contest_id: int | None
    contest_name: str | None
    contest_start_time: datetime | None
    rating: int
    rating_change: int
    recorded_at: datetime


class DashboardRatingResponse(BaseModel):
    profile_id: int
    current_rating: int | None
    max_rating: int | None
    rank: str | None
    history: list[DashboardRatingHistoryItem]


class DashboardDifficultyCount(BaseModel):
    difficulty: Difficulty
    solved_count: int


class DashboardProblemsResponse(BaseModel):
    profile_id: int
    solved_count: int
    solved_by_difficulty: list[DashboardDifficultyCount]


class DashboardSubmissionSummary(BaseModel):
    total_submissions: int
    accepted_submissions: int
    rejected_submissions: int


class DashboardRecentSubmission(BaseModel):
    id: int
    platform_submission_id: str
    submitted_at: datetime
    language: str
    status: SubmissionStatus
    problem_id: int
    problem_title: str
    problem_url: str
    difficulty: Difficulty
    contest_id: int | None
    contest_name: str | None
    platform: Platform


class DashboardSubmissionActivity(BaseModel):
    activity_date: date
    total_submissions: int
    accepted_submissions: int
    rejected_submissions: int


class DashboardSubmissionsResponse(BaseModel):
    profile_id: int
    summary: DashboardSubmissionSummary
    recent_submissions: list[DashboardRecentSubmission]
    activity: list[DashboardSubmissionActivity]


class DashboardContestItem(BaseModel):
    contest_id: int
    contest_name: str
    contest_url: str
    start_time: datetime
    duration_minutes: int
    rank: int | None
    old_rating: int | None
    new_rating: int | None
    rating_change: int | None
    solved: int
    penalty: int | None
    platform: str


class DashboardContestsResponse(BaseModel):
    profile_id: int
    contests_attended: int
    contests: list[DashboardContestItem]


class DashboardPlatformSummary(BaseModel):
    profile_id: int
    platform: Platform
    username: str
    total_problems_solved: int
    total_submissions: int
    contests_attended: int
    current_rating: int | None
    max_rating: int | None
    rank: str | None
    last_synced_at: datetime | None


class DashboardAggregateOverview(BaseModel):
    total_problems_solved: int
    total_submissions: int
    contests_attended: int
    connected_platforms: int
    platforms: list[DashboardPlatformSummary]


class DashboardAggregateSubmissionsResponse(BaseModel):
    summary: DashboardSubmissionSummary
    recent_submissions: list[DashboardRecentSubmission]
    activity: list[DashboardSubmissionActivity]


class DashboardAggregateContestsResponse(BaseModel):
    contests_attended: int
    contests: list[DashboardContestItem]


class DashboardAggregateResponse(BaseModel):
    overview: DashboardAggregateOverview
    submissions: DashboardAggregateSubmissionsResponse
    contests: DashboardAggregateContestsResponse
