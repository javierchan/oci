"""Dashboard snapshot schemas for technical KPI and chart views."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DashboardKPIStrip(BaseModel):
    """Top-line technical KPIs for the dashboard."""

    model_config = ConfigDict(strict=True, extra="forbid")

    oic_msgs_month: float = 0.0
    peak_packs_hour: float = 0.0
    di_workspace_active: bool = False
    di_data_processed_gb_month: float = 0.0
    functions_execution_units_gb_s: float = 0.0


class CoverageChart(BaseModel):
    """Coverage metrics for populated catalog fields."""

    model_config = ConfigDict(strict=True, extra="forbid")

    total_integrations: int = 0
    with_interface_id: int = 0
    without_interface_id: int = 0
    pattern_assigned: int = 0
    payload_informed: int = 0
    source_destination_informed: int = 0


class CompletenessChart(BaseModel):
    """Completeness breakdown for key governed fields."""

    model_config = ConfigDict(strict=True, extra="forbid")

    qa_ok: int = 0
    qa_revisar: int = 0
    qa_pending: int = 0
    rationale_informed: int = 0
    core_tools_informed: int = 0
    comments_informed: int = 0
    retry_policy_informed: int = 0


class PatternMixEntry(BaseModel):
    """Pattern-assignment count entry."""

    model_config = ConfigDict(strict=True, extra="forbid")

    pattern_id: str
    name: str
    count: int


class PayloadDistributionBucket(BaseModel):
    """Payload bucket count entry."""

    model_config = ConfigDict(strict=True, extra="forbid")

    label: str
    count: int


class DashboardCharts(BaseModel):
    """Composite dashboard chart payload."""

    model_config = ConfigDict(strict=True, extra="forbid")

    coverage: CoverageChart
    completeness: CompletenessChart
    pattern_mix: list[PatternMixEntry] = Field(default_factory=list)
    payload_distribution: list[PayloadDistributionBucket] = Field(default_factory=list)


class DashboardRisk(BaseModel):
    """Technical risk summary with drill-through IDs."""

    model_config = ConfigDict(strict=True, extra="forbid")

    code: str
    label: str
    count: int
    integration_ids: list[str] = Field(default_factory=list)


class DashboardMaturity(BaseModel):
    """High-level technical maturity indicators."""

    model_config = ConfigDict(strict=True, extra="forbid")

    qa_ok_pct: float = 0.0
    pattern_assigned_pct: float = 0.0
    payload_informed_pct: float = 0.0
    governed_pct: float = 0.0


class DashboardSnapshotSummary(BaseModel):
    """List view for persisted dashboard snapshots."""

    model_config = ConfigDict(strict=True, extra="forbid")

    snapshot_id: str
    volumetry_snapshot_id: str
    mode: str
    created_at: datetime


class DashboardSnapshotResponse(BaseModel):
    """Full technical dashboard snapshot response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    snapshot_id: str
    project_id: str
    volumetry_snapshot_id: str
    mode: str
    kpi_strip: DashboardKPIStrip
    charts: DashboardCharts
    risks: list[DashboardRisk] = Field(default_factory=list)
    maturity: DashboardMaturity
    created_at: datetime


class DashboardSnapshotListResponse(BaseModel):
    """Dashboard snapshot collection."""

    model_config = ConfigDict(strict=True, extra="forbid")

    snapshots: list[DashboardSnapshotSummary] = Field(default_factory=list)
    total: int = 0
