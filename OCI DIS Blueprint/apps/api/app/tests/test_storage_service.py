"""Object Storage ownership and regression tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.services import storage_service


def test_object_storage_round_trip(isolated_object_storage: dict[str, bytes]) -> None:
    reference = storage_service.put_bytes(
        "imports/project-1/capture.xlsx",
        b"governed-workbook",
        content_type="application/octet-stream",
    )

    assert reference == "s3://oci-dis-files/imports/project-1/capture.xlsx"
    assert storage_service.read_bytes(reference) == b"governed-workbook"
    assert storage_service.exists(reference) is True
    assert storage_service.list_keys("imports/project-1") == [
        "imports/project-1/capture.xlsx"
    ]
    assert storage_service.delete_prefix("imports/project-1") == 1
    assert storage_service.exists(reference) is False
    assert isolated_object_storage == {}


def test_runtime_services_do_not_reintroduce_persistent_upload_directories() -> None:
    services_root = Path(__file__).resolve().parents[1] / "services"
    forbidden = ('Path("uploads', "Path('uploads", "/app/uploads", "generated-reports")
    offenders: list[str] = []
    for source in services_root.glob("*.py"):
        contents = source.read_text(encoding="utf-8")
        if any(token in contents for token in forbidden):
            offenders.append(source.name)

    assert offenders == []


def test_production_contract_has_no_shared_artifact_filesystem() -> None:
    repo_root = Path("/contracts")
    if not repo_root.is_dir():
        repo_root = Path(__file__).resolve().parents[4]
    forbidden = ("uploads_data", "/app/uploads", "generated-reports")
    contract_files = (
        repo_root / "docker-compose.yml",
        repo_root / "package.json",
        repo_root / "apps/api/Dockerfile",
        repo_root / "apps/api/production-entrypoint.sh",
    )
    offenders = [
        str(path.relative_to(repo_root))
        for path in contract_files
        if any(token in path.read_text(encoding="utf-8") for token in forbidden)
    ]

    assert offenders == []


@pytest.mark.asyncio
async def test_project_deletion_removes_owned_object_prefixes(
    api_client: AsyncClient,
) -> None:
    project = (
        await api_client.post(
            "/api/v1/projects/",
            json={
                "name": "Storage cleanup",
                "customer_name": "Storage Test Customer",
                "owner_id": "architect",
            },
        )
    ).json()
    project_id = project["id"]
    storage_service.put_bytes(f"imports/{project_id}/capture.xlsx", b"capture")
    storage_service.put_bytes(f"exports/{project_id}/files/export.xlsx", b"export")
    storage_service.put_bytes(f"synthetic/{project_id}/reports/report.json", b"{}")

    archive = await api_client.post(f"/api/v1/projects/{project_id}/archive")
    deleted = await api_client.delete(f"/api/v1/projects/{project_id}")

    assert archive.status_code == 200
    assert deleted.status_code == 200
    assert storage_service.list_keys(f"imports/{project_id}/") == []
    assert storage_service.list_keys(f"exports/{project_id}/") == []
    assert storage_service.list_keys(f"synthetic/{project_id}/") == []


@pytest.mark.asyncio
async def test_rejected_import_does_not_leave_an_orphan_object(
    api_client: AsyncClient,
) -> None:
    response = await api_client.post(
        "/api/v1/imports/missing-project",
        files={
            "file": (
                "capture.xlsx",
                b"not-reached-by-parser",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 404
    assert storage_service.list_keys("imports/missing-project/") == []
