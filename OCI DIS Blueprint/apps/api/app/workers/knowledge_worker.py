"""Scheduled ownership loop for App knowledge and OCI embeddings."""

from __future__ import annotations

from app.core.db import AsyncSessionLocal
from app.schemas.agent import AgentCreateRequest
from app.services import agent_service
from app.workers.async_runner import run_async
from app.workers.celery_app import celery_app
from app.workers.scheduled_lease import scheduled_task_lease


SCHEDULED_ACTOR_ID = "app-knowledge-governance-agent"
SCHEDULE_LOCK_KEY = "oci-dis:maintenance:app-knowledge:lock"


@celery_app.task(
    name="app.workers.knowledge_worker.execute_scheduled_knowledge_maintenance_task"
)
def execute_scheduled_knowledge_maintenance_task() -> dict[str, object]:
    """Run the governed agent; publish only a complete validated vector space."""

    from app.core.config import get_settings

    settings = get_settings()

    async def _run() -> dict[str, object]:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                created = await agent_service.create_agent_run(
                    AgentCreateRequest(
                        agent_type="knowledge_maintenance",
                        context={
                            "automation_trigger": "scheduled",
                            "refresh_embeddings": True,
                        },
                        message=(
                            "Synchronize derived App knowledge and OCI embeddings, "
                            "then report any unresolved contract drift."
                        ),
                        include_provider=True,
                    ),
                    actor_id=SCHEDULED_ACTOR_ID,
                    actor_role="Admin",
                    db=db,
                )
            async with db.begin():
                await agent_service.mark_agent_run_running(created.id, db)
            async with db.begin():
                completed = await agent_service.run_agent(created.id, db)
            return {
                "run_id": completed.id,
                "status": completed.status,
                "agent_type": completed.agent_type,
            }

    with scheduled_task_lease(
        settings.REDIS_URL,
        SCHEDULE_LOCK_KEY,
        settings.SCHEDULED_TASK_LOCK_TTL_SECONDS,
    ) as acquired:
        if not acquired:
            return {"status": "skipped", "reason": "knowledge_maintenance_already_running"}
        return run_async(_run())
