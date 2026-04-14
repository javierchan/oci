"""Audit event schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AuditEventResponse(BaseModel):
    """Serialized audit event."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    project_id: Optional[str]
    actor_id: str
    event_type: str
    entity_type: str
    entity_id: str
    correlation_id: Optional[str] = None
    old_value: Optional[dict[str, object]] = None
    new_value: Optional[dict[str, object]] = None
    metadata: Optional[dict[str, object]] = None
    created_at: datetime


class AuditEventListResponse(BaseModel):
    """Paginated audit list response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    events: list[AuditEventResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
