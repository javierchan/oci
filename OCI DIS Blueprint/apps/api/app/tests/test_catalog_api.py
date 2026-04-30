"""Integration coverage for manual catalog capture and lineage retrieval."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import AssumptionSet, DictionaryOption


def build_linear_canvas(tool_key: str) -> str:
    """Create a minimal valid canvas route for one core tool."""

    return json.dumps(
        {
            "v": 3,
            "nodes": [
                {
                    "instanceId": "tool-1",
                    "toolKey": tool_key,
                    "label": tool_key,
                    "payloadNote": "",
                    "x": 240,
                    "y": 80,
                }
            ],
            "edges": [
                {
                    "edgeId": "edge-1",
                    "sourceInstanceId": "source-system",
                    "targetInstanceId": "tool-1",
                    "label": "",
                },
                {
                    "edgeId": "edge-2",
                    "sourceInstanceId": "tool-1",
                    "targetInstanceId": "destination-system",
                    "label": "",
                },
            ],
            "coreToolKeys": [tool_key],
            "overlayKeys": [],
        },
        ensure_ascii=False,
    )


def build_disconnected_canvas(tool_key: str) -> str:
    """Create a malformed canvas with no source-to-destination route."""

    return json.dumps(
        {
            "v": 3,
            "nodes": [
                {
                    "instanceId": "tool-1",
                    "toolKey": tool_key,
                    "label": tool_key,
                    "payloadNote": "",
                    "x": 240,
                    "y": 80,
                }
            ],
            "edges": [],
            "coreToolKeys": [tool_key],
            "overlayKeys": [],
        },
        ensure_ascii=False,
    )


async def seed_canvas_validation_reference_data(test_engine: AsyncEngine) -> None:
    """Seed the minimum governed reference data required for canvas validation."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        session.add(
            AssumptionSet(
                version="1.0.0",
                label="Canvas validation assumptions",
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
                    category="TOOLS",
                    code="T02",
                    value="OCI Data Integration",
                    description="Batch data movement",
                    is_volumetric=True,
                    sort_order=2,
                    version="1.0.0",
                ),
                DictionaryOption(
                    category="OVERLAYS",
                    code="AO01",
                    value="OCI API Gateway",
                    description="Protected REST edge",
                    is_volumetric=True,
                    sort_order=1,
                    version="1.0.0",
                ),
            ]
        )
        await session.commit()


@pytest.mark.asyncio
async def test_manual_capture_lists_catalog_and_lineage(api_client: AsyncClient) -> None:
    """Verify manual capture persists a catalog row and exposes lineage metadata."""

    create_project_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "Catalog Test Project",
            "owner_id": "integration-test",
            "description": "Catalog integration test",
        },
    )
    assert create_project_response.status_code == 201
    project_id = create_project_response.json()["id"]

    create_integration_response = await api_client.post(
        f"/api/v1/catalog/{project_id}",
        params={"actor_id": "integration-test"},
        json={
            "interface_id": "INT-TEST-001",
            "brand": "Oracle",
            "business_process": "Finance",
            "interface_name": "GL Sync",
            "description": "Manual capture test integration",
            "source_system": "SAP ECC",
            "destination_system": "Oracle ATP",
            "frequency": "Una vez al día",
            "payload_per_execution_kb": 128,
            "tbq": "Y",
        },
    )
    assert create_integration_response.status_code == 201
    integration = create_integration_response.json()
    integration_id = integration["id"]
    assert integration["interface_id"] == "INT-TEST-001"
    assert integration["source_system"] == "SAP ECC"

    list_response = await api_client.get(f"/api/v1/catalog/{project_id}")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] == 1
    assert len(listed["integrations"]) == 1
    assert listed["integrations"][0]["id"] == integration_id

    lineage_response = await api_client.get(f"/api/v1/catalog/{project_id}/{integration_id}/lineage")
    assert lineage_response.status_code == 200
    lineage = lineage_response.json()
    assert lineage["included"] is True
    assert lineage["import_filename"] == "manual-capture.json"
    assert lineage["raw_data"]["interface_id"] == "INT-TEST-001"


