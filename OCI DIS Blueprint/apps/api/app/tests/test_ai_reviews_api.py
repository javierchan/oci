"""API coverage for governed AI review jobs."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import AsyncClient, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.models import AiReviewBaseline, AssumptionSet, CatalogIntegration, Project, VolumetrySnapshot
from app.routers import ai_reviews
from app.schemas.ai_review import AiReviewGraphContext
from app.services import ai_review_service, genai_client
from app.services.genai_client import (
    _build_prompt,
    _normalize_summary,
    _resolved_oci_config,
    _response_text,
    _token_usage,
    provider_status_payload,
)


def test_provider_status_distinguishes_configured_verified_and_degraded(tmp_path: Path) -> None:
    """Configuration alone must not be presented as verified provider availability."""

    key_file = tmp_path / "api_key"
    key_file.write_text("sk-test-only", encoding="utf-8")
    settings = Settings(
        OCI_GENAI_API_KEY_FILE=str(key_file),
        OCI_GENAI_PROJECT_ID="ocid1.generativeaiproject.oc1.test",
    )

    configured = provider_status_payload(settings)
    verified = provider_status_payload(settings, last_provider_status="completed")
    degraded = provider_status_payload(settings, last_provider_status="failed")

    assert configured["mode"] == "llm_configured"
    assert verified["mode"] == "llm_available"
    assert degraded["mode"] == "llm_degraded"
    assert "latest synthesis failed" in str(degraded["status_message"])


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
        assumptions = AssumptionSet(
            id="assumptions-review-1",
            version="review-test-1.0.0",
            label="Review test assumptions",
            is_default=True,
            assumptions={},
            notes=None,
        )
        session.add_all([project, review_row, ok_row, snapshot, assumptions])
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

    def fake_apply_async(*, args: list[object], task_id: str, queue: str) -> SimpleNamespace:
        assert args == [task_id]
        assert queue == "agents"
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        ai_reviews.execute_agent_run_task,
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
    assert "planned-baseline-missing" in finding_ids
    assert result.drift.status == "no_baseline"
    assert result.groups[0].id == "critical_blockers"
    assert all(finding.evidence_ids for finding in result.findings)
    assert result.evidence[0].id == "EV-001"
    assert len(result.reviewer_personas) == 4
    assert result.decision_brief.signoff_status == "needs_review"
    assert result.decision_brief.primary_risk
    assert result.decision_brief.decision_points
    assert result.topology_insights
    assert result.topology_insights[0].insight_type == "system_hotspot"
    assert len(result.stress_scenarios) == 4
    assert result.stress_scenarios[-1].multiplier == 10.0
    assert result.remediation_plan
    assert result.remediation_plan[0].finding_ids
    assert result.action_workspace is not None
    assert result.action_workspace.context == "project"
    assert result.action_workspace.candidates
    assert result.action_workspace.candidates[0].implementation_steps
    assert result.action_workspace.candidates[0].validation_plan
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

    export_response = await api_client.get(f"/api/v1/ai-reviews/{job_id}/export")
    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("text/markdown")
    assert "# AI Review Brief - AI Review Fixture" in export_response.text


@pytest.mark.asyncio
async def test_integration_scoped_ai_review_requires_and_uses_integration_id(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify integration scope is validated and persisted."""

    project_id, integration_id = await _seed_review_fixture(test_engine)

    def fake_apply_async(*, args: list[object], task_id: str, queue: str) -> SimpleNamespace:
        assert queue == "agents"
        return SimpleNamespace(id=task_id, args=args)

    monkeypatch.setattr(
        ai_reviews.execute_agent_run_task,
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
    workspace = completed.result.recommendation_workspace
    assert workspace is not None
    assert workspace.integration_id == integration_id
    assert workspace.candidates
    assert len(workspace.candidates) <= 3
    assert workspace.recommended_candidate_id is not None
    assert all(candidate.canvas_state for candidate in workspace.candidates)
    assert all(
        candidate.cost_impact.status == "requires_draft_simulation"
        for candidate in workspace.candidates
    )
    candidate = next(
        item for item in workspace.candidates if item.id == workspace.recommended_candidate_id
    )

    select_response = await api_client.post(
        f"/api/v1/ai-reviews/{job_id}/recommendations/{candidate.id}/select-draft",
        headers=_admin_headers(),
        json={"note": "Preview governed route without saving it."},
    )
    assert select_response.status_code == 200
    selected = select_response.json()
    assert selected["candidate"]["id"] == candidate.id
    candidate_acceptance = next(
        item
        for item in selected["job"]["accepted_recommendations"]
        if item["recommendation_type"] == "candidate"
    )
    assert candidate_acceptance["finding_id"] == candidate.id

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        unchanged_row = await session.get(CatalogIntegration, integration_id)
        assert unchanged_row is not None
    assert unchanged_row.additional_tools_overlays is None
    assert unchanged_row.core_tools == "OCI Streaming"

    simulation_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}/integrations/{integration_id}/simulate-draft",
        headers=_admin_headers(),
        json={
            "core_tools": candidate.core_tools,
            "canvas_state": candidate.canvas_state,
        },
    )
    assert simulation_response.status_code == 200, simulation_response.text
    simulation = simulation_response.json()
    assert simulation["persisted"] is False
    assert simulation["integration_id"] == integration_id
    assert simulation["commercial_impact"]["status"] == "scenario_required"
    assert simulation["assumption_set_version"] == "review-test-1.0.0"

    async with session_factory() as session:
        snapshots = (
            await session.execute(
                select(VolumetrySnapshot).where(VolumetrySnapshot.project_id == project_id)
            )
        ).scalars().all()
        assert len(snapshots) == 1

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
    finding_acceptance = next(
        item
        for item in applied["job"]["accepted_recommendations"]
        if item["recommendation_type"] == "finding" and item["finding_id"] == finding.id
    )
    assert finding_acceptance["applied_patch"]["integration_id"] == integration_id
    assert "AI Review finding" in applied["integration"]["comments"]


