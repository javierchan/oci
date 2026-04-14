"""Project request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProjectCreateRequest(BaseModel):
    """Payload for creating a project."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str
    owner_id: str
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    """Serialized project resource."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    name: str
    owner_id: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """Paginated-ish project list response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    projects: list[ProjectResponse]