@pytest.mark.asyncio
async def test_patch_rejects_oracle_backed_canvas_blockers(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Reject design saves that the UI already blocks on Oracle-backed limits."""

    await seed_canvas_validation_reference_data(test_engine)

    create_project_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "Canvas Blocker Project",
            "owner_id": "integration-test",
            "description": "Canvas blocker validation",
        },
    )
    project_id = create_project_response.json()["id"]

    create_integration_response = await api_client.post(
        f"/api/v1/catalog/{project_id}",
        params={"actor_id": "integration-test"},
        json={
            "interface_id": "INT-BLOCK-001",
            "brand": "Oracle",
            "business_process": "Finance",
            "interface_name": "Oversized OIC Route",
            "description": "Route should fail server-side blocker validation",
            "source_system": "SAP ECC",
            "destination_system": "Oracle ATP",
            "frequency": "Cada 1 hora",
            "payload_per_execution_kb": 15000,
            "tbq": "Y",
        },
    )
    assert create_integration_response.status_code == 201
    integration_id = create_integration_response.json()["id"]

    patch_response = await api_client.patch(
        f"/api/v1/catalog/{project_id}/{integration_id}",
        params={"actor_id": "integration-test"},
        json={
            "core_tools": "OIC Gen3",
            "additional_tools_overlays": build_linear_canvas("OIC Gen3"),
        },
    )

    assert patch_response.status_code == 400
    payload = patch_response.json()
    assert payload["detail"]["error_code"] == "INVALID_CANVAS_DESIGN"
    assert "Oracle-backed canvas blockers detected" in payload["detail"]["detail"]
    assert payload["detail"]["findings"][0]["severity"] == "blocker"


@pytest.mark.asyncio
async def test_patch_rejects_disconnected_canvas_route(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Reject canvas payloads that do not actually connect source to destination."""

    await seed_canvas_validation_reference_data(test_engine)

    create_project_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "Disconnected Canvas Project",
            "owner_id": "integration-test",
            "description": "Canvas route validation",
        },
    )
    project_id = create_project_response.json()["id"]

    create_integration_response = await api_client.post(
        f"/api/v1/catalog/{project_id}",
        params={"actor_id": "integration-test"},
        json={
            "interface_id": "INT-DISCONNECTED-001",
            "brand": "Oracle",
            "business_process": "Supply Chain",
            "interface_name": "Disconnected Canvas",
            "description": "Canvas must enforce a route",
            "source_system": "JDE",
            "destination_system": "Oracle ATP",
            "frequency": "Cada 1 hora",
            "payload_per_execution_kb": 64,
            "tbq": "Y",
        },
    )
    assert create_integration_response.status_code == 201
    integration_id = create_integration_response.json()["id"]

    patch_response = await api_client.patch(
        f"/api/v1/catalog/{project_id}/{integration_id}",
        params={"actor_id": "integration-test"},
        json={
            "core_tools": "OIC Gen3",
            "additional_tools_overlays": build_disconnected_canvas("OIC Gen3"),
        },
    )

    assert patch_response.status_code == 400
    payload = patch_response.json()
    assert payload["detail"]["error_code"] == "CANVAS_ROUTE_INCOMPLETE"


@pytest.mark.asyncio
async def test_bulk_patch_does_not_bypass_canvas_validation(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Bulk patch should report row-level validation errors instead of persisting invalid routes."""

    await seed_canvas_validation_reference_data(test_engine)

    create_project_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "Bulk Canvas Validation Project",
            "owner_id": "integration-test",
            "description": "Bulk patch canvas validation",
        },
    )
    project_id = create_project_response.json()["id"]

    integration_ids: list[str] = []
    for sequence in range(2):
        create_integration_response = await api_client.post(
            f"/api/v1/catalog/{project_id}",
            params={"actor_id": "integration-test"},
            json={
                "interface_id": f"INT-BULK-{sequence + 1:03d}",
                "brand": "Oracle",
                "business_process": "Operations",
                "interface_name": f"Bulk Canvas {sequence + 1}",
                "description": "Bulk patch should not bypass validation",
                "source_system": "SAP ECC",
                "destination_system": "Oracle ATP",
                "frequency": "Cada 1 hora",
                "payload_per_execution_kb": 15000,
                "tbq": "Y",
            },
        )
        assert create_integration_response.status_code == 201
        integration_ids.append(create_integration_response.json()["id"])

    bulk_response = await api_client.post(
        f"/api/v1/catalog/{project_id}/bulk-patch",
        json={
            "integration_ids": integration_ids,
            "actor_id": "integration-test",
            "patch": {
                "core_tools": "OIC Gen3",
                "additional_tools_overlays": build_linear_canvas("OIC Gen3"),
            },
        },
    )

    assert bulk_response.status_code == 200
    payload = bulk_response.json()
    assert payload["updated"] == 0
    assert len(payload["errors"]) == 2
    assert all("Oracle-backed canvas blockers detected" in error for error in payload["errors"])
