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
    AiReviewBaseline,
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
    AiReviewBaselineCreateRequest,
    AiReviewBaselineListResponse,
    AiReviewBaselineLookupResponse,
    AiReviewBaselineResponse,
    AiReviewCategory,
    AiReviewCreateRequest,
    AiReviewDecisionBrief,
    AiReviewDriftItem,
    AiReviewDriftReport,
    AiReviewEvidence,
    AiReviewFieldDiff,
    AiReviewFinding,
    AiReviewGraphContext,
    AiReviewGroup,
    AiReviewJobCompareResponse,
    AiReviewJobListResponse,
    AiReviewJobResponse,
    AiReviewMetric,
    AiReviewPersonaSummary,
    AiReviewProviderStatus,
    AiReviewRecommendationAcceptance,
    AiReviewRemediationStep,
    AiReviewResponse,
    AiReviewSeverity,
    AiReviewStressScenario,
    AiReviewSuggestedPatch,
    AiReviewTopologyInsight,
)
from app.schemas.catalog import CatalogIntegrationPatch
from app.services import audit_service, catalog_service, service_rule_service
from app.services.canvas_interoperability import CanvasDesignValidationError, parse_canvas_state
from app.services.llm_review_client import LlmReviewResult, provider_status_payload, synthesize_review_summary
from app.services.pattern_support import get_pattern_support
from app.services.serializers import sanitize_for_json, split_csv

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

DRIFT_FIELD_META: dict[str, tuple[str, Literal["critical", "high", "medium", "low"]]] = {
    "source_system": ("Source system", "high"),
    "destination_system": ("Destination system", "high"),
    "selected_pattern": ("Selected pattern", "high"),
    "core_tools": ("Core route tools", "high"),
    "additional_tools_overlays": ("Architectural overlays", "medium"),
    "trigger_type": ("Trigger type", "medium"),
    "payload_per_execution_kb": ("Payload per execution", "medium"),
    "qa_status": ("QA status", "medium"),
}

