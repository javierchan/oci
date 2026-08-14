"""Celery application configuration for import and recalculation workers."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("oci_dis_blueprint", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.task_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.result_serializer = "json"
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.task_track_started = True
celery_app.conf.worker_prefetch_multiplier = settings.CELERY_WORKER_PREFETCH_MULTIPLIER
celery_app.conf.result_expires = settings.CELERY_RESULT_EXPIRES_SECONDS
celery_app.conf.broker_transport_options = {
    "visibility_timeout": settings.CELERY_VISIBILITY_TIMEOUT_SECONDS,
}
celery_app.conf.imports = (
    "app.workers.agent_worker",
    "app.workers.import_worker",
    "app.workers.knowledge_worker",
    "app.workers.maintenance_worker",
    "app.workers.pricing_worker",
    "app.workers.recalc_worker",
    "app.workers.service_verification_worker",
    "app.workers.synthetic_worker",
)
celery_app.conf.task_routes = {
    "app.workers.agent_worker.execute_agent_run_task": {"queue": "agents"},
    "app.workers.knowledge_worker.execute_scheduled_knowledge_maintenance_task": {
        "queue": "agents"
    },
}

beat_schedule: dict[str, dict[str, object]] = {}
if settings.SERVICE_VERIFICATION_SCHEDULE_ENABLED:
    beat_schedule["service-verification-stale-scan"] = {
        "task": "app.workers.service_verification_worker.execute_stale_service_verification_task",
        "schedule": settings.SERVICE_VERIFICATION_SCHEDULE_SECONDS,
    }
if settings.OCI_GOVERNANCE_SCHEDULE_ENABLED:
    beat_schedule["official-oci-commercial-governance"] = {
        "task": "app.workers.pricing_worker.execute_scheduled_oci_governance_task",
        "schedule": settings.OCI_GOVERNANCE_SCHEDULE_SECONDS,
    }
if settings.APP_KNOWLEDGE_AUTOMATION_ENABLED:
    beat_schedule["app-knowledge-governance"] = {
        "task": "app.workers.knowledge_worker.execute_scheduled_knowledge_maintenance_task",
        "schedule": settings.APP_KNOWLEDGE_SCHEDULE_SECONDS,
    }
beat_schedule["agent-history-retention"] = {
    "task": "app.workers.maintenance_worker.prune_agent_history_task",
    "schedule": settings.AGENT_HISTORY_PRUNE_SCHEDULE_SECONDS,
}
if beat_schedule:
    celery_app.conf.beat_schedule = beat_schedule

# Import worker modules after the Celery app is created so task decorators register
# against this application in both API-side dispatch and worker-side startup flows.
from app.workers import import_worker as _import_worker  # noqa: E402,F401
from app.workers import knowledge_worker as _knowledge_worker  # noqa: E402,F401
from app.workers import maintenance_worker as _maintenance_worker  # noqa: E402,F401
from app.workers import agent_worker as _agent_worker  # noqa: E402,F401
from app.workers import pricing_worker as _pricing_worker  # noqa: E402,F401
from app.workers import recalc_worker as _recalc_worker  # noqa: E402,F401
from app.workers import service_verification_worker as _service_verification_worker  # noqa: E402,F401
from app.workers import synthetic_worker as _synthetic_worker  # noqa: E402,F401
