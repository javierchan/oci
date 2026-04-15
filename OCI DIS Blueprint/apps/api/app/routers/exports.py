"""Exports router — /exports (PRD-039)."""
from fastapi import APIRouter

router = APIRouter(prefix="/exports", tags=["Exports"])


@router.post("/{project_id}/xlsx", summary="Export catalog as XLSX")
async def export_xlsx(project_id: str, snapshot_id: str):
    return {"job_id": "placeholder", "format": "xlsx"}


@router.post("/{project_id}/pdf", summary="Export dashboard as PDF")
async def export_pdf(project_id: str, snapshot_id: str):
    return {"job_id": "placeholder", "format": "pdf"}


@router.post("/{project_id}/json", summary="Export project snapshot as JSON")
async def export_json(project_id: str, snapshot_id: str):
    return {"job_id": "placeholder", "format": "json"}


@router.get("/{project_id}/jobs/{job_id}", summary="Poll export job status")
async def get_export_job(project_id: str, job_id: str):
    return {"job_id": job_id, "status": "pending", "download_url": None}
