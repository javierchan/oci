"""Synchronous file export helpers for catalog, snapshot, and dashboard artifacts."""

from __future__ import annotations

import json
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from fastapi import HTTPException
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DictionaryOption, Project, VolumetrySnapshot
from app.schemas.export import ExportJobResponse
from app.services import dashboard_service, justification_service, recalc_service
from app.services.catalog_service import list_integrations
from app.services.pattern_support import get_pattern_support
from app.services.serializers import sanitize_for_json


EXPORT_ROOT = Path("uploads/exports")
FILES_DIR = EXPORT_ROOT / "files"
JOBS_DIR = EXPORT_ROOT / "jobs"
TEMPLATE_SHEET_NAME = "Catálogo de Integraciones"
REFERENCE_SHEET_NAME = "Reference"
TEMPLATE_VERSION = "1.0.0"

TEMPLATE_COLUMNS = [
    ("seq_number", "#", "number", "", "Optional"),
    ("interface_id", "ID de Interfaz", "text", "", "Optional"),
    ("brand", "Marca", "text", "", "Required"),
    ("business_process", "Proceso de Negocio", "text", "", "Required"),
    ("interface_name", "Interfaz", "text", "", "Required"),
    ("description", "Descripción", "text", "", "Optional"),
    ("type", "Tipo", "enum", "Dictionary: TRIGGER_TYPE", "Optional"),
    ("interface_status", "Estado Interfaz", "text", "", "Optional"),
    ("complexity", "Complejidad", "enum", "Dictionary: COMPLEXITY", "Optional"),
    ("initial_scope", "Alcance Inicial", "text", "", "Optional"),
    ("status", "Estado", "text", "", "Optional"),
    ("mapping_status", "Estado de Mapeo", "text", "", "Optional"),
    ("source_system", "Sistema de Origen", "text", "", "Required"),
    ("source_technology", "Tecnología de Origen", "text", "", "Optional"),
    ("source_api_reference", "API Reference", "text", "", "Optional"),
    ("source_owner", "Propietario de Origen", "text", "", "Optional"),
    ("destination_system", "Sistema de Destino", "text", "", "Required"),
    ("destination_technology", "Tecnología de Destino", "text", "", "Optional"),
    ("destination_owner", "Propietario de Destino", "text", "", "Optional"),
    ("frequency", "Frecuencia", "enum", "Dictionary: FREQUENCY", "Required"),
    ("payload_per_execution_kb", "Tamaño KB", "number", "", "Optional"),
    ("tbq", "TBQ", "enum", "Y, N", "Required"),
    ("patterns", "Patrones", "text", "", "Optional"),
    ("uncertainty", "Incertidumbre", "text", "", "Optional"),
    ("owner", "Owner", "text", "", "Optional"),
]
TEMPLATE_HEADERS = [column[1] for column in TEMPLATE_COLUMNS]

TEMPLATE_EXAMPLE_ROW = [
    1,
    "INT-001",
    "Oracle",
    "Finance & Accounting",
    "GL Journal Entry Sync",
    "Nightly GL sync from SAP to Oracle ATP",
    "Scheduled",
    "En Progreso",
    "Medio",
    "Si",
    "En Progreso",
    "Pendiente",
    "SAP ECC",
    "REST",
    "/api/v1/gl",
    "Finance Team",
    "Oracle ATP",
    "REST",
    "ATP Team",
    "Una vez al día",
    150,
    "Y",
    "#02",
    "",
    "Finance Architect",
]

REQUIRED_HEADER_COLUMNS = {3, 4, 5, 13, 17, 20, 22}
GOVERNED_HEADER_COLUMNS = {7, 9, 14, 18, 21}

