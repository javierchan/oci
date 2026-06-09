"""Schemas for governed project-level and integration-level AI review jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import CatalogIntegrationResponse


AiReviewScope = Literal["project", "integration"]
AiReviewGraphContextType = Literal["node", "edge"]
AiReviewSeverity = Literal["critical", "high", "medium", "low", "positive"]
AiReviewCategory = Literal[
    "critical_blockers",
    "high_confidence_fixes",
    "needs_architect_decision",
    "looks_production_ready",
]
AiReviewArea = Literal[
    "data_quality",
    "snapshot_freshness",
    "canvas_consistency",
    "oci_compatibility",
    "stress_review",
    "planned_drift",
    "demo_readiness",
    "red_team",
    "governance",
]
AiReviewDriftStatus = Literal["no_baseline", "no_drift", "minor_drift", "material_drift", "blocking_drift"]
AiReviewProviderMode = Literal["deterministic_only", "llm_available", "misconfigured"]


class AiReviewGraphContext(BaseModel):
    """Optional graph selection context used to scope project-level review evidence."""

    model_config = ConfigDict(strict=True, extra="forbid")

    type: AiReviewGraphContextType
    label: Optional[str] = None
    source: Optional[str] = None
    target: Optional[str] = None


class AiReviewCreateRequest(BaseModel):
    """Request payload to submit a governed AI review job."""

    model_config = ConfigDict(strict=True, extra="forbid")

    scope: AiReviewScope = "project"
    integration_id: Optional[str] = None
    include_llm: bool = True
    graph_context: Optional[AiReviewGraphContext] = None
    reviewer_personas: list[Literal["architect", "security", "operations", "executive"]] = Field(
        default_factory=lambda: ["architect", "security", "operations", "executive"],
    )


class AiReviewBaselineCreateRequest(BaseModel):
    """Request payload to approve the current governed state as a planned baseline."""

    model_config = ConfigDict(strict=True, extra="forbid")

    scope: AiReviewScope = "project"
    integration_id: Optional[str] = None
    label: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = Field(default=None, max_length=2000)


class AiReviewBaselineResponse(BaseModel):
    """Serialized approved planned-state baseline metadata."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    project_id: str
    scope: AiReviewScope
    integration_id: Optional[str] = None
    created_by: str
    label: str
    note: Optional[str] = None
    row_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AiReviewBaselineLookupResponse(BaseModel):
    """Lookup response for the active planned baseline in one review scope."""

    model_config = ConfigDict(strict=True, extra="forbid")

    baseline: Optional[AiReviewBaselineResponse] = None


class AiReviewBaselineListResponse(BaseModel):
    """Historical planned baselines for one review scope, active first."""

    model_config = ConfigDict(strict=True, extra="forbid")

    baselines: list[AiReviewBaselineResponse] = Field(default_factory=list)
    total: int = 0


class AiReviewMetric(BaseModel):
    """One compact metric surfaced in the AI review board."""

    model_config = ConfigDict(strict=True, extra="forbid")

    label: str
    value: str
    detail: str


class AiReviewQuotaState(BaseModel):
    """Role and budget status for governed AI review creation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    daily_job_limit: int
    actor_jobs_today: int = 0
    remaining_jobs_today: int
    llm_daily_job_limit: int


class AiReviewProviderStatus(BaseModel):
    """Provider health/configuration status without exposing credentials."""

    model_config = ConfigDict(strict=True, extra="forbid")

    provider: Literal["codex"] = "codex"
    configured: bool
    mode: AiReviewProviderMode
    model: str
    wire_api: str
    base_url: str
    request_timeout_seconds: float
    quota: AiReviewQuotaState
    data_retention_policy: str
    prompt_redaction_policy: list[str] = Field(default_factory=list)
    status_message: str


class AiReviewDecisionBrief(BaseModel):
    """Decision-ready AI review brief assembled from governed evidence."""

    model_config = ConfigDict(strict=True, extra="forbid")

    signoff_status: Literal["blocked", "needs_review", "ready_with_caveats", "ready"]
    headline: str
    primary_risk: str
    recommended_next_action: str
    decision_points: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class AiReviewTopologyInsight(BaseModel):
    """Topology-aware insight derived from source, destination, QA, and warning concentration."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    insight_type: Literal["system_hotspot", "edge_hotspot", "payload_hotspot"]
    severity: Literal["high", "medium", "low", "positive"]
    title: str
    summary: str
    metric: str
    system_name: Optional[str] = None
    source_system: Optional[str] = None
    destination_system: Optional[str] = None
    action_href: Optional[str] = None
    integration_ids: list[str] = Field(default_factory=list)


