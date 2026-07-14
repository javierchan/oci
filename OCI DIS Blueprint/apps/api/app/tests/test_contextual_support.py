"""API coverage for session-isolated contextual App support."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import AuditEvent, CatalogIntegration, PatternDefinition, Project, ServiceCapabilityProfile
from app.routers import support as support_router
from app.services import agent_service, support_service


SESSION_A = "11111111-1111-4111-8111-111111111111"
SESSION_B = "22222222-2222-4222-8222-222222222222"
HEADERS_A = {"X-Actor-Id": "support-user", "X-Actor-Role": "Viewer", "X-Support-Session-Id": SESSION_A}
HEADERS_B = {"X-Actor-Id": "other-user", "X-Actor-Role": "Viewer", "X-Support-Session-Id": SESSION_B}


def test_support_domain_boundary_is_conservative() -> None:
    assert support_service.question_is_in_scope("How does BOM pricing work?", has_context=False)
    assert support_service.question_is_in_scope("What does this mean?", has_context=True)
    assert not support_service.question_is_in_scope("What is the weather today?", has_context=True)
    assert not support_service.question_is_in_scope("Write a poem", has_context=False)
    assert not support_service._question_needs_project_scope("¿Cuántos proyectos tenemos?")
    assert support_service._question_needs_project_scope("¿Cuál es el precio total de este proyecto?")


@pytest.mark.asyncio
async def test_support_resolves_single_active_project_for_global_cost_question(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            project = Project(
                name="Only Active Support Project",
                description="Commercial context must be available outside the BOM route.",
                status="active",
                owner_id="support-owner",
            )
            session.add(project)
            await session.flush()
            evidence = await support_service.build_support_evidence(
                None,
                None,
                {
                    "question": "¿Cuál es el precio total de este proyecto?",
                    "route": "/admin/agents",
                    "page_title": "Governance · Agents",
                    "attachments": [],
                    "transcript": [
                        {"role": "user", "content": "¿Cuántos proyectos tenemos?"},
                    ],
                },
                session,
            )

    resolution = cast(dict[str, object], evidence["project_resolution"])
    project_evidence = cast(dict[str, object], evidence["project"])
    citations = cast(list[dict[str, str]], evidence["citations"])
    assert evidence["question_intent"] == "project_cost"
    assert resolution["method"] == "single_active_project"
    assert resolution["resolved_project_id"] == project.id
    assert resolution["ambiguous"] is False
    assert project_evidence["name"] == "Only Active Support Project"
    assert project_evidence["latest_bom"] is None
    assert any(item["href"] == f"/projects/{project.id}" for item in citations)
    assert any(item["href"] == f"/projects/{project.id}/bom" for item in citations)
    assert "todavía no tiene un BOM calculado" in str(evidence["fallback_answer"])
    assert evidence["direct_answer"] == evidence["fallback_answer"]


@pytest.mark.asyncio
async def test_support_keeps_multiple_active_projects_ambiguous_until_named(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            first = Project(
                name="Northwind Architecture",
                status="active",
                owner_id="support-owner",
            )
            second = Project(
                name="Contoso Architecture",
                status="active",
                owner_id="support-owner",
            )
            session.add_all([first, second])
            await session.flush()
            ambiguous = await support_service.build_support_evidence(
                None,
                None,
                {
                    "question": "¿Cuál es el costo de este proyecto?",
                    "route": "/admin/agents",
                    "attachments": [],
                    "transcript": [],
                },
                session,
            )
            named = await support_service.build_support_evidence(
                None,
                None,
                {
                    "question": "¿Cuál es el costo de Contoso Architecture?",
                    "route": "/admin/agents",
                    "attachments": [],
                    "transcript": [],
                },
                session,
            )

    ambiguous_resolution = cast(dict[str, object], ambiguous["project_resolution"])
    named_resolution = cast(dict[str, object], named["project_resolution"])
    assert ambiguous_resolution["ambiguous"] is True
    assert ambiguous_resolution["resolved_project_id"] is None
    assert "project" not in ambiguous
    assert len(cast(list[object], ambiguous["project_workspaces"])) == 2
    assert named_resolution["method"] == "named_in_conversation"
    assert named_resolution["resolved_project_id"] == second.id
    assert cast(dict[str, object], named["project"])["name"] == "Contoso Architecture"


@pytest.mark.asyncio
async def test_support_conversation_is_isolated_and_out_of_scope_is_refused(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_apply_async(*, args: list[str], task_id: str, queue: str) -> SimpleNamespace:
        assert args == [task_id]
        assert queue == "agents"
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(support_router.execute_agent_run_task, "apply_async", fake_apply_async)
    created = await api_client.post("/api/v1/support/conversations/current", headers=HEADERS_A)
    assert created.status_code == 200
    conversation_id = created.json()["id"]

    isolated = await api_client.get(
        f"/api/v1/support/conversations/{conversation_id}", headers=HEADERS_B
    )
    assert isolated.status_code == 404

    submitted = await api_client.post(
        f"/api/v1/support/conversations/{conversation_id}/messages",
        headers=HEADERS_A,
        json={
            "content": "What is the weather today?",
            "route": "/projects",
            "page_title": "Projects",
            "attachments": [],
        },
    )
    assert submitted.status_code == 202
    assistant = submitted.json()["messages"][-1]
    assert assistant["status"] == "pending"
    assert assistant["agent_run_id"]

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            await agent_service.mark_agent_run_running(assistant["agent_run_id"], session)
        async with session.begin():
            completed = await agent_service.run_agent(assistant["agent_run_id"], session)

    assert completed.status == "completed"
    assert completed.result is not None
    assert completed.result["provider_status"] == "skipped"
    refreshed = await api_client.get(
        f"/api/v1/support/conversations/{conversation_id}", headers=HEADERS_A
    )
    final_message = refreshed.json()["messages"][-1]
    assert final_message["status"] == "refused"
    assert "help with OCI DIS Architect" in final_message["content"]

    isolated_clear = await api_client.delete(
        f"/api/v1/support/conversations/{conversation_id}/messages", headers=HEADERS_B
    )
    assert isolated_clear.status_code == 404
    cleared = await api_client.delete(
        f"/api/v1/support/conversations/{conversation_id}/messages", headers=HEADERS_A
    )
    assert cleared.status_code == 200
    assert cleared.json()["id"] == conversation_id
    assert cleared.json()["messages"] == []
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        event = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "support_conversation_history_cleared",
                AuditEvent.entity_id == conversation_id,
            )
        )
    assert event is not None
    assert event.old_value == {"message_count": 2, "attachment_count": 0}
    assert event.new_value == {"message_count": 0, "attachment_count": 0}


@pytest.mark.asyncio
async def test_support_turn_persists_explicit_component_context(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        support_router.execute_agent_run_task,
        "apply_async",
        lambda **kwargs: SimpleNamespace(id=kwargs["task_id"]),
    )
    created = await api_client.post("/api/v1/support/conversations/current", headers=HEADERS_B)
    conversation_id = created.json()["id"]
    submitted = await api_client.post(
        f"/api/v1/support/conversations/{conversation_id}/messages",
        headers=HEADERS_B,
        json={
            "content": "Explain this integration.",
            "route": "/projects/project-1/catalog/integration-1",
            "page_title": "Integration Detail",
            "attachments": [
                {
                    "attachment_type": "integration",
                    "label": "Integration Detail",
                    "entity_id": "integration-1",
                    "href": "/projects/project-1/catalog/integration-1",
                    "context": {"selected_tab": "canvas"},
                }
            ],
        },
    )
    assert submitted.status_code == 202
    user_message = submitted.json()["messages"][-2]
    assert user_message["attachments"][0]["label"] == "Integration Detail"
    assert user_message["attachments"][0]["context"] == {"selected_tab": "canvas"}
    pending_clear = await api_client.delete(
        f"/api/v1/support/conversations/{conversation_id}/messages", headers=HEADERS_B
    )
    assert pending_clear.status_code == 409
    assert pending_clear.json()["detail"]["error_code"] == "SUPPORT_TURN_PENDING"


@pytest.mark.asyncio
async def test_support_evidence_connects_integration_to_business_process_and_governance(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            project = Project(
                name="Support Evidence Project",
                description="Governed order lifecycle assessment",
                status="active",
                owner_id="support-owner",
            )
            session.add(project)
            await session.flush()
            first = CatalogIntegration(
                project_id=project.id,
                seq_number=1,
                interface_id="SUP-001",
                interface_name="Capture Customer Order",
                description="Receives a validated customer order.",
                business_process="Order to Cash",
                source_system="Commerce",
                destination_system="Order Management",
                selected_pattern="#98",
                qa_status="OK",
            )
            second = CatalogIntegration(
                project_id=project.id,
                seq_number=2,
                interface_id="SUP-002",
                interface_name="Create Receivable",
                description="Creates the customer receivable after fulfillment.",
                business_process="Order to Cash",
                source_system="Order Management",
                destination_system="Finance",
                selected_pattern="#98",
                qa_status="REVISAR",
            )
            session.add_all(
                [
                    first,
                    second,
                    PatternDefinition(
                        pattern_id="#98",
                        name="Support Test Pattern",
                        category="Test",
                        description="A governed test pattern.",
                        is_active=True,
                    ),
                    ServiceCapabilityProfile(
                        service_id="support-test-service",
                        name="Support Test Service",
                        category="Integration",
                        architectural_fit="Routes governed application messages.",
                        is_active=True,
                    ),
                ]
            )
            await session.flush()
            evidence = await support_service.build_support_evidence(
                project.id,
                first.id,
                {
                    "question": "Explain the Order to Cash process, its pattern, and Service Products.",
                    "route": f"/projects/{project.id}/catalog/{first.id}",
                    "page_title": "Integration Detail",
                    "attachments": [],
                    "transcript": [
                        {"role": "user", "content": "What does this process do?"},
                        {"role": "assistant", "content": "An earlier unverified model answer."},
                    ],
                },
                session,
            )

    integration_evidence = cast(dict[str, object], evidence["integration"])
    process_evidence = cast(dict[str, object], evidence["business_process_flow"])
    ordered_integrations = cast(list[dict[str, object]], process_evidence["ordered_integrations"])
    pattern_library = cast(list[dict[str, object]], evidence["pattern_library"])
    service_library = cast(list[dict[str, object]], evidence["service_product_library"])
    assert evidence["in_scope"] is True
    assert len(cast(list[object], evidence["app_sections"])) == 8
    assert integration_evidence["description"] == "Receives a validated customer order."
    assert process_evidence["name"] == "Order to Cash"
    assert process_evidence["captured_predecessor"] is None
    assert process_evidence["captured_successor"] == "Create Receivable"
    assert [item["name"] for item in ordered_integrations] == [
        "Capture Customer Order",
        "Create Receivable",
    ]
    assert any(item["name"] == "Support Test Pattern" for item in pattern_library)
    assert any(
        item["name"] == "Support Test Service" for item in service_library
    )
    assert evidence["conversation_questions"] == [
        {"role": "user", "content": "What does this process do?"}
    ]
    assert "Capture Customer Order moves governed data" in str(evidence["fallback_answer"])


def test_support_summary_grounding_rejects_unsupported_actions_and_sensitive_claims() -> None:
    evidence: dict[str, object] = {
        "integration": {
            "recommended_next_action": "Review the captured process boundary and saved design."
        }
    }

    assert support_service.support_summary_is_grounded(
        "QA is OK. Review the captured process boundary and saved design.", evidence
    )
    assert not support_service.support_summary_is_grounded(
        "Approve this integration and continue to deployment.", evidence
    )
    assert not support_service.support_summary_is_grounded(
        "This avoids GDPR sanctions.", evidence
    )
    assert not support_service.support_summary_is_grounded(
        "Open /projects/{project_id} for [REDACTED] details.", evidence
    )
    spanish_fallback = support_service._support_fallback_answer(
        {
            "response_language": "es",
            "integration": {
                "name": "Pedido a Inventario",
                "source_system": "ERP",
                "destination_system": "Inventario",
                "business_process": "Order to Cash",
                "qa_status": "OK",
                "qa_reasons": [],
                "needs_attention": False,
            },
        }
    )
    assert "mueve datos gobernados" in spanish_fallback
    assert "Siguiente paso" in spanish_fallback
    cost_fallback = support_service._support_fallback_answer(
        {
            "response_language": "es",
            "question_intent": "project_cost",
            "project": {
                "name": "Proyecto Comercial",
                "latest_bom": {
                    "currency": "USD",
                    "contract_total": 42081.7,
                    "monthly_total": 6875.9,
                    "peak_monthly_total": 7112.25,
                    "coverage_pct": 100,
                    "publication_status": "approved",
                },
            },
        }
    )
    assert "USD 42,081.70" in cost_fallback
    assert "Pico mensual: USD 7,112.25" in cost_fallback
    assert "Cobertura de precios: 100%" in cost_fallback
