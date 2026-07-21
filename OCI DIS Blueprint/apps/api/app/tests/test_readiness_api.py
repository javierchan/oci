"""API coverage for runtime readiness diagnostics."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.readiness import _repository_heads


def test_repository_heads_are_independent_of_working_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Resolve Alembic revisions from the API root even when CI runs elsewhere."""

    monkeypatch.chdir(tmp_path)
    assert _repository_heads() == {"20260721_0047"}


@pytest.mark.asyncio
async def test_readiness_reports_metadata_created_test_database(api_client: AsyncClient) -> None:
    """Verify readiness is explicit and structured even under the SQLite test DB."""

    response = await api_client.get("/api/v1/readiness")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["database_migrations"]["ready"] is True
    assert payload["database_migrations"]["pending_revisions"] == []
    assert payload["object_storage"] == {
        "ready": True,
        "bucket": "oci-dis-files",
        "provider": "MinIO",
        "recovery_hint": None,
    }