DRIFT_SEVERITY_RANK: dict[Literal["critical", "high", "medium", "low"], int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
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


def _scope_label(scope: str, integration_id: str | None) -> str:
    return "Integration" if scope == "integration" and integration_id else "Project"


def _format_baseline_label(scope: str, integration_id: str | None) -> str:
    return f"{_scope_label(scope, integration_id)} planned baseline {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"


def _tools_value(value: str | None) -> str | None:
    if value is None:
        return None
    parts = [part.strip() for part in value.split(",") if part.strip()]
    return ", ".join(parts) if parts else None


def _canvas_governance_values(row: CatalogIntegration) -> tuple[str | None, str | None]:
    """Return stable route-tool and overlay values without persisting canvas layout JSON."""

    fallback_core = _tools_value(row.core_tools)
    fallback_overlays = _tools_value(row.additional_tools_overlays)
    try:
        parsed = parse_canvas_state(row.additional_tools_overlays, split_csv(row.core_tools))
    except CanvasDesignValidationError:
        return fallback_core, fallback_overlays

    return (
        _tools_value(", ".join(parsed.core_tool_keys)),
        _tools_value(", ".join(parsed.overlay_keys)),
    )


def _row_baseline_state(row: CatalogIntegration) -> dict[str, object | None]:
    core_tools, overlays = _canvas_governance_values(row)
    return {
        "id": row.id,
        "seq_number": row.seq_number,
        "interface_id": row.interface_id,
        "interface_name": row.interface_name,
        "source_system": row.source_system,
        "destination_system": row.destination_system,
        "selected_pattern": row.selected_pattern,
        "core_tools": core_tools,
        "additional_tools_overlays": overlays,
        "trigger_type": row.trigger_type,
        "payload_per_execution_kb": row.payload_per_execution_kb,
        "qa_status": row.qa_status,
    }


def _baseline_payload(
    *,
    project: Project,
    rows: list[CatalogIntegration],
    scope: Literal["project", "integration"],
    integration_id: str | None,
    latest_snapshot: VolumetrySnapshot | None,
    latest_dashboard: DashboardSnapshot | None,
) -> dict[str, object]:
    qa_counts = Counter((row.qa_status or "PENDING").upper() for row in rows)
    return cast(
        dict[str, object],
        sanitize_for_json(
            {
                "version": 1,
                "project_id": project.id,
                "project_name": project.name,
                "scope": scope,
                "integration_id": integration_id,
                "captured_at": datetime.now(UTC).isoformat(),
                "row_count": len(rows),
                "latest_volumetry_snapshot_id": latest_snapshot.id if latest_snapshot else None,
                "latest_dashboard_snapshot_id": latest_dashboard.id if latest_dashboard else None,
                "qa_counts": dict(qa_counts),
                "rows": [_row_baseline_state(row) for row in rows],
            }
        ),
    )


def _stringify_drift_value(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, int):
        return str(value)
    return str(value)


def _read_canvas_overlay_value(value: object | None) -> object | None:
    if not isinstance(value, str) or not value.strip().startswith("{"):
        return value
    try:
        parsed = parse_canvas_state(value, ())
    except CanvasDesignValidationError:
        return value
    return ", ".join(parsed.overlay_keys) if parsed.overlay_keys else None


def _display_drift_value(field: str, value: object | None) -> str | None:
    if field == "additional_tools_overlays":
        value = _read_canvas_overlay_value(value)
    return _stringify_drift_value(value)


def _normalize_drift_value(field: str, value: object | None) -> str:
    if value is None:
        return ""
    if field == "additional_tools_overlays":
        value = _read_canvas_overlay_value(value)
        if value is None:
            return ""
    if field in {"core_tools", "additional_tools_overlays"}:
        return "|".join(sorted(part.strip().lower() for part in str(value).split(",") if part.strip()))
    if field == "payload_per_execution_kb":
        try:
            return f"{float(str(value)):.3f}"
        except (TypeError, ValueError):
            return str(value).strip().lower()
    return str(value).strip().lower()


def _drift_status(items: list[AiReviewDriftItem]) -> tuple[
    Literal["no_drift", "minor_drift", "material_drift", "blocking_drift"],
    Literal["critical", "high", "medium", "low"] | None,
]:
    if not items:
        return "no_drift", None
    worst = max(items, key=lambda item: DRIFT_SEVERITY_RANK[item.severity]).severity
    if worst == "critical":
        return "blocking_drift", worst
    if worst == "high":
        return "material_drift", worst
    return "minor_drift", worst


def _baseline_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return []
    return [cast(dict[str, object], row) for row in rows if isinstance(row, dict)]


def _drift_report(
    *,
    baseline: AiReviewBaseline | None,
    project_id: str,
    rows: list[CatalogIntegration],
) -> AiReviewDriftReport:
    if baseline is None:
        return AiReviewDriftReport(
            status="no_baseline",
            summary="No approved planned baseline exists for this review scope yet.",
        )

    baseline_payload = cast(dict[str, object], baseline.baseline_payload or {})
    planned_rows = {str(row.get("id")): row for row in _baseline_rows(baseline_payload) if row.get("id")}
    actual_rows = {row.id: _row_baseline_state(row) for row in rows}
    items: list[AiReviewDriftItem] = []

    for planned_id, planned in sorted(planned_rows.items()):
        if planned_id not in actual_rows:
            items.append(
                AiReviewDriftItem(
                    id=f"DRIFT-{len(items) + 1:03d}",
                    severity="critical",
                    entity_type="integration",
                    integration_id=planned_id,
                    field="integration",
                    label=str(planned.get("interface_name") or planned.get("interface_id") or planned_id),
                    planned="Present in planned baseline",
                    actual="Missing from current catalog scope",
                    detail="A planned integration is no longer present in the current review scope.",
                    action_href=_catalog_href(project_id),
                )
            )
            continue

        actual = actual_rows[planned_id]
        label = str(actual.get("interface_name") or actual.get("interface_id") or planned_id)
        for field, (field_label, severity) in DRIFT_FIELD_META.items():
            planned_value = planned.get(field)
            actual_value = actual.get(field)
            if _normalize_drift_value(field, planned_value) == _normalize_drift_value(field, actual_value):
                continue
            items.append(
                AiReviewDriftItem(
                    id=f"DRIFT-{len(items) + 1:03d}",
                    severity=severity,
                    entity_type="integration",
                    integration_id=planned_id,
                    field=field,
                    label=f"{label} · {field_label}",
                    planned=_display_drift_value(field, planned_value),
                    actual=_display_drift_value(field, actual_value),
                    detail=f"{field_label} differs from the approved planned baseline.",
                    action_href=_integration_href(project_id, planned_id),
                )
            )

    for actual_id, actual in sorted(actual_rows.items()):
        if actual_id in planned_rows:
            continue
        items.append(
            AiReviewDriftItem(
                id=f"DRIFT-{len(items) + 1:03d}",
                severity="medium",
                entity_type="integration",
                integration_id=actual_id,
                field="integration",
                label=str(actual.get("interface_name") or actual.get("interface_id") or actual_id),
                planned="Not present in planned baseline",
                actual="Present in current catalog scope",
                detail="A current integration was added after the planned baseline was approved.",
                action_href=_integration_href(project_id, actual_id),
            )
        )

    status, worst = _drift_status(items)
    if status == "no_drift":
        summary = "Current governed state matches the active planned baseline."
    else:
        summary = f"{len(items)} planned-versus-actual drift item(s) require review."

    return AiReviewDriftReport(
        status=status,
        baseline=serialize_ai_review_baseline(baseline),
        item_count=len(items),
        worst_severity=worst,
        summary=summary,
        items=items[:20],
    )


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


def _field_diff(field: str, current: object | None, recommended: object | None) -> AiReviewFieldDiff:
    return AiReviewFieldDiff(
        field=field,
        current=_stringify_drift_value(current),
        recommended=_stringify_drift_value(recommended),
    )


def _trigger_pattern_candidate(row: CatalogIntegration) -> tuple[str, str] | None:
    trigger_text = f"{row.trigger_type or ''} {row.type or ''} {row.base or ''}".lower()
    if "rest" in trigger_text or "soap" in trigger_text or "request" in trigger_text:
        return (
            "#01",
            "AI Review inferred Request-Reply because trigger evidence indicates a synchronous REST/SOAP path.",
        )
    if "event" in trigger_text or "webhook" in trigger_text or "stream" in trigger_text or "pub" in trigger_text:
        return (
            "#02",
            "AI Review inferred Event-Driven / Pub-Sub because trigger evidence indicates asynchronous event delivery.",
        )
    return None


def _trigger_tool_candidate(row: CatalogIntegration) -> tuple[str, str | None] | None:
    trigger_text = f"{row.trigger_type or ''} {row.type or ''} {row.base or ''}".lower()
    if "event" in trigger_text or "webhook" in trigger_text or "stream" in trigger_text or "pub" in trigger_text:
        return "OIC Gen3, OCI Streaming", None
    if "rest" in trigger_text or "soap" in trigger_text or "request" in trigger_text:
        overlay = "OCI API Gateway" if row.source_api_reference or "api" in (row.source_technology or "").lower() else None
        return "OIC Gen3", overlay
    if "scheduled" in trigger_text or "schedule" in trigger_text:
        return "OIC Gen3", None
    return None


def _is_canvas_state(value: str | None) -> bool:
    return bool(value and value.strip().startswith("{"))


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
    patch: dict[str, object] = {}
    field_diffs: list[AiReviewFieldDiff] = []
    label = "Apply governance note"
    description = (
        "Adds the human-approved recommendation to the architect-owned comments field. "
        "It does not alter source lineage or payload values."
    )
    safety_note = "Bounded to architect-owned fields and emitted through catalog audit."

    if recommended_comments != (row.comments or ""):
        patch["comments"] = recommended_comments
        field_diffs.append(_field_diff("comments", row.comments, recommended_comments))

    if finding.id == "pattern-coverage-gap" and not _has_text(row.selected_pattern):
        candidate = _trigger_pattern_candidate(row)
        if candidate is not None:
            selected_pattern, rationale = candidate
            patch["selected_pattern"] = selected_pattern
            if not _has_text(row.pattern_rationale):
                patch["pattern_rationale"] = rationale
            field_diffs.append(_field_diff("selected_pattern", row.selected_pattern, selected_pattern))
            if "pattern_rationale" in patch:
                field_diffs.append(_field_diff("pattern_rationale", row.pattern_rationale, rationale))
            label = "Apply pattern recommendation"
            description = (
                "Assigns a fully supported pattern only because the current row has no pattern and trigger "
                "evidence maps conservatively to a phase-parity pattern."
            )
            safety_note = (
                "Safe because it fills empty architect-owned pattern fields from explicit trigger evidence; "
                "source lineage remains unchanged."
            )

    if finding.id == "design-canvas-gap" and not _has_text(row.core_tools) and not _is_canvas_state(row.additional_tools_overlays):
        tool_candidate = _trigger_tool_candidate(row)
        if tool_candidate is not None:
            core_tools, overlay = tool_candidate
            overlay_text = overlay
            patch["core_tools"] = core_tools
            field_diffs.append(_field_diff("core_tools", row.core_tools, core_tools))
            if overlay_text is not None and not _has_text(row.additional_tools_overlays):
                patch["additional_tools_overlays"] = overlay_text
                field_diffs.append(_field_diff("additional_tools_overlays", row.additional_tools_overlays, overlay_text))
            label = "Apply route tool recommendation"
            description = (
                "Registers conservative core route tools for a row that currently has no governed design tools."
            )
            safety_note = (
                "Safe because it fills empty architect-owned tool fields from explicit trigger evidence and "
                "does not overwrite an existing canvas state."
            )

    if not patch:
        return None
    return AiReviewSuggestedPatch(
        integration_id=row.id,
        label=label,
        description=description,
        patch=patch,
        field_diffs=field_diffs,
        safe_to_apply=True,
        safety_note=safety_note,
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
        "planned_drift",
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


async def _active_baseline(
    project_id: str,
    scope: Literal["project", "integration"],
    integration_id: str | None,
    db: AsyncSession,
) -> AiReviewBaseline | None:
    query = (
        select(AiReviewBaseline)
        .where(
            AiReviewBaseline.project_id == project_id,
            AiReviewBaseline.scope == scope,
            AiReviewBaseline.is_active.is_(True),
        )
        .order_by(AiReviewBaseline.created_at.desc())
        .limit(1)
    )
    if scope == "integration":
        query = query.where(AiReviewBaseline.integration_id == integration_id)
    else:
        query = query.where(AiReviewBaseline.integration_id.is_(None))
    return await db.scalar(query)


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


def _row_daily_payload_kb(row: CatalogIntegration) -> float:
    payload = row.payload_per_execution_kb or 0.0
    executions = row.executions_per_day or 0.0
    return float(payload * executions)


def _format_data_volume(daily_payload_kb: float) -> str:
    if daily_payload_kb <= 0:
        return "0 GB/day"
    daily_gb = daily_payload_kb / 1024 / 1024
    if daily_gb < 1:
        return f"{daily_gb:.2f} GB/day"
    return f"{daily_gb:.1f} GB/day"


def _decision_brief(
    *,
    score: int,
    label: str,
    findings: list[AiReviewFinding],
    drift: AiReviewDriftReport,
) -> AiReviewDecisionBrief:
    blockers = [
        finding.title
        for finding in findings
        if finding.severity in {"critical", "high"} and finding.severity != "positive"
    ][:5]
    top_action = next((finding.recommendation for finding in findings if finding.severity != "positive"), "")
    primary_risk = blockers[0] if blockers else "No critical or high-priority blocker is visible in the governed evidence."
    if any(finding.severity == "critical" for finding in findings) or drift.status == "blocking_drift":
        signoff_status: Literal["blocked", "needs_review", "ready_with_caveats", "ready"] = "blocked"
        headline = f"{label}: architecture sign-off is blocked until critical evidence is resolved."
    elif blockers or drift.status in {"material_drift", "minor_drift"}:
        signoff_status = "needs_review"
        headline = f"{label}: architect decisions remain before this can be treated as approved."
    elif score < 90:
        signoff_status = "ready_with_caveats"
        headline = f"{label}: usable for review with caveats that should be tracked."
    else:
        signoff_status = "ready"
        headline = f"{label}: governed evidence is clean enough for executive review."

    decision_points = [
        f"{finding.title}: {finding.recommendation}"
        for finding in findings
        if finding.severity != "positive"
    ][:4]
    if not decision_points:
        decision_points = ["Keep the baseline current and re-run AI Review after material catalog or canvas changes."]

    return AiReviewDecisionBrief(
        signoff_status=signoff_status,
        headline=headline,
        primary_risk=primary_risk,
        recommended_next_action=top_action or "Save or refresh the planned baseline and keep monitoring drift.",
        decision_points=decision_points,
        blockers=blockers,
    )


def _topology_insights(
    *,
    project_id: str,
    rows: list[CatalogIntegration],
    warning_map: dict[str, list[str]],
) -> list[AiReviewTopologyInsight]:
    if not rows:
        return []

    system_rows: dict[str, list[CatalogIntegration]] = {}
    edge_rows: dict[tuple[str, str], list[CatalogIntegration]] = {}
    for row in rows:
        source = row.source_system or "Unknown source"
        destination = row.destination_system or "Unknown destination"
        system_rows.setdefault(source, []).append(row)
        system_rows.setdefault(destination, []).append(row)
        edge_rows.setdefault((source, destination), []).append(row)

    insights: list[AiReviewTopologyInsight] = []
    top_system, top_system_rows = max(system_rows.items(), key=lambda item: len(item[1]))
    top_system_review_rows = [
        row
        for row in top_system_rows
        if (row.qa_status or "").upper() == "REVISAR" or row.id in warning_map
    ]
    insights.append(
        AiReviewTopologyInsight(
            id="TOP-001",
            insight_type="system_hotspot",
            severity="high" if top_system_review_rows else "medium",
            title=f"{top_system} is the highest-dependency system in scope",
            summary=(
                f"{top_system} participates in {len(top_system_rows)} integration touchpoint(s); "
                f"{len(top_system_review_rows)} need QA or service-warning attention."
            ),
            metric=f"{len(top_system_rows)} touchpoints",
            system_name=top_system,
            action_href=_catalog_href(project_id, f"system={quote_plus(top_system)}"),
            integration_ids=_first_ids(top_system_review_rows or top_system_rows),
        )
    )

    edge_candidates = [
        (edge, edge_scope)
        for edge, edge_scope in edge_rows.items()
        if any((row.qa_status or "").upper() == "REVISAR" or row.id in warning_map for row in edge_scope)
    ]
    if edge_candidates:
        (source, destination), risky_edge_rows = max(
            edge_candidates,
            key=lambda item: (
                sum(1 for row in item[1] if row.id in warning_map),
                sum(1 for row in item[1] if (row.qa_status or "").upper() == "REVISAR"),
                len(item[1]),
            ),
        )
        insights.append(
            AiReviewTopologyInsight(
                id="TOP-002",
                insight_type="edge_hotspot",
                severity="high",
                title=f"{source} -> {destination} concentrates review risk",
                summary=(
                    f"{len(risky_edge_rows)} integration(s) share this route; "
                    f"{sum(1 for row in risky_edge_rows if row.id in warning_map)} have service-warning evidence."
                ),
                metric=f"{len(risky_edge_rows)} route rows",
                source_system=source,
                destination_system=destination,
                action_href=_catalog_href(
                    project_id,
                    f"source_system={quote_plus(source)}&destination_system={quote_plus(destination)}",
                ),
                integration_ids=_first_ids(risky_edge_rows),
            )
        )

    payload_edges = [
        (edge, edge_scope, sum(_row_daily_payload_kb(row) for row in edge_scope))
        for edge, edge_scope in edge_rows.items()
    ]
    payload_edges = [item for item in payload_edges if item[2] > 0]
    if payload_edges:
        (source, destination), payload_edge_rows, daily_payload_kb = max(payload_edges, key=lambda item: item[2])
        insights.append(
            AiReviewTopologyInsight(
                id="TOP-003",
                insight_type="payload_hotspot",
                severity="medium",
                title=f"{source} -> {destination} carries the highest modeled payload",
                summary=(
                    f"Current modeled daily transfer is {_format_data_volume(daily_payload_kb)} before growth multipliers."
                ),
                metric=_format_data_volume(daily_payload_kb),
                source_system=source,
                destination_system=destination,
                action_href=_catalog_href(
                    project_id,
                    f"source_system={quote_plus(source)}&destination_system={quote_plus(destination)}",
                ),
                integration_ids=_first_ids(sorted(payload_edge_rows, key=_row_daily_payload_kb, reverse=True)),
            )
        )

    return insights[:3]


def _stress_scenarios(
    *,
    rows: list[CatalogIntegration],
    warning_map: dict[str, list[str]],
) -> list[AiReviewStressScenario]:
    total = len(rows)
    if total == 0:
        return []
    missing_payload = [row for row in rows if row.payload_per_execution_kb is None]
    current_daily_payload_kb = sum(_row_daily_payload_kb(row) for row in rows)
    top_rows = sorted(rows, key=_row_daily_payload_kb, reverse=True)
    payload_coverage = _pct(total - len(missing_payload), total)
    confidence: Literal["high", "medium", "low"]
    if payload_coverage < 60:
        confidence = "low"
    elif warning_map or payload_coverage < 90:
        confidence = "medium"
    else:
        confidence = "high"
    warning_text = []
    if missing_payload:
        warning_text.append(f"{len(missing_payload)} row(s) lack payload evidence.")
    if warning_map:
        warning_text.append(f"{len(warning_map)} row(s) already have design/service warnings at current scale.")

    scenarios: list[AiReviewStressScenario] = []
    for multiplier, name in (
        (1.0, "Current evidence baseline"),
        (2.0, "2x growth stress"),
        (5.0, "5x growth stress"),
        (10.0, "10x growth stress"),
    ):
        if multiplier == 1.0:
            summary = (
                f"Modeled daily payload is {_format_data_volume(current_daily_payload_kb)} with "
                f"{payload_coverage}% payload coverage."
            )
        else:
            summary = (
                f"At {multiplier:g}x, modeled daily payload becomes "
                f"{_format_data_volume(current_daily_payload_kb * multiplier)}. "
                "Treat rows with current warnings as first redesign candidates."
            )
        scenarios.append(
            AiReviewStressScenario(
                id=f"STRESS-{int(multiplier):03d}",
                name=name,
                multiplier=multiplier,
                confidence=confidence,
                summary=summary,
                projected_daily_payload_gb=round((current_daily_payload_kb * multiplier) / 1024 / 1024, 3),
                top_integration_ids=_first_ids(top_rows),
                warnings=warning_text if multiplier == 1.0 else warning_text or [
                    "No payload coverage or current-warning caveat was detected."
                ],
            )
        )
    return scenarios


def _remediation_owner(review_area: str) -> Literal["Architect", "Analyst", "Operations", "Executive"]:
    if review_area in {"data_quality", "snapshot_freshness"}:
        return "Analyst"
    if review_area in {"stress_review", "red_team"}:
        return "Operations"
    if review_area == "demo_readiness":
        return "Executive"
    return "Architect"


def _remediation_plan(findings: list[AiReviewFinding]) -> list[AiReviewRemediationStep]:
    actionable = [finding for finding in findings if finding.severity != "positive"]
    plan: list[AiReviewRemediationStep] = []
    for index, finding in enumerate(actionable[:6], start=1):
        plan.append(
            AiReviewRemediationStep(
                id=f"STEP-{index:03d}",
                priority=index,
                owner=_remediation_owner(finding.review_area),
                title=finding.title,
                action=finding.recommendation,
                expected_impact=(
                    "Improves sign-off confidence by resolving a "
                    f"{finding.severity} {finding.review_area.replace('_', ' ')} finding."
                ),
                action_href=finding.action_href,
                finding_ids=[finding.id],
                integration_ids=finding.integration_ids[:MAX_LINKED_INTEGRATIONS],
            )
        )
    return plan


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
    drift = normalized.get("drift")
    if isinstance(drift, dict):
        baseline = drift.get("baseline")
        if isinstance(baseline, dict):
            for key in ("created_at", "updated_at"):
                value = baseline.get(key)
                if isinstance(value, str):
                    baseline[key] = _parse_datetime(value)
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


def serialize_ai_review_baseline(baseline: AiReviewBaseline) -> AiReviewBaselineResponse:
    """Convert a persisted planned baseline into its API response."""

    return AiReviewBaselineResponse(
        id=baseline.id,
        project_id=baseline.project_id,
        scope=cast(Literal["project", "integration"], baseline.scope),
        integration_id=baseline.integration_id,
        created_by=baseline.created_by,
        label=baseline.label,
        note=baseline.note,
        row_count=baseline.row_count,
        is_active=baseline.is_active,
        created_at=baseline.created_at,
        updated_at=baseline.updated_at,
    )


async def _load_job(job_id: str, db: AsyncSession) -> AiReviewJob:
    job = await db.get(AiReviewJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "AI review job not found.", "error_code": "AI_REVIEW_JOB_NOT_FOUND"},
        )
    return job


async def _actor_job_count_today(actor_id: str, db: AsyncSession) -> int:
    start_of_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(
        await db.scalar(
            select(func.count())
            .select_from(AiReviewJob)
            .where(
                AiReviewJob.requested_by == actor_id,
                AiReviewJob.created_at >= start_of_day,
            )
        )
        or 0
    )


async def _enforce_job_quota(actor_id: str, db: AsyncSession) -> None:
    settings = get_settings()
    daily_limit = max(0, settings.AI_REVIEW_DAILY_JOB_LIMIT)
    used = await _actor_job_count_today(actor_id, db)
    if used >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail={
                "detail": "Daily AI review job quota exceeded for this actor.",
                "error_code": "AI_REVIEW_DAILY_QUOTA_EXCEEDED",
                "daily_job_limit": daily_limit,
                "actor_jobs_today": used,
            },
        )


