"""End-to-end authentication, token, and project-isolation contracts."""

from __future__ import annotations

from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import Project, ProjectMembership
from app.models.identity import LocalCredential
from app.models.project import ProjectStatus
from app.services.auth_service import upsert_local_user


pytestmark = pytest.mark.asyncio


async def _provision_user(
    engine: AsyncEngine,
    *,
    username: str,
    email: str,
    password: str,
    grant_existing_projects: bool = False,
    role: str = "Admin",
) -> str:
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        async with db.begin():
            user = await upsert_local_user(
                username=username,
                email=email,
                display_name=username.title(),
                role=role,
                password=password,
                grant_existing_projects=grant_existing_projects,
                db=db,
            )
        return user.id


async def _grant_project_role(
    engine: AsyncEngine,
    *,
    user_id: str,
    project_id: str,
    project_role: str,
) -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        async with db.begin():
            db.add(
                ProjectMembership(
                    project_id=project_id,
                    user_id=user_id,
                    project_role=project_role,
                    granted_by=user_id,
                )
            )


async def test_local_session_ignores_spoofed_actor_and_owns_new_project(
    auth_api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    user_id = await _provision_user(
        test_engine,
        username="architect",
        email="architect@example.com",
        password="correct horse battery staple",
    )

    bad_login = await auth_api_client.post(
        "/api/v1/auth/login",
        json={"username": "architect", "password": "wrong password"},
    )
    assert bad_login.status_code == 401

    login = await auth_api_client.post(
        "/api/v1/auth/login",
        json={"username": "ARCHITECT", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["id"] == user_id
    assert login.json()["user"]["providers"] == ["local"]
    assert login.cookies.get("oci_dis_session")

    created = await auth_api_client.post(
        "/api/v1/projects/",
        headers={
            "Origin": "http://localhost:3000",
            "X-Actor-Id": "spoofed-user",
            "X-Actor-Role": "Viewer",
        },
        json={
            "name": "Private Architecture",
            "customer_name": "Example Customer",
            "owner_id": "spoofed-user",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["owner_id"] == user_id

    project_id = created.json()["id"]
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        membership = await db.scalar(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project_id,
                ProjectMembership.user_id == user_id,
            )
        )
        assert membership is not None
        assert membership.project_role == "Owner"

    dashboard = await auth_api_client.get(f"/api/v1/dashboard/{project_id}/snapshots")
    assert dashboard.status_code == 200, dashboard.text
    assert dashboard.json()["snapshots"] == []


async def test_project_membership_returns_404_across_users(
    auth_api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        async with db.begin():
            hidden = Project(
                name="Hidden Project",
                customer_name="Private Customer",
                owner_id="someone-else",
                status=ProjectStatus.ACTIVE,
            )
            db.add(hidden)
            await db.flush()
            hidden_id = hidden.id

    await _provision_user(
        test_engine,
        username="viewer",
        email="viewer@example.com",
        password="a sufficiently long password",
    )
    login = await auth_api_client.post(
        "/api/v1/auth/login",
        json={"username": "viewer", "password": "a sufficiently long password"},
    )
    assert login.status_code == 200
    listing = await auth_api_client.get("/api/v1/projects/")
    assert listing.status_code == 200
    assert listing.json()["projects"] == []
    hidden_response = await auth_api_client.get(f"/api/v1/projects/{hidden_id}")
    assert hidden_response.status_code == 404


async def test_viewer_and_project_viewer_cannot_mutate_authorized_project(
    auth_api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        async with db.begin():
            project = Project(
                name="Read-only Project",
                customer_name="Protected Customer",
                owner_id="owner-id",
                status=ProjectStatus.ACTIVE,
            )
            db.add(project)
            await db.flush()
            project_id = project.id

    viewer_id = await _provision_user(
        test_engine,
        username="read-only-user",
        email="read-only@example.com",
        password="a read only user password",
        role="Viewer",
    )
    await _grant_project_role(
        test_engine,
        user_id=viewer_id,
        project_id=project_id,
        project_role="Viewer",
    )
    login = await auth_api_client.post(
        "/api/v1/auth/login",
        json={"username": "read-only-user", "password": "a read only user password"},
    )
    assert login.status_code == 200
    assert (await auth_api_client.get(f"/api/v1/projects/{project_id}")).status_code == 200

    update = await auth_api_client.patch(
        f"/api/v1/projects/{project_id}",
        headers={"Origin": "http://localhost:3000"},
        json={"description": "Forbidden change"},
    )
    assert update.status_code == 403
    assert update.json()["detail"]["error_code"] == "PROJECT_OWNER_REQUIRED"

    capture = await auth_api_client.post(
        f"/api/v1/catalog/{project_id}",
        headers={"Origin": "http://localhost:3000"},
        json={},
    )
    assert capture.status_code == 403
    assert capture.json()["detail"]["error_code"] == "ACTION_ROLE_REQUIRED"


async def test_architect_with_viewer_membership_is_still_read_only(
    auth_api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        async with db.begin():
            project = Project(
                name="Viewer Membership Project",
                customer_name="Protected Customer",
                owner_id="owner-id",
                status=ProjectStatus.ACTIVE,
            )
            db.add(project)
            await db.flush()
            project_id = project.id

    architect_id = await _provision_user(
        test_engine,
        username="restricted-architect",
        email="restricted-architect@example.com",
        password="a restricted architect password",
        role="Architect",
    )
    await _grant_project_role(
        test_engine,
        user_id=architect_id,
        project_id=project_id,
        project_role="Viewer",
    )
    login = await auth_api_client.post(
        "/api/v1/auth/login",
        json={
            "username": "restricted-architect",
            "password": "a restricted architect password",
        },
    )
    assert login.status_code == 200

    update = await auth_api_client.patch(
        f"/api/v1/catalog/{project_id}/missing-integration",
        headers={"Origin": "http://localhost:3000"},
        json={"comments": "This must be rejected before resource lookup"},
    )
    assert update.status_code == 403
    assert update.json()["detail"]["error_code"] == "PROJECT_ROLE_REQUIRED"


async def test_failed_login_lockout_is_committed(
    auth_api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _provision_user(
        test_engine,
        username="locked-user",
        email="locked@example.com",
        password="correct but eventually locked password",
    )

    for _ in range(5):
        response = await auth_api_client.post(
            "/api/v1/auth/login",
            json={"username": "locked-user", "password": "incorrect password"},
        )
        assert response.status_code == 401

    correct_but_locked = await auth_api_client.post(
        "/api/v1/auth/login",
        json={
            "username": "locked-user",
            "password": "correct but eventually locked password",
        },
    )
    assert correct_but_locked.status_code == 401

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        credential = await db.scalar(select(LocalCredential))
        assert credential is not None
        assert credential.locked_until is not None


async def test_external_api_token_is_read_only_and_project_scoped(
    auth_api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        async with db.begin():
            first = Project(
                name="First",
                customer_name="Customer",
                owner_id="bootstrap",
                status=ProjectStatus.ACTIVE,
            )
            second = Project(
                name="Second",
                customer_name="Customer",
                owner_id="bootstrap",
                status=ProjectStatus.ACTIVE,
            )
            db.add_all([first, second])
            await db.flush()
            first_id, second_id = first.id, second.id

    user_id = await _provision_user(
        test_engine,
        username="codex",
        email="codex@example.com",
        password="codex local access password",
        grant_existing_projects=True,
    )
    login = await auth_api_client.post(
        "/api/v1/auth/login",
        json={"username": "codex", "password": "codex local access password"},
    )
    assert login.status_code == 200

    created = await auth_api_client.post(
        "/api/v1/auth/api-tokens",
        headers={"Origin": "http://localhost:3000"},
        json={
            "name": "External QA",
            "expires_in_days": 30,
            "project_ids": [first_id],
            "scopes": ["projects:read"],
        },
    )
    assert created.status_code == 201, created.text
    raw_token = created.json()["token"]
    assert raw_token.startswith("odis_api_")
    assert raw_token not in str(created.json()["token_prefix"])

    bearer = {"Authorization": f"Bearer {raw_token}"}
    visible = await auth_api_client.get("/api/v1/projects/", headers=bearer)
    assert visible.status_code == 200
    assert [item["id"] for item in visible.json()["projects"]] == [first_id]
    assert (
        await auth_api_client.get(f"/api/v1/projects/{first_id}", headers=bearer)
    ).status_code == 200
    assert (
        await auth_api_client.get(f"/api/v1/projects/{second_id}", headers=bearer)
    ).status_code == 404
    denied = await auth_api_client.post(
        "/api/v1/projects/",
        headers=bearer,
        json={"name": "Forbidden", "customer_name": "Customer"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["error_code"] == "API_TOKEN_READ_ONLY"

    missing_scope = await auth_api_client.get(
        f"/api/v1/catalog/{first_id}",
        headers=bearer,
    )
    assert missing_scope.status_code == 403
    assert missing_scope.json()["detail"]["error_code"] == "API_TOKEN_SCOPE_REQUIRED"

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        member_count = len(
            (
                await db.scalars(
                    select(ProjectMembership).where(ProjectMembership.user_id == user_id)
                )
            ).all()
        )
        assert member_count == 2
