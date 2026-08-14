"""Idempotent first-install identity bootstrap for local hosts and OCI Jobs."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppUser, AuthIdentity
from app.schemas.auth import ApiTokenCreateRequest
from app.services import audit_service
from app.services.auth_service import (
    LOCAL_PROVIDER,
    AuthPrincipal,
    create_api_token,
    normalize_username,
    upsert_local_user,
)


class InstallationAlreadyInitializedError(RuntimeError):
    """Raised when bootstrap would create a second, unexpected first administrator."""


@dataclass(frozen=True, slots=True)
class InstallationBootstrapResult:
    """Safe bootstrap outcome plus one-time secrets returned only to the CLI."""

    created: bool
    user_id: str
    username: str
    api_token: str | None = None
    api_token_id: str | None = None


async def bootstrap_installation_admin(
    *,
    username: str,
    email: str,
    display_name: str,
    password: str,
    grant_existing_projects: bool,
    create_initial_api_token: bool,
    api_token_scopes: list[str],
    api_token_days: int,
    db: AsyncSession,
) -> InstallationBootstrapResult:
    """Create exactly one first Admin without rotating credentials on retries.

    A retry for the same local subject is a successful no-op. If another user
    already exists, bootstrap fails closed and directs operators to the governed
    User Management or local-user CLI instead of silently creating an Admin.
    """

    subject = normalize_username(username)
    identity = await db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.provider == LOCAL_PROVIDER,
            AuthIdentity.subject == subject,
        )
    )
    user_count = int(await db.scalar(select(func.count()).select_from(AppUser)) or 0)
    if identity is not None:
        user = await db.get(AppUser, identity.user_id)
        if user is None:
            raise RuntimeError("local bootstrap identity references a missing user")
        return InstallationBootstrapResult(
            created=False,
            user_id=user.id,
            username=subject,
        )
    if user_count:
        raise InstallationAlreadyInitializedError(
            "installation already contains users; use User Management or "
            "scripts/manage_local_user.py for additional accounts"
        )

    user = await upsert_local_user(
        username=subject,
        email=email,
        display_name=display_name,
        role="Admin",
        password=password,
        grant_existing_projects=grant_existing_projects,
        db=db,
    )
    raw_token: str | None = None
    token_id: str | None = None
    if create_initial_api_token:
        token = await create_api_token(
            AuthPrincipal(
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
                role="Admin",
                authentication_method="session",
                credential_id="installation-bootstrap",
                expires_at=None,
            ),
            ApiTokenCreateRequest(
                name="Initial deployment automation",
                expires_in_days=api_token_days,
                project_ids=None,
                scopes=api_token_scopes,
            ),
            db,
        )
        raw_token = token.token
        token_id = token.id

    await audit_service.emit(
        event_type="installation_identity_bootstrapped",
        entity_type="app_user",
        entity_id=user.id,
        actor_id=user.id,
        old_value=None,
        new_value={
            "provider": LOCAL_PROVIDER,
            "role": "Admin",
            "existing_projects_granted": grant_existing_projects,
            "initial_api_token_created": create_initial_api_token,
            "initial_api_token_scopes": api_token_scopes if create_initial_api_token else [],
        },
        project_id=None,
        db=db,
    )
    return InstallationBootstrapResult(
        created=True,
        user_id=user.id,
        username=subject,
        api_token=raw_token,
        api_token_id=token_id,
    )