async def get_ai_review_provider_status(actor_id: str, db: AsyncSession) -> AiReviewProviderStatus:
    """Return provider health, quota, and data-policy metadata for the caller."""

    used = await _actor_job_count_today(actor_id or AI_REVIEW_ACTOR_FALLBACK, db)
    payload = provider_status_payload(get_settings(), actor_jobs_today=used)
    return AiReviewProviderStatus.model_validate(payload)


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


async def get_active_ai_review_baseline(
    project_id: str,
    scope: Literal["project", "integration"],
    integration_id: str | None,
    db: AsyncSession,
) -> AiReviewBaselineLookupResponse:
    """Return the active approved planned baseline for one review scope."""

    await _load_project(project_id, db)
    if scope == "integration" and integration_id is None:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "integration_id is required when scope is integration.",
                "error_code": "AI_REVIEW_BASELINE_INTEGRATION_SCOPE_REQUIRES_ID",
            },
        )
    if scope == "project" and integration_id is not None:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "integration_id can only be provided for integration-scoped baselines.",
                "error_code": "AI_REVIEW_BASELINE_PROJECT_SCOPE_REJECTS_INTEGRATION_ID",
            },
        )
    if integration_id is not None:
        await _load_integration(project_id, integration_id, db)
    baseline = await _active_baseline(project_id, scope, integration_id, db)
    return AiReviewBaselineLookupResponse(
        baseline=serialize_ai_review_baseline(baseline) if baseline else None,
    )


