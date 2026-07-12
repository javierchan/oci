"""Dedicated Celery worker task for governed agent runs."""

from __future__ import annotations

from app.core.db import AsyncSessionLocal
from app.services import agent_service
from app.workers.async_runner import run_async
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.agent_worker.execute_agent_run_task")
def execute_agent_run_task(run_id: str) -> dict[str, object]:
    """Execute one persisted agent run on the isolated agents queue."""

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                run = await agent_service.mark_agent_run_running(run_id, db)
            if str(run.status.value if hasattr(run.status, "value") else run.status) == "cancelled":
                return {"run_id": run.id, "status": "cancelled"}
            try:
                async with db.begin():
                    result = await agent_service.run_agent(run_id, db)
                return {"run_id": result.id, "status": result.status, "agent_type": result.agent_type}
            except Exception as exc:  # pragma: no cover - defensive worker path.
                async with db.begin():
                    await agent_service.mark_agent_run_failed(run_id, {"detail": str(exc)[:500]}, db)
                raise

    return run_async(_run())
