from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RatingHistoryBase(BaseModel):
    profile_id: int
    contest_id: int | None = None
    rating: int
    rating_change: int
    recorded_at: datetime


class RatingHistoryCreate(RatingHistoryBase):
    pass


class RatingHistoryUpdate(BaseModel):
    profile_id: int | None = None
    contest_id: int | None = None
    rating: int | None = None
    rating_change: int | None = None
    recorded_at: datetime | None = None


class RatingHistoryResponse(RatingHistoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
