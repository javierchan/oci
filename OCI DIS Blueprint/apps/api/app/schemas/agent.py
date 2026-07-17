"""Strict API contracts for governed OCI Generative AI agent runs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


AgentType = Literal[
    "architecture_review",
    "service_verification",
    "import_quality",
    "integration_design",
    "topology_investigation",
    "bom_scenario",
    "support_assistant",
]
AgentRunStatusValue = Literal[
    "pending", "running", "waiting_approval", "completed", "failed", "cancelled"
]


class AgentOutputBrief(BaseModel):
    """Shared explainable hierarchy rendered for every governed agent."""

    model_config = ConfigDict(strict=True, extra="forbid")

    headline: str
    finding: str
    why: str
    next_actions: list[str] = Field(default_factory=list)
    validation: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]


class AgentOutputQuality(BaseModel):
    """Auditable normalization and grounding decision for one agent answer."""

    model_config = ConfigDict(strict=True, extra="forbid")

    normalized: bool
    grounded: bool
    fallback_used: bool
    fallback_reason: Optional[str]
    evidence_completeness_pct: int = Field(ge=0, le=100)


class AgentDecisionImpact(BaseModel):
    """Deterministic impact statement for one decision alternative."""

    model_config = ConfigDict(strict=True, extra="forbid")

    technical: list[str] = Field(default_factory=list)
    commercial: list[str] = Field(default_factory=list)
    governance: list[str] = Field(default_factory=list)
    operational: list[str] = Field(default_factory=list)


class AgentDecisionAlternative(BaseModel):
    """One evidence-linked alternative that can be compared before approval."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    title: str
    summary: str
    status: Literal["ready", "review", "blocked"]
    recommended: bool
    changes: list[str] = Field(default_factory=list)
    implementation_steps: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    impact: AgentDecisionImpact
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]
    action_type: Optional[str] = None
    action_label: Optional[str] = None
    action_href: Optional[str] = None


class AgentDecisionWorkspace(BaseModel):
    """Shared decision contract rendered across all specialized agents."""

    model_config = ConfigDict(strict=True, extra="forbid")

    workspace_type: Literal["architecture", "data_quality", "commercial", "support"]
    goal: str
    current_state: str
    recommendation_basis: str
    recommended_alternative_id: Optional[str]
    alternatives: list[AgentDecisionAlternative] = Field(default_factory=list)
    outcome_metrics: list[dict[str, object]] = Field(default_factory=list)
    post_validation: list[str] = Field(default_factory=list)


class AgentDefinitionResponse(BaseModel):
    """Versioned, immutable runtime definition exposed to authorized clients."""

    model_config = ConfigDict(strict=True, extra="forbid")

    type: AgentType
    version: str
    name: str
    description: str
    location: str
    tools: list[str]
    allowed_roles: list[str]
    mutates_data: bool
    requires_project: bool


class AgentProviderStatusResponse(BaseModel):
    """Non-secret OCI provider and Docker runtime readiness."""

    model_config = ConfigDict(strict=True, extra="forbid")

    provider: Literal["oci_genai"] = "oci_genai"
    model: str
    region: str
    endpoint: str
    api_key_configured: bool
    project_configured: bool
    function_calling_available: bool
    transport_strategy: str
    responses_capability: str
    guardrails_enabled: bool
    guardrails_version: str
    max_retries: int
    runtime: Literal["docker_celery_agents_queue"] = "docker_celery_agents_queue"
    status_message: str


class AgentProviderMetricCounters(BaseModel):
    """Fixed-cardinality OCI provider counters with no identity dimensions."""

    model_config = ConfigDict(strict=True, extra="forbid")

    requests_total: int
    successful_requests_total: int
    retries_total: int
    http_429_total: int
    http_5xx_total: int
    transport_errors_total: int
    guardrail_blocks_total: int
    guardrail_failures_total: int
    responses_fallbacks_total: int
    provider_degradations_total: int


class AgentProviderMetricsResponse(BaseModel):
    """Aggregated operational telemetry shared by API and agent workers."""

    model_config = ConfigDict(strict=True, extra="forbid")

    source: Literal["redis", "process"]
    retention_seconds: int
    last_event_at: Optional[datetime]
    last_degradation_at: Optional[datetime]
    counters: AgentProviderMetricCounters


