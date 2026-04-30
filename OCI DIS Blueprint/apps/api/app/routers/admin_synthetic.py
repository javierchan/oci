"""Admin-only router for governed synthetic generation jobs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import TypeVar

from app.core.db import get_db
from app.schemas.synthetic import (
    SyntheticGenerationJobCreateRequest,
    SyntheticGenerationJobListResponse,
    SyntheticGenerationJobResponse,
    SyntheticGenerationPresetListResponse,
)
from app.services import synthetic_service
from app.services.authz import require_admin
from app.workers.synthetic_worker import execute_synthetic_generation_job_task

router = APIRouter(prefix="/admin/synthetic", tags=["Admin Synthetic"])
RouteResult = TypeVar("RouteResult")


async def _with_synthetic_schema_guard(
    operation: Callable[[], Awaitable[RouteResult]],
) -> RouteResult:
    """Translate known schema-readiness failures into structured API responses."""

    try:
        return await operation()
    except (ProgrammingError, OperationalError) as exc:
        synthetic_service.raise_if_synthetic_schema_not_ready(exc)
        raise


@router.get(
    "/presets",
    response_model=SyntheticGenerationPresetListResponse,
    summary="List governed synthetic-generation presets",
)
async def list_presets(
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> SyntheticGenerationPresetListResponse:
    require_admin(actor_role)
    return synthetic_service.list_synthetic_presets()


@router.get(
    "/jobs",
    response_model=SyntheticGenerationJobListResponse,
    summary="List recent synthetic-generation jobs",
)
async def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> SyntheticGenerationJobListResponse:
    require_admin(actor_role)
    return await _with_synthetic_schema_guard(
        lambda: synthetic_service.list_synthetic_jobs(db, limit=limit),
    )


@router.post(
    "/jobs",
    response_model=SyntheticGenerationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new synthetic-generation job",
)
async def create_job(
    body: SyntheticGenerationJobCreateRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> SyntheticGenerationJobResponse:
    require_admin(actor_role)

    async def operation() -> SyntheticGenerationJobResponse:
        async with db.begin():
            job = await synthetic_service.create_synthetic_job(body, actor_id, db)
        try:
            execute_synthetic_generation_job_task.apply_async(args=[job.id], task_id=job.id)
        except Exception as exc:  # pragma: no cover - defensive dispatch path
            async with db.begin():
                await synthetic_service.mark_synthetic_job_failed(
                    job.id,
                    {"detail": f"Unable to dispatch synthetic generation job: {exc}"},
                    db,
                )
            raise HTTPException(
                status_code=503,
                detail={
                    "detail": "Synthetic generation worker could not be dispatched.",
                    "error_code": "SYNTHETIC_JOB_DISPATCH_FAILED",
                },
            ) from exc
        return job

    return await _with_synthetic_schema_guard(operation)


@router.get(
    "/jobs/{job_id}",
    response_model=SyntheticGenerationJobResponse,
    summary="Inspect one synthetic-generation job",
)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> SyntheticGenerationJobResponse:
    require_admin(actor_role)
    return await _with_synthetic_schema_guard(
        lambda: synthetic_service.get_synthetic_job(job_id, db),
    )


@router.post(
    "/jobs/{job_id}/retry",
    response_model=SyntheticGenerationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry a failed synthetic-generation job",
)
async def retry_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> SyntheticGenerationJobResponse:
    require_admin(actor_role)

    async def operation() -> SyntheticGenerationJobResponse:
        async with db.begin():
            job = await synthetic_service.retry_synthetic_job(job_id, actor_id, db)
        try:
            execute_synthetic_generation_job_task.apply_async(args=[job.id], task_id=job.id)
        except Exception as exc:  # pragma: no cover - defensive dispatch path
            async with db.begin():
                await synthetic_service.mark_synthetic_job_failed(
                    job.id,
                    {"detail": f"Unable to dispatch synthetic generation retry: {exc}"},
                    db,
                )
            raise HTTPException(
                status_code=503,
                detail={
                    "detail": "Synthetic generation retry could not be dispatched.",
                    "error_code": "SYNTHETIC_JOB_RETRY_DISPATCH_FAILED",
                },
            ) from exc
        return job

    return await _with_synthetic_schema_guard(operation)


@router.post(
    "/jobs/{job_id}/cleanup",
    response_model=SyntheticGenerationJobResponse,
    summary="Archive and remove a synthetic job's generated assets",
)
async def cleanup_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> SyntheticGenerationJobResponse:
    require_admin(actor_role)

    async def operation() -> SyntheticGenerationJobResponse:
        async with db.begin():
            return await synthetic_service.cleanup_synthetic_job(job_id, actor_id, db)

    return await _with_synthetic_schema_guard(operation)
