"""Readiness response schemas for deployment and migration checks."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class MigrationReadinessResponse(BaseModel):
    """Current Alembic migration state compared with repository heads."""

    model_config = ConfigDict(strict=True, extra="forbid")

    ready: bool
    current_revisions: list[str] = Field(default_factory=list)
    head_revisions: list[str] = Field(default_factory=list)
    pending_revisions: list[str] = Field(default_factory=list)
    recovery_hint: str | None = None


class ObjectStorageReadinessResponse(BaseModel):
    """Connectivity state for the authoritative artifact store."""

    model_config = ConfigDict(strict=True, extra="forbid")

    ready: bool
    bucket: str
    provider: str
    recovery_hint: str | None = None


class RedisReadinessResponse(BaseModel):
    """Connectivity state for shared sessions, queues, locks, and counters."""

    model_config = ConfigDict(strict=True, extra="forbid")

    ready: bool
    recovery_hint: str | None = None


class AppKnowledgeReadinessResponse(BaseModel):
    """Active knowledge identity and complete provider-vector readiness."""

    model_config = ConfigDict(strict=True, extra="forbid")

    ready: bool
    source_hash: str | None = None
    runtime_version: str | None = None
    embedding_model: str | None = None
    vector_count: int = 0
    recovery_hint: str | None = None


class ReadinessResponse(BaseModel):
    """API readiness contract for operators and frontend diagnostics."""

    model_config = ConfigDict(strict=True, extra="forbid")

    status: str
    version: str
    database_migrations: MigrationReadinessResponse
    object_storage: ObjectStorageReadinessResponse
    redis: RedisReadinessResponse
    app_knowledge: AppKnowledgeReadinessResponse
