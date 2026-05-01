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

    # Governed AI review LLM provider (Oracle Code Assist / Responses API)
    OCA_API_KEY: str = ""
    OCA_BASE_URL: str = "https://code-internal.aiservice.us-chicago-1.oci.oraclecloud.com/20250206/app/litellm"
    OCA_MODEL: str = "oca/gpt-5.5"
    OCA_WIRE_API: str = "responses"
    OCA_REQUEST_TIMEOUT_SECONDS: float = 20.0
    OCA_CONFIG_PATH: str = "/codex/config.toml"
    OCA_AUTH_JSON_PATH: str = "/codex/auth.json"
    OCA_CLIENT_NAME: str = "codex-cli"
    OCA_CLIENT_VERSION: str = "0"

    # Calc Engine
    OIC_BILLING_THRESHOLD_KB: float = 50.0
    OIC_PACK_SIZE_MSGS_PER_HOUR: int = 5000
    PAYLOAD_MONTH_DAYS: int = 30

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
