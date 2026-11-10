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
    # Optional fallback model tried when the primary model is unavailable
    # (e.g. 503 high-demand or 404 model-not-found). Must be verified against
    # BOTH client.models.generate_content (agent) and client.interactions.create
    # (chat) before enabling. Leave unset to disable fallback.
    GEMINI_FALLBACK_MODEL: str | None = None
    # Request timeout in seconds for Gemini API calls
    GEMINI_TIMEOUT_SECONDS: int = 30
    # Bounded retries with exponential backoff + jitter for transient provider
    # errors (503/429/timeout/network). Permanent errors (401/403/400) are
    # never retried.
    GEMINI_MAX_RETRIES: int = 2
    GEMINI_RETRY_BASE_DELAY_SECONDS: float = 0.5
    GEMINI_RETRY_MAX_DELAY_SECONDS: float = 8.0

    class Config:
        env_file = ".env"


settings = Settings()