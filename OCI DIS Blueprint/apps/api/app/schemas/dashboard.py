"""Dashboard snapshot schemas for technical KPI and chart views."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DashboardKPIStrip(BaseModel):
    """Top-line technical KPIs for the dashboard."""

    model_config = ConfigDict(strict=True, extra="forbid")

    oic_msgs_month: float = 0.0
    peak_packs_hour: float = 0.0
    di_workspace_active: bool = False
    di_data_processed_gb_month: float = 0.0
    functions_execution_units_gb_s: float = 0.0


class CoverageMetric(BaseModel):
    """Coverage count plus completion ratio for one governed signal."""

    model_config = ConfigDict(strict=True, extra="forbid")

    complete: int = 0
    total: int = 0
    ratio: float = 0.0


class CoverageChart(BaseModel):
    """Coverage metrics for populated catalog fields."""

    model_config = ConfigDict(strict=True, extra="forbid")

    total_integrations: int = 0
    formal_id: CoverageMetric = Field(default_factory=CoverageMetric)
    pattern: CoverageMetric = Field(default_factory=CoverageMetric)
    payload: CoverageMetric = Field(default_factory=CoverageMetric)
    trigger: CoverageMetric = Field(default_factory=CoverageMetric)
    source_destination: CoverageMetric = Field(default_factory=CoverageMetric)
    fan_out: CoverageMetric = Field(default_factory=CoverageMetric)


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


class DashboardForecastConfidence(BaseModel):
    """Truthfulness signal for forecast-like technical metrics."""

    model_config = ConfigDict(strict=True, extra="forbid")

    level: str = "low"
    title: str = "Low confidence"
    message: str = ""
    payload_coverage_ratio: float = 0.0


class DashboardServiceRuleStatus(BaseModel):
    """Provenance and freshness of rules used for the technical snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid")

    version: str = "unavailable"
    source: str = "unavailable"
    freshness_status: str = "unavailable"
    stale_evidence_count: int = 0
    open_findings_count: int = 0
    last_verified_at: str | None = None


class DashboardProductUsage(BaseModel):
    """One captured product and the integrations that use it."""

    model_config = ConfigDict(strict=True, extra="forbid")

    tool_key: str
    service_id: str | None = None
    role: Literal["core", "overlay"]
    integration_count: int = 0
    coverage_ratio: float = 0.0


class DashboardProductFootprint(BaseModel):
    """Complete product inventory derived from governed catalog canvases."""

    model_config = ConfigDict(strict=True, extra="forbid")

    captured_product_count: int = 0
    represented_product_count: int = 0
    rows_with_products: int = 0
    total_rows: int = 0
    products: list[DashboardProductUsage] = Field(default_factory=list)


class DashboardCharts(BaseModel):
    """Composite dashboard chart payload."""

    model_config = ConfigDict(strict=True, extra="forbid")

    coverage: CoverageChart
    completeness: CompletenessChart
    pattern_mix: list[PatternMixEntry] = Field(default_factory=list)
    payload_distribution: list[PayloadDistributionBucket] = Field(default_factory=list)
    forecast_confidence: DashboardForecastConfidence = Field(default_factory=DashboardForecastConfidence)
    service_rules: DashboardServiceRuleStatus = Field(default_factory=DashboardServiceRuleStatus)
    product_footprint: DashboardProductFootprint = Field(default_factory=DashboardProductFootprint)


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
