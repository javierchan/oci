"""Governed architecture review jobs for the Run AI Review workflow."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Iterable, Literal, Optional, cast
from urllib.parse import quote_plus

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    AiReviewJob,
    CatalogIntegration,
    DashboardSnapshot,
    Project,
    VolumetrySnapshot,
)
from app.schemas.ai_review import (
    AiReviewAcceptRecommendationRequest,
    AiReviewApplyPatchRequest,
    AiReviewApplyPatchResponse,
    AiReviewCategory,
    AiReviewCreateRequest,
    AiReviewEvidence,
    AiReviewFieldDiff,
    AiReviewFinding,
    AiReviewGraphContext,
    AiReviewGroup,
    AiReviewJobListResponse,
    AiReviewJobResponse,
    AiReviewMetric,
    AiReviewPersonaSummary,
    AiReviewRecommendationAcceptance,
    AiReviewResponse,
    AiReviewSeverity,
    AiReviewSuggestedPatch,
)
from app.schemas.catalog import CatalogIntegrationPatch
from app.services import audit_service, catalog_service
from app.services.llm_review_client import LlmReviewResult, synthesize_review_summary
from app.services.pattern_support import get_pattern_support
from app.services.serializers import sanitize_for_json

MAX_LINKED_INTEGRATIONS = 8
AI_REVIEW_ACTOR_FALLBACK = "api-user"

SEVERITY_RANK: dict[AiReviewSeverity, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "positive": 0,
}

GROUP_META: dict[AiReviewCategory, tuple[str, str]] = {
    "critical_blockers": (
        "Critical blockers",
        "Issues that make the review unreliable until fixed.",
    ),
    "high_confidence_fixes": (
        "High-confidence fixes",
        "Concrete work that can be started without a broad architecture debate.",
    ),
    "needs_architect_decision": (
        "Needs architect decision",
        "Design, compatibility, or governance calls that should be decided by an architect.",
    ),
    "looks_production_ready": (
        "Looks production-ready",
        "Signals that are currently clean or ready to present.",
    ),
}


def _has_text(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def _pct(complete: int, total: int) -> int:
    return round((complete / total) * 100) if total else 0


def _format_percent(complete: int, total: int) -> str:
    return f"{_pct(complete, total)}%"


def _display_name(row: CatalogIntegration) -> str:
    return row.interface_name or row.interface_id or f"Integration {row.seq_number}"


def _first_ids(rows: Iterable[CatalogIntegration]) -> list[str]:
    return [row.id for row in list(rows)[:MAX_LINKED_INTEGRATIONS]]


def _catalog_href(project_id: str, params: str = "") -> str:
    suffix = f"?{params}" if params else ""
    return f"/projects/{project_id}/catalog{suffix}"


def _graph_context_detail(graph_context: AiReviewGraphContext | None) -> str:
    if graph_context is None:
        return "Full project scope."
    if graph_context.type == "node":
        return f"Graph node scope: {graph_context.label or 'unnamed system'}."
    return f"Graph edge scope: {graph_context.source or 'unknown source'} -> {graph_context.target or 'unknown target'}."


def _catalog_href_for_context(project_id: str, graph_context: AiReviewGraphContext | None) -> str:
    if graph_context is None:
        return _catalog_href(project_id)
    if graph_context.type == "node" and graph_context.label:
        return _catalog_href(project_id, f"system={quote_plus(graph_context.label)}")
    if graph_context.type == "edge" and graph_context.source and graph_context.target:
        return _catalog_href(
            project_id,
            f"source_system={quote_plus(graph_context.source)}&destination_system={quote_plus(graph_context.target)}",
        )
    return _catalog_href(project_id)


def _integration_href(project_id: str, integration_id: str) -> str:
    return f"/projects/{project_id}/catalog/{integration_id}"


def _rows_for_graph_context(
    rows: list[CatalogIntegration],
    graph_context: AiReviewGraphContext | None,
) -> list[CatalogIntegration]:
    if graph_context is None:
        return rows
    if graph_context.type == "node" and graph_context.label:
        return [
            row
            for row in rows
            if row.source_system == graph_context.label or row.destination_system == graph_context.label
        ]
    if graph_context.type == "edge" and graph_context.source and graph_context.target:
        return [
            row
            for row in rows
            if row.source_system == graph_context.source and row.destination_system == graph_context.target
        ]
    return rows


def _with_review_note(existing: str | None, finding: AiReviewFinding) -> str:
    marker = f"AI Review finding {finding.id}"
    note = (
        f"{marker}: {finding.recommendation} "
        f"Current: {finding.current_state} Recommended: {finding.recommended_state}"
    )
    if existing and marker in existing:
        return existing
    return f"{existing.rstrip()}\n\n{note}" if existing and existing.strip() else note


def _suggested_patch_for_finding(
    finding: AiReviewFinding,
    rows_by_id: dict[str, CatalogIntegration],
) -> AiReviewSuggestedPatch | None:
    if finding.severity == "positive" or len(finding.integration_ids) != 1:
        return None
    row = rows_by_id.get(finding.integration_ids[0])
    if row is None:
        return None
    recommended_comments = _with_review_note(row.comments, finding)
    if recommended_comments == (row.comments or ""):
        return None
    return AiReviewSuggestedPatch(
        integration_id=row.id,
        label="Apply governance note",
        description=(
            "Adds the human-approved recommendation to the architect-owned comments field. "
            "It does not alter source lineage, patterns, service selections, or payload values."
        ),
        patch={"comments": recommended_comments},
        field_diffs=[
            AiReviewFieldDiff(
                field="comments",
                current=row.comments,
                recommended=recommended_comments,
            )
        ],
        safe_to_apply=True,
        safety_note="Bounded to the architect-owned comments field and still emitted through catalog audit.",
    )


def _with_suggested_patches(
    findings: list[AiReviewFinding],
    rows: list[CatalogIntegration],
) -> list[AiReviewFinding]:
    rows_by_id = {row.id: row for row in rows}
    return [
        finding.model_copy(update={"suggested_patch": _suggested_patch_for_finding(finding, rows_by_id)})
        for finding in findings
    ]


def _validate_graph_context(graph_context: AiReviewGraphContext | None) -> None:
    if graph_context is None:
        return
    if graph_context.type == "node" and not _has_text(graph_context.label):
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "graph_context.label is required for node-scoped reviews.",
                "error_code": "AI_REVIEW_GRAPH_NODE_REQUIRES_LABEL",
            },
        )
    if graph_context.type == "edge" and (not _has_text(graph_context.source) or not _has_text(graph_context.target)):
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "graph_context.source and graph_context.target are required for edge-scoped reviews.",
                "error_code": "AI_REVIEW_GRAPH_EDGE_REQUIRES_SOURCE_TARGET",
            },
        )


def _status_value(job: AiReviewJob) -> Literal["pending", "running", "completed", "failed"]:
    value = job.status.value if hasattr(job.status, "value") else str(job.status)
    return cast(Literal["pending", "running", "completed", "failed"], value)


def _finding_category(severity: AiReviewSeverity, review_area: str) -> AiReviewCategory:
    if severity == "critical":
        return "critical_blockers"
    if severity == "positive":
        return "looks_production_ready"
    if review_area in {"data_quality", "snapshot_freshness"}:
        return "high_confidence_fixes"
    return "needs_architect_decision"


def _finding(
    finding_id: str,
    severity: AiReviewSeverity,
    review_area: Literal[
        "data_quality",
        "snapshot_freshness",
        "canvas_consistency",
        "oci_compatibility",
        "stress_review",
        "demo_readiness",
        "red_team",
        "governance",
    ],
    title: str,
    summary: str,
    evidence_ids: list[str],
    evidence: list[str],
    current_state: str,
    recommended_state: str,
    recommendation: str,
    action_label: str,
    action_href: str | None = None,
    integration_ids: list[str] | None = None,
) -> AiReviewFinding:
    return AiReviewFinding(
        id=finding_id,
        severity=severity,
        category=_finding_category(severity, review_area),
        review_area=review_area,
        title=title,
        summary=summary,
        evidence_ids=evidence_ids,
        evidence=evidence,
        current_state=current_state,
        recommended_state=recommended_state,
        recommendation=recommendation,
        action_label=action_label,
        action_href=action_href,
        integration_ids=integration_ids or [],
    )


async def _load_project(project_id: str, db: AsyncSession) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"},
        )
    return project


async def _load_integration(project_id: str, integration_id: str, db: AsyncSession) -> CatalogIntegration:
    row = await db.get(CatalogIntegration, integration_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "Integration not found for this project.",
                "error_code": "INTEGRATION_NOT_FOUND",
            },
        )
    return row


async def _load_rows(
    project_id: str,
    db: AsyncSession,
    integration_id: str | None = None,
) -> list[CatalogIntegration]:
    if integration_id:
        return [await _load_integration(project_id, integration_id, db)]
    rows = await db.scalars(
        select(CatalogIntegration)
        .where(CatalogIntegration.project_id == project_id)
        .order_by(CatalogIntegration.seq_number, CatalogIntegration.created_at)
    )
    return list(rows.all())


async def _latest_volumetry_snapshot(project_id: str, db: AsyncSession) -> VolumetrySnapshot | None:
    return await db.scalar(
        select(VolumetrySnapshot)
        .where(VolumetrySnapshot.project_id == project_id)
        .order_by(VolumetrySnapshot.created_at.desc())
        .limit(1)
    )


async def _latest_dashboard_snapshot(project_id: str, db: AsyncSession) -> DashboardSnapshot | None:
    return await db.scalar(
        select(DashboardSnapshot)
        .where(DashboardSnapshot.project_id == project_id)
        .order_by(DashboardSnapshot.created_at.desc())
        .limit(1)
    )


def _design_warning_map(
    snapshot: VolumetrySnapshot | None,
    allowed_ids: set[str] | None = None,
) -> dict[str, list[str]]:
    if snapshot is None:
        return {}

    warning_map: dict[str, list[str]] = {}
    for integration_id, metrics in (snapshot.row_results or {}).items():
        if allowed_ids is not None and integration_id not in allowed_ids:
            continue
        warnings = metrics.get("design_constraint_warnings") if isinstance(metrics, dict) else None
        if isinstance(warnings, list) and warnings:
            warning_map[integration_id] = [str(warning) for warning in warnings]
    return warning_map


def _readiness_label(score: int, critical_count: int, high_count: int) -> str:
    if critical_count > 0:
        return "Blocked"
    if high_count > 0 or score < 70:
        return "Needs architecture review"
    if score < 85:
        return "Demo-ready with caveats"
    return "Ready for executive demo"


def _score(findings: list[AiReviewFinding]) -> int:
    deductions = {
        "critical": 35,
        "high": 18,
        "medium": 9,
        "low": 3,
        "positive": -3,
    }
    score = 100
    for finding in findings:
        score -= deductions[finding.severity]
    return max(0, min(100, score))


def _risk_counts(findings: list[AiReviewFinding]) -> tuple[int, int]:
    critical = sum(1 for finding in findings if finding.severity == "critical")
    high = sum(1 for finding in findings if finding.severity == "high")
    return critical, high


def _summary(score: int, label: str, findings: list[AiReviewFinding]) -> str:
    critical, high = _risk_counts(findings)
    if critical:
        return (
            f"{label}: the review found {critical} critical blocker(s). Resolve those before using this workspace "
            "as a reliable architecture baseline."
        )
    if high:
        return (
            f"{label}: the workspace is usable for analysis, but {high} high-priority architect decision(s) "
            "remain before the review should be treated as complete."
        )
    return (
        f"{label}: readiness score {score}/100. The review found no critical or high-priority blockers in the "
        "current governed evidence pack."
    )


def _evidence(
    items: list[AiReviewEvidence],
    *,
    label: str,
    detail: str,
    source: str,
    entity_type: str,
    entity_id: str | None = None,
    href: str | None = None,
) -> AiReviewEvidence:
    item = AiReviewEvidence(
        id=f"EV-{len(items) + 1:03d}",
        label=label,
        detail=detail,
        source=source,
        entity_type=entity_type,
        entity_id=entity_id,
        href=href,
    )
    items.append(item)
    return item


def _evidence_lines(evidence: list[AiReviewEvidence], ids: list[str]) -> list[str]:
    by_id = {item.id: item for item in evidence}
    return [f"{item.id}: {item.label} — {item.detail}" for evidence_id in ids if (item := by_id.get(evidence_id))]


def _groups(findings: list[AiReviewFinding]) -> list[AiReviewGroup]:
    groups: list[AiReviewGroup] = []
    for group_id, (title, description) in GROUP_META.items():
        group_findings = [finding for finding in findings if finding.category == group_id]
        worst = max(group_findings, key=lambda finding: SEVERITY_RANK[finding.severity]).severity if group_findings else None
        groups.append(
            AiReviewGroup(
                id=group_id,
                title=title,
                description=description,
                finding_ids=[finding.id for finding in group_findings],
                count=len(group_findings),
                worst_severity=worst,
            )
        )
    return groups


def _personas(
    requested_personas: list[str],
    *,
    score: int,
    label: str,
    findings: list[AiReviewFinding],
    metrics: list[AiReviewMetric],
) -> list[AiReviewPersonaSummary]:
    finding_titles = [finding.title for finding in findings if finding.severity in {"critical", "high"}]
    metric_map = {metric.label: metric.value for metric in metrics}
    summaries: dict[str, AiReviewPersonaSummary] = {
        "architect": AiReviewPersonaSummary(
            persona="architect",
            title="Architecture reviewer",
            summary=f"{label} at {score}/100. Prioritize route validity, pattern fit, and canvas/service compatibility.",
            focus=finding_titles[:4] or ["No critical/high architecture findings."],
        ),
        "security": AiReviewPersonaSummary(
            persona="security",
            title="Security reviewer",
            summary="Review source/destination ownership and gateway/API exposure before treating the design as controlled.",
            focus=["Source and destination traceability", "Trigger evidence", "Overlay and gateway usage"],
        ),
        "operations": AiReviewPersonaSummary(
            persona="operations",
            title="Operations reviewer",
            summary="Operational readiness depends on QA closure, service warnings, and stress behavior under load.",
            focus=["QA OK " + metric_map.get("QA OK", "—"), "Design coverage " + metric_map.get("Design coverage", "—")],
        ),
        "executive": AiReviewPersonaSummary(
            persona="executive",
            title="Executive reviewer",
            summary=f"Demo readiness is {label.lower()} with score {score}/100. Use the top findings as the decision agenda.",
            focus=["Readiness score", "Top risks", "Next architect action"],
        ),
    }
    return [summaries[persona] for persona in requested_personas if persona in summaries]


def _compact_findings(findings: list[AiReviewFinding]) -> list[AiReviewFinding]:
    return findings[:8]


def _accepted_recommendations(job: AiReviewJob) -> list[AiReviewRecommendationAcceptance]:
    return [
        AiReviewRecommendationAcceptance.model_validate(
            {
                **item,
                "accepted_at": _parse_datetime(item["accepted_at"]) if isinstance(item.get("accepted_at"), str) else item.get("accepted_at"),
            }
        )
        for item in (job.accepted_recommendations or [])
        if isinstance(item, dict)
    ]


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _review_from_payload(payload: dict | None) -> AiReviewResponse | None:
    if not payload:
        return None
    normalized = dict(payload)
    generated_at = normalized.get("generated_at")
    if isinstance(generated_at, str):
        normalized["generated_at"] = _parse_datetime(generated_at)
    return AiReviewResponse.model_validate(normalized)


def serialize_ai_review_job(job: AiReviewJob) -> AiReviewJobResponse:
    """Convert a persisted job into its API response."""

    return AiReviewJobResponse(
        id=job.id,
        project_id=job.project_id,
        requested_by=job.requested_by,
        status=_status_value(job),
        scope=cast(Literal["project", "integration"], job.scope),
        integration_id=job.integration_id,
        input_payload=cast(dict[str, object], sanitize_for_json(job.input_payload)),
        result=_review_from_payload(job.result_payload),
        accepted_recommendations=_accepted_recommendations(job),
        error_details=cast(Optional[dict[str, object]], sanitize_for_json(job.error_details)),
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def _load_job(job_id: str, db: AsyncSession) -> AiReviewJob:
    job = await db.get(AiReviewJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "AI review job not found.", "error_code": "AI_REVIEW_JOB_NOT_FOUND"},
        )
    return job


async def list_ai_review_jobs(project_id: str, db: AsyncSession, limit: int = 20) -> AiReviewJobListResponse:
    """Return recent review history for a project."""

    await _load_project(project_id, db)
    total = int(await db.scalar(select(func.count()).select_from(AiReviewJob).where(AiReviewJob.project_id == project_id)) or 0)
    result = await db.scalars(
        select(AiReviewJob)
        .where(AiReviewJob.project_id == project_id)
        .order_by(AiReviewJob.created_at.desc())
        .limit(limit)
    )
    return AiReviewJobListResponse(jobs=[serialize_ai_review_job(job) for job in result.all()], total=total)


async def get_ai_review_job(job_id: str, db: AsyncSession) -> AiReviewJobResponse:
    """Return one persisted AI review job."""

    return serialize_ai_review_job(await _load_job(job_id, db))


async def create_ai_review_job(
    project_id: str,
    body: AiReviewCreateRequest,
    actor_id: str,
    db: AsyncSession,
) -> AiReviewJobResponse:
    """Persist a new governed AI review job request."""

    await _load_project(project_id, db)
    _validate_graph_context(body.graph_context)
    if body.scope == "integration":
        if body.integration_id is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "integration_id is required when scope is integration.",
                    "error_code": "AI_REVIEW_INTEGRATION_SCOPE_REQUIRES_ID",
                },
            )
        await _load_integration(project_id, body.integration_id, db)
    elif body.integration_id is not None:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "integration_id can only be provided for integration-scoped reviews.",
                "error_code": "AI_REVIEW_PROJECT_SCOPE_REJECTS_INTEGRATION_ID",
            },
        )

    input_payload = cast(dict[str, object], sanitize_for_json(body.model_dump()))
    job = AiReviewJob(
        project_id=project_id,
        requested_by=actor_id or AI_REVIEW_ACTOR_FALLBACK,
        scope=body.scope,
        integration_id=body.integration_id,
        input_payload=input_payload,
        accepted_recommendations=[],
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)
    response = serialize_ai_review_job(job)
    await audit_service.emit(
        event_type="ai_review_job_created",
        entity_type="ai_review_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value=None,
        new_value=response.model_dump(mode="json"),
        project_id=project_id,
        db=db,
        correlation_id=job.id,
    )
    return response


async def mark_ai_review_job_running(job_id: str, db: AsyncSession) -> AiReviewJobResponse:
    """Mark a review job as running."""

    job = await _load_job(job_id, db)
    old_value = {"status": _status_value(job)}
    job.status = type(job.status).RUNNING
    job.started_at = datetime.now(UTC)
    job.finished_at = None
    job.error_details = None
    await db.flush()
    await db.refresh(job)
    await audit_service.emit(
        event_type="ai_review_job_started",
        entity_type="ai_review_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value=old_value,
        new_value={"status": _status_value(job), "started_at": job.started_at.isoformat()},
        project_id=job.project_id,
        db=db,
        correlation_id=job.id,
    )
    return serialize_ai_review_job(job)


async def mark_ai_review_job_failed(
    job_id: str,
    error_details: dict[str, object],
    db: AsyncSession,
) -> AiReviewJobResponse:
    """Persist a failed terminal state for a review job."""

    job = await _load_job(job_id, db)
    old_value = {"status": _status_value(job), "error_details": job.error_details}
    job.status = type(job.status).FAILED
    job.finished_at = datetime.now(UTC)
    job.error_details = cast(dict[str, object], sanitize_for_json(error_details))
    await db.flush()
    await db.refresh(job)
    await audit_service.emit(
        event_type="ai_review_job_failed",
        entity_type="ai_review_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value=old_value,
        new_value={"status": _status_value(job), "error_details": job.error_details},
        project_id=job.project_id,
        db=db,
        correlation_id=job.id,
    )
    return serialize_ai_review_job(job)


async def build_review_result(
    *,
    project_id: str,
    scope: Literal["project", "integration"],
    integration_id: str | None,
    include_llm: bool,
    graph_context: AiReviewGraphContext | None,
    reviewer_personas: list[str],
    db: AsyncSession,
) -> AiReviewResponse:
    """Build a project or integration review from governed deterministic evidence."""

    project = await _load_project(project_id, db)
    rows = await _load_rows(project_id, db, integration_id=integration_id if scope == "integration" else None)
    if scope == "project":
        rows = _rows_for_graph_context(rows, graph_context)
    latest_snapshot = await _latest_volumetry_snapshot(project_id, db)
    latest_dashboard = await _latest_dashboard_snapshot(project_id, db)
    scoped_ids = {row.id for row in rows}
    warning_map = _design_warning_map(latest_snapshot, allowed_ids=scoped_ids if scope == "integration" else None)

    total = len(rows)
    qa_counts = Counter((row.qa_status or "PENDING").upper() for row in rows)
    missing_payload = [row for row in rows if row.payload_per_execution_kb is None]
    missing_pattern = [row for row in rows if not _has_text(row.selected_pattern)]
    missing_route = [row for row in rows if not _has_text(row.source_system) or not _has_text(row.destination_system)]
    missing_trigger = [row for row in rows if not _has_text(row.trigger_type)]
    missing_design = [row for row in rows if not _has_text(row.core_tools)]
    reference_only = [
        row
        for row in rows
        if row.selected_pattern and get_pattern_support(row.selected_pattern).level == "reference"
    ]
    review_rows = [row for row in rows if (row.qa_status or "").upper() == "REVISAR"]
    pending_rows = [row for row in rows if (row.qa_status or "").upper() == "PENDING"]
    warning_rows = [row for row in rows if row.id in warning_map]
    qa_ok_with_warnings = [row for row in rows if (row.qa_status or "").upper() == "OK" and row.id in warning_map]

    evidence: list[AiReviewEvidence] = []
    ev_catalog = _evidence(
        evidence,
        label="Catalog scope",
        detail=f"{total} governed integration(s) reviewed. {_graph_context_detail(graph_context)}",
        source="catalog_integrations",
        entity_type="project",
        entity_id=project_id,
        href=_catalog_href_for_context(project_id, graph_context),
    )
    ev_qa = _evidence(
        evidence,
        label="QA distribution",
        detail=f"OK={qa_counts.get('OK', 0)}, REVISAR={qa_counts.get('REVISAR', 0)}, PENDING={qa_counts.get('PENDING', 0)}.",
        source="catalog_integrations.qa_status",
        entity_type="project",
        entity_id=project_id,
        href=_catalog_href_for_context(project_id, graph_context),
    )
    ev_snapshot = _evidence(
        evidence,
        label="Latest volumetry snapshot",
        detail=latest_snapshot.id if latest_snapshot else "No volumetry snapshot found.",
        source="volumetry_snapshots",
        entity_type="volumetry_snapshot",
        entity_id=latest_snapshot.id if latest_snapshot else None,
        href=f"/projects/{project_id}",
    )
    ev_dashboard = _evidence(
        evidence,
        label="Latest dashboard snapshot",
        detail=latest_dashboard.id if latest_dashboard else "No dashboard snapshot found.",
        source="dashboard_snapshots",
        entity_type="dashboard_snapshot",
        entity_id=latest_dashboard.id if latest_dashboard else None,
        href=f"/projects/{project_id}",
    )
    ev_design = _evidence(
        evidence,
        label="Canvas/service warnings",
        detail=f"{len(warning_map)} integration(s) have persisted design-constraint warnings.",
        source="volumetry_snapshots.row_results.design_constraint_warnings",
        entity_type="project",
        entity_id=project_id,
        href=_catalog_href_for_context(project_id, graph_context),
    )
    ev_coverage = _evidence(
        evidence,
        label="Coverage metrics",
        detail=(
            f"Payload={_format_percent(total - len(missing_payload), total)}, "
            f"Pattern={_format_percent(total - len(missing_pattern), total)}, "
            f"Design={_format_percent(total - len(missing_design), total)}."
        ),
        source="catalog_integrations",
        entity_type="project",
        entity_id=project_id,
        href=_catalog_href(project_id),
    )

    findings: list[AiReviewFinding] = []
    if total == 0:
        ids = [ev_catalog.id]
        findings.append(
            _finding(
                "empty-catalog",
                "critical",
                "data_quality",
                "No governed catalog rows are available",
                "The project cannot be reviewed until at least one integration exists.",
                ids,
                _evidence_lines(evidence, ids),
                "catalog_rows=0",
                "At least one governed integration should exist before running architecture review.",
                "Import or manually capture integrations before using AI review.",
                "Open catalog",
                _catalog_href(project_id),
            )
        )
    if latest_snapshot is None:
        ids = [ev_catalog.id, ev_snapshot.id]
        findings.append(
            _finding(
                "missing-volumetry-snapshot",
                "high" if total else "medium",
                "snapshot_freshness",
                "No volumetry snapshot exists",
                "The review cannot verify current technical sizing until the project is recalculated.",
                ids,
                _evidence_lines(evidence, ids),
                "latest_snapshot=none",
                "Latest catalog state should have a matching volumetry snapshot.",
                "Run recalculation before treating service-footprint conclusions as final.",
                "Run recalculation",
                f"/projects/{project_id}",
            )
        )
    elif latest_snapshot.snapshot_metadata and latest_snapshot.snapshot_metadata.get("integration_count") != total and scope == "project":
        ids = [ev_catalog.id, ev_snapshot.id]
        findings.append(
            _finding(
                "stale-volumetry-snapshot",
                "high",
                "snapshot_freshness",
                "Latest volumetry snapshot does not match catalog size",
                "Recalculate before presenting sizing, readiness, or service-footprint conclusions.",
                ids,
                _evidence_lines(evidence, ids),
                f"snapshot_integrations={latest_snapshot.snapshot_metadata.get('integration_count')}, catalog_integrations={total}",
                "Snapshot integration count should match the governed catalog count.",
                "Run recalculation and re-run the review job.",
                "Run recalculation",
                f"/projects/{project_id}",
            )
        )
    if latest_dashboard is None and total:
        ids = [ev_dashboard.id]
        findings.append(
            _finding(
                "missing-dashboard-snapshot",
                "medium",
                "snapshot_freshness",
                "No dashboard snapshot exists",
                "The review can inspect catalog quality, but dashboard maturity and risk summaries are not available yet.",
                ids,
                _evidence_lines(evidence, ids),
                "latest_dashboard_snapshot=none",
                "Dashboard snapshot should be available for demo-readiness review.",
                "Open the dashboard after recalculation so dashboard artifacts are generated.",
                "Open dashboard",
                f"/projects/{project_id}",
            )
        )
    if review_rows:
        ids = [ev_qa.id]
        findings.append(
            _finding(
                "qa-review-open",
                "high",
                "governance",
                "QA review rows remain open",
                f"{len(review_rows)} integration(s) still require architect review before this project is clean.",
                ids,
                [*_evidence_lines(evidence, ids), *[_display_name(row) for row in review_rows[:3]]],
                f"qa_revisar={len(review_rows)}",
                "QA review rows should be resolved or explicitly accepted by the architect.",
                "Filter QA review rows and close the architect decisions before presenting as complete.",
                "Filter QA review",
                _catalog_href(project_id, "qa_status=REVISAR"),
                _first_ids(review_rows),
            )
        )
    if warning_rows:
        first_warning = next(iter(warning_map.values()))[0]
        ids = [ev_design.id]
        findings.append(
            _finding(
                "design-constraints-open",
                "high",
                "canvas_consistency",
                "Canvas/service compatibility warnings are present",
                "One or more integrations have persisted design-constraint warnings from the latest recalculation.",
                ids,
                [*_evidence_lines(evidence, ids), f"Example: {first_warning}"],
                f"warning_rows={len(warning_rows)}",
                "Canvas routes should align with supported OCI service combinations and documented limits.",
                "Open the affected integrations, resolve canvas/service blockers, then recalculate.",
                "Open catalog",
                _catalog_href(project_id),
                _first_ids(warning_rows),
            )
        )
    if reference_only:
        ids = [ev_catalog.id]
        findings.append(
            _finding(
                "reference-only-patterns",
                "high",
                "governance",
                "Reference-only patterns are selected",
                "Some rows use patterns documented for reference but not treated as fully parity-ready.",
                ids,
                [*_evidence_lines(evidence, ids), *[_display_name(row) for row in reference_only[:3]]],
                f"reference_only_rows={len(reference_only)}",
                "Production-ready reviews should distinguish fully supported patterns from reference-library patterns.",
                "Review those rows and either select supported patterns or document explicit architect acceptance.",
                "Review patterns",
                _catalog_href(project_id),
                _first_ids(reference_only),
            )
        )
    if missing_payload and total:
        severity: AiReviewSeverity = "high" if _pct(total - len(missing_payload), total) < 60 else "medium"
        ids = [ev_coverage.id]
        findings.append(
            _finding(
                "payload-coverage-gap",
                severity,
                "data_quality",
                "Payload evidence is incomplete",
                "Forecasts are less reliable when payload per execution is missing.",
                ids,
                _evidence_lines(evidence, ids),
                f"missing_payload={len(missing_payload)}",
                "Payload coverage should be high enough for sizing and stress analysis.",
                "Capture payload evidence or mark uncertainty explicitly before using forecasts.",
                "Filter catalog",
                _catalog_href(project_id),
                _first_ids(missing_payload),
            )
        )
    if missing_pattern and total:
        ids = [ev_coverage.id]
        findings.append(
            _finding(
                "pattern-coverage-gap",
                "medium",
                "data_quality",
                "Pattern assignment is incomplete",
                "Rows without selected patterns cannot be reviewed as a governed OCI design decision.",
                ids,
                _evidence_lines(evidence, ids),
                f"missing_pattern={len(missing_pattern)}",
                "Every reviewed row should have a selected pattern or explicit exception.",
                "Assign patterns for missing rows or document why they remain unassigned.",
                "Assign patterns",
                _catalog_href(project_id),
                _first_ids(missing_pattern),
            )
        )
    if missing_route and total:
        ids = [ev_coverage.id]
        findings.append(
            _finding(
                "route-coverage-gap",
                "medium",
                "data_quality",
                "Source or destination systems are missing",
                "The dependency map and flow review depend on complete source and destination system names.",
                ids,
                _evidence_lines(evidence, ids),
                f"missing_route={len(missing_route)}",
                "Every route should have source and destination systems.",
                "Complete route ownership before graph or design review is treated as final.",
                "Review routes",
                _catalog_href(project_id),
                _first_ids(missing_route),
            )
        )
    if missing_trigger and total:
        ids = [ev_coverage.id]
        findings.append(
            _finding(
                "trigger-coverage-gap",
                "medium",
                "data_quality",
                "Trigger evidence is incomplete",
                "Missing trigger types reduce confidence in OIC, event, and API route recommendations.",
                ids,
                _evidence_lines(evidence, ids),
                f"missing_trigger={len(missing_trigger)}",
                "Trigger type should be captured for sizing and compatibility review.",
                "Review technical fields and normalize the trigger vocabulary.",
                "Review technical fields",
                _catalog_href(project_id),
                _first_ids(missing_trigger),
            )
        )
    if missing_design and total:
        ids = [ev_coverage.id]
        findings.append(
            _finding(
                "design-canvas-gap",
                "medium",
                "canvas_consistency",
                "Design canvas coverage is incomplete",
                "Rows without core tools cannot receive a strong route-composition review.",
                ids,
                _evidence_lines(evidence, ids),
                f"missing_design={len(missing_design)}",
                "Every reviewed row should have governed core route tools.",
                "Open the design canvas for missing rows and save a connected route.",
                "Open catalog",
                _catalog_href(project_id),
                _first_ids(missing_design),
            )
        )
    if warning_rows:
        ids = [ev_design.id]
        findings.append(
            _finding(
                "ten-x-stress-review",
                "medium",
                "stress_review",
                "10x stress review flags existing service-limit exposure",
                "Rows with current design warnings are the first candidates to fail or need redesign under 10x volume.",
                ids,
                _evidence_lines(evidence, ids),
                f"warning_rows_at_1x={len(warning_rows)}",
                "No service-limit warnings should exist before modeling aggressive growth.",
                "Resolve current warnings, then re-run volumetry and repeat the 10x stress review.",
                "Open catalog",
                _catalog_href(project_id),
                _first_ids(warning_rows),
            )
        )
    elif total and not missing_payload:
        ids = [ev_coverage.id]
        findings.append(
            _finding(
                "ten-x-stress-review-clean-inputs",
                "positive",
                "stress_review",
                "10x stress review has complete input coverage",
                "Payload coverage is complete, so growth stress modeling has usable source inputs.",
                ids,
                _evidence_lines(evidence, ids),
                "payload_coverage=100%",
                "Growth stress review should use complete payload inputs.",
                "Keep payload evidence current as integrations change.",
                "Open dashboard",
                f"/projects/{project_id}",
            )
        )
    if qa_ok_with_warnings:
        ids = [ev_qa.id, ev_design.id]
        findings.append(
            _finding(
                "red-team-qa-ok-with-design-warnings",
                "high",
                "red_team",
                "Red-team contradiction: QA OK rows still have design warnings",
                "At least one row is marked QA OK while the latest recalculation reports canvas/service warnings.",
                ids,
                _evidence_lines(evidence, ids),
                f"qa_ok_warning_rows={len(qa_ok_with_warnings)}",
                "QA green should not contradict active service compatibility evidence.",
                "Review QA rules and affected rows so dashboard confidence matches service-limit evidence.",
                "Open catalog",
                _catalog_href(project_id, "qa_status=OK"),
                _first_ids(qa_ok_with_warnings),
            )
        )
    if pending_rows:
        ids = [ev_qa.id]
        findings.append(
            _finding(
                "qa-pending-open",
                "low",
                "governance",
                "Pending QA rows remain",
                "Pending rows should be resolved or explicitly accepted before an executive demo.",
                ids,
                _evidence_lines(evidence, ids),
                f"qa_pending={len(pending_rows)}",
                "Pending QA should be zero or accepted with rationale.",
                "Resolve pending rows or create an explicit review acceptance.",
                "Filter pending",
                _catalog_href(project_id, "qa_status=PENDING"),
                _first_ids(pending_rows),
            )
        )
    if total and not review_rows and not pending_rows and not warning_rows:
        ids = [ev_qa.id, ev_design.id]
        findings.append(
            _finding(
                "demo-readiness-clean",
                "positive",
                "demo_readiness",
                "Demo readiness signals are clean",
                "The governed QA and canvas/service signals show no critical or high-priority blockers.",
                ids,
                _evidence_lines(evidence, ids),
                "qa_review=0, qa_pending=0, design_warnings=0",
                "Demo-ready projects should have no unresolved QA or design blockers.",
                "Keep the review result as a presentation evidence snapshot.",
                "Open dashboard",
                f"/projects/{project_id}",
            )
        )

    findings = _with_suggested_patches(
        sorted(findings, key=lambda finding: (-SEVERITY_RANK[finding.severity], finding.id)),
        rows,
    )
    score = _score(findings)
    critical_count, high_count = _risk_counts(findings)
    label = _readiness_label(score, critical_count, high_count)
    metrics = [
        AiReviewMetric(label="Catalog rows", value=str(total), detail="Governed integrations in review scope."),
        AiReviewMetric(
            label="QA OK",
            value=_format_percent(qa_counts.get("OK", 0), total),
            detail=f"{qa_counts.get('OK', 0)} of {total} rows are OK.",
        ),
        AiReviewMetric(
            label="Payload coverage",
            value=_format_percent(total - len(missing_payload), total),
            detail=f"{len(missing_payload)} row(s) still lack payload evidence.",
        ),
        AiReviewMetric(
            label="Pattern coverage",
            value=_format_percent(total - len(missing_pattern), total),
            detail=f"{len(missing_pattern)} row(s) still lack a selected pattern.",
        ),
        AiReviewMetric(
            label="Design coverage",
            value=_format_percent(total - len(missing_design), total),
            detail=f"{len(missing_design)} row(s) still lack core route tools.",
        ),
    ]
    evidence_pack = [
        f"project_id={project_id}",
        f"scope={scope}",
        f"integration_id={integration_id or 'all'}",
        f"graph_context={_graph_context_detail(graph_context)}",
        f"catalog_rows={total}",
        f"qa_ok={qa_counts.get('OK', 0)}",
        f"qa_revisar={qa_counts.get('REVISAR', 0)}",
        f"qa_pending={qa_counts.get('PENDING', 0)}",
        f"latest_volumetry_snapshot={latest_snapshot.id if latest_snapshot else 'none'}",
        f"latest_dashboard_snapshot={latest_dashboard.id if latest_dashboard else 'none'}",
        f"design_warning_rows={len(warning_map)}",
        f"formal_evidence_ids={','.join(item.id for item in evidence)}",
    ]
    deterministic_summary = _summary(score, label, findings)
    llm_result = (
        await synthesize_review_summary(
            settings=get_settings(),
            project_name=project.name,
            readiness_score=score,
            readiness_label=label,
            deterministic_summary=deterministic_summary,
            metrics=metrics,
            findings=_compact_findings(findings),
            evidence_pack=evidence_pack,
        )
        if include_llm
        else LlmReviewResult(status="skipped", model=None, summary=None)
    )

    return AiReviewResponse(
        project_id=project_id,
        project_name=project.name,
        scope=scope,
        integration_id=integration_id,
        generated_at=datetime.now(UTC),
        readiness_score=score,
        readiness_label=label,
        summary=deterministic_summary,
        llm_status=llm_result.status,
        llm_model=llm_result.model,
        llm_summary=llm_result.summary,
        graph_context=graph_context,
        metrics=metrics,
        findings=findings,
        groups=_groups(findings),
        evidence=evidence,
        evidence_pack=evidence_pack,
        reviewer_personas=_personas(
            reviewer_personas,
            score=score,
            label=label,
            findings=findings,
            metrics=metrics,
        ),
    )


async def run_project_review(project_id: str, db: AsyncSession) -> AiReviewResponse:
    """Backward-compatible synchronous project review builder."""

    return await build_review_result(
        project_id=project_id,
        scope="project",
        integration_id=None,
        include_llm=True,
        graph_context=None,
        reviewer_personas=["architect", "security", "operations", "executive"],
        db=db,
    )


async def run_ai_review_job(job_id: str, db: AsyncSession) -> AiReviewJobResponse:
    """Execute one persisted AI review job through deterministic evidence and optional LLM."""

    job = await _load_job(job_id, db)
    input_payload = cast(dict[str, object], job.input_payload)
    review = await build_review_result(
        project_id=job.project_id,
        scope=cast(Literal["project", "integration"], job.scope),
        integration_id=job.integration_id,
        include_llm=bool(input_payload.get("include_llm", True)),
        graph_context=(
            AiReviewGraphContext.model_validate(input_payload["graph_context"])
            if isinstance(input_payload.get("graph_context"), dict)
            else None
        ),
        reviewer_personas=[str(item) for item in cast(list[object], input_payload.get("reviewer_personas", []))],
        db=db,
    )
    old_value = {"status": _status_value(job)}
    job.status = type(job.status).COMPLETED
    job.finished_at = datetime.now(UTC)
    job.result_payload = cast(dict[str, object], sanitize_for_json(review.model_dump(mode="json")))
    job.error_details = None
    await db.flush()
    await db.refresh(job)
    response = serialize_ai_review_job(job)
    await audit_service.emit(
        event_type="ai_review_job_completed",
        entity_type="ai_review_job",
        entity_id=job.id,
        actor_id=job.requested_by,
        old_value=old_value,
        new_value=response.model_dump(mode="json"),
        project_id=job.project_id,
        db=db,
        correlation_id=job.id,
    )
    return response


async def accept_ai_review_finding(
    job_id: str,
    finding_id: str,
    body: AiReviewAcceptRecommendationRequest,
    actor_id: str,
    db: AsyncSession,
) -> AiReviewJobResponse:
    """Record human acceptance of one recommendation without changing catalog data."""

    job = await _load_job(job_id, db)
    if _status_value(job) != "completed" or job.result_payload is None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Only completed AI review jobs can accept recommendations.",
                "error_code": "AI_REVIEW_JOB_NOT_COMPLETED",
            },
        )
    review = _review_from_payload(job.result_payload)
    if review is None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "AI review job has no result payload.",
                "error_code": "AI_REVIEW_RESULT_MISSING",
            },
        )
    if not any(finding.id == finding_id for finding in review.findings):
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "Finding not found in this review job.",
                "error_code": "AI_REVIEW_FINDING_NOT_FOUND",
            },
        )
    accepted = [
        item.model_dump(mode="json")
        for item in _accepted_recommendations(job)
        if item.finding_id != finding_id
    ]
    acceptance = AiReviewRecommendationAcceptance(
        finding_id=finding_id,
        accepted_by=actor_id or AI_REVIEW_ACTOR_FALLBACK,
        accepted_at=datetime.now(UTC),
        note=body.note,
    )
    old_value = {"accepted_recommendations": job.accepted_recommendations or []}
    accepted.append(acceptance.model_dump(mode="json"))
    job.accepted_recommendations = accepted
    await db.flush()
    await db.refresh(job)
    response = serialize_ai_review_job(job)
    await audit_service.emit(
        event_type="ai_review_recommendation_accepted",
        entity_type="ai_review_job",
        entity_id=job.id,
        actor_id=acceptance.accepted_by,
        old_value=old_value,
        new_value={"accepted_recommendations": accepted},
        project_id=job.project_id,
        db=db,
        correlation_id=job.id,
    )
    return response


async def apply_ai_review_finding_patch(
    job_id: str,
    finding_id: str,
    body: AiReviewApplyPatchRequest,
    actor_id: str,
    db: AsyncSession,
) -> AiReviewApplyPatchResponse:
    """Apply one deterministic suggested patch after human confirmation."""

    job = await _load_job(job_id, db)
    if _status_value(job) != "completed" or job.result_payload is None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Only completed AI review jobs can apply recommendations.",
                "error_code": "AI_REVIEW_JOB_NOT_COMPLETED",
            },
        )
    review = _review_from_payload(job.result_payload)
    if review is None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "AI review job has no result payload.",
                "error_code": "AI_REVIEW_RESULT_MISSING",
            },
        )
    finding = next((item for item in review.findings if item.id == finding_id), None)
    if finding is None:
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "Finding not found in this review job.",
                "error_code": "AI_REVIEW_FINDING_NOT_FOUND",
            },
        )
    if finding.suggested_patch is None or not finding.suggested_patch.safe_to_apply:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "This finding does not have a deterministic patch that is safe to apply automatically.",
                "error_code": "AI_REVIEW_PATCH_NOT_AVAILABLE",
            },
        )

    row = await _load_integration(job.project_id, finding.suggested_patch.integration_id, db)
    refreshed_patch = _suggested_patch_for_finding(finding, {row.id: row})
    if refreshed_patch is None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The suggested patch is already applied or no longer matches the current integration state.",
                "error_code": "AI_REVIEW_PATCH_STALE",
            },
        )

    integration = await catalog_service.update_integration(
        job.project_id,
        row.id,
        CatalogIntegrationPatch.model_validate(refreshed_patch.patch),
        actor_id or AI_REVIEW_ACTOR_FALLBACK,
        db,
    )
    accepted = [
        item.model_dump(mode="json")
        for item in _accepted_recommendations(job)
        if item.finding_id != finding_id
    ]
    acceptance = AiReviewRecommendationAcceptance(
        finding_id=finding_id,
        accepted_by=actor_id or AI_REVIEW_ACTOR_FALLBACK,
        accepted_at=datetime.now(UTC),
        note=body.note or "Applied deterministic suggested patch from the review board.",
        applied_patch=refreshed_patch.model_dump(mode="json"),
    )
    old_value = {"accepted_recommendations": job.accepted_recommendations or []}
    accepted.append(acceptance.model_dump(mode="json"))
    job.accepted_recommendations = accepted
    await db.flush()
    await db.refresh(job)
    response = serialize_ai_review_job(job)
    await audit_service.emit(
        event_type="ai_review_recommendation_applied",
        entity_type="ai_review_job",
        entity_id=job.id,
        actor_id=acceptance.accepted_by,
        old_value=old_value,
        new_value={
            "accepted_recommendations": accepted,
            "applied_patch": refreshed_patch.model_dump(mode="json"),
            "integration_id": row.id,
        },
        project_id=job.project_id,
        db=db,
        correlation_id=job.id,
    )
    return AiReviewApplyPatchResponse(
        job=response,
        integration=integration,
        applied_patch=refreshed_patch,
    )
