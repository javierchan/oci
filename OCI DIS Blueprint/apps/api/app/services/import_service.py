"""Workbook import service that persists source and catalog rows."""

from __future__ import annotations

import json
import re
import uuid
from io import BytesIO
from typing import Any, cast
from unicodedata import normalize

from fastapi import HTTPException
from openpyxl import load_workbook
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.calc_engine import (
    HEADER_ALIASES,
    detect_header_row,
    evaluate_qa,
    executions_per_day,
    normalize_payload_to_kb,
    parse_rows,
    payload_per_hour_kb,
)
from app.models import CatalogIntegration, ImportBatch, JustificationRecord, Project, SourceIntegrationRow
from app.models.project import ImportStatus
from app.schemas.imports import (
    ImportBatchDeleteResponse,
    ImportBatchListResponse,
    ImportBatchResponse,
    ImportQualityAssistantResponse,
    ImportQualityFinding,
    ImportQualityMetric,
    NormalizationEventResponse,
    SourceRowListResponse,
    SourceRowResponse,
)
from app.services import audit_service, recalc_service, storage_service
from app.services.capture_template_service import (
    CAPTURE_SHEET_NAME,
    COLUMNS as TEMPLATE_COLUMNS,
    IMPORTER_MIN_VERSION,
    MANIFEST_SHEET_NAME,
    TEMPLATE_VERSION,
)
from app.services.pattern_support import support_reason_code
from app.services.serializers import parse_bool, parse_float, parse_int, parse_text, sanitize_for_json

SOURCE_SHEET_NAME = CAPTURE_SHEET_NAME
RAW_HEADERS_METADATA_KEY = "__raw_headers__"
TEMPLATE_VERSION_METADATA_KEY = "__template_version__"
TEMPLATE_COMPATIBILITY_METADATA_KEY = "__template_compatibility__"
TEMPLATE_GENERATED_AT_METADATA_KEY = "__template_generated_at__"
FALLBACK_COLUMN_INDEXES: dict[str, int] = {
    "seq_number": 1,
    "interface_id": 2,
    "owner": 3,
    "brand": 4,
    "business_process": 5,
    "interface_name": 6,
    "description": 7,
    "status": 8,
    "mapping_status": 9,
    "initial_scope": 10,
    "complexity": 11,
    "frequency": 12,
    "type": 13,
    "base": 14,
    "interface_status": 15,
    "is_real_time": 16,
    "trigger_type": 17,
    "response_size_kb": 18,
    "payload_per_execution_kb": 19,
    "is_fan_out": 20,
    "fan_out_targets": 21,
    "source_system": 22,
    "source_technology": 23,
    "source_api_reference": 24,
    "source_owner": 25,
    "destination_system": 26,
    "destination_technology_1": 27,
    "destination_technology_2": 28,
    "destination_owner": 29,
    "calendarization": 30,
    "selected_pattern": 33,
    "pattern_rationale": 34,
    "comments": 35,
    "retry_policy": 36,
    "core_tools": 37,
    "additional_tools_overlays": 38,
    "qa_status": 39,
    "uncertainty": 40,
}
_MISSING = object()
_PAYLOAD_WITH_UNIT_PATTERN = re.compile(
    r"^\s*(?P<value>-?\d+(?:[.,]\d+)?)\s*(?P<unit>kb|mb)\s*$",
    re.IGNORECASE,
)


def _normalize_header_key(value: str) -> str:
    collapsed = " ".join(value.strip().lower().replace("\n", " ").split())
    return normalize("NFKD", collapsed).encode("ascii", "ignore").decode("ascii")


def _header_alias_matches(alias: str, header: str) -> bool:
    if header == alias:
        return True
    return (
        header.startswith(f"{alias} ")
        or header.startswith(f"{alias}(")
        or header.startswith(f"{alias}:")
        or header.startswith(f"{alias}-")
    )


def _bad_request(detail: str, error_code: str) -> HTTPException:
    return HTTPException(status_code=400, detail={"detail": detail, "error_code": error_code})