@pytest.mark.asyncio
async def test_ai_review_roles_provider_status_quota_and_compare(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify production AI Review boundaries: roles, provider status, quota, and job comparison."""

    project_id, _ = await _seed_review_fixture(test_engine)

    provider_response = await api_client.get("/api/v1/ai-reviews/provider-status")
    assert provider_response.status_code == 200
    provider_payload = provider_response.json()
    assert provider_payload["provider"] == "oci_genai"
    assert provider_payload["model"] == "OpenAI gpt-oss-20b"
    assert provider_payload["transport"] == "oci-openai-responses-first-auto"
    assert provider_payload["transport_strategy"]["preferred"] == "responses"
    assert provider_payload["retry_policy"]["max_retries"] == 2
    assert provider_payload["safety"]["guardrails_enabled"] is True
    assert provider_payload["region"] == "us-chicago-1"
    assert isinstance(provider_payload["configured"], bool)
    assert provider_payload["quota"]["daily_job_limit"] >= 0
    assert "email addresses" in provider_payload["prompt_redaction_policy"]

    viewer_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}",
        headers={"X-Actor-Id": "viewer-user", "X-Actor-Role": "Viewer"},
        json={"include_llm": False},
    )
    assert viewer_response.status_code == 403

    def fake_apply_async(*, args: list[object], task_id: str, queue: str) -> SimpleNamespace:
        assert queue == "agents"
        return SimpleNamespace(id=task_id, args=args)

    monkeypatch.setattr(
        ai_reviews.execute_agent_run_task,
        "apply_async",
        fake_apply_async,
    )

    first_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}",
        headers=_admin_headers(),
        json={"include_llm": False},
    )
    assert first_response.status_code == 202
    first_job_id = first_response.json()["id"]

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            await ai_review_service.mark_ai_review_job_running(first_job_id, session)
        async with session.begin():
            await ai_review_service.run_ai_review_job(first_job_id, session)

    second_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}",
        headers={**_admin_headers(), "X-Actor-Id": "architect-user-2"},
        json={"include_llm": False},
    )
    assert second_response.status_code == 202
    second_job_id = second_response.json()["id"]
    async with session_factory() as session:
        async with session.begin():
            await ai_review_service.mark_ai_review_job_running(second_job_id, session)
        async with session.begin():
            await ai_review_service.run_ai_review_job(second_job_id, session)

    compare_response = await api_client.get(
        f"/api/v1/ai-reviews/projects/{project_id}/jobs/compare",
        params={"base_job_id": first_job_id, "target_job_id": second_job_id},
    )
    assert compare_response.status_code == 200
    compare_payload = compare_response.json()
    assert compare_payload["base_job_id"] == first_job_id
    assert compare_payload["target_job_id"] == second_job_id
    assert "summary" in compare_payload

    monkeypatch.setattr(
        ai_review_service,
        "get_settings",
        lambda: Settings(AI_REVIEW_DAILY_JOB_LIMIT=0),
    )
    quota_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}",
        headers={**_admin_headers(), "X-Actor-Id": "quota-user"},
        json={"include_llm": False},
    )
    assert quota_response.status_code == 429
    assert quota_response.json()["detail"]["error_code"] == "AI_REVIEW_DAILY_QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_ai_review_baseline_detects_planned_actual_drift(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Verify an approved planned baseline produces drift findings when current state changes."""

    project_id, integration_id = await _seed_review_fixture(test_engine)

    create_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}/baseline",
        headers=_admin_headers(),
        json={"scope": "project", "label": "Approved demo plan"},
    )
    assert create_response.status_code == 201
    baseline = create_response.json()
    assert baseline["label"] == "Approved demo plan"
    assert baseline["row_count"] == 2

    get_response = await api_client.get(f"/api/v1/ai-reviews/projects/{project_id}/baseline?scope=project")
    assert get_response.status_code == 200
    assert get_response.json()["baseline"]["id"] == baseline["id"]

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            row = await session.get(CatalogIntegration, integration_id)
            assert row is not None
            row.selected_pattern = "#01"
            row.core_tools = "OIC Gen3"
        review = await ai_review_service.build_review_result(
            project_id=project_id,
            scope="project",
            integration_id=None,
            include_llm=False,
            graph_context=None,
            reviewer_personas=["architect"],
            db=session,
        )

    assert review.drift.status == "material_drift"
    assert review.drift.baseline is not None
    assert review.drift.baseline.id == baseline["id"]
    assert review.drift.item_count >= 2
    assert any(item.field == "selected_pattern" for item in review.drift.items)
    assert any(finding.id == "planned-actual-drift" for finding in review.findings)


