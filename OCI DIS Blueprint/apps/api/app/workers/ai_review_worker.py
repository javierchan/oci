"""Celery worker task for persisted AI review jobs."""

from __future__ import annotations

from app.core.db import AsyncSessionLocal
from app.services import ai_review_service
from app.workers.async_runner import run_async
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.ai_review_worker.execute_ai_review_job_task")
def execute_ai_review_job_task(job_id: str) -> dict[str, object]:
    """Execute one persisted AI review job."""

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                await ai_review_service.mark_ai_review_job_running(job_id, db)
            try:
                async with db.begin():
                    job = await ai_review_service.run_ai_review_job(job_id, db)
                return {
                    "job_id": job.id,
                    "status": job.status,
                    "project_id": job.project_id,
                    "finished_at": job.finished_at.isoformat() if job.finished_at else None,
                }
            except Exception as exc:  # pragma: no cover - defensive worker path
                async with db.begin():
                    await ai_review_service.mark_ai_review_job_failed(job_id, {"detail": str(exc)}, db)
                raise

    return run_async(_run())
