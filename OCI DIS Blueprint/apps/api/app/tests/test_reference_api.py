"""API coverage for enriched reference-data payloads."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import AssumptionSet, DictionaryOption, PatternDefinition


@pytest.mark.asyncio
async def test_patterns_api_returns_enriched_metadata(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add(
            PatternDefinition(
                pattern_id="#01",
                name="Request-Reply",
                category="SÍNCRONO",
                description="Immediate response pattern",
                oci_components="OIC Gen3 — orchestration\nOCI API Gateway — edge",
                when_to_use="Use for low-latency APIs",
                when_not_to_use="Avoid for long-running jobs",
                technical_flow="Gateway -> OIC -> ORDS",
                business_value="Fast partner SLA support",
                is_system=True,
            )
        )
        await session.commit()

    response = await api_client.get("/api/v1/patterns/%2301")
    assert response.status_code == 200
    payload = response.json()
    assert payload["components"] == ["OIC Gen3", "OCI API Gateway"]
    assert payload["component_details"].startswith("OIC Gen3")
    assert payload["when_to_use"] == "Use for low-latency APIs"
    assert payload["when_not_to_use"] == "Avoid for long-running jobs"
    assert payload["business_value"] == "Fast partner SLA support"
    assert payload["support"]["level"] == "full"
    assert payload["support"]["parity_ready"] is True
    assert payload["support"]["dimensions"]["volumetry"] is True


@pytest.mark.asyncio
async def test_dictionary_api_returns_volumetric_metadata(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add_all(
            [
                DictionaryOption(
                    category="TOOLS",
                    code="T01",
                    value="OIC Gen3",
                    description="Type: Core. Volumetry: direct.",
                    is_volumetric=True,
                    sort_order=1,
                    version="1.0.0",
                ),
                DictionaryOption(
                    category="FREQUENCY",
                    code="FQ15",
                    value="Tiempo Real",
                    description="Proxy batch equivalent",
                    executions_per_day=24.0,
                    sort_order=1,
                    version="1.0.0",
                ),
            ]
        )
        await session.commit()

    tools_response = await api_client.get("/api/v1/dictionaries/TOOLS")
    assert tools_response.status_code == 200
    tools_payload = tools_response.json()
    assert tools_payload["options"][0]["code"] == "T01"
    assert tools_payload["options"][0]["is_volumetric"] is True
    assert tools_payload["options"][0]["version"] == "1.0.0"

    frequency_response = await api_client.get("/api/v1/dictionaries/FREQUENCY")
    assert frequency_response.status_code == 200
    frequency_payload = frequency_response.json()
    assert frequency_payload["options"][0]["code"] == "FQ15"
    assert frequency_payload["options"][0]["executions_per_day"] == 24.0


@pytest.mark.asyncio
async def test_canvas_governance_api_returns_combinations(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add_all(
            [
                DictionaryOption(
                    category="TOOLS",
                    code="T01",
                    value="OIC Gen3",
                    description="Core orchestration",
                    is_volumetric=True,
                    sort_order=1,
                    version="1.0.0",
                ),
                DictionaryOption(
                    category="OVERLAYS",
                    code="AO01",
                    value="OCI API Gateway",
                    description="Protected API edge",
                    is_volumetric=True,
                    sort_order=1,
                    version="1.0.0",
                ),
            ]
        )
        await session.commit()

    response = await api_client.get("/api/v1/dictionaries/canvas-governance")
    assert response.status_code == 200
    payload = response.json()
    assert payload["tools"][0]["value"] == "OIC Gen3"
    assert payload["overlays"][0]["value"] == "OCI API Gateway"

    combination = next(
        item for item in payload["combinations"] if item["code"] == "G04"
    )
    assert combination["supported_tool_keys"] == [
        "OIC Gen3",
        "OCI Queue",
        "OCI Functions",
    ]
    assert combination["compatible_pattern_ids"] == ["#02", "#08", "#17"]


@pytest.mark.asyncio
async def test_reference_only_patterns_are_explicit_in_pattern_api(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add(
            PatternDefinition(
                pattern_id="#17",
                name="Webhook Fanout",
                category="ASÍNCRONO / API",
                description="Distribute one webhook to multiple subscribers",
                is_system=True,
            )
        )
        await session.commit()

    response = await api_client.get("/api/v1/patterns/%2317")
    assert response.status_code == 200
    payload = response.json()
    assert payload["support"]["level"] == "reference"
    assert payload["support"]["parity_ready"] is False
    assert payload["support"]["badge_label"] == "Reference only"


@pytest.mark.asyncio
async def test_live_oic_estimate_uses_default_governed_assumptions(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add(
            AssumptionSet(
                version="1.0.0",
                label="Test governed assumptions",
                is_default=True,
                assumptions={
                    "oic_billing_threshold_kb": 25,
                    "oic_pack_size_msgs_per_hour": 1,
                    "month_days": 31,
                },
                notes="Test fixture",
            )
        )
        await session.commit()

    response = await api_client.post(
        "/api/v1/catalog/project-1/estimate",
        json={
            "frequency": "Cada 1 hora",
            "payload_per_execution_kb": 26,
            "response_kb": 0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["billing_msgs_per_execution"] == 2.0
    assert payload["billing_msgs_per_month"] == 1488.0
    assert payload["peak_packs_per_hour"] == 2.0
    assert payload["executions_per_day"] == 24.0
