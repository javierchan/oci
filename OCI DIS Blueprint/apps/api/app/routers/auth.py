"""Local session and read-only external API token endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentPrincipal
from app.core.config import get_settings
from app.core.db import get_db
from app.schemas.auth import (
    ApiTokenCreateRequest,
    ApiTokenCreatedResponse,
    ApiTokenListResponse,
    ApiTokenScopeListResponse,
    AuthSessionResponse,
    ChangePasswordRequest,
    LoginRequest,
)
from app.services import auth_service


router = APIRouter(prefix="/auth", tags=["Authentication"])


def _require_browser_session(principal: CurrentPrincipal) -> None:
    if principal.authentication_method != "session":
        raise auth_service.session_required()


@router.post("/login", response_model=AuthSessionResponse, summary="Create a local browser session")
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    principal, raw_session = await auth_service.authenticate_local(
        body.username,
        body.password,
        db,
    )
    payload = await auth_service.session_response(principal, db)
    await db.commit()
    settings = get_settings()
    response.set_cookie(
        key=settings.AUTH_SESSION_COOKIE_NAME,
        value=raw_session,
        max_age=settings.AUTH_SESSION_TTL_HOURS * 3600,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return payload


@router.get("/me", response_model=AuthSessionResponse, summary="Read the current authenticated user")
async def me(
    principal: CurrentPrincipal,
    db: AsyncSession = Depends(get_db),
) -> AuthSessionResponse:
    return await auth_service.session_response(principal, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke the current browser session")
async def logout(
    response: Response,
    principal: CurrentPrincipal,
    db: AsyncSession = Depends(get_db),
) -> Response:
    if principal.authentication_method == "session":
        await auth_service.revoke_session(principal.credential_id, principal.user_id, db)
        await db.commit()
    response.delete_cookie(get_settings().AUTH_SESSION_COOKIE_NAME, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change the current local password",
)
async def change_password(
    body: ChangePasswordRequest,
    principal: CurrentPrincipal,
    db: AsyncSession = Depends(get_db),
) -> Response:
    _require_browser_session(principal)
    await auth_service.change_local_password(
        principal,
        body.current_password,
        body.new_password,
        db,
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api-tokens", response_model=ApiTokenListResponse, summary="List the current user's API tokens")
async def list_api_tokens(
    principal: CurrentPrincipal,
    db: AsyncSession = Depends(get_db),
) -> ApiTokenListResponse:
    _require_browser_session(principal)
    return await auth_service.list_api_tokens(principal.user_id, db)


@router.get(
    "/api-token-scopes",
    response_model=ApiTokenScopeListResponse,
    summary="List governed read-only API token capabilities",
)
async def list_api_token_scopes(principal: CurrentPrincipal) -> ApiTokenScopeListResponse:
    _require_browser_session(principal)
    return auth_service.list_api_token_scopes()


@router.post(
    "/api-tokens",
    response_model=ApiTokenCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a read-only external API token",
)
async def create_api_token(
    body: ApiTokenCreateRequest,
    principal: CurrentPrincipal,
    db: AsyncSession = Depends(get_db),
) -> ApiTokenCreatedResponse:
    _require_browser_session(principal)
    result = await auth_service.create_api_token(principal, body, db)
    await db.commit()
    return result


@router.delete(
    "/api-tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke one external API token",
)
async def revoke_api_token(
    token_id: str,
    principal: CurrentPrincipal,
    db: AsyncSession = Depends(get_db),
) -> Response:
    _require_browser_session(principal)
    await auth_service.revoke_api_token(principal, token_id, db)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
