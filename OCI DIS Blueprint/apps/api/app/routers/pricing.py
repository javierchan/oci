"""Admin and read APIs for governed OCI pricing catalogs and SKU mappings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.pricing import (
    PriceCatalogSnapshotListResponse,
    PriceCatalogSnapshotResponse,
    PriceItemListResponse,
    PriceSourceListResponse,
    PriceSyncJobListResponse,
    PriceSyncJobResponse,
    PriceSyncRequest,
    SkuMappingListResponse,
    SkuMappingPatchRequest,
    SkuMappingResponse,
)
from app.services import pricing_service
from app.services.authz import require_admin, require_roles
from app.workers.pricing_worker import execute_price_sync_job_task


router = APIRouter(prefix="/pricing", tags=["Pricing"])


def _require_pricing_read(role: str | None) -> None:
    require_roles(role, {"Admin", "Architect", "Analyst", "Viewer"}, error_code="PRICING_READ_ROLE_REQUIRED")


@router.get("/sources", response_model=PriceSourceListResponse, summary="List governed OCI price sources")
async def list_price_sources(
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> PriceSourceListResponse:
    _require_pricing_read(actor_role)
    return await pricing_service.list_price_sources(db)


@router.post(
    "/rate-card-imports",
    response_model=PriceCatalogSnapshotResponse,
    summary="Import an authorized contract rate card CSV",
)
async def import_rate_card(
    file: UploadFile = File(...),
    name: str = Form(..., min_length=1, max_length=255),
    currency: str = Form("USD", min_length=3, max_length=3),
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> PriceCatalogSnapshotResponse:
    require_admin(actor_role)
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=422,
            detail={"detail": "Rate card must be uploaded as CSV", "error_code": "RATE_CARD_FORMAT_INVALID"},
        )
    contents = await file.read()
    try:
        async with db.begin():
            return await pricing_service.import_rate_card(
                name=name,
                currency=currency,
                filename=file.filename,
                contents=contents,
                actor_id=actor_id,
                db=db,
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"detail": str(exc), "error_code": "RATE_CARD_CONTENT_INVALID"},
        ) from exc


@router.post(
    "/sync-jobs",
    response_model=PriceSyncJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Synchronize one governed OCI price source",
)
async def create_price_sync_job(
    body: PriceSyncRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> PriceSyncJobResponse:
    require_admin(actor_role)
    async with db.begin():
        job = await pricing_service.create_sync_job(body, actor_id, db)
    try:
        execute_price_sync_job_task.apply_async(args=[job.id], task_id=job.id)
    except Exception as exc:  # pragma: no cover - defensive dispatch path
        async with db.begin():
            await pricing_service.mark_sync_job_failed(job.id, {"detail": str(exc)}, db)
        raise HTTPException(
            status_code=503,
            detail={"detail": "Price sync worker could not be dispatched", "error_code": "PRICE_SYNC_DISPATCH_FAILED"},
        ) from exc
    return job


@router.get("/sync-jobs", response_model=PriceSyncJobListResponse, summary="List price sync jobs")
async def list_price_sync_jobs(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> PriceSyncJobListResponse:
    _require_pricing_read(actor_role)
    return await pricing_service.list_sync_jobs(db, limit)


@router.get("/sync-jobs/{job_id}", response_model=PriceSyncJobResponse, summary="Get one price sync job")
async def get_price_sync_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> PriceSyncJobResponse:
    _require_pricing_read(actor_role)
    return await pricing_service.get_sync_job(job_id, db)


@router.get(
    "/catalog-snapshots",
    response_model=PriceCatalogSnapshotListResponse,
    summary="List immutable OCI price catalogs",
)
async def list_price_catalog_snapshots(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> PriceCatalogSnapshotListResponse:
    _require_pricing_read(actor_role)
    return await pricing_service.list_price_snapshots(db, limit)


@router.post(
    "/catalog-snapshots/{snapshot_id}/approve",
    response_model=PriceCatalogSnapshotResponse,
    summary="Approve a reviewed price catalog",
)
async def approve_price_catalog_snapshot(
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> PriceCatalogSnapshotResponse:
    require_admin(actor_role)
    async with db.begin():
        return await pricing_service.approve_price_snapshot(snapshot_id, actor_id, db)


@router.get(
    "/catalog-snapshots/{snapshot_id}/items",
    response_model=PriceItemListResponse,
    summary="List normalized price items",
)
async def list_price_items(
    snapshot_id: str,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> PriceItemListResponse:
    _require_pricing_read(actor_role)
    return await pricing_service.list_price_items(snapshot_id, db, search=search, page=page, page_size=page_size)


@router.get("/sku-mappings", response_model=SkuMappingListResponse, summary="List governed SKU mappings")
async def list_sku_mappings(
    db: AsyncSession = Depends(get_db),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> SkuMappingListResponse:
    _require_pricing_read(actor_role)
    return await pricing_service.list_sku_mappings(db)


@router.patch("/sku-mappings/{mapping_id}", response_model=SkuMappingResponse, summary="Update a SKU mapping")
async def patch_sku_mapping(
    mapping_id: str,
    body: SkuMappingPatchRequest,
    db: AsyncSession = Depends(get_db),
    actor_id: str = Header("api-user", alias="X-Actor-Id"),
    actor_role: str = Header(..., alias="X-Actor-Role"),
) -> SkuMappingResponse:
    require_admin(actor_role)
    async with db.begin():
        return await pricing_service.patch_sku_mapping(mapping_id, body, actor_id, db)
