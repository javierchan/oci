"""Project recalculation service and volumetry snapshot access helpers."""

from __future__ import annotations

from dataclasses import fields

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.calc_engine import (
    Assumptions,
    IntegrationInput,
    consolidate_project,
    di_data_processed_gb,
    functions_execution_units,
    functions_invocations_per_month,
    oic_billing_messages_per_month,
    payload_per_month_kb,
    streaming_gb_per_month,
    streaming_partition_count,
)
from app.models import AssumptionSet, CatalogIntegration, Project, VolumetrySnapshot
from app.schemas.volumetry import (
    ConsolidatedMetrics,
    DIMetrics,
    FunctionsMetrics,
    OICMetrics,
    QueueMetrics,
    StreamingMetrics,
    VolumetrySnapshotListResponse,
    VolumetrySnapshotResponse,
)
from app.services import audit_service


def _to_assumptions(assumption_set: AssumptionSet) -> Assumptions:
    allowed_keys = {field.name for field in fields(Assumptions)}
    filtered = {
        key: value
        for key, value in assumption_set.assumptions.items()
        if key in allowed_keys
    }
    return Assumptions(**filtered)


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
        selected_pattern=row.selected_pattern,
    )


def _serialize_consolidated(consolidated: dict[str, object]) -> ConsolidatedMetrics:
    oic = consolidated.get("oic", {})
    data_integration = consolidated.get("data_integration", {})
    functions = consolidated.get("functions", {})
    streaming = consolidated.get("streaming", {})
    queue = consolidated.get("queue", {})
    return ConsolidatedMetrics(
        oic=OICMetrics(**oic),
        data_integration=DIMetrics(**data_integration),
        functions=FunctionsMetrics(**functions),
        streaming=StreamingMetrics(**streaming),
        queue=QueueMetrics(**queue),
    )


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


async def recalculate_project(project_id: str, actor_id: str, db: AsyncSession) -> VolumetrySnapshot:
    """Compute a fresh immutable volumetry snapshot for the whole project."""

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

    assumptions = _to_assumptions(assumption_set)
    row_inputs = [_integration_input(row) for row in integrations]
    consolidated = consolidate_project(row_inputs, assumptions)
    row_results: dict[str, dict[str, object]] = {}

    di_total_gb = 0.0
    streaming_total_gb = 0.0
    peak_streaming_partitions = 0

    for row in integrations:
        monthly_payload_kb = (
            payload_per_month_kb(row.payload_per_execution_kb, row.executions_per_day, assumptions).value
            if row.payload_per_execution_kb is not None and row.executions_per_day is not None
            else None
        )
        oic_msgs_month = (
            oic_billing_messages_per_month(
                row.payload_per_execution_kb,
                row.response_size_kb or 0.0,
                row.executions_per_day,
                assumptions,
            ).value
            if row.payload_per_execution_kb is not None and row.executions_per_day is not None
            else None
        )
        functions_invocations = functions_invocations_per_month(_integration_input(row), assumptions).value
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
            streaming_partition_count((row.payload_per_hour_kb or 0.0) / 3600.0, assumptions).value
            if row.payload_per_hour_kb is not None
            else None
        )

        if di_gb_month:
            di_total_gb += di_gb_month
        if streaming_gb_month:
            streaming_total_gb += streaming_gb_month
        if streaming_partitions:
            peak_streaming_partitions = max(peak_streaming_partitions, int(streaming_partitions))

        row_results[row.id] = {
            "executions_per_day": row.executions_per_day,
            "payload_per_hour_kb": row.payload_per_hour_kb,
            "oic_billing_msgs_month": oic_msgs_month,
            "functions_invocations_month": functions_invocations,
            "functions_execution_units_gb_s": functions_units,
            "data_integration_gb_month": di_gb_month,
            "streaming_gb_month": streaming_gb_month,
            "streaming_partition_count": streaming_partitions,
        }

    consolidated["data_integration"]["data_processed_gb_month"] = di_total_gb
    consolidated["streaming"]["total_gb_month"] = streaming_total_gb
    consolidated["streaming"]["partition_count"] = peak_streaming_partitions

    snapshot = VolumetrySnapshot(
        project_id=project_id,
        assumption_set_version=assumption_set.version,
        triggered_by=actor_id,
        row_results=row_results,
        consolidated=consolidated,
        snapshot_metadata={"integration_count": len(integrations)},
    )
    db.add(snapshot)
    await db.flush()
    await audit_service.emit(
        event_type="recalculation",
        entity_type="project",
        entity_id=project_id,
        actor_id=actor_id,
        old_value=None,
        new_value={"snapshot_id": snapshot.id, "assumption_set_version": assumption_set.version},
        project_id=project_id,
        db=db,
    )
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
        snapshots=[serialize_snapshot(snapshot) for snapshot in result.all()]
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