async def list_ai_review_baselines(
    project_id: str,
    scope: Literal["project", "integration"],
    integration_id: str | None,
    db: AsyncSession,
    *,
    limit: int = 10,
) -> AiReviewBaselineListResponse:
    """Return active and historical planned baselines for governance review."""

    await _load_project(project_id, db)
    if scope == "integration" and integration_id is None:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "integration_id is required when scope is integration.",
                "error_code": "AI_REVIEW_BASELINE_INTEGRATION_SCOPE_REQUIRES_ID",
            },
        )
    if scope == "project" and integration_id is not None:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "integration_id can only be provided for integration-scoped baselines.",
                "error_code": "AI_REVIEW_BASELINE_PROJECT_SCOPE_REJECTS_INTEGRATION_ID",
            },
        )
    if integration_id is not None:
        await _load_integration(project_id, integration_id, db)

    result = await db.scalars(
        select(AiReviewBaseline)
        .where(
            AiReviewBaseline.project_id == project_id,
            AiReviewBaseline.scope == scope,
            AiReviewBaseline.integration_id == integration_id,
        )
        .order_by(AiReviewBaseline.is_active.desc(), AiReviewBaseline.created_at.desc())
        .limit(limit)
    )
    baselines = result.all()
    return AiReviewBaselineListResponse(
        baselines=[serialize_ai_review_baseline(baseline) for baseline in baselines],
        total=len(baselines),
    )


