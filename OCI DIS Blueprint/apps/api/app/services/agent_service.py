"""Persistence, policy, execution, and audit services for governed agent runs."""

from __future__ import annotations

from datetime import UTC, datetime
from statistics import median
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import AGENT_DEFINITIONS, AgentDefinition, get_agent_definition
from app.agents.tools import build_tool_executor
from app.core.config import get_settings
from app.models import (
    AgentApproval,
    AgentArtifact,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AiReviewJob,
    AiReviewJobStatus,
    AuditEvent,
    CatalogIntegration,
    Project,
    SupportMessage,
)
from app.schemas.agent import (
    AgentApprovalDecisionRequest,
    AgentApprovalResponse,
    AgentCreateRequest,
    AgentDefinitionResponse,
    AgentProviderMetricCounters,
    AgentProviderMetricsResponse,
    AgentProviderStatusResponse,
    AgentRunListResponse,
    AgentRunResponse,
    AgentStepResponse,
    AgentRunStatusValue,
    AgentType,
    AgentValueMetricsResponse,
)
from app.services import audit_service, support_service
from app.services.agent_decision_service import (
    build_decision_workspace,
    execute_approved_proposal,
    persist_proposals,
)
from app.services.agent_output_service import govern_agent_output
from app.services.authz import normalize_role, require_roles
from app.services.genai_client import GenAiAgentResult, run_governed_tool_agent
from app.services.genai_client import provider_status_payload
from app.services.genai_telemetry import get_genai_metrics
from app.services.serializers import sanitize_for_json


TERMINAL_STATUSES = {
    AgentRunStatus.COMPLETED,
    AgentRunStatus.FAILED,
    AgentRunStatus.CANCELLED,
}
AGENT_RUN_HISTORY_LIMIT = 50


async def prune_agent_run_history(
    db: AsyncSession,
    *,
    retention_limit: int = AGENT_RUN_HISTORY_LIMIT,
) -> int:
    """Delete terminal runs beyond the global bounded execution-history window."""

    if retention_limit < 1:
        raise ValueError("Agent run retention_limit must be at least 1.")
    expired_ids = list(
        (
            await db.scalars(
                select(AgentRun.id)
                .where(AgentRun.status.in_(TERMINAL_STATUSES))
                .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
                .offset(retention_limit)
            )
        ).all()
    )
    if not expired_ids:
        return 0

    await db.execute(
        update(SupportMessage)
        .where(SupportMessage.agent_run_id.in_(expired_ids))
        .values(agent_run_id=None)
    )
    await db.execute(delete(AgentApproval).where(AgentApproval.run_id.in_(expired_ids)))
    await db.execute(delete(AgentArtifact).where(AgentArtifact.run_id.in_(expired_ids)))
    await db.execute(delete(AgentStep).where(AgentStep.run_id.in_(expired_ids)))
    await db.execute(
        delete(AuditEvent).where(
            or_(
                and_(
                    AuditEvent.entity_type == "agent_run",
                    AuditEvent.entity_id.in_(expired_ids),
                ),
                AuditEvent.correlation_id.in_(expired_ids),
            )
        )
    )
    await db.execute(delete(AgentRun).where(AgentRun.id.in_(expired_ids)))
    await db.flush()
    return len(expired_ids)


def observed_provider_status(
    result_payload: dict[str, object],
) -> Literal["completed", "failed"] | None:
    """Separate expected safety refusals from provider availability failures."""

    candidate = result_payload.get("provider_status")
    if candidate == "failed" and result_payload.get("guardrails_status") == "blocked":
        return None
    if candidate in {"completed", "failed"}:
        return cast(Literal["completed", "failed"], candidate)
    return None


def observed_provider_transport(
    result_payload: dict[str, object],
) -> Literal["responses", "chat_completions"] | None:
    """Return a persisted OCI transport observation from a completed agent run."""

    candidate = result_payload.get("provider_transport") or result_payload.get("transport")
    if candidate in {"responses", "chat_completions"}:
        return cast(Literal["responses", "chat_completions"], candidate)
    return None


def _status_value(run: AgentRun) -> str:
    return run.status.value if isinstance(run.status, AgentRunStatus) else str(run.status)


def serialize_definition(definition: AgentDefinition) -> AgentDefinitionResponse:
    """Serialize one immutable agent definition."""

    return AgentDefinitionResponse(
        type=definition.type,
        version=definition.version,
        name=definition.name,
        description=definition.description,
        location=definition.location,
        tools=list(definition.tools),
        allowed_roles=sorted(definition.allowed_roles),
        mutates_data=definition.mutates_data,
        requires_project=definition.requires_project,
    )


