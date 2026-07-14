"""Pydantic contracts for governed OCI pricing and Bill of Materials workflows."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.ai_review import AiReviewActionWorkspace


class PriceSourceResponse(BaseModel):
    """One governed source of OCI list or contracted prices."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    name: str
    source_type: str
    base_url: Optional[str]
    currency: str
    status: str
    last_synced_at: Optional[datetime]
    created_by: str
    created_at: datetime
    updated_at: datetime


class PriceSourceListResponse(BaseModel):
    """Available price sources."""

    model_config = ConfigDict(strict=True, extra="forbid")

    sources: list[PriceSourceResponse] = Field(default_factory=list)
    total: int


class PriceSyncRequest(BaseModel):
    """Request to synchronize a price source in one currency."""

    model_config = ConfigDict(strict=True, extra="forbid")

    source_id: Optional[str] = None
    currency: str = Field(default="USD", min_length=3, max_length=3)


class PriceSyncJobResponse(BaseModel):
    """Terminal price synchronization job state."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    source_id: str
    requested_by: str
    currency: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    item_count: int
    changes_detected: int
    snapshot_id: Optional[str]
    error_details: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class PriceSyncJobListResponse(BaseModel):
    """Recent price synchronization jobs."""

    model_config = ConfigDict(strict=True, extra="forbid")

    jobs: list[PriceSyncJobResponse] = Field(default_factory=list)
    total: int


class PriceCatalogSnapshotResponse(BaseModel):
    """Immutable normalized price catalog metadata."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    source_id: str
    sync_job_id: Optional[str]
    currency: str
    source_last_updated: Optional[datetime]
    retrieved_at: datetime
    content_hash: str
    item_count: int
    approval_status: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    metadata: dict[str, Any]
    created_at: datetime


class PriceCatalogSnapshotListResponse(BaseModel):
    """Recent immutable price catalogs."""

    model_config = ConfigDict(strict=True, extra="forbid")

    snapshots: list[PriceCatalogSnapshotResponse] = Field(default_factory=list)
    total: int


class PriceItemResponse(BaseModel):
    """Normalized price item or tier."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    snapshot_id: str
    part_number: str
    display_name: str
    metric_name: str
    service_category: str
    price_type: str
    currency: str
    model: str
    value: float
    range_min: Optional[float]
    range_max: Optional[float]
    range_unit: Optional[str]


class PriceItemListResponse(BaseModel):
    """Paginated price items."""

    model_config = ConfigDict(strict=True, extra="forbid")

    items: list[PriceItemResponse] = Field(default_factory=list)
    total: int
    page: int
    page_size: int


class SkuMappingResponse(BaseModel):
    """Approved mapping from service demand to OCI SKU."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    service_id: str
    tool_key: str
    part_number: Optional[str]
    billing_metric_key: str
    formula_key: str
    quantity_behavior: str
    quantity_increment: float
    minimum_quantity: float
    quantity_unit: str
    predicates: dict[str, Any]
    is_billable: bool
    status: str
    version: str
    source_url: Optional[str]
    confidence: float
    updated_at: datetime


class SkuMappingListResponse(BaseModel):
    """Governed SKU mappings and coverage."""

    model_config = ConfigDict(strict=True, extra="forbid")

    mappings: list[SkuMappingResponse] = Field(default_factory=list)
    total: int
    billable_count: int
    non_billable_count: int


class SkuMappingPatchRequest(BaseModel):
    """Admin change to an existing mapping decision."""

    model_config = ConfigDict(strict=True, extra="forbid")

    part_number: Optional[str] = None
    billing_metric_key: Optional[str] = None
    formula_key: Optional[str] = None
    quantity_behavior: Optional[str] = Field(
        default=None,
        pattern="^(packaged|fixed_capacity|hourly|continuous|manual_monthly)$",
    )
    quantity_increment: Optional[float] = Field(default=None, gt=0)
    minimum_quantity: Optional[float] = Field(default=None, ge=0)
    quantity_unit: Optional[str] = Field(default=None, min_length=1, max_length=100)
    predicates: Optional[dict[str, Any]] = None
    is_billable: Optional[bool] = None
    status: Optional[str] = Field(default=None, pattern="^(draft|approved|retired)$")
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class DeploymentMonthlyQuantityInput(BaseModel):
    """One explicit monthly quantity in the commercial unit of the selected metric."""

    model_config = ConfigDict(strict=True, extra="forbid")

    period_index: int = Field(ge=1, le=120)
    quantity: float = Field(ge=0)


