"""Catalog schemas for listing, editing, and lineage views."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

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
    raw_column_values: Optional[dict[str, Any]] = None


class ManualIntegrationCreate(BaseModel):
    """Payload for guided manual capture of a new integration."""

    model_config = ConfigDict(strict=True, extra="forbid")

    interface_id: Optional[str] = None
    brand: str
    business_process: str
    interface_name: str
    description: Optional[str] = None
    source_system: str
    source_technology: Optional[str] = None
    source_api_reference: Optional[str] = None
    source_owner: Optional[str] = None
    destination_system: str
    destination_technology: Optional[str] = None
    destination_owner: Optional[str] = None
    type: Optional[str] = None
    frequency: Optional[str] = None
    payload_per_execution_kb: Optional[float] = None
    complexity: Optional[str] = None
    uncertainty: Optional[str] = None
    selected_pattern: Optional[str] = None
    pattern_rationale: Optional[str] = None
    core_tools: Optional[list[str]] = None
    tbq: str = "Y"
    initial_scope: Optional[str] = None
    owner: Optional[str] = None


class OICEstimateRequest(BaseModel):
    """Live OIC estimate request with no persistence side effects."""

    model_config = ConfigDict(strict=True, extra="forbid")

    frequency: Optional[str] = None
    payload_per_execution_kb: Optional[float] = None
    response_kb: float = 0.0


class OICEstimateResponse(BaseModel):
    """Live OIC estimate response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    billing_msgs_per_execution: Optional[float] = None
    billing_msgs_per_month: Optional[float] = None
    peak_packs_per_hour: Optional[float] = None
    executions_per_day: Optional[float] = None
    computable: bool


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
    raw_data: dict[str, Any]
    column_names: dict[str, str] = Field(default_factory=dict)
    included: bool
    exclusion_reason: Optional[str] = None
    normalization_events: list[dict[str, object]] = Field(default_factory=list)
    import_batch_id: str
    import_batch_date: datetime
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


class CatalogIntegrationDeleteResponse(BaseModel):
    """Removal result for one catalog integration."""

    model_config = ConfigDict(strict=True, extra="forbid")

    project_id: str
    integration_id: str
    detail: str
    deleted_source_row_id: Optional[str] = None
    deleted_import_batch_id: Optional[str] = None
    deleted_justification_id: Optional[str] = None
    recalculated_snapshot_id: Optional[str] = None
