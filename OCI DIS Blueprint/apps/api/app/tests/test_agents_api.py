"""API and service coverage for governed Docker agent executions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from pathlib import Path

import pytest
from httpx import AsyncClient, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import (
    AgentApproval,
    AgentArtifact,
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AuditEvent,
    Project,
    SupportConversation,
    SupportMessage,
)
from app.core.config import Settings
from app.routers import agents as agents_router
from app.services import agent_service
from app.services import genai_client
from scripts import prune_agent_history


HEADERS = {"X-Actor-Id": "architect-user", "X-Actor-Role": "Admin"}


def test_production_api_prunes_agent_history_before_uvicorn_start() -> None:
    """Keep the import-safe module invocation in the production entrypoint contract."""

    repo_root = Path("/contracts")
    if not repo_root.is_dir():
        repo_root = Path(__file__).resolve().parents[4]
    entrypoint = (repo_root / "apps/api/production-entrypoint.sh").read_text(encoding="utf-8")

    assert 'if [ "${1:-}" = "uvicorn" ]' in entrypoint
    assert "su-exec app python -m scripts.prune_agent_history" in entrypoint


@pytest.mark.asyncio
async def test_agent_history_pruning_defers_until_schema_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh deployment can start before Alembic creates agent_runs."""

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        def begin(self) -> "FakeSession":
            return self

        async def scalar(self, _: object) -> None:
            return None

    async def unexpected_prune(_: object) -> int:
        raise AssertionError("Retention must not query an unavailable table")

    monkeypatch.setattr(prune_agent_history, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(prune_agent_history, "prune_agent_run_history", unexpected_prune)

    assert await prune_agent_history.prune_history() is None


@pytest.mark.asyncio
async def test_agent_history_pruning_runs_after_schema_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The normal retention policy still runs after migrations are installed."""

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        def begin(self) -> "FakeSession":
            return self

        async def scalar(self, _: object) -> str:
            return "agent_runs"

    async def fake_prune(session: object) -> int:
        assert isinstance(session, FakeSession)
        return 3

    monkeypatch.setattr(prune_agent_history, "AsyncSessionLocal", FakeSession)
    monkeypatch.setattr(prune_agent_history, "prune_agent_run_history", fake_prune)

    assert await prune_agent_history.prune_history() == 3


def test_guardrail_refusal_does_not_degrade_provider_health() -> None:
    """A successful safety control is not reported as OCI provider downtime."""

    assert agent_service.observed_provider_status(
        {"provider_status": "failed", "guardrails_status": "blocked"}
    ) is None
    assert agent_service.observed_provider_status(
        {"provider_status": "failed", "guardrails_status": "failed"}
    ) == "failed"
    assert agent_service.observed_provider_status(
        {"provider_status": "completed", "guardrails_status": "completed"}
    ) == "completed"
    assert agent_service.observed_provider_transport(
        {"provider_status": "completed", "provider_transport": "chat_completions"}
    ) == "chat_completions"
    assert agent_service.observed_provider_transport(
        {"provider_status": "completed", "provider_transport": "responses"}
    ) == "responses"
    assert agent_service.observed_provider_transport(
        {"provider_status": "skipped", "provider_transport": None}
    ) is None


async def _seed_project(test_engine: AsyncEngine) -> str:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(
            id="project-agent-1",
            name="Agent Runtime Fixture",
            owner_id="architect-user",
            status="active",
            description=None,
            project_metadata=None,
        )
        session.add(project)
        await session.commit()
    return project.id


@pytest.mark.asyncio
async def test_agent_catalog_create_execute_and_read(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every registered agent is visible and a deterministic run reaches terminal state."""

    project_id = await _seed_project(test_engine)

    def fake_apply_async(*, args: list[str], task_id: str, queue: str) -> SimpleNamespace:
        assert args == [task_id]
        assert queue == "agents"
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(agents_router.execute_agent_run_task, "apply_async", fake_apply_async)
    catalog_response = await api_client.get("/api/v1/agents", headers=HEADERS)
    assert catalog_response.status_code == 200
    assert {item["type"] for item in catalog_response.json()} == {
        "architecture_review",
        "service_verification",
        "import_quality",
        "integration_design",
        "topology_investigation",
        "bom_scenario",
        "support_assistant",
    }
    provider_response = await api_client.get("/api/v1/agents/provider-status", headers=HEADERS)
    assert provider_response.status_code == 200
    assert provider_response.json()["runtime"] == "docker_celery_agents_queue"
    assert provider_response.json()["project_configured"] is False
    metrics_response = await api_client.get("/api/v1/agents/provider-metrics", headers=HEADERS)
    assert metrics_response.status_code == 200
    assert metrics_response.json()["source"] in {"redis", "process"}
    assert metrics_response.json()["counters"]["retries_total"] >= 0
    viewer_metrics_response = await api_client.get(
        "/api/v1/agents/provider-metrics",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert viewer_metrics_response.status_code == 403

    create_response = await api_client.post(
        "/api/v1/agents/runs",
        headers=HEADERS,
        json={
            "agent_type": "architecture_review",
            "project_id": project_id,
            "include_provider": False,
        },
    )
    assert create_response.status_code == 202
    run_id = create_response.json()["id"]

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            await agent_service.mark_agent_run_running(run_id, session)
        async with session.begin():
            completed = await agent_service.run_agent(run_id, session)

    assert completed.status == "completed"
    assert completed.result is not None
    assert completed.result["authority"] == "governed_deterministic_evidence"
    assert completed.result["provider_status"] == "skipped"
    assert completed.step_count == 4
    assert [step.step_type for step in completed.steps] == ["evidence", "decision", "provider", "proposal"]
    assert completed.steps[0].tool_name == "load_architecture_review_evidence"
    assert completed.steps[0].output_summary == "Governed evidence collected by load_architecture_review_evidence."
    assert completed.steps[2].output_summary == (
        "Provider synthesis was unavailable; governed deterministic evidence was used."
    )
    assert "we need" not in (completed.steps[2].output_summary or "").lower()
    assert isinstance(completed.result["decision_workspace"], dict)
    assert completed.result["decision_workspace"].get("alternatives")

    read_response = await api_client.get(f"/api/v1/agents/runs/{run_id}", headers=HEADERS)
    assert read_response.status_code == 200
    assert read_response.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_pending_agent_can_be_cancelled(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancellation is persisted before a queued worker starts."""

    project_id = await _seed_project(test_engine)
    monkeypatch.setattr(
        agents_router.execute_agent_run_task,
        "apply_async",
        lambda **kwargs: SimpleNamespace(id=kwargs["task_id"]),
    )
    created = await api_client.post(
        "/api/v1/agents/runs",
        headers=HEADERS,
        json={"agent_type": "architecture_review", "project_id": project_id, "include_provider": False},
    )
    response = await api_client.post(
        f"/api/v1/agents/runs/{created.json()['id']}/cancel",
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["cancel_requested"] is True


@pytest.mark.asyncio
async def test_approved_agent_proposal_executes_once_with_post_validation(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Approved drafts use deterministic execution and retain the outcome evidence."""

    project_id = await _seed_project(test_engine)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    started = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
    async with session_factory() as session:
        run = AgentRun(
            id="agent-approved-execution",
            agent_type="architecture_review",
            definition_version="2.0.0",
            project_id=project_id,
            requested_by="architect-user",
            status=AgentRunStatus.COMPLETED,
            context_payload={},
            result_payload={"authority": "governed_deterministic_evidence"},
            started_at=started,
            finished_at=started + timedelta(seconds=4),
        )
        approval = AgentApproval(
            id="agent-approved-proposal",
            run_id=run.id,
            action_type="create_agent_action_draft",
            status="approved",
            proposed_payload={
                "alternative_id": "resolve-qa",
                "project_id": project_id,
                "candidate": {"title": "Resolve QA blockers", "action_href": f"/projects/{project_id}/catalog"},
            },
            reviewed_by="architect-user",
            reviewed_at=started,
        )
        session.add_all([run, approval])
        await session.commit()

    response = await api_client.post(
        f"/api/v1/agents/runs/{run.id}/approvals/{approval.id}/execute",
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    execution = response.json()["approvals"][0]
    assert execution["execution_status"] == "completed"
    assert execution["execution_result"]["outcome"] == "governed_draft_created"
    assert execution["execution_result"]["validation"] == "draft_persisted_no_authoritative_data_changed"

    repeated = await api_client.post(
        f"/api/v1/agents/runs/{run.id}/approvals/{approval.id}/execute",
        headers=HEADERS,
    )
    assert repeated.status_code == 200
    assert repeated.json()["approvals"][0]["execution_result"] == execution["execution_result"]

    async with session_factory() as session:
        artifacts = list(
            (
                await session.scalars(
                    select(AgentArtifact)
                    .where(AgentArtifact.run_id == run.id)
                    .order_by(AgentArtifact.created_at)
                )
            ).all()
        )
        assert [artifact.artifact_type for artifact in artifacts] == ["decision_draft", "post_validation"]


@pytest.mark.asyncio
async def test_agent_value_metrics_report_observed_quality_and_human_follow_up(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Value telemetry uses retained execution facts rather than invented time savings."""

    project_id = await _seed_project(test_engine)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    started = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    async with session_factory() as session:
        first = AgentRun(
            id="agent-value-first",
            agent_type="architecture_review",
            definition_version="1.1.0",
            project_id=project_id,
            requested_by="architect-user",
            status=AgentRunStatus.COMPLETED,
            context_payload={},
            result_payload={
                "provider_status": "completed",
                "brief": {"next_actions": ["Resolve the governed finding."]},
                "output_quality": {
                    "grounded": True,
                    "fallback_used": False,
                    "evidence_completeness_pct": 100,
                },
            },
            started_at=started,
            finished_at=started + timedelta(seconds=10),
            created_at=started,
            updated_at=started,
        )
        follow_up = AgentRun(
            id="agent-value-follow-up",
            agent_type="architecture_review",
            definition_version="1.1.0",
            project_id=project_id,
            requested_by="architect-user",
            status=AgentRunStatus.COMPLETED,
            context_payload={},
            result_payload={
                "provider_status": "completed",
                "brief": {"next_actions": ["Confirm closure."]},
                "output_quality": {
                    "grounded": False,
                    "fallback_used": True,
                    "evidence_completeness_pct": 70,
                },
            },
            started_at=started + timedelta(minutes=2),
            finished_at=started + timedelta(minutes=2, seconds=20),
            created_at=started + timedelta(minutes=2),
            updated_at=started + timedelta(minutes=2),
        )
        session.add_all([first, follow_up])
        await session.flush()
        session.add(
            AgentApproval(
                id="agent-value-approval",
                run_id=first.id,
                action_type="review_action",
                status="approved",
                proposed_payload={"candidate_id": "candidate-1"},
                reviewed_by="architect-user",
                reviewed_at=started + timedelta(minutes=1),
            )
        )
        await session.commit()

    response = await api_client.get("/api/v1/agents/value-metrics", headers=HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert payload["retained_runs"] == 2
    assert payload["quality_evaluated_runs"] == 2
    assert payload["grounded_output_rate_pct"] == 50.0
    assert payload["high_evidence_completeness_rate_pct"] == 50.0
    assert payload["acceptance_rate_pct"] == 100.0
    assert payload["approval_follow_up_rate_pct"] == 100.0
    assert payload["proposals_created"] == 1
    assert payload["proposals_executed"] == 0
    assert payload["post_validations_completed"] == 0
    assert payload["execution_rate_pct"] == 0.0
    assert payload["median_execution_seconds"] == 15.0

    viewer_response = await api_client.get(
        "/api/v1/agents/value-metrics",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert viewer_response.status_code == 403


@pytest.mark.asyncio
async def test_agent_history_retains_latest_50_terminal_runs_and_preserves_active_work(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Retention removes complete execution evidence without deleting active work or support text."""

    project_id = await _seed_project(test_engine)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    expired_run_ids = ["agent-retention-000", "agent-retention-001"]
    active_run_id = "agent-retention-active"
    message_id = "support-message-retention"

    async with session_factory() as session:
        conversation = SupportConversation(
            id="support-conversation-retention",
            session_id="12345678-1234-4234-8234-123456789012",
            actor_id="architect-user",
            title="Retention fixture",
            status="active",
        )
        session.add(conversation)
        for index in range(52):
            run_id = f"agent-retention-{index:03d}"
            session.add(
                AgentRun(
                    id=run_id,
                    agent_type="architecture_review",
                    definition_version="1.0.0",
                    project_id=project_id,
                    requested_by="architect-user",
                    status=AgentRunStatus.COMPLETED,
                    context_payload={},
                    result_payload={"summary": f"Run {index}"},
                    step_count=1,
                    max_steps=4,
                    created_at=base_time + timedelta(minutes=index),
                    updated_at=base_time + timedelta(minutes=index),
                    finished_at=base_time + timedelta(minutes=index),
                )
            )
        session.add(
            AgentRun(
                id=active_run_id,
                agent_type="architecture_review",
                definition_version="1.0.0",
                project_id=project_id,
                requested_by="architect-user",
                status=AgentRunStatus.RUNNING,
                context_payload={},
                step_count=0,
                max_steps=4,
                created_at=base_time - timedelta(days=1),
                updated_at=base_time - timedelta(days=1),
                started_at=base_time - timedelta(days=1),
            )
        )
        await session.flush()
        session.add_all(
            [
                AgentStep(
                    id="agent-step-retention",
                    run_id=expired_run_ids[0],
                    sequence=1,
                    step_type="tool",
                    status="completed",
                ),
                AgentArtifact(
                    id="agent-artifact-retention",
                    run_id=expired_run_ids[0],
                    artifact_type="governed_evidence",
                    label="Expired evidence",
                    payload={"status": "expired"},
                ),
                AgentApproval(
                    id="agent-approval-retention",
                    run_id=expired_run_ids[0],
                    action_type="apply_patch",
                    status="pending",
                    proposed_payload={"status": "expired"},
                ),
                SupportMessage(
                    id=message_id,
                    conversation_id=conversation.id,
                    role="assistant",
                    content="This support answer must survive run retention.",
                    status="completed",
                    agent_run_id=expired_run_ids[0],
                    context_snapshot={},
                    citations=[],
                ),
                AuditEvent(
                    id="audit-event-retention",
                    project_id=project_id,
                    actor_id="architect-user",
                    event_type="agent_run_completed",
                    entity_type="agent_run",
                    entity_id=expired_run_ids[0],
                    correlation_id=expired_run_ids[0],
                ),
            ]
        )
        await session.commit()

        async with session.begin():
            deleted = await agent_service.prune_agent_run_history(session)

        assert deleted == 2
        terminal_count = await session.scalar(
            select(func.count())
            .select_from(AgentRun)
            .where(AgentRun.status.in_(agent_service.TERMINAL_STATUSES))
        )
        assert terminal_count == agent_service.AGENT_RUN_HISTORY_LIMIT
        assert await session.get(AgentRun, active_run_id) is not None
        assert await session.get(AgentRun, expired_run_ids[0]) is None
        assert await session.get(AgentRun, expired_run_ids[1]) is None
        assert await session.get(AgentStep, "agent-step-retention") is None
        assert await session.get(AgentArtifact, "agent-artifact-retention") is None
        assert await session.get(AgentApproval, "agent-approval-retention") is None
        assert await session.get(AuditEvent, "audit-event-retention") is None
        support_message = await session.get(SupportMessage, message_id)
        assert support_message is not None
        assert support_message.content == "This support answer must survive run retention."
        assert support_message.agent_run_id is None

    oversized_response = await api_client.get("/api/v1/agents/runs?limit=51", headers=HEADERS)
    assert oversized_response.status_code == 422
    history_response = await api_client.get("/api/v1/agents/runs?limit=50", headers=HEADERS)
    assert history_response.status_code == 200
    retained_runs = history_response.json()["runs"]
    assert len(retained_runs) == 50
    assert {
        run["result"]["summary"]
        for run in retained_runs
        if run["result"] is not None
    } == {
        "Legacy execution predates the governed output contract; inspect its audit evidence if needed."
    }


@pytest.mark.asyncio
async def test_oci_tool_loop_sends_project_header_and_returns_tool_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OCI function calling uses the project OCID and a bounded two-request loop."""

    key_path = tmp_path / "api_key"
    key_path.write_text("sk-test-value", encoding="utf-8")
    calls: list[dict[str, object]] = []

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]) -> Response:
            calls.append({"url": url, "headers": headers, "json": json})
            request = Request("POST", url)
            if len(calls) == 1:
                return Response(
                    200,
                    request=request,
                    headers={"opc-request-id": "first-request"},
                    json={
                        "id": "resp-tool",
                        "choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1", "type": "function", "function": {"name": "get_evidence", "arguments": "{}"}}]}}],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 4},
                    },
                )
            return Response(
                200,
                request=request,
                headers={"opc-request-id": "second-request"},
                json={
                    "id": "resp-final",
                    "choices": [{"message": {"role": "assistant", "content": "Governed evidence E-1 is ready."}}],
                    "usage": {"prompt_tokens": 8, "completion_tokens": 6},
                },
            )

    monkeypatch.setattr(genai_client.httpx, "AsyncClient", FakeClient)

    async def executor(_: dict[str, object]) -> dict[str, object]:
        return {"evidence_id": "E-1", "status": "ready"}

    result = await genai_client.run_governed_tool_agent(
        settings=Settings(
            OCI_GENAI_API_KEY_FILE=str(key_path),
            OCI_GENAI_PROJECT_ID="ocid1.generativeaiproject.oc1.test",
            OCI_GENAI_BASE_URL="https://example.test/openai/v1",
            OCI_GENAI_TRANSPORT_MODE="chat_completions",
            OCI_GENAI_GUARDRAILS_ENABLED=False,
        ),
        instruction="Use governed evidence only.",
        user_message="Inspect evidence.",
        tool_name="get_evidence",
        tool_description="Get evidence.",
        tool_parameters={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        tool_executor=executor,
    )

    assert result.status == "completed"
    assert result.tool_output == {"evidence_id": "E-1", "status": "ready"}
    assert result.summary == "Governed evidence E-1 is ready."
    assert result.input_tokens == 18
    assert result.output_tokens == 10
    assert calls[0]["headers"]["OpenAI-Project"] == "ocid1.generativeaiproject.oc1.test"  # type: ignore[index]
    first_json = calls[0]["json"]
    assert isinstance(first_json, dict)
    assert len(str(first_json["safety_identifier"])) == 64
    assert len(calls) == 2
