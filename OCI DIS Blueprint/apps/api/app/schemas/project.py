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


class ProjectPatchRequest(BaseModel):
    """Payload for partially updating project metadata."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: Optional[str] = None
    owner_id: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    """Serialized project resource."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    name: str
    owner_id: str
    description: Optional[str]
    status: str
    project_metadata: Optional[dict[str, object]] = None
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    """Paginated-ish project list response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    projects: list[ProjectResponse]


class ProjectArchiveResponse(BaseModel):
    """Archive action result for one project."""

    model_config = ConfigDict(strict=True, extra="forbid")

    project: ProjectResponse
    detail: str


class ProjectDeleteResponse(BaseModel):
    """Deletion result for one archived project."""

    model_config = ConfigDict(strict=True, extra="forbid")

    project_id: str
    detail: str
    deleted_import_batches: int
    deleted_source_rows: int
    deleted_integrations: int
    deleted_justifications: int
    deleted_volumetry_snapshots: int
    deleted_dashboard_snapshots: int
    deleted_audit_events: int
