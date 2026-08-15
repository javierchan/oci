"""External capture review integration tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import (
    AgentRun,
    AgentRunStatus,
    ExternalCaptureDraft,
    PatternDefinition,
)
from app.services.external_capture_service import (
    build_agent_evidence,
    record_agent_analysis,
)


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
            "name": "Synthetic Merchandising Review",
            "customer_name": "Synthetic Retail Group",
            "owner_id": "architect-1",
            "description": "Governed customer evidence review.",
            "project_metadata": {
                "client_name": "Synthetic Retail Group",
                "engagement_name": "Synthetic Merchandising Review",
                "source_kind": "external_manual_capture",
            },
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["project_metadata"]["client_name"] == "Synthetic Retail Group"
    return str(payload["id"])


async def _create_session(api_client: AsyncClient, project_id: str) -> str:
    response = await api_client.post(
        f"/api/v1/projects/{project_id}/external-capture/sessions",
        headers=REVIEW_HEADERS,
        json={
            "name": "Customer WIP line-by-line review",
            "client_name": "Synthetic Retail Group",
            "source_label": "Synthetic customer WIP evidence",
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


async def _create_unforced_session(
    api_client: AsyncClient,
    project_id: str,
) -> str:
    response = await api_client.post(
        f"/api/v1/projects/{project_id}/external-capture/sessions",
        headers=REVIEW_HEADERS,
        json={
            "name": "Customer evidence without TBQ override",
            "client_name": "Synthetic Customer",
            "source_label": "Synthetic customer evidence",
            "source_hash": "b" * 64,
            "normalization_policy": {
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


async def test_external_capture_reports_only_actual_tbq_policy_overrides(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_pattern(test_engine)
    project_id = await _create_project(api_client)
    session_id = await _create_unforced_session(api_client, project_id)

    response = await api_client.post(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            "/drafts/bulk"
        ),
        headers=REVIEW_HEADERS,
        json={
            "drafts": [
                {
                    "source_row_number": 6,
                    "source_record": {"Interfaz": "Synthetic interface", "TBQ": "N"},
                    "proposed_payload": _complete_payload(),
                    "pattern_assessment": {
                        "source_pattern": "#18",
                        "recommended_pattern": None,
                        "decision": "human_confirmation_required",
                    },
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["summary"]["pattern_changes"] == 0
    listed = await api_client.get(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            "/drafts"
        ),
        headers=REVIEW_HEADERS,
    )
    draft = listed.json()["drafts"][0]
    assert draft["proposed_payload"]["tbq"] == "N"
    assert draft["validation_evidence"]["tbq_forced_to_y"] is False
    assert draft["validation_evidence"]["tbq_value_is_y"] is False
    assert "PATTERN_RECOMMENDATION_CHANGED" not in {
        trigger["code"] for trigger in draft["review_triggers"]
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
                        "Costo Total $ USD Diario": "=Table357[[#This Row],[Costo]]*1",
                        "Request OIC": 42,
                        "Client-only note": "not governed",
                    },
                    "proposed_payload": {
                        **_complete_payload(),
                        "description": "=A1",
                    },
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
    assert complete["proposed_payload"]["description"] is None
    assert complete["validation_evidence"][
        "excluded_operational_formula_fields"
    ] == ["description"]
    assert complete["source_record"]["TBQ"] == ""
    assert "Costo Total $ USD Diario" not in complete["source_record"]
    assert "Request OIC" not in complete["source_record"]
    assert "Client-only note" not in complete["source_record"]
    assert complete["ignored_source_fields"] == [
        {
            "source_header": "Costo Total $ USD Diario",
            "classification": "commercial_formula",
            "reason": (
                "Commercial formula excluded from the App record; it is never "
                "evaluated or promoted."
            ),
            "value_kind": "formula",
        },
        {
            "source_header": "Request OIC",
            "classification": "derived_demand",
            "reason": (
                "Derived workbook demand is not a supported capture input and is "
                "excluded from the App record."
            ),
            "value_kind": "value",
        },
        {
            "source_header": "Client-only note",
            "classification": "unsupported",
            "reason": (
                "This source column has no governed App target and is excluded from "
                "the App record."
            ),
            "value_kind": "value",
        },
    ]
    assert all(
        "=Table357" not in str(field)
        for field in complete["ignored_source_fields"]
    )
    assert complete["validation_evidence"]["tbq_forced_to_y"] is True
    assert complete["validation_evidence"]["source_file_persisted"] is False
    assert incomplete["required_field_gaps"] == ["destination_system"]
    assert incomplete["approval_blocked"] is True
    assert incomplete["review_triggers"][0] == {
        "code": "REQUIRED_FIELD:destination_system",
        "kind": "required_gap",
        "title": "Destination system is missing",
        "evidence": (
            "The proposed App record has no supported value for Destination system."
        ),
        "required_decision": (
            "Provide verified destination system evidence or reject this proposal."
        ),
        "blocks_approval": True,
    }
    assert incomplete["review_summary"].startswith(
        "Approval is blocked: Destination system is missing."
    )

    session_factory = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with session_factory() as session:
        persisted_complete = await session.scalar(
            select(ExternalCaptureDraft).where(
                ExternalCaptureDraft.id == complete["id"]
            )
        )
        assert persisted_complete is not None
        assert "Costo Total $ USD Diario" not in persisted_complete.source_record
        assert "=Table357" not in str(persisted_complete.source_record)
        assert persisted_complete.validation_evidence[
            "excluded_source_fields"
        ][0]["source_header"] == "Costo Total $ USD Diario"
        focused_evidence = await build_agent_evidence(
            project_id,
            session_id,
            str(complete["id"]),
            session,
        )
    focused = focused_evidence["focused_row"]
    assert isinstance(focused, dict)
    assert focused["draft_id"] == complete["id"]
    assert focused["supported_source_evidence"]["Tamaño KB"] == 48.5
    assert "Costo Total $ USD Diario" not in focused["supported_source_evidence"]
    assert focused["ignored_source_fields"][0]["source_header"] == (
        "Costo Total $ USD Diario"
    )
    assert focused_evidence["sample_rows"] == []
    assert "=Table357" not in str(focused)

    blocked_review = await api_client.post(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            f"/drafts/{incomplete['id']}/review"
        ),
        headers=ARCHITECT_HEADERS,
        json={
            "decision": "approve",
            "rationale": "Approve as supplied.",
            "expected_updated_at": incomplete["updated_at"],
        },
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

    analysis_required = await api_client.post(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            f"/drafts/{complete['id']}/review"
        ),
        headers=ARCHITECT_HEADERS,
        json={
            "decision": "approve",
            "rationale": "Pattern and source evidence reviewed line by line.",
            "expected_updated_at": complete["updated_at"],
        },
    )
    assert analysis_required.status_code == 409
    assert (
        analysis_required.json()["detail"]["error_code"]
        == "EXTERNAL_CAPTURE_AGENT_ANALYSIS_REQUIRED"
    )

    async with session_factory() as session:
        async with session.begin():
            run = AgentRun(
                agent_type="import_quality",
                definition_version="3.2.0",
                project_id=project_id,
                requested_by="architect-1",
                status=AgentRunStatus.COMPLETED,
                context_payload={
                    "external_capture_session_id": session_id,
                    "external_capture_draft_id": complete["id"],
                },
                result_payload={"summary": "Grounded row analysis completed."},
                step_count=4,
                max_steps=4,
            )
            session.add(run)
            await session.flush()
            await record_agent_analysis(
                project_id=project_id,
                session_id=session_id,
                draft_id=str(complete["id"]),
                run_id=run.id,
                analyzed_evidence_hash=str(focused["analysis_evidence_hash"]),
                analysis_payload={
                    "summary": "Grounded row analysis completed.",
                    "provider_status": "completed",
                    "output_quality": {
                        "grounded": True,
                        "fallback_used": False,
                    },
                    "correction_contract_valid": True,
                    "agent_row_analysis": {
                        "explanation": "The row still needs architect review.",
                        "deviations": [],
                        "proposed_patch": {},
                        "excluded_fields": ["Costo Total $ USD Diario"],
                        "required_decisions": [],
                    },
                },
                actor_id="architect-1",
                db=session,
            )

    refreshed_drafts = await api_client.get(
        f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}/drafts",
        headers=ARCHITECT_HEADERS,
    )
    current_complete = next(
        draft for draft in refreshed_drafts.json()["drafts"] if draft["id"] == complete["id"]
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
            "expected_updated_at": current_complete["updated_at"],
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
    assert integration["qa_status"] == "REVIEW"


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


async def test_external_capture_bulk_fix_applies_only_current_grounded_patches(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_pattern(test_engine)
    project_id = await _create_project(api_client)
    session_id = await _create_unforced_session(api_client, project_id)
    staged = await api_client.post(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            "/drafts/bulk"
        ),
        headers=REVIEW_HEADERS,
        json={
            "drafts": [
                {
                    "source_row_number": 20,
                    "source_record": {
                        "Interfaz": "Synthetic interface A",
                        "Sistema Destino": "Corrected Destination",
                    },
                    "proposed_payload": {
                        **_complete_payload(),
                        "interface_id": "SYN-020",
                        "destination_system": "Original Destination",
                    },
                },
                {
                    "source_row_number": 21,
                    "source_record": {"Interfaz": "Synthetic interface B"},
                    "proposed_payload": {
                        **_complete_payload(),
                        "interface_id": "SYN-021",
                    },
                },
            ]
        },
    )
    assert staged.status_code == 200
    listed = await api_client.get(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            "/drafts?page=1&page_size=25"
        ),
        headers=ARCHITECT_HEADERS,
    )
    drafts = listed.json()["drafts"]
    assert len(drafts) == 2

    session_factory = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with session_factory() as session:
        async with session.begin():
            for index, draft in enumerate(drafts):
                evidence = await build_agent_evidence(
                    project_id,
                    session_id,
                    str(draft["id"]),
                    session,
                )
                focused = evidence["focused_row"]
                assert isinstance(focused, dict)
                run = AgentRun(
                    agent_type="import_quality",
                    definition_version="3.2.0",
                    project_id=project_id,
                    requested_by="architect-1",
                    status=AgentRunStatus.COMPLETED,
                    context_payload={
                        "external_capture_session_id": session_id,
                        "external_capture_draft_id": draft["id"],
                    },
                    result_payload={"summary": "Synthetic grounded analysis."},
                    step_count=4,
                    max_steps=4,
                )
                session.add(run)
                await session.flush()
                proposed_patch = (
                    {"destination_system": "Corrected Destination"}
                    if index == 0
                    else {}
                )
                required_decisions = (
                    []
                    if index == 0
                    else ["Confirm the intended governed pattern."]
                )
                await record_agent_analysis(
                    project_id=project_id,
                    session_id=session_id,
                    draft_id=str(draft["id"]),
                    run_id=run.id,
                    analyzed_evidence_hash=str(
                        focused["analysis_evidence_hash"]
                    ),
                    analysis_payload={
                        "summary": "Synthetic grounded analysis.",
                        "provider_status": "completed",
                        "output_quality": {
                            "grounded": True,
                            "fallback_used": False,
                        },
                        "correction_contract_valid": True,
                        "agent_row_analysis": {
                            "explanation": "Synthetic row analysis.",
                            "deviations": [],
                            "proposed_patch": proposed_patch,
                            "excluded_fields": [],
                            "required_decisions": required_decisions,
                            "no_op_patch_fields": [],
                        },
                    },
                    actor_id="architect-1",
                    db=session,
                )

    refreshed = await api_client.get(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            "/drafts?page=1&page_size=25"
        ),
        headers=ARCHITECT_HEADERS,
    )
    refreshed_drafts = refreshed.json()["drafts"]
    assert refreshed_drafts[0]["agent_analysis"]["correction_available"] is True
    assert refreshed_drafts[0]["agent_analysis"]["correction_fields"] == [
        "destination_system"
    ]
    assert refreshed_drafts[1]["agent_analysis"]["correction_available"] is False
    assert len(refreshed_drafts[1]["agent_analysis"]["required_decisions"]) == 1

    applied = await api_client.post(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            "/corrections/apply"
        ),
        headers=ARCHITECT_HEADERS,
        json={"scope": "all_eligible", "draft_ids": [], "confirm": True},
    )
    assert applied.status_code == 200
    result = applied.json()
    assert result["requested"] == 2
    assert result["eligible"] == 1
    assert result["applied"] == 1
    assert result["skipped"] == 1
    assert result["failed"] == 0
    assert result["human_decision_rows"] == 1
    assert result["results"][0]["reason_code"] == (
        "CORRECTION_APPLIED_REANALYSIS_REQUIRED"
    )
    assert result["results"][1]["reason_code"] == "HUMAN_DECISION_REQUIRED"

    after = await api_client.get(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            "/drafts?page=1&page_size=25"
        ),
        headers=ARCHITECT_HEADERS,
    )
    after_drafts = after.json()["drafts"]
    assert (
        after_drafts[0]["proposed_payload"]["destination_system"]
        == "Corrected Destination"
    )
    assert after_drafts[0]["agent_analysis"]["status"] == "stale"
    assert all(draft["status"] == "needs_review" for draft in after_drafts)

    repeated = await api_client.post(
        (
            f"/api/v1/projects/{project_id}/external-capture/sessions/{session_id}"
            "/corrections/apply"
        ),
        headers=ARCHITECT_HEADERS,
        json={"scope": "all_eligible", "draft_ids": [], "confirm": True},
    )
    assert repeated.status_code == 200
    assert repeated.json()["eligible"] == 0
    assert repeated.json()["applied"] == 0

    catalog = await api_client.get(
        f"/api/v1/catalog/{project_id}?page=1&page_size=20"
    )
    assert catalog.status_code == 200
    assert catalog.json()["total"] == 0
