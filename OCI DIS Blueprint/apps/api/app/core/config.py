"""Application configuration — all settings sourced from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    APP_NAME: str = "OCI DIS Blueprint API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    CORS_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
    ]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://dis:dis@localhost:5432/oci_dis"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Security / Auth
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Object Storage (OCI or S3-compatible)
    STORAGE_BUCKET: str = "oci-dis-files"
    STORAGE_ENDPOINT: str = ""
    STORAGE_ACCESS_KEY: str = ""
    STORAGE_SECRET_KEY: str = ""

    # Governed AI review LLM provider (Codex backend / Responses API)
    CODEX_BASE_URL: str = "https://chatgpt.com/backend-api/codex"
    CODEX_MODEL: str = "gpt-5.5"
    CODEX_WIRE_API: str = "responses"
    CODEX_REQUEST_TIMEOUT_SECONDS: float = 20.0
    CODEX_CONFIG_PATH: str = "/codex/config.toml"
    CODEX_AUTH_JSON_PATH: str = "/codex/auth.json"
    CODEX_PROVIDER_NAME: str = "codex"
    CODEX_CLIENT_NAME: str = "codex-cli"
    CODEX_CLIENT_VERSION: str = "0"
    AI_REVIEW_DAILY_JOB_LIMIT: int = 100
    AI_REVIEW_LLM_DAILY_JOB_LIMIT: int = 25

    # Service Product Library verification agent
    SERVICE_VERIFICATION_SCHEDULE_ENABLED: bool = False
    SERVICE_VERIFICATION_SCHEDULE_SECONDS: int = 86400
    SERVICE_VERIFICATION_STALE_SCAN_MAX_SOURCES: int = 20

    # Import rules (parity-mode defaults — PRD-017)
    IMPORT_TBQ_COLUMN: str = "TBQ"
    IMPORT_TBQ_REQUIRED_VALUE: str = "Y"
    IMPORT_EXCLUDE_ESTADO: list[str] = ["Duplicado 2"]
    IMPORT_SOURCE_DATA_START_ROW: int = 6  # Headers at row 5, data at row 6

    # Observability
    OTLP_ENDPOINT: str = ""
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
