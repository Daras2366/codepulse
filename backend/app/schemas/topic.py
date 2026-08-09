from pydantic import BaseModel, ConfigDict


class TopicBase(BaseModel):
    name: str


class TopicCreate(TopicBase):
    pass


class TopicUpdate(BaseModel):
    name: str | None = None


class TopicResponse(TopicBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
