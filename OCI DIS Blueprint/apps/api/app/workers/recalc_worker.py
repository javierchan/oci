"""Celery recalculation task for volumetry snapshot generation."""

from __future__ import annotations

from app.core.db import AsyncSessionLocal
from app.services import recalc_service
from app.workers.async_runner import run_async
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.recalc_worker.recalculate_project_task")
def recalculate_project_task(project_id: str, actor_id: str) -> dict[str, object]:
    """Execute a full-project recalculation inside a dedicated async DB session."""

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                snapshot = await recalc_service.recalculate_project(
                    project_id=project_id,
                    actor_id=actor_id,
                    db=db,
                )
                return {
                    "snapshot_id": snapshot.id,
                    "project_id": project_id,
                    "scope": "project",
                    "integration_ids": [],
                    "created_at": snapshot.created_at.isoformat(),
                }

    return run_async(_run())


@celery_app.task(name="app.workers.recalc_worker.recalculate_scoped_task")
def recalculate_scoped_task(
    project_id: str,
    actor_id: str,
    integration_ids: list[str],
) -> dict[str, object]:
    """Execute a scoped recalculation inside a dedicated async DB session."""

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                snapshot = await recalc_service.recalculate_project(
                    project_id=project_id,
                    actor_id=actor_id,
                    db=db,
                )
                metadata = dict(snapshot.snapshot_metadata or {})
                metadata["scope"] = "scoped"
                metadata["integration_ids"] = integration_ids
                snapshot.snapshot_metadata = metadata
                await db.flush()
                await db.refresh(snapshot)
                return {
                    "snapshot_id": snapshot.id,
                    "project_id": project_id,
                    "scope": "scoped",
                    "integration_ids": integration_ids,
                    "created_at": snapshot.created_at.isoformat(),
                }

    return run_async(_run())
