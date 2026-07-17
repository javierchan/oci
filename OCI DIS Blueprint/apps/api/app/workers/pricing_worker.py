"""Celery tasks for OCI price synchronization and BOM generation."""

from __future__ import annotations

import uuid

import redis

from app.core.config import get_settings
from app.core.db import AsyncSessionLocal
from app.schemas.pricing import PriceSyncRequest
from app.services import bom_service, pricing_service
from app.workers.async_runner import run_async
from app.workers.celery_app import celery_app


SCHEDULE_LOCK_KEY = "oci-dis:governance:official-sources:lock"


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


@celery_app.task(name="app.workers.pricing_worker.execute_scheduled_oci_governance_task")
def execute_scheduled_oci_governance_task() -> dict[str, object]:
    """Run the daily atomic OCI source verification under a Redis lease."""

    settings = get_settings()
    lock_token = str(uuid.uuid4())
    client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    acquired = bool(
        client.set(
            SCHEDULE_LOCK_KEY,
            lock_token,
            nx=True,
            ex=settings.OCI_GOVERNANCE_LOCK_TTL_SECONDS,
        )
    )
    if not acquired:
        return {"status": "skipped", "reason": "verification_already_running"}

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            try:
                async with db.begin():
                    created = await pricing_service.create_sync_job(
                        PriceSyncRequest(currency=settings.OCI_GOVERNANCE_CURRENCY),
                        "system:oci-governance-scheduler",
                        db,
                    )
                async with db.begin():
                    job = await pricing_service.run_sync_job(created.id, db, trigger_type="scheduled")
                return {
                    "status": job.status,
                    "job_id": job.id,
                    "snapshot_id": job.snapshot_id,
                    "changes_detected": job.changes_detected,
                }
            except Exception as exc:  # pragma: no cover - defensive scheduler path
                if "created" in locals():
                    async with db.begin():
                        await pricing_service.mark_sync_job_failed(created.id, {"detail": str(exc)}, db)
                raise

    try:
        return run_async(_run())
    finally:
        client.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
            1,
            SCHEDULE_LOCK_KEY,
            lock_token,
        )
        client.close()


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
