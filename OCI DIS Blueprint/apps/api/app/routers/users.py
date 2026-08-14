"""Admin-only user management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.user_management import (
    ManagedUserCreateRequest,
    ManagedUserListResponse,
    ManagedUserPatchRequest,
    ManagedUserResponse,
    UserMembershipReplaceRequest,
)
from app.services import user_management_service
from app.services.authz import require_admin


router = APIRouter(prefix="/admin/users", tags=["User Management"])


@router.get("", response_model=ManagedUserListResponse, summary="List managed App users")
async def list_users(
    include_inactive: bool = Query(True),
    actor_role: str = Header(..., alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ManagedUserListResponse:
    require_admin(actor_role)
    return await user_management_service.list_users(db, include_inactive=include_inactive)


@router.get("/{user_id}", response_model=ManagedUserResponse, summary="Read one managed App user")
async def get_user(
    user_id: str,
    actor_role: str = Header(..., alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ManagedUserResponse:
    require_admin(actor_role)
    return await user_management_service.get_user(user_id, db)


@router.post(
    "",
    response_model=ManagedUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a local App user",
)
async def create_user(
    body: ManagedUserCreateRequest,
    actor_id: str = Header(..., alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ManagedUserResponse:
    require_admin(actor_role)
    result = await user_management_service.create_user(body, actor_id, db)
    await db.commit()
    return result

@router.patch("/{user_id}", response_model=ManagedUserResponse, summary="Edit a managed App user")
async def update_user(
    user_id: str,
    body: ManagedUserPatchRequest,
    actor_id: str = Header(..., alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ManagedUserResponse:
    require_admin(actor_role)
    result = await user_management_service.update_user(user_id, body, actor_id, db)
    await db.commit()
    return result


@router.put(
    "/{user_id}/memberships",
    response_model=ManagedUserResponse,
    summary="Replace a user's project memberships",
)
async def replace_memberships(
    user_id: str,
    body: UserMembershipReplaceRequest,
    actor_id: str = Header(..., alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
    db: AsyncSession = Depends(get_db),
) -> ManagedUserResponse:
    require_admin(actor_role)
    result = await user_management_service.replace_user_memberships(user_id, body, actor_id, db)
    await db.commit()
    return result
