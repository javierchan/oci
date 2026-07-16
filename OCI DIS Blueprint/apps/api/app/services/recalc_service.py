"""Project recalculation service and volumetry snapshot access helpers."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.calc_engine import (
    Assumptions,
    CERTIFICATION_VERSION,
    IntegrationInput,
    composition_issues,
    consolidate_project,
    executions_per_day as calc_executions_per_day,
    di_data_processed_gb,
    functions_execution_units,
    functions_invocations_per_month,
    get_pattern_certification,
    oic_billing_messages_per_month,
    payload_per_hour_kb as calc_payload_per_hour_kb,
    payload_per_month_kb,
    streaming_gb_per_month,
    streaming_partition_count,
)
from app.models import AssumptionSet, CatalogIntegration, DictionaryOption, Project, VolumetrySnapshot
from app.schemas.volumetry import (
    ConsolidatedMetrics,
    DIMetrics,
    FunctionsMetrics,
    OICMetrics,
    QueueMetrics,
    RecalculationJobStatusResponse,
    ScopedRecalculationRequest,
    StreamingMetrics,
    VolumetrySnapshotListResponse,
    VolumetrySnapshotResponse,
    VolumetrySnapshotRowResultsResponse,
    VolumetrySnapshotSummary,
)
from app.services import audit_service, service_rule_service
from app.services.canvas_interoperability import build_design_constraint_messages
from app.services.service_rule_service import ServiceRuleBundle
from app.workers.celery_app import celery_app


@dataclass(frozen=True)
class DraftIntegrationOverride:
    """Unsaved integration design values used by an in-memory recalculation."""

    integration_id: str
    core_tools: str
    additional_tools_overlays: str


@dataclass(frozen=True)
class ProjectVolumetryCalculation:
    """Deterministic project volumetry result before persistence concerns."""

    assumption_set_version: str
    integrations: list[CatalogIntegration]
    row_results: dict[str, dict[str, object]]
    consolidated: dict[str, object]
    metadata: dict[str, object]


def _to_assumptions(
    assumption_set: AssumptionSet,
    service_rules: ServiceRuleBundle = service_rule_service.EMPTY_SERVICE_RULE_BUNDLE,
) -> Assumptions:
    allowed_keys = {field.name for field in fields(Assumptions)}
    filtered = {
        key: value
        for key, value in assumption_set.assumptions.items()
        if key in allowed_keys
    }
    return service_rule_service.apply_service_rules(Assumptions(**filtered), service_rules)


def _integration_input(row: CatalogIntegration) -> IntegrationInput:
    return IntegrationInput(
        integration_id=row.id,
        payload_per_execution_kb=row.payload_per_execution_kb,
        executions_per_day=row.executions_per_day,
        trigger_type=row.trigger_type,
        is_real_time=row.is_real_time,
        core_tools=row.core_tools,
        response_size_kb=row.response_size_kb,
        is_fan_out=row.is_fan_out,
        fan_out_targets=row.fan_out_targets,
    )


async def _frequency_map(db: AsyncSession) -> dict[str, float | None]:
    options = (
        await db.scalars(
            select(DictionaryOption).where(
                DictionaryOption.category == "FREQUENCY",
                DictionaryOption.is_active.is_(True),
            )
        )
    ).all()
    return {option.value: option.executions_per_day for option in options}


def _resolved_executions_per_day(
    row: CatalogIntegration,
    frequency_map: dict[str, float | None],
) -> float | None:
    if row.frequency and row.frequency in frequency_map:
        return frequency_map[row.frequency]
    if row.frequency:
        calc_result = calc_executions_per_day(row.frequency)
        if calc_result is not None:
            return calc_result.value
    return row.executions_per_day


def _resolved_payload_per_hour_kb(
    payload_per_execution: float | None,
    executions_day: float | None,
    stored_value: float | None,
) -> float | None:
    if payload_per_execution is not None and executions_day is not None:
        return calc_payload_per_hour_kb(payload_per_execution, executions_day).value
    return stored_value


def _integration_input_with_overrides(
    row: CatalogIntegration,
    executions_day: float | None,
    core_tools: str | None = None,
) -> IntegrationInput:
    base = _integration_input(row)
    return IntegrationInput(
        integration_id=base.integration_id,
        payload_per_execution_kb=base.payload_per_execution_kb,
        executions_per_day=executions_day,
        trigger_type=base.trigger_type,
        is_real_time=base.is_real_time,
        core_tools=core_tools if core_tools is not None else base.core_tools,
        response_size_kb=base.response_size_kb,
        is_fan_out=base.is_fan_out,
        fan_out_targets=base.fan_out_targets,
    )


def _design_constraint_warnings(
    row: CatalogIntegration,
    assumptions: Assumptions,
    service_rules: ServiceRuleBundle,
    override: DraftIntegrationOverride | None = None,
) -> list[str]:
    return build_design_constraint_messages(
        core_tools=override.core_tools if override else row.core_tools,
        additional_tools_overlays=(
            override.additional_tools_overlays if override else row.additional_tools_overlays
        ),
        assumptions=assumptions,
        payload_kb=row.payload_per_execution_kb,
        trigger_type=row.trigger_type,
        is_real_time=row.is_real_time,
        source_technology=row.source_technology,
        destination_technology=row.destination_technology_1,
        integration_type=row.type,
        service_rules=service_rules,
    )


def _serialize_consolidated(consolidated: dict[str, object]) -> ConsolidatedMetrics:
    oic = dict(cast(dict[str, Any], consolidated.get("oic", {})))
    if "total_billing_msgs_per_month" not in oic and "total_billing_msgs_month" in oic:
        oic["total_billing_msgs_per_month"] = oic["total_billing_msgs_month"]
    if "total_billing_msgs_month" not in oic and "total_billing_msgs_per_month" in oic:
        oic["total_billing_msgs_month"] = oic["total_billing_msgs_per_month"]
    data_integration = cast(dict[str, Any], consolidated.get("data_integration", {}))
    functions = cast(dict[str, Any], consolidated.get("functions", {}))
    streaming = cast(dict[str, Any], consolidated.get("streaming", {}))
    queue = cast(dict[str, Any], consolidated.get("queue", {}))
    return ConsolidatedMetrics(
        oic=OICMetrics(**oic),
        data_integration=DIMetrics(**data_integration),
        functions=FunctionsMetrics(**functions),
        streaming=StreamingMetrics(**streaming),
        queue=QueueMetrics(**queue),
    )


def serialize_consolidated_calculation(consolidated: dict[str, object]) -> ConsolidatedMetrics:
    """Expose a typed consolidated result for side-effect-free calculation consumers."""

    return _serialize_consolidated(consolidated)


def serialize_snapshot(snapshot: VolumetrySnapshot) -> VolumetrySnapshotResponse:
    """Convert a snapshot model into a response schema."""

    return VolumetrySnapshotResponse(
        snapshot_id=snapshot.id,
        project_id=snapshot.project_id,
        assumption_set_version=snapshot.assumption_set_version,
        triggered_by=snapshot.triggered_by,
        row_results=snapshot.row_results,
        consolidated=_serialize_consolidated(snapshot.consolidated),
        metadata=snapshot.snapshot_metadata,
        created_at=snapshot.created_at,
    )


def serialize_snapshot_summary(snapshot: VolumetrySnapshot) -> VolumetrySnapshotSummary:
    """Convert a snapshot model into a lightweight list response."""

    return VolumetrySnapshotSummary(
        snapshot_id=snapshot.id,
        project_id=snapshot.project_id,
        assumption_set_version=snapshot.assumption_set_version,
        triggered_by=snapshot.triggered_by,
        consolidated=_serialize_consolidated(snapshot.consolidated),
        metadata=snapshot.snapshot_metadata,
        row_result_count=len(snapshot.row_results or {}),
        created_at=snapshot.created_at,
    )


async def calculate_project_volumetry(
    project_id: str,
    db: AsyncSession,
    draft_override: DraftIntegrationOverride | None = None,
) -> ProjectVolumetryCalculation:
    """Calculate project volumetry, optionally replacing one unsaved canvas design."""

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"},
        )
    assumption_set = await db.scalar(select(AssumptionSet).where(AssumptionSet.is_default.is_(True)))
    if assumption_set is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Default assumption set not found", "error_code": "DEFAULT_ASSUMPTION_SET_NOT_FOUND"},
        )
    integrations = (
        await db.scalars(
            select(CatalogIntegration)
            .where(CatalogIntegration.project_id == project_id)
            .order_by(CatalogIntegration.seq_number, CatalogIntegration.created_at)
        )
    ).all()

    service_rules = await service_rule_service.load_service_rule_bundle(db)
    assumptions = _to_assumptions(assumption_set, service_rules)
    frequency_map = await _frequency_map(db)
    derived_inputs: dict[str, tuple[float | None, float | None]] = {}
    row_inputs: list[IntegrationInput] = []
    for row in integrations:
        executions_day = _resolved_executions_per_day(row, frequency_map)
        payload_hour = _resolved_payload_per_hour_kb(
            row.payload_per_execution_kb,
            executions_day,
            row.payload_per_hour_kb,
        )
        derived_inputs[row.id] = (executions_day, payload_hour)
        override = draft_override if draft_override and draft_override.integration_id == row.id else None
        row_inputs.append(
            _integration_input_with_overrides(
                row,
                executions_day,
                override.core_tools if override else None,
            )
        )
    consolidated = consolidate_project(row_inputs, assumptions)
    row_results: dict[str, dict[str, object]] = {}

    di_total_gb = 0.0
    streaming_total_gb = 0.0
    peak_streaming_partitions = 0
    certified_pattern_ids: set[str] = set()
    uncertified_pattern_ids: set[str] = set()
    noncompliant_integration_count = 0

    for row in integrations:
        executions_day, payload_hour = derived_inputs[row.id]
        override = draft_override if draft_override and draft_override.integration_id == row.id else None
        monthly_payload_kb = (
            payload_per_month_kb(row.payload_per_execution_kb, executions_day, assumptions).value
            if row.payload_per_execution_kb is not None and executions_day is not None
            else None
        )
        oic_msgs_month = (
            oic_billing_messages_per_month(
                row.payload_per_execution_kb,
                row.response_size_kb or 0.0,
                executions_day,
                assumptions,
            ).value
            if row.payload_per_execution_kb is not None and executions_day is not None
            else None
        )
        functions_invocations = functions_invocations_per_month(
            _integration_input_with_overrides(
                row,
                executions_day,
                override.core_tools if override else None,
            ),
            assumptions,
        ).value
        functions_units = (
            functions_execution_units(
                functions_invocations or 0.0,
                assumptions.functions_default_duration_ms,
                assumptions.functions_default_memory_mb,
                assumptions.functions_default_concurrency,
            ).value
            if functions_invocations is not None
            else None
        )
        di_gb_month = (
            di_data_processed_gb(monthly_payload_kb).value if monthly_payload_kb is not None else None
        )
        streaming_gb_month = (
            streaming_gb_per_month(monthly_payload_kb).value if monthly_payload_kb is not None else None
        )
        streaming_partitions = (
            streaming_partition_count((payload_hour or 0.0) / 3600.0, assumptions).value
            if payload_hour is not None
            else None
        )

        if di_gb_month:
            di_total_gb += di_gb_month
        if streaming_gb_month:
            streaming_total_gb += streaming_gb_month
        if streaming_partitions:
            peak_streaming_partitions = max(peak_streaming_partitions, int(streaming_partitions))

        design_constraint_warnings = _design_constraint_warnings(
            row,
            assumptions,
            service_rules,
            override,
        )
        certification = get_pattern_certification(row.selected_pattern)
        effective_core_tools = override.core_tools if override else row.core_tools
        effective_overlays = (
            override.additional_tools_overlays if override else row.additional_tools_overlays
        )
        certification_issues = list(
            composition_issues(row.selected_pattern, effective_core_tools, effective_overlays)
        )
        if certification is not None:
            certified_pattern_ids.add(certification.pattern_id)
        elif row.selected_pattern:
            uncertified_pattern_ids.add(row.selected_pattern)
        if certification_issues:
            noncompliant_integration_count += 1
        row_results[row.id] = {
            "executions_per_day": executions_day,
            "payload_per_hour_kb": payload_hour,
            "oic_billing_msgs_month": oic_msgs_month,
            "functions_invocations_month": functions_invocations,
            "functions_execution_units_gb_s": functions_units,
            "data_integration_gb_month": di_gb_month,
            "streaming_gb_month": streaming_gb_month,
            "streaming_partition_count": streaming_partitions,
            "design_constraint_warnings": design_constraint_warnings,
            "pattern_certification": {
                "status": "certified" if certification is not None else "unverified",
                "version": certification.certification_version if certification else None,
                "sizing_strategy": certification.sizing_strategy if certification else None,
                "commercial_service_ids": (
                    list(certification.commercial_service_ids) if certification else []
                ),
                "external_dependencies": (
                    list(certification.external_dependencies) if certification else []
                ),
                "composition_compliant": not certification_issues,
                "composition_issues": certification_issues,
            },
        }

    consolidated["data_integration"]["data_processed_gb_month"] = di_total_gb
    consolidated["streaming"]["total_gb_month"] = streaming_total_gb
    consolidated["streaming"]["partition_count"] = peak_streaming_partitions

    return ProjectVolumetryCalculation(
        assumption_set_version=assumption_set.version,
        integrations=list(integrations),
        row_results=row_results,
        consolidated=consolidated,
        metadata={
            "integration_count": len(integrations),
            "service_rules": service_rules.metadata(),
            "pattern_certification": {
                "version": CERTIFICATION_VERSION,
                "certified_pattern_ids": sorted(certified_pattern_ids),
                "uncertified_pattern_ids": sorted(uncertified_pattern_ids),
                "noncompliant_integration_count": noncompliant_integration_count,
            },
            "draft_override_integration_id": draft_override.integration_id if draft_override else None,
            "persisted": False,
        },
    )


async def recalculate_project(project_id: str, actor_id: str, db: AsyncSession) -> VolumetrySnapshot:
    """Compute and persist a fresh immutable volumetry snapshot for the whole project."""

    calculation = await calculate_project_volumetry(project_id, db)

    snapshot = VolumetrySnapshot(
        project_id=project_id,
        assumption_set_version=calculation.assumption_set_version,
        triggered_by=actor_id,
        row_results=calculation.row_results,
        consolidated=calculation.consolidated,
        snapshot_metadata={
            "integration_count": calculation.metadata["integration_count"],
            "service_rules": calculation.metadata["service_rules"],
            "pattern_certification": calculation.metadata["pattern_certification"],
        },
    )
    db.add(snapshot)
    await db.flush()
    await audit_service.emit(
        event_type="recalculation",
        entity_type="project",
        entity_id=project_id,
        actor_id=actor_id,
        old_value=None,
        new_value={
            "snapshot_id": snapshot.id,
            "assumption_set_version": calculation.assumption_set_version,
            "service_rules": calculation.metadata["service_rules"],
        },
        project_id=project_id,
        db=db,
    )
    from app.services import dashboard_service

    await dashboard_service.create_dashboard_snapshot(project_id=project_id, volumetry_snapshot=snapshot, db=db)
    await db.refresh(snapshot)
    return snapshot


async def list_snapshots(project_id: str, db: AsyncSession) -> VolumetrySnapshotListResponse:
    """List volumetry snapshots for a project."""

    result = await db.scalars(
        select(VolumetrySnapshot)
        .where(VolumetrySnapshot.project_id == project_id)
        .order_by(VolumetrySnapshot.created_at.desc())
    )
    return VolumetrySnapshotListResponse(
        snapshots=[serialize_snapshot_summary(snapshot) for snapshot in result.all()]
    )


async def get_snapshot(project_id: str, snapshot_id: str, db: AsyncSession) -> VolumetrySnapshotResponse:
    """Load one volumetry snapshot for a project."""

    snapshot = await db.scalar(
        select(VolumetrySnapshot).where(
            VolumetrySnapshot.project_id == project_id,
            VolumetrySnapshot.id == snapshot_id,
        )
    )
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Volumetry snapshot not found", "error_code": "VOLUMETRY_SNAPSHOT_NOT_FOUND"},
        )
    return serialize_snapshot(snapshot)


async def list_snapshot_rows(
    project_id: str,
    snapshot_id: str,
    page: int,
    page_size: int,
    db: AsyncSession,
) -> VolumetrySnapshotRowResultsResponse:
    """Return a paginated view of row-level metrics for one snapshot."""

    snapshot = await db.scalar(
        select(VolumetrySnapshot).where(
            VolumetrySnapshot.project_id == project_id,
            VolumetrySnapshot.id == snapshot_id,
        )
    )
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Volumetry snapshot not found", "error_code": "VOLUMETRY_SNAPSHOT_NOT_FOUND"},
        )

    ordered_results = [
        {"integration_id": integration_id, **metrics}
        for integration_id, metrics in sorted(snapshot.row_results.items())
        if isinstance(metrics, dict)
    ]
    total = len(ordered_results)
    offset = (page - 1) * page_size
    return VolumetrySnapshotRowResultsResponse(
        rows=ordered_results[offset : offset + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_consolidated_metrics(project_id: str, snapshot_id: str, db: AsyncSession) -> ConsolidatedMetrics:
    """Load consolidated metrics for one snapshot."""

    snapshot = await db.scalar(
        select(VolumetrySnapshot).where(
            VolumetrySnapshot.project_id == project_id,
            VolumetrySnapshot.id == snapshot_id,
        )
    )
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Volumetry snapshot not found", "error_code": "VOLUMETRY_SNAPSHOT_NOT_FOUND"},
        )
    return _serialize_consolidated(snapshot.consolidated)


async def recalculate_scoped(
    project_id: str,
    request: ScopedRecalculationRequest,
    db: AsyncSession,
) -> RecalculationJobStatusResponse:
    """Run a full recalculation while annotating the trigger as scoped to specific rows."""

    unique_ids = await validate_scoped_integration_ids(project_id, request.integration_ids, db)
    snapshot = await recalculate_project(project_id, request.actor_id, db)
    metadata = dict(snapshot.snapshot_metadata or {})
    metadata["scope"] = "scoped"
    metadata["integration_ids"] = unique_ids
    snapshot.snapshot_metadata = metadata
    await db.flush()
    await db.refresh(snapshot)
    return RecalculationJobStatusResponse(
        job_id=snapshot.id,
        project_id=project_id,
        status="completed",
        snapshot_id=snapshot.id,
        scope="scoped",
        integration_ids=unique_ids,
        created_at=snapshot.created_at,
    )


async def validate_scoped_integration_ids(
    project_id: str,
    integration_ids: list[str],
    db: AsyncSession,
) -> list[str]:
    """Validate and normalize the list of scoped integration IDs."""

    unique_ids = list(dict.fromkeys(integration_ids))
    if not unique_ids:
        raise HTTPException(
            status_code=400,
            detail={"detail": "At least one integration ID is required.", "error_code": "INTEGRATION_IDS_REQUIRED"},
        )

    matching_ids = set(
        (
            await db.scalars(
                select(CatalogIntegration.id).where(
                    CatalogIntegration.project_id == project_id,
                    CatalogIntegration.id.in_(unique_ids),
                )
            )
        ).all()
    )
    missing_ids = [integration_id for integration_id in unique_ids if integration_id not in matching_ids]
    if missing_ids:
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "One or more catalog integrations were not found in the project.",
                "error_code": "CATALOG_INTEGRATION_NOT_FOUND",
                "integration_ids": missing_ids,
            },
        )
    return unique_ids


def build_recalculation_job_response(
    job_id: str,
    project_id: str,
    status: str,
    *,
    snapshot_id: str | None = None,
    scope: str = "project",
    integration_ids: list[str] | None = None,
    created_at: Any = None,
) -> RecalculationJobStatusResponse:
    """Build a normalized job payload for queued or historical recalculation flows."""

    return RecalculationJobStatusResponse(
        job_id=job_id,
        project_id=project_id,
        status=status,
        snapshot_id=snapshot_id,
        scope=scope,
        integration_ids=integration_ids or [],
        created_at=created_at,
    )


async def get_recalculation_job_status(
    project_id: str,
    job_id: str,
    db: AsyncSession,
) -> RecalculationJobStatusResponse:
    """Return the current status for a queued or historical recalculation job."""

    task_result = celery_app.AsyncResult(job_id)
    if task_result.state in {"PENDING", "RECEIVED", "STARTED", "RETRY"}:
        normalized = task_result.state.lower()
        if normalized == "received":
            normalized = "pending"
        return build_recalculation_job_response(job_id, project_id, normalized)
    if task_result.state == "FAILURE":
        return build_recalculation_job_response(job_id, project_id, "failed")
    if task_result.state == "SUCCESS":
        payload = cast(dict[str, Any], task_result.result or {})
        snapshot_id = cast(str | None, payload.get("snapshot_id"))
        scope = cast(str, payload.get("scope", "project"))
        result_integration_ids = cast(list[str], payload.get("integration_ids", []))
        created_at = payload.get("created_at")
        if snapshot_id is not None:
            snapshot = await db.scalar(
                select(VolumetrySnapshot).where(
                    VolumetrySnapshot.project_id == project_id,
                    VolumetrySnapshot.id == snapshot_id,
                )
            )
            if snapshot is not None:
                metadata = snapshot.snapshot_metadata or {}
                snapshot_integration_ids = metadata.get("integration_ids")
                return build_recalculation_job_response(
                    job_id=job_id,
                    project_id=project_id,
                    status="completed",
                    snapshot_id=snapshot.id,
                    scope="scoped" if metadata.get("scope") == "scoped" else scope,
                    integration_ids=snapshot_integration_ids if isinstance(snapshot_integration_ids, list) else result_integration_ids,
                    created_at=snapshot.created_at,
                )
        return build_recalculation_job_response(
            job_id=job_id,
            project_id=project_id,
            status="completed",
            snapshot_id=snapshot_id,
            scope=scope,
            integration_ids=result_integration_ids,
            created_at=created_at,
        )

    snapshot = await db.scalar(
        select(VolumetrySnapshot).where(
            VolumetrySnapshot.project_id == project_id,
            VolumetrySnapshot.id == job_id,
        )
    )
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Recalculation job not found", "error_code": "RECALCULATION_JOB_NOT_FOUND"},
        )

    metadata = snapshot.snapshot_metadata or {}
    stored_integration_ids = metadata.get("integration_ids")
    return build_recalculation_job_response(
        job_id=snapshot.id,
        project_id=project_id,
        status="completed",
        snapshot_id=snapshot.id,
        scope="scoped" if metadata.get("scope") == "scoped" else "project",
        integration_ids=cast(list[str], stored_integration_ids) if isinstance(stored_integration_ids, list) else [],
        created_at=snapshot.created_at,
    )
