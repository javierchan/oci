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


class CommercialDocumentResponse(BaseModel):
    """One immutable official Oracle commercial-document snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    source_name: str
    original_filename: str
    content_hash: str
    parser_version: str
    status: str
    record_count: int
    retrieved_at: datetime
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    manifest: dict[str, Any]


class CommercialCatalogSummaryResponse(BaseModel):
    """Coverage and review state for one commercial evidence snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid")

    skus: int
    candidates: int
    pending: int
    approved: int
    blocked: int
    exceptions: int


class CommercialProductIdentityResponse(BaseModel):
    """Stable SKU identity plus every official workbook location."""

    model_config = ConfigDict(strict=True, extra="forbid")

    display_name: str
    service_category: Optional[str]
    product_hierarchy: list[str] = Field(default_factory=list)
    product_paths: list[list[str]] = Field(default_factory=list)
    official_location_count: int = Field(ge=0)
    structured_product: dict[str, Any] = Field(default_factory=dict)


class CommercialTermEvidenceResponse(BaseModel):
    """Human-readable commercial evidence selected for one SKU candidate."""

    model_config = ConfigDict(strict=True, extra="forbid")

    service_name: str
    metric_name: Optional[str]
    price_type: Optional[str]
    commercial_prices: list[Any] = Field(default_factory=list)
    additional_information: Optional[str]
    notes: Optional[str]
    source_sheet: str
    source_row: int
    constraints: list[dict[str, Any]] = Field(default_factory=list)


class CommercialRelationshipSummaryResponse(BaseModel):
    """One documented prerequisite, entitlement, or composition relationship."""

    model_config = ConfigDict(strict=True, extra="forbid")

    relationship_type: str
    target_part_number: Optional[str]
    target_name: str
    guidance: Optional[str]
    resolution_status: str


class CommercialCandidateIdentitySummaryResponse(BaseModel):
    """Small product projection safe for a paginated commercial queue row."""

    model_config = ConfigDict(strict=True, extra="forbid")

    display_name: str
    service_category: Optional[str]


class CommercialTermSummaryResponse(BaseModel):
    """Small commercial-term projection safe for a paginated queue row."""

    model_config = ConfigDict(strict=True, extra="forbid")

    service_name: str
    metric_name: Optional[str]
    price_type: Optional[str]


class CommercialCandidateResponse(BaseModel):
    """Lightweight generated mapping candidate for a bounded review page."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    part_number: str
    service_id: Optional[str]
    family_key: Optional[str]
    classification: str
    confidence: float
    status: str
    generator_version: str
    rule_status: Optional[str]
    rule_fixture_status: Optional[str]
    identity: CommercialCandidateIdentitySummaryResponse
    commercial_term: Optional[CommercialTermSummaryResponse]


class CommercialCandidateDetailResponse(BaseModel):
    """Full immutable commercial evidence for one explicitly opened candidate."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    part_number: str
    service_id: Optional[str]
    family_key: Optional[str]
    classification: str
    confidence: float
    status: str
    generator_version: str
    rule_status: Optional[str]
    rule_fixture_status: Optional[str]
    identity: CommercialProductIdentityResponse
    commercial_term: Optional[CommercialTermEvidenceResponse]
    composition: list[CommercialRelationshipSummaryResponse] = Field(default_factory=list)
    proposed_mapping: dict[str, Any]
    reasons: list[Any] = Field(default_factory=list)


class CommercialExceptionResponse(BaseModel):
    """Blocking or reviewable source ambiguity."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    candidate_id: Optional[str]
    part_number: Optional[str]
    code: str
    severity: str
    status: str
    details: dict[str, Any]


class CommercialReleaseResponse(BaseModel):
    """Atomic approved price, term, mapping, rule, and evidence release."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    version: str
    status: str
    validation_status: str
    open_exception_count: int
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    metadata: dict[str, Any]


class CommercialWorkspaceResponse(BaseModel):
    """Admin review workspace for official commercial evidence."""

    model_config = ConfigDict(strict=True, extra="forbid")

    document: Optional[CommercialDocumentResponse]
    summary: CommercialCatalogSummaryResponse
    candidates: list[CommercialCandidateResponse] = Field(default_factory=list)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)
    exceptions: list[CommercialExceptionResponse] = Field(default_factory=list)
    exceptions_page: int = Field(ge=1)
    exceptions_page_size: int = Field(ge=1, le=200)
    exceptions_total: int = Field(ge=0)
    releases: list[CommercialReleaseResponse] = Field(default_factory=list)
    field_authority: dict[str, str] = Field(default_factory=dict)