class AiReviewStressScenario(BaseModel):
    """Deterministic growth or evidence scenario for architecture review."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    name: str
    multiplier: float
    confidence: Literal["high", "medium", "low"]
    summary: str
    projected_daily_payload_gb: float
    top_integration_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AiReviewRemediationStep(BaseModel):
    """One prioritized, owner-oriented action generated from findings."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    priority: int
    owner: Literal["Architect", "Analyst", "Operations", "Executive"]
    title: str
    action: str
    expected_impact: str
    action_href: Optional[str] = None
    finding_ids: list[str] = Field(default_factory=list)
    integration_ids: list[str] = Field(default_factory=list)


class AiReviewEvidence(BaseModel):
    """Traceable evidence item referenced by findings."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    label: str
    detail: str
    source: str
    entity_type: str
    entity_id: Optional[str] = None
    href: Optional[str] = None


class AiReviewDriftItem(BaseModel):
    """One planned-baseline versus actual-state drift item."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    severity: Literal["critical", "high", "medium", "low"]
    entity_type: Literal["project", "integration"]
    integration_id: Optional[str] = None
    field: str
    label: str
    planned: Optional[str] = None
    actual: Optional[str] = None
    detail: str
    action_href: Optional[str] = None


class AiReviewDriftReport(BaseModel):
    """Planned-baseline versus current-state comparison surfaced in the review board."""

    model_config = ConfigDict(strict=True, extra="forbid")

    status: AiReviewDriftStatus
    baseline: Optional[AiReviewBaselineResponse] = None
    item_count: int = 0
    worst_severity: Optional[Literal["critical", "high", "medium", "low"]] = None
    summary: str
    items: list[AiReviewDriftItem] = Field(default_factory=list)


class AiReviewFieldDiff(BaseModel):
    """One field-level current-versus-recommended patch preview."""

    model_config = ConfigDict(strict=True, extra="forbid")

    field: str
    current: Optional[str] = None
    recommended: Optional[str] = None


class AiReviewSuggestedPatch(BaseModel):
    """A bounded, deterministic, human-approved patch candidate."""

    model_config = ConfigDict(strict=True, extra="forbid")

    integration_id: str
    label: str
    description: str
    patch: dict[str, object]
    field_diffs: list[AiReviewFieldDiff] = Field(default_factory=list)
    safe_to_apply: bool = False
    safety_note: str


class AiReviewFinding(BaseModel):
    """One prioritized review finding with evidence and a suggested next action."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    severity: AiReviewSeverity
    category: AiReviewCategory
    review_area: AiReviewArea
    title: str
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    current_state: str
    recommended_state: str
    recommendation: str
    action_label: str
    action_href: str | None = None
    integration_ids: list[str] = Field(default_factory=list)
    suggested_patch: Optional[AiReviewSuggestedPatch] = None


class AiReviewGroup(BaseModel):
    """UI-ready grouping for review-board findings."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: AiReviewCategory
    title: str
    description: str
    finding_ids: list[str] = Field(default_factory=list)
    count: int = 0
    worst_severity: Optional[AiReviewSeverity] = None


class AiReviewPersonaSummary(BaseModel):
    """Perspective-specific deterministic reviewer summary."""

    model_config = ConfigDict(strict=True, extra="forbid")

    persona: Literal["architect", "security", "operations", "executive"]
    title: str
    summary: str
    focus: list[str] = Field(default_factory=list)


