"""Volumetry snapshot and consolidated metric schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OICMetrics(BaseModel):
    """OIC consolidated metrics."""

    model_config = ConfigDict(strict=True, extra="forbid")

    total_billing_msgs_month: float = 0.0
    total_billing_msgs_per_month: float = 0.0
    peak_billing_msgs_hour: float = 0.0
    peak_packs_hour: float = 0.0
    row_count: int = 0


class DIMetrics(BaseModel):
    """Data Integration consolidated metrics."""

    model_config = ConfigDict(strict=True, extra="forbid")

    workspace_active: bool = False
    row_count: int = 0
    data_processed_gb_month: float = 0.0


class FunctionsMetrics(BaseModel):
    """Oracle Functions consolidated metrics."""

    model_config = ConfigDict(strict=True, extra="forbid")

    total_invocations_month: float = 0.0
    total_execution_units_gb_s: float = 0.0
    row_count: int = 0


class StreamingMetrics(BaseModel):
    """OCI Streaming consolidated metrics."""

    model_config = ConfigDict(strict=True, extra="forbid")

    row_count: int = 0
    total_gb_month: float = 0.0
    partition_count: int = 0


class QueueMetrics(BaseModel):
    """OCI Queue consolidated metrics."""

    model_config = ConfigDict(strict=True, extra="forbid")

    row_count: int = 0


class ConsolidatedMetrics(BaseModel):
    """Top-level consolidated metrics object."""

    model_config = ConfigDict(strict=True, extra="forbid")

    oic: OICMetrics
    data_integration: DIMetrics
    functions: FunctionsMetrics
    streaming: StreamingMetrics
    queue: QueueMetrics


class VolumetrySnapshotResponse(BaseModel):
    """Serialized volumetry snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid")

    snapshot_id: str
    project_id: str
    assumption_set_version: str
    triggered_by: str
    row_results: dict[str, dict[str, object]]
    consolidated: ConsolidatedMetrics
    metadata: Optional[dict[str, object]] = None
    created_at: datetime


class VolumetrySnapshotSummary(BaseModel):
    """List-view snapshot metadata without row-level metrics."""

    model_config = ConfigDict(strict=True, extra="forbid")

    snapshot_id: str
    project_id: str
    assumption_set_version: str
    triggered_by: str
    consolidated: ConsolidatedMetrics
    metadata: Optional[dict[str, object]] = None
    row_result_count: int = 0
    created_at: datetime


class VolumetrySnapshotListResponse(BaseModel):
    """List of volumetry snapshots."""

    model_config = ConfigDict(strict=True, extra="forbid")

    snapshots: list[VolumetrySnapshotSummary] = Field(default_factory=list)


class VolumetrySnapshotRowResultsResponse(BaseModel):
    """Paginated row-level metrics for one volumetry snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid")

    rows: list[dict[str, object]] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class ScopedRecalculationRequest(BaseModel):
    """Request body for a scoped recalculation trigger."""

    model_config = ConfigDict(strict=True, extra="forbid")

    integration_ids: list[str] = Field(default_factory=list)
    actor_id: str = "api-user"


class RecalculationJobStatusResponse(BaseModel):
    """Snapshot-backed status payload for synchronous recalculation requests."""

    model_config = ConfigDict(strict=True, extra="forbid")

    job_id: str
    project_id: str
    status: str
    snapshot_id: str | None = None
    scope: str = "project"
    integration_ids: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
