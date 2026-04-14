"""Workbook import service that persists source and catalog rows."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.calc_engine import evaluate_qa, executions_per_day, parse_rows, payload_per_hour_kb
from app.models import CatalogIntegration, ImportBatch, JustificationRecord, Project, SourceIntegrationRow
from app.models.project import ImportStatus
from app.schemas.imports import (
    ImportBatchDeleteResponse,
    ImportBatchListResponse,
    ImportBatchResponse,
    NormalizationEventResponse,
    SourceRowListResponse,
    SourceRowResponse,
)
from app.services import audit_service, recalc_service
from app.services.catalog_service import serialize_catalog_integration
from app.services.justification_service import serialize_justification_record
from app.services.serializers import parse_bool, parse_float, parse_int, parse_text, sanitize_for_json

SOURCE_SHEET_NAME = "Catálogo de Integraciones"
FALLBACK_COLUMN_INDEXES: dict[str, int] = {
    "seq_number": 0,
    "interface_id": 1,
    "owner": 2,
    "brand": 3,
    "business_process": 4,
    "interface_name": 5,
    "description": 6,
    "status": 7,
    "mapping_status": 8,
    "initial_scope": 9,
    "complexity": 10,
    "frequency": 11,
    "type": 12,
    "base": 13,
    "interface_status": 14,
    "is_real_time": 15,
    "trigger_type": 16,
    "response_size_kb": 17,
    "payload_per_execution_kb": 18,
    "is_fan_out": 19,
    "fan_out_targets": 20,
    "source_system": 21,
    "source_technology": 22,
    "source_api_reference": 23,
    "source_owner": 24,
    "destination_system": 25,
    "destination_technology_1": 26,
    "destination_technology_2": 27,
    "destination_owner": 28,
    "calendarization": 29,
    "selected_pattern": 32,
    "pattern_rationale": 33,
    "comments": 34,
    "retry_policy": 35,
    "core_tools": 36,
    "additional_tools_overlays": 37,
    "qa_status": 38,
    "tbq": 39,
}


def _bad_request(detail: str, error_code: str) -> HTTPException:
    return HTTPException(status_code=400, detail={"detail": detail, "error_code": error_code})


def serialize_batch(batch: ImportBatch) -> ImportBatchResponse:
    """Convert an import batch model into a response schema."""

    return ImportBatchResponse(
        id=batch.id,
        project_id=batch.project_id,
        filename=batch.filename,
        parser_version=batch.parser_version,
        status=batch.status.value,
        source_row_count=batch.source_row_count,
        tbq_y_count=batch.tbq_y_count,
        excluded_count=batch.excluded_count,
        loaded_count=batch.loaded_count,
        header_map=batch.header_map,
        error_details=batch.error_details,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def serialize_source_row(row: SourceIntegrationRow) -> SourceRowResponse:
    """Convert a source row model into a response schema."""

    return SourceRowResponse(
        id=row.id,
        source_row_number=row.source_row_number,
        included=row.included,
        exclusion_reason=row.exclusion_reason,
        raw_data=row.raw_data,
        normalization_events=[
            NormalizationEventResponse(**event) for event in (row.normalization_events or [])
        ],
    )


def _extract_raw_value(raw_data: dict[str, object], header_map: dict[str, str], field: str) -> object:
    column_index = header_map.get(field, str(FALLBACK_COLUMN_INDEXES.get(field, -1)))
    if column_index == "-1":
        return None
    return raw_data.get(column_index)


def _normalized_frequency(raw_data: dict[str, object], events: list[dict[str, object]], header_map: dict[str, str]) -> str | None:
    for event in events:
        if event.get("field") == "frequency":
            return parse_text(event.get("new_value"))
    return parse_text(_extract_raw_value(raw_data, header_map, "frequency"))


def _build_catalog_integration(
    project_id: str,
    source_row_id: str,
    raw_data: dict[str, object],
    normalization_events: list[dict[str, object]],
    header_map: dict[str, str],
) -> CatalogIntegration:
    frequency_value = _normalized_frequency(raw_data, normalization_events, header_map)
    payload_value = parse_float(_extract_raw_value(raw_data, header_map, "payload_per_execution_kb"))
    execs_result = executions_per_day(frequency_value) if frequency_value else None
    execs_per_day = execs_result.value if execs_result is not None else None
    payload_hour_result = (
        payload_per_hour_kb(payload_value, execs_per_day)
        if payload_value is not None and execs_per_day is not None
        else None
    )
    qa_result = evaluate_qa(
        interface_id=parse_text(_extract_raw_value(raw_data, header_map, "interface_id")),
        trigger_type=parse_text(_extract_raw_value(raw_data, header_map, "trigger_type")),
        selected_pattern=parse_text(_extract_raw_value(raw_data, header_map, "selected_pattern")),
        pattern_rationale=parse_text(_extract_raw_value(raw_data, header_map, "pattern_rationale")),
        core_tools=parse_text(_extract_raw_value(raw_data, header_map, "core_tools")),
        payload_per_execution_kb=payload_value,
        is_fan_out=parse_bool(_extract_raw_value(raw_data, header_map, "is_fan_out")),
        fan_out_targets=parse_int(_extract_raw_value(raw_data, header_map, "fan_out_targets")),
        uncertainty=parse_text(raw_data.get("40")) or None,
    )
    return CatalogIntegration(
        project_id=project_id,
        source_row_id=source_row_id,
        seq_number=parse_int(_extract_raw_value(raw_data, header_map, "seq_number")) or 0,
        interface_id=parse_text(_extract_raw_value(raw_data, header_map, "interface_id")),
        owner=parse_text(_extract_raw_value(raw_data, header_map, "owner")),
        brand=parse_text(_extract_raw_value(raw_data, header_map, "brand")),
        business_process=parse_text(_extract_raw_value(raw_data, header_map, "business_process")),
        interface_name=parse_text(_extract_raw_value(raw_data, header_map, "interface_name")),
        description=parse_text(_extract_raw_value(raw_data, header_map, "description")),
        status=parse_text(_extract_raw_value(raw_data, header_map, "status")),
        mapping_status=parse_text(_extract_raw_value(raw_data, header_map, "mapping_status")),
        initial_scope=parse_text(_extract_raw_value(raw_data, header_map, "initial_scope")),
        complexity=parse_text(_extract_raw_value(raw_data, header_map, "complexity")),
        frequency=frequency_value,
        type=parse_text(_extract_raw_value(raw_data, header_map, "type")),
        base=parse_text(_extract_raw_value(raw_data, header_map, "base")),
        interface_status=parse_text(_extract_raw_value(raw_data, header_map, "interface_status")),
        is_real_time=parse_bool(_extract_raw_value(raw_data, header_map, "is_real_time")),
        trigger_type=parse_text(_extract_raw_value(raw_data, header_map, "trigger_type")),
        response_size_kb=parse_float(_extract_raw_value(raw_data, header_map, "response_size_kb")),
        payload_per_execution_kb=payload_value,
        is_fan_out=parse_bool(_extract_raw_value(raw_data, header_map, "is_fan_out")),
        fan_out_targets=parse_int(_extract_raw_value(raw_data, header_map, "fan_out_targets")),
        source_system=parse_text(_extract_raw_value(raw_data, header_map, "source_system")),
        source_technology=parse_text(_extract_raw_value(raw_data, header_map, "source_technology")),
        source_api_reference=parse_text(_extract_raw_value(raw_data, header_map, "source_api_reference")),
        source_owner=parse_text(_extract_raw_value(raw_data, header_map, "source_owner")),
        destination_system=parse_text(_extract_raw_value(raw_data, header_map, "destination_system")),
        destination_technology_1=parse_text(_extract_raw_value(raw_data, header_map, "destination_technology_1")),
        destination_technology_2=parse_text(_extract_raw_value(raw_data, header_map, "destination_technology_2")),
        destination_owner=parse_text(_extract_raw_value(raw_data, header_map, "destination_owner")),
        executions_per_day=execs_per_day,
        payload_per_hour_kb=payload_hour_result.value if payload_hour_result else None,
        selected_pattern=parse_text(_extract_raw_value(raw_data, header_map, "selected_pattern")),
        pattern_rationale=parse_text(_extract_raw_value(raw_data, header_map, "pattern_rationale")),
        comments=parse_text(_extract_raw_value(raw_data, header_map, "comments")),
        retry_policy=parse_text(_extract_raw_value(raw_data, header_map, "retry_policy")),
        core_tools=parse_text(_extract_raw_value(raw_data, header_map, "core_tools")),
        additional_tools_overlays=parse_text(
            _extract_raw_value(raw_data, header_map, "additional_tools_overlays")
        ),
        qa_status=qa_result.status,
        qa_reasons=qa_result.reasons,
        calendarization=parse_text(_extract_raw_value(raw_data, header_map, "calendarization")),
        uncertainty=parse_text(raw_data.get("40")),
    )


async def create_import_batch(project_id: str, filename: str, db: AsyncSession) -> ImportBatch:
    """Create a pending import batch."""

    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"},
        )
    batch = ImportBatch(
        project_id=project_id,
        filename=filename,
        parser_version="1.0.0",
        status=ImportStatus.PENDING,
    )
    db.add(batch)
    await db.flush()
    await db.refresh(batch)
    return batch


async def process_import(batch_id: str, file_path: str, db: AsyncSession) -> ImportBatch:
    """Parse the workbook, persist all source rows, and materialize included catalog rows."""

    batch = await db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Import batch not found", "error_code": "IMPORT_BATCH_NOT_FOUND"},
        )

    batch.status = ImportStatus.PROCESSING
    await db.flush()

    workbook = load_workbook(filename=file_path, data_only=True)
    if SOURCE_SHEET_NAME not in workbook.sheetnames:
        raise _bad_request(
            f"Required sheet '{SOURCE_SHEET_NAME}' not found in workbook.",
            "IMPORT_SHEET_NOT_FOUND",
        )
    sheet = workbook[SOURCE_SHEET_NAME]
    all_rows = [list(row) for row in sheet.iter_rows(values_only=True)]
    import_result = parse_rows(all_rows)
    correlation_id = str(uuid.uuid4())

    for parsed_row in import_result.rows:
        normalization_events = [
            sanitize_for_json(event.__dict__) for event in parsed_row.normalization_events
        ]
        source_row = SourceIntegrationRow(
            import_batch_id=batch.id,
            source_row_number=parsed_row.source_row_number,
            raw_data=sanitize_for_json(parsed_row.raw_data),
            included=parsed_row.included,
            exclusion_reason=parsed_row.exclusion_reason,
            normalization_events=normalization_events,
        )
        db.add(source_row)
        await db.flush()

        for event in normalization_events:
            await audit_service.emit(
                event_type="normalization",
                entity_type="source_integration_row",
                entity_id=source_row.id,
                actor_id="system-import",
                old_value={"field": event["field"], "value": event["old_value"]},
                new_value={"field": event["field"], "value": event["new_value"], "rule": event["rule"]},
                project_id=batch.project_id,
                db=db,
                correlation_id=correlation_id,
            )

        if parsed_row.included:
            db.add(
                _build_catalog_integration(
                    project_id=batch.project_id,
                    source_row_id=source_row.id,
                    raw_data=source_row.raw_data,
                    normalization_events=normalization_events,
                    header_map=import_result.header_map,
                )
            )

    batch.source_row_count = import_result.source_row_count
    batch.tbq_y_count = import_result.tbq_y_count
    batch.excluded_count = import_result.excluded_count
    batch.loaded_count = import_result.loaded_count
    batch.header_map = import_result.header_map
    batch.parser_version = import_result.parser_version
    batch.status = ImportStatus.COMPLETED
    await db.flush()
    await db.refresh(batch)
    return batch


async def mark_import_failed(batch_id: str, error_details: dict[str, object], db: AsyncSession) -> None:
    """Mark an import batch as failed."""

    batch = await db.get(ImportBatch, batch_id)
    if batch is None:
        return
    batch.status = ImportStatus.FAILED
    batch.error_details = sanitize_for_json(error_details)
    await db.flush()


async def list_import_batches(project_id: str, db: AsyncSession) -> ImportBatchListResponse:
    """List all import batches for a project."""

    result = await db.scalars(
        select(ImportBatch)
        .where(ImportBatch.project_id == project_id)
        .order_by(ImportBatch.created_at.desc())
    )
    return ImportBatchListResponse(import_batches=[serialize_batch(batch) for batch in result.all()])


async def get_import_batch(project_id: str, batch_id: str, db: AsyncSession) -> ImportBatchResponse:
    """Load one import batch for a project."""

    batch = await db.scalar(
        select(ImportBatch).where(
            ImportBatch.project_id == project_id,
            ImportBatch.id == batch_id,
        )
    )
    if batch is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Import batch not found", "error_code": "IMPORT_BATCH_NOT_FOUND"},
        )
    return serialize_batch(batch)


async def list_import_rows(
    project_id: str,
    batch_id: str,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 100,
) -> SourceRowListResponse:
    """Return paginated source rows for one batch."""

    batch = await db.scalar(
        select(ImportBatch).where(
            ImportBatch.project_id == project_id,
            ImportBatch.id == batch_id,
        )
    )
    if batch is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Import batch not found", "error_code": "IMPORT_BATCH_NOT_FOUND"},
        )

    query = select(SourceIntegrationRow).where(SourceIntegrationRow.import_batch_id == batch_id)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    offset = (page - 1) * page_size
    result = await db.scalars(
        query.order_by(SourceIntegrationRow.source_row_number).offset(offset).limit(page_size)
    )
    return SourceRowListResponse(
        rows=[serialize_source_row(row) for row in result.all()],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


async def save_upload_file(file_name: str, contents: bytes, upload_dir: Path) -> str:
    """Persist an uploaded source workbook to local storage."""

    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"{uuid.uuid4()}-{file_name}"
    destination.write_bytes(contents)
    return str(destination)


async def delete_import_batch(
    project_id: str,
    batch_id: str,
    actor_id: str,
    db: AsyncSession,
) -> ImportBatchDeleteResponse:
    """Remove one import batch and its governed descendants, then recalculate the project."""

    batch = await db.scalar(
        select(ImportBatch)
        .options(selectinload(ImportBatch.source_rows))
        .where(
            ImportBatch.project_id == project_id,
            ImportBatch.id == batch_id,
        )
    )
    if batch is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Import batch not found", "error_code": "IMPORT_BATCH_NOT_FOUND"},
        )
    if batch.status in {ImportStatus.PENDING, ImportStatus.PROCESSING}:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Cannot remove an import while it is still processing.",
                "error_code": "IMPORT_BATCH_ACTIVE",
            },
        )

    old_value = serialize_batch(batch).model_dump()
    source_rows = list(batch.source_rows)
    source_row_ids = [row.id for row in source_rows]
    integrations = (
        await db.scalars(
            select(CatalogIntegration).where(CatalogIntegration.source_row_id.in_(source_row_ids))
        )
    ).all() if source_row_ids else []
    integration_ids = [integration.id for integration in integrations]
    justifications = (
        await db.scalars(
            select(JustificationRecord).where(
                JustificationRecord.project_id == project_id,
                JustificationRecord.integration_id.in_(integration_ids),
            )
        )
    ).all() if integration_ids else []

    for record in justifications:
        await audit_service.emit(
            event_type="justification_deleted",
            entity_type="justification_record",
            entity_id=record.id,
            actor_id=actor_id,
            old_value=serialize_justification_record(record).model_dump(),
            new_value=None,
            project_id=project_id,
            db=db,
        )
        await db.delete(record)

    for integration in integrations:
        await audit_service.emit(
            event_type="catalog_deleted",
            entity_type="catalog_integration",
            entity_id=integration.id,
            actor_id=actor_id,
            old_value=serialize_catalog_integration(integration).model_dump(),
            new_value=None,
            project_id=project_id,
            db=db,
        )
        await db.delete(integration)

    for source_row in source_rows:
        await db.delete(source_row)
    await db.delete(batch)
    await db.flush()

    snapshot = await recalc_service.recalculate_project(project_id=project_id, actor_id=actor_id, db=db)
    response = ImportBatchDeleteResponse(
        project_id=project_id,
        batch_id=batch_id,
        detail="Import removed and project recalculated.",
        deleted_source_rows=len(source_rows),
        deleted_integrations=len(integrations),
        deleted_justifications=len(justifications),
        recalculated_snapshot_id=snapshot.id,
    )
    await audit_service.emit(
        event_type="import_deleted",
        entity_type="import_batch",
        entity_id=batch_id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=response.model_dump(),
        project_id=project_id,
        db=db,
    )
    return response
