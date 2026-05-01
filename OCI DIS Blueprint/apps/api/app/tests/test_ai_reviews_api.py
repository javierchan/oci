"""API coverage for governed AI review jobs."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import CatalogIntegration, Project, VolumetrySnapshot
from app.routers import ai_reviews
from app.schemas.ai_review import AiReviewGraphContext
from app.services import ai_review_service
from app.services.llm_review_client import _resolved_oca_config, _response_payload, _response_text


def _admin_headers() -> dict[str, str]:
    return {
        "X-Actor-Id": "architect-user",
        "X-Actor-Role": "Admin",
    }


async def _seed_review_fixture(test_engine: AsyncEngine) -> tuple[str, str]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(
            id="project-review-1",
            name="AI Review Fixture",
            owner_id="architect",
            status="active",
            description=None,
            project_metadata=None,
        )
        review_row = CatalogIntegration(
            id="integration-review-1",
            project_id=project.id,
            seq_number=1,
            interface_name="Large payload webhook",
            interface_id="INT-001",
            source_system="CRM",
            destination_system="ERP",
            trigger_type="REST Trigger",
            payload_per_execution_kb=None,
            selected_pattern="#17",
            core_tools="OCI Streaming",
            qa_status="REVISAR",
            qa_reasons=["PATTERN_REFERENCE_ONLY"],
        )
        ok_row = CatalogIntegration(
            id="integration-ok-1",
            project_id=project.id,
            seq_number=2,
            interface_name="Order sync",
            interface_id="INT-002",
            source_system="POS",
            destination_system="OMS",
            trigger_type="Scheduled",
            payload_per_execution_kb=25.0,
            selected_pattern="#01",
            core_tools="OIC Gen3",
            qa_status="OK",
            qa_reasons=[],
        )
        snapshot = VolumetrySnapshot(
            id="snapshot-review-1",
            project_id=project.id,
            assumption_set_version="1.0.0",
            triggered_by="test",
            row_results={
                review_row.id: {
                    "design_constraint_warnings": [
                        "Route connected, but review is still required.",
                    ],
                },
                ok_row.id: {
                    "design_constraint_warnings": [
                        "QA green but service limit still requires review.",
                    ],
                },
            },
            consolidated={
                "oic": {},
                "data_integration": {},
                "functions": {},
                "streaming": {},
                "queue": {},
            },
            snapshot_metadata={"integration_count": 2},
        )
        session.add_all([project, review_row, ok_row, snapshot])
        await session.commit()
        return project.id, review_row.id


@pytest.mark.asyncio
async def test_project_ai_review_job_create_run_get_and_accept(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify review jobs are persisted, executable, inspectable, and auditable."""

    project_id, _ = await _seed_review_fixture(test_engine)

    def fake_apply_async(*, args: list[object], task_id: str) -> SimpleNamespace:
        assert args == [task_id]
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        ai_reviews.execute_ai_review_job_task,
        "apply_async",
        fake_apply_async,
    )

    create_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}",
        headers=_admin_headers(),
        json={"include_llm": False},
    )
    assert create_response.status_code == 202
    created = create_response.json()
    assert created["status"] == "pending"
    assert created["scope"] == "project"
    assert created["result"] is None
    job_id = created["id"]

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            await ai_review_service.mark_ai_review_job_running(job_id, session)
        async with session.begin():
            completed = await ai_review_service.run_ai_review_job(job_id, session)

    result = completed.result
    assert result is not None
    finding_ids = {finding.id for finding in result.findings}
    assert result.project_id == project_id
    assert result.readiness_label == "Needs architecture review"
    assert "qa-review-open" in finding_ids
    assert "reference-only-patterns" in finding_ids
    assert "payload-coverage-gap" in finding_ids
    assert "design-constraints-open" in finding_ids
    assert "ten-x-stress-review" in finding_ids
    assert "red-team-qa-ok-with-design-warnings" in finding_ids
    assert result.groups[0].id == "critical_blockers"
    assert all(finding.evidence_ids for finding in result.findings)
    assert result.evidence[0].id == "EV-001"
    assert len(result.reviewer_personas) == 4
    assert result.llm_status == "skipped"

    get_response = await api_client.get(f"/api/v1/ai-reviews/{job_id}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["status"] == "completed"
    assert fetched["result"]["evidence"][0]["id"] == "EV-001"

    list_response = await api_client.get(f"/api/v1/ai-reviews/projects/{project_id}/jobs")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] == 1
    assert listed["jobs"][0]["id"] == job_id

    accept_response = await api_client.post(
        f"/api/v1/ai-reviews/{job_id}/findings/qa-review-open/accept",
        headers=_admin_headers(),
        json={"note": "Accepted for architecture triage."},
    )
    assert accept_response.status_code == 200
    accepted = accept_response.json()["accepted_recommendations"]
    assert accepted[0]["finding_id"] == "qa-review-open"
    assert accepted[0]["accepted_by"] == "architect-user"


