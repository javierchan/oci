"""Application configuration — all settings sourced from environment variables."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # App
    APP_NAME: str = "OCI DIS Blueprint API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
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

    # Governed OCI Generative AI provider
    OCI_GENAI_REGION: str = "us-chicago-1"
    OCI_GENAI_BASE_URL: str = (
        "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com/openai/v1"
    )
    OCI_GENAI_MODEL_ID: str = "openai.gpt-oss-20b"
    OCI_GENAI_MODEL_NAME: str = "OpenAI gpt-oss-20b"
    OCI_GENAI_PROJECT_ID: str = ""
    OCI_GENAI_COMPARTMENT_ID: str = ""
    OCI_GENAI_API_KEY_FILE: str = "/tmp/oci-dis-home/.oci-genai/api_key"
    OCI_GENAI_TRANSPORT_MODE: Literal["auto", "responses", "chat_completions"] = "auto"
    OCI_GENAI_RESPONSES_UNAVAILABLE_TTL_SECONDS: int = 3600
    OCI_GENAI_CONNECT_TIMEOUT_SECONDS: float = 10.0
    OCI_GENAI_READ_TIMEOUT_SECONDS: float = 240.0
    OCI_GENAI_MAX_RETRIES: int = 2
    OCI_GENAI_RETRY_BASE_SECONDS: float = 0.5
    OCI_GENAI_RETRY_MAX_SECONDS: float = 8.0
    OCI_GENAI_MAX_OUTPUT_TOKENS: int = 2048
    OCI_GENAI_AGENT_MAX_STEPS: int = 4
    OCI_GENAI_AGENT_MAX_EVIDENCE_CHARS: int = 60000
    OCI_GENAI_GUARDRAILS_ENABLED: bool = True
    OCI_GENAI_GUARDRAILS_VERSION: str = "1.0.1"
    OCI_GENAI_GUARDRAILS_FAILURE_MODE: Literal["closed", "open"] = "closed"
    OCI_GENAI_METRICS_REDIS_ENABLED: bool = True
    OCI_GENAI_METRICS_REDIS_KEY: str = "oci_dis:genai:metrics:v1"
    OCI_GENAI_METRICS_RETENTION_SECONDS: int = 2592000
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
