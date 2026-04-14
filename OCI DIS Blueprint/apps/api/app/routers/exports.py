"""Exports router — synchronous artifact generation for M7."""

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.export import ExportJobResponse
from app.services import export_service

router = APIRouter(prefix="/exports", tags=["Exports"])


@router.get("/template/xlsx", summary="Download the offline capture template workbook")
async def download_capture_template(db: AsyncSession = Depends(get_db)) -> Response:
    workbook_bytes = await export_service.generate_capture_template(db)
    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=oci-dis-capture-template.xlsx"},
    )


@router.post("/{project_id}/xlsx", response_model=ExportJobResponse, summary="Export catalog as XLSX")
async def export_xlsx(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
) -> ExportJobResponse:
    return await export_service.create_xlsx_export(project_id, snapshot_id, db)


@router.post("/{project_id}/pdf", response_model=ExportJobResponse, summary="Export dashboard as PDF")
async def export_pdf(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
) -> ExportJobResponse:
    return await export_service.create_pdf_export(project_id, snapshot_id, db)


@router.post("/{project_id}/json", response_model=ExportJobResponse, summary="Export project snapshot as JSON")
async def export_json(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
) -> ExportJobResponse:
    return await export_service.create_json_export(project_id, snapshot_id, db)


@router.get("/{project_id}/jobs/{job_id}", response_model=ExportJobResponse, summary="Poll export job status")
async def get_export_job(project_id: str, job_id: str) -> ExportJobResponse:
    return await export_service.get_export_job(project_id, job_id)


@router.get("/{project_id}/jobs/{job_id}/download", summary="Download generated export artifact")
async def download_export(project_id: str, job_id: str) -> FileResponse:
    file_path, job = export_service.get_export_file(project_id, job_id)
    media_types = {
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json",
        "pdf": "application/pdf",
    }
    return FileResponse(
        path=file_path,
        media_type=media_types.get(job.format, "application/octet-stream"),
        filename=job.filename,
    )