@pytest.mark.asyncio
async def test_integration_scoped_ai_review_requires_and_uses_integration_id(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify integration scope is validated and persisted."""

    project_id, integration_id = await _seed_review_fixture(test_engine)

    def fake_apply_async(*, args: list[object], task_id: str) -> SimpleNamespace:
        return SimpleNamespace(id=task_id, args=args)

    monkeypatch.setattr(
        ai_reviews.execute_ai_review_job_task,
        "apply_async",
        fake_apply_async,
    )

    missing_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}",
        headers=_admin_headers(),
        json={"scope": "integration", "include_llm": False},
    )
    assert missing_response.status_code == 422

    create_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}",
        headers=_admin_headers(),
        json={"scope": "integration", "integration_id": integration_id, "include_llm": False},
    )
    assert create_response.status_code == 202
    created = create_response.json()
    assert created["scope"] == "integration"
    assert created["integration_id"] == integration_id

    job_id = created["id"]
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            await ai_review_service.mark_ai_review_job_running(job_id, session)
        async with session.begin():
            completed = await ai_review_service.run_ai_review_job(job_id, session)

    assert completed.result is not None
    finding = next(item for item in completed.result.findings if item.suggested_patch is not None)
    assert finding.suggested_patch is not None
    assert finding.suggested_patch.integration_id == integration_id
    assert finding.suggested_patch.patch["comments"]

    apply_response = await api_client.post(
        f"/api/v1/ai-reviews/{job_id}/findings/{finding.id}/apply-patch",
        headers=_admin_headers(),
        json={"note": "Apply governed note."},
    )
    assert apply_response.status_code == 200
    applied = apply_response.json()
    assert applied["job"]["accepted_recommendations"][0]["finding_id"] == finding.id
    assert applied["job"]["accepted_recommendations"][0]["applied_patch"]["integration_id"] == integration_id
    assert "AI Review finding" in applied["integration"]["comments"]


@pytest.mark.asyncio
async def test_graph_context_scopes_project_ai_review_evidence(
    test_engine: AsyncEngine,
) -> None:
    """Verify graph node context narrows a project review to the selected system cluster."""

    project_id, _ = await _seed_review_fixture(test_engine)

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        review = await ai_review_service.build_review_result(
            project_id=project_id,
            scope="project",
            integration_id=None,
            include_llm=False,
            graph_context=AiReviewGraphContext(type="node", label="CRM"),
            reviewer_personas=["architect"],
            db=session,
        )

    assert review.graph_context is not None
    assert review.graph_context.type == "node"
    assert review.metrics[0].label == "Catalog rows"
    assert review.metrics[0].value == "1"
    assert any("Graph node scope: CRM" in item for item in review.evidence_pack)


def test_oca_response_payload_parses_server_sent_event_frame() -> None:
    response = Response(
        200,
        text=(
            'data: {"output":[{"type":"message","content":[{"type":"output_text",'
            '"text":"Executive summary."}]}]}\n\n'
        ),
    )

    payload = _response_payload(response)

    assert _response_text(payload) == "Executive summary."


def test_oca_runtime_config_uses_codex_config_and_auth(tmp_path) -> None:
    config_path = tmp_path / "config.toml"
    auth_path = tmp_path / "auth.json"
    config_path.write_text(
        "\n".join(
            [
                "[model_providers.oca]",
                'base_url = "https://example.test/litellm"',
                'wire_api = "responses"',
                'model = "oca/gpt-5.5"',
                'http_headers = { client = "codex-cli", client-version = "0" }',
            ]
        ),
        encoding="utf-8",
    )
    auth_path.write_text('{"OPENAI_API_KEY":"codex-test-key"}', encoding="utf-8")
    settings = Settings(
        OCA_API_KEY="",
        OCA_BASE_URL="https://fallback.test",
        OCA_MODEL="fallback-model",
        OCA_CONFIG_PATH=str(config_path),
        OCA_AUTH_JSON_PATH=str(auth_path),
    )

    runtime_config = _resolved_oca_config(settings)

    assert runtime_config.api_key == "codex-test-key"
    assert runtime_config.base_url == "https://example.test/litellm"
    assert runtime_config.model == "oca/gpt-5.5"
    assert runtime_config.headers["client"] == "codex-cli"
    assert runtime_config.headers["client-version"] == "0"
