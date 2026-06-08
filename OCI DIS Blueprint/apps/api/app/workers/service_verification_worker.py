"""Celery worker tasks for governed service-product verification jobs."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.schemas.service_products import ServiceVerificationRunRequest
from app.services import service_product_service
from app.workers.async_runner import run_async
from app.workers.celery_app import celery_app

SCHEDULED_ACTOR_ID = "service-verification-scheduler"


@celery_app.task(name="app.workers.service_verification_worker.execute_service_verification_job_task")
def execute_service_verification_job_task(job_id: str) -> dict[str, object]:
    """Execute one persisted service verification job."""

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            try:
                async with db.begin():
                    job = await service_product_service.run_verification_job(job_id, db)
                return {
                    "job_id": job.id,
                    "status": job.status,
                    "sources_checked": job.sources_checked,
                    "changes_detected": job.changes_detected,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                }
            except Exception as exc:  # pragma: no cover - defensive worker path
                async with db.begin():
                    await service_product_service.mark_verification_job_failed(job_id, {"detail": str(exc)}, db)
                raise

    return run_async(_run())


@celery_app.task(name="app.workers.service_verification_worker.execute_stale_service_verification_task")
def execute_stale_service_verification_task() -> dict[str, object]:
    """Create and execute a scheduled stale-source verification job."""

    settings = get_settings()

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                job = await service_product_service.create_verification_job(
                    ServiceVerificationRunRequest(
                        max_sources=settings.SERVICE_VERIFICATION_STALE_SCAN_MAX_SOURCES,
                        force=False,
                    ),
                    SCHEDULED_ACTOR_ID,
                    db,
                )
            async with db.begin():
                completed = await service_product_service.run_verification_job(job.id, db)
            return {
                "job_id": completed.id,
                "status": completed.status,
                "sources_checked": completed.sources_checked,
                "changes_detected": completed.changes_detected,
                "completed_at": completed.completed_at.isoformat() if completed.completed_at else None,
            }

    return run_async(_run())