@pytest.mark.asyncio
async def test_canvas_storage_version_change_does_not_create_architecture_drift(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Compare governed overlays instead of treating Canvas V3-to-V4 layout JSON as drift."""

    project_id, integration_id = await _seed_review_fixture(test_engine)
    create_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}/baseline",
        headers=_admin_headers(),
        json={"scope": "project", "label": "Approved canvas plan"},
    )
    assert create_response.status_code == 201
    baseline_id = create_response.json()["id"]

    v3_canvas = json.dumps(
        {
            "v": 3,
            "nodes": [],
            "edges": [],
            "coreToolKeys": ["OCI Streaming"],
            "overlayKeys": ["OCI Events"],
        }
    )
    v4_canvas = json.dumps(
        {
            "v": 4,
            "nodes": [],
            "edges": [],
            "coreToolKeys": ["OCI Streaming"],
            "overlayKeys": ["OCI Events"],
            "endpointPositions": {
                "source-system": {"x": 40, "y": 120},
                "destination-system": {"x": 900, "y": 120},
            },
        }
    )

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            baseline = await session.get(AiReviewBaseline, baseline_id)
            row = await session.get(CatalogIntegration, integration_id)
            assert baseline is not None
            assert row is not None
            payload = dict(baseline.baseline_payload)
            rows = [dict(item) for item in payload["rows"]]
            rows[0]["additional_tools_overlays"] = v3_canvas
            payload["rows"] = rows
            baseline.baseline_payload = payload
            row.additional_tools_overlays = v4_canvas

        review = await ai_review_service.build_review_result(
            project_id=project_id,
            scope="project",
            integration_id=None,
            include_llm=False,
            graph_context=None,
            reviewer_personas=["architect"],
            db=session,
        )

    assert all(item.field != "additional_tools_overlays" for item in review.drift.items)


@pytest.mark.asyncio
async def test_integration_ai_review_baseline_requires_scope_and_detects_drift(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Verify integration-level planned baselines are scoped to one catalog row."""

    project_id, integration_id = await _seed_review_fixture(test_engine)

    missing_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}/baseline",
        headers=_admin_headers(),
        json={"scope": "integration"},
    )
    assert missing_response.status_code == 422

    create_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}/baseline",
        headers=_admin_headers(),
        json={"scope": "integration", "integration_id": integration_id, "label": "Approved integration plan"},
    )
    assert create_response.status_code == 201
    baseline = create_response.json()
    assert baseline["scope"] == "integration"
    assert baseline["integration_id"] == integration_id
    assert baseline["row_count"] == 1

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        async with session.begin():
            row = await session.get(CatalogIntegration, integration_id)
            assert row is not None
            row.source_system = "CRM-CHANGED"
        review = await ai_review_service.build_review_result(
            project_id=project_id,
            scope="integration",
            integration_id=integration_id,
            include_llm=False,
            graph_context=None,
            reviewer_personas=["architect"],
            db=session,
        )

    assert review.drift.status == "material_drift"
    assert review.drift.item_count == 1
    assert review.drift.items[0].field == "source_system"
    assert any(finding.id == "planned-actual-drift" for finding in review.findings)