def list_agent_definitions(actor_role: str) -> list[AgentDefinitionResponse]:
    """Return definitions visible to the caller role."""

    role = normalize_role(actor_role)
    return [
        serialize_definition(definition)
        for definition in AGENT_DEFINITIONS.values()
        if role in definition.allowed_roles
    ]


async def get_agent_provider_status(db: AsyncSession) -> AgentProviderStatusResponse:
    """Return non-secret agent configuration and last observed runtime health."""

    settings = get_settings()
    provider = provider_status_payload(settings)
    key_configured = bool(provider["configured"])
    project_configured = bool(settings.OCI_GENAI_PROJECT_ID.strip())
    recent_runs = await db.scalars(
        select(AgentRun)
        .where(AgentRun.result_payload.is_not(None))
        .order_by(AgentRun.finished_at.desc())
        .limit(20)
    )
    last_provider_status: str | None = None
    last_provider_transport: Literal["responses", "chat_completions"] | None = None
    for recent_run in recent_runs.all():
        result_payload = recent_run.result_payload
        if not isinstance(result_payload, dict):
            continue
        candidate = observed_provider_status(cast(dict[str, object], result_payload))
        if candidate is not None:
            last_provider_status = candidate
            last_provider_transport = observed_provider_transport(
                cast(dict[str, object], result_payload)
            )
            break
    responses_capability = str(provider["transport_strategy"]["responses_capability"])  # type: ignore[index]
    if responses_capability == "unverified" and last_provider_status == "completed":
        if last_provider_transport == "responses":
            responses_capability = "available"
        elif last_provider_transport == "chat_completions":
            responses_capability = "unavailable"
    available = key_configured and project_configured and last_provider_status == "completed"
    if available:
        message = "OCI Responses-first Function Calling is verified with governed Chat fallback when Responses is unavailable; deterministic tools remain authoritative."
    elif key_configured and project_configured and last_provider_status == "failed":
        message = "OCI Responses-first Function Calling is configured, but the latest agent attempt failed; deterministic tools remain available."
    elif key_configured and project_configured:
        message = "OCI Responses-first Function Calling is configured but has not completed a verified agent run yet."
    elif not key_configured:
        message = "OCI Generative AI API key is not mounted; agents use deterministic evidence only."
    else:
        message = "OCI Generative AI Project OCID is not configured; agents use deterministic evidence only."
    return AgentProviderStatusResponse(
        model=settings.OCI_GENAI_MODEL_NAME,
        region=settings.OCI_GENAI_REGION,
        endpoint=settings.OCI_GENAI_BASE_URL,
        api_key_configured=key_configured,
        project_configured=project_configured,
        function_calling_available=available,
        transport_strategy=str(provider["transport"]),
        responses_capability=responses_capability,
        guardrails_enabled=bool(provider["safety"]["guardrails_enabled"]),  # type: ignore[index]
        guardrails_version=str(provider["safety"]["guardrails_version"]),  # type: ignore[index]
        max_retries=int(provider["retry_policy"]["max_retries"]),  # type: ignore[index]
        status_message=message,
    )


async def get_agent_provider_metrics() -> AgentProviderMetricsResponse:
    """Return privacy-safe provider counters aggregated through Redis."""

    payload = await get_genai_metrics(get_settings())
    counters = cast(dict[str, int], payload["counters"])
    last_event_value = payload["last_event_at"]
    last_degradation_value = payload["last_degradation_at"]
    return AgentProviderMetricsResponse(
        source=cast(Literal["redis", "process"], payload["source"]),
        retention_seconds=cast(int, payload["retention_seconds"]),
        last_event_at=(
            datetime.fromisoformat(last_event_value)
            if isinstance(last_event_value, str)
            else None
        ),
        last_degradation_at=(
            datetime.fromisoformat(last_degradation_value)
            if isinstance(last_degradation_value, str)
            else None
        ),
        counters=AgentProviderMetricCounters(**counters),
    )


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 1) if denominator else 0.0