class AiReviewRecommendationAcceptance(BaseModel):
    """Human acceptance record for one recommendation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    finding_id: str
    accepted_by: str
    accepted_at: datetime
    note: Optional[str] = None
    applied_patch: Optional[dict[str, object]] = None


class AiReviewAcceptRecommendationRequest(BaseModel):
    """Bounded payload for accepting one recommendation without catalog mutation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    note: Optional[str] = Field(default=None, max_length=1000)


class AiReviewApplyPatchRequest(BaseModel):
    """Payload for applying a deterministic AI review patch after human confirmation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    note: Optional[str] = Field(default=None, max_length=1000)


class AiReviewResponse(BaseModel):
    """Governed review assembled from deterministic product evidence plus optional LLM summary."""

    model_config = ConfigDict(strict=True, extra="forbid")

    project_id: str
    project_name: str
    scope: AiReviewScope = "project"
    integration_id: Optional[str] = None
    engine: str = "governed-deterministic-review-v2"
    generated_at: datetime
    readiness_score: int
    readiness_label: str
    summary: str
    llm_status: Literal["not_configured", "completed", "failed", "skipped"] = "not_configured"
    llm_model: Optional[str] = None
    llm_summary: Optional[str] = None
    graph_context: Optional[AiReviewGraphContext] = None
    metrics: list[AiReviewMetric] = Field(default_factory=list)
    decision_brief: AiReviewDecisionBrief = Field(
        default_factory=lambda: AiReviewDecisionBrief(
            signoff_status="needs_review",
            headline="Review generated before decision brief enrichment was available.",
            primary_risk="Open review findings need architect triage.",
            recommended_next_action="Review the findings and evidence registry.",
        )
    )
    topology_insights: list[AiReviewTopologyInsight] = Field(default_factory=list)
    stress_scenarios: list[AiReviewStressScenario] = Field(default_factory=list)
    remediation_plan: list[AiReviewRemediationStep] = Field(default_factory=list)
    findings: list[AiReviewFinding] = Field(default_factory=list)
    groups: list[AiReviewGroup] = Field(default_factory=list)
    evidence: list[AiReviewEvidence] = Field(default_factory=list)
    evidence_pack: list[str] = Field(default_factory=list)
    reviewer_personas: list[AiReviewPersonaSummary] = Field(default_factory=list)
    drift: AiReviewDriftReport = Field(
        default_factory=lambda: AiReviewDriftReport(
            status="no_baseline",
            summary="No planned baseline was available when this review was generated.",
        )
    )


class AiReviewJobResponse(BaseModel):
    """Serialized persisted AI review job."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    project_id: str
    requested_by: str
    status: Literal["pending", "running", "completed", "failed"]
    scope: AiReviewScope
    integration_id: Optional[str] = None
    input_payload: dict[str, object]
    result: Optional[AiReviewResponse] = None
    accepted_recommendations: list[AiReviewRecommendationAcceptance] = Field(default_factory=list)
    error_details: Optional[dict[str, object]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AiReviewJobListResponse(BaseModel):
    """Collection response for persisted AI review jobs."""

    model_config = ConfigDict(strict=True, extra="forbid")

    jobs: list[AiReviewJobResponse] = Field(default_factory=list)
    total: int = 0


class AiReviewJobCompareResponse(BaseModel):
    """Comparison between two completed AI review job results."""

    model_config = ConfigDict(strict=True, extra="forbid")

    project_id: str
    base_job_id: str
    target_job_id: str
    base_readiness_score: int
    target_readiness_score: int
    readiness_score_delta: int
    base_readiness_label: str
    target_readiness_label: str
    finding_count_delta: int
    critical_high_delta: int
    added_findings: list[str] = Field(default_factory=list)
    resolved_findings: list[str] = Field(default_factory=list)
    persistent_findings: list[str] = Field(default_factory=list)
    summary: str


class AiReviewApplyPatchResponse(BaseModel):
    """Result of applying a suggested patch and refreshing the review job."""

    model_config = ConfigDict(strict=True, extra="forbid")

    job: AiReviewJobResponse
    integration: CatalogIntegrationResponse
    applied_patch: AiReviewSuggestedPatch
