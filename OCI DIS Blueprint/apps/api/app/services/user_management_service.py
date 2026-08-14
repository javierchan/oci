"""Admin-managed App users, local usernames, roles, and project memberships."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import cast

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ApiToken,
    AppUser,
    AuthIdentity,
    AuthSession,
    LocalCredential,
    Project,
    ProjectMembership,
)
from app.schemas.user_management import (
    AppRole,
    ManagedUserCreateRequest,
    ManagedUserListResponse,
    ManagedUserPatchRequest,
    ManagedUserResponse,
    ProjectRole,
    UserMembershipReplaceRequest,
    UserProjectMembershipInput,
    UserProjectMembershipResponse,
)
from app.services import audit_service, auth_service, concurrency
from app.services.authz import normalize_role


def _conflict(detail: str, error_code: str) -> HTTPException:
    return HTTPException(status_code=409, detail={"detail": detail, "error_code": error_code})


async def _load_user(
    user_id: str,
    db: AsyncSession,
    *,
    for_update: bool = False,
) -> AppUser:
    query = select(AppUser).where(AppUser.id == user_id)
    if for_update:
        query = query.with_for_update()
    user = await db.scalar(query)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "User not found", "error_code": "USER_NOT_FOUND"},
        )
    return user


async def _local_identity(user_id: str, db: AsyncSession) -> AuthIdentity | None:
    return await db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.user_id == user_id,
            AuthIdentity.provider == auth_service.LOCAL_PROVIDER,
        )
    )


async def _serialize_users(users: list[AppUser], db: AsyncSession) -> list[ManagedUserResponse]:
    if not users:
        return []
    user_ids = [user.id for user in users]
    identities = list(
        (
            await db.scalars(
                select(AuthIdentity)
                .where(AuthIdentity.user_id.in_(user_ids))
                .order_by(AuthIdentity.provider, AuthIdentity.subject)
            )
        ).all()
    )
    membership_rows = list(
        (
            await db.execute(
                select(ProjectMembership, Project.name)
                .join(Project, Project.id == ProjectMembership.project_id)
                .where(ProjectMembership.user_id.in_(user_ids))
                .order_by(Project.name, ProjectMembership.project_id)
            )
        ).all()
    )
    identities_by_user: dict[str, list[AuthIdentity]] = defaultdict(list)
    memberships_by_user: dict[str, list[UserProjectMembershipResponse]] = defaultdict(list)
    for identity in identities:
        identities_by_user[identity.user_id].append(identity)
    for membership, project_name in membership_rows:
        memberships_by_user[membership.user_id].append(
            UserProjectMembershipResponse(
                project_id=membership.project_id,
                project_name=project_name,
                project_role=cast(ProjectRole, membership.project_role),
            )
        )
    result: list[ManagedUserResponse] = []
    for user in users:
        user_identities = identities_by_user[user.id]
        local = next(
            (identity for identity in user_identities if identity.provider == auth_service.LOCAL_PROVIDER),
            None,
        )
        result.append(
            ManagedUserResponse(
                id=user.id,
                username=local.subject if local else None,
                email=user.email,
                display_name=user.display_name,
                role=cast(AppRole, normalize_role(user.role) or "Viewer"),
                is_active=user.is_active,
                providers=cast(list, [identity.provider for identity in user_identities]),
                memberships=memberships_by_user[user.id],
                last_authenticated_at=user.last_authenticated_at,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )
    return result


async def list_users(db: AsyncSession, *, include_inactive: bool) -> ManagedUserListResponse:
    query = select(AppUser).order_by(AppUser.display_name, AppUser.email)
    if not include_inactive:
        query = query.where(AppUser.is_active.is_(True))
    users = list((await db.scalars(query)).all())
    return ManagedUserListResponse(users=await _serialize_users(users, db), total=len(users))


async def get_user(user_id: str, db: AsyncSession) -> ManagedUserResponse:
    user = await _load_user(user_id, db)
    return (await _serialize_users([user], db))[0]


async def _assert_username_available(
    username: str,
    db: AsyncSession,
    *,
    except_identity_id: str | None = None,
) -> None:
    existing = await db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.provider == auth_service.LOCAL_PROVIDER,
            AuthIdentity.subject == auth_service.normalize_username(username),
        )
    )
    if existing is not None and existing.id != except_identity_id:
        raise _conflict("Username is already in use", "USERNAME_ALREADY_EXISTS")


async def _assert_email_available(
    email: str,
    db: AsyncSession,
    *,
    except_user_id: str | None = None,
) -> None:
    existing = await db.scalar(select(AppUser).where(AppUser.email == email.strip().casefold()))
    if existing is not None and existing.id != except_user_id:
        raise _conflict("Email is already in use", "EMAIL_ALREADY_EXISTS")


async def _replace_memberships(
    user: AppUser,
    requested: list[UserProjectMembershipInput],
    actor_id: str,
    db: AsyncSession,
) -> None:
    requested_by_id = {item.project_id: item for item in requested}
    if len(requested_by_id) != len(requested):
        raise HTTPException(
            status_code=422,
            detail={"detail": "Project memberships must be unique", "error_code": "DUPLICATE_PROJECT_MEMBERSHIP"},
        )
    projects = list(
        (
            await db.scalars(
                select(Project).where(
                    (Project.id.in_(set(requested_by_id))) | (Project.owner_id == user.id)
                )
            )
        ).all()
    )
    found = {project.id for project in projects}
    missing = set(requested_by_id) - found
    if missing:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"},
        )
    await db.execute(delete(ProjectMembership).where(ProjectMembership.user_id == user.id))
    for project in projects:
        role = "Owner" if project.owner_id == user.id else requested_by_id[project.id].project_role
        db.add(
            ProjectMembership(
                project_id=project.id,
                user_id=user.id,
                project_role=role,
                granted_by=actor_id,
            )
        )
    await db.flush()


async def create_user(
    body: ManagedUserCreateRequest,
    actor_id: str,
    db: AsyncSession,
) -> ManagedUserResponse:
    await _assert_username_available(body.username, db)
    await _assert_email_available(body.email, db)
    user = await auth_service.upsert_local_user(
        username=body.username,
        email=body.email,
        display_name=body.display_name,
        role=body.role,
        password=body.password,
        grant_existing_projects=False,
        db=db,
    )
    await _replace_memberships(user, body.memberships, actor_id, db)
    await audit_service.emit(
        event_type="app_user_created",
        entity_type="app_user",
        entity_id=user.id,
        actor_id=actor_id,
        old_value=None,
        new_value={
            "username": body.username,
            "email": body.email,
            "role": body.role,
            "project_count": len(body.memberships),
        },
        project_id=None,
        db=db,
    )
    return await get_user(user.id, db)


async def _ensure_admin_continuity(
    user: AppUser,
    *,
    next_role: str,
    next_active: bool,
    actor_id: str,
    db: AsyncSession,
) -> None:
    if user.id == actor_id and (next_role != "Admin" or not next_active):
        raise _conflict("An administrator cannot deactivate or demote the active account", "SELF_ADMIN_LOCKOUT")
    if user.role == "Admin" and user.is_active and (next_role != "Admin" or not next_active):
        active_admins = int(
            await db.scalar(
                select(func.count()).select_from(AppUser).where(
                    AppUser.role == "Admin", AppUser.is_active.is_(True)
                )
            )
            or 0
        )
        if active_admins <= 1:
            raise _conflict("At least one active administrator is required", "LAST_ADMIN_REQUIRED")


async def update_user(
    user_id: str,
    body: ManagedUserPatchRequest,
    actor_id: str,
    db: AsyncSession,
) -> ManagedUserResponse:
    user = await _load_user(user_id, db, for_update=True)
    concurrency.assert_current_version(
        current_updated_at=user.updated_at,
        expected_updated_at=body.expected_updated_at,
        entity_type="App user",
        entity_id=user.id,
    )
    identity = await _local_identity(user.id, db)
    fields = body.model_fields_set - {"expected_updated_at"}
    next_role = body.role if "role" in fields and body.role is not None else user.role
    next_active = body.is_active if "is_active" in fields and body.is_active is not None else user.is_active
    await _ensure_admin_continuity(
        user,
        next_role=next_role,
        next_active=next_active,
        actor_id=actor_id,
        db=db,
    )
    old_value: dict[str, object] = {
        "username": identity.subject if identity else None,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
    }
    if "username" in fields:
        if identity is None:
            raise _conflict("This user has no local username", "LOCAL_IDENTITY_MISSING")
        assert body.username is not None
        await _assert_username_available(body.username, db, except_identity_id=identity.id)
        identity.subject = auth_service.normalize_username(body.username)
    if "email" in fields:
        assert body.email is not None
        await _assert_email_available(body.email, db, except_user_id=user.id)
        user.email = body.email
    if "display_name" in fields:
        assert body.display_name is not None
        user.display_name = body.display_name
    if "role" in fields:
        user.role = next_role
    if "is_active" in fields:
        user.is_active = next_active
        if identity is not None:
            identity.is_active = next_active
    credentials_revoked = not next_active
    if "reset_password" in fields:
        if identity is None:
            raise _conflict("This user has no local credential", "LOCAL_CREDENTIAL_MISSING")
        assert body.reset_password is not None
        credential = await db.get(LocalCredential, identity.id)
        if credential is None:
            raise _conflict("This user has no local credential", "LOCAL_CREDENTIAL_MISSING")
        credential.password_hash = await auth_service.hash_password(body.reset_password)
        credential.password_changed_at = datetime.now(UTC)
        credential.failed_attempts = 0
        credential.locked_until = None
        credentials_revoked = True
    if credentials_revoked:
        now = datetime.now(UTC)
        await db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.execute(
            update(ApiToken)
            .where(ApiToken.user_id == user.id, ApiToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
    user.updated_at = datetime.now(UTC)
    await db.flush()
    new_value: dict[str, object] = {
        "username": identity.subject if identity else None,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "credentials_revoked": credentials_revoked,
    }
    await audit_service.emit(
        event_type="app_user_updated",
        entity_type="app_user",
        entity_id=user.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=new_value,
        project_id=None,
        db=db,
    )
    return await get_user(user.id, db)


async def replace_user_memberships(
    user_id: str,
    body: UserMembershipReplaceRequest,
    actor_id: str,
    db: AsyncSession,
) -> ManagedUserResponse:
    user = await _load_user(user_id, db, for_update=True)
    concurrency.assert_current_version(
        current_updated_at=user.updated_at,
        expected_updated_at=body.expected_updated_at,
        entity_type="App user",
        entity_id=user.id,
    )
    previous_count = int(
        await db.scalar(
            select(func.count()).select_from(ProjectMembership).where(
                ProjectMembership.user_id == user.id
            )
        )
        or 0
    )
    await _replace_memberships(user, body.memberships, actor_id, db)
    user.updated_at = datetime.now(UTC)
    await db.flush()
    current = await get_user(user.id, db)
    await audit_service.emit(
        event_type="project_memberships_replaced",
        entity_type="app_user",
        entity_id=user.id,
        actor_id=actor_id,
        old_value={"project_count": previous_count},
        new_value={"project_count": len(current.memberships)},
        project_id=None,
        db=db,
    )
    return current
