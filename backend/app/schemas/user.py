from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    username: str
    full_name: str | None = None
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str | None
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)