class CommercialCoverageReportResponse(BaseModel):
    """Aggregate preview or result of one governed catalog coverage advance."""

    model_config = ConfigDict(strict=True, extra="forbid")

    document_id: str
    dry_run: bool
    requested_exception_codes: list[str] = Field(default_factory=list)
    eligible_open_exceptions: int = Field(ge=0)
    resolved_exceptions: int = Field(ge=0)
    skipped_exceptions: int = Field(ge=0)
    skipped_by_reason: dict[str, int] = Field(default_factory=dict)
    candidate_count: int = Field(ge=0)
    direct_metered_count: int = Field(ge=0)
    external_rate_card_count: int = Field(ge=0)
    current_approved: int = Field(ge=0)
    current_blocked: int = Field(ge=0)
    projected_approved: int = Field(ge=0)
    projected_blocked: int = Field(ge=0)
    projected_direct_metered_approved: int = Field(ge=0)
    projected_direct_metered_blocked: int = Field(ge=0)
    projected_external_rate_card_approved: int = Field(ge=0)
    projected_external_rate_card_blocked: int = Field(ge=0)
    blockers_by_reason: dict[str, int] = Field(default_factory=dict)
    promotion_status: str
    promotion_error_code: Optional[str]
    promotion_detail: Optional[str]
    release_part_number_count: int = Field(ge=0)
    release_bom_part_number_count: int = Field(ge=0)


class CommercialCoverageWorkspaceResponse(CommercialWorkspaceResponse):
    """Commercial workspace plus a bounded catalog coverage funnel."""

    coverage_report: CommercialCoverageReportResponse


class OciProductPriceSummaryResponse(BaseModel):
    """Bounded PAYG price range from the latest approved USD snapshot."""

    model_config = ConfigDict(strict=True, extra="forbid")

    currency: str
    min_payg_unit_price: float
    max_payg_unit_price: float


class OciProductCatalogRowResponse(BaseModel):
    """Lightweight product taxonomy row for one paginated catalog page."""

    model_config = ConfigDict(strict=True, extra="forbid")

    product_key: str
    name: str
    category: Optional[str]
    sku_count: int = Field(ge=1)
    price_summary: Optional[OciProductPriceSummaryResponse]


class OciProductCatalogListResponse(BaseModel):
    """Paginated read-only OCI product taxonomy."""

    model_config = ConfigDict(strict=True, extra="forbid")

    products: list[OciProductCatalogRowResponse] = Field(default_factory=list)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class OciProductSkuResponse(BaseModel):
    """One SKU projection inside an explicitly opened product."""

    model_config = ConfigDict(strict=True, extra="forbid")

    part_number: str
    display_name: str
    metric_name: Optional[str]
    price_type: Optional[str]
    current_payg_unit_price: Optional[float]
    commercial_classification: Optional[str]
    is_bom_mapped: bool


class OciProductCatalogDetailResponse(BaseModel):
    """One product identity with a paginated, bounded SKU list."""

    model_config = ConfigDict(strict=True, extra="forbid")

    product_key: str
    name: str
    category: Optional[str]
    sku_count: int = Field(ge=1)
    price_summary: Optional[OciProductPriceSummaryResponse]
    skus: list[OciProductSkuResponse] = Field(default_factory=list)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class ProductCoverageBlockerResponse(BaseModel):
    """Machine-readable reason that prevents one product or SKU from promotion."""

    model_config = ConfigDict(strict=True, extra="forbid")

    part_number: Optional[str]
    code: str
    detail: str


class ProductCoverageRowResponse(BaseModel):
    """Lightweight product coverage candidate used by paginated review."""

    model_config = ConfigDict(strict=True, extra="forbid")

    product_key: str
    product_name: str
    category: Optional[str]
    sku_count: int = Field(ge=0)
    mapping_count: int = Field(ge=0)
    readiness_status: str
    commercial_readiness: str
    status: str
    promotable: bool
    blocker_count: int = Field(ge=0)
    generator_version: str


class ProductCoverageListResponse(BaseModel):
    """Bounded page of governed product coverage proposals."""

    model_config = ConfigDict(strict=True, extra="forbid")

    products: list[ProductCoverageRowResponse] = Field(default_factory=list)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class ProductCoverageDetailResponse(ProductCoverageRowResponse):
    """Complete proposed operational materialization for one OCI product."""

    proposed_service_id: str
    proposed_profile: dict[str, Any]
    proposed_policy: dict[str, Any]
    proposed_mappings: list[dict[str, Any]] = Field(default_factory=list)
    readiness_blockers: list[ProductCoverageBlockerResponse] = Field(default_factory=list)
    source_document_snapshot_id: Optional[str]
    review_rationale: Optional[str]
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ProductCoverageGenerationResponse(BaseModel):
    """Deterministic coverage-generation summary."""

    model_config = ConfigDict(strict=True, extra="forbid")

    generated: int = Field(ge=0)
    refreshed: int = Field(ge=0)
    ready: int = Field(ge=0)
    blocked_release: int = Field(ge=0)
    blocked_evidence: int = Field(ge=0)
    total: int = Field(ge=0)
    generator_version: str


