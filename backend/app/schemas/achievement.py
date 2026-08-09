from pydantic import BaseModel, ConfigDict

from app.models.enums import AchievementCategory


class AchievementBase(BaseModel):
    name: str
    description: str
    icon: str | None = None
    category: AchievementCategory


class AchievementCreate(AchievementBase):
    pass


class AchievementUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    category: AchievementCategory | None = None


class AchievementResponse(AchievementBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
