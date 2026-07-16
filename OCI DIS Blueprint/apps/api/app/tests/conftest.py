"""Shared fixtures for backend API integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from ..core.db import get_db
from ..main import app
from ..models import Base
from ..services import storage_service


@pytest.fixture(autouse=True)
def isolated_object_storage(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    """Keep API tests deterministic without requiring an external S3 process."""

    objects: dict[str, bytes] = {}

    def put_bytes(key: str, contents: bytes, **_: object) -> str:
        reference = storage_service.object_reference(key)
        objects[reference] = bytes(contents)
        return reference

    def read_bytes(reference: str) -> bytes:
        if reference.startswith("s3://"):
            try:
                return objects[reference]
            except KeyError as exc:
                raise FileNotFoundError(reference) from exc
        path = Path(reference)
        if not path.is_file():
            raise FileNotFoundError(reference)
        return path.read_bytes()

    def delete(reference: str) -> None:
        if reference.startswith("s3://"):
            objects.pop(reference, None)
        else:
            Path(reference).unlink(missing_ok=True)

    def exists(reference: str) -> bool:
        return reference in objects if reference.startswith("s3://") else Path(reference).is_file()

    def list_keys(prefix: str = "") -> list[str]:
        normalized = prefix.lstrip("/")
        return sorted(
            reference.split("/", 3)[-1]
            for reference in objects
            if reference.split("/", 3)[-1].startswith(normalized)
        )

    monkeypatch.setattr(storage_service, "put_bytes", put_bytes)
    monkeypatch.setattr(storage_service, "read_bytes", read_bytes)
    monkeypatch.setattr(storage_service, "delete", delete)
    monkeypatch.setattr(storage_service, "exists", exists)
    monkeypatch.setattr(storage_service, "list_keys", list_keys)
    monkeypatch.setattr(
        storage_service,
        "delete_prefix",
        lambda prefix: sum(
            1
            for reference in list(objects)
            if reference.split("/", 3)[-1].startswith(prefix.strip("/") + "/")
            and objects.pop(reference, None) is not None
        ),
    )
    monkeypatch.setattr(storage_service, "ensure_bucket", lambda: None)
    return objects


@pytest_asyncio.fixture
async def test_engine() -> AsyncIterator[AsyncEngine]:
    """Create an isolated async SQLite engine for one test."""

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def api_client(test_engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    """Provide an HTTP client bound to the FastAPI app with a test DB override."""

    session_factory = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=cast(Any, app))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()