class ProductCoverageReviewRequest(BaseModel):
    """Explicit administrator disposition for one product coverage proposal."""

    model_config = ConfigDict(strict=True, extra="forbid")

    decision: str = Field(pattern="^(approve|reject)$")
    rationale: str = Field(min_length=8, max_length=2000)


class CommercialCandidateReviewRequest(BaseModel):
    """Explicit administrator disposition of one generated candidate."""

    model_config = ConfigDict(strict=True, extra="forbid")

    decision: str = Field(pattern="^(approve|reject|keep_blocked)$")
    rationale: str = Field(min_length=8, max_length=2000)


class CommercialCatalogFinalizeRequest(BaseModel):
    """Explicit global catalog review using deterministic eligibility gates."""

    model_config = ConfigDict(strict=True, extra="forbid")

    rationale: str = Field(min_length=8, max_length=2000)


class CommercialBulkResolveRequest(BaseModel):
    """Allowlisted bulk resolution of non-material low-risk exceptions."""

    model_config = ConfigDict(strict=True, extra="forbid")

    exception_codes: list[str] = Field(min_length=1, max_length=10)
    rationale: str = Field(min_length=8, max_length=2000)
    dry_run: bool = False


class CommercialCoverageAdvanceRequest(BaseModel):
    """Preview or execute deterministic catalog coverage advancement."""

    model_config = ConfigDict(strict=True, extra="forbid")

    rationale: str = Field(min_length=8, max_length=2000)
    dry_run: bool = False
    promote: bool = False


class CommercialExceptionReviewRequest(BaseModel):
    """Explicit human disposition of one observed commercial discrepancy."""

    model_config = ConfigDict(strict=True, extra="forbid")

    decision: str = Field(pattern="^(resolve|accept_risk|keep_open)$")
    rationale: str = Field(min_length=8, max_length=2000)
    target_part_number: Optional[str] = Field(default=None, min_length=2, max_length=50)


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


class GovernanceSourceArtifactResponse(BaseModel):
    """Immutable official-source artifact captured for one verification run."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    source_kind: str
    source_url: str
    content_hash: str
    record_count: int
    storage_reference: str
    source_last_updated: Optional[datetime]
    retrieval_status: str
    validation_summary: dict[str, Any]
    retrieved_at: datetime


class QuotationRegressionRunResponse(BaseModel):
    """One family-level deterministic quotation regression result."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    family_key: str
    status: str
    fixture_count: int
    passed_count: int
    failed_count: int
    mapping_count: int
    findings: list[Any]
    started_at: datetime
    completed_at: datetime


