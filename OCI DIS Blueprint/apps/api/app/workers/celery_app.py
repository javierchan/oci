"""Celery application configuration for import and recalculation workers."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("oci_dis_blueprint", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.task_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.result_serializer = "json"
celery_app.conf.imports = (
    "app.workers.import_worker",
    "app.workers.recalc_worker",
)

# Import worker modules after the Celery app is created so task decorators register
# against this application in both API-side dispatch and worker-side startup flows.
from app.workers import import_worker as _import_worker  # noqa: E402,F401
from app.workers import recalc_worker as _recalc_worker  # noqa: E402,F401