BLUE_FILL = PatternFill(fill_type="solid", fgColor="4472C4")
YELLOW_FILL = PatternFill(fill_type="solid", fgColor="FFC000")
GRAY_FILL = PatternFill(fill_type="solid", fgColor="808080")
WHITE_FONT = Font(color="FFFFFF", bold=True)
BLACK_FONT = Font(color="000000", bold=True)
EXAMPLE_FONT = Font(color="6B7280", italic=True)


def _ensure_export_dirs() -> None:
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _escape_excel_list(values: list[str]) -> str:
    return '"' + ",".join(value.replace('"', '""') for value in values) + '"'


async def _dictionary_values(category: str, db: AsyncSession) -> list[str]:
    result = await db.scalars(
        select(DictionaryOption.value)
        .where(
            DictionaryOption.category == category,
            DictionaryOption.is_active.is_(True),
        )
        .order_by(DictionaryOption.sort_order, DictionaryOption.value)
    )
    return [value for value in result.all() if value]


def _header_fill(index: int) -> PatternFill:
    if index in REQUIRED_HEADER_COLUMNS:
        return BLUE_FILL
    if index in GOVERNED_HEADER_COLUMNS:
        return YELLOW_FILL
    return GRAY_FILL


def _header_font(index: int) -> Font:
    if index in GOVERNED_HEADER_COLUMNS:
        return BLACK_FONT
    return WHITE_FONT


def _set_template_workbook_properties(workbook: Workbook) -> None:
    created_at = _utc_now()
    workbook.properties.creator = "OCI DIS Blueprint"
    workbook.properties.lastModifiedBy = "OCI DIS Blueprint"
    workbook.properties.created = created_at
    workbook.properties.modified = created_at


async def _load_project(project_id: str, db: AsyncSession) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"},
        )
    return project


async def _load_snapshot(project_id: str, snapshot_id: str, db: AsyncSession) -> VolumetrySnapshot:
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
    return snapshot


async def latest_snapshot_id(project_id: str, db: AsyncSession) -> str:
    """Return the latest volumetry snapshot ID for one project."""

    snapshot = await db.scalar(
        select(VolumetrySnapshot)
        .where(VolumetrySnapshot.project_id == project_id)
        .order_by(VolumetrySnapshot.created_at.desc())
    )
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Volumetry snapshot not found", "error_code": "VOLUMETRY_SNAPSHOT_NOT_FOUND"},
        )
    return snapshot.id


