from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "CodePulse API"
    DEBUG: bool = True

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ---------------------------------------------------------------------------
    # Codeforces sync configuration
    # ---------------------------------------------------------------------------
    # Maximum number of submissions to import per sync run.  Pages of 100 are
    # fetched until this limit is reached or Codeforces returns an empty page.
    # Raise this value in .env (e.g. CODEFORCES_SUBMISSION_LIMIT=5000) to sync
    # a deeper history without changing code.
    CODEFORCES_SUBMISSION_LIMIT: int = 1000
    CODEFORCES_SUBMISSION_PAGE_SIZE: int = 100

    class Config:
        env_file = ".env"


settings = Settings()