"""Assumptions router — /assumptions."""

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.reference import (
    AssumptionSetCreate,
    AssumptionSetListResponse,
    AssumptionSetResponse,
    AssumptionSetUpdate,
)
from app.services import reference_service
from app.services.authz import require_admin

router = APIRouter(prefix="/assumptions", tags=["Assumptions"])


@router.get("/", response_model=AssumptionSetListResponse, summary="List assumption sets")
async def list_assumption_sets(db: AsyncSession = Depends(get_db)) -> AssumptionSetListResponse:
    """Return all governed assumption sets."""

    return await reference_service.list_assumption_sets(db)


@router.post(
    "/",
    response_model=AssumptionSetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a governed assumption set",
)
async def create_assumption_set(
    body: AssumptionSetCreate,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Admin", alias="X-Actor-Role"),
) -> AssumptionSetResponse:
    """Create a versioned assumption set through the governance service."""

    require_admin(actor_role)
    async with db.begin():
        return await reference_service.create_assumption_set(body, actor_id, db)


@router.get("/default", response_model=AssumptionSetResponse, summary="Get default assumption set")
async def get_default(db: AsyncSession = Depends(get_db)) -> AssumptionSetResponse:
    """Return the default governed assumption set."""

    return await reference_service.get_default_assumption_set(db)


@router.get("/{version}", response_model=AssumptionSetResponse, summary="Get assumption set by version")
async def get_assumption_set(
    version: str,
    db: AsyncSession = Depends(get_db),
) -> AssumptionSetResponse:
    """Return one governed assumption set by version."""

    return await reference_service.get_assumption_set(version, db)


@router.patch("/{version}", response_model=AssumptionSetResponse, summary="Update a governed assumption set")
async def update_assumption_set(
    version: str,
    body: AssumptionSetUpdate,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Admin", alias="X-Actor-Role"),
) -> AssumptionSetResponse:
    """Patch one versioned assumption set."""

    require_admin(actor_role)
    async with db.begin():
        return await reference_service.update_assumption_set(version, body, actor_id, db)


@router.post(
    "/{version}/default",
    response_model=AssumptionSetResponse,
    summary="Promote an assumption set to default",
)
async def set_default_assumption_set(
    version: str,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Admin", alias="X-Actor-Role"),
) -> AssumptionSetResponse:
    """Mark one governed assumption set as the default version."""

    require_admin(actor_role)
    async with db.begin():
        return await reference_service.set_default_assumption_set(version, actor_id, db)
