"""Catalog query, manual capture, update, bulk patch, and lineage services."""

from __future__ import annotations

from dataclasses import fields
from typing import Any, Optional, cast

from fastapi import HTTPException
from sqlalchemy import func, or_, select, union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.calc_engine import (
    Assumptions,
    evaluate_qa,
    executions_per_day,
    oic_billing_messages_per_execution,
    oic_billing_messages_per_month,
    oic_peak_packs_per_hour,
    payload_per_hour_kb,
)
from app.models import (
    AssumptionSet,
    CatalogIntegration,
    DictionaryOption,
    ImportBatch,
    JustificationRecord,
    PatternDefinition,
    SourceIntegrationRow,
)
from app.schemas.catalog import (
    BulkPatchResult,
    CatalogIntegrationDeleteResponse,
    CatalogIntegrationDetail,
    CatalogIntegrationPatch,
    CatalogIntegrationResponse,
    CatalogListResponse,
    LineageDetail,
    ManualIntegrationCreate,
    OICEstimateRequest,
    OICEstimateResponse,
)
from app.services import audit_service, import_service, recalc_service
from app.services.justification_service import serialize_justification_record
from app.services.pattern_support import support_reason_code
from app.services.serializers import parse_float, parse_int, parse_text, sanitize_for_json, split_csv

PATCHABLE_FIELDS = {
    "selected_pattern",
    "pattern_rationale",
    "comments",
    "retry_policy",
    "core_tools",
    "additional_tools_overlays",
}
RAW_COLUMN_PATCH_FIELD = "raw_column_values"
SOURCE_MANAGED_FIELDS = {
    "seq_number",
    "interface_id",
    "owner",
    "brand",
    "business_process",
    "interface_name",
    "description",
    "status",
    "mapping_status",
    "initial_scope",
    "complexity",
    "frequency",
    "type",
    "base",
    "interface_status",
    "is_real_time",
    "trigger_type",
    "response_size_kb",
    "payload_per_execution_kb",
    "is_fan_out",
    "fan_out_targets",
    "source_system",
    "source_technology",
    "source_api_reference",
    "source_owner",
    "destination_system",
    "destination_technology_1",
    "destination_technology_2",
    "destination_owner",
    "executions_per_day",
    "payload_per_hour_kb",
    "qa_status",
    "qa_reasons",
    "calendarization",
    "uncertainty",
}
MANUAL_SOURCE_ROW_FIELD_PARSERS: dict[str, Any] = {
    "seq_number": parse_int,
    "interface_id": parse_text,
    "owner": parse_text,
    "brand": parse_text,
    "business_process": parse_text,
    "interface_name": parse_text,
    "description": parse_text,
    "status": parse_text,
    "mapping_status": parse_text,
    "initial_scope": parse_text,
    "complexity": parse_text,
    "frequency": parse_text,
    "type": parse_text,
    "source_system": parse_text,
    "source_technology": parse_text,
    "source_api_reference": parse_text,
    "source_owner": parse_text,
    "destination_system": parse_text,
    "destination_technology_1": parse_text,
    "destination_owner": parse_text,
    "payload_per_execution_kb": parse_float,
    "uncertainty": parse_text,
}

