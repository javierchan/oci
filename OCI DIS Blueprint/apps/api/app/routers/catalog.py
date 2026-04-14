"""Catalog router — list, detail, patch, bulk patch, and lineage."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.catalog import (
    BulkPatchRequest,
    BulkPatchResult,
    CatalogIntegrationDeleteResponse,
    CatalogIntegrationDetail,
    CatalogIntegrationPatch,
    CatalogIntegrationResponse,
    CatalogListResponse,
    LineageDetail,
    ManualIntegrationCreate,
    OICEstimateRequest,
    OICEstimateResponse,
)
from app.schemas.graph import GraphResponse
from app.services import catalog_service, graph_service

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
    source_system: Optional[str] = None,
    destination_system: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> CatalogListResponse:
    return await catalog_service.list_integrations(
        project_id=project_id,
        page=page,
        page_size=page_size,
        filters={
            "pattern": pattern,
            "brand": brand,
            "qa_status": qa_status,
            "search": search,
            "source_system": source_system,
            "destination_system": destination_system,
        },
        db=db,
    )


@router.post("/{project_id}", response_model=CatalogIntegrationResponse, status_code=status.HTTP_201_CREATED, summary="Create a catalog integration from manual capture")
async def create_integration(
    project_id: str,
    body: ManualIntegrationCreate,
    actor_id: str = "api-user",
    db: AsyncSession = Depends(get_db),
) -> CatalogIntegrationResponse:
    async with db.begin():
        return await catalog_service.manual_create_integration(project_id, body, actor_id, db)


@router.get("/{project_id}/systems", response_model=list[str], summary="List unique systems for autocomplete")
async def list_systems(project_id: str, db: AsyncSession = Depends(get_db)) -> list[str]:
    return await catalog_service.list_systems(project_id, db)


@router.get("/{project_id}/duplicates", response_model=list[CatalogIntegrationResponse], summary="Check for duplicate source/destination/business process matches")
async def find_duplicates(
    project_id: str,
    source_system: str,
    destination_system: str,
    business_process: str,
    db: AsyncSession = Depends(get_db),
) -> list[CatalogIntegrationResponse]:
    return await catalog_service.find_duplicates(
        project_id=project_id,
        source_system=source_system,
        destination_system=destination_system,
        business_process=business_process,
        db=db,
    )


@router.post("/{project_id}/estimate", response_model=OICEstimateResponse, summary="Get a live OIC estimate for capture inputs")
async def estimate_oic(
    project_id: str,
    body: OICEstimateRequest,
    db: AsyncSession = Depends(get_db),
) -> OICEstimateResponse:
    return await catalog_service.estimate_oic(project_id, body, db)


@router.get("/{project_id}/graph", response_model=GraphResponse, summary="Get the system dependency graph")
async def get_graph(
    project_id: str,
    business_process: Optional[str] = None,
    brand: Optional[str] = None,
    qa_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> GraphResponse:
    return await graph_service.compute_graph(project_id, business_process, brand, qa_status, db)


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


@router.delete(
    "/{project_id}/{integration_id}",
    response_model=CatalogIntegrationDeleteResponse,
    summary="Remove a catalog integration and recalculate the project",
)
async def delete_integration(
    project_id: str,
    integration_id: str,
    actor_id: str = "api-user",
    db: AsyncSession = Depends(get_db),
) -> CatalogIntegrationDeleteResponse:
    async with db.begin():
        return await catalog_service.delete_integration(project_id, integration_id, actor_id, db)
