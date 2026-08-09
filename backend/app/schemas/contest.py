from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Platform


class ContestBase(BaseModel):
    platform_contest_id: str
    title: str
    platform: Platform
    contest_url: str
    start_time: datetime
    duration_minutes: int


class ContestCreate(ContestBase):
    pass


class ContestUpdate(BaseModel):
    platform_contest_id: str | None = None
    title: str | None = None
    platform: Platform | None = None
    contest_url: str | None = None
    start_time: datetime | None = None
    duration_minutes: int | None = None


class ContestResponse(ContestBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
