"""Recalculation router — synchronous M4 trigger endpoint."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.volumetry import VolumetrySnapshotResponse
from app.services import recalc_service

router = APIRouter(prefix="/recalculate", tags=["Recalculate"])


@router.post("/{project_id}", response_model=VolumetrySnapshotResponse, status_code=status.HTTP_202_ACCEPTED, summary="Trigger full project recalculation")
async def recalculate_project(
    project_id: str,
    actor_id: str = "api-user",
    db: AsyncSession = Depends(get_db),
) -> VolumetrySnapshotResponse:
    async with db.begin():
        snapshot = await recalc_service.recalculate_project(project_id, actor_id, db)
    return recalc_service.serialize_snapshot(snapshot)


@router.post("/{project_id}/scoped", status_code=status.HTTP_202_ACCEPTED, summary="Recalculate a subset of rows")
async def recalculate_scoped(project_id: str, body: dict):
    """Recalculate only the specified integration IDs (faster for single-row edits)."""
    return {"job_id": "placeholder", "status": "queued"}


@router.get("/{project_id}/jobs/{job_id}", summary="Poll recalculation job status")
async def get_job_status(project_id: str, job_id: str):
    return {"job_id": job_id, "status": "pending", "snapshot_id": None}
