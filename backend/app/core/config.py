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

    # ---------------------------------------------------------------------------
    # Gemini AI Coach configuration
    # ---------------------------------------------------------------------------
    # API key for Google Gemini (used for AI Coach features)
    # Get your key from: https://aistudio.google.com/app/apikey
    GEMINI_API_KEY: str | None = None
    # Model to use — default is a currently supported fast model.
    # Verified against the live Gemini API on 2026-11-08:
    #   gemini-3.5-flash  — works with both generate_content (agent, function
    #                       calling) and interactions.create (chat), ~2-3s.
    #   gemini-3.8-flash  — listed but intermittently exceeds the 30s timeout.
    #   gemini-2.5-flash  — 404 for this API key ("no longer available").
    # Override with GEMINI_MODEL in .env. Verify at:
    # https://ai.google.dev/gemini-api/docs/models
    GEMINI_MODEL: str = "gemini-3.5-flash"
    # Request timeout in seconds for Gemini API calls
    GEMINI_TIMEOUT_SECONDS: int = 30

    class Config:
        env_file = ".env"


settings = Settings()