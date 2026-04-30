"""Regression coverage for design warnings persisted in recalculation snapshots."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import AssumptionSet, DictionaryOption
from app.services import recalc_service


@pytest.mark.asyncio
async def test_recalculation_includes_low_latency_data_integration_warning(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Recalculation should carry forward governed design warnings beyond payload-size checks."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add(
            AssumptionSet(
                version="1.0.0",
                label="Recalc design warnings",
                is_default=True,
                assumptions={
                    "oic_rest_max_payload_kb": 10240,
                    "functions_max_invoke_body_kb": 6144,
                    "api_gw_max_body_kb": 20480,
                    "queue_max_message_kb": 256,
                    "streaming_max_message_kb": 1024,
                },
                notes="Test fixture",
            )
        )
        session.add(
            DictionaryOption(
                category="TOOLS",
                code="T02",
                value="OCI Data Integration",
                description="Batch ETL",
                is_volumetric=True,
                sort_order=1,
                version="1.0.0",
            )
        )
        await session.commit()

    create_project_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "Recalc Warning Project",
            "owner_id": "integration-test",
            "description": "Recalc warning validation",
        },
    )
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    create_integration_response = await api_client.post(
        f"/api/v1/catalog/{project_id}",
        params={"actor_id": "integration-test"},
        json={
            "interface_id": "INT-DI-001",
            "brand": "Oracle",
            "business_process": "Analytics",
            "interface_name": "Low Latency DI",
            "description": "Recalc should flag low-latency DI use",
            "source_system": "JDE",
            "destination_system": "ADW",
            "source_technology": "REST",
            "destination_technology": "REST",
            "type": "Event",
            "frequency": "Tiempo Real",
            "payload_per_execution_kb": 64,
            "core_tools": ["OCI Data Integration"],
            "tbq": "Y",
        },
    )
    assert create_integration_response.status_code == 201
    integration_id = create_integration_response.json()["id"]

    async with session_factory() as session:
        async with session.begin():
            snapshot = await recalc_service.recalculate_project(
                project_id=project_id,
                actor_id="integration-test",
                db=session,
            )

    row_metrics = snapshot.row_results[integration_id]
    warnings = row_metrics["design_constraint_warnings"]
    assert isinstance(warnings, list)
    assert any(
        "Data Integration is on a low-latency path" in warning
        for warning in warnings
    )
