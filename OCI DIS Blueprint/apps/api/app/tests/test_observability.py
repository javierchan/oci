"""Request-correlation coverage for the deployment-neutral telemetry contract."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from httpx import AsyncClient

from app.core import observability


@pytest.mark.asyncio
async def test_request_id_is_generated_and_propagated(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_info = Mock()
    monkeypatch.setattr(observability.logger, "info", log_info)
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert len(response.headers["x-request-id"]) >= 8
    assert response.headers["traceparent"].startswith("00-")
    event = json.loads(log_info.call_args.args[0])
    assert event["event"] == "http_request"
    assert event["route"] == "/health"
    assert event["status_code"] == 200
    assert event["request_id"] == response.headers["x-request-id"]
    assert event["trace_id"] in response.headers["traceparent"]


@pytest.mark.asyncio
async def test_valid_upstream_request_id_is_preserved(api_client: AsyncClient) -> None:
    response = await api_client.get(
        "/health",
        headers={"X-Request-ID": "gateway-request-1234"},
    )
    assert response.headers["x-request-id"] == "gateway-request-1234"


@pytest.mark.asyncio
async def test_valid_traceparent_is_continued_with_a_new_server_span(api_client: AsyncClient) -> None:
    trace_id = "1234567890abcdef1234567890abcdef"
    incoming = f"00-{trace_id}-1234567890abcdef-01"
    response = await api_client.get("/health", headers={"traceparent": incoming})

    assert response.status_code == 200
    returned = response.headers["traceparent"]
    assert returned.startswith(f"00-{trace_id}-")
    assert returned.endswith("-01")
    assert returned != incoming