@pytest.mark.asyncio
async def test_ai_review_baseline_history_lists_active_then_archived(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Verify baseline governance keeps replacement history visible."""

    project_id, _ = await _seed_review_fixture(test_engine)

    first_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}/baseline",
        headers=_admin_headers(),
        json={"label": "Initial approved baseline", "note": "Architecture board approval."},
    )
    assert first_response.status_code == 201

    second_response = await api_client.post(
        f"/api/v1/ai-reviews/projects/{project_id}/baseline",
        headers=_admin_headers(),
        json={"label": "Updated approved baseline", "note": "Replacement after design review."},
    )
    assert second_response.status_code == 201

    list_response = await api_client.get(f"/api/v1/ai-reviews/projects/{project_id}/baselines")
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total"] == 2
    assert payload["baselines"][0]["label"] == "Updated approved baseline"
    assert payload["baselines"][0]["is_active"] is True
    assert payload["baselines"][1]["label"] == "Initial approved baseline"
    assert payload["baselines"][1]["is_active"] is False


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
    assert review.topology_insights
    assert review.topology_insights[0].system_name in {"CRM", "ERP"}
    assert review.stress_scenarios[0].confidence in {"medium", "low"}
    assert review.action_workspace is not None
    assert review.action_workspace.context == "topology"
    assert review.action_workspace.candidates[0].what_to_change


def test_oci_chat_completions_payload_extracts_text_and_usage() -> None:
    payload = {
        "choices": [{"message": {"role": "assistant", "content": "Executive summary."}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 32},
    }

    input_tokens, output_tokens = _token_usage(payload)

    assert _response_text(payload) == "Executive summary."
    assert input_tokens == 120
    assert output_tokens == 32


def test_oci_summary_normalization_removes_markdown_emphasis() -> None:
    assert _normalize_summary("**Decision:** confirm `HA/DR` topology.") == "Decision: confirm HA/DR topology."


def test_oci_runtime_config_requires_mounted_api_key_file(tmp_path) -> None:
    api_key_path = tmp_path / "api_key"
    settings = Settings(
        OCI_GENAI_API_KEY_FILE=str(api_key_path),
    )

    assert _resolved_oci_config(settings).configured is False

    api_key_path.write_text("sk-test-secret", encoding="utf-8")

    runtime_config = _resolved_oci_config(settings)
    assert runtime_config.configured is True
    assert runtime_config.model_name == "OpenAI gpt-oss-20b"
    assert runtime_config.model_id == "openai.gpt-oss-20b"
    assert runtime_config.base_url.endswith("/openai/v1")


@pytest.mark.asyncio
async def test_oci_genai_uses_bearer_key_chat_completions_and_canonical_model(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_key_path = tmp_path / "api_key"
    api_key_path.write_text("sk-test-secret", encoding="utf-8")
    captured: dict[str, object] = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs: object) -> None:
            captured["client_kwargs"] = kwargs

        async def __aenter__(self) -> "FakeAsyncClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> Response:
            captured["url"] = url
            captured.update(kwargs)
            return Response(
                200,
                headers={"opc-request-id": "oci-request-123"},
                json={
                    "choices": [{"message": {"role": "assistant", "content": "Architecture scope confirmed."}}],
                    "usage": {"prompt_tokens": 20, "completion_tokens": 4},
                },
                request=Request("POST", url),
            )

    monkeypatch.setattr(genai_client.httpx, "AsyncClient", FakeAsyncClient)
    settings = Settings(
        OCI_GENAI_API_KEY_FILE=str(api_key_path),
        OCI_GENAI_PROJECT_ID="ocid1.generativeaiproject.oc1.test",
        OCI_GENAI_TRANSPORT_MODE="chat_completions",
        OCI_GENAI_GUARDRAILS_ENABLED=False,
    )

    result = await genai_client.synthesize_governed_summary(
        settings=settings,
        system_instruction="Use only evidence.",
        evidence={"scope": "architecture"},
    )

    assert result.status == "completed"
    assert result.opc_request_id == "oci-request-123"
    assert captured["url"] == (
        "https://inference.generativeai.us-chicago-1.oci.oraclecloud.com/"
        "openai/v1/chat/completions"
    )
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer sk-test-secret"
    assert headers["OpenAI-Project"] == "ocid1.generativeaiproject.oc1.test"
    request_json = captured["json"]
    assert isinstance(request_json, dict)
    assert request_json["model"] == settings.OCI_GENAI_MODEL_ID
    assert len(str(request_json["safety_identifier"])) == 64
    assert "system" not in str(request_json["safety_identifier"])


def test_oci_prompt_redacts_sensitive_values() -> None:
    prompt = _build_prompt(
        project_name="Secret Fixture",
        readiness_score=80,
        readiness_label="Demo-ready with caveats",
        deterministic_summary="Owner jane.doe@example.com uses api_key=abcdef1234567890abcdef1234567890.",
        metrics=[],
        findings=[],
        evidence_pack=["Bearer abcdef1234567890abcdef1234567890"],
    )

    payload = prompt[1]["content"]

    assert "jane.doe@example.com" not in payload
    assert "abcdef1234567890abcdef1234567890" not in payload
    assert "[REDACTED]" in payload
