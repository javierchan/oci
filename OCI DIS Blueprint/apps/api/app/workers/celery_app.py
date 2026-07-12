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
celery_app.conf.imports = (
    "app.workers.agent_worker",
    "app.workers.import_worker",
    "app.workers.pricing_worker",
    "app.workers.recalc_worker",
    "app.workers.service_verification_worker",
    "app.workers.synthetic_worker",
)
celery_app.conf.task_routes = {
    "app.workers.agent_worker.execute_agent_run_task": {"queue": "agents"},
}

if settings.SERVICE_VERIFICATION_SCHEDULE_ENABLED:
    celery_app.conf.beat_schedule = {
        "service-verification-stale-scan": {
            "task": "app.workers.service_verification_worker.execute_stale_service_verification_task",
            "schedule": settings.SERVICE_VERIFICATION_SCHEDULE_SECONDS,
        },
    }

# Import worker modules after the Celery app is created so task decorators register
# against this application in both API-side dispatch and worker-side startup flows.
from app.workers import import_worker as _import_worker  # noqa: E402,F401
from app.workers import agent_worker as _agent_worker  # noqa: E402,F401
from app.workers import pricing_worker as _pricing_worker  # noqa: E402,F401
from app.workers import recalc_worker as _recalc_worker  # noqa: E402,F401
from app.workers import service_verification_worker as _service_verification_worker  # noqa: E402,F401
from app.workers import synthetic_worker as _synthetic_worker  # noqa: E402,F401
