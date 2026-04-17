"""API coverage for OCI service capability profile endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import ServiceCapabilityProfile


@pytest.mark.asyncio
async def test_services_api_returns_seedable_service_profiles(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add(
            ServiceCapabilityProfile(
                service_id="OIC3",
                name="Oracle Integration 3 (OIC Gen3)",
                category="ORCHESTRATION",
                sla_uptime_pct=99.9,
                pricing_model="Message pack",
                limits={"max_message_size_kb": 10240},
                architectural_fit="Adapter-heavy orchestration",
                anti_patterns="Avoid high-rate event streams",
                interoperability_notes="Integrates with OCI Streaming",
                oracle_docs_urls="https://docs.oracle.com/example",
            )
        )
        await session.commit()

    list_response = await api_client.get("/api/v1/services/")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["total"] == 1
    assert list_payload["services"][0]["service_id"] == "OIC3"
    assert list_payload["services"][0]["limits"]["max_message_size_kb"] == 10240

    detail_response = await api_client.get("/api/v1/services/OIC3")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["name"] == "Oracle Integration 3 (OIC Gen3)"
    assert detail_payload["category"] == "ORCHESTRATION"
    assert detail_payload["pricing_model"] == "Message pack"
