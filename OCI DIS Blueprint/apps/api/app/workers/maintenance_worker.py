"""Scheduled, singleton-safe application maintenance tasks."""

from __future__ import annotations

from scripts.prune_agent_history import prune_history

from app.core.config import get_settings
from app.workers.async_runner import run_async
from app.workers.celery_app import celery_app
from app.workers.scheduled_lease import scheduled_task_lease


SCHEDULE_LOCK_KEY = "oci-dis:maintenance:agent-history:lock"


@celery_app.task(name="app.workers.maintenance_worker.prune_agent_history_task")
def prune_agent_history_task() -> dict[str, object]:
    """Apply bounded AgentRun retention outside API pod startup."""

    settings = get_settings()
    with scheduled_task_lease(
        settings.REDIS_URL,
        SCHEDULE_LOCK_KEY,
        settings.SCHEDULED_TASK_LOCK_TTL_SECONDS,
    ) as acquired:
        if not acquired:
            return {"status": "skipped", "reason": "retention_already_running"}
        deleted = run_async(prune_history())
        if deleted is None:
            return {"status": "deferred", "reason": "schema_not_ready"}
        return {"status": "completed", "deleted": deleted}
