"""Dictionaries router — governed dropdown values and admin mutations."""

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.reference import (
    CanvasGovernanceResponse,
    DictionaryCategoryListResponse,
    DictionaryOptionCreate,
    DictionaryOptionListResponse,
    DictionaryOptionResponse,
    DictionaryOptionUpdate,
)
from app.services import reference_service
from app.services.authz import require_admin

router = APIRouter(prefix="/dictionaries", tags=["Dictionaries"])


@router.get("/", response_model=DictionaryCategoryListResponse, summary="List all dictionary categories")
async def list_categories(db: AsyncSession = Depends(get_db)) -> DictionaryCategoryListResponse:
    return await reference_service.list_dictionary_categories(db)


@router.get(
    "/canvas-governance",
    response_model=CanvasGovernanceResponse,
    summary="List governed tools, overlays, and standard combinations for the design canvas",
)
async def get_canvas_governance(db: AsyncSession = Depends(get_db)) -> CanvasGovernanceResponse:
    return await reference_service.get_canvas_governance(db)


@router.get("/{category}", response_model=DictionaryOptionListResponse, summary="List options for a category")
async def list_options(category: str, db: AsyncSession = Depends(get_db)) -> DictionaryOptionListResponse:
    return await reference_service.list_dictionary_options(category, db)


@router.post(
    "/{category}",
    response_model=DictionaryOptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a governed dictionary option",
)
async def create_option(
    category: str,
    body: DictionaryOptionCreate,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> DictionaryOptionResponse:
    require_admin(actor_role)
    async with db.begin():
        return await reference_service.create_dictionary_option(category, body, actor_id, db)


@router.patch(
    "/{category}/{option_id}",
    response_model=DictionaryOptionResponse,
    summary="Update a governed dictionary option",
)
async def update_option(
    category: str,
    option_id: str,
    body: DictionaryOptionUpdate,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> DictionaryOptionResponse:
    require_admin(actor_role)
    async with db.begin():
        return await reference_service.update_dictionary_option(category, option_id, body, actor_id, db)


@router.delete(
    "/{category}/{option_id}",
    response_model=DictionaryOptionResponse,
    summary="Deactivate a governed dictionary option",
)
async def delete_option(
    category: str,
    option_id: str,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> DictionaryOptionResponse:
    require_admin(actor_role)
    async with db.begin():
        return await reference_service.deactivate_dictionary_option(category, option_id, actor_id, db)
