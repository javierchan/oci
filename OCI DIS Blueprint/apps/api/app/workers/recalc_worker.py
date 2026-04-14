"""Celery recalculation task for volumetry snapshot generation."""

from __future__ import annotations

import asyncio

from app.core.db import AsyncSessionLocal
from app.services import recalc_service
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
                return {"snapshot_id": snapshot.id, "project_id": project_id}

    return asyncio.run(_run())
