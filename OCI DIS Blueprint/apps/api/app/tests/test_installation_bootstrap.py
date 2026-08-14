"""First-install identity bootstrap tests."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import ApiToken, AppUser, AuditEvent, Project, ProjectMembership
from scripts.bootstrap_installation import reserve_secret_output
from app.services.auth_service import authenticate_local
from app.services.installation_service import (
    InstallationAlreadyInitializedError,
    bootstrap_installation_admin,
)


def test_secret_output_is_exclusive_and_mode_0600(tmp_path) -> None:
    output_path = tmp_path / "nested" / "initial-access.json"
    handle = reserve_secret_output(output_path)
    handle.write("{}")
    handle.close()

    assert output_path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        reserve_secret_output(output_path)


@pytest.mark.asyncio
async def test_bootstrap_creates_one_admin_token_membership_and_audit(
    test_engine: AsyncEngine,
) -> None:
    sessions = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with sessions() as db:
        async with db.begin():
            db.add(Project(name="Bootstrap Project", owner_id="legacy-owner"))
    async with sessions() as db:
        async with db.begin():
            result = await bootstrap_installation_admin(
                username="Initial.Admin",
                email="initial.admin@example.com",
                display_name="Initial Admin",
                password="bootstrap-password-1234",
                grant_existing_projects=True,
                create_initial_api_token=True,
                api_token_scopes=["projects:read", "integrations:read"],
                api_token_days=14,
                db=db,
            )

        assert result.created is True
        assert result.username == "initial.admin"
        assert result.api_token is not None
        assert result.api_token.startswith("odis_api_")
        assert await db.scalar(select(func.count()).select_from(AppUser)) == 1
        assert await db.scalar(select(func.count()).select_from(ProjectMembership)) == 1
        token = await db.scalar(select(ApiToken))
        assert token is not None
        assert token.scopes == ["projects:read", "integrations:read"]
        event = await db.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "installation_identity_bootstrapped"
            )
        )
        assert event is not None
        assert event.new_value["initial_api_token_created"] is True
        assert "password" not in str(event.new_value).casefold()


@pytest.mark.asyncio
async def test_bootstrap_retry_is_noop_and_does_not_rotate_password(
    test_engine: AsyncEngine,
) -> None:
    sessions = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with sessions() as db:
        async with db.begin():
            first = await bootstrap_installation_admin(
                username="admin",
                email="admin@example.com",
                display_name="Admin",
                password="first-bootstrap-password",
                grant_existing_projects=True,
                create_initial_api_token=False,
                api_token_scopes=["projects:read"],
                api_token_days=30,
                db=db,
            )
    async with sessions() as db:
        async with db.begin():
            retry = await bootstrap_installation_admin(
                username="ADMIN",
                email="changed@example.com",
                display_name="Changed",
                password="second-bootstrap-password",
                grant_existing_projects=True,
                create_initial_api_token=True,
                api_token_scopes=["projects:read"],
                api_token_days=30,
                db=db,
            )
        assert retry.created is False
        assert retry.user_id == first.user_id
        assert retry.api_token is None
        assert await db.scalar(select(func.count()).select_from(ApiToken)) == 0
        await authenticate_local("admin", "first-bootstrap-password", db)


@pytest.mark.asyncio
async def test_bootstrap_fails_closed_when_another_user_exists(
    test_engine: AsyncEngine,
) -> None:
    sessions = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with sessions() as db:
        async with db.begin():
            await bootstrap_installation_admin(
                username="admin",
                email="admin@example.com",
                display_name="Admin",
                password="bootstrap-password-1234",
                grant_existing_projects=False,
                create_initial_api_token=False,
                api_token_scopes=["projects:read"],
                api_token_days=30,
                db=db,
            )
    async with sessions() as db:
        with pytest.raises(InstallationAlreadyInitializedError):
            async with db.begin():
                await bootstrap_installation_admin(
                    username="second-admin",
                    email="second@example.com",
                    display_name="Second Admin",
                    password="bootstrap-password-5678",
                    grant_existing_projects=False,
                    create_initial_api_token=False,
                    api_token_scopes=["projects:read"],
                    api_token_days=30,
                    db=db,
                )
