"""Integration coverage for the admin synthetic-lab API surface."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import SyntheticGenerationJob
from app.models.project import Project, ProjectStatus
from app.routers import admin_synthetic


def _admin_headers() -> dict[str, str]:
    return {
        "X-Actor-Id": "admin-user",
        "X-Actor-Role": "Admin",
    }


def _missing_table_programming_error() -> ProgrammingError:
    return ProgrammingError(
        "SELECT count(*) FROM synthetic_generation_jobs",
        {},
        Exception('relation "synthetic_generation_jobs" does not exist'),
    )


def _missing_table_operational_error() -> OperationalError:
    return OperationalError(
        "INSERT INTO synthetic_generation_jobs DEFAULT VALUES",
        {},
        Exception("no such table: synthetic_generation_jobs"),
    )


@pytest.mark.asyncio
async def test_admin_synthetic_presets_include_smoke_variants(api_client: AsyncClient) -> None:
    """Verify both bounded smoke presets are exposed alongside the enterprise preset."""

    response = await api_client.get(
        "/api/v1/admin/synthetic/presets",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    presets = response.json()["presets"]
    codes = {preset["code"] for preset in presets}
    assert "enterprise-default" in codes
    assert "ephemeral-smoke" in codes
    assert "retained-smoke" in codes
    smoke_preset = next(preset for preset in presets if preset["code"] == "ephemeral-smoke")
    assert smoke_preset["cleanup_policy"] == "ephemeral_auto_cleanup"
    assert smoke_preset["target_catalog_size"] == 18
    retained_preset = next(preset for preset in presets if preset["code"] == "retained-smoke")
    assert retained_preset["cleanup_policy"] == "manual"
    assert retained_preset["target_catalog_size"] == 18


@pytest.mark.asyncio
async def test_admin_synthetic_job_create_list_and_get(api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify synthetic jobs can be created, listed, and fetched."""

    def fake_apply_async(*, args: list[object], task_id: str) -> SimpleNamespace:
        assert args == [task_id]
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        admin_synthetic.execute_synthetic_generation_job_task,
        "apply_async",
        fake_apply_async,
    )

    create_response = await api_client.post(
        "/api/v1/admin/synthetic/jobs",
        headers=_admin_headers(),
        json={
            "project_name": "Synthetic API Test",
            "target_catalog_size": 480,
            "import_target": 420,
            "manual_target": 60,
            "excluded_import_target": 36,
            "seed_value": 20260428,
        },
    )
    assert create_response.status_code == 202
    created = create_response.json()
    assert created["status"] == "pending"
    assert created["project_name"] == "Synthetic API Test"
    assert created["catalog_target"] == 480
    assert created["normalized_payload"]["import_target"] == 420
    job_id = created["id"]

    list_response = await api_client.get(
        "/api/v1/admin/synthetic/jobs",
        headers=_admin_headers(),
    )
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["total"] == 1
    assert listed["jobs"][0]["id"] == job_id

    get_response = await api_client.get(
        f"/api/v1/admin/synthetic/jobs/{job_id}",
        headers=_admin_headers(),
    )
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["id"] == job_id
    assert fetched["preset_code"] == "enterprise-default"


@pytest.mark.asyncio
async def test_admin_synthetic_smoke_job_uses_ephemeral_cleanup_defaults(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the smoke preset creates a job that auto-cleans after completion."""

    def fake_apply_async(*, args: list[object], task_id: str) -> SimpleNamespace:
        assert args == [task_id]
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        admin_synthetic.execute_synthetic_generation_job_task,
        "apply_async",
        fake_apply_async,
    )

    create_response = await api_client.post(
        "/api/v1/admin/synthetic/jobs",
        headers=_admin_headers(),
        json={
            "preset_code": "ephemeral-smoke",
        },
    )
    assert create_response.status_code == 202
    created = create_response.json()
    assert created["preset_code"] == "ephemeral-smoke"
    assert created["normalized_payload"]["cleanup_policy"] == "ephemeral_auto_cleanup"
    assert created["normalized_payload"]["target_catalog_size"] == 18
    assert created["normalized_payload"]["include_exports"] is False


@pytest.mark.asyncio
async def test_admin_synthetic_retained_smoke_job_uses_manual_cleanup_defaults(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify the retained smoke preset creates a bounded manual-cleanup job."""

    def fake_apply_async(*, args: list[object], task_id: str) -> SimpleNamespace:
        assert args == [task_id]
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        admin_synthetic.execute_synthetic_generation_job_task,
        "apply_async",
        fake_apply_async,
    )

    create_response = await api_client.post(
        "/api/v1/admin/synthetic/jobs",
        headers=_admin_headers(),
        json={
            "preset_code": "retained-smoke",
        },
    )
    assert create_response.status_code == 202
    created = create_response.json()
    assert created["preset_code"] == "retained-smoke"
    assert created["normalized_payload"]["cleanup_policy"] == "manual"
    assert created["normalized_payload"]["target_catalog_size"] == 18
    assert created["normalized_payload"]["include_exports"] is False


