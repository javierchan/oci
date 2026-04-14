"""Volumetry router — snapshot browsing endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.volumetry import ConsolidatedMetrics, VolumetrySnapshotListResponse, VolumetrySnapshotResponse
from app.services import recalc_service

router = APIRouter(prefix="/volumetry", tags=["Volumetry"])


@router.get("/{project_id}/snapshots", response_model=VolumetrySnapshotListResponse, summary="List volumetry snapshots")
async def list_snapshots(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> VolumetrySnapshotListResponse:
    return await recalc_service.list_snapshots(project_id, db)


@router.get("/{project_id}/snapshots/{snapshot_id}", response_model=VolumetrySnapshotResponse, summary="Get full volumetry snapshot")
async def get_snapshot(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
) -> VolumetrySnapshotResponse:
    return await recalc_service.get_snapshot(project_id, snapshot_id, db)


@router.get("/{project_id}/snapshots/{snapshot_id}/consolidated", response_model=ConsolidatedMetrics, summary="Consolidated driver totals")
async def get_consolidated(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
) -> ConsolidatedMetrics:
    return await recalc_service.get_consolidated_metrics(project_id, snapshot_id, db)
