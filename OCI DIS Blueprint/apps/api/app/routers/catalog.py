"""Catalog router — list, detail, patch, bulk patch, and lineage."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.catalog import (
    BulkPatchRequest,
    BulkPatchResult,
    CatalogIntegrationDetail,
    CatalogIntegrationPatch,
    CatalogIntegrationResponse,
    CatalogListResponse,
    LineageDetail,
)
from app.services import catalog_service

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get("/{project_id}", response_model=CatalogListResponse, summary="List catalog integrations with filters/search")
async def list_integrations(
    project_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    pattern: Optional[str] = None,
    brand: Optional[str] = None,
    qa_status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> CatalogListResponse:
    return await catalog_service.list_integrations(
        project_id=project_id,
        page=page,
        page_size=page_size,
        filters={"pattern": pattern, "brand": brand, "qa_status": qa_status, "search": search},
        db=db,
    )


@router.get("/{project_id}/{integration_id}", response_model=CatalogIntegrationDetail, summary="Get single integration with lineage")
async def get_integration(
    project_id: str,
    integration_id: str,
    db: AsyncSession = Depends(get_db),
) -> CatalogIntegrationDetail:
    return await catalog_service.get_integration(project_id, integration_id, db)


@router.patch("/{project_id}/{integration_id}", response_model=CatalogIntegrationResponse, summary="Update architect-owned fields")
async def update_integration(
    project_id: str,
    integration_id: str,
    body: CatalogIntegrationPatch,
    actor_id: str = "api-user",
    db: AsyncSession = Depends(get_db),
) -> CatalogIntegrationResponse:
    async with db.begin():
        return await catalog_service.update_integration(project_id, integration_id, body, actor_id, db)


@router.post("/{project_id}/bulk-patch", response_model=BulkPatchResult, summary="Bulk update selected rows")
async def bulk_patch(
    project_id: str,
    body: BulkPatchRequest,
    db: AsyncSession = Depends(get_db),
) -> BulkPatchResult:
    async with db.begin():
        return await catalog_service.bulk_patch(
            project_id=project_id,
            integration_ids=body.integration_ids,
            patch=body.patch,
            actor_id=body.actor_id,
            db=db,
        )


@router.get("/{project_id}/{integration_id}/lineage", response_model=LineageDetail, summary="Get source lineage for a row")
async def get_lineage(
    project_id: str,
    integration_id: str,
    db: AsyncSession = Depends(get_db),
) -> LineageDetail:
    return await catalog_service.get_lineage(project_id, integration_id, db)