@pytest.mark.asyncio
async def test_admin_synthetic_retry_clones_failed_job(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify retry creates a new pending job from a failed one."""

    def fake_apply_async(*, args: list[object], task_id: str) -> SimpleNamespace:
        assert args == [task_id]
        return SimpleNamespace(id=task_id)

    monkeypatch.setattr(
        admin_synthetic.execute_synthetic_generation_job_task,
        "apply_async",
        fake_apply_async,
    )

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        failed_job = SyntheticGenerationJob(
            requested_by="seed-admin",
            status="failed",
            preset_code="enterprise-default",
            input_payload={"project_name": "Retry Source"},
            normalized_payload={
                "preset_code": "enterprise-default",
                "project_name": "Retry Source",
                "target_catalog_size": 480,
                "min_distinct_systems": 70,
                "import_target": 420,
                "manual_target": 60,
                "excluded_import_target": 36,
                "include_justifications": True,
                "include_exports": True,
                "include_design_warnings": True,
                "cleanup_policy": "manual",
                "seed_value": 20260416,
            },
            project_name="Retry Source",
            seed_value=20260416,
            catalog_target=480,
            manual_target=60,
            import_target=420,
            excluded_import_target=36,
            error_details={"detail": "Synthetic run failed."},
        )
        session.add(failed_job)
        await session.commit()
        source_job_id = failed_job.id

    retry_response = await api_client.post(
        f"/api/v1/admin/synthetic/jobs/{source_job_id}/retry",
        headers=_admin_headers(),
    )
    assert retry_response.status_code == 202
    retried = retry_response.json()
    assert retried["id"] != source_job_id
    assert retried["status"] == "pending"
    assert retried["normalized_payload"]["seed_value"] == 20260416


@pytest.mark.asyncio
async def test_admin_synthetic_cleanup_archives_and_deletes_project(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Verify cleanup removes a completed synthetic project's persisted records."""

    create_project_response = await api_client.post(
        "/api/v1/projects/",
        json={
            "name": "Synthetic Cleanup Project",
            "owner_id": "admin-user",
            "description": "Cleanup target",
        },
    )
    assert create_project_response.status_code == 201
    project = create_project_response.json()

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project_row = await session.get(Project, project["id"])
        assert project_row is not None
        project_row.status = ProjectStatus.ACTIVE
        project_row.project_metadata = {"synthetic": True}
        job = SyntheticGenerationJob(
            requested_by="admin-user",
            status="completed",
            preset_code="enterprise-default",
            input_payload={"project_name": project["name"]},
            normalized_payload={
                "preset_code": "enterprise-default",
                "project_name": project["name"],
                "target_catalog_size": 480,
                "min_distinct_systems": 70,
                "import_target": 420,
                "manual_target": 60,
                "excluded_import_target": 36,
                "include_justifications": True,
                "include_exports": True,
                "include_design_warnings": True,
                "cleanup_policy": "manual",
                "seed_value": 20260416,
            },
            project_id=project["id"],
            project_name=project["name"],
            seed_value=20260416,
            catalog_target=480,
            manual_target=60,
            import_target=420,
            excluded_import_target=36,
            result_summary={"project_id": project["id"]},
            validation_results={"catalog_count": 480},
            artifact_manifest={
                "workbook_path": "uploads/synthetic/missing.xlsx",
                "report_json_path": "generated-reports/missing.json",
                "report_markdown_path": "generated-reports/missing.md",
                "export_jobs": {},
            },
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    cleanup_response = await api_client.post(
        f"/api/v1/admin/synthetic/jobs/{job_id}/cleanup",
        headers=_admin_headers(),
    )
    assert cleanup_response.status_code == 200
    cleaned = cleanup_response.json()
    assert cleaned["status"] == "cleaned_up"
    assert "cleanup_removed_paths" in cleaned["result_summary"]

    get_project_response = await api_client.get(f"/api/v1/projects/{project['id']}")
    assert get_project_response.status_code == 404


@pytest.mark.asyncio
async def test_admin_synthetic_cleanup_failed_job_without_project(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """Verify failed synthetic jobs without persisted assets can still be cleaned up."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        failed_job = SyntheticGenerationJob(
            requested_by="seed-admin",
            status="failed",
            preset_code="ephemeral-smoke",
            input_payload={"preset_code": "ephemeral-smoke"},
            normalized_payload={
                "preset_code": "ephemeral-smoke",
                "project_name": "Retry Cleanup Source",
                "target_catalog_size": 18,
                "min_distinct_systems": 12,
                "import_target": 12,
                "manual_target": 6,
                "excluded_import_target": 2,
                "include_justifications": False,
                "include_exports": False,
                "include_design_warnings": True,
                "cleanup_policy": "ephemeral_auto_cleanup",
                "seed_value": 20260428,
            },
            project_name="Retry Cleanup Source",
            seed_value=20260428,
            catalog_target=18,
            manual_target=6,
            import_target=12,
            excluded_import_target=2,
            error_details={"detail": "Seeded failure for cleanup validation."},
        )
        session.add(failed_job)
        await session.commit()
        job_id = failed_job.id

    cleanup_response = await api_client.post(
        f"/api/v1/admin/synthetic/jobs/{job_id}/cleanup",
        headers=_admin_headers(),
    )

    assert cleanup_response.status_code == 200
    cleaned = cleanup_response.json()
    assert cleaned["id"] == job_id
    assert cleaned["status"] == "cleaned_up"
    assert cleaned["project_id"] is None
    assert cleaned["error_details"] == {"detail": "Seeded failure for cleanup validation."}
    assert cleaned["result_summary"]["cleanup_removed_paths"] == []
    assert "cleaned_up_at" in cleaned["result_summary"]


@pytest.mark.asyncio
async def test_admin_synthetic_requires_admin_role(api_client: AsyncClient) -> None:
    """Verify non-admin actors are rejected from the synthetic-lab routes."""

    response = await api_client.get(
        "/api/v1/admin/synthetic/jobs",
        headers={"X-Actor-Id": "viewer-user", "X-Actor-Role": "Viewer"},
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["detail"]["error_code"] == "ADMIN_ROLE_REQUIRED"


@pytest.mark.asyncio
async def test_admin_synthetic_list_jobs_reports_schema_not_ready(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify list jobs returns a structured 503 when the synthetic jobs table is missing."""

    async def fake_list_synthetic_jobs(*args: object, **kwargs: object) -> object:
        raise _missing_table_programming_error()

    monkeypatch.setattr(
        admin_synthetic.synthetic_service,
        "list_synthetic_jobs",
        fake_list_synthetic_jobs,
    )

    response = await api_client.get(
        "/api/v1/admin/synthetic/jobs",
        headers=_admin_headers(),
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["error_code"] == "SYNTHETIC_SCHEMA_NOT_READY"
    assert payload["detail"]["expected_migration"] == "20260428_0007"
    assert "alembic upgrade head" in payload["detail"]["recovery_hint"]


@pytest.mark.asyncio
async def test_admin_synthetic_create_job_reports_schema_not_ready(
    api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify create job returns a structured 503 when the synthetic jobs table is missing."""

    async def fake_create_synthetic_job(*args: object, **kwargs: object) -> object:
        raise _missing_table_operational_error()

    monkeypatch.setattr(
        admin_synthetic.synthetic_service,
        "create_synthetic_job",
        fake_create_synthetic_job,
    )

    response = await api_client.post(
        "/api/v1/admin/synthetic/jobs",
        headers=_admin_headers(),
        json={
            "project_name": "Synthetic API Test",
            "target_catalog_size": 480,
            "import_target": 420,
            "manual_target": 60,
            "excluded_import_target": 36,
            "seed_value": 20260428,
        },
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["error_code"] == "SYNTHETIC_SCHEMA_NOT_READY"
    assert payload["detail"]["table"] == "synthetic_generation_jobs"
