"""Celery import task that wraps the synchronous M2 import flow."""

from __future__ import annotations

from app.core.db import AsyncSessionLocal
from app.services import import_service
from app.workers.async_runner import run_async
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.import_worker.process_import_task")
def process_import_task(batch_id: str, source_reference: str) -> dict[str, object]:
    """Execute an import inside a dedicated async DB session."""

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            try:
                async with db.begin():
                    batch = await import_service.process_import(
                        batch_id=batch_id,
                        source_reference=source_reference,
                        db=db,
                    )
                    return {"batch_id": batch.id, "status": batch.status.value}
            except Exception as exc:  # pragma: no cover - defensive worker path
                async with db.begin():
                    await import_service.mark_import_failed(
                        batch_id=batch_id,
                        error_details={"detail": str(exc)},
                        db=db,
                    )
                raise

    return run_async(_run())


@celery_app.task(name="app.workers.import_worker.materialize_import_task")
def materialize_import_task(batch_id: str) -> dict[str, object]:
    """Materialize an externally mapped batch only after explicit human approval."""

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            try:
                async with db.begin():
                    batch = await import_service.materialize_approved_import(batch_id=batch_id, db=db)
                    return {"batch_id": batch.id, "status": batch.status.value}
            except Exception as exc:  # pragma: no cover - defensive worker path
                async with db.begin():
                    await import_service.mark_import_failed(
                        batch_id=batch_id,
                        error_details={"detail": str(exc)},
                        db=db,
                    )
                raise

    return run_async(_run())
