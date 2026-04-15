"""Recalculation router — queued job submission and status endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import Project
from app.schemas.volumetry import (
    RecalculationJobStatusResponse,
    ScopedRecalculationRequest,
)
from app.services import recalc_service
from app.workers.recalc_worker import recalculate_project_task, recalculate_scoped_task

router = APIRouter(prefix="/recalculate", tags=["Recalculate"])


@router.post(
    "/{project_id}",
    response_model=RecalculationJobStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger full project recalculation",
)
async def recalculate_project(
    project_id: str,
    actor_id: str = "api-user",
    db: AsyncSession = Depends(get_db),
) -> RecalculationJobStatusResponse:
    async with db.begin():
        project = await db.get(Project, project_id)
        if project is None:
            raise HTTPException(
                status_code=404,
                detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"},
            )
    task = recalculate_project_task.delay(project_id, actor_id)
    return recalc_service.build_recalculation_job_response(
        job_id=task.id,
        project_id=project_id,
        status="pending",
    )


@router.post(
    "/{project_id}/scoped",
    response_model=RecalculationJobStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Recalculate a subset of rows",
)
async def recalculate_scoped(
    project_id: str,
    body: ScopedRecalculationRequest,
    db: AsyncSession = Depends(get_db),
) -> RecalculationJobStatusResponse:
    """Queue a scoped recalculation while preserving the selected integration scope."""

    async with db.begin():
        integration_ids = await recalc_service.validate_scoped_integration_ids(
            project_id,
            body.integration_ids,
            db,
        )
    task = recalculate_scoped_task.delay(project_id, body.actor_id, integration_ids)
    return recalc_service.build_recalculation_job_response(
        job_id=task.id,
        project_id=project_id,
        status="pending",
        scope="scoped",
        integration_ids=integration_ids,
    )


@router.get(
    "/{project_id}/jobs/{job_id}",
    response_model=RecalculationJobStatusResponse,
    summary="Poll recalculation job status",
)
async def get_job_status(
    project_id: str,
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> RecalculationJobStatusResponse:
    return await recalc_service.get_recalculation_job_status(project_id, job_id, db)
