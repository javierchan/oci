"""FastAPI authentication and project-authorization dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.api_token_scopes import LEGACY_API_READ_SCOPE, required_scope_for_path
from app.core.db import get_db
from app.models import AgentRun, AiReviewJob
from app.services import auth_service
from app.services.auth_service import AuthPrincipal


SAFE_API_TOKEN_METHODS = {"GET", "HEAD", "OPTIONS"}


def _replace_actor_headers(request: Request, principal: AuthPrincipal) -> None:
    """Replace caller-controlled identity headers before legacy route dependencies read them."""

    headers = request.scope.get("headers")
    if not isinstance(headers, list):
        return
    headers[:] = [
        (name, value)
        for name, value in headers
        if name.lower() not in {b"x-actor-id", b"x-actor-role"}
    ]
    headers.extend(
        [
            (b"x-actor-id", principal.user_id.encode("utf-8")),
            (b"x-actor-role", principal.role.encode("utf-8")),
        ]
    )


def _validate_cookie_origin(request: Request) -> None:
    if request.method in SAFE_API_TOKEN_METHODS:
        return
    origin = request.headers.get("origin")
    if origin not in set(get_settings().CORS_ALLOWED_ORIGINS):
        raise HTTPException(
            status_code=403,
            detail={"detail": "Request origin is not allowed", "error_code": "CSRF_ORIGIN_REQUIRED"},
        )


async def authenticate_request(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db, use_cache=False)],
) -> AuthPrincipal:
    """Authenticate a browser session or a read-only external API token."""

    authorization = request.headers.get("authorization", "")
    principal: AuthPrincipal
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.casefold() != "bearer" or not token:
            raise auth_service.unauthorized()
        principal = await auth_service.authenticate_api_token(token, db)
        if request.method not in SAFE_API_TOKEN_METHODS:
            raise HTTPException(
                status_code=403,
                detail={
                    "detail": "This API token is read-only",
                    "error_code": "API_TOKEN_READ_ONLY",
                },
            )
        required_scope = required_scope_for_path(request.url.path)
        if required_scope is None or not (
            required_scope in principal.scopes or LEGACY_API_READ_SCOPE in principal.scopes
        ):
            raise HTTPException(
                status_code=403,
                detail={
                    "detail": "This API token does not grant the required read capability",
                    "error_code": "API_TOKEN_SCOPE_REQUIRED",
                    "required_scope": required_scope,
                },
            )
        await db.commit()
    else:
        raw_session = request.cookies.get(get_settings().AUTH_SESSION_COOKIE_NAME)
        if not raw_session:
            raise auth_service.unauthorized()
        _validate_cookie_origin(request)
        principal = await auth_service.authenticate_session(raw_session, db)
        await db.commit()

    request.state.auth = principal
    _replace_actor_headers(request, principal)
    return principal


async def authorize_project_request(
    request: Request,
    principal: Annotated[AuthPrincipal, Depends(authenticate_request)],
    db: Annotated[AsyncSession, Depends(get_db, use_cache=False)],
) -> AuthPrincipal:
    """Enforce explicit membership for path- and query-scoped project routes."""

    candidate = request.path_params.get("project_id") or request.query_params.get("project_id")
    if candidate:
        await auth_service.require_project_access(principal, str(candidate), db)
        await db.rollback()
        return principal

    run_id = request.path_params.get("run_id")
    if run_id and request.url.path.startswith("/api/v1/agents/runs/"):
        run = await db.get(AgentRun, str(run_id))
        if run is None:
            raise HTTPException(
                status_code=404,
                detail={"detail": "Agent run not found", "error_code": "AGENT_RUN_NOT_FOUND"},
            )
        if run.project_id:
            await auth_service.require_project_access(principal, run.project_id, db)
        elif run.requested_by != principal.user_id and principal.role != "Admin":
            raise HTTPException(
                status_code=404,
                detail={"detail": "Agent run not found", "error_code": "AGENT_RUN_NOT_FOUND"},
            )

    job_id = request.path_params.get("job_id")
    if job_id and request.url.path.startswith("/api/v1/ai-reviews/"):
        job = await db.get(AiReviewJob, str(job_id))
        if job is None:
            raise HTTPException(
                status_code=404,
                detail={"detail": "AI review not found", "error_code": "AI_REVIEW_NOT_FOUND"},
            )
        await auth_service.require_project_access(principal, job.project_id, db)
    await db.rollback()
    return principal


CurrentPrincipal = Annotated[AuthPrincipal, Depends(authenticate_request)]
AuthorizedPrincipal = Annotated[AuthPrincipal, Depends(authorize_project_request)]