def _job_file(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _file_path(job_id: str, extension: str) -> Path:
    return FILES_DIR / f"{job_id}.{extension}"


def _write_job_metadata(job: ExportJobResponse, file_path: Path) -> None:
    payload = sanitize_for_json(
        {
            **job.model_dump(),
            "created_at": job.created_at,
            "file_path": str(file_path),
        }
    )
    _job_file(job.job_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _job_from_payload(payload: dict[str, object]) -> ExportJobResponse:
    created_at = payload.get("created_at")
    normalized = {key: value for key, value in payload.items() if key != "file_path"}
    if isinstance(created_at, str):
        normalized["created_at"] = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return ExportJobResponse(**cast(dict[str, Any], normalized))


async def _build_job(
    project_id: str,
    snapshot_id: str,
    export_format: str,
    filename: str,
    file_path: Path,
) -> ExportJobResponse:
    created_at = _utc_now()
    job_id = file_path.stem
    job = ExportJobResponse(
        job_id=job_id,
        project_id=project_id,
        snapshot_id=snapshot_id,
        format=export_format,
        status="completed",
        filename=filename,
        download_url=f"/api/v1/exports/{project_id}/jobs/{job_id}/download",
        created_at=created_at,
    )
    _write_job_metadata(job, file_path)
    return job


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _excel_cell_value(value: object) -> object:
    serialized = sanitize_for_json(value)
    if isinstance(serialized, (list, dict)):
        return json.dumps(serialized, ensure_ascii=True)
    return serialized


def _pattern_support_payload(pattern_ids: list[str]) -> dict[str, object]:
    selected_pattern_ids = sorted({pattern_id for pattern_id in pattern_ids if pattern_id})
    return {
        "fully_supported_pattern_ids": [
            pattern_id
            for pattern_id in selected_pattern_ids
            if get_pattern_support(pattern_id).parity_ready
        ],
        "reference_only_pattern_ids": [
            pattern_id
            for pattern_id in selected_pattern_ids
            if not get_pattern_support(pattern_id).parity_ready
        ],
    }


async def generate_capture_template(db: AsyncSession) -> bytes:
    """Build the offline integration-capture workbook template."""

    workbook = Workbook()
    _set_template_workbook_properties(workbook)
    sheet = workbook.active
    sheet.title = TEMPLATE_SHEET_NAME

    for column_index, header in enumerate(TEMPLATE_HEADERS, start=1):
        cell = sheet.cell(row=1, column=column_index, value=header)
        cell.fill = _header_fill(column_index)
        cell.font = _header_font(column_index)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for column_index, value in enumerate(TEMPLATE_EXAMPLE_ROW, start=1):
        cell = sheet.cell(row=2, column=column_index, value=value)
        cell.font = EXAMPLE_FONT
        cell.alignment = Alignment(vertical="top", wrap_text=True)

    frequency_values, trigger_values, complexity_values = await _load_template_validations(db)
    validations = [
        ("T3:T200", frequency_values),
        ("G3:G200", trigger_values),
        ("I3:I200", complexity_values),
        ("V3:V200", ["Y", "N"]),
    ]
    for cell_range, values in validations:
        if not values:
            continue
        validation = DataValidation(
            type="list",
            formula1=_escape_excel_list(values),
            allow_blank=True,
        )
        validation.add(cell_range)
        sheet.add_data_validation(validation)

    for column_index, header in enumerate(TEMPLATE_HEADERS, start=1):
        max_length = max(len(str(header)), len(str(TEMPLATE_EXAMPLE_ROW[column_index - 1])))
        column_letter = sheet.cell(row=1, column=column_index).column_letter
        sheet.column_dimensions[column_letter].width = max(15, max_length * 1.2)

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{sheet.cell(row=1, column=len(TEMPLATE_HEADERS)).column_letter}2"

    reference_sheet = workbook.create_sheet(REFERENCE_SHEET_NAME)
    reference_sheet.append(["Column Name", "Canonical Field", "Data Type", "Accepted Values", "Requirement"])
    for index, (field_name, header, data_type, accepted_values, requirement) in enumerate(TEMPLATE_COLUMNS, start=1):
        reference_sheet.append([header, field_name, data_type, accepted_values or "Free text", requirement])
        reference_sheet.column_dimensions["A"].width = 24
        reference_sheet.column_dimensions["B"].width = 24
        reference_sheet.column_dimensions["C"].width = 16
        reference_sheet.column_dimensions["D"].width = 28
        reference_sheet.column_dimensions["E"].width = 14
        if index == 1:
            for cell in reference_sheet[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    reference_sheet.freeze_panes = "A2"
    reference_sheet.auto_filter.ref = "A1:E1"

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


async def _load_template_validations(db: AsyncSession) -> tuple[list[str], list[str], list[str]]:
    frequency_values = await _dictionary_values("FREQUENCY", db)
    trigger_values = await _dictionary_values("TRIGGER_TYPE", db)
    complexity_values = await _dictionary_values("COMPLEXITY", db)
    return frequency_values, trigger_values, complexity_values


def _render_basic_pdf(lines: list[str], file_path: Path) -> None:
    sanitized = [line[:110] for line in lines]
    content_parts = ["BT", "/F1 12 Tf", "50 790 Td"]
    for index, line in enumerate(sanitized):
        if index > 0:
            content_parts.append("0 -16 Td")
        content_parts.append(f"({_pdf_escape(line)}) Tj")
    content_parts.append("ET")
    stream = "\n".join(content_parts).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("ascii")
    )
    file_path.write_bytes(pdf)


async def create_xlsx_export(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession,
) -> ExportJobResponse:
    """Generate a workbook with catalog, row-level volumetry, and consolidated totals."""

    await _load_project(project_id, db)
    snapshot = await _load_snapshot(project_id, snapshot_id, db)
    catalog_page = await list_integrations(project_id, page=1, page_size=10_000, filters={}, db=db)

    workbook = Workbook()
    catalog_sheet = workbook.active
    catalog_sheet.title = "Catalog"
    catalog_rows = [item.model_dump() for item in catalog_page.integrations]
    catalog_headers = list(catalog_rows[0].keys()) if catalog_rows else ["id"]
    catalog_sheet.append(catalog_headers)
    for row in catalog_rows:
        catalog_sheet.append([_excel_cell_value(row.get(header)) for header in catalog_headers])

    volumetry_sheet = workbook.create_sheet("Volumetry")
    volumetry_headers = [
        "integration_id",
        "executions_per_day",
        "payload_per_hour_kb",
        "oic_billing_msgs_month",
        "functions_invocations_month",
        "functions_execution_units_gb_s",
        "data_integration_gb_month",
        "streaming_gb_month",
        "streaming_partition_count",
    ]
    volumetry_sheet.append(volumetry_headers)
    for integration_id, metrics in snapshot.row_results.items():
        volumetry_sheet.append([integration_id, *[metrics.get(header) for header in volumetry_headers[1:]]])

    consolidated_sheet = workbook.create_sheet("Consolidated")
    consolidated_sheet.append(["domain", "metric", "value"])
    for domain, metrics in snapshot.consolidated.items():
        for metric, value in metrics.items():
            consolidated_sheet.append([domain, metric, _excel_cell_value(value)])

    support_sheet = workbook.create_sheet("Pattern Support")
    support_sheet.append(["Pattern ID", "Support", "Parity Ready", "Summary"])
    selected_pattern_ids = sorted(
        {
            str(row.get("selected_pattern"))
            for row in catalog_rows
            if row.get("selected_pattern")
        }
    )
    if selected_pattern_ids:
        for pattern_id in selected_pattern_ids:
            support = get_pattern_support(pattern_id)
            support_sheet.append(
                [pattern_id, support.badge_label, "Yes" if support.parity_ready else "No", support.summary]
            )
    else:
        support_sheet.append(["—", "No assigned patterns", "—", "This export does not include any selected pattern IDs."])

    _ensure_export_dirs()
    job_id = str(uuid4())
    file_path = _file_path(job_id, "xlsx")
    workbook.save(file_path)
    return await _build_job(
        project_id=project_id,
        snapshot_id=snapshot_id,
        export_format="xlsx",
        filename=f"{project_id}-{snapshot_id}.xlsx",
        file_path=file_path,
    )


async def create_json_export(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession,
) -> ExportJobResponse:
    """Generate a JSON snapshot bundle for one project and volumetry snapshot."""

    project = await _load_project(project_id, db)
    snapshot = await _load_snapshot(project_id, snapshot_id, db)
    catalog_page = await list_integrations(project_id, page=1, page_size=10_000, filters={}, db=db)
    dashboard_snapshot = await dashboard_service.get_snapshot(project_id, snapshot_id, db)
    justifications = await justification_service.list_justifications(project_id, db)

    payload = sanitize_for_json(
        {
            "project": {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "owner_id": project.owner_id,
            },
            "snapshot": recalc_service.serialize_snapshot(snapshot).model_dump(),
            "dashboard": dashboard_snapshot.model_dump(),
            "catalog": catalog_page.model_dump(),
            "justifications": justifications.model_dump(),
            "pattern_support_boundary": _pattern_support_payload(
                [item.selected_pattern for item in catalog_page.integrations if item.selected_pattern]
            ),
            "exported_at": _utc_now(),
        }
    )

    _ensure_export_dirs()
    job_id = str(uuid4())
    file_path = _file_path(job_id, "json")
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return await _build_job(
        project_id=project_id,
        snapshot_id=snapshot_id,
        export_format="json",
        filename=f"{project_id}-{snapshot_id}.json",
        file_path=file_path,
    )


async def create_pdf_export(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession,
) -> ExportJobResponse:
    """Generate a simple technical dashboard PDF summary."""

    project = await _load_project(project_id, db)
    dashboard_snapshot = await dashboard_service.get_snapshot(project_id, snapshot_id, db)
    catalog_page = await list_integrations(project_id, page=1, page_size=10_000, filters={}, db=db)
    support_boundary = _pattern_support_payload(
        [item.selected_pattern for item in catalog_page.integrations if item.selected_pattern]
    )

    lines = [
        f"OCI DIS Blueprint Dashboard Export - {project.name}",
        f"Project ID: {project_id}",
        f"Snapshot ID: {dashboard_snapshot.snapshot_id}",
        f"OIC msgs/month: {dashboard_snapshot.kpi_strip.oic_msgs_month:g}",
        f"OIC peak packs/hour: {dashboard_snapshot.kpi_strip.peak_packs_hour:g}",
        (
            "DI workspace active: "
            f"{'Yes' if dashboard_snapshot.kpi_strip.di_workspace_active else 'No'}"
        ),
        f"DI GB/month: {dashboard_snapshot.kpi_strip.di_data_processed_gb_month:g}",
        f"Functions GB-s: {dashboard_snapshot.kpi_strip.functions_execution_units_gb_s:g}",
        f"QA OK %: {dashboard_snapshot.maturity.qa_ok_pct:.2f}",
        f"Pattern assigned %: {dashboard_snapshot.maturity.pattern_assigned_pct:.2f}",
    ]
    if support_boundary["reference_only_pattern_ids"]:
        lines.append(
            "Reference-only patterns in use: "
            + ", ".join(cast(list[str], support_boundary["reference_only_pattern_ids"]))
        )
    if support_boundary["fully_supported_pattern_ids"]:
        lines.append(
            "Parity-ready patterns in use: "
            + ", ".join(cast(list[str], support_boundary["fully_supported_pattern_ids"]))
        )
    for risk in dashboard_snapshot.risks[:5]:
        lines.append(f"Risk {risk.label}: {risk.count}")

    _ensure_export_dirs()
    job_id = str(uuid4())
    file_path = _file_path(job_id, "pdf")
    _render_basic_pdf(lines, file_path)
    return await _build_job(
        project_id=project_id,
        snapshot_id=snapshot_id,
        export_format="pdf",
        filename=f"{project_id}-{snapshot_id}.pdf",
        file_path=file_path,
    )


async def get_export_job(project_id: str, job_id: str) -> ExportJobResponse:
    """Load export metadata from the local export store."""

    metadata_path = _job_file(job_id)
    if not metadata_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"detail": "Export job not found", "error_code": "EXPORT_JOB_NOT_FOUND"},
        )
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    if payload.get("project_id") != project_id:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Export job not found", "error_code": "EXPORT_JOB_NOT_FOUND"},
        )
    return _job_from_payload(payload)


def get_export_file(project_id: str, job_id: str) -> tuple[Path, ExportJobResponse]:
    """Resolve a generated artifact for download."""

    metadata_path = _job_file(job_id)
    if not metadata_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"detail": "Export job not found", "error_code": "EXPORT_JOB_NOT_FOUND"},
        )
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    if payload.get("project_id") != project_id:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Export job not found", "error_code": "EXPORT_JOB_NOT_FOUND"},
        )
    file_path = Path(payload["file_path"])
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"detail": "Export file not found", "error_code": "EXPORT_FILE_NOT_FOUND"},
        )
    job = _job_from_payload(payload)
    return file_path, job