class AgentValueMetricsResponse(BaseModel):
    """Observable product-value signals from the bounded retained run window."""

    model_config = ConfigDict(strict=True, extra="forbid")

    retained_runs: int
    completed_runs: int
    quality_evaluated_runs: int
    grounded_output_runs: int
    grounding_fallback_runs: int
    high_evidence_completeness_runs: int
    recommendation_runs: int
    provider_synthesis_runs: int
    approval_decisions: int
    approved_decisions: int
    rejected_decisions: int
    proposals_created: int
    proposals_executed: int
    post_validations_completed: int
    follow_up_runs_after_approval: int
    provider_synthesis_rate_pct: float
    grounded_output_rate_pct: float
    high_evidence_completeness_rate_pct: float
    acceptance_rate_pct: Optional[float]
    approval_follow_up_rate_pct: Optional[float]
    execution_rate_pct: Optional[float]
    median_execution_seconds: Optional[float]


class AgentCreateRequest(BaseModel):
    """Bounded request for one asynchronous agent run."""

    model_config = ConfigDict(strict=True, extra="forbid")

    agent_type: AgentType
    project_id: Optional[str] = None
    integration_id: Optional[str] = None
    context: dict[str, object] = Field(default_factory=dict)
    message: Optional[str] = Field(default=None, max_length=2000)
    include_provider: bool = True


class AgentStepResponse(BaseModel):
    """Sanitized execution step for progress and diagnostics."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    sequence: int
    step_type: str
    tool_name: Optional[str]
    status: str
    output_summary: Optional[str]
    opc_request_id: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class AgentApprovalResponse(BaseModel):
    """Human approval state for one proposed mutation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    action_type: str
    status: str
    proposed_payload: dict[str, object]
    reviewed_by: Optional[str]
    review_note: Optional[str]
    reviewed_at: Optional[datetime]
    execution_status: Literal["not_started", "running", "completed", "failed"]
    execution_result: Optional[dict[str, object]]
    executed_at: Optional[datetime]


class AgentApprovalDecisionRequest(BaseModel):
    """Explicit human decision for an agent proposal."""

    model_config = ConfigDict(strict=True, extra="forbid")

    decision: Literal["approved", "rejected"]
    note: Optional[str] = Field(default=None, max_length=1000)


class AgentRunResponse(BaseModel):
    """Full persisted agent execution without secrets or raw provider payloads."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    agent_type: AgentType
    definition_version: str
    project_id: Optional[str]
    integration_id: Optional[str]
    requested_by: str
    status: AgentRunStatusValue
    context: dict[str, object]
    result: Optional[dict[str, object]]
    error: Optional[dict[str, object]]
    model: Optional[str]
    provider_response_id: Optional[str]
    opc_request_id: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    step_count: int
    max_steps: int
    cancel_requested: bool
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    steps: list[AgentStepResponse] = Field(default_factory=list)
    approvals: list[AgentApprovalResponse] = Field(default_factory=list)


class AgentRunListResponse(BaseModel):
    """Recent governed agent executions."""

    model_config = ConfigDict(strict=True, extra="forbid")

    runs: list[AgentRunResponse]
    total: int


SupportAttachmentType = Literal[
    "page", "project", "integration", "catalog", "topology", "canvas", "import", "bom", "admin"
]


class SupportAttachmentRequest(BaseModel):
    """Explicit App component context supplied by the user."""

    model_config = ConfigDict(strict=True, extra="forbid")

    attachment_type: SupportAttachmentType
    label: str = Field(min_length=1, max_length=160)
    entity_id: Optional[str] = Field(default=None, max_length=64)
    href: str = Field(min_length=1, max_length=1000)
    context: dict[str, object] = Field(default_factory=dict)


class SupportMessageCreateRequest(BaseModel):
    """One bounded support question plus current and pinned context."""

    model_config = ConfigDict(strict=True, extra="forbid")

    content: str = Field(min_length=1, max_length=2000)
    route: str = Field(min_length=1, max_length=1000)
    page_title: str = Field(min_length=1, max_length=160)
    project_id: Optional[str] = None
    integration_id: Optional[str] = None
    attachments: list[SupportAttachmentRequest] = Field(default_factory=list, max_length=8)


class SupportAttachmentResponse(BaseModel):
    """Persisted component context safe to render in the assistant."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    attachment_type: SupportAttachmentType
    label: str
    entity_id: Optional[str]
    href: str
    context: dict[str, object]


class SupportMessageResponse(BaseModel):
    """Persisted support turn and its agent execution state."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    role: Literal["user", "assistant"]
    content: str
    status: Literal["pending", "completed", "failed", "refused"]
    agent_run_id: Optional[str]
    context: dict[str, object]
    citations: list[dict[str, str]]
    attachments: list[SupportAttachmentResponse]
    created_at: datetime


class SupportConversationResponse(BaseModel):
    """Session-isolated support conversation with bounded history."""

    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    title: str
    status: Literal["active", "archived"]
    messages: list[SupportMessageResponse]
    created_at: datetime
    updated_at: datetime