def _read_template_manifest(workbook: Any) -> dict[str, str]:
    """Read the hidden template manifest without depending on fixed cell coordinates."""

    if MANIFEST_SHEET_NAME not in workbook.sheetnames:
        return {}
    sheet = workbook[MANIFEST_SHEET_NAME]
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value != "MANIFEST_KEY":
                continue
            result: dict[str, str] = {}
            for manifest_row in range(cell.row + 1, sheet.max_row + 1):
                key = sheet.cell(manifest_row, cell.column).value
                value = sheet.cell(manifest_row, cell.column + 1).value
                if key in (None, ""):
                    break
                result[str(key)] = "" if value is None else str(value)
            return result
    return {}


def _validate_template_version(manifest: dict[str, str]) -> str:
    """Return a compatibility label or reject a workbook from a future major contract."""

    version = manifest.get("template_version")
    if not version:
        return "legacy_v1_accepted"
    try:
        major = int(version.split(".", 1)[0])
        current_major = int(TEMPLATE_VERSION.split(".", 1)[0])
    except ValueError as exc:
        raise _bad_request(
            f"Template version '{version}' is not valid. Download a fresh template from the App.",
            "IMPORT_TEMPLATE_VERSION_INVALID",
        ) from exc
    if major > current_major:
        raise _bad_request(
            f"Template v{version} requires a newer importer. This environment supports through v{TEMPLATE_VERSION}.",
            "IMPORT_TEMPLATE_VERSION_UNSUPPORTED",
        )
    return "current" if version == TEMPLATE_VERSION else "older_supported"


def _assert_no_capture_formulas(sheet: Any) -> None:
    """Reject formulas in capture cells to prevent hidden logic and formula injection."""

    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            if cell.data_type == "f" or (isinstance(cell.value, str) and cell.value.startswith("=")):
                raise _bad_request(
                    f"Formula found in {SOURCE_SHEET_NAME}!{cell.coordinate}. Replace it with its final value before upload.",
                    "IMPORT_FORMULA_NOT_ALLOWED",
                )


def _validate_current_headers(all_rows: list[list], manifest: dict[str, str]) -> None:
    """Keep the current capture contract exact while preserving older workbooks."""

    if manifest.get("template_version") != TEMPLATE_VERSION:
        return
    header_index = detect_header_row(all_rows)
    actual_headers = [str(value).strip() if value is not None else "" for value in all_rows[header_index]]
    expected_headers = [column.header for column in TEMPLATE_COLUMNS]
    if actual_headers[: len(expected_headers)] != expected_headers:
        raise _bad_request(
            f"The governed v{TEMPLATE_VERSION} capture headers were renamed, removed, or reordered. Download a fresh template and paste values only into its capture rows.",
            "IMPORT_TEMPLATE_HEADERS_CHANGED",
        )


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


def _extract_raw_headers(header_map: dict[str, str] | None) -> dict[str, str]:
    if not header_map:
        return {}
    encoded_headers = header_map.get(RAW_HEADERS_METADATA_KEY)
    if not encoded_headers:
        return {}
    try:
        payload = json.loads(encoded_headers)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}


def _header_label_for_field(header_map: dict[str, str], field: str) -> str | None:
    raw_headers = _extract_raw_headers(header_map)
    column_index = header_map.get(field)
    if column_index is None:
        return None
    return raw_headers.get(column_index)


def _normalize_raw_header_label(value: object, index: int, used_labels: set[str]) -> str:
    base_label = str(value).strip() if value is not None else ""
    if not base_label:
        base_label = f"Column {index + 1}"

    label = base_label
    duplicate_number = 2
    while label in used_labels:
        label = f"{base_label} ({duplicate_number})"
        duplicate_number += 1
    used_labels.add(label)
    return label


def _build_raw_header_labels(raw_headers: list[object]) -> dict[str, str]:
    used_labels: set[str] = set()
    return {
        str(index): _normalize_raw_header_label(value, index, used_labels)
        for index, value in enumerate(raw_headers)
    }


def _build_raw_column_values(raw_data: dict[str, object], raw_headers: dict[str, str]) -> dict[str, object]:
    values: dict[str, object] = {}
    for raw_key, raw_value in raw_data.items():
        if raw_key in raw_headers:
            values[raw_headers[raw_key]] = raw_value
            continue
        if raw_key.isdigit():
            values[f"Column {int(raw_key) + 1}"] = raw_value
            continue
        values[raw_key] = raw_value
    return values


