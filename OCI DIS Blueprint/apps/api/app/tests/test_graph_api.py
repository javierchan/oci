"""Contract tests for risk-aware system dependency graph responses."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import CatalogIntegration, PatternDefinition, Project


async def seed_graph_project(test_engine: AsyncEngine) -> str:
    """Seed a mixed-risk relationship with governed metric and interaction evidence."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(name="Graph contract", owner_id="graph-test")
        session.add(project)
        await session.flush()
        session.add_all(
            [
                PatternDefinition(pattern_id="#01", name="Request-Reply", category="Synchronous"),
                PatternDefinition(pattern_id="#02", name="Event-Driven", category="Asynchronous"),
            ]
        )
        session.add_all(
            [
                CatalogIntegration(
                    project_id=project.id,
                    seq_number=1,
                    interface_name="Synchronous order lookup",
                    owner="Order architecture",
                    brand="Retail North",
                    business_process="Order to Cash — Retail to Finance",
                    type="Synchronous",
                    trigger_type="REST Trigger",
                    source_system="Retail Core ERP",
                    source_technology="Oracle EBS",
                    source_owner="ERP Operations",
                    destination_system="Finance Analytics Lake",
                    destination_technology_1="Autonomous Database",
                    destination_owner="Finance Data",
                    executions_per_day=120.0,
                    payload_per_hour_kb=640.0,
                    selected_pattern="#01",
                    qa_status="OK",
                ),
                CatalogIntegration(
                    project_id=project.id,
                    seq_number=2,
                    interface_name="Asynchronous order event",
                    owner="Integration architecture",
                    brand="Retail North",
                    business_process="Order to Cash — Retail to Finance",
                    type="Asynchronous",
                    trigger_type="Event Trigger",
                    source_system="Retail Core ERP",
                    source_technology="Oracle EBS",
                    source_owner="ERP Operations",
                    destination_system="Finance Analytics Lake",
                    destination_technology_1="Autonomous Database",
                    destination_owner="Finance Data",
                    executions_per_day=240.0,
                    payload_per_hour_kb=1280.0,
                    selected_pattern="#02",
                    qa_status="REVISAR",
                ),
            ]
        )
        await session.commit()
        return project.id


@pytest.mark.asyncio
async def test_graph_exposes_risk_metrics_modes_and_actionable_integrations(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Verify a mixed edge cannot appear safe and preserves evidence for investigation."""

    project_id = await seed_graph_project(test_engine)

    response = await api_client.get(f"/api/v1/catalog/{project_id}/graph")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["integration_count"] == 2
    assert payload["meta"]["business_process_families"] == ["Order to Cash"]
    assert payload["meta"]["executions_coverage"] == 2
    assert payload["meta"]["payload_coverage"] == 2
    assert payload["meta"]["latest_updated_at"] is not None

    edge = payload["edges"][0]
    assert edge["dominant_qa_status"] == "OK"
    assert edge["risk_qa_status"] == "REVISAR"
    assert edge["risk_score"] == 12
    assert edge["interaction_mode"] == "MIXED"
    assert edge["total_executions_per_day"] == 360.0
    assert edge["total_payload_per_hour_kb"] == 1920.0
    assert edge["executions_coverage"] == 2
    assert edge["payload_coverage"] == 2
    assert edge["patterns"] == ["#01 · Request-Reply", "#02 · Event-Driven"]
    assert [item["name"] for item in edge["integrations"]] == [
        "Synchronous order lookup",
        "Asynchronous order event",
    ]
    assert [item["pattern"] for item in edge["integrations"]] == [
        "#01 · Request-Reply",
        "#02 · Event-Driven",
    ]

    source_node = next(node for node in payload["nodes"] if node["id"] == "Retail Core ERP")
    assert source_node["owners"] == ["ERP Operations"]
    assert source_node["technologies"] == ["Oracle EBS"]


@pytest.mark.asyncio
async def test_graph_filters_by_business_process_family(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Verify process-family filtering avoids requiring a detailed route label."""

    project_id = await seed_graph_project(test_engine)

    matching = await api_client.get(
        f"/api/v1/catalog/{project_id}/graph",
        params={"business_process_family": "Order to Cash"},
    )
    missing = await api_client.get(
        f"/api/v1/catalog/{project_id}/graph",
        params={"business_process_family": "Procure to Pay"},
    )

    assert matching.status_code == 200
    assert matching.json()["meta"]["integration_count"] == 2
    assert missing.status_code == 200
    assert missing.json()["meta"]["integration_count"] == 0
