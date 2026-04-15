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
from app.services.serializers import sanitize_for_json


EXPORT_ROOT = Path("uploads/exports")
FILES_DIR = EXPORT_ROOT / "files"
JOBS_DIR = EXPORT_ROOT / "jobs"
TEMPLATE_SHEET_NAME = "Catálogo de Integraciones"

TEMPLATE_HEADERS = [
    "#",
    "ID de Interfaz",
    "Marca",
    "Proceso de Negocio",
    "Interfaz",
    "Descripción",
    "Tipo",
    "Estado Interfaz",
    "Complejidad",
    "Alcance Inicial",
    "Estado",
    "Estado de Mapeo",
    "Sistema de Origen",
    "Tecnología de Origen",
    "API Reference",
    "Propietario de Origen",
    "Sistema de Destino",
    "Tecnología de Destino",
    "Propietario de Destino",
    "Frecuencia",
    "Tamaño KB",
    "TBQ",
    "Patrones",
    "Incertidumbre",
    "Owner",
]

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


async def generate_capture_template(db: AsyncSession) -> bytes:
    """Build the offline integration-capture workbook template."""

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = TEMPLATE_SHEET_NAME

    sheet.merge_cells("A1:Y1")
    sheet.merge_cells("A2:Y2")
    sheet.merge_cells("A3:Y3")
    sheet["A1"] = "OCI DIS Blueprint — Integration Capture Template"
    sheet["A2"] = "Fill from row 7 onwards. Do not modify rows 1-5. Required fields marked with *. TBQ column must be Y for import."
    sheet["A3"] = f"Template v1.0 — generated {_utc_now().date().isoformat()}"

    for row_index in (1, 2, 3):
        cell = sheet[f"A{row_index}"]
        cell.alignment = Alignment(wrap_text=True)
        cell.font = Font(bold=row_index == 1, size=14 if row_index == 1 else 11)

    for column_index, header in enumerate(TEMPLATE_HEADERS, start=1):
        cell = sheet.cell(row=5, column=column_index, value=header)
        cell.fill = _header_fill(column_index)
        cell.font = _header_font(column_index)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for column_index, value in enumerate(TEMPLATE_EXAMPLE_ROW, start=1):
        cell = sheet.cell(row=6, column=column_index, value=value)
        cell.font = EXAMPLE_FONT
        cell.alignment = Alignment(vertical="top", wrap_text=True)

    frequency_values, trigger_values, complexity_values = await _load_template_validations(db)
    validations = [
        ("T7:T200", frequency_values),
        ("G7:G200", trigger_values),
        ("I7:I200", complexity_values),
        ("V7:V200", ["Y", "N"]),
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
        sheet.column_dimensions[sheet.cell(row=5, column=column_index).column_letter].width = max(12, max_length * 1.2)

    sheet.freeze_panes = "A6"

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
