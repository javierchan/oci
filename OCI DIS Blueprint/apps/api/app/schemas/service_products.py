"""Schemas for governed service product library responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ServiceProductVersionResponse(BaseModel):
    """Versioned metadata snapshot for one service product."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    version_label: str
    description: Optional[str]
    capabilities: dict[str, Any]
    use_cases: list[Any]
    anti_patterns: list[Any]
    regional_availability: Optional[str]
    commercial_notes: Optional[str]
    security_notes: Optional[str]
    deprecation_notes: Optional[str]
    metadata: dict[str, Any]
    effective_from: Optional[datetime]
    created_by: str
    created_at: datetime
    updated_at: datetime


class ServiceLimitResponse(BaseModel):
    """Normalized service limit or operational constraint."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    limit_key: str
    label: str
    scope: str
    limit_type: str
    constraint_kind: str
    enforcement: str
    applicability: dict[str, Any]
    value: Any
    unit: Optional[str]
    default_value: Any = None
    can_request_increase: bool
    source_url: Optional[str]
    source_retrieved_at: Optional[datetime]
    confidence: float
    notes: Optional[str]
    is_active: bool
    updated_at: datetime


class ServiceEvidenceSourceResponse(BaseModel):
    """Trusted evidence source tracked for verification."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    source_type: str
    url: str
    title: str
    publisher: str
    trust_tier: str
    retrieval_strategy: str
    expected_update_frequency_days: int
    last_checked_at: Optional[datetime]
    last_changed_at: Optional[datetime]
    content_hash: Optional[str]
    status: str
    updated_at: datetime


class ServiceInteroperabilityRuleResponse(BaseModel):
    """Directional service interoperability rule."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    source_service_id: str
    source_service_name: str
    target_service_id: str
    target_service_name: str
    relationship_type: str
    supported: bool
    directionality: str
    patterns: list[Any]
    required_components: list[Any]
    constraints: dict[str, Any]
    risk_notes: Optional[str]
    source_url: Optional[str]
    confidence: float
    last_verified_at: Optional[datetime]
    is_active: bool
    updated_at: datetime


class ServiceProductSummaryResponse(BaseModel):
    """List-card summary for one service product."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    service_id: str
    name: str
    category: str
    architecture_role: Optional[str]
    summary: Optional[str]
    pricing_model: Optional[str]
    sla_uptime_pct: Optional[float]
    version: str
    is_active: bool
    limits_count: int = 0
    evidence_count: int = 0
    interoperability_count: int = 0
    verification_status: str = "seeded_pending_verification"
    commercial_classification: str
    commercial_readiness: str
    publication_policy: str
    approved_mapping_count: int = 0
    commercial_guidance: str
    commercial_required_inputs: list[str] = Field(default_factory=list)
    last_verified_at: Optional[datetime] = None
    updated_at: datetime


class ServiceProductDetailResponse(ServiceProductSummaryResponse):
    """Detailed service product profile with normalized governance evidence."""

    model_config = ConfigDict(strict=True, extra="forbid")

    architectural_fit: Optional[str]
    anti_patterns: Optional[str]
    interoperability_notes: Optional[str]
    oracle_docs_urls: Optional[str]
    current_version: Optional[ServiceProductVersionResponse] = None
    limits: list[ServiceLimitResponse] = Field(default_factory=list)
    evidence_sources: list[ServiceEvidenceSourceResponse] = Field(default_factory=list)
    interoperability_rules: list[ServiceInteroperabilityRuleResponse] = Field(default_factory=list)


class ServiceProductListResponse(BaseModel):
    """Service product list response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    products: list[ServiceProductSummaryResponse]
    total: int
    stale_evidence_count: int = 0
    open_findings_count: int = 0


class ServiceInteroperabilityMatrixResponse(BaseModel):
    """Service-to-service matrix response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    services: list[ServiceProductSummaryResponse]
    rules: list[ServiceInteroperabilityRuleResponse]
    total_rules: int


class ServiceVerificationJobResponse(BaseModel):
    """Verification job summary for future execute-agent runs."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    requested_by: str
    scope: str
    request_payload: Optional[dict[str, Any]]
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    services_checked: list[Any]
    sources_checked: int
    changes_detected: int
    findings: list[Any]
    recommendations: list[Any]
    error_details: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class ServiceVerificationFindingResponse(BaseModel):
    """Human-reviewable finding produced by a service verification job."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    job_id: str
    service_profile_id: Optional[str]
    finding_type: str
    severity: str
    title: str
    summary: str
    old_value: Any
    new_value: Any
    source_url: Optional[str]
    evidence_excerpt: Optional[str]
    recommended_action: Optional[str]
    review_status: str
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ServiceVerificationJobListResponse(BaseModel):
    """Verification job list response."""

    model_config = ConfigDict(strict=True, extra="forbid")

    jobs: list[ServiceVerificationJobResponse]
    total: int


class ServiceVerificationAlertResponse(BaseModel):
    """Actionable verification freshness alert."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    alert_type: str
    severity: str
    title: str
    summary: str
    service_profile_id: Optional[str]
    service_id: Optional[str]
    source_url: Optional[str]
    finding_id: Optional[str]
    status: str
    created_at: datetime


class ServiceVerificationAlertListResponse(BaseModel):
    """Verification freshness and finding alert queue."""

    model_config = ConfigDict(strict=True, extra="forbid")

    alerts: list[ServiceVerificationAlertResponse]
    total: int
    open_findings_count: int
    stale_evidence_count: int


class ServiceVerificationRunRequest(BaseModel):
    """Request to execute source verification for selected service products."""

    model_config = ConfigDict(strict=True, extra="forbid")

    service_ids: list[str] = Field(default_factory=list)
    max_sources: int = Field(default=8, ge=1, le=50)
    force: bool = False


class ServiceVerificationFindingReviewRequest(BaseModel):
    """Manual review decision for a verification finding."""

    model_config = ConfigDict(strict=True, extra="forbid")

    review_status: str = Field(pattern="^(accepted|dismissed|reviewed)$")
    note: Optional[str] = None
