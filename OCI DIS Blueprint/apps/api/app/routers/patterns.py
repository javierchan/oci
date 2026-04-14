"""Patterns router — served from seeded and admin-managed reference data."""

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.reference import (
    PatternDefinitionCreate,
    PatternDefinitionResponse,
    PatternDefinitionUpdate,
    PatternListResponse,
)
from app.services import reference_service
from app.services.authz import require_admin

router = APIRouter(prefix="/patterns", tags=["Patterns"])


@router.get("", response_model=PatternListResponse, include_in_schema=False)
@router.get("/", response_model=PatternListResponse, summary="List all integration patterns")
async def list_patterns(db: AsyncSession = Depends(get_db)) -> PatternListResponse:
    return await reference_service.list_patterns(db)


@router.get("/{pattern_id}", response_model=PatternDefinitionResponse, summary="Get a pattern by ID (e.g. #01)")
async def get_pattern(pattern_id: str, db: AsyncSession = Depends(get_db)) -> PatternDefinitionResponse:
    return await reference_service.get_pattern(pattern_id, db)


@router.post("/", response_model=PatternDefinitionResponse, status_code=status.HTTP_201_CREATED, summary="Create a custom pattern definition")
async def create_pattern(
    body: PatternDefinitionCreate,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Admin", alias="X-Actor-Role"),
) -> PatternDefinitionResponse:
    require_admin(actor_role)
    async with db.begin():
        return await reference_service.create_pattern(body, actor_id, db)


@router.patch("/{pattern_id}", response_model=PatternDefinitionResponse, summary="Update a pattern definition")
async def update_pattern(
    pattern_id: str,
    body: PatternDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Admin", alias="X-Actor-Role"),
) -> PatternDefinitionResponse:
    require_admin(actor_role)
    async with db.begin():
        return await reference_service.update_pattern(pattern_id, body, actor_id, db)


@router.delete("/{pattern_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a custom pattern definition")
async def delete_pattern(
    pattern_id: str,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header("Admin", alias="X-Actor-Role"),
) -> Response:
    require_admin(actor_role)
    async with db.begin():
        await reference_service.delete_pattern(pattern_id, actor_id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
