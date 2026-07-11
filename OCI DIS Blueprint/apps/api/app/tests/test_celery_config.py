"""Regression coverage for production Celery startup behavior."""

from app.workers.celery_app import celery_app


def test_worker_retries_broker_connection_on_startup() -> None:
    """Keep startup retries explicit across the Celery 6 configuration change."""

    assert celery_app.conf.broker_connection_retry_on_startup is True