class DeploymentRampPhaseInput(BaseModel):
    """Inclusive activation phase for an environment or one service override."""

    model_config = ConfigDict(strict=True, extra="forbid")

    service_id: Optional[str] = Field(default=None, min_length=1, max_length=80)
    metric_key: Optional[str] = Field(default=None, min_length=1, max_length=150)
    sku_mapping_id: Optional[str] = Field(default=None, min_length=1, max_length=36)
    start_month: int = Field(ge=1, le=120)
    end_month: int = Field(ge=1, le=120)
    start_multiplier: float = Field(default=1.0, ge=0, le=1)
    end_multiplier: float = Field(default=1.0, ge=0, le=1)
    interpolation: str = Field(default="step", pattern="^(step|linear|monthly)$")
    start_quantity: Optional[float] = Field(default=None, ge=0)
    end_quantity: Optional[float] = Field(default=None, ge=0)
    quantity_unit: Optional[str] = Field(default=None, min_length=1, max_length=100)
    monthly_quantities: list[DeploymentMonthlyQuantityInput] = Field(default_factory=list, max_length=120)
    rationale: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_interval(self) -> "DeploymentRampPhaseInput":
        if self.end_month < self.start_month:
            raise ValueError("Ramp phase end_month must not precede start_month")
        has_explicit_quantity = self.start_quantity is not None or bool(self.monthly_quantities)
        if has_explicit_quantity:
            if not self.service_id or not self.metric_key or not self.quantity_unit:
                raise ValueError("Explicit quantity plans require service_id, metric_key, and quantity_unit")
            if self.interpolation == "monthly":
                months = [item.period_index for item in self.monthly_quantities]
                expected = list(range(self.start_month, self.end_month + 1))
                if sorted(months) != expected:
                    raise ValueError("Monthly quantity plans require one value for every active month")
            elif self.start_quantity is None or self.end_quantity is None:
                raise ValueError("Constant and linear plans require start_quantity and end_quantity")
            elif self.interpolation == "step" and self.start_quantity != self.end_quantity:
                raise ValueError("Constant quantity plans require equal start and end quantities")
        elif self.interpolation == "monthly":
            raise ValueError("Monthly interpolation requires explicit quantities")
        elif self.interpolation == "step" and self.start_multiplier != self.end_multiplier:
            raise ValueError("Step phases require equal start and end multipliers")
        return self


class DeploymentEnvironmentInput(BaseModel):
    """Physical environment allocation used by one deployment scenario."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    active_hours_month: float = Field(default=744.0, ge=0, le=744)
    demand_share: float = Field(default=1.0, ge=0, le=1)
    ha_multiplier: float = Field(default=1.0, ge=1, le=10)
    dr_role: str = Field(default="primary", pattern="^(primary|standby|none)$")
    phases: list[DeploymentRampPhaseInput] = Field(default_factory=list, max_length=100)


class DeploymentScenarioCreateRequest(BaseModel):
    """Create a governed deployment scenario from a technical snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(default="Baseline deployment", min_length=1, max_length=255)
    technical_snapshot_id: Optional[str] = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    region: str = Field(default="global", min_length=1, max_length=100)
    price_mode: str = Field(default="public_list", pattern="^(public_list|contract_rate|manual_rate_card)$")
    contract_months: int = Field(default=12, ge=1, le=120)
    start_date: date = Field(default_factory=date.today, strict=False)
    proration_policy: str = Field(default="full_month", pattern="^full_month$")
    consumption_model: str = Field(default="explicit_units", pattern="^(explicit_units|legacy_share)$")
    environments: list[DeploymentEnvironmentInput] = Field(default_factory=list)
    service_config: dict[str, dict[str, Any]] = Field(default_factory=dict)
    assumptions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ramps(self) -> "DeploymentScenarioCreateRequest":
        for environment in self.environments:
            phases_by_service: dict[str, list[DeploymentRampPhaseInput]] = {}
            for phase in environment.phases:
                if phase.end_month > self.contract_months:
                    raise ValueError("Ramp phase exceeds contract_months")
                phase_key = f"{phase.service_id or '*'}:{phase.metric_key or '*'}"
                phases_by_service.setdefault(phase_key, []).append(phase)
                if self.consumption_model == "explicit_units":
                    if (
                        not phase.service_id
                        or not phase.metric_key
                        or not phase.quantity_unit
                        or (phase.start_quantity is None and not phase.monthly_quantities)
                    ):
                        raise ValueError(
                            "Explicit consumption phases require a product, metric, unit, and real quantity"
                        )
            for phases in phases_by_service.values():
                ordered = sorted(phases, key=lambda item: (item.start_month, item.end_month))
                for previous, current in zip(ordered, ordered[1:]):
                    if current.start_month <= previous.end_month:
                        raise ValueError("Ramp phases for the same service cannot overlap")
        return self


