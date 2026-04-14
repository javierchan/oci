"""Catalog query, update, bulk patch, and lineage services."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.calc_engine import evaluate_qa, executions_per_day, payload_per_hour_kb
from app.models import CatalogIntegration, DictionaryOption, PatternDefinition, SourceIntegrationRow
from app.schemas.catalog import (
    BulkPatchResult,
    CatalogIntegrationDetail,
    CatalogIntegrationPatch,
    CatalogIntegrationResponse,
    CatalogListResponse,
    LineageDetail,
)
from app.services import audit_service, recalc_service
from app.services.serializers import split_csv

PATCHABLE_FIELDS = {
    "selected_pattern",
    "pattern_rationale",
    "comments",
    "retry_policy",
    "core_tools",
    "additional_tools_overlays",
}


def serialize_catalog_integration(row: CatalogIntegration) -> CatalogIntegrationResponse:
    """Convert a catalog row model into a response schema."""

    return CatalogIntegrationResponse(
        id=row.id,
        project_id=row.project_id,
        source_row_id=row.source_row_id,
        seq_number=row.seq_number,
        interface_id=row.interface_id,
        owner=row.owner,
        brand=row.brand,
        business_process=row.business_process,
        interface_name=row.interface_name,
        description=row.description,
        status=row.status,
        mapping_status=row.mapping_status,
        initial_scope=row.initial_scope,
        complexity=row.complexity,
        frequency=row.frequency,
        type=row.type,
        base=row.base,
        interface_status=row.interface_status,
        is_real_time=row.is_real_time,
        trigger_type=row.trigger_type,
        response_size_kb=row.response_size_kb,
        payload_per_execution_kb=row.payload_per_execution_kb,
        is_fan_out=row.is_fan_out,
        fan_out_targets=row.fan_out_targets,
        source_system=row.source_system,
        source_technology=row.source_technology,
        source_api_reference=row.source_api_reference,
        source_owner=row.source_owner,
        destination_system=row.destination_system,
        destination_technology_1=row.destination_technology_1,
        destination_technology_2=row.destination_technology_2,
        destination_owner=row.destination_owner,
        executions_per_day=row.executions_per_day,
        payload_per_hour_kb=row.payload_per_hour_kb,
        selected_pattern=row.selected_pattern,
        pattern_rationale=row.pattern_rationale,
        comments=row.comments,
        retry_policy=row.retry_policy,
        core_tools=row.core_tools,
        additional_tools_overlays=row.additional_tools_overlays,
        qa_status=row.qa_status,
        qa_reasons=row.qa_reasons or [],
        calendarization=row.calendarization,
        uncertainty=row.uncertainty,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _lineage_detail(source_row: SourceIntegrationRow) -> LineageDetail:
    batch = source_row.import_batch
    return LineageDetail(
        source_row_id=source_row.id,
        source_row_number=source_row.source_row_number,
        raw_data=source_row.raw_data,
        included=source_row.included,
        exclusion_reason=source_row.exclusion_reason,
        normalization_events=source_row.normalization_events or [],
        import_batch_id=batch.id,
        import_filename=batch.filename,
    )


async def _load_catalog_row(project_id: str, integration_id: str, db: AsyncSession) -> CatalogIntegration:
    row = await db.scalar(
        select(CatalogIntegration)
        .options(selectinload(CatalogIntegration.source_row).selectinload(SourceIntegrationRow.import_batch))
        .where(
            CatalogIntegration.project_id == project_id,
            CatalogIntegration.id == integration_id,
        )
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Catalog integration not found", "error_code": "CATALOG_INTEGRATION_NOT_FOUND"},
        )
    return row


async def _validate_pattern(pattern_id: Optional[str], db: AsyncSession) -> None:
    if pattern_id is None:
        return
    exists = await db.scalar(select(PatternDefinition.id).where(PatternDefinition.pattern_id == pattern_id))
    if exists is None:
        raise HTTPException(
            status_code=400,
            detail={"detail": f"Unknown pattern '{pattern_id}'.", "error_code": "INVALID_PATTERN"},
        )


async def _validate_core_tools(core_tools: Optional[str], db: AsyncSession) -> None:
    if not core_tools:
        return
    tools = split_csv(core_tools)
    allowed = set(
        (
            await db.scalars(
                select(DictionaryOption.value).where(DictionaryOption.category == "TOOLS")
            )
        ).all()
    )
    invalid = [tool for tool in tools if tool not in allowed]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": f"Unknown core tool values: {', '.join(invalid)}.",
                "error_code": "INVALID_CORE_TOOLS",
            },
        )


def _recompute_derived_fields(row: CatalogIntegration) -> None:
    execs_result = executions_per_day(row.frequency) if row.frequency else None
    row.executions_per_day = execs_result.value if execs_result else None
    if row.payload_per_execution_kb is not None and row.executions_per_day is not None:
        row.payload_per_hour_kb = payload_per_hour_kb(
            row.payload_per_execution_kb, row.executions_per_day
        ).value
    else:
        row.payload_per_hour_kb = None


def _recompute_qa(row: CatalogIntegration) -> None:
    qa_result = evaluate_qa(
        interface_id=row.interface_id,
        trigger_type=row.trigger_type,
        selected_pattern=row.selected_pattern,
        pattern_rationale=row.pattern_rationale,
        core_tools=row.core_tools,
        payload_per_execution_kb=row.payload_per_execution_kb,
        is_fan_out=row.is_fan_out,
        fan_out_targets=row.fan_out_targets,
        uncertainty=row.uncertainty,
    )
    row.qa_status = qa_result.status
    row.qa_reasons = qa_result.reasons


async def list_integrations(
    project_id: str,
    page: int,
    page_size: int,
    filters: dict[str, str | None],
    db: AsyncSession,
) -> CatalogListResponse:
    """Return a paginated, filterable catalog list in source order."""

    query = (
        select(CatalogIntegration)
        .where(CatalogIntegration.project_id == project_id)
        .order_by(CatalogIntegration.seq_number, CatalogIntegration.id)
    )
    if pattern := filters.get("pattern"):
        query = query.where(CatalogIntegration.selected_pattern == pattern)
    if brand := filters.get("brand"):
        query = query.where(CatalogIntegration.brand == brand)
    if qa_status := filters.get("qa_status"):
        query = query.where(CatalogIntegration.qa_status == qa_status)
    if search := filters.get("search"):
        like = f"%{search}%"
        query = query.where(
            or_(
                CatalogIntegration.interface_id.ilike(like),
                CatalogIntegration.interface_name.ilike(like),
                CatalogIntegration.description.ilike(like),
                CatalogIntegration.source_system.ilike(like),
                CatalogIntegration.destination_system.ilike(like),
            )
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    offset = (page - 1) * page_size
    result = await db.scalars(query.offset(offset).limit(page_size))
    return CatalogListResponse(
        integrations=[serialize_catalog_integration(row) for row in result.all()],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


async def get_lineage(project_id: str, integration_id: str, db: AsyncSession) -> LineageDetail:
    """Return lineage for one catalog row."""

    row = await _load_catalog_row(project_id, integration_id, db)
    if row.source_row is None or row.source_row.import_batch is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Lineage not found", "error_code": "LINEAGE_NOT_FOUND"},
        )
    return _lineage_detail(row.source_row)


async def get_integration(project_id: str, integration_id: str, db: AsyncSession) -> CatalogIntegrationDetail:
    """Return a single integration and its lineage."""

    row = await _load_catalog_row(project_id, integration_id, db)
    if row.source_row is None or row.source_row.import_batch is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Lineage not found", "error_code": "LINEAGE_NOT_FOUND"},
        )
    return CatalogIntegrationDetail(
        integration=serialize_catalog_integration(row),
        lineage=_lineage_detail(row.source_row),
    )


async def update_integration(
    project_id: str,
    integration_id: str,
    patch: CatalogIntegrationPatch,
    actor_id: str,
    db: AsyncSession,
) -> CatalogIntegrationResponse:
    """Apply an architect-owned patch, emit audit, and recalc when needed."""

    row = await _load_catalog_row(project_id, integration_id, db)
    patch_data = patch.model_dump(exclude_none=True)
    invalid_fields = set(patch_data) - PATCHABLE_FIELDS
    if invalid_fields:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": f"Unsupported patch fields: {', '.join(sorted(invalid_fields))}.",
                "error_code": "INVALID_PATCH_FIELDS",
            },
        )
    if not patch_data:
        return serialize_catalog_integration(row)

    await _validate_pattern(patch_data.get("selected_pattern"), db)
    await _validate_core_tools(patch_data.get("core_tools"), db)

    old_value = serialize_catalog_integration(row).model_dump()
    recalc_required = False
    for field, value in patch_data.items():
        setattr(row, field, value)
        if field in {"core_tools", "selected_pattern"}:
            recalc_required = True

    _recompute_derived_fields(row)
    _recompute_qa(row)
    await db.flush()
    await audit_service.emit(
        event_type="catalog_update",
        entity_type="catalog_integration",
        entity_id=row.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=serialize_catalog_integration(row).model_dump(),
        project_id=project_id,
        db=db,
    )

    if recalc_required:
        await recalc_service.recalculate_project(project_id=project_id, actor_id=actor_id, db=db)

    await db.refresh(row)
    return serialize_catalog_integration(row)


async def bulk_patch(
    project_id: str,
    integration_ids: list[str],
    patch: CatalogIntegrationPatch,
    actor_id: str,
    db: AsyncSession,
) -> BulkPatchResult:
    """Apply one patch to multiple catalog rows."""

    updated = 0
    errors: list[str] = []
    patch_data = patch.model_dump(exclude_none=True)
    await _validate_pattern(patch_data.get("selected_pattern"), db)
    await _validate_core_tools(patch_data.get("core_tools"), db)

    recalc_required = False
    for integration_id in integration_ids:
        try:
            row = await _load_catalog_row(project_id, integration_id, db)
            old_value = serialize_catalog_integration(row).model_dump()
            for field, value in patch_data.items():
                setattr(row, field, value)
                if field in {"core_tools", "selected_pattern"}:
                    recalc_required = True
            _recompute_derived_fields(row)
            _recompute_qa(row)
            await db.flush()
            await audit_service.emit(
                event_type="catalog_bulk_update",
                entity_type="catalog_integration",
                entity_id=row.id,
                actor_id=actor_id,
                old_value=old_value,
                new_value=serialize_catalog_integration(row).model_dump(),
                project_id=project_id,
                db=db,
            )
            updated += 1
        except HTTPException as exc:
            detail = exc.detail["detail"] if isinstance(exc.detail, dict) else str(exc.detail)
            errors.append(f"{integration_id}: {detail}")

    if recalc_required and updated > 0:
        await recalc_service.recalculate_project(project_id=project_id, actor_id=actor_id, db=db)

    return BulkPatchResult(updated=updated, errors=errors)
