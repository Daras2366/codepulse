from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "CodePulse API"
    DEBUG: bool = True

    DATABASE_URL: str

    class Config:
        env_file = ".env"


settings = Settings()