from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Difficulty, Platform


class ProblemBase(BaseModel):
    platform: Platform
    platform_problem_id: str
    title: str
    slug: str
    problem_url: str
    difficulty: Difficulty
    acceptance_rate: float | None = None


class ProblemCreate(ProblemBase):
    pass


class ProblemUpdate(BaseModel):
    platform: Platform | None = None
    platform_problem_id: str | None = None
    title: str | None = None
    slug: str | None = None
    problem_url: str | None = None
    difficulty: Difficulty | None = None
    acceptance_rate: float | None = None


class ProblemResponse(ProblemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
