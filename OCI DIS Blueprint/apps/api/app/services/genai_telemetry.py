"""Privacy-safe operational counters for OCI Generative AI provider calls."""

from __future__ import annotations

from collections.abc import Awaitable
from datetime import UTC, datetime
from threading import Lock
from typing import Literal, cast

import redis.asyncio as redis_async
import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings


LOGGER = structlog.get_logger(__name__)

GenAiMetricName = Literal[
    "requests_total",
    "successful_requests_total",
    "retries_total",
    "http_429_total",
    "http_5xx_total",
    "transport_errors_total",
    "guardrail_blocks_total",
    "guardrail_failures_total",
    "responses_fallbacks_total",
    "provider_degradations_total",
]

METRIC_NAMES: tuple[GenAiMetricName, ...] = (
    "requests_total",
    "successful_requests_total",
    "retries_total",
    "http_429_total",
    "http_5xx_total",
    "transport_errors_total",
    "guardrail_blocks_total",
    "guardrail_failures_total",
    "responses_fallbacks_total",
    "provider_degradations_total",
)

_LOCAL_LOCK = Lock()
_LOCAL_COUNTERS: dict[GenAiMetricName, int] = {name: 0 for name in METRIC_NAMES}
_LOCAL_LAST_EVENT_AT: str | None = None
_LOCAL_LAST_DEGRADATION_AT: str | None = None
_REDIS_CLIENTS: dict[str, Redis] = {}


def _redis_client(url: str) -> Redis:
    """Reuse one async Redis pool per process and connection URL."""

    client = _REDIS_CLIENTS.get(url)
    if client is None:
        client = redis_async.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=0.25,
            socket_timeout=0.5,
        )
        _REDIS_CLIENTS[url] = client
    return client


def _record_local(metric: GenAiMetricName, amount: int, timestamp: str) -> None:
    """Maintain a process fallback without storing request or actor dimensions."""

    global _LOCAL_LAST_EVENT_AT, _LOCAL_LAST_DEGRADATION_AT
    with _LOCAL_LOCK:
        _LOCAL_COUNTERS[metric] += amount
        _LOCAL_LAST_EVENT_AT = timestamp
        if metric == "provider_degradations_total":
            _LOCAL_LAST_DEGRADATION_AT = timestamp


async def record_genai_metric(
    settings: Settings,
    metric: GenAiMetricName,
    *,
    amount: int = 1,
) -> None:
    """Increment one bounded metric without affecting the provider request path."""

    if amount <= 0:
        return
    timestamp = datetime.now(UTC).isoformat()
    _record_local(metric, amount, timestamp)
    if not settings.OCI_GENAI_METRICS_REDIS_ENABLED or not settings.REDIS_URL.strip():
        return
    try:
        client = _redis_client(settings.REDIS_URL)
        pipeline = client.pipeline(transaction=False)
        pipeline.hincrby(settings.OCI_GENAI_METRICS_REDIS_KEY, metric, amount)
        metadata = {"last_event_at": timestamp}
        if metric == "provider_degradations_total":
            metadata["last_degradation_at"] = timestamp
        pipeline.hset(settings.OCI_GENAI_METRICS_REDIS_KEY, mapping=metadata)
        pipeline.expire(
            settings.OCI_GENAI_METRICS_REDIS_KEY,
            max(60, settings.OCI_GENAI_METRICS_RETENTION_SECONDS),
        )
        await pipeline.execute()
    except (RedisError, OSError, TimeoutError) as exc:
        await LOGGER.adebug(
            "oci_genai_metrics_redis_unavailable",
            error_type=exc.__class__.__name__,
        )


def _local_snapshot() -> tuple[dict[GenAiMetricName, int], str | None, str | None]:
    with _LOCAL_LOCK:
        return (
            dict(_LOCAL_COUNTERS),
            _LOCAL_LAST_EVENT_AT,
            _LOCAL_LAST_DEGRADATION_AT,
        )


async def get_genai_metrics(settings: Settings) -> dict[str, object]:
    """Return shared Redis counters, falling back to this process when unavailable."""

    if settings.OCI_GENAI_METRICS_REDIS_ENABLED and settings.REDIS_URL.strip():
        try:
            values = await cast(
                Awaitable[dict[str, str]],
                _redis_client(settings.REDIS_URL).hgetall(
                    settings.OCI_GENAI_METRICS_REDIS_KEY
                ),
            )
            if values:
                return {
                    "source": "redis",
                    "retention_seconds": max(60, settings.OCI_GENAI_METRICS_RETENTION_SECONDS),
                    "last_event_at": values.get("last_event_at"),
                    "last_degradation_at": values.get("last_degradation_at"),
                    "counters": {
                        name: int(values.get(name, "0"))
                        for name in METRIC_NAMES
                    },
                }
        except (RedisError, OSError, TimeoutError):
            pass
    counters, last_event_at, last_degradation_at = _local_snapshot()
    return {
        "source": "process",
        "retention_seconds": max(60, settings.OCI_GENAI_METRICS_RETENTION_SECONDS),
        "last_event_at": last_event_at,
        "last_degradation_at": last_degradation_at,
        "counters": cast(dict[str, int], counters),
    }


def reset_local_genai_metrics() -> None:
    """Reset process counters for deterministic tests only."""

    global _LOCAL_LAST_EVENT_AT, _LOCAL_LAST_DEGRADATION_AT
    with _LOCAL_LOCK:
        for name in METRIC_NAMES:
            _LOCAL_COUNTERS[name] = 0
        _LOCAL_LAST_EVENT_AT = None
        _LOCAL_LAST_DEGRADATION_AT = None
