from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import SubmissionStatus


class SubmissionBase(BaseModel):
    profile_id: int
    problem_id: int
    submitted_at: datetime
    language: str
    status: SubmissionStatus
    platform_submission_id: str
    contest_id: int | None = None


class SubmissionCreate(SubmissionBase):
    pass


class SubmissionUpdate(BaseModel):
    profile_id: int | None = None
    problem_id: int | None = None
    submitted_at: datetime | None = None
    language: str | None = None
    status: SubmissionStatus | None = None
    platform_submission_id: str | None = None
    contest_id: int | None = None


class SubmissionResponse(SubmissionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
