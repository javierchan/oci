"""Integration coverage for project CRUD and audit flows."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_project_patch_emits_audit_event(api_client: AsyncClient) -> None:
    """Verify project metadata patching persists changes and emits an audit event."""

    create_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "Integration Test Project",
            "owner_id": "integration-test",
            "description": "Initial description",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    project_id = created["id"]

    patch_response = await api_client.patch(
        f"/api/v1/projects/{project_id}",
        params={"actor_id": "integration-test"},
        json={
            "name": "Integration Test Project Updated",
            "description": "Updated description",
        },
    )
    assert patch_response.status_code == 200
    patched = patch_response.json()
    assert patched["name"] == "Integration Test Project Updated"
    assert patched["description"] == "Updated description"
    assert patched["owner_id"] == "integration-test"

    get_response = await api_client.get(f"/api/v1/projects/{project_id}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["name"] == "Integration Test Project Updated"

    audit_response = await api_client.get(f"/api/v1/audit/{project_id}")
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    assert audit_payload["total"] == 1
    assert len(audit_payload["events"]) == 1

    audit_event = audit_payload["events"][0]
    assert audit_event["event_type"] == "project_updated"
    assert audit_event["entity_type"] == "project"
    assert audit_event["entity_id"] == project_id
    assert audit_event["old_value"]["name"] == "Integration Test Project"
    assert audit_event["new_value"]["name"] == "Integration Test Project Updated"