def _extract_value_from_header_alias(raw_data: dict[str, object], field: str) -> object:
    aliases = HEADER_ALIASES.get(field, [])
    if not aliases:
        return _MISSING

    normalized_key_map = {
        _normalize_header_key(str(raw_key)): raw_key
        for raw_key in raw_data
        if isinstance(raw_key, str)
    }

    for alias in aliases:
        normalized_alias = _normalize_header_key(alias)
        direct_key = normalized_key_map.get(normalized_alias)
        if direct_key is not None:
            return raw_data[direct_key]
        for normalized_header, raw_key in normalized_key_map.items():
            if _header_alias_matches(normalized_alias, normalized_header):
                return raw_data[raw_key]

    return _MISSING


def _extract_raw_value(raw_data: dict[str, object], header_map: dict[str, str], field: str) -> object:
    if field in raw_data:
        return raw_data.get(field)

    alias_value = _extract_value_from_header_alias(raw_data, field)
    if alias_value is not _MISSING:
        return alias_value

    raw_headers = _extract_raw_headers(header_map)
    column_index = header_map.get(field)
    if column_index is None:
        fallback_index = FALLBACK_COLUMN_INDEXES.get(field)
        if fallback_index is None:
            return None
        column_index = str(fallback_index)
    if column_index == "-1":
        return None
    header_label = raw_headers.get(column_index)
    if header_label and header_label in raw_data:
        return raw_data.get(header_label)
    if column_index in raw_data:
        return raw_data.get(column_index)
    if column_index.isdigit():
        fallback_label = f"Column {int(column_index) + 1}"
        if fallback_label in raw_data:
            return raw_data.get(fallback_label)
    return raw_data.get(column_index)


def _parse_payload_measurement(raw_value: object) -> tuple[float | None, str | None]:
    if raw_value in (None, ""):
        return None, None
    if isinstance(raw_value, (int, float)):
        return float(raw_value), None

    text = str(raw_value).strip()
    match = _PAYLOAD_WITH_UNIT_PATTERN.match(text)
    if match:
        numeric = match.group("value").replace(",", ".")
        return float(numeric), match.group("unit").upper()
    return parse_float(text), None


def _infer_payload_unit(raw_value: object, header_label: str | None) -> str:
    _, explicit_unit = _parse_payload_measurement(raw_value)
    if explicit_unit in {"KB", "MB"}:
        return explicit_unit

    normalized_header = _normalize_header_key(header_label or "")
    if "mb" in normalized_header or "mega" in normalized_header:
        return "MB"
    return "KB"


def _normalized_payload_value(
    raw_data: dict[str, object],
    header_map: dict[str, str],
) -> tuple[float | None, dict[str, object] | None]:
    raw_value = _extract_raw_value(raw_data, header_map, "payload_per_execution_kb")
    parsed_value, _ = _parse_payload_measurement(raw_value)
    if parsed_value is None:
        return None, None

    unit = _infer_payload_unit(raw_value, _header_label_for_field(header_map, "payload_per_execution_kb"))
    normalized = (
        normalize_payload_to_kb(parsed_value, "MB").value
        if unit == "MB"
        else normalize_payload_to_kb(parsed_value, "KB").value
    )
    if normalized is None:
        return None, None

    if unit == "MB":
        return normalized, {
            "field": "payload_per_execution_kb",
            "old_value": raw_value,
            "new_value": normalized,
            "rule": "payload_unit_mb_to_kb",
        }
    return normalized, None


