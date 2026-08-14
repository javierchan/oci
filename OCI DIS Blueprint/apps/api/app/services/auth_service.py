"""Local authentication, session, token, and project-membership services."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from fastapi import HTTPException
from pwdlib import PasswordHash
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api_token_scopes import (
    ALL_API_TOKEN_SCOPES,
    API_TOKEN_SCOPE_CATALOG,
    LEGACY_API_READ_SCOPE,
)
from app.core.config import get_settings
from app.models import (
    ApiToken,
    AppUser,
    AuthIdentity,
    AuthSession,
    LocalCredential,
    Project,
    ProjectMembership,
)
from app.schemas.auth import (
    ApiTokenCreateRequest,
    ApiTokenCreatedResponse,
    ApiTokenListResponse,
    ApiTokenResponse,
    ApiTokenScopeListResponse,
    ApiTokenScopeResponse,
    AuthSessionResponse,
    AuthUserResponse,
)
from app.services import audit_service
from app.services.authz import normalize_role


PASSWORD_HASH = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = PASSWORD_HASH.hash("not-a-real-user-password")
LOCAL_PROVIDER = "local"
OCI_IAM_PROVIDER = "oci_iam"


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    """Validated request identity independent of the authentication mechanism."""

    user_id: str
    email: str
    display_name: str
    role: str
    authentication_method: Literal["session", "api_token"]
    credential_id: str
    expires_at: datetime | None
    allowed_project_ids: frozenset[str] | None = None
    scopes: frozenset[str] = frozenset()
    bypass_project_membership: bool = False


def utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def digest_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_username(value: str) -> str:
    return value.strip().casefold()


def validate_password(password: str) -> None:
    settings = get_settings()
    if len(password) < settings.AUTH_PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": f"Password must contain at least {settings.AUTH_PASSWORD_MIN_LENGTH} characters.",
                "error_code": "PASSWORD_TOO_SHORT",
            },
        )


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
        detail={"detail": "Authentication required", "error_code": "AUTHENTICATION_REQUIRED"},
    )


def session_required() -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={"detail": "A browser session is required", "error_code": "SESSION_REQUIRED"},
    )


async def hash_password(password: str) -> str:
    validate_password(password)
    return await asyncio.to_thread(PASSWORD_HASH.hash, password)


async def _serialize_user(user: AppUser, db: AsyncSession) -> AuthUserResponse:
    identities = list(
        (
            await db.scalars(
                select(AuthIdentity)
                .where(AuthIdentity.user_id == user.id, AuthIdentity.is_active.is_(True))
                .order_by(AuthIdentity.provider)
            )
        ).all()
    )
    project_count = int(
        await db.scalar(
            select(func.count())
            .select_from(ProjectMembership)
            .where(ProjectMembership.user_id == user.id)
        )
        or 0
    )
    role = normalize_role(user.role) or "Viewer"
    local_identity = next(
        (identity for identity in identities if identity.provider == LOCAL_PROVIDER),
        None,
    )
    return AuthUserResponse(
        id=user.id,
        username=local_identity.subject if local_identity else None,
        email=user.email,
        display_name=user.display_name,
        role=cast(Literal["Admin", "Architect", "Analyst", "Viewer"], role),
        providers=cast(
            list[Literal["local", "oci_iam"]],
            [identity.provider for identity in identities],
        ),
        project_count=project_count,
    )


async def session_response(
    principal: AuthPrincipal,
    db: AsyncSession,
) -> AuthSessionResponse:
    user = await db.get(AppUser, principal.user_id)
    if user is None:
        raise unauthorized()
    return AuthSessionResponse(
        user=await _serialize_user(user, db),
        authentication_method=principal.authentication_method,
        expires_at=principal.expires_at,
    )


async def authenticate_local(
    username: str,
    password: str,
    db: AsyncSession,
) -> tuple[AuthPrincipal, str]:
    """Verify local credentials and create a new opaque browser session."""

    subject = normalize_username(username)
    row = (
        await db.execute(
            select(AuthIdentity, AppUser, LocalCredential)
            .join(AppUser, AppUser.id == AuthIdentity.user_id)
            .join(LocalCredential, LocalCredential.identity_id == AuthIdentity.id)
            .where(
                AuthIdentity.provider == LOCAL_PROVIDER,
                AuthIdentity.subject == subject,
            )
            .with_for_update()
        )
    ).one_or_none()
    now = utcnow()
    if row is None:
        await asyncio.to_thread(PASSWORD_HASH.verify, password, DUMMY_PASSWORD_HASH)
        raise unauthorized()

    identity, user, credential = row
    locked_until = _as_utc(credential.locked_until)
    if (
        not user.is_active
        or not identity.is_active
        or (locked_until is not None and locked_until > now)
    ):
        await asyncio.to_thread(PASSWORD_HASH.verify, password, DUMMY_PASSWORD_HASH)
        raise unauthorized()

    verified = await asyncio.to_thread(PASSWORD_HASH.verify, password, credential.password_hash)
    if not verified:
        settings = get_settings()
        credential.failed_attempts += 1
        if credential.failed_attempts >= settings.AUTH_MAX_FAILED_ATTEMPTS:
            credential.locked_until = now + timedelta(minutes=settings.AUTH_LOCKOUT_MINUTES)
            credential.failed_attempts = 0
        await db.flush()
        # Failed logins exit through an HTTP exception, so the router's successful
        # transaction path cannot commit this security state for us.
        await db.commit()
        raise unauthorized()

    credential.failed_attempts = 0
    credential.locked_until = None
    identity.last_authenticated_at = now
    user.last_authenticated_at = now
    raw_token = secrets.token_urlsafe(48)
    expires_at = now + timedelta(hours=get_settings().AUTH_SESSION_TTL_HOURS)
    session = AuthSession(
        user_id=user.id,
        identity_id=identity.id,
        token_hash=digest_secret(raw_token),
        expires_at=expires_at,
        last_seen_at=now,
    )
    db.add(session)
    await db.flush()
    principal = AuthPrincipal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=normalize_role(user.role) or "Viewer",
        authentication_method="session",
        credential_id=session.id,
        expires_at=expires_at,
    )
    return principal, raw_token


async def authenticate_session(raw_token: str, db: AsyncSession) -> AuthPrincipal:
    row = (
        await db.execute(
            select(AuthSession, AppUser)
            .join(AppUser, AppUser.id == AuthSession.user_id)
            .where(AuthSession.token_hash == digest_secret(raw_token))
        )
    ).one_or_none()
    now = utcnow()
    if row is None:
        raise unauthorized()
    session, user = row
    expires_at = _as_utc(session.expires_at)
    if (
        not user.is_active
        or session.revoked_at is not None
        or expires_at is None
        or expires_at <= now
    ):
        raise unauthorized()
    return AuthPrincipal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=normalize_role(user.role) or "Viewer",
        authentication_method="session",
        credential_id=session.id,
        expires_at=expires_at,
    )


async def authenticate_api_token(raw_token: str, db: AsyncSession) -> AuthPrincipal:
    row = (
        await db.execute(
            select(ApiToken, AppUser)
            .join(AppUser, AppUser.id == ApiToken.user_id)
            .where(ApiToken.token_hash == digest_secret(raw_token))
        )
    ).one_or_none()
    now = utcnow()
    if row is None:
        raise unauthorized()
    token, user = row
    expires_at = _as_utc(token.expires_at)
    scopes = {str(item) for item in (token.scopes or [])}
    if (
        not user.is_active
        or token.revoked_at is not None
        or (expires_at is not None and expires_at <= now)
        or not (scopes & (ALL_API_TOKEN_SCOPES | {LEGACY_API_READ_SCOPE}))
    ):
        raise unauthorized()
    token.last_used_at = now
    await db.flush()
    allowed = (
        frozenset(str(item) for item in token.allowed_project_ids)
        if token.allowed_project_ids is not None
        else None
    )
    return AuthPrincipal(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=normalize_role(user.role) or "Viewer",
        authentication_method="api_token",
        credential_id=token.id,
        expires_at=expires_at,
        allowed_project_ids=allowed,
        scopes=frozenset(scopes),
    )


async def revoke_session(session_id: str, user_id: str, db: AsyncSession) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.id == session_id, AuthSession.user_id == user_id)
        .values(revoked_at=utcnow())
    )


async def change_local_password(
    principal: AuthPrincipal,
    current_password: str,
    new_password: str,
    db: AsyncSession,
) -> None:
    if principal.authentication_method != "session":
        raise HTTPException(
            status_code=403,
            detail={"detail": "A local browser session is required", "error_code": "LOCAL_SESSION_REQUIRED"},
        )
    row = (
        await db.execute(
            select(LocalCredential, AuthIdentity)
            .join(AuthIdentity, AuthIdentity.id == LocalCredential.identity_id)
            .where(AuthIdentity.user_id == principal.user_id, AuthIdentity.provider == LOCAL_PROVIDER)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "This user has no local credential", "error_code": "LOCAL_CREDENTIAL_MISSING"},
        )
    credential, _identity = row
    if not await asyncio.to_thread(PASSWORD_HASH.verify, current_password, credential.password_hash):
        raise unauthorized()
    credential.password_hash = await hash_password(new_password)
    credential.password_changed_at = utcnow()
    await db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == principal.user_id,
            AuthSession.id != principal.credential_id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )
    await audit_service.emit(
        event_type="local_password_changed",
        entity_type="app_user",
        entity_id=principal.user_id,
        actor_id=principal.user_id,
        old_value=None,
        new_value={"other_sessions_revoked": True},
        project_id=None,
        db=db,
    )


def serialize_api_token(token: ApiToken) -> ApiTokenResponse:
    return ApiTokenResponse(
        id=token.id,
        name=token.name,
        token_prefix=token.token_prefix,
        scopes=[str(item) for item in token.scopes],
        project_ids=cast(list[str] | None, token.allowed_project_ids),
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        revoked_at=token.revoked_at,
        created_at=token.created_at,
    )


async def list_api_tokens(user_id: str, db: AsyncSession) -> ApiTokenListResponse:
    tokens = list(
        (
            await db.scalars(
                select(ApiToken)
                .where(ApiToken.user_id == user_id)
                .order_by(ApiToken.created_at.desc())
            )
        ).all()
    )
    return ApiTokenListResponse(tokens=[serialize_api_token(token) for token in tokens])


def list_api_token_scopes() -> ApiTokenScopeListResponse:
    return ApiTokenScopeListResponse(
        scopes=[
            ApiTokenScopeResponse(
                code=item.code,
                label=item.label,
                description=item.description,
            )
            for item in API_TOKEN_SCOPE_CATALOG
        ]
    )


async def create_api_token(
    principal: AuthPrincipal,
    body: ApiTokenCreateRequest,
    db: AsyncSession,
) -> ApiTokenCreatedResponse:
    if principal.authentication_method != "session":
        raise HTTPException(
            status_code=403,
            detail={"detail": "A browser session is required", "error_code": "SESSION_REQUIRED"},
        )
    project_ids = body.project_ids
    if project_ids:
        member_ids = set(
            (
                await db.scalars(
                    select(ProjectMembership.project_id).where(
                        ProjectMembership.user_id == principal.user_id,
                        ProjectMembership.project_id.in_(project_ids),
                    )
                )
            ).all()
        )
        if member_ids != set(project_ids):
            raise HTTPException(
                status_code=404,
                detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"},
            )
    raw_token = f"odis_api_{secrets.token_urlsafe(40)}"
    token = ApiToken(
        user_id=principal.user_id,
        name=body.name,
        token_prefix=raw_token[:16],
        token_hash=digest_secret(raw_token),
        scopes=body.scopes,
        allowed_project_ids=project_ids,
        expires_at=utcnow() + timedelta(days=body.expires_in_days),
    )
    db.add(token)
    await db.flush()
    await audit_service.emit(
        event_type="api_token_created",
        entity_type="api_token",
        entity_id=token.id,
        actor_id=principal.user_id,
        old_value=None,
        new_value={
            "name": token.name,
            "scopes": token.scopes,
            "project_count": len(project_ids) if project_ids is not None else None,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        },
        project_id=None,
        db=db,
    )
    return ApiTokenCreatedResponse(
        **serialize_api_token(token).model_dump(),
        token=raw_token,
    )


async def revoke_api_token(
    principal: AuthPrincipal,
    token_id: str,
    db: AsyncSession,
) -> None:
    token = await db.scalar(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == principal.user_id)
    )
    if token is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "API token not found", "error_code": "API_TOKEN_NOT_FOUND"},
        )
    if token.revoked_at is None:
        token.revoked_at = utcnow()
        await audit_service.emit(
            event_type="api_token_revoked",
            entity_type="api_token",
            entity_id=token.id,
            actor_id=principal.user_id,
            old_value={"revoked": False},
            new_value={"revoked": True},
            project_id=None,
            db=db,
        )


async def has_project_access(
    principal: AuthPrincipal,
    project_id: str,
    db: AsyncSession,
) -> bool:
    return await get_project_membership_role(principal, project_id, db) is not None


async def get_project_membership_role(
    principal: AuthPrincipal,
    project_id: str,
    db: AsyncSession,
) -> str | None:
    """Return the live project role allowed by the current credential boundary."""

    if principal.allowed_project_ids is not None and project_id not in principal.allowed_project_ids:
        return None
    return cast(
        str | None,
        await db.scalar(
            select(ProjectMembership.project_role).where(
                ProjectMembership.user_id == principal.user_id,
                ProjectMembership.project_id == project_id,
            )
        ),
    )


async def require_project_access(
    principal: AuthPrincipal,
    project_id: str,
    db: AsyncSession,
) -> None:
    if not await has_project_access(principal, project_id, db):
        raise HTTPException(
            status_code=404,
            detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"},
        )


async def require_project_roles(
    principal: AuthPrincipal,
    project_id: str,
    allowed_roles: set[str] | frozenset[str],
    db: AsyncSession,
) -> str:
    """Require both live project access and one permitted membership role."""

    project_role = await get_project_membership_role(principal, project_id, db)
    if project_role is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Project not found", "error_code": "PROJECT_NOT_FOUND"},
        )
    if project_role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail={
                "detail": "The project membership does not grant this action.",
                "error_code": "PROJECT_ROLE_REQUIRED",
                "allowed_project_roles": sorted(allowed_roles),
            },
        )
    return project_role


async def upsert_local_user(
    *,
    username: str,
    email: str,
    display_name: str,
    role: str,
    password: str,
    grant_existing_projects: bool,
    db: AsyncSession,
    project_ids: list[str] | None = None,
) -> AppUser:
    """Provision one local user without enabling public self-registration."""

    canonical_role = normalize_role(role)
    if not canonical_role:
        raise ValueError("role must be Admin, Architect, Analyst, or Viewer")
    normalized_email = email.strip().casefold()
    subject = normalize_username(username)
    identity = await db.scalar(
        select(AuthIdentity).where(
            AuthIdentity.provider == LOCAL_PROVIDER,
            AuthIdentity.subject == subject,
        )
    )
    if identity is None:
        user = await db.scalar(select(AppUser).where(AppUser.email == normalized_email))
        if user is None:
            user = AppUser(
                email=normalized_email,
                display_name=display_name.strip(),
                role=canonical_role,
                is_active=True,
            )
            db.add(user)
            await db.flush()
        identity = AuthIdentity(
            user_id=user.id,
            provider=LOCAL_PROVIDER,
            subject=subject,
            is_active=True,
        )
        db.add(identity)
        await db.flush()
    else:
        user = await db.get(AppUser, identity.user_id)
        if user is None:
            raise RuntimeError("local identity references a missing user")
        user.email = normalized_email
        user.display_name = display_name.strip()
        user.role = canonical_role
        user.is_active = True
        identity.is_active = True
    credential = await db.get(LocalCredential, identity.id)
    password_digest = await hash_password(password)
    if credential is None:
        credential = LocalCredential(
            identity_id=identity.id,
            password_hash=password_digest,
            password_changed_at=utcnow(),
        )
        db.add(credential)
    else:
        credential.password_hash = password_digest
        credential.password_changed_at = utcnow()
        credential.failed_attempts = 0
        credential.locked_until = None
    requested_project_ids = set(project_ids or [])
    if grant_existing_projects or requested_project_ids:
        project_query = select(Project)
        if not grant_existing_projects:
            project_query = project_query.where(Project.id.in_(requested_project_ids))
        projects = list((await db.scalars(project_query)).all())
        found_project_ids = {project.id for project in projects}
        missing_project_ids = requested_project_ids - found_project_ids
        if missing_project_ids:
            raise ValueError(
                "project_ids contain unknown projects: " + ", ".join(sorted(missing_project_ids))
            )
        existing = set(
            (
                await db.scalars(
                    select(ProjectMembership.project_id).where(
                        ProjectMembership.user_id == user.id
                    )
                )
            ).all()
        )
        for project in projects:
            if project.id not in existing:
                db.add(
                    ProjectMembership(
                        project_id=project.id,
                        user_id=user.id,
                        project_role="Owner" if project.owner_id == user.id else "Contributor",
                        granted_by=user.id,
                    )
                )
    await db.flush()
    return user
