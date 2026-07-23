"""API coverage for sequential, explainable integration technical demand."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import (
    CatalogIntegration,
    Project,
    ServiceCapabilityProfile,
    ServiceProductSkuMapping,
)
from app.services.technical_demand_service import select_node_mappings


def _linear_canvas() -> str:
    """Build one governed OIC-to-Queue-to-Functions route."""

    return json.dumps(
        {
            "v": 3,
            "nodes": [
                {
                    "instanceId": "oic-node",
                    "toolKey": "OIC Gen3",
                    "label": "OIC",
                    "payloadNote": "",
                    "x": 240,
                    "y": 120,
                },
                {
                    "instanceId": "queue-node",
                    "toolKey": "OCI Queue",
                    "label": "Queue",
                    "payloadNote": "",
                    "x": 520,
                    "y": 120,
                },
                {
                    "instanceId": "functions-node",
                    "toolKey": "OCI Functions",
                    "label": "Functions",
                    "payloadNote": "",
                    "x": 800,
                    "y": 120,
                },
            ],
            "edges": [
                {
                    "edgeId": "edge-1",
                    "sourceInstanceId": "source-system",
                    "targetInstanceId": "oic-node",
                },
                {
                    "edgeId": "edge-2",
                    "sourceInstanceId": "oic-node",
                    "targetInstanceId": "queue-node",
                },
                {
                    "edgeId": "edge-3",
                    "sourceInstanceId": "queue-node",
                    "targetInstanceId": "functions-node",
                },
                {
                    "edgeId": "edge-4",
                    "sourceInstanceId": "functions-node",
                    "targetInstanceId": "destination-system",
                },
            ],
            "coreToolKeys": ["OIC Gen3", "OCI Queue", "OCI Functions"],
            "overlayKeys": [],
        },
        separators=(",", ":"),
    )


def _mapping(
    *,
    service_id: str,
    tool_key: str,
    part_number: str,
    metric_key: str,
    quantity_unit: str,
    metering_policy: dict[str, object],
) -> ServiceProductSkuMapping:
    """Build one approved required mapping for the technical-demand projection."""

    return ServiceProductSkuMapping(
        service_id=service_id,
        tool_key=tool_key,
        part_number=part_number,
        billing_metric_key=metric_key,
        formula_key="metered_quantity",
        quantity_unit=quantity_unit,
        metering_policy=metering_policy,
        selection_policy="required",
        status="approved",
        version="test-1",
        source_url=f"https://docs.oracle.com/{service_id.lower()}",
    )


async def _seed_route(
    test_engine: AsyncEngine,
    *,
    payload_per_execution_kb: float = 128.0,
) -> tuple[str, str]:
    """Seed the minimum governed evidence required by the route endpoint."""

    session_factory = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with session_factory() as session:
        project = Project(
            name="Technical Demand Project",
            customer_name="ACME Inc.",
            owner_id="integration-test",
        )
        session.add(project)
        await session.flush()

        integration = CatalogIntegration(
            project_id=project.id,
            seq_number=1,
            tbq="Y",
            interface_id="INT-DEMAND-001",
            interface_name="OIC Queue Functions route",
            brand="Retail",
            business_process="Order orchestration",
            frequency="Cada 1 hora",
            executions_per_day=24.0,
            payload_per_execution_kb=payload_per_execution_kb,
            source_system="Order Hub",
            destination_system="Fulfillment Hub",
            core_tools="OIC Gen3, OCI Queue, OCI Functions",
            additional_tools_overlays=_linear_canvas(),
        )
        session.add(integration)

        profiles = [
            ServiceCapabilityProfile(
                service_id="OIC3",
                name="Oracle Integration 3",
                category="Integration",
                oracle_docs_urls="https://docs.oracle.com/oic",
            ),
            ServiceCapabilityProfile(
                service_id="QUEUE",
                name="OCI Queue",
                category="Messaging",
                oracle_docs_urls="https://docs.oracle.com/queue",
            ),
            ServiceCapabilityProfile(
                service_id="FUNCTIONS",
                name="OCI Functions",
                category="Compute",
                oracle_docs_urls="https://docs.oracle.com/functions",
            ),
        ]
        session.add_all(profiles)
        await session.flush()

        mappings = [
            _mapping(
                service_id="OIC3",
                tool_key="OIC Gen3",
                part_number="B89639",
                metric_key="oic_peak_packs_hour",
                quantity_unit="message packs",
                metering_policy={
                    "message_block_kb": 50,
                    "pack_messages_per_hour": 5000,
                },
            ),
            _mapping(
                service_id="QUEUE",
                tool_key="OCI Queue",
                part_number="B91025",
                metric_key="queue_request_millions",
                quantity_unit="million requests",
                metering_policy={
                    "request_block_kb": 64,
                    "max_message_kb": 256,
                },
            ),
            _mapping(
                service_id="FUNCTIONS",
                tool_key="OCI Functions",
                part_number="B90618",
                metric_key="functions_invocation_millions",
                quantity_unit="million invocations",
                metering_policy={"max_request_body_kb": 6144},
            ),
        ]
        for profile, mapping in zip(profiles, mappings, strict=True):
            mapping.service_profile_id = profile.id
        session.add_all(mappings)
        await session.commit()
        return project.id, integration.id


@pytest.mark.asyncio
async def test_technical_demand_propagates_payload_and_service_operations(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Project one payload sequentially into each service's commercial metric."""

    project_id, integration_id = await _seed_route(test_engine)

    response = await api_client.get(
        f"/api/v1/catalog/{project_id}/{integration_id}/technical-demand"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == project_id
    assert payload["integration_id"] == integration_id
    assert payload["blockers"] == []

    nodes = payload["nodes"]
    assert [node["service_id"] for node in nodes] == ["OIC3", "QUEUE", "FUNCTIONS"]
    for node in nodes:
        assert node["status"] == "resolved"
        assert node["input_payload_kb"] == pytest.approx(128.0)
        assert node["output_payload_kb"] == pytest.approx(128.0)
        assert node["input_messages_per_execution"] == pytest.approx(1.0)
        assert node["output_messages_per_execution"] == pytest.approx(1.0)
        assert node["blockers"] == []
        assert node["source_urls"]

    oic_metric = nodes[0]["metrics"][0]
    assert oic_metric["metric_key"] == "oic_peak_packs_hour"
    assert oic_metric["quantity"] == pytest.approx(1.0)
    assert oic_metric["messages_per_month"] == pytest.approx(744.0)
    assert oic_metric["billing_units_per_month"] == pytest.approx(2232.0)

    queue_metric = nodes[1]["metrics"][0]
    assert queue_metric["metric_key"] == "queue_request_millions"
    assert queue_metric["messages_per_month"] == pytest.approx(744.0)
    assert queue_metric["operations_per_month"] == {
        "delete": pytest.approx(744.0),
        "get": pytest.approx(744.0),
        "push": pytest.approx(744.0),
        "update": pytest.approx(0.0),
    }
    assert queue_metric["billing_units_per_month"] == pytest.approx(3720.0)
    assert queue_metric["quantity"] == pytest.approx(0.00372)

    functions_metric = nodes[2]["metrics"][0]
    assert functions_metric["metric_key"] == "functions_invocation_millions"
    assert functions_metric["messages_per_month"] == pytest.approx(744.0)
    assert functions_metric["quantity"] == pytest.approx(0.000744)


@pytest.mark.asyncio
async def test_technical_demand_attributes_oversize_blocker_to_queue_then_propagates_it(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Keep a node's own service limit distinct from inherited route blockers."""

    project_id, integration_id = await _seed_route(
        test_engine,
        payload_per_execution_kb=257.0,
    )

    response = await api_client.get(
        f"/api/v1/catalog/{project_id}/{integration_id}/technical-demand"
    )

    assert response.status_code == 200
    nodes = response.json()["nodes"]
    queue_metric = nodes[1]["metrics"][0]
    functions_metric = nodes[2]["metrics"][0]

    assert nodes[1]["status"] == "blocked"
    assert "exceeds the governed 256 KB limit" in queue_metric["blockers"][0]
    assert queue_metric["rule"] == (
        "push/get payload operations round to 64 KB blocks; "
        "delete/update count as requests"
    )
    assert queue_metric["quantity"] is None

    assert nodes[2]["status"] == "blocked"
    assert functions_metric["blockers"] == queue_metric["blockers"]
    assert functions_metric["rule"] == (
        "Upstream route blockers must be resolved before demand can be priced."
    )
    assert functions_metric["quantity"] is None


def test_canvas_mapping_selection_matches_bom_explicit_variant_precedence() -> None:
    """An explicit scenario SKU replaces the required variant for the same metric."""

    required = _mapping(
        service_id="OIC3",
        tool_key="OIC Gen3",
        part_number="B89639",
        metric_key="oic_peak_packs_hour",
        quantity_unit="message packs",
        metering_policy={},
    )
    required.id = "required-mapping"
    selected = _mapping(
        service_id="OIC3",
        tool_key="OIC Gen3",
        part_number="B89640",
        metric_key="oic_peak_packs_hour",
        quantity_unit="message packs",
        metering_policy={},
    )
    selected.id = "selected-mapping"
    selected.selection_policy = "optional"
    secondary = _mapping(
        service_id="OIC3",
        tool_key="OIC Gen3",
        part_number="B90000",
        metric_key="oic_secondary_metric",
        quantity_unit="units",
        metering_policy={},
    )
    secondary.id = "secondary-mapping"

    result = select_node_mappings(
        [required, selected, secondary],
        service_id="OIC3",
        service_config={},
        selected_mapping_ids={selected.id},
    )

    assert [mapping.part_number for mapping in result] == ["B89640", "B90000"]
