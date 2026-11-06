from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class UserCreate(BaseModel):
    username: str
    full_name: str | None = None
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if len(v) > 128:
            raise ValueError("Password must not exceed 128 characters")
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str | None
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)