async def get_agent_value_metrics(db: AsyncSession) -> AgentValueMetricsResponse:
    """Compute honest value signals from the bounded retained execution window."""

    runs = list(
        (
            await db.scalars(
                select(AgentRun)
                .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
                .limit(AGENT_RUN_HISTORY_LIMIT)
            )
        ).all()
    )
    run_ids = [run.id for run in runs]
    approvals = (
        list(
            (
                await db.scalars(
                    select(AgentApproval)
                    .where(
                        AgentApproval.run_id.in_(run_ids),
                        AgentApproval.status.in_({"approved", "rejected"}),
                    )
                    .order_by(AgentApproval.reviewed_at)
                )
            ).all()
        )
        if run_ids
        else []
    )
    completed = [run for run in runs if run.status == AgentRunStatus.COMPLETED]
    quality_payloads: list[dict[str, object]] = []
    recommendation_runs = 0
    provider_synthesis_runs = 0
    durations: list[float] = []
    for run in completed:
        payload = cast(dict[str, object], run.result_payload or {})
        quality = payload.get("output_quality")
        if isinstance(quality, dict):
            quality_payloads.append(cast(dict[str, object], quality))
        brief = payload.get("brief")
        if isinstance(brief, dict) and isinstance(brief.get("next_actions"), list) and brief["next_actions"]:
            recommendation_runs += 1
        if payload.get("provider_status") == "completed":
            provider_synthesis_runs += 1
        if run.started_at is not None and run.finished_at is not None:
            durations.append(max((run.finished_at - run.started_at).total_seconds(), 0.0))

    grounded_output_runs = sum(item.get("grounded") is True for item in quality_payloads)
    grounding_fallback_runs = sum(item.get("fallback_used") is True for item in quality_payloads)
    high_evidence_runs = sum(
        isinstance(item.get("evidence_completeness_pct"), int)
        and cast(int, item["evidence_completeness_pct"]) >= 80
        for item in quality_payloads
    )
    approved = [approval for approval in approvals if approval.status == "approved"]
    rejected = [approval for approval in approvals if approval.status == "rejected"]
    proposals = (
        list(
            (
                await db.scalars(
                    select(AgentApproval).where(AgentApproval.run_id.in_(run_ids))
                )
            ).all()
        )
        if run_ids
        else []
    )
    executed = [approval for approval in proposals if approval.execution_status == "completed"]
    runs_by_id = {run.id: run for run in runs}
    follow_up_runs = 0
    for approval in approved:
        source_run = runs_by_id.get(approval.run_id)
        decision_at = approval.reviewed_at
        if source_run is None or decision_at is None:
            continue
        if any(
            candidate.created_at > decision_at
            and candidate.agent_type == source_run.agent_type
            and candidate.project_id == source_run.project_id
            for candidate in runs
        ):
            follow_up_runs += 1

    return AgentValueMetricsResponse(
        retained_runs=len(runs),
        completed_runs=len(completed),
        quality_evaluated_runs=len(quality_payloads),
        grounded_output_runs=grounded_output_runs,
        grounding_fallback_runs=grounding_fallback_runs,
        high_evidence_completeness_runs=high_evidence_runs,
        recommendation_runs=recommendation_runs,
        provider_synthesis_runs=provider_synthesis_runs,
        approval_decisions=len(approvals),
        approved_decisions=len(approved),
        rejected_decisions=len(rejected),
        proposals_created=len(proposals),
        proposals_executed=len(executed),
        post_validations_completed=sum(
            isinstance(approval.execution_result, dict)
            and bool(approval.execution_result.get("validation"))
            for approval in executed
        ),
        follow_up_runs_after_approval=follow_up_runs,
        provider_synthesis_rate_pct=_rate(provider_synthesis_runs, len(completed)),
        grounded_output_rate_pct=_rate(grounded_output_runs, len(quality_payloads)),
        high_evidence_completeness_rate_pct=_rate(high_evidence_runs, len(quality_payloads)),
        acceptance_rate_pct=_rate(len(approved), len(approvals)) if approvals else None,
        approval_follow_up_rate_pct=_rate(follow_up_runs, len(approved)) if approved else None,
        execution_rate_pct=_rate(len(executed), len(approved)) if approved else None,
        median_execution_seconds=round(float(median(durations)), 1) if durations else None,
    )


async def _load_run(run_id: str, db: AsyncSession) -> AgentRun:
    run = await db.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Agent run not found", "error_code": "AGENT_RUN_NOT_FOUND"},
        )
    return run


def _step_summary(step: AgentStep) -> str | None:
    payload = step.output_payload
    if not isinstance(payload, dict):
        return None
    summary = payload.get("summary")
    if isinstance(summary, str):
        return summary[:500]
    return None


def _provider_diagnostic_summary(*, provider_status: str, fallback_used: bool) -> str:
    """Return a bounded operational status without persisting model prose."""

    if provider_status != "completed":
        return "Provider synthesis was unavailable; governed deterministic evidence was used."
    if fallback_used:
        return "Provider synthesis completed but did not pass the output contract; governed deterministic evidence was used."
    return "Provider synthesis completed and passed the governed output contract."


async def serialize_agent_run(run: AgentRun, db: AsyncSession, *, compact: bool = False) -> AgentRunResponse:
    """Serialize one run with sanitized progress, steps, and approvals."""

    steps = list(
        (
            await db.scalars(
                select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.sequence)
            )
        ).all()
    )
    approvals = list(
        (
            await db.scalars(
                select(AgentApproval).where(AgentApproval.run_id == run.id).order_by(AgentApproval.created_at)
            )
        ).all()
    )
    result_payload = cast(dict[str, object] | None, run.result_payload)
    if compact and result_payload is not None:
        legacy_summary = (
            "Legacy execution predates the governed output contract; inspect its audit evidence if needed."
            if not isinstance(result_payload.get("output_quality"), dict)
            else result_payload.get("summary")
        )
        result_payload = {
            key: result_payload[key]
            for key in ("provider_status", "authority", "tool", "output_quality")
            if key in result_payload
        }
        if isinstance(legacy_summary, str):
            result_payload["summary"] = legacy_summary
    return AgentRunResponse(
        id=run.id,
        agent_type=cast(AgentType, run.agent_type),
        definition_version=run.definition_version,
        project_id=run.project_id,
        integration_id=run.integration_id,
        requested_by=run.requested_by,
        status=cast(AgentRunStatusValue, _status_value(run)),
        context=cast(dict[str, object], run.context_payload),
        result=result_payload,
        error=cast(dict[str, object] | None, run.error_details),
        model=run.model_name,
        provider_response_id=run.provider_response_id,
        opc_request_id=run.opc_request_id,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        step_count=run.step_count,
        max_steps=run.max_steps,
        cancel_requested=run.cancel_requested,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        steps=[
            AgentStepResponse(
                id=step.id, sequence=step.sequence, step_type=step.step_type,
                tool_name=step.tool_name, status=step.status,
                output_summary=_step_summary(step), opc_request_id=step.opc_request_id,
                started_at=step.started_at, finished_at=step.finished_at,
            )
            for step in steps
        ],
        approvals=[
            AgentApprovalResponse(
                id=approval.id, action_type=approval.action_type, status=approval.status,
                proposed_payload=cast(dict[str, object], approval.proposed_payload),
                reviewed_by=approval.reviewed_by, review_note=approval.review_note,
                reviewed_at=approval.reviewed_at,
                execution_status=cast(
                    Literal["not_started", "running", "completed", "failed"],
                    approval.execution_status,
                ),
                execution_result=cast(dict[str, object] | None, approval.execution_result),
                executed_at=approval.executed_at,
            )
            for approval in approvals
        ],
    )


async def create_agent_run(
    request: AgentCreateRequest,
    actor_id: str,
    actor_role: str,
    db: AsyncSession,
) -> AgentRunResponse:
    """Validate policy and persist one pending agent run."""

    definition = get_agent_definition(request.agent_type)
    require_roles(actor_role, definition.allowed_roles, error_code="AGENT_RUN_ROLE_REQUIRED")
    if definition.requires_project and request.project_id is None:
        raise HTTPException(status_code=422, detail={"detail": "project_id is required", "error_code": "AGENT_PROJECT_REQUIRED"})
    if request.project_id is not None and await db.get(Project, request.project_id) is None:
        raise HTTPException(status_code=404, detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"})
    if request.integration_id is not None:
        integration = await db.get(CatalogIntegration, request.integration_id)
        if integration is None or integration.project_id != request.project_id:
            raise HTTPException(status_code=404, detail={"detail": "Integration not found", "error_code": "INTEGRATION_NOT_FOUND"})
    context = cast(dict[str, object], sanitize_for_json(request.context))
    context["include_provider"] = request.include_provider
    if request.message:
        context["message"] = request.message
    run = AgentRun(
        agent_type=definition.type,
        definition_version=definition.version,
        project_id=request.project_id,
        integration_id=request.integration_id,
        requested_by=actor_id or "api-user",
        context_payload=context,
        max_steps=min(max(get_settings().OCI_GENAI_AGENT_MAX_STEPS, 2), 8),
    )
    db.add(run)
    await db.flush()
    await db.refresh(run)
    await audit_service.emit(
        event_type="agent_run_created", entity_type="agent_run", entity_id=run.id,
        actor_id=run.requested_by, old_value=None,
        new_value={"agent_type": run.agent_type, "status": _status_value(run)},
        project_id=run.project_id, correlation_id=run.id, db=db,
    )
    return await serialize_agent_run(run, db)


async def link_agent_run(
    run_id: str,
    *,
    legacy_job_type: str,
    legacy_job_id: str,
    db: AsyncSession,
) -> AgentRunResponse:
    """Link a new agent run to a compatibility job presented by an existing workflow."""

    run = await _load_run(run_id, db)
    run.legacy_job_type = legacy_job_type
    run.legacy_job_id = legacy_job_id
    await db.flush()
    return await serialize_agent_run(run, db)


async def list_agent_runs(
    db: AsyncSession,
    *,
    actor_role: str,
    project_id: str | None = None,
    limit: int = 20,
) -> AgentRunListResponse:
    """Return recent runs visible to the caller role."""

    visible_types = [item.type for item in list_agent_definitions(actor_role)]
    query = select(AgentRun).where(AgentRun.agent_type.in_(visible_types))
    count_query = select(func.count()).select_from(AgentRun).where(AgentRun.agent_type.in_(visible_types))
    if project_id is not None:
        query = query.where(AgentRun.project_id == project_id)
        count_query = count_query.where(AgentRun.project_id == project_id)
    effective_limit = min(limit, AGENT_RUN_HISTORY_LIMIT)
    runs = list((await db.scalars(query.order_by(AgentRun.created_at.desc()).limit(effective_limit))).all())
    return AgentRunListResponse(
        runs=[await serialize_agent_run(run, db, compact=True) for run in runs],
        total=int(await db.scalar(count_query) or 0),
    )


async def get_agent_run(run_id: str, actor_role: str, db: AsyncSession) -> AgentRunResponse:
    """Return one run after definition-level authorization."""

    run = await _load_run(run_id, db)
    definition = get_agent_definition(cast(AgentType, run.agent_type))
    require_roles(actor_role, definition.allowed_roles | {"Viewer"}, error_code="AGENT_RUN_READ_ROLE_REQUIRED")
    return await serialize_agent_run(run, db)


async def mark_agent_run_running(run_id: str, db: AsyncSession) -> AgentRun:
    """Move a pending run into active execution."""

    run = await _load_run(run_id, db)
    if run.cancel_requested:
        run.status = AgentRunStatus.CANCELLED
        run.finished_at = datetime.now(UTC)
        await db.flush()
        return run
    if run.status != AgentRunStatus.PENDING:
        return run
    run.status = AgentRunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    if run.legacy_job_type == "ai_review" and run.legacy_job_id:
        legacy_job = await db.get(AiReviewJob, run.legacy_job_id)
        if legacy_job is not None:
            legacy_job.status = AiReviewJobStatus.RUNNING
            legacy_job.started_at = run.started_at
            legacy_job.finished_at = None
            legacy_job.error_details = None
    await db.flush()
    return run


async def run_agent(run_id: str, db: AsyncSession) -> AgentRunResponse:
    """Execute evidence, decision, provider, and proposal stages."""

    run = await _load_run(run_id, db)
    if run.status in TERMINAL_STATUSES:
        return await serialize_agent_run(run, db)
    definition = get_agent_definition(cast(AgentType, run.agent_type))
    context = cast(dict[str, object], run.context_payload)
    tool_name, description, parameters, executor = build_tool_executor(
        agent_type=definition.type, project_id=run.project_id,
        integration_id=run.integration_id, context=context,
        actor_id=run.requested_by, db=db,
    )
    include_provider = context.get("include_provider") is not False
    result: GenAiAgentResult | None = None
    evidence_started_at = datetime.now(UTC)
    preflight_evidence = await executor({})
    if definition.type == "support_assistant" and preflight_evidence.get("in_scope") is False:
        include_provider = False
    tool_step = AgentStep(
        run_id=run.id,
        sequence=1,
        step_type="evidence",
        tool_name=tool_name,
        status="completed",
        started_at=evidence_started_at,
        finished_at=datetime.now(UTC),
        input_payload={"arguments": "validated"},
        output_payload={"summary": f"Governed evidence collected by {tool_name}."},
    )
    db.add(tool_step)

    async def cached_executor(_: dict[str, object]) -> dict[str, object]:
        return preflight_evidence

    provider_step = AgentStep(
        run_id=run.id, sequence=3, step_type="provider", tool_name=tool_name,
        status="running", started_at=datetime.now(UTC), input_payload={"tool": tool_name},
    )
    db.add(provider_step)
    await db.flush()
    if include_provider:
        result = await run_governed_tool_agent(
            settings=get_settings(), instruction=definition.instruction,
            user_message=str(context.get("message") or f"Run {definition.name} for the governed scope."),
            tool_name=tool_name, tool_description=description,
            tool_parameters=parameters, tool_executor=cached_executor,
            safety_subject=run.requested_by,
        )
    evidence = (
        result.tool_output
        if result and result.tool_output is not None
        else preflight_evidence
    )
    safety_refused = bool(result and result.error == "input_guardrails_blocked")
    provider_step.status = (
        "policy_refused"
        if definition.type == "support_assistant" and (evidence.get("in_scope") is False or safety_refused)
        else "completed"
        if result and result.status == "completed"
        else "fallback"
    )
    provider_step.output_payload = {
        "summary": "Provider output is pending governed normalization.",
        "provider_status": result.status if result else "skipped",
        "transport": result.transport if result else None,
        "retry_count": result.retry_count if result else 0,
        "guardrails_status": result.guardrails_status if result else "skipped",
    }
    provider_step.opc_request_id = result.opc_request_id if result else None
    provider_step.finished_at = datetime.now(UTC)
    artifact = AgentArtifact(
        run_id=run.id, artifact_type="governed_evidence", label=f"{definition.name} evidence",
        payload=cast(dict[str, object], sanitize_for_json(evidence)),
    )
    db.add(artifact)
    direct_answer = evidence.get("direct_answer")
    summary = (
        "I could not process that request because OCI safety controls detected unsafe or manipulative instructions."
        if definition.type == "support_assistant" and safety_refused
        else str(direct_answer)
        if definition.type == "support_assistant" and isinstance(direct_answer, str)
        else result.summary
        if result and result.summary
        else _deterministic_summary(definition, evidence)
    )
    grounding_fallback = False
    if (
        definition.type == "support_assistant"
        and evidence.get("in_scope") is not False
        and not safety_refused
        and not support_service.support_summary_is_grounded(summary, evidence)
    ):
        summary = str(evidence.get("fallback_answer") or _deterministic_summary(definition, evidence))
        grounding_fallback = True
    governed_output = govern_agent_output(definition, summary, evidence)
    if grounding_fallback and not governed_output.quality.fallback_used:
        governed_output.quality.fallback_used = True
        governed_output.quality.grounded = False
        governed_output.quality.fallback_reason = "support_grounding_gate"
    summary = governed_output.summary
    grounding_fallback = governed_output.quality.fallback_used
    decision_workspace, proposal_specs = build_decision_workspace(
        definition,
        evidence,
        project_id=run.project_id,
        integration_id=run.integration_id,
    )
    decision_step = AgentStep(
        run_id=run.id,
        sequence=2,
        step_type="decision",
        tool_name="build_decision_workspace",
        status="completed",
        started_at=tool_step.finished_at,
        finished_at=datetime.now(UTC),
        input_payload={"evidence": "governed"},
        output_payload={
            "summary": f"Compared {len(decision_workspace.alternatives)} governed alternative(s).",
            "recommended_alternative_id": decision_workspace.recommended_alternative_id,
        },
    )
    db.add(decision_step)
    approvals = await persist_proposals(run, proposal_specs, db)
    proposal_step = AgentStep(
        run_id=run.id,
        sequence=4,
        step_type="proposal",
        tool_name="prepare_governed_proposals",
        status="completed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        input_payload={"recommended_alternative_id": decision_workspace.recommended_alternative_id},
        output_payload={"summary": f"Prepared {len(approvals)} approval-gated proposal(s)."},
    )
    db.add(proposal_step)
    provider_step.output_payload["summary"] = _provider_diagnostic_summary(
        provider_status=result.status if result else "skipped",
        fallback_used=grounding_fallback,
    )
    provider_step.output_payload["grounding_fallback"] = grounding_fallback
    provider_step.output_payload["output_quality"] = governed_output.quality.model_dump(mode="json")
    provider_status = result.status if result else "skipped"
    if definition.type == "support_assistant":
        message_id = context.get("support_assistant_message_id")
        citations_value = evidence.get("citations")
        citations = (
            [
                {"label": str(item.get("label") or "App context"), "href": str(item.get("href") or "/projects")}
                for item in citations_value
                if isinstance(item, dict)
            ]
            if isinstance(citations_value, list)
            else []
        )
        if isinstance(message_id, str):
            await support_service.complete_support_message(
                message_id,
                content=summary,
                status="refused" if evidence.get("in_scope") is False or safety_refused else "completed",
                citations=citations,
                db=db,
            )
    if run.legacy_job_type == "ai_review" and run.legacy_job_id:
        legacy_job = await db.get(AiReviewJob, run.legacy_job_id)
        if legacy_job is not None:
            legacy_evidence = dict(evidence)
            legacy_evidence["llm_status"] = provider_status
            legacy_evidence["llm_model"] = result.model if result else None
            legacy_evidence["llm_summary"] = summary if result else None
            legacy_job.result_payload = cast(dict[str, object], sanitize_for_json(legacy_evidence))
            legacy_job.status = AiReviewJobStatus.COMPLETED
            legacy_job.finished_at = datetime.now(UTC)
            await audit_service.emit(
                event_type="ai_review_job_completed",
                entity_type="ai_review_job",
                entity_id=legacy_job.id,
                actor_id=legacy_job.requested_by,
                old_value={"status": "running"},
                new_value={"status": "completed", "agent_run_id": run.id},
                project_id=legacy_job.project_id,
                correlation_id=legacy_job.id,
                db=db,
            )
    run.result_payload = {
        "summary": summary,
        "provider_status": provider_status,
        "provider_error": result.error if result else None,
        "provider_transport": result.transport if result else None,
        "provider_retry_count": result.retry_count if result else 0,
        "guardrails_status": result.guardrails_status if result else "skipped",
        "grounding_fallback": grounding_fallback,
        "brief": governed_output.brief.model_dump(mode="json"),
        "decision_workspace": decision_workspace.model_dump(mode="json"),
        "output_quality": governed_output.quality.model_dump(mode="json"),
        "tool": tool_name,
        "evidence": sanitize_for_json(evidence),
        "authority": "governed_deterministic_evidence",
    }
    run.model_name = result.model if result else None
    run.provider_response_id = result.response_id if result else None
    run.opc_request_id = result.opc_request_id if result else None
    run.input_tokens = result.input_tokens if result else None
    run.output_tokens = result.output_tokens if result else None
    run.step_count = 4
    run.status = AgentRunStatus.CANCELLED if run.cancel_requested else AgentRunStatus.COMPLETED
    run.finished_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(run)
    await audit_service.emit(
        event_type="agent_run_completed", entity_type="agent_run", entity_id=run.id,
        actor_id=run.requested_by, old_value={"status": "running"},
        new_value={"status": _status_value(run), "tool": tool_name, "provider_status": run.result_payload["provider_status"]},
        project_id=run.project_id, correlation_id=run.id, db=db,
    )
    response = await serialize_agent_run(run, db)
    await prune_agent_run_history(db)
    return response


def _deterministic_summary(definition: AgentDefinition, evidence: dict[str, object]) -> str:
    """Return an honest fallback summary when provider synthesis is unavailable."""

    if definition.type == "import_quality":
        return str(evidence.get("recommended_next_action") or "Import evidence is ready for analyst review.")
    if definition.type == "bom_scenario":
        current_bom = evidence.get("current_bom")
        if isinstance(current_bom, dict) and current_bom.get("ready_for_use") is True:
            return (
                "The published BOM is current, fully covered, and ready for governed use; "
                "regenerate it only after an approved input changes."
            )
        questions = evidence.get("required_questions")
        count = len(questions) if isinstance(questions, list) else 0
        return f"Governed BOM scenario evidence is ready; {count} client input question(s) remain."
    if definition.type == "service_verification":
        return f"Official-source verification completed with {evidence.get('changes_detected', 0)} detected change(s)."
    if definition.type == "support_assistant":
        if evidence.get("in_scope") is False:
            return str(evidence.get("refusal") or "This question is outside OCI DIS Architect support scope.")
        return str(evidence.get("fallback_answer") or "Governed App context is ready for review.")
    brief = evidence.get("decision_brief")
    if isinstance(brief, dict) and isinstance(brief.get("headline"), str):
        return str(brief["headline"])
    return f"{definition.name} completed with governed deterministic evidence."


async def mark_agent_run_failed(run_id: str, error: dict[str, object], db: AsyncSession) -> AgentRunResponse:
    """Persist a redacted terminal failure."""

    run = await _load_run(run_id, db)
    run.status = AgentRunStatus.FAILED
    run.error_details = cast(dict[str, object], sanitize_for_json(error))
    run.finished_at = datetime.now(UTC)
    if run.legacy_job_type == "ai_review" and run.legacy_job_id:
        legacy_job = await db.get(AiReviewJob, run.legacy_job_id)
        if legacy_job is not None:
            legacy_job.status = AiReviewJobStatus.FAILED
            legacy_job.error_details = run.error_details
            legacy_job.finished_at = run.finished_at
    message_id = cast(dict[str, object], run.context_payload).get("support_assistant_message_id")
    if run.agent_type == "support_assistant" and isinstance(message_id, str):
        await support_service.fail_support_message(message_id, db)
    await db.flush()
    response = await serialize_agent_run(run, db)
    await prune_agent_run_history(db)
    return response


async def request_agent_cancellation(run_id: str, actor_id: str, actor_role: str, db: AsyncSession) -> AgentRunResponse:
    """Request cancellation without killing unrelated worker tasks."""

    run = await _load_run(run_id, db)
    definition = get_agent_definition(cast(AgentType, run.agent_type))
    require_roles(actor_role, definition.allowed_roles, error_code="AGENT_CANCEL_ROLE_REQUIRED")
    run.cancel_requested = True
    if run.status == AgentRunStatus.PENDING:
        run.status = AgentRunStatus.CANCELLED
        run.finished_at = datetime.now(UTC)
    await db.flush()
    await audit_service.emit(
        event_type="agent_run_cancellation_requested", entity_type="agent_run", entity_id=run.id,
        actor_id=actor_id, old_value=None, new_value={"status": _status_value(run)},
        project_id=run.project_id, correlation_id=run.id, db=db,
    )
    response = await serialize_agent_run(run, db)
    if run.status in TERMINAL_STATUSES:
        await prune_agent_run_history(db)
    return response


async def decide_agent_approval(
    run_id: str, approval_id: str, request: AgentApprovalDecisionRequest,
    actor_id: str, actor_role: str, db: AsyncSession,
) -> AgentRunResponse:
    """Record a human decision; execution remains delegated to a deterministic endpoint."""

    require_roles(actor_role, {"Admin", "Architect"}, error_code="AGENT_APPROVAL_ROLE_REQUIRED")
    run = await _load_run(run_id, db)
    approval = await db.get(AgentApproval, approval_id)
    if approval is None or approval.run_id != run.id:
        raise HTTPException(status_code=404, detail={"detail": "Approval not found", "error_code": "AGENT_APPROVAL_NOT_FOUND"})
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail={"detail": "Approval already decided", "error_code": "AGENT_APPROVAL_ALREADY_DECIDED"})
    approval.status = request.decision
    approval.reviewed_by = actor_id
    approval.review_note = request.note
    approval.reviewed_at = datetime.now(UTC)
    await db.flush()
    await audit_service.emit(
        event_type="agent_approval_decided", entity_type="agent_approval", entity_id=approval.id,
        actor_id=actor_id, old_value={"status": "pending"}, new_value={"status": approval.status},
        project_id=run.project_id, correlation_id=run.id, db=db,
    )
    return await serialize_agent_run(run, db)


async def execute_agent_approval(
    run_id: str,
    approval_id: str,
    actor_id: str,
    actor_role: str,
    db: AsyncSession,
) -> AgentRunResponse:
    """Execute an approved deterministic proposal and persist post-validation."""

    require_roles(actor_role, {"Admin", "Architect"}, error_code="AGENT_EXECUTION_ROLE_REQUIRED")
    run = await _load_run(run_id, db)
    approval = await db.get(AgentApproval, approval_id)
    if approval is None or approval.run_id != run.id:
        raise HTTPException(status_code=404, detail={"detail": "Approval not found", "error_code": "AGENT_APPROVAL_NOT_FOUND"})
    old_status = approval.execution_status
    result = await execute_approved_proposal(run, approval, actor_id=actor_id, db=db)
    await audit_service.emit(
        event_type="agent_proposal_executed",
        entity_type="agent_approval",
        entity_id=approval.id,
        actor_id=actor_id,
        old_value={"execution_status": old_status},
        new_value={"execution_status": approval.execution_status, "result": result},
        project_id=run.project_id,
        correlation_id=run.id,
        db=db,
    )
    return await serialize_agent_run(run, db)
