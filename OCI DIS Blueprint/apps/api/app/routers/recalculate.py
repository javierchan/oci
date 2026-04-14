"""Recalculation router — /recalculate (PRD-035)."""
from fastapi import APIRouter, BackgroundTasks, status

router = APIRouter(prefix="/recalculate", tags=["Recalculate"])


@router.post("/{project_id}", status_code=status.HTTP_202_ACCEPTED, summary="Trigger full project recalculation")
async def recalculate_project(project_id: str, background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Queues a full deterministic recalculation for the project.
    Returns a job ID to poll for status. On completion creates an immutable VolumetrySnapshot.
    Triggered when: assumptions change, pattern changes, payload changes, trigger type changes.
    """
    return {"job_id": "placeholder", "project_id": project_id, "status": "queued"}


@router.post("/{project_id}/scoped", status_code=status.HTTP_202_ACCEPTED, summary="Recalculate a subset of rows")
async def recalculate_scoped(project_id: str, body: dict):
    """Recalculate only the specified integration IDs (faster for single-row edits)."""
    return {"job_id": "placeholder", "status": "queued"}


@router.get("/{project_id}/jobs/{job_id}", summary="Poll recalculation job status")
async def get_job_status(project_id: str, job_id: str):
    return {"job_id": job_id, "status": "pending", "snapshot_id": None}
