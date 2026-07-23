"""Integration coverage for manual catalog capture and lineage retrieval."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import AssumptionSet, CatalogIntegration, DictionaryOption


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
                    "oic_kafka_max_payload_kb": 10240,
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
                DictionaryOption(
                    category="TOOLS",
                    code=None,
                    value="Oracle ORDS",
                    description=None,
                    is_volumetric=True,
                    sort_order=99,
                    version="1.0.0",
                ),
            ]
        )
        await session.commit()


@pytest.mark.asyncio
async def test_refresh_project_qa_removes_stale_derived_reasons(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """QA refresh recomputes decisions without rewriting integration evidence."""

    project_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "QA Refresh Project",
            "customer_name": "Catalog Test Customer",
            "owner_id": "integration-test",
        },
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        row = CatalogIntegration(
            project_id=project_id,
            seq_number=1,
            interface_id="QA-REFRESH-001",
            interface_name="Refresh stale QA state",
            trigger_type="REST",
            selected_pattern="#01",
            pattern_rationale="Certified synchronous request and reply route.",
            core_tools="OIC Gen3",
            payload_per_execution_kb=10.0,
            target_latency_sla="2 seconds",
            qa_status="REVISAR",
            qa_reasons=["PATTERN_REFERENCE_ONLY"],
        )
        session.add(row)
        await session.commit()

    refresh_response = await api_client.post(
        f"/api/v1/catalog/{project_id}/refresh-qa",
        params={"actor_id": "integration-test"},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json() == {
        "project_id": project_id,
        "evaluated": 1,
        "changed": 1,
        "qa_ok": 1,
        "qa_revisar": 0,
        "qa_pending": 0,
    }

    list_response = await api_client.get(f"/api/v1/catalog/{project_id}")
    assert list_response.status_code == 200
    assert list_response.json()["integrations"][0]["qa_status"] == "OK"
    assert list_response.json()["integrations"][0]["qa_reasons"] == []


@pytest.mark.asyncio
async def test_manual_capture_lists_catalog_and_lineage(api_client: AsyncClient) -> None:
    """Verify manual capture persists a catalog row and exposes lineage metadata."""

    create_project_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "Catalog Test Project",
            "customer_name": "Catalog Test Customer",
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
            "status": "In analysis",
            "interface_status": "Definitive",
            "mapping_status": "To be confirmed",
            "source_system": "SAP ECC",
            "destination_system": "Oracle ATP",
            "base": "Delta",
            "frequency": "Una vez al día",
            "payload_per_execution_kb": 128,
            "is_fan_out": True,
            "fan_out_targets": 3,
            "tbq": "Y",
            "calendarization": "Daily at 19:30",
            "source_evidence": {"legacy_destination_api_reference": "/gl/sync"},
        },
    )
    assert create_integration_response.status_code == 201
    integration = create_integration_response.json()
    integration_id = integration["id"]
    assert integration["interface_id"] == "INT-TEST-001"
    assert integration["source_system"] == "SAP ECC"
    assert integration["base"] == "Delta"
    assert integration["status"] == "In analysis"
    assert integration["interface_status"] == "Definitive"
    assert integration["mapping_status"] == "To be confirmed"
    assert integration["calendarization"] == "Daily at 19:30"
    assert integration["is_fan_out"] is True
    assert integration["fan_out_targets"] == 3

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
    assert lineage["raw_data"]["source_evidence"]["legacy_destination_api_reference"] == "/gl/sync"
    assert lineage["raw_data"]["is_fan_out"] is True
    assert lineage["raw_data"]["fan_out_targets"] == 3


@pytest.mark.asyncio
async def test_patch_tbq_updates_commercial_scope_and_keeps_technical_catalog(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Architects can remove a row from the BOM without deleting its technical evidence."""

    await seed_canvas_validation_reference_data(test_engine)

    project_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "TBQ Patch Project",
            "customer_name": "Catalog Test Customer",
            "owner_id": "integration-test",
            "description": "TBQ patch",
        },
    )
    project_id = project_response.json()["id"]
    create_response = await api_client.post(
        f"/api/v1/catalog/{project_id}",
        params={"actor_id": "integration-test"},
        json={
            "interface_id": "INT-TBQ-PATCH-001",
            "brand": "Oracle",
            "business_process": "Finance",
            "interface_name": "Commercial scope patch",
            "source_system": "ERP",
            "destination_system": "ATP",
            "frequency": "Cada 1 hora",
            "tbq": "Y",
        },
    )
    integration_id = create_response.json()["id"]

    patch_response = await api_client.patch(
        f"/api/v1/catalog/{project_id}/{integration_id}",
        params={"actor_id": "integration-test"},
        json={"tbq": "N"},
    )

    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["tbq"] == "N"
    assert patch_response.json()["commercially_eligible"] is False
    catalog_response = await api_client.get(f"/api/v1/catalog/{project_id}")
    assert catalog_response.json()["total"] == 1

    lineage_response = await api_client.get(f"/api/v1/catalog/{project_id}/{integration_id}/lineage")
    raw_values = lineage_response.json()["raw_data"]
    raw_values["tbq"] = "Y"
    source_patch_response = await api_client.patch(
        f"/api/v1/catalog/{project_id}/{integration_id}",
        params={"actor_id": "integration-test"},
        json={"raw_column_values": raw_values},
    )
    assert source_patch_response.status_code == 200
    assert source_patch_response.json()["tbq"] == "Y"
    assert source_patch_response.json()["commercially_eligible"] is True


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
            "customer_name": "Catalog Test Customer",
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
            "source_technology": "Kafka",
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
            "customer_name": "Catalog Test Customer",
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
async def test_patch_rejects_uncoded_dictionary_tools(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Uncoded admin/system endpoint records must not satisfy core-tool validation."""

    await seed_canvas_validation_reference_data(test_engine)

    create_project_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "Uncoded Tool Project",
            "customer_name": "Catalog Test Customer",
            "owner_id": "integration-test",
            "description": "Canvas taxonomy validation",
        },
    )
    project_id = create_project_response.json()["id"]

    create_integration_response = await api_client.post(
        f"/api/v1/catalog/{project_id}",
        params={"actor_id": "integration-test"},
        json={
            "interface_id": "INT-UNCODED-001",
            "brand": "Oracle",
            "business_process": "Finance",
            "interface_name": "Uncoded Tool Route",
            "description": "Uncoded tools should not be accepted as core tools",
            "source_system": "SAP ECC",
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
            "core_tools": "Oracle ORDS",
            "additional_tools_overlays": build_linear_canvas("Oracle ORDS"),
        },
    )

    assert patch_response.status_code == 400
    payload = patch_response.json()
    assert payload["detail"]["error_code"] == "INVALID_CORE_TOOLS"


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
            "customer_name": "Catalog Test Customer",
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
                "source_technology": "Kafka",
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


@pytest.mark.asyncio
async def test_bulk_patch_rejects_row_specific_raw_source_evidence(
    api_client: AsyncClient,
) -> None:
    """Bulk changes must not overwrite per-row source lineage evidence."""

    create_project_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "Raw Evidence Bulk Patch Project",
            "customer_name": "Catalog Test Customer",
            "owner_id": "integration-test",
            "description": "Raw evidence remains row-specific",
        },
    )
    project_id = create_project_response.json()["id"]

    bulk_response = await api_client.post(
        f"/api/v1/catalog/{project_id}/bulk-patch",
        json={
            "integration_ids": [],
            "actor_id": "integration-test",
            "patch": {"raw_column_values": {"TBQ": "N"}},
        },
    )

    assert bulk_response.status_code == 400
    assert bulk_response.json()["detail"]["error_code"] == "RAW_COLUMN_VALUES_BULK_UNSUPPORTED"
