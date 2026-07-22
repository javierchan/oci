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

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # S3-compatible artifact storage (MinIO locally, OCI Object Storage when deployed)
    STORAGE_BUCKET: str = "oci-dis-files"
    STORAGE_ENDPOINT: str = "http://localhost:9000"
    STORAGE_REGION: str = "us-ashburn-1"
    STORAGE_ACCESS_KEY: str = "minio"
    STORAGE_SECRET_KEY: str = "minio123"
    STORAGE_ADDRESSING_STYLE: Literal["path", "virtual"] = "path"

    # Governed OCI Generative AI provider
    OCI_GENAI_REGION: str = "us-chicago-1"
    OCI_GENAI_BASE_URL: str = (
        "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com/openai/v1"
    )
    OCI_GENAI_MODEL_ID: str = "openai.gpt-oss-20b"
    OCI_GENAI_MODEL_NAME: str = "OpenAI gpt-oss-20b"
    OCI_GENAI_SUPPORT_MODEL_ID: str = "openai.gpt-oss-120b"
    OCI_GENAI_SUPPORT_MODEL_NAME: str = "OpenAI gpt-oss-120b"
    OCI_GENAI_KNOWLEDGE_MODEL_ID: str = "openai.gpt-oss-120b"
    OCI_GENAI_KNOWLEDGE_MODEL_NAME: str = "OpenAI gpt-oss-120b"
    OCI_GENAI_EMBEDDING_MODEL_ID: str = "cohere.embed-v4.0"
    OCI_GENAI_EMBEDDING_MODEL_NAME: str = "Cohere Embed v4.0"
    OCI_GENAI_LARGE_READ_TIMEOUT_SECONDS: float = 300.0
    OCI_GENAI_LARGE_MAX_OUTPUT_TOKENS: int = 3072
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
    SERVICE_VERIFICATION_SCHEDULE_ENABLED: bool = True
    SERVICE_VERIFICATION_SCHEDULE_SECONDS: int = 86400
    SERVICE_VERIFICATION_STALE_SCAN_MAX_SOURCES: int = 20

    # Continuous official OCI pricing/estimator governance
    OCI_GOVERNANCE_SCHEDULE_ENABLED: bool = True
    OCI_GOVERNANCE_SCHEDULE_SECONDS: int = 86400
    OCI_GOVERNANCE_LOCK_TTL_SECONDS: int = 3600
    OCI_GOVERNANCE_MAX_SOURCE_AGE_HOURS: int = 72
    OCI_GOVERNANCE_CURRENCY: str = "USD"

    # Logging
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_genai_settings_for_use_case(use_case: str) -> Settings:
    """Return an immutable per-use-case model projection without global state."""

    settings = get_settings()
    if use_case == "support_assistant":
        return settings.model_copy(
            update={
                "OCI_GENAI_MODEL_ID": settings.OCI_GENAI_SUPPORT_MODEL_ID,
                "OCI_GENAI_MODEL_NAME": settings.OCI_GENAI_SUPPORT_MODEL_NAME,
                "OCI_GENAI_READ_TIMEOUT_SECONDS": settings.OCI_GENAI_LARGE_READ_TIMEOUT_SECONDS,
                "OCI_GENAI_MAX_OUTPUT_TOKENS": settings.OCI_GENAI_LARGE_MAX_OUTPUT_TOKENS,
            }
        )
    if use_case == "knowledge_maintenance":
        return settings.model_copy(
            update={
                "OCI_GENAI_MODEL_ID": settings.OCI_GENAI_KNOWLEDGE_MODEL_ID,
                "OCI_GENAI_MODEL_NAME": settings.OCI_GENAI_KNOWLEDGE_MODEL_NAME,
                "OCI_GENAI_READ_TIMEOUT_SECONDS": settings.OCI_GENAI_LARGE_READ_TIMEOUT_SECONDS,
                "OCI_GENAI_MAX_OUTPUT_TOKENS": settings.OCI_GENAI_LARGE_MAX_OUTPUT_TOKENS,
            }
        )
    return settings
