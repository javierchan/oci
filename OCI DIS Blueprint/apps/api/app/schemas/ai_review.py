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
    "demo_readiness",
    "red_team",
    "governance",
]


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


class AiReviewMetric(BaseModel):
    """One compact metric surfaced in the AI review board."""

    model_config = ConfigDict(strict=True, extra="forbid")

    label: str
    value: str
    detail: str


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
    findings: list[AiReviewFinding] = Field(default_factory=list)
    groups: list[AiReviewGroup] = Field(default_factory=list)
    evidence: list[AiReviewEvidence] = Field(default_factory=list)
    evidence_pack: list[str] = Field(default_factory=list)
    reviewer_personas: list[AiReviewPersonaSummary] = Field(default_factory=list)


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


class AiReviewApplyPatchResponse(BaseModel):
    """Result of applying a suggested patch and refreshing the review job."""

    model_config = ConfigDict(strict=True, extra="forbid")

    job: AiReviewJobResponse
    integration: CatalogIntegrationResponse
    applied_patch: AiReviewSuggestedPatch
