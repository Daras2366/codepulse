from sqlalchemy.orm import Session

from app.models.platform_profile import PlatformProfile
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.platform_profile_repository import PlatformProfileRepository
from app.schemas.dashboard import (
    DashboardContestItem,
    DashboardContestsResponse,
    DashboardDifficultyCount,
    DashboardOverviewResponse,
    DashboardProblemsResponse,
    DashboardRatingHistoryItem,
    DashboardRatingResponse,
    DashboardRecentSubmission,
    DashboardSubmissionActivity,
    DashboardSubmissionSummary,
    DashboardSubmissionsResponse,
)


class DashboardProfileNotFoundError(ValueError):
    """Raised when a dashboard profile cannot be found."""


class DashboardProfileAccessDeniedError(PermissionError):
    """Raised when a user requests another user's dashboard profile."""


class DashboardService:
    def __init__(self, db: Session):
        self.profiles = PlatformProfileRepository(db)
        self.dashboard = DashboardRepository(db)

    def get_overview(
        self,
        profile_id: int,
        user_id: int,
    ) -> DashboardOverviewResponse:
        profile = self._get_profile(profile_id, user_id)
        submission_summary = self.dashboard.get_submission_summary(profile.id)

        return DashboardOverviewResponse(
            profile_id=profile.id,
            platform=profile.platform,
            username=profile.username,
            total_problems_solved=int(submission_summary.solved_count),
            total_submissions=int(submission_summary.total_submissions),
            contests_attended=self.dashboard.get_contests_attended_count(profile.id),
            current_rating=profile.current_rating,
            max_rating=profile.max_rating,
            rank=profile.rank,
            last_synced_at=profile.last_synced_at,
        )

    def get_rating(
        self,
        profile_id: int,
        user_id: int,
    ) -> DashboardRatingResponse:
        profile = self._get_profile(profile_id, user_id)
        history = [
            DashboardRatingHistoryItem(
                contest_id=rating.contest_id,
                contest_name=contest.title if contest is not None else None,
                contest_start_time=(
                    contest.start_time if contest is not None else None
                ),
                rating=rating.rating,
                rating_change=rating.rating_change,
                recorded_at=rating.recorded_at,
            )
            for rating, contest in self.dashboard.get_rating_history(profile.id)
        ]

        return DashboardRatingResponse(
            profile_id=profile.id,
            current_rating=profile.current_rating,
            max_rating=profile.max_rating,
            rank=profile.rank,
            history=history,
        )

    def get_problems(
        self,
        profile_id: int,
        user_id: int,
    ) -> DashboardProblemsResponse:
        profile = self._get_profile(profile_id, user_id)
        summary = self.dashboard.get_submission_summary(profile.id)
        solved_by_difficulty = [
            DashboardDifficultyCount(
                difficulty=row.difficulty,
                solved_count=int(row.solved_count),
            )
            for row in self.dashboard.get_solved_by_difficulty(profile.id)
        ]

        return DashboardProblemsResponse(
            profile_id=profile.id,
            solved_count=int(summary.solved_count),
            solved_by_difficulty=solved_by_difficulty,
        )

    def get_submissions(
        self,
        profile_id: int,
        user_id: int,
        recent_limit: int = 20,
    ) -> DashboardSubmissionsResponse:
        profile = self._get_profile(profile_id, user_id)
        summary = self.dashboard.get_submission_summary(profile.id)
        recent_submissions = [
            DashboardRecentSubmission(
                id=submission.id,
                platform_submission_id=submission.platform_submission_id,
                submitted_at=submission.submitted_at,
                language=submission.language,
                status=submission.status,
                problem_id=problem.id,
                problem_title=problem.title,
                problem_url=problem.problem_url,
                difficulty=problem.difficulty,
                contest_id=submission.contest_id,
                contest_name=contest.title if contest is not None else None,
            )
            for submission, problem, contest in self.dashboard.get_recent_submissions(
                profile.id,
                recent_limit,
            )
        ]
        activity = [
            DashboardSubmissionActivity(
                activity_date=row.activity_date,
                total_submissions=int(row.total_submissions),
                accepted_submissions=int(row.accepted_submissions),
                rejected_submissions=(
                    int(row.total_submissions) - int(row.accepted_submissions)
                ),
            )
            for row in self.dashboard.get_submission_activity(profile.id)
        ]

        return DashboardSubmissionsResponse(
            profile_id=profile.id,
            summary=DashboardSubmissionSummary(
                total_submissions=int(summary.total_submissions),
                accepted_submissions=int(summary.accepted_submissions),
                rejected_submissions=(
                    int(summary.total_submissions)
                    - int(summary.accepted_submissions)
                ),
            ),
            recent_submissions=recent_submissions,
            activity=activity,
        )

    def get_contests(
        self,
        profile_id: int,
        user_id: int,
    ) -> DashboardContestsResponse:
        profile = self._get_profile(profile_id, user_id)
        contests = [
            DashboardContestItem(
                contest_id=contest.id,
                contest_name=contest.title,
                contest_url=contest.contest_url,
                start_time=contest.start_time,
                duration_minutes=contest.duration_minutes,
                rank=participation.rank,
                old_rating=participation.old_rating,
                new_rating=participation.new_rating,
                rating_change=participation.rating_change,
                solved=participation.solved,
                penalty=participation.penalty,
                platform=contest.platform.value,
            )
            for participation, contest in self.dashboard.get_contest_history(
                profile.id
            )
        ]

        return DashboardContestsResponse(
            profile_id=profile.id,
            contests_attended=len(contests),
            contests=contests,
        )

    def _get_profile(
        self,
        profile_id: int,
        user_id: int,
    ) -> PlatformProfile:
        profile = self.profiles.get_by_id(profile_id)
        if profile is None:
            raise DashboardProfileNotFoundError(
                f"Platform profile {profile_id} was not found."
            )

        if profile.user_id != user_id:
            raise DashboardProfileAccessDeniedError(
                f"You do not have permission to access platform profile {profile_id}."
            )

        return profile
