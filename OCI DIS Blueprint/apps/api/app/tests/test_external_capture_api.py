"""External capture review integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import PatternDefinition


REVIEW_HEADERS = {"X-Actor-Id": "analyst-1", "X-Actor-Role": "Analyst"}
ARCHITECT_HEADERS = {"X-Actor-Id": "architect-1", "X-Actor-Role": "Architect"}

pytestmark = pytest.mark.asyncio


async def _seed_pattern(test_engine: AsyncEngine) -> None:
    session_factory = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with session_factory() as session:
        async with session.begin():
            session.add(
                PatternDefinition(
                    pattern_id="#18",
                    name="External Integration",
                    category="External",
                    is_active=True,
                )
            )


async def _create_project(api_client: AsyncClient) -> str:
    response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "ADN - Retail Merchandising",
            "owner_id": "architect-1",
            "description": "Governed customer evidence review.",
            "project_metadata": {
                "client_name": "Innovación y Conveniencia, S.A. de C.V.",
                "engagement_name": "ADN - Retail Merchandising",
                "source_kind": "external_manual_capture",
            },
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["project_metadata"]["client_name"] == (
        "Innovación y Conveniencia, S.A. de C.V."
    )
    return str(payload["id"])


async def _create_session(api_client: AsyncClient, project_id: str) -> str:
    response = await api_client.post(
        f"/api/v1/projects/{project_id}/external-capture/sessions",
        headers=REVIEW_HEADERS,
        json={
            "name": "Customer WIP line-by-line review",
            "client_name": "Innovación y Conveniencia, S.A. de C.V.",
            "source_label": "Customer WIP evidence · Catalogo_Integraciones_LAB",
            "source_hash": "a" * 64,
            "normalization_policy": {
                "force_tbq_y": True,
                "payload_source_column": "Tamaño KB",
                "pattern_review_required": True,
                "workbook_persisted": False,
            },
        },
    )
    assert response.status_code == 201
    return str(response.json()["session"]["id"])


def _complete_payload() -> dict[str, object]:
    return {
        "interface_id": "LAB-001",
        "brand": "Retail",
        "business_process": "Merchandising",
        "interface_name": "Publish item updates",
        "source_system": "Oracle Retail Merchandising",
        "destination_system": "Store Integration",
        "type": "Event Trigger",
        "frequency": "Event-driven",
        "payload_per_execution_kb": 48.5,
        "selected_pattern": "#18",
        "pattern_rationale": "External evidence requires architect confirmation.",
        "tbq": "N",
    }


async def test_external_capture_requires_review_before_promotion(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_pattern(test_engine)
    project_id = await _create_project(api_client)
    session_id = await _create_session(api_client, project_id)

    stage_response = await api_client.post(
        f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}/drafts/bulk",
        headers=REVIEW_HEADERS,
        json={
            "drafts": [
                {
                    "source_row_number": 6,
                    "source_record": {
                        "Tamaño KB": 48.5,
                        "TBQ": "",
                        "Complejidad": "Muy Alto",
                    },
                    "proposed_payload": _complete_payload(),
                    "normalized_values": {
                        "complexity": {
                            "source": "Muy Alto",
                            "proposed": "High",
                        }
                    },
                    "pattern_assessment": {
                        "source_pattern": "#02",
                        "recommended_pattern": "#18",
                        "decision": "needs_confirmation",
                    },
                    "validation_evidence": {
                        "payload_source": "Tamaño KB",
                        "source_file_persisted": False,
                    },
                    "confidence": 0.82,
                },
                {
                    "source_row_number": 7,
                    "source_record": {"Tamaño KB": 12},
                    "proposed_payload": {
                        **_complete_payload(),
                        "interface_id": "LAB-002",
                        "interface_name": "Incomplete destination evidence",
                        "destination_system": "",
                    },
                    "normalized_values": {},
                    "pattern_assessment": {
                        "source_pattern": "#18",
                        "recommended_pattern": "#18",
                        "decision": "confirmed",
                    },
                    "validation_evidence": {},
                    "confidence": 0.5,
                },
            ]
        },
    )
    assert stage_response.status_code == 200
    stage_payload = stage_response.json()
    assert stage_payload["created"] == 2
    assert stage_payload["summary"]["total"] == 2
    assert stage_payload["summary"]["schema_ready"] == 1
    assert stage_payload["summary"]["missing_required"] == 1
    assert stage_payload["summary"]["needs_review"] == 2

    drafts_response = await api_client.get(
        f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}/drafts",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert drafts_response.status_code == 200
    drafts = drafts_response.json()["drafts"]
    complete, incomplete = drafts
    assert complete["proposed_payload"]["tbq"] == "Y"
    assert complete["source_record"]["TBQ"] == ""
    assert complete["validation_evidence"]["tbq_forced_to_y"] is True
    assert complete["validation_evidence"]["source_file_persisted"] is False
    assert incomplete["required_field_gaps"] == ["destination_system"]

    blocked_review = await api_client.post(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            f"/drafts/{incomplete['id']}/review"
        ),
        headers=ARCHITECT_HEADERS,
        json={"decision": "approve", "rationale": "Approve as supplied."},
    )
    assert blocked_review.status_code == 409
    assert (
        blocked_review.json()["detail"]["error_code"]
        == "EXTERNAL_CAPTURE_DRAFT_NOT_READY"
    )

    blocked_promotion = await api_client.post(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            f"/drafts/{complete['id']}/promote"
        ),
        headers=ARCHITECT_HEADERS,
    )
    assert blocked_promotion.status_code == 409
    assert (
        blocked_promotion.json()["detail"]["error_code"]
        == "EXTERNAL_CAPTURE_APPROVAL_REQUIRED"
    )

    review_response = await api_client.post(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            f"/drafts/{complete['id']}/review"
        ),
        headers=ARCHITECT_HEADERS,
        json={
            "decision": "approve",
            "rationale": "Pattern and source evidence reviewed line by line.",
        },
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "approved"

    promotion_response = await api_client.post(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            f"/drafts/{complete['id']}/promote"
        ),
        headers=ARCHITECT_HEADERS,
    )
    assert promotion_response.status_code == 200
    promoted = promotion_response.json()
    assert promoted["draft"]["status"] == "promoted"

    catalog_response = await api_client.get(
        f"/api/v1/catalog/{project_id}?page=1&page_size=20"
    )
    assert catalog_response.status_code == 200
    catalog = catalog_response.json()
    assert catalog["total"] == 1
    integration = catalog["integrations"][0]
    assert integration["id"] == promoted["integration_id"]
    assert integration["tbq"] == "Y"
    assert integration["payload_per_execution_kb"] == 48.5
    assert integration["selected_pattern"] == "#18"
    assert integration["qa_status"] == "REVISAR"


async def test_external_capture_upsert_search_and_project_delete(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_pattern(test_engine)
    project_id = await _create_project(api_client)
    session_id = await _create_session(api_client, project_id)
    draft = {
        "source_row_number": 18,
        "source_record": {"Interfaz": "Item sync"},
        "proposed_payload": _complete_payload(),
        "normalized_values": {},
        "pattern_assessment": {
            "source_pattern": "#18",
            "recommended_pattern": "#18",
            "decision": "confirmed",
        },
        "validation_evidence": {},
        "confidence": 0.9,
    }
    endpoint = (
        f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}/drafts/bulk"
    )
    first = await api_client.post(
        endpoint,
        headers=REVIEW_HEADERS,
        json={"drafts": [draft]},
    )
    second = await api_client.post(
        endpoint,
        headers=REVIEW_HEADERS,
        json={"drafts": [draft]},
    )
    assert first.json()["created"] == 1
    assert second.json()["created"] == 0
    assert second.json()["updated"] == 1
    assert second.json()["total"] == 1

    search = await api_client.get(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}/drafts"
            "?search=Store%20Integration"
        ),
        headers={"X-Actor-Role": "Viewer"},
    )
    assert search.status_code == 200
    assert search.json()["total"] == 1

    archive = await api_client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers={"X-Actor-Id": "owner-1", "X-Actor-Role": "Admin"},
    )
    assert archive.status_code == 200
    delete_response = await api_client.delete(
        f"/api/v1/projects/{project_id}",
        headers={"X-Actor-Id": "owner-1", "X-Actor-Role": "Admin"},
    )
    assert delete_response.status_code == 200

    after_delete = await api_client.get(
        f"/api/v1/projects/{project_id}/external-capture/sessions",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert after_delete.status_code == 200
    assert after_delete.json()["sessions"] == []
