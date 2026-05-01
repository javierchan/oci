"""API coverage for runtime readiness diagnostics."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_readiness_reports_metadata_created_test_database(api_client: AsyncClient) -> None:
    """Verify readiness is explicit and structured even under the SQLite test DB."""

    response = await api_client.get("/api/v1/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["database_migrations"]["ready"] is True
    assert payload["database_migrations"]["pending_revisions"] == []