def _split_destination_technologies(raw_value: str | None, secondary_value: str | None) -> tuple[str | None, str | None]:
    primary = raw_value.strip() if raw_value else None
    secondary = secondary_value.strip() if secondary_value else None
    if not primary or secondary:
        return primary or None, secondary or None

    separators = ["/", "|", ";", "\n", ","]
    for separator in separators:
        if separator not in primary:
            continue
        parts = [part.strip() for part in re.split(rf"\s*{re.escape(separator)}\s*", primary) if part.strip()]
        if len(parts) == 2:
            return parts[0], parts[1]

    return primary, None


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
    payload_value, _ = _normalized_payload_value(raw_data, header_map)
    destination_technology_1, destination_technology_2 = _split_destination_technologies(
        parse_text(_extract_raw_value(raw_data, header_map, "destination_technology_1")),
        parse_text(_extract_raw_value(raw_data, header_map, "destination_technology_2")),
    )
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
        uncertainty=parse_text(_extract_raw_value(raw_data, header_map, "uncertainty")) or None,
        is_active_row=True,
        retry_policy=parse_text(_extract_raw_value(raw_data, header_map, "retry_policy")),
        idempotency=parse_text(_extract_raw_value(raw_data, header_map, "idempotency")),
        target_latency_sla=parse_text(_extract_raw_value(raw_data, header_map, "target_latency_sla")),
        data_security_classification=parse_text(
            _extract_raw_value(raw_data, header_map, "data_security_classification")
        ),
        retention_processing_window=parse_text(
            _extract_raw_value(raw_data, header_map, "retention_processing_window")
        ),
        business_criticality=parse_text(
            _extract_raw_value(raw_data, header_map, "business_criticality")
        ),
        additional_tools_overlays=parse_text(
            _extract_raw_value(raw_data, header_map, "additional_tools_overlays")
        ),
    )
    qa_reasons = list(qa_result.reasons)
    support_reason = support_reason_code(
        parse_text(_extract_raw_value(raw_data, header_map, "selected_pattern"))
    )
    if support_reason and support_reason not in qa_reasons:
        qa_reasons.append(support_reason)
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
        business_criticality=parse_text(_extract_raw_value(raw_data, header_map, "business_criticality")),
        status=parse_text(_extract_raw_value(raw_data, header_map, "status")),
        mapping_status=parse_text(_extract_raw_value(raw_data, header_map, "mapping_status")),
        initial_scope=parse_text(_extract_raw_value(raw_data, header_map, "initial_scope")),
        complexity=parse_text(_extract_raw_value(raw_data, header_map, "complexity")),
        frequency=frequency_value,
        type=parse_text(_extract_raw_value(raw_data, header_map, "type")),
        base=parse_text(_extract_raw_value(raw_data, header_map, "base")),
        interface_status=parse_text(_extract_raw_value(raw_data, header_map, "interface_status")),
        is_real_time=parse_bool(_extract_raw_value(raw_data, header_map, "is_real_time")),
        target_latency_sla=parse_text(_extract_raw_value(raw_data, header_map, "target_latency_sla")),
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
        destination_technology_1=destination_technology_1,
        destination_technology_2=destination_technology_2,
        destination_owner=parse_text(_extract_raw_value(raw_data, header_map, "destination_owner")),
        data_security_classification=parse_text(
            _extract_raw_value(raw_data, header_map, "data_security_classification")
        ),
        executions_per_day=execs_per_day,
        payload_per_hour_kb=payload_hour_result.value if payload_hour_result else None,
        selected_pattern=parse_text(_extract_raw_value(raw_data, header_map, "selected_pattern")),
        pattern_rationale=parse_text(_extract_raw_value(raw_data, header_map, "pattern_rationale")),
        comments=parse_text(_extract_raw_value(raw_data, header_map, "comments")),
        retry_policy=parse_text(_extract_raw_value(raw_data, header_map, "retry_policy")),
        idempotency=parse_text(_extract_raw_value(raw_data, header_map, "idempotency")),
        core_tools=parse_text(_extract_raw_value(raw_data, header_map, "core_tools")),
        additional_tools_overlays=parse_text(
            _extract_raw_value(raw_data, header_map, "additional_tools_overlays")
        ),
        qa_status="OK" if not qa_reasons else "REVISAR",
        qa_reasons=qa_reasons,
        calendarization=parse_text(_extract_raw_value(raw_data, header_map, "calendarization")),
        retention_processing_window=parse_text(
            _extract_raw_value(raw_data, header_map, "retention_processing_window")
        ),
        uncertainty=parse_text(_extract_raw_value(raw_data, header_map, "uncertainty")),
    )


async def create_import_batch(
    project_id: str,
    filename: str,
    db: AsyncSession,
    storage_reference: str | None = None,
) -> ImportBatch:
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
        storage_reference=storage_reference,
        parser_version=IMPORTER_MIN_VERSION,
        status=ImportStatus.PENDING,
    )
    db.add(batch)
    await db.flush()
    await db.refresh(batch)
    return batch


