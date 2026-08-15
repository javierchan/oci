"""API coverage for runtime readiness diagnostics."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.core.readiness import _repository_heads
from app import main as main_module


def test_repository_heads_are_independent_of_working_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Resolve Alembic revisions from the API root even when CI runs elsewhere."""

    monkeypatch.chdir(tmp_path)
    assert _repository_heads() == {"20260814_0061"}


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
    assert payload["redis"] == {"ready": True, "recovery_hint": None}
    assert payload["app_knowledge"]["ready"] is True
    assert payload["app_knowledge"]["source_hash"]
    assert payload["app_knowledge"]["runtime_version"].startswith("packaged:")
    assert payload["app_knowledge"]["embedding_model"] == "Cohere Embed v4.0"
    assert payload["app_knowledge"]["vector_count"] > 0


@pytest.mark.asyncio
async def test_readiness_fails_closed_without_mutating_dependencies(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"storage": 0, "redis_close": 0}

    def unavailable_storage() -> None:
        calls["storage"] += 1
        raise ConnectionError("storage unavailable")

    class UnavailableRedis:
        async def ping(self) -> bool:
            raise ConnectionError("redis unavailable")

        async def aclose(self) -> None:
            calls["redis_close"] += 1

    monkeypatch.setattr(
        main_module.storage_service,
        "check_bucket_access",
        unavailable_storage,
    )
    monkeypatch.setattr(
        main_module,
        "create_readiness_redis_client",
        lambda: UnavailableRedis(),
    )

    response = await api_client.get("/readiness")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["object_storage"]["ready"] is False
    assert payload["redis"]["ready"] is False
    assert calls == {"storage": 1, "redis_close": 1}


@pytest.mark.asyncio
async def test_readiness_fails_closed_for_invalid_app_knowledge(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main_module,
        "load_knowledge_base",
        lambda: (_ for _ in ()).throw(ValueError("invalid knowledge")),
    )

    response = await api_client.get("/readiness")
    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["app_knowledge"]["ready"] is False
    assert "same source hash" in payload["app_knowledge"]["recovery_hint"]
