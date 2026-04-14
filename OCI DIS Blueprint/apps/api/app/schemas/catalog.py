"""Catalog schemas for listing, editing, and lineage views."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CatalogIntegrationPatch(BaseModel):
    """Allowed architect-owned fields for row updates."""

    model_config = ConfigDict(strict=True, extra="forbid")

    selected_pattern: Optional[str] = None
    pattern_rationale: Optional[str] = None
    comments: Optional[str] = None
    retry_policy: Optional[str] = None
    core_tools: Optional[str] = None
    additional_tools_overlays: Optional[str] = None


class CatalogIntegrationResponse(BaseModel):
    """Serialized catalog row with QA fields."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    project_id: str
    source_row_id: Optional[str]
    seq_number: int
    interface_id: Optional[str]
    owner: Optional[str]
    brand: Optional[str]
    business_process: Optional[str]
    interface_name: Optional[str]
    description: Optional[str]
    status: Optional[str]
    mapping_status: Optional[str]
    initial_scope: Optional[str]
    complexity: Optional[str]
    frequency: Optional[str]
    type: Optional[str]
    base: Optional[str]
    interface_status: Optional[str]
    is_real_time: Optional[bool]
    trigger_type: Optional[str]
    response_size_kb: Optional[float]
    payload_per_execution_kb: Optional[float]
    is_fan_out: Optional[bool]
    fan_out_targets: Optional[int]
    source_system: Optional[str]
    source_technology: Optional[str]
    source_api_reference: Optional[str]
    source_owner: Optional[str]
    destination_system: Optional[str]
    destination_technology_1: Optional[str]
    destination_technology_2: Optional[str]
    destination_owner: Optional[str]
    executions_per_day: Optional[float]
    payload_per_hour_kb: Optional[float]
    selected_pattern: Optional[str]
    pattern_rationale: Optional[str]
    comments: Optional[str]
    retry_policy: Optional[str]
    core_tools: Optional[str]
    additional_tools_overlays: Optional[str]
    qa_status: Optional[str]
    qa_reasons: list[str] = Field(default_factory=list)
    calendarization: Optional[str]
    uncertainty: Optional[str]
    created_at: datetime
    updated_at: datetime


class CatalogListResponse(BaseModel):
    """Paginated catalog list response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    integrations: list[CatalogIntegrationResponse]
    total: int
    page: int
    page_size: int


class LineageDetail(BaseModel):
    """Source lineage for a catalog row."""

    model_config = ConfigDict(strict=True, extra="forbid")

    source_row_id: str
    source_row_number: int
    raw_data: dict[str, object]
    included: bool
    exclusion_reason: Optional[str] = None
    normalization_events: list[dict[str, object]] = Field(default_factory=list)
    import_batch_id: str
    import_filename: str


class CatalogIntegrationDetail(BaseModel):
    """Catalog row plus detailed lineage."""

    model_config = ConfigDict(strict=True, extra="forbid")

    integration: CatalogIntegrationResponse
    lineage: LineageDetail


class BulkPatchRequest(BaseModel):
    """Bulk patch request payload."""

    model_config = ConfigDict(strict=True, extra="forbid")

    integration_ids: list[str]
    patch: CatalogIntegrationPatch
    actor_id: str = "api-user"


class BulkPatchResult(BaseModel):
    """Bulk patch operation result."""

    model_config = ConfigDict(strict=True, extra="forbid")

    updated: int
    errors: list[str] = Field(default_factory=list)
