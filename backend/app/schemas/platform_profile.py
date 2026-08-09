from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Platform


class PlatformProfileBase(BaseModel):
    user_id: int
    platform: Platform
    username: str
    current_rating: int | None = None
    max_rating: int | None = None
    rank: str | None = None
    problems_solved: int = 0
    contests_attended: int = 0
    profile_url: str | None = None
    is_connected: bool = True
    last_synced_at: datetime | None = None


class PlatformProfileCreate(PlatformProfileBase):
    pass


class PlatformProfileUpdate(BaseModel):
    user_id: int | None = None
    platform: Platform | None = None
    username: str | None = None
    current_rating: int | None = None
    max_rating: int | None = None
    rank: str | None = None
    problems_solved: int | None = None
    contests_attended: int | None = None
    profile_url: str | None = None
    is_connected: bool | None = None
    last_synced_at: datetime | None = None


class PlatformProfileResponse(PlatformProfileBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