class DeploymentScenarioResponse(BaseModel):
    """Governed project deployment scenario."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    project_id: str
    name: str
    status: str
    currency: str
    region: str
    price_mode: str
    technical_snapshot_id: str
    contract_months: int
    start_date: date
    proration_policy: str
    consumption_model: str
    environments: list[DeploymentEnvironmentInput]
    service_config: dict[str, Any]
    assumptions: dict[str, Any]
    created_by: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class DeploymentScenarioListResponse(BaseModel):
    """Deployment scenarios for one project."""

    model_config = ConfigDict(strict=True, extra="forbid")

    scenarios: list[DeploymentScenarioResponse] = Field(default_factory=list)
    total: int


class ScenarioMetricOptionResponse(BaseModel):
    """Governed commercial unit and baseline demand available to the ramp editor."""

    model_config = ConfigDict(strict=True, extra="forbid")

    service_id: str
    product_name: str
    metric_key: str
    metric_label: str
    quantity_unit: str
    baseline_quantity: float
    quantity_behavior: str
    quantity_increment: float
    minimum_quantity: float
    default_sku_mapping_id: str
    variants: list["ScenarioSkuVariantResponse"] = Field(default_factory=list)


class ScenarioSkuVariantResponse(BaseModel):
    """One approved commercial variant selectable for an environment metric."""

    model_config = ConfigDict(strict=True, extra="forbid")

    sku_mapping_id: str
    label: str
    part_number: Optional[str]
    predicates: dict[str, Any]
    is_billable: bool
    quantity_behavior: str
    quantity_increment: float
    minimum_quantity: float
    quantity_unit: str


class ScenarioAssistantResponse(BaseModel):
    """Evidence-backed scenario draft and minimum missing client questions."""

    model_config = ConfigDict(strict=True, extra="forbid")

    draft: DeploymentScenarioCreateRequest
    detected_services: list[str]
    metric_options: list[ScenarioMetricOptionResponse]
    required_questions: list[str]
    warnings: list[str]
    confidence: str
    ai_status: str
    ai_summary: Optional[str]


class BomGenerationRequest(BaseModel):
    """Request a governed BOM for an approved deployment scenario."""

    model_config = ConfigDict(strict=True, extra="forbid")

    scenario_id: str


class BomJobResponse(BaseModel):
    """Terminal BOM generation job state."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    project_id: str
    scenario_id: str
    requested_by: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    bom_snapshot_id: Optional[str]
    error_details: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class BomJobListResponse(BaseModel):
    """Recent BOM jobs for one project."""

    model_config = ConfigDict(strict=True, extra="forbid")

    jobs: list[BomJobResponse] = Field(default_factory=list)
    total: int


class BomLineItemResponse(BaseModel):
    """One auditable priced or blocked line."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    environment: str
    service_id: str
    part_number: Optional[str]
    description: str
    metric_name: str
    quantity: float
    unit: str
    unit_price: float
    monthly_amount: float
    annual_amount: float
    contract_amount: float
    formula: str
    inputs: dict[str, Any]
    status: str
    warnings: list[Any]
    provenance: dict[str, Any]
    periods: list["BomLinePeriodResponse"] = Field(default_factory=list)


class BomLinePeriodResponse(BaseModel):
    """One immutable monthly amount with pricing provenance."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    period_index: int
    period_start: date
    multiplier: float
    quantity: float
    active_hours: float
    unit_price: float
    amount: float
    selected_price_item_id: Optional[str]
    formula: str
    inputs: dict[str, Any]
    status: str
    warnings: list[Any]
    provenance: dict[str, Any]


class BomPeriodSummary(BaseModel):
    """Aggregated monthly run rate and composition for charts and exports."""

    model_config = ConfigDict(strict=True, extra="forbid")

    period_index: int
    period_start: date
    total: float
    cumulative_total: float
    by_environment: dict[str, float]
    by_service: dict[str, float]


class BomSnapshotResponse(BaseModel):
    """Full immutable BOM and its provenance."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    project_id: str
    scenario_id: str
    technical_snapshot_id: str
    price_catalog_snapshot_id: str
    mapping_version: str
    engine_version: str
    currency: str
    coverage_pct: float
    monthly_total: float
    annual_total: float
    contract_total: float
    steady_state_monthly_total: float
    peak_monthly_total: float
    ramp_deferred_amount: float
    first_active_period: Optional[int]
    steady_state_period: Optional[int]
    monthly_series: list[BomPeriodSummary] = Field(default_factory=list)
    recommendation_workspace: AiReviewActionWorkspace
    summary: dict[str, Any]
    warnings: list[Any]
    publication_status: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    line_items: list[BomLineItemResponse] = Field(default_factory=list)
    created_at: datetime


class BomSnapshotListResponse(BaseModel):
    """Recent BOM snapshots without line-item payloads."""

    model_config = ConfigDict(strict=True, extra="forbid")

    snapshots: list[BomSnapshotResponse] = Field(default_factory=list)
    total: int


class BomComparisonResponse(BaseModel):
    """Deterministic delta between two governed BOM snapshots."""

    model_config = ConfigDict(strict=True, extra="forbid")

    baseline_snapshot_id: str
    comparison_snapshot_id: str
    currency: str
    monthly_delta: float
    annual_delta: float
    contract_delta: float
    service_monthly_deltas: dict[str, float]
    environment_monthly_deltas: dict[str, float]
    period_deltas: dict[int, float]
    driver_categories: dict[str, bool]
    drivers: list[str] = Field(default_factory=list)


class BomReviewRequest(BaseModel):
    """Approve or publish a complete BOM snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid")

    publication_status: str = Field(pattern="^(approved|published)$")
    note: Optional[str] = None