FIELD_LABELS = {
    "seq_number": "#",
    "interface_id": "Interface ID",
    "brand": "Brand",
    "business_process": "Business Process",
    "interface_name": "Interface Name",
    "description": "Description",
    "type": "Trigger Type",
    "interface_status": "Interface Status",
    "complexity": "Complexity",
    "initial_scope": "Initial Scope",
    "status": "Status",
    "mapping_status": "Mapping Status",
    "source_system": "Source System",
    "source_technology": "Source Technology",
    "source_api_reference": "Source API Reference",
    "source_owner": "Source Owner",
    "destination_system": "Destination System",
    "destination_technology": "Destination Technology",
    "destination_technology_1": "Destination Technology",
    "destination_technology_2": "Destination Technology 2",
    "destination_owner": "Destination Owner",
    "frequency": "Frequency",
    "payload_per_execution_kb": "Payload (KB)",
    "tbq": "TBQ",
    "patterns": "Patterns",
    "selected_pattern": "Patterns",
    "uncertainty": "Uncertainty",
    "owner": "Owner",
    "identified_in": "Identified In",
    "business_process_dd": "Business Process (DD)",
    "slide": "Slide",
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


def _fallback_column_label(column_key: str) -> str:
    if column_key.isdigit():
        return f"Column {int(column_key) + 1}"
    return FIELD_LABELS.get(column_key, column_key.replace("_", " ").title())


def _build_column_names(source_row: SourceIntegrationRow) -> dict[str, str]:
    batch = source_row.import_batch
    raw_data = source_row.raw_data or {}
    column_names: dict[str, str] = {}
    raw_headers = import_service._extract_raw_headers(batch.header_map if batch else None)

    if raw_headers:
        for raw_key, raw_value in raw_data.items():
            if raw_key in raw_headers.values():
                column_names[raw_key] = raw_key
            elif raw_key in raw_headers:
                column_names[raw_key] = raw_headers[raw_key]
            else:
                column_names[raw_key] = FIELD_LABELS.get(raw_key, _fallback_column_label(raw_key))
        return column_names

    if batch.header_map:
        for field_name, column_index in batch.header_map.items():
            if field_name == import_service.RAW_HEADERS_METADATA_KEY:
                continue
            column_names[str(column_index)] = FIELD_LABELS.get(
                field_name,
                _fallback_column_label(str(column_index)),
            )

    for raw_key in raw_data:
        if raw_key not in column_names:
            column_names[str(raw_key)] = _fallback_column_label(str(raw_key))

    return column_names


def _lineage_detail(source_row: SourceIntegrationRow) -> LineageDetail:
    batch = source_row.import_batch
    return LineageDetail(
        source_row_id=source_row.id,
        source_row_number=source_row.source_row_number,
        raw_data=source_row.raw_data,
        column_names=_build_column_names(source_row),
        included=source_row.included,
        exclusion_reason=source_row.exclusion_reason,
        normalization_events=source_row.normalization_events or [],
        import_batch_id=batch.id,
        import_batch_date=batch.created_at,
        import_filename=batch.filename,
    )


def _copy_source_managed_fields(target: CatalogIntegration, rebuilt: CatalogIntegration) -> None:
    for field in SOURCE_MANAGED_FIELDS:
        setattr(target, field, getattr(rebuilt, field))


def _apply_manual_source_row_updates(row: CatalogIntegration, raw_data: dict[str, object]) -> None:
    for field_name, parser in MANUAL_SOURCE_ROW_FIELD_PARSERS.items():
        if field_name not in raw_data:
            continue
        setattr(row, field_name, parser(raw_data.get(field_name)))
    if "type" in raw_data:
        row.trigger_type = parse_text(raw_data.get("type"))
    _recompute_derived_fields(row)
    _recompute_qa(row)


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


def _normalize_core_tools(value: Optional[list[str] | str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    normalized = [tool.strip() for tool in value if tool.strip()]
    return ", ".join(normalized) if normalized else None


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
        is_active_row=True,
    )
    reasons = list(qa_result.reasons)
    support_reason = support_reason_code(row.selected_pattern)
    if support_reason and support_reason not in reasons:
        reasons.append(support_reason)
    row.qa_status = "OK" if not reasons else "REVISAR"
    row.qa_reasons = reasons


async def _load_default_assumptions(db: AsyncSession) -> Assumptions:
    assumption_set = await db.scalar(select(AssumptionSet).where(AssumptionSet.is_default.is_(True)))
    if assumption_set is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Default assumption set not found", "error_code": "DEFAULT_ASSUMPTION_SET_NOT_FOUND"},
        )
    allowed_keys = {field.name for field in fields(Assumptions)}
    filtered = {
        key: value
        for key, value in assumption_set.assumptions.items()
        if key in allowed_keys
    }
    return Assumptions(**filtered)


async def _next_seq_number(project_id: str, db: AsyncSession) -> int:
    current = await db.scalar(
        select(func.max(CatalogIntegration.seq_number)).where(CatalogIntegration.project_id == project_id)
    )
    return int(current or 0) + 1


async def _next_source_row_number(project_id: str, db: AsyncSession) -> int:
    current = await db.scalar(
        select(func.max(SourceIntegrationRow.source_row_number))
        .join(ImportBatch, ImportBatch.id == SourceIntegrationRow.import_batch_id)
        .where(ImportBatch.project_id == project_id)
    )
    return int(current or 0) + 1


async def _create_manual_import_batch(project_id: str, db: AsyncSession) -> ImportBatch:
    batch = ImportBatch(
        project_id=project_id,
        filename="manual-capture.json",
        parser_version="manual-capture-v1",
        status="completed",
        source_row_count=1,
        tbq_y_count=1,
        excluded_count=0,
        loaded_count=1,
        header_map=None,
        error_details=None,
    )
    db.add(batch)
    await db.flush()
    return batch


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
    if source_system := filters.get("source_system"):
        query = query.where(CatalogIntegration.source_system == source_system)
    if destination_system := filters.get("destination_system"):
        query = query.where(CatalogIntegration.destination_system == destination_system)
    if search := filters.get("search"):
        like = f"%{search}%"
        query = query.where(
            or_(
                CatalogIntegration.interface_id.ilike(like),
                CatalogIntegration.brand.ilike(like),
                CatalogIntegration.business_process.ilike(like),
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


async def manual_create_integration(
    project_id: str,
    data: ManualIntegrationCreate,
    actor_id: str,
    db: AsyncSession,
) -> CatalogIntegrationResponse:
    """Create a governed integration from the guided capture flow."""

    core_tools_value = _normalize_core_tools(data.core_tools)
    await _validate_pattern(data.selected_pattern, db)
    await _validate_core_tools(core_tools_value, db)

    source_row_number = await _next_source_row_number(project_id, db)
    seq_number = await _next_seq_number(project_id, db)
    import_batch = await _create_manual_import_batch(project_id, db)
    raw_data = data.model_dump()

    source_row = SourceIntegrationRow(
        import_batch_id=import_batch.id,
        source_row_number=source_row_number,
        raw_data=raw_data,
        included=True,
        exclusion_reason=None,
        normalization_events=[],
    )
    db.add(source_row)
    await db.flush()

    execs_result = executions_per_day(data.frequency) if data.frequency else None
    computed_execs = execs_result.value if execs_result is not None else None
    computed_payload_hour = (
        payload_per_hour_kb(data.payload_per_execution_kb, computed_execs).value
        if data.payload_per_execution_kb is not None and computed_execs is not None
        else None
    )
    qa_result = evaluate_qa(
        interface_id=data.interface_id,
        trigger_type=data.type,
        selected_pattern=data.selected_pattern,
        pattern_rationale=data.pattern_rationale,
        core_tools=core_tools_value,
        payload_per_execution_kb=data.payload_per_execution_kb,
        is_fan_out=None,
        fan_out_targets=None,
        uncertainty=data.uncertainty,
        is_active_row=True,
    )

    row = CatalogIntegration(
        project_id=project_id,
        source_row_id=source_row.id,
        seq_number=seq_number,
        interface_id=data.interface_id,
        owner=data.owner,
        brand=data.brand,
        business_process=data.business_process,
        interface_name=data.interface_name,
        description=data.description,
        initial_scope=data.initial_scope,
        complexity=data.complexity,
        frequency=data.frequency,
        type=data.type,
        trigger_type=data.type,
        payload_per_execution_kb=data.payload_per_execution_kb,
        source_system=data.source_system,
        source_technology=data.source_technology,
        source_api_reference=data.source_api_reference,
        source_owner=data.source_owner,
        destination_system=data.destination_system,
        destination_technology_1=data.destination_technology,
        destination_owner=data.destination_owner,
        executions_per_day=computed_execs,
        payload_per_hour_kb=computed_payload_hour,
        selected_pattern=data.selected_pattern,
        pattern_rationale=data.pattern_rationale,
        core_tools=core_tools_value,
        qa_status=qa_result.status,
        qa_reasons=qa_result.reasons,
        uncertainty=data.uncertainty,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    await audit_service.emit(
        event_type="manual_capture",
        entity_type="catalog_integration",
        entity_id=row.id,
        actor_id=actor_id,
        old_value=None,
        new_value=serialize_catalog_integration(row).model_dump(),
        project_id=project_id,
        db=db,
    )
    return serialize_catalog_integration(row)


async def list_systems(project_id: str, db: AsyncSession) -> list[str]:
    """Return unique source and destination system names for autocomplete."""

    source_query = (
        select(CatalogIntegration.source_system.label("system_name"))
        .where(
            CatalogIntegration.project_id == project_id,
            CatalogIntegration.source_system.is_not(None),
        )
    )
    destination_query = (
        select(CatalogIntegration.destination_system.label("system_name"))
        .where(
            CatalogIntegration.project_id == project_id,
            CatalogIntegration.destination_system.is_not(None),
        )
    )
    result = await db.execute(select(union(source_query, destination_query).subquery().c.system_name))
    return sorted({str(value).strip() for value in result.scalars().all() if value and str(value).strip()})


async def find_duplicates(
    project_id: str,
    source_system: str,
    destination_system: str,
    business_process: str,
    db: AsyncSession,
) -> list[CatalogIntegrationResponse]:
    """Return matching integrations for duplicate detection in capture flow."""

    result = await db.scalars(
        select(CatalogIntegration)
        .where(
            CatalogIntegration.project_id == project_id,
            CatalogIntegration.source_system == source_system,
            CatalogIntegration.destination_system == destination_system,
            CatalogIntegration.business_process == business_process,
        )
        .order_by(CatalogIntegration.seq_number, CatalogIntegration.created_at)
    )
    return [serialize_catalog_integration(row) for row in result.all()]


async def estimate_oic(
    project_id: str,
    body: OICEstimateRequest,
    db: AsyncSession,
) -> OICEstimateResponse:
    """Return a live OIC estimate without persisting any data."""

    if body.frequency is None or body.payload_per_execution_kb is None:
        return OICEstimateResponse(computable=False)

    assumptions = await _load_default_assumptions(db)
    execs_per_day_result = executions_per_day(body.frequency)
    if execs_per_day_result.value is None:
        return OICEstimateResponse(computable=False)

    billing_per_exec = oic_billing_messages_per_execution(
        body.payload_per_execution_kb,
        body.response_kb,
        assumptions,
    ).value
    billing_per_month = oic_billing_messages_per_month(
        body.payload_per_execution_kb,
        body.response_kb,
        execs_per_day_result.value,
        assumptions,
    ).value
    peak_billing_per_hour = (
        (billing_per_exec or 0.0) * execs_per_day_result.value / 24.0
        if billing_per_exec is not None
        else 0.0
    )
    peak_packs = oic_peak_packs_per_hour(peak_billing_per_hour, assumptions).value
    return OICEstimateResponse(
        billing_msgs_per_execution=billing_per_exec,
        billing_msgs_per_month=billing_per_month,
        peak_packs_per_hour=peak_packs,
        executions_per_day=execs_per_day_result.value,
        computable=True,
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
    raw_column_values = patch_data.pop(RAW_COLUMN_PATCH_FIELD, None)
    invalid_fields = set(patch_data) - PATCHABLE_FIELDS
    if invalid_fields:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": f"Unsupported patch fields: {', '.join(sorted(invalid_fields))}.",
                "error_code": "INVALID_PATCH_FIELDS",
            },
        )
    if not patch_data and raw_column_values is None:
        return serialize_catalog_integration(row)

    await _validate_pattern(patch_data.get("selected_pattern"), db)
    await _validate_core_tools(patch_data.get("core_tools"), db)

    old_value = serialize_catalog_integration(row).model_dump()
    recalc_required = raw_column_values is not None

    if raw_column_values is not None:
        if row.source_row is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "detail": "Raw column values can only be edited for rows with source lineage.",
                    "error_code": "RAW_COLUMN_VALUES_UNSUPPORTED",
                },
            )
        source_row = row.source_row
        old_raw_data = cast(dict[str, object], sanitize_for_json(source_row.raw_data or {}))
        source_row.raw_data = cast(dict[str, Any], sanitize_for_json(raw_column_values))
        await audit_service.emit(
            event_type="source_row_update",
            entity_type="source_integration_row",
            entity_id=source_row.id,
            actor_id=actor_id,
            old_value=old_raw_data,
            new_value=source_row.raw_data,
            project_id=project_id,
            db=db,
        )
        if source_row.import_batch and source_row.import_batch.header_map:
            rebuilt = import_service._build_catalog_integration(
                project_id=row.project_id,
                source_row_id=source_row.id,
                raw_data=cast(dict[str, object], source_row.raw_data),
                normalization_events=cast(list[dict[str, object]], source_row.normalization_events or []),
                header_map=source_row.import_batch.header_map,
            )
            _copy_source_managed_fields(row, rebuilt)
        else:
            _apply_manual_source_row_updates(row, cast(dict[str, object], source_row.raw_data))

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


async def delete_integration(
    project_id: str,
    integration_id: str,
    actor_id: str,
    db: AsyncSession,
) -> CatalogIntegrationDeleteResponse:
    """Remove one catalog integration and recalculate the project."""

    row = await _load_catalog_row(project_id, integration_id, db)
    old_value = serialize_catalog_integration(row).model_dump()
    source_row = row.source_row
    import_batch = source_row.import_batch if source_row is not None else None
    is_manual_capture = import_batch is not None and import_batch.parser_version == "manual-capture-v1"
    justification = await db.scalar(
        select(JustificationRecord).where(
            JustificationRecord.project_id == project_id,
            JustificationRecord.integration_id == integration_id,
        )
    )

    deleted_source_row_id: str | None = None
    deleted_import_batch_id: str | None = None
    deleted_justification_id: str | None = None

    if justification is not None:
        deleted_justification_id = justification.id
        await audit_service.emit(
            event_type="justification_deleted",
            entity_type="justification_record",
            entity_id=justification.id,
            actor_id=actor_id,
            old_value=serialize_justification_record(justification).model_dump(),
            new_value=None,
            project_id=project_id,
            db=db,
        )
        await db.delete(justification)

    await audit_service.emit(
        event_type="catalog_deleted",
        entity_type="catalog_integration",
        entity_id=row.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=None,
        project_id=project_id,
        db=db,
    )
    await db.delete(row)
    await db.flush()

    if is_manual_capture and source_row is not None and import_batch is not None:
        deleted_source_row_id = source_row.id
        await db.delete(source_row)
        await db.flush()
        remaining_rows = await db.scalar(
            select(func.count())
            .select_from(SourceIntegrationRow)
            .where(SourceIntegrationRow.import_batch_id == import_batch.id)
        )
        if (remaining_rows or 0) == 0:
            deleted_import_batch_id = import_batch.id
            await db.delete(import_batch)
            await db.flush()

    snapshot = await recalc_service.recalculate_project(project_id=project_id, actor_id=actor_id, db=db)
    return CatalogIntegrationDeleteResponse(
        project_id=project_id,
        integration_id=integration_id,
        detail="Integration removed and project recalculated.",
        deleted_source_row_id=deleted_source_row_id,
        deleted_import_batch_id=deleted_import_batch_id,
        deleted_justification_id=deleted_justification_id,
        recalculated_snapshot_id=snapshot.id,
    )
