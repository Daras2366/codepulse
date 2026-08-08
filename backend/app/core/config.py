from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "CodePulse API"
    DEBUG: bool = True

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"


settings = Settings()