async def create_ai_review_baseline(
    project_id: str,
    body: AiReviewBaselineCreateRequest,
    actor_id: str,
    db: AsyncSession,
) -> AiReviewBaselineResponse:
    """Approve the current governed state as the active planned baseline."""

    project = await _load_project(project_id, db)
    if body.scope == "integration":
        if body.integration_id is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "integration_id is required when scope is integration.",
                    "error_code": "AI_REVIEW_BASELINE_INTEGRATION_SCOPE_REQUIRES_ID",
                },
            )
        await _load_integration(project_id, body.integration_id, db)
    elif body.integration_id is not None:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "integration_id can only be provided for integration-scoped baselines.",
                "error_code": "AI_REVIEW_BASELINE_PROJECT_SCOPE_REJECTS_INTEGRATION_ID",
            },
        )

    rows = await _load_rows(project_id, db, integration_id=body.integration_id if body.scope == "integration" else None)
    latest_snapshot = await _latest_volumetry_snapshot(project_id, db)
    latest_dashboard = await _latest_dashboard_snapshot(project_id, db)
    payload = _baseline_payload(
        project=project,
        rows=rows,
        scope=body.scope,
        integration_id=body.integration_id,
        latest_snapshot=latest_snapshot,
        latest_dashboard=latest_dashboard,
    )

    existing = await db.scalars(
        select(AiReviewBaseline).where(
            AiReviewBaseline.project_id == project_id,
            AiReviewBaseline.scope == body.scope,
            AiReviewBaseline.is_active.is_(True),
            (
                AiReviewBaseline.integration_id == body.integration_id
                if body.scope == "integration"
                else AiReviewBaseline.integration_id.is_(None)
            ),
        )
    )
    for baseline in existing.all():
        baseline.is_active = False

    baseline = AiReviewBaseline(
        project_id=project_id,
        scope=body.scope,
        integration_id=body.integration_id,
        created_by=actor_id or AI_REVIEW_ACTOR_FALLBACK,
        label=body.label or _format_baseline_label(body.scope, body.integration_id),
        note=body.note,
        baseline_payload=payload,
        row_count=len(rows),
        is_active=True,
    )
    db.add(baseline)
    await db.flush()
    await db.refresh(baseline)
    response = serialize_ai_review_baseline(baseline)
    await audit_service.emit(
        event_type="ai_review_baseline_created",
        entity_type="ai_review_baseline",
        entity_id=baseline.id,
        actor_id=baseline.created_by,
        old_value=None,
        new_value=response.model_dump(mode="json"),
        project_id=project_id,
        db=db,
        correlation_id=baseline.id,
    )
    return response


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

    requested_by = actor_id or AI_REVIEW_ACTOR_FALLBACK
    await _enforce_job_quota(requested_by, db)
    input_payload = cast(dict[str, object], sanitize_for_json(body.model_dump()))
    job = AiReviewJob(
        project_id=project_id,
        requested_by=requested_by,
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
    old_value: dict[str, object] = {"status": _status_value(job)}
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
    old_value: dict[str, object] = {"status": _status_value(job), "error_details": job.error_details}
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
    active_baseline = await _active_baseline(project_id, scope, integration_id if scope == "integration" else None, db)
    scoped_ids = {row.id for row in rows}
    warning_map = _design_warning_map(latest_snapshot, allowed_ids=scoped_ids if scope == "integration" else None)
    drift = _drift_report(
        baseline=active_baseline,
        project_id=project_id,
        rows=rows,
    )
    service_rules = await service_rule_service.load_service_rule_bundle(db)

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
    ev_baseline = _evidence(
        evidence,
        label="Planned baseline",
        detail=(
            f"{drift.baseline.label} · {drift.item_count} drift item(s)."
            if drift.baseline
            else "No active approved planned baseline exists for this scope."
        ),
        source="ai_review_baselines",
        entity_type="ai_review_baseline" if drift.baseline else "project",
        entity_id=drift.baseline.id if drift.baseline else project_id,
        href=f"/projects/{project_id}",
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
    _evidence(
        evidence,
        label="Service Product rules",
        detail=(
            f"{service_rules.version}; freshness={service_rules.freshness_status}; "
            f"stale evidence={service_rules.stale_evidence_count}; "
            f"open findings={service_rules.open_findings_count}."
        ),
        source="service_product_library",
        entity_type="service_rule_bundle",
        entity_id=service_rules.version,
        href="/admin/services",
    )

    findings: list[AiReviewFinding] = []
    if drift.status == "no_baseline":
        ids = [ev_baseline.id]
        findings.append(
            _finding(
                "planned-baseline-missing",
                "low",
                "planned_drift",
                "No approved planned baseline exists",
                "The review can recommend improvements, but it cannot detect planned-versus-actual drift yet.",
                ids,
                _evidence_lines(evidence, ids),
                "planned_baseline=none",
                "A reviewed project should have an explicit planned baseline before drift governance is expected.",
                "Save the current approved state as the planned baseline, then re-run AI Review.",
                "Save planned baseline",
                f"/projects/{project_id}",
            )
        )
    elif drift.item_count > 0:
        ids = [ev_baseline.id]
        severity: AiReviewSeverity = "critical" if drift.worst_severity == "critical" else "high"
        findings.append(
            _finding(
                "planned-actual-drift",
                severity,
                "planned_drift",
                "Current state has drifted from the approved plan",
                drift.summary,
                ids,
                [*_evidence_lines(evidence, ids), *[item.detail for item in drift.items[:3]]],
                f"drift_status={drift.status}, drift_items={drift.item_count}",
                "Actual project state should match the active planned baseline or be re-approved as the new plan.",
                "Review the drift items and either restore the planned design or save a new planned baseline.",
                "Review drift",
                f"/projects/{project_id}",
                [item.integration_id for item in drift.items if item.integration_id][:MAX_LINKED_INTEGRATIONS],
            )
        )
    else:
        ids = [ev_baseline.id]
        findings.append(
            _finding(
                "planned-actual-aligned",
                "positive",
                "planned_drift",
                "Current state matches the approved plan",
                "No planned-versus-actual drift was detected for this review scope.",
                ids,
                _evidence_lines(evidence, ids),
                "drift_items=0",
                "Actual project state should remain aligned with the active planned baseline.",
                "Keep the baseline current whenever an architect approves material design changes.",
                "Open dashboard",
                f"/projects/{project_id}",
            )
        )
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
        payload_severity: AiReviewSeverity = "high" if _pct(total - len(missing_payload), total) < 60 else "medium"
        ids = [ev_coverage.id]
        findings.append(
            _finding(
                "payload-coverage-gap",
                payload_severity,
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
        AiReviewMetric(
            label="Planned drift",
            value="No baseline" if drift.status == "no_baseline" else str(drift.item_count),
            detail=drift.summary,
        ),
        AiReviewMetric(
            label="Service rules",
            value=service_rules.freshness_status.replace("_", " ").title(),
            detail=f"Runtime decisions use {service_rules.version} from {service_rules.source}.",
        ),
    ]
    decision_brief = _decision_brief(score=score, label=label, findings=findings, drift=drift)
    topology_insights = _topology_insights(project_id=project_id, rows=rows, warning_map=warning_map)
    stress_scenarios = _stress_scenarios(rows=rows, warning_map=warning_map)
    remediation_plan = _remediation_plan(findings)
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
        f"planned_baseline={drift.baseline.id if drift.baseline else 'none'}",
        f"planned_drift_status={drift.status}",
        f"planned_drift_items={drift.item_count}",
        f"service_rules_version={service_rules.version}",
        f"service_rules_source={service_rules.source}",
        f"service_rules_freshness={service_rules.freshness_status}",
        f"service_rules_stale_evidence={service_rules.stale_evidence_count}",
        f"service_rules_open_findings={service_rules.open_findings_count}",
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
            decision_brief=decision_brief.model_dump(mode="json"),
            topology_insights=[item.model_dump(mode="json") for item in topology_insights],
            stress_scenarios=[item.model_dump(mode="json") for item in stress_scenarios],
            remediation_plan=[item.model_dump(mode="json") for item in remediation_plan],
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
        decision_brief=decision_brief,
        topology_insights=topology_insights,
        stress_scenarios=stress_scenarios,
        remediation_plan=remediation_plan,
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
        drift=drift,
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
    old_value: dict[str, object] = {"status": _status_value(job)}
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
    old_value: dict[str, object] = {"accepted_recommendations": job.accepted_recommendations or []}
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
    old_value: dict[str, object] = {"accepted_recommendations": job.accepted_recommendations or []}
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


def _completed_review_for_job(job: AiReviewJob) -> AiReviewResponse:
    if _status_value(job) != "completed" or job.result_payload is None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "AI review comparison/export requires completed jobs with result payloads.",
                "error_code": "AI_REVIEW_JOB_RESULT_REQUIRED",
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
    return review


def _critical_high_count(review: AiReviewResponse) -> int:
    return sum(1 for finding in review.findings if finding.severity in {"critical", "high"})


async def compare_ai_review_jobs(
    project_id: str,
    base_job_id: str,
    target_job_id: str,
    db: AsyncSession,
) -> AiReviewJobCompareResponse:
    """Compare two completed review jobs for evolution/regression analysis."""

    await _load_project(project_id, db)
    base_job = await _load_job(base_job_id, db)
    target_job = await _load_job(target_job_id, db)
    if base_job.project_id != project_id or target_job.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail={"detail": "AI review job not found for this project.", "error_code": "AI_REVIEW_JOB_NOT_FOUND"},
        )
    base_review = _completed_review_for_job(base_job)
    target_review = _completed_review_for_job(target_job)
    base_findings = {finding.id: finding.title for finding in base_review.findings}
    target_findings = {finding.id: finding.title for finding in target_review.findings}
    added_ids = sorted(set(target_findings) - set(base_findings))
    resolved_ids = sorted(set(base_findings) - set(target_findings))
    persistent_ids = sorted(set(base_findings) & set(target_findings))
    readiness_delta = target_review.readiness_score - base_review.readiness_score
    critical_high_delta = _critical_high_count(target_review) - _critical_high_count(base_review)
    if readiness_delta > 0 and critical_high_delta <= 0:
        summary = f"Readiness improved by {readiness_delta} point(s) with no increase in critical/high findings."
    elif readiness_delta < 0 or critical_high_delta > 0:
        summary = (
            f"Readiness changed by {readiness_delta} point(s); critical/high finding count changed by "
            f"{critical_high_delta}."
        )
    else:
        summary = "Readiness is stable against the selected baseline review job."
    return AiReviewJobCompareResponse(
        project_id=project_id,
        base_job_id=base_job_id,
        target_job_id=target_job_id,
        base_readiness_score=base_review.readiness_score,
        target_readiness_score=target_review.readiness_score,
        readiness_score_delta=readiness_delta,
        base_readiness_label=base_review.readiness_label,
        target_readiness_label=target_review.readiness_label,
        finding_count_delta=len(target_review.findings) - len(base_review.findings),
        critical_high_delta=critical_high_delta,
        added_findings=[target_findings[finding_id] for finding_id in added_ids],
        resolved_findings=[base_findings[finding_id] for finding_id in resolved_ids],
        persistent_findings=[target_findings[finding_id] for finding_id in persistent_ids],
        summary=summary,
    )


def render_ai_review_markdown(job: AiReviewJob) -> str:
    """Render one completed AI review job as portable Markdown evidence."""

    review = _completed_review_for_job(job)
    lines = [
        f"# AI Review Brief - {review.project_name}",
        "",
        f"- Job ID: `{job.id}`",
        f"- Project ID: `{job.project_id}`",
        f"- Scope: `{review.scope}`",
        f"- Generated: `{review.generated_at.isoformat()}`",
        f"- Engine: `{review.engine}`",
        f"- LLM status: `{review.llm_status}`",
        "",
        "## Decision Brief",
        "",
        f"- Sign-off status: **{review.decision_brief.signoff_status.replace('_', ' ')}**",
        f"- Readiness: **{review.readiness_label}** ({review.readiness_score}/100)",
        f"- Headline: {review.decision_brief.headline}",
        f"- Primary risk: {review.decision_brief.primary_risk}",
        f"- Next action: {review.decision_brief.recommended_next_action}",
        "",
        "## Summary",
        "",
        review.llm_summary or review.summary,
        "",
        "## Metrics",
        "",
    ]
    lines.extend(f"- {metric.label}: {metric.value} ({metric.detail})" for metric in review.metrics)
    lines.extend(["", "## Topology Intelligence", ""])
    if review.topology_insights:
        for insight in review.topology_insights:
            lines.append(f"- {insight.title}: {insight.summary} `{insight.metric}`")
    else:
        lines.append("- No topology insight was generated for this scope.")
    lines.extend(["", "## Stress Scenarios", ""])
    for scenario in review.stress_scenarios:
        lines.append(
            f"- {scenario.name} ({scenario.multiplier:g}x, {scenario.confidence} confidence): "
            f"{scenario.summary}"
        )
    lines.extend(["", "## Remediation Plan", ""])
    if review.remediation_plan:
        for step in review.remediation_plan:
            lines.append(f"{step.priority}. {step.title} — {step.action} Owner: {step.owner}.")
    else:
        lines.append("- No remediation steps were generated.")
    lines.extend(["", "## Findings", ""])
    for finding in review.findings:
        lines.append(
            f"- [{finding.severity.upper()}] {finding.title}: {finding.recommendation} "
            f"Evidence: {', '.join(finding.evidence_ids) or 'none'}."
        )
    lines.extend(["", "## Evidence Registry", ""])
    for evidence in review.evidence:
        lines.append(f"- {evidence.id}: {evidence.label} — {evidence.detail}")
    lines.extend(
        [
            "",
            "## Governance",
            "",
            "- Export generated from persisted AI Review evidence.",
            "- Applying recommendations remains a separate audited action.",
        ]
    )
    return "\n".join(lines) + "\n"


async def export_ai_review_markdown(job_id: str, actor_id: str, db: AsyncSession) -> tuple[str, str, str]:
    """Return Markdown content for one job and audit the export event."""

    job = await _load_job(job_id, db)
    content = render_ai_review_markdown(job)
    filename = f"{job.project_id}-{job.id}-ai-review.md"
    await audit_service.emit(
        event_type="ai_review_exported",
        entity_type="ai_review_job",
        entity_id=job.id,
        actor_id=actor_id or AI_REVIEW_ACTOR_FALLBACK,
        old_value=None,
        new_value={"format": "md", "filename": filename},
        project_id=job.project_id,
        db=db,
        correlation_id=job.id,
    )
    return content, filename, job.project_id
