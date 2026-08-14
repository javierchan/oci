"""Coverage for shared project views and evidence-backed coordination tasks."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


HEADERS = {"X-Actor-Id": "architect-1", "X-Actor-Role": "Architect"}


async def _project(client: AsyncClient) -> str:
    response = await client.post("/api/v1/projects/", json={"name": "Coordination Project", "customer_name": "Example Customer", "owner_id": "architect-1"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_shared_view_is_persisted_and_audited(api_client: AsyncClient) -> None:
    project_id = await _project(api_client)
    created = await api_client.post(
        f"/api/v1/projects/{project_id}/saved-views", headers=HEADERS,
        json={"surface": "catalog", "label": "QA review", "filters": {"qa_status": "REVISAR"}, "is_shared": True},
    )
    assert created.status_code == 201, created.text
    view = created.json()
    listed = await api_client.get(f"/api/v1/projects/{project_id}/saved-views?surface=catalog", headers=HEADERS)
    assert listed.status_code == 200
    assert listed.json()["views"][0]["id"] == view["id"]
    audit = await api_client.get(f"/api/v1/audit/{project_id}")
    assert audit.json()["events"][0]["event_type"] == "project_view_created"
    deleted = await api_client.delete(f"/api/v1/projects/{project_id}/saved-views/{view['id']}", headers=HEADERS)
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_attention_task_requires_evidence_before_resolution(api_client: AsyncClient) -> None:
    project_id = await _project(api_client)
    created = await api_client.post(
        f"/api/v1/projects/{project_id}/attention-tasks", headers=HEADERS,
        json={"attention_key": "qa:pending", "source": "qa", "title": "Resolve QA gaps", "evidence_href": f"/projects/{project_id}/catalog", "assignee": "architect-2", "due_date": "2026-08-20"},
    )
    assert created.status_code == 201, created.text
    task = created.json()
    missing_evidence = await api_client.patch(f"/api/v1/projects/{project_id}/attention-tasks/{task['id']}", headers=HEADERS, json={"status": "resolved"})
    assert missing_evidence.status_code == 422
    resolved = await api_client.patch(
        f"/api/v1/projects/{project_id}/attention-tasks/{task['id']}", headers=HEADERS,
        json={"status": "resolved", "evidence": {"summary": "QA evidence reviewed in catalog"}},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    listed = await api_client.get(f"/api/v1/projects/{project_id}/attention-tasks", headers=HEADERS)
    assert listed.status_code == 200
    assert listed.json()["tasks"][0]["evidence"]["summary"] == "QA evidence reviewed in catalog"
