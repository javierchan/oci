"""Celery worker task for persisted synthetic-generation jobs."""

from __future__ import annotations

from app.core.db import AsyncSessionLocal
from app.services import synthetic_service
from app.workers.async_runner import run_async
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.synthetic_worker.execute_synthetic_generation_job_task")
def execute_synthetic_generation_job_task(job_id: str) -> dict[str, object]:
    """Execute one persisted synthetic-generation job."""

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                await synthetic_service.mark_synthetic_job_running(job_id, db)
            try:
                async with db.begin():
                    job = await synthetic_service.run_synthetic_generation_job(job_id, db)
                if synthetic_service.should_auto_cleanup_payload(job.normalized_payload):
                    try:
                        async with db.begin():
                            job = await synthetic_service.cleanup_synthetic_job(
                                job_id,
                                synthetic_service.SYNTHETIC_ACTOR_ID,
                                db,
                            )
                    except Exception as cleanup_exc:  # pragma: no cover - defensive worker path
                        async with db.begin():
                            job = await synthetic_service.mark_synthetic_job_failed(
                                job_id,
                                {
                                    "detail": f"Ephemeral auto-cleanup failed after completion: {cleanup_exc}",
                                    "cleanup_failed_after_completion": True,
                                },
                                db,
                            )
                return {
                    "job_id": job.id,
                    "status": job.status,
                    "project_id": job.project_id,
                    "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                }
            except Exception as exc:  # pragma: no cover - defensive worker path
                async with db.begin():
                    await synthetic_service.mark_synthetic_job_failed(job_id, {"detail": str(exc)}, db)
                raise

    return run_async(_run())