class GovernanceChangeSetResponse(BaseModel):
    """Atomic OCI source, drift, regression, and approval decision."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    sync_job_id: str
    price_source_id: str
    price_snapshot_id: str
    previous_change_set_id: Optional[str]
    trigger_type: str
    currency: str
    status: str
    drift_classification: str
    materiality_score: float
    source_manifest: dict[str, Any]
    drift_summary: dict[str, Any]
    impact_summary: dict[str, Any]
    validation_status: str
    regression_summary: dict[str, Any]
    approval_status: str
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    promoted_at: Optional[datetime]
    error_details: Optional[dict[str, Any]]
    artifacts: list[GovernanceSourceArtifactResponse] = Field(default_factory=list)
    regressions: list[QuotationRegressionRunResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class GovernanceChangeSetListResponse(BaseModel):
    """Recent continuous OCI verification decisions."""

    model_config = ConfigDict(strict=True, extra="forbid")

    change_sets: list[GovernanceChangeSetResponse] = Field(default_factory=list)
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


class QuantityPresetResponse(BaseModel):
    """Governed planning shortcut expressed in the SKU's commercial unit."""

    model_config = ConfigDict(strict=True, extra="forbid")

    label: str
    quantity: float
    description: str


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
    usage_basis: str
    quote_rounding: str
    aggregation_window: str
    proration_policy: str
    free_tier_scope: str
    planning_envelope_increment: Optional[float]
    metering_policy: dict[str, Any]
    selection_policy: str
    requires_explicit_quantity: bool
    entry_guidance: str
    quantity_presets: list[QuantityPresetResponse] = Field(default_factory=list)
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
    usage_basis: Optional[str] = Field(default=None, min_length=1, max_length=40)
    quote_rounding: Optional[str] = Field(default=None, min_length=1, max_length=40)
    aggregation_window: Optional[str] = Field(default=None, min_length=1, max_length=40)
    proration_policy: Optional[str] = Field(default=None, min_length=1, max_length=40)
    free_tier_scope: Optional[str] = Field(default=None, min_length=1, max_length=40)
    planning_envelope_increment: Optional[float] = Field(default=None, gt=0)
    metering_policy: Optional[dict[str, Any]] = None
    selection_policy: Optional[str] = Field(default=None, pattern="^(required|optional|dependent)$")
    requires_explicit_quantity: Optional[bool] = None
    entry_guidance: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    quantity_presets: Optional[list[QuantityPresetResponse]] = None
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
    commitment_model: str = Field(
        default="pay_as_you_go",
        pattern="^(pay_as_you_go|annual_commitment|annual_flex|monthly_flex)$",
    )
    licensing_model: str = Field(
        default="license_included",
        pattern="^(license_included|byol)$",
    )
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
    commitment_model: str
    licensing_model: str
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
    source_baseline_quantity: float
    baseline_quantity: float
    planning_envelope_quantity: Optional[float]
    quantity_behavior: str
    quantity_increment: float
    minimum_quantity: float
    usage_basis: str
    quote_rounding: str
    aggregation_window: str
    proration_policy: str
    free_tier_scope: str
    planning_envelope_increment: Optional[float]
    metering_policy: dict[str, Any]
    requires_explicit_quantity: bool
    entry_guidance: str
    quantity_presets: list[QuantityPresetResponse] = Field(default_factory=list)
    default_sku_mapping_id: str
    default_selected: bool
    variants: list["ScenarioSkuVariantResponse"] = Field(default_factory=list)


class ScenarioSkuVariantResponse(BaseModel):
    """One approved commercial variant selectable for an environment metric."""

    model_config = ConfigDict(strict=True, extra="forbid")

    sku_mapping_id: str
    label: str
    part_number: Optional[str]
    predicates: dict[str, Any]
    is_billable: bool
    selection_policy: str
    quantity_behavior: str
    quantity_increment: float
    minimum_quantity: float
    quantity_unit: str
    usage_basis: str
    quote_rounding: str
    aggregation_window: str
    proration_policy: str
    free_tier_scope: str
    planning_envelope_increment: Optional[float]
    metering_policy: dict[str, Any]
    requires_explicit_quantity: bool
    entry_guidance: str
    quantity_presets: list[QuantityPresetResponse] = Field(default_factory=list)


class ScenarioCommercialCoverageResponse(BaseModel):
    """Product-level commercial readiness for a detected architecture service."""

    model_config = ConfigDict(strict=True, extra="forbid")

    service_id: str
    product_name: str
    classification: str
    readiness: str
    publication_policy: str
    approved_mapping_count: int
    required_inputs: list[str]
    dependent_service_ids: list[str]
    dependencies_present: list[str]
    guidance: str
    source_urls: list[str]


class CurrentBomContextResponse(BaseModel):
    """Authoritative current BOM state available to the scenario assistant."""

    model_config = ConfigDict(strict=True, extra="forbid")

    snapshot_id: str
    scenario_id: str
    scenario_name: str
    scenario_status: str
    publication_status: str
    technical_snapshot_id: str
    technical_snapshot_current: bool
    coverage_pct: float
    currency: str
    monthly_total: float
    contract_total: float
    environment_names: list[str]
    line_item_count: int
    unresolved_line_count: int
    warnings_count: int
    ready_for_use: bool
    created_at: datetime


class ScenarioAssistantResponse(BaseModel):
    """Evidence-backed scenario draft and minimum missing client questions."""

    model_config = ConfigDict(strict=True, extra="forbid")

    draft: DeploymentScenarioCreateRequest
    detected_services: list[str]
    metric_options: list[ScenarioMetricOptionResponse]
    commercial_coverage: list[ScenarioCommercialCoverageResponse]
    current_bom: Optional[CurrentBomContextResponse] = None
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
    commercial_term_id: Optional[str] = None
    commercial_rule_family_id: Optional[str] = None
    evidence_reference_ids: list[str] = Field(default_factory=list)
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
    commercial_term_id: Optional[str] = None
    commercial_rule_family_id: Optional[str] = None
    evidence_reference_ids: list[str] = Field(default_factory=list)
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
    commercial_release_id: Optional[str] = None
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