async def process_import(batch_id: str, source_reference: str, db: AsyncSession) -> ImportBatch:
    """Parse the workbook, persist all source rows, and materialize included catalog rows."""

    batch = await db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Import batch not found", "error_code": "IMPORT_BATCH_NOT_FOUND"},
        )

    batch.status = ImportStatus.PROCESSING
    await db.flush()

    workbook = load_workbook(
        filename=BytesIO(storage_service.read_bytes(source_reference)),
        data_only=False,
        read_only=True,
    )
    manifest = _read_template_manifest(workbook)
    compatibility = _validate_template_version(manifest)
    if SOURCE_SHEET_NAME not in workbook.sheetnames:
        raise _bad_request(
            f"Required sheet '{SOURCE_SHEET_NAME}' not found in workbook.",
            "IMPORT_SHEET_NOT_FOUND",
        )
    sheet = workbook[SOURCE_SHEET_NAME]
    _assert_no_capture_formulas(sheet)
    all_rows = [list(row) for row in sheet.iter_rows(values_only=True)]
    _validate_current_headers(all_rows, manifest)
    import_result = parse_rows(all_rows)
    header_row_index = detect_header_row(all_rows)
    raw_header_labels = _build_raw_header_labels(all_rows[header_row_index] if all_rows else [])
    stored_header_map = {
        **import_result.header_map,
        RAW_HEADERS_METADATA_KEY: json.dumps(raw_header_labels, ensure_ascii=True),
        TEMPLATE_VERSION_METADATA_KEY: manifest.get("template_version", "1.x-unversioned"),
        TEMPLATE_COMPATIBILITY_METADATA_KEY: compatibility,
        TEMPLATE_GENERATED_AT_METADATA_KEY: manifest.get("generated_at_utc", ""),
    }
    correlation_id = str(uuid.uuid4())

    for parsed_row in import_result.rows:
        normalization_events = [
            sanitize_for_json(event.__dict__) for event in parsed_row.normalization_events
        ]
        raw_column_values = _build_raw_column_values(parsed_row.raw_data, raw_header_labels)
        _, payload_event = _normalized_payload_value(raw_column_values, stored_header_map)
        if payload_event is not None:
            normalization_events.append(sanitize_for_json(payload_event))
        source_row = SourceIntegrationRow(
            import_batch_id=batch.id,
            source_row_number=parsed_row.source_row_number,
            raw_data=sanitize_for_json(raw_column_values),
            included=parsed_row.included,
            exclusion_reason=parsed_row.exclusion_reason,
            normalization_events=normalization_events,
        )
        db.add(source_row)
        await db.flush()

        for event in normalization_events:
            event_dict = cast(dict[str, Any], event)
            await audit_service.emit(
                event_type="normalization",
                entity_type="source_integration_row",
                entity_id=source_row.id,
                actor_id="system-import",
                old_value={"field": event_dict["field"], "value": event_dict["old_value"]},
                new_value={
                    "field": event_dict["field"],
                    "value": event_dict["new_value"],
                    "rule": event_dict["rule"],
                },
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
                    normalization_events=cast(list[dict[str, Any]], normalization_events),
                    header_map=stored_header_map,
                )
            )

    batch.source_row_count = import_result.source_row_count
    batch.tbq_y_count = import_result.tbq_y_count
    batch.excluded_count = import_result.excluded_count
    batch.loaded_count = import_result.loaded_count
    batch.header_map = stored_header_map
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
    batch.error_details = cast(dict[str, Any] | None, sanitize_for_json(error_details))
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


def _quality_metric(label: str, value: str, detail: str) -> ImportQualityMetric:
    return ImportQualityMetric(label=label, value=value, detail=detail)


def _quality_finding(
    severity: str,
    title: str,
    summary: str,
    action_label: str,
    action_href: str,
) -> ImportQualityFinding:
    return ImportQualityFinding(
        severity=severity,
        title=title,
        summary=summary,
        action_label=action_label,
        action_href=action_href,
    )


def _quality_pct(complete: int, total: int) -> str:
    return f"{round((complete / total) * 100)}%" if total else "0%"


def _source_row_has_value(row: SourceIntegrationRow, header_map: dict[str, str], field: str) -> bool:
    value = _extract_raw_value(cast(dict[str, object], row.raw_data or {}), header_map, field)
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


