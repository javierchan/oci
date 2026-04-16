"""Patterns router — list, read, and govern integration pattern taxonomy."""

from typing import Any, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import PatternDefinition
from app.schemas.reference import (
    PatternDefinitionCreate,
    PatternDefinitionResponse,
    PatternDefinitionUpdate,
)
from app.services import reference_service
from app.services.authz import require_admin

router = APIRouter(prefix="/patterns", tags=["Patterns"])


def _serialize_pattern(pattern: PatternDefinition) -> dict[str, Any]:
    return cast(dict[str, Any], reference_service.serialize_pattern(pattern).model_dump(mode="json"))


@router.get("", include_in_schema=False)
@router.get("/", summary="List all integration patterns")
async def list_patterns(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    result = await db.scalars(
        select(PatternDefinition)
        .where(PatternDefinition.is_active.is_(True))
        .order_by(PatternDefinition.pattern_id.asc())
    )
    patterns = [_serialize_pattern(pattern) for pattern in result.all()]
    return {"patterns": patterns, "total": len(patterns)}


@router.get("/{pattern_id}", summary="Get a pattern by ID (e.g. #01)")
async def get_pattern(pattern_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    pattern = await db.scalar(select(PatternDefinition).where(PatternDefinition.pattern_id == pattern_id))
    if pattern is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Pattern not found", "error_code": "PATTERN_NOT_FOUND"},
        )
    return _serialize_pattern(pattern)


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
