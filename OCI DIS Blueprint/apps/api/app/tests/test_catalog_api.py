"""Integration coverage for manual catalog capture and lineage retrieval."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


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