async def get_import_quality_assistant(
    project_id: str,
    batch_id: str,
    db: AsyncSession,
) -> ImportQualityAssistantResponse:
    """Return deterministic data-quality guidance for one import batch."""

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

    source_rows = sorted(batch.source_rows, key=lambda row: row.source_row_number)
    included_rows = [row for row in source_rows if row.included]
    excluded_rows = [row for row in source_rows if not row.included]
    header_map = cast(dict[str, str], batch.header_map or {})
    normalization_event_count = sum(len(row.normalization_events or []) for row in source_rows)
    included_total = len(included_rows)
    coverage_fields = {
        "Payload": "payload_per_execution_kb",
        "Pattern": "selected_pattern",
        "Trigger": "trigger_type",
        "Source": "source_system",
        "Destination": "destination_system",
    }
    coverage_counts = {
        label: sum(1 for row in included_rows if _source_row_has_value(row, header_map, field))
        for label, field in coverage_fields.items()
    }
    metrics = [
        _quality_metric("Rows parsed", str(len(source_rows)), "Source rows persisted from this workbook batch."),
        _quality_metric("Included rows", str(len(included_rows)), "Rows that entered the governed catalog flow."),
        _quality_metric("Excluded rows", str(len(excluded_rows)), "Rows excluded by import rules or workbook evidence."),
        _quality_metric(
            "Normalizations",
            str(normalization_event_count),
            "Frequency, payload, or header normalization events captured during ingest.",
        ),
        *[
            _quality_metric(label, _quality_pct(count, included_total), f"{count} of {included_total} included rows populated.")
            for label, count in coverage_counts.items()
        ],
    ]
    findings: list[ImportQualityFinding] = []
    import_href = f"/projects/{project_id}/import?batch_id={batch_id}"
    catalog_href = f"/projects/{project_id}/catalog"
    if batch.status.value == "failed":
        findings.append(
            _quality_finding(
                "critical",
                "Import failed before catalog governance",
                "The batch did not complete, so no downstream catalog quality can be trusted for this upload.",
                "Review import error",
                import_href,
            )
        )
    if excluded_rows:
        reasons = sorted({row.exclusion_reason or "No reason captured" for row in excluded_rows})
        findings.append(
            _quality_finding(
                "medium",
                "Source rows were excluded",
                f"{len(excluded_rows)} row(s) were excluded. Top reason: {reasons[0]}.",
                "Review excluded rows",
                import_href,
            )
        )
    for label, count in coverage_counts.items():
        if included_total and count < included_total:
            severity = "high" if label in {"Payload", "Pattern", "Trigger"} else "medium"
            findings.append(
                _quality_finding(
                    severity,
                    f"{label} coverage is incomplete",
                    f"{included_total - count} included row(s) are missing {label.lower()} evidence.",
                    "Open governed catalog",
                    catalog_href,
                )
            )
    if normalization_event_count:
        findings.append(
            _quality_finding(
                "positive",
                "Workbook normalization evidence captured",
                f"{normalization_event_count} normalization event(s) preserve the ingest decision trail.",
                "Review source rows",
                import_href,
            )
        )

    if any(finding.severity in {"critical", "high"} for finding in findings):
        next_action = "Resolve high-priority import evidence gaps before using forecasts or AI Review for sign-off."
    elif findings:
        next_action = "Review excluded rows and normalization evidence, then continue catalog governance."
    else:
        next_action = "Import quality is clean; continue with catalog QA, canvas design, and recalculation."
    return ImportQualityAssistantResponse(
        project_id=project_id,
        batch_id=batch_id,
        status=batch.status.value,
        filename=batch.filename,
        row_count=len(source_rows),
        included_count=len(included_rows),
        excluded_count=len(excluded_rows),
        normalization_event_count=normalization_event_count,
        recommended_next_action=next_action,
        metrics=metrics,
        findings=findings,
    )


async def save_upload_file(
    file_name: str,
    contents: bytes,
    *,
    project_id: str = "unassigned",
) -> str:
    """Persist an uploaded source workbook in authoritative Object Storage."""

    key = f"imports/{project_id}/{uuid.uuid4()}-{storage_service.safe_filename(file_name)}"
    return storage_service.put_bytes(
        key,
        contents,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        metadata={"project-id": project_id},
    )


async def delete_import_batch(
    project_id: str,
    batch_id: str,
    actor_id: str,
    db: AsyncSession,
) -> ImportBatchDeleteResponse:
    """Remove one import batch and its governed descendants, then recalculate the project."""

    from app.services.catalog_service import serialize_catalog_integration
    from app.services.justification_service import serialize_justification_record

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
    storage_reference = batch.storage_reference
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
    if storage_reference:
        storage_service.delete(storage_reference)

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
