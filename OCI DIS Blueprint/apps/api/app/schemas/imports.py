"""Import batch and source-row schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NormalizationEventResponse(BaseModel):
    """Serialized normalization event."""

    model_config = ConfigDict(strict=True, extra="forbid")

    field: str
    old_value: object = None
    new_value: object = None
    rule: str


class ImportBatchResponse(BaseModel):
    """Serialized import batch."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    project_id: str
    filename: str
    parser_version: str
    status: str
    source_row_count: Optional[int] = None
    tbq_y_count: Optional[int] = None
    excluded_count: Optional[int] = None
    loaded_count: Optional[int] = None
    header_map: Optional[dict[str, str]] = None
    error_details: Optional[dict[str, object]] = None
    created_at: datetime
    updated_at: datetime


class ImportBatchListResponse(BaseModel):
    """Serialized import batch collection."""

    model_config = ConfigDict(strict=True, extra="forbid")

    import_batches: list[ImportBatchResponse]


class SourceRowResponse(BaseModel):
    """Serialized source integration row."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    source_row_number: int
    included: bool
    exclusion_reason: Optional[str] = None
    raw_data: dict[str, object]
    normalization_events: list[NormalizationEventResponse] = Field(default_factory=list)


class SourceRowListResponse(BaseModel):
    """Paginated list of source rows."""

    model_config = ConfigDict(strict=True, extra="forbid")

    rows: list[SourceRowResponse]
    total: int
    page: int
    page_size: int


class ImportQualityMetric(BaseModel):
    """One metric used by the import data-quality assistant."""

    model_config = ConfigDict(strict=True, extra="forbid")

    label: str
    value: str
    detail: str


class ImportQualityFinding(BaseModel):
    """One deterministic import-quality finding with an action target."""

    model_config = ConfigDict(strict=True, extra="forbid")

    severity: str
    title: str
    summary: str
    action_label: str
    action_href: str


class ImportQualityAssistantResponse(BaseModel):
    """Data-quality assistant summary for one import batch."""

    model_config = ConfigDict(strict=True, extra="forbid")

    project_id: str
    batch_id: str
    status: str
    filename: str
    row_count: int
    included_count: int
    excluded_count: int
    normalization_event_count: int
    recommended_next_action: str
    metrics: list[ImportQualityMetric] = Field(default_factory=list)
    findings: list[ImportQualityFinding] = Field(default_factory=list)


class ImportBatchDeleteResponse(BaseModel):
    """Removal result for one import batch."""

    model_config = ConfigDict(strict=True, extra="forbid")

    project_id: str
    batch_id: str
    detail: str
    deleted_source_rows: int
    deleted_integrations: int
    deleted_justifications: int
    recalculated_snapshot_id: Optional[str] = None
