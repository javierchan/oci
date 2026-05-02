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


class ReadinessResponse(BaseModel):
    """API readiness contract for operators and frontend diagnostics."""

    model_config = ConfigDict(strict=True, extra="forbid")

    status: str
    version: str
    database_migrations: MigrationReadinessResponse
