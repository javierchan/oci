"""Celery tasks for OCI price synchronization and BOM generation."""

from __future__ import annotations

from app.core.db import AsyncSessionLocal
from app.services import bom_service, pricing_service
from app.workers.async_runner import run_async
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.pricing_worker.execute_price_sync_job_task")
def execute_price_sync_job_task(job_id: str) -> dict[str, object]:
    """Execute one persisted price synchronization job."""

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            try:
                async with db.begin():
                    job = await pricing_service.run_sync_job(job_id, db)
                return {
                    "job_id": job.id,
                    "status": job.status,
                    "snapshot_id": job.snapshot_id,
                    "item_count": job.item_count,
                    "changes_detected": job.changes_detected,
                }
            except Exception as exc:  # pragma: no cover - defensive worker path
                async with db.begin():
                    await pricing_service.mark_sync_job_failed(job_id, {"detail": str(exc)}, db)
                raise

    return run_async(_run())


@celery_app.task(name="app.workers.pricing_worker.execute_bom_job_task")
def execute_bom_job_task(job_id: str) -> dict[str, object]:
    """Execute one persisted BOM generation job."""

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            try:
                async with db.begin():
                    job = await bom_service.run_bom_job(job_id, db)
                return {
                    "job_id": job.id,
                    "status": job.status,
                    "bom_snapshot_id": job.bom_snapshot_id,
                }
            except Exception as exc:  # pragma: no cover - defensive worker path
                async with db.begin():
                    await bom_service.mark_bom_job_failed(job_id, {"detail": str(exc)}, db)
                raise

    return run_async(_run())
