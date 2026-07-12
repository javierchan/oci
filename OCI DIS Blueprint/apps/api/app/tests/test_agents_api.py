"""API and service coverage for governed Docker agent executions."""

from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest
from httpx import AsyncClient, Request, Response
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import Project
from app.core.config import Settings
from app.routers import agents as agents_router
from app.services import agent_service
from app.services import genai_client


HEADERS = {"X-Actor-Id": "architect-user", "X-Actor-Role": "Admin"}


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
    assert completed.steps[0].tool_name == "load_architecture_review_evidence"

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
