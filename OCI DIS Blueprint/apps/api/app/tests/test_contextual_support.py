"""API coverage for session-isolated contextual App support."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Awaitable, Callable, cast

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import (
    AuditEvent,
    CatalogIntegration,
    PatternDefinition,
    PriceCatalogSnapshot,
    PriceItem,
    PriceSource,
    Project,
    ServiceCapabilityProfile,
    ServiceProductSkuMapping,
)
from app.routers import support as support_router
from app.services import agent_service, support_service
from app.services.genai_client import GenAiAgentResult
from app.services.support_routing_service import route_support_question


SESSION_A = "11111111-1111-4111-8111-111111111111"
SESSION_B = "22222222-2222-4222-8222-222222222222"
HEADERS_A = {"X-Actor-Id": "support-user", "X-Actor-Role": "Viewer", "X-Support-Session-Id": SESSION_A}
HEADERS_B = {"X-Actor-Id": "other-user", "X-Actor-Role": "Viewer", "X-Support-Session-Id": SESSION_B}
CAPABILITY_EVAL_CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "support_assistant_capability_cases.json").read_text()
)


def test_support_domain_boundary_accepts_benign_topics_for_graceful_redirect() -> None:
    assert support_service.question_is_in_scope("How does BOM pricing work?", has_context=False)
    assert support_service.question_is_in_scope("What does this mean?", has_context=True)
    assert support_service.question_is_in_scope("¿Cómo se factura al cliente?", has_context=True)
    assert support_service.question_is_in_scope("What is the weather today?", has_context=True)
    assert support_service.question_is_in_scope("Write a poem", has_context=False)
    assert not support_service.question_is_in_scope("", has_context=True)
    assert not support_service._question_needs_project_scope("¿Cuántos proyectos tenemos?")
    assert support_service._question_needs_project_scope("¿Cuál es el precio total de este proyecto?")


def test_support_routes_spanish_billing_verbs_to_commercial_evidence() -> None:
    route = route_support_question(
        "¿Cómo se cobra OCI Functions a un cliente?",
        project_is_explicit=False,
        needs_project_scope=False,
    )
    assert route.intent == "commercial_guidance"
    assert route.needs_commercial_evidence is True


@pytest.mark.asyncio
async def test_support_capability_eval_matrix_uses_governed_evidence_and_mocked_genai(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep capability routing, abstention, exports, and citations deterministic."""

    monkeypatch.setattr(
        support_router.execute_agent_run_task,
        "apply_async",
        lambda **kwargs: SimpleNamespace(id=kwargs["task_id"]),
    )
    provider_calls = 0

    async def governed_mock_provider(*args: object, **kwargs: object) -> GenAiAgentResult:
        nonlocal provider_calls
        provider_calls += 1
        settings = cast(Settings, kwargs["settings"])
        assert settings.OCI_GENAI_MODEL_NAME == "OpenAI gpt-oss-120b"
        executor = cast(
            Callable[[dict[str, object]], Awaitable[dict[str, object]]],
            kwargs["tool_executor"],
        )
        evidence = await executor({})
        return GenAiAgentResult(
            status="completed",
            model="OpenAI gpt-oss-120b",
            summary=str(evidence["fallback_answer"]),
            tool_name=str(kwargs["tool_name"]),
            tool_output=evidence,
            transport="responses",
        )

    monkeypatch.setattr(agent_service, "run_governed_tool_agent", governed_mock_provider)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    created = await api_client.post("/api/v1/support/conversations/current", headers=HEADERS_A)
    conversation_id = created.json()["id"]

    for case in CAPABILITY_EVAL_CASES:
        submitted = await api_client.post(
            f"/api/v1/support/conversations/{conversation_id}/messages",
            headers=HEADERS_A,
            json={
                "content": case["question"],
                "route": "/projects",
                "page_title": "Projects",
                "attachments": [],
            },
        )
        assert submitted.status_code == 202, f"{case['id']}: {submitted.text}"
        assistant = submitted.json()["messages"][-1]
        async with session_factory() as session:
            async with session.begin():
                await agent_service.mark_agent_run_running(assistant["agent_run_id"], session)
            async with session.begin():
                completed = await agent_service.run_agent(assistant["agent_run_id"], session)

        assert completed.result is not None
        result = cast(dict[str, object], completed.result)
        evidence = cast(dict[str, object], result["evidence"])
        assert evidence["question_intent"] == case["expected_intent"], case["id"]
        app_knowledge = cast(dict[str, object], evidence["app_knowledge"])
        assessment = app_knowledge.get("capability_assessment")
        if case["expected_capability"] is None:
            assert assessment is None, case["id"]
        else:
            assert isinstance(assessment, dict), case["id"]
            assert assessment["status"] == case["expected_capability"], case["id"]

        refreshed = await api_client.get(
            f"/api/v1/support/conversations/{conversation_id}", headers=HEADERS_A
        )
        message = refreshed.json()["messages"][-1]
        content = message["content"].casefold()
        for required in case["required_terms"]:
            assert required in content, f"{case['id']}: missing {required!r} in {content!r}"
        for forbidden in case["forbidden_terms"]:
            assert forbidden not in content, f"{case['id']}: found {forbidden!r} in {content!r}"
        assert content.count("**next action:**") == 1, case["id"]
        for citation in message["citations"]:
            assert citation["href"].startswith("/"), case["id"]
            assert "[" not in citation["href"] and "{" not in citation["href"], case["id"]
        source_labels = {citation["label"] for citation in message["citations"]}
        assert set(case["expected_sources"]).issubset(source_labels), case["id"]

    assert provider_calls == len(CAPABILITY_EVAL_CASES)


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
    assert "direct_answer" not in evidence
    assert cast(dict[str, object], evidence["response_contract"])["model_authorship"] == "primary"
    assert any(item["id"] == "project.integration_count" for item in cast(list[dict[str, object]], evidence["verified_facts"]))


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
async def test_support_answers_general_commercial_questions_without_forcing_route_project_scope(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            project = Project(
                name="Route Context Project",
                status="active",
                owner_id="support-owner",
            )
            session.add(project)
            await session.flush()
            evidence = await support_service.build_support_evidence(
                project.id,
                None,
                {
                    "question": "¿Cuánto cuesta OIC Enterprise y cómo se factura a un cliente?",
                    "route": f"/projects/{project.id}/graph",
                    "page_title": "Map",
                    "attachments": [],
                    "transcript": [],
                },
                session,
            )

    citations = cast(list[dict[str, str]], evidence["citations"])
    assert evidence["question_intent"] == "commercial_guidance"
    assert "direct_answer" not in evidence
    assert "no identifica todavía un Service Product/SKU" in str(evidence["fallback_answer"])
    assert any(item["href"] == "/admin/pricing" for item in citations)


@pytest.mark.asyncio
async def test_support_resolves_commercial_follow_up_from_dialogue_and_governed_price_evidence(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            source = PriceSource(
                name="Support price source",
                source_type="public_list",
                currency="USD",
                created_by="support-test",
            )
            profile = ServiceCapabilityProfile(
                service_id="OIC3",
                name="Oracle Integration 3 (OIC Gen3)",
                category="ORCHESTRATION",
                pricing_model="Message pack",
                is_active=True,
            )
            session.add_all([source, profile])
            await session.flush()
            snapshot = PriceCatalogSnapshot(
                source_id=source.id,
                currency="USD",
                retrieved_at=datetime.now(UTC),
                content_hash="support-price-catalog",
                item_count=1,
                approval_status="approved",
            )
            session.add_all(
                [
                    snapshot,
                    ServiceProductSkuMapping(
                        service_id="OIC3",
                        tool_key="OIC Gen3",
                        part_number="B89644",
                        billing_metric_key="oic_peak_packs_hour",
                        formula_key="hourly_capacity",
                        quantity_unit="message packs",
                        predicates={"edition": "enterprise", "byol": True},
                        status="approved",
                    ),
                ]
            )
            await session.flush()
            session.add(
                PriceItem(
                    snapshot_id=snapshot.id,
                    part_number="B89644",
                    display_name="Oracle Integration Cloud Service - Enterprise - BYOL",
                    metric_name="20K Messages Per Hour",
                    service_category="Application Integration - OIC",
                    price_type="HOUR",
                    currency="USD",
                    value=0.3226,
                )
            )
            await session.flush()
            evidence = await support_service.build_support_evidence(
                None,
                None,
                {
                    "question": "pero quiero saber cuanto cuesta este servicio en OCI",
                    "route": "/admin/pricing",
                    "attachments": [],
                    "transcript": [
                        {"role": "user", "content": "Como se cobra OCI Gen3 Enterprise en BYOL?"},
                    ],
                },
                session,
            )

    commercial_context = cast(dict[str, object], evidence["commercial_service_context"])
    options = cast(list[dict[str, object]], commercial_context["sku_options"])
    assert evidence["response_language"] == "es"
    assert evidence["question_intent"] == "commercial_guidance"
    assert commercial_context["service_id"] == "OIC3"
    assert options[0]["part_number"] == "B89644"
    assert cast(dict[str, object], options[0]["price"])["value"] == 0.3226
    assert "USD 0.3226" in str(evidence["fallback_answer"])


@pytest.mark.asyncio
async def test_support_persists_only_resolved_conversation_references(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            conversation = support_service.SupportConversation(
                session_id=SESSION_A,
                actor_id="support-user",
                title="Support",
                status="active",
            )
            session.add(conversation)
            await session.flush()
            await support_service.update_conversation_state(
                conversation.id,
                {
                    "question_intent": "commercial_guidance",
                    "response_language": "es",
                    "commercial_service_context": {"service_id": "FUNCTIONS", "service_name": "OCI Functions"},
                    "project_resolution": {"resolved_project_id": "project-1"},
                },
                session,
            )

    assert conversation.context_state == {
        "topic": "commercial_guidance",
        "language": "es",
        "active_service": {"id": "FUNCTIONS", "name": "OCI Functions"},
        "active_project_id": "project-1",
    }


@pytest.mark.asyncio
async def test_support_does_not_carry_commercial_intent_into_a_new_pattern_question(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            session.add(
                PatternDefinition(
                    pattern_id="P01",
                    name="Request and Reply",
                    category="Synchronous",
                    description="A caller waits for one response from the target service.",
                    when_to_use="a caller needs an immediate response to continue its process.",
                    when_not_to_use="the work can be accepted now and completed asynchronously.",
                    applicability_examples=[],
                    selection_questions=[],
                    required_inputs=[],
                )
            )
            await session.flush()
            evidence = await support_service.build_support_evidence(
                None,
                None,
                {
                    "question": "Explica el patrón request and reply",
                    "route": "/projects",
                    "attachments": [],
                    "transcript": [
                        {"role": "user", "content": "¿Cómo se cobra OCI Functions?"},
                    ],
                },
                session,
            )

    assert evidence["question_intent"] == "app_guidance"
    assert "commercial_service_context" not in evidence
    assert "direct_answer" not in evidence
    assert "Request and Reply" in str(evidence["fallback_answer"])
    assert "OCI Functions" not in str(evidence["fallback_answer"])


@pytest.mark.asyncio
async def test_support_builds_model_grounding_without_stale_topic_leakage(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            evidence = await support_service.build_support_evidence(
                None,
                None,
                {
                    "question": "¿Cómo importo un archivo y reviso qué filas quedaron fuera?",
                    "route": "/projects",
                    "attachments": [],
                    "transcript": [
                        {"role": "user", "content": "¿Cómo se cobra OCI Functions?"},
                    ],
                    "conversation_state": {
                        "topic": "commercial_guidance",
                        "active_service": {"id": "FUNCTIONS", "name": "OCI Functions"},
                    },
                },
                session,
            )

    contract = cast(dict[str, object], evidence["response_contract"])
    assert evidence["question_intent"] == "workflow_guidance"
    assert contract["model_authorship"] == "primary"
    assert contract["deterministic_fallback"] == "provider_failure_or_grounding_failure_only"
    assert "direct_answer" not in evidence
    assert "**Import**" in str(evidence["fallback_answer"])
    assert "OCI Functions" not in str(evidence["fallback_answer"])


@pytest.mark.asyncio
async def test_support_explains_scenario_licensing_without_requiring_a_product_sku(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            evidence = await support_service.build_support_evidence(
                None,
                None,
                {
                    "question": "¿Qué significa License Included o BYOL en un escenario?",
                    "route": "/projects",
                    "attachments": [],
                    "transcript": [],
                },
                session,
            )

    assert evidence["question_intent"] == "workflow_guidance"
    assert "direct_answer" not in evidence
    assert "**BOM & Cost**" in str(evidence["fallback_answer"])


@pytest.mark.asyncio
async def test_support_uses_only_a_resolved_service_for_a_narrow_commercial_follow_up(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            evidence = await support_service.build_support_evidence(
                None,
                None,
                {
                    "question": "¿Qué métricas se suman para ese servicio?",
                    "route": "/admin/pricing",
                    "attachments": [],
                    "transcript": [{"role": "user", "content": "¿Cómo se cobra OCI Functions?"}],
                    "conversation_state": {
                        "active_service": {"id": "FUNCTIONS", "name": "OCI Functions"},
                    },
                },
                session,
            )

    assert evidence["question_intent"] == "commercial_guidance"


@pytest.mark.asyncio
async def test_support_conversation_is_isolated_and_external_topic_is_redirected(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_apply_async(*, args: list[str], task_id: str, queue: str) -> SimpleNamespace:
        assert args == [task_id]
        assert queue == "agents"
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(support_router.execute_agent_run_task, "apply_async", fake_apply_async)

    async def redirect_with_app_help(*args: object, **kwargs: object) -> GenAiAgentResult:
        return GenAiAgentResult(
            status="completed",
            model="mock-support-model",
            summary=(
                "I can’t help with weather, but I can help you inspect governed OCI integration evidence.\n\n"
                "**Next action:** [Open Projects](/projects)"
            ),
            tool_name="answer_app_support_question",
            transport="responses",
        )

    monkeypatch.setattr(agent_service, "run_governed_tool_agent", redirect_with_app_help)

    fallback = support_service._support_fallback_answer(
        {
            "response_language": "en",
            "app_redirect": {"required": True},
        }
    )
    assert "I can’t answer that external-topic question" in fallback
    assert "I’m here to help with OCI DIS Architect" in fallback
    assert "weather" not in fallback.casefold()

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
    assert completed.result["provider_status"] == "completed"
    refreshed = await api_client.get(
        f"/api/v1/support/conversations/{conversation_id}", headers=HEADERS_A
    )
    final_message = refreshed.json()["messages"][-1]
    assert final_message["status"] == "completed"
    assert "[Open Projects](/projects)" in final_message["content"]

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
    assert cleared.json()["context_state"] == {}
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
async def test_support_user_can_remove_one_resolved_context_item(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    created = await api_client.post("/api/v1/support/conversations/current", headers=HEADERS_A)
    conversation_id = created.json()["id"]
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            conversation = await session.get(support_service.SupportConversation, conversation_id)
            assert conversation is not None
            conversation.context_state = {
                "active_service": {"id": "OIC3", "name": "Oracle Integration 3"},
                "active_pattern": {"id": "P01", "name": "Request-Reply"},
                "topic": "app_guidance",
            }

    removed = await api_client.delete(
        f"/api/v1/support/conversations/{conversation_id}/context/active_service",
        headers=HEADERS_A,
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["context_state"] == {
        "active_pattern": {"id": "P01", "name": "Request-Reply"},
        "topic": "app_guidance",
    }
    isolated = await api_client.delete(
        f"/api/v1/support/conversations/{conversation_id}/context/topic",
        headers=HEADERS_B,
    )
    assert isolated.status_code == 404


@pytest.mark.asyncio
async def test_support_hides_internal_reasoning_from_persisted_history(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    created = await api_client.post("/api/v1/support/conversations/current", headers=HEADERS_A)
    conversation_id = created.json()["id"]
    leaked_content = (
        "The answer should lead them to Projects and Capture. Use citations: route /projects. "
        "No tables. Use plain language. Mention next actions. Provide guidance."
    )
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            message = support_service.SupportMessage(
                conversation_id=conversation_id,
                role="assistant",
                content=leaked_content,
                status="completed",
                context_snapshot={},
                citations=[],
            )
            session.add(message)

    refreshed = await api_client.get(
        f"/api/v1/support/conversations/{conversation_id}", headers=HEADERS_A
    )

    assert refreshed.status_code == 200
    visible_content = refreshed.json()["messages"][-1]["content"]
    assert visible_content == support_service.WITHHELD_INTERNAL_RESPONSE
    assert "The answer should" not in visible_content
    async with session_factory() as session:
        persisted = await session.get(support_service.SupportMessage, message.id)
        assert persisted is not None
        assert persisted.content == leaked_content


@pytest.mark.asyncio
async def test_support_refuses_to_persist_internal_reasoning_as_a_completed_answer(
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            conversation = support_service.SupportConversation(
                session_id="33333333-3333-4333-8333-333333333333",
                actor_id="support-user",
                title="Rationale protection",
                status="active",
            )
            session.add(conversation)
            await session.flush()
            message = support_service.SupportMessage(
                conversation_id=conversation.id,
                role="assistant",
                content="pending",
                status="pending",
                context_snapshot={},
                citations=[],
            )
            session.add(message)
            await session.flush()
            await support_service.complete_support_message(
                message.id,
                content="Use citations. Let's craft. We'll follow style.",
                status="completed",
                citations=[{"label": "Projects", "href": "/projects"}],
                db=session,
            )

        await session.refresh(message)
        assert message.content == support_service.WITHHELD_INTERNAL_RESPONSE
        assert message.status == "failed"
        assert message.citations == []


@pytest.mark.asyncio
async def test_support_uses_provider_as_primary_author_for_a_resolved_workflow_answer(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        support_router.execute_agent_run_task,
        "apply_async",
        lambda **kwargs: SimpleNamespace(id=kwargs["task_id"]),
    )

    calls = 0

    async def provider_authors_answer(*args: object, **kwargs: object) -> GenAiAgentResult:
        nonlocal calls
        calls += 1
        return GenAiAgentResult(
            status="completed",
            model="mock-support-model",
            summary=(
                "Importa el libro desde el workspace del proyecto; la App conservará el lote y la trazabilidad.\n\n"
                "1. Descarga o prepara el template gobernado.\n"
                "2. Sube el archivo y revisa el resultado de mapeo.\n\n"
                "**Siguiente paso:** [Abrir proyectos](/projects)"
            ),
            tool_name="answer_app_support_question",
            transport="responses",
        )

    monkeypatch.setattr(agent_service, "run_governed_tool_agent", provider_authors_answer)
    created = await api_client.post("/api/v1/support/conversations/current", headers=HEADERS_A)
    conversation_id = created.json()["id"]
    submitted = await api_client.post(
        f"/api/v1/support/conversations/{conversation_id}/messages",
        headers=HEADERS_A,
        json={
            "content": "¿Cómo importo un archivo?",
            "route": "/projects",
            "page_title": "Projects",
            "attachments": [],
        },
    )
    assistant = submitted.json()["messages"][-1]

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            await agent_service.mark_agent_run_running(assistant["agent_run_id"], session)
        async with session.begin():
            completed = await agent_service.run_agent(assistant["agent_run_id"], session)

    assert completed.result is not None
    assert calls == 1
    assert completed.result["provider_status"] == "completed"
    assert completed.steps[2].status == "completed"
    refreshed = await api_client.get(
        f"/api/v1/support/conversations/{conversation_id}", headers=HEADERS_A
    )
    assert "Importa el libro" in refreshed.json()["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_support_uses_deterministic_fallback_only_when_provider_fails(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        support_router.execute_agent_run_task,
        "apply_async",
        lambda **kwargs: SimpleNamespace(id=kwargs["task_id"]),
    )

    async def failed_provider(*args: object, **kwargs: object) -> GenAiAgentResult:
        return GenAiAgentResult(
            status="failed",
            model="mock-support-model",
            summary=None,
            tool_name="answer_app_support_question",
            error="provider_unavailable",
            transport="responses",
        )

    monkeypatch.setattr(agent_service, "run_governed_tool_agent", failed_provider)
    created = await api_client.post("/api/v1/support/conversations/current", headers=HEADERS_A)
    conversation_id = created.json()["id"]
    submitted = await api_client.post(
        f"/api/v1/support/conversations/{conversation_id}/messages",
        headers=HEADERS_A,
        json={
            "content": "How do I import a workbook?",
            "route": "/projects",
            "page_title": "Projects",
            "attachments": [],
        },
    )
    assert submitted.status_code == 202, submitted.text
    assistant = submitted.json()["messages"][-1]

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            await agent_service.mark_agent_run_running(assistant["agent_run_id"], session)
        async with session.begin():
            completed = await agent_service.run_agent(assistant["agent_run_id"], session)

    assert completed.result is not None
    assert completed.result["provider_status"] == "failed"
    refreshed = await api_client.get(
        f"/api/v1/support/conversations/{conversation_id}", headers=HEADERS_A
    )
    content = refreshed.json()["messages"][-1]["content"]
    assert "**Import**" in content
    assert "[Open Import](/projects)" in content


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
    app_knowledge = cast(dict[str, object], evidence["app_knowledge"])
    assert app_knowledge["documented"] is True
    assert cast(list[object], app_knowledge["entries"])
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
    assert support_service.support_summary_is_grounded(
        "Review the integration before approval and deployment.", evidence
    )
    assert support_service.support_summary_is_grounded(
        "| Finding | Action |\n|---|---|\n| QA | Review the integration |", evidence
    )
    assert support_service.support_summary_is_grounded(" ".join(["grounded"] * 400), evidence)
    assert not support_service.support_summary_is_grounded(
        "This avoids GDPR sanctions.", evidence
    )
    assert not support_service.support_summary_is_grounded(
        "Open /projects/{project_id} for [REDACTED] details.", evidence
    )
    assert not support_service.support_summary_is_grounded("Use Oracle SKU B999999.", evidence)
    assert support_service.support_summary_is_grounded(
        "Use Oracle SKU B999999.", {"verified_facts": [{"value": "B999999"}]}
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
    edition_choice_fallback = support_service._support_fallback_answer(
        {
            "response_language": "es",
            "question_intent": "commercial_guidance",
            "commercial_service_context": {
                "service_name": "Oracle Integration 3 (OIC Gen3)",
                "sku_options": [
                    {
                        "part_number": "B89643",
                        "predicates": {"edition": "standard", "byol": True},
                        "price": {
                            "currency": "USD",
                            "value": 0.1613,
                            "price_type": "HOUR",
                        },
                    },
                    {
                        "part_number": "B89644",
                        "predicates": {"edition": "enterprise", "byol": True},
                        "price": {
                            "currency": "USD",
                            "value": 0.3226,
                            "price_type": "HOUR",
                        },
                    },
                ],
            },
        }
    )
    assert "Identifiqué **Oracle Integration 3 (OIC Gen3)**" in edition_choice_fallback
    assert "Standard BYOL (B89643): USD 0.1613 por hora" in edition_choice_fallback
    assert "Enterprise BYOL (B89644): USD 0.3226 por hora" in edition_choice_fallback
