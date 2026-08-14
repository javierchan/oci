"""Admin user-management and editable local-username contracts."""

from __future__ import annotations

from httpx import AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import Project
from app.models.project import ProjectStatus
from app.services.auth_service import upsert_local_user


pytestmark = pytest.mark.asyncio


async def _admin_login(client: AsyncClient, engine: AsyncEngine) -> str:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        async with db.begin():
            admin = await upsert_local_user(
                username="root-admin",
                email="root@example.com",
                display_name="Root Admin",
                role="Admin",
                password="root administrator password",
                grant_existing_projects=True,
                db=db,
            )
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "root-admin", "password": "root administrator password"},
    )
    assert response.status_code == 200
    return admin.id


async def test_admin_creates_edits_and_reassigns_local_user(
    auth_api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        async with db.begin():
            project = Project(
                name="Assigned Project",
                customer_name="Customer",
                owner_id="bootstrap",
                status=ProjectStatus.ACTIVE,
            )
            db.add(project)
            await db.flush()
            project_id = project.id

    await _admin_login(auth_api_client, test_engine)
    created = await auth_api_client.post(
        "/api/v1/admin/users",
        headers={"Origin": "http://localhost:3000"},
        json={
            "username": "javier",
            "email": "javier@example.com",
            "display_name": "Javier Example",
            "role": "Analyst",
            "password": "initial user password",
            "memberships": [{"project_id": project_id, "project_role": "Contributor"}],
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    assert created.json()["username"] == "javier"
    assert created.json()["memberships"][0]["project_id"] == project_id

    renamed = await auth_api_client.patch(
        f"/api/v1/admin/users/{user_id}",
        headers={"Origin": "http://localhost:3000"},
        json={"username": "javierchan", "role": "Architect"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["username"] == "javierchan"
    assert renamed.json()["role"] == "Architect"

    old_login = await auth_api_client.post(
        "/api/v1/auth/login",
        json={"username": "javier", "password": "initial user password"},
    )
    assert old_login.status_code == 401
    new_login = await auth_api_client.post(
        "/api/v1/auth/login",
        json={"username": "JAVIERCHAN", "password": "initial user password"},
    )
    assert new_login.status_code == 200
    visible = await auth_api_client.get("/api/v1/projects/")
    assert [item["id"] for item in visible.json()["projects"]] == [project_id]

    forbidden = await auth_api_client.get("/api/v1/admin/users")
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["error_code"] == "ADMIN_ROLE_REQUIRED"


async def test_admin_cannot_deactivate_own_active_account(
    auth_api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    admin_id = await _admin_login(auth_api_client, test_engine)
    response = await auth_api_client.patch(
        f"/api/v1/admin/users/{admin_id}",
        headers={"Origin": "http://localhost:3000"},
        json={"is_active": False},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "SELF_ADMIN_LOCKOUT"
