from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ContestParticipationBase(BaseModel):
    profile_id: int
    contest_id: int
    rank: int | None = None
    old_rating: int | None = None
    new_rating: int | None = None
    rating_change: int | None = None
    solved: int = 0
    penalty: int | None = None


class ContestParticipationCreate(ContestParticipationBase):
    pass


class ContestParticipationUpdate(BaseModel):
    profile_id: int | None = None
    contest_id: int | None = None
    rank: int | None = None
    old_rating: int | None = None
    new_rating: int | None = None
    rating_change: int | None = None
    solved: int | None = None
    penalty: int | None = None


class ContestParticipationResponse(ContestParticipationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
