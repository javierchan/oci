"""Volumetry router — /volumetry (PRD-027 to PRD-034)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.volumetry import (
    ConsolidatedMetrics,
    VolumetrySnapshotListResponse,
    VolumetrySnapshotResponse,
    VolumetrySnapshotRowResultsResponse,
)
from app.services import recalc_service

router = APIRouter(prefix="/volumetry", tags=["Volumetry"])


@router.get(
    "/{project_id}/snapshots",
    response_model=VolumetrySnapshotListResponse,
    summary="List volumetry snapshots",
)
async def list_snapshots(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> VolumetrySnapshotListResponse:
    """Return persisted volumetry snapshots for a project."""

    return await recalc_service.list_snapshots(project_id, db)


@router.get(
    "/{project_id}/snapshots/{snapshot_id}",
    response_model=VolumetrySnapshotResponse,
    summary="Get full volumetry snapshot",
)
async def get_snapshot(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
) -> VolumetrySnapshotResponse:
    """Returns row-level and consolidated metrics with assumption references."""

    return await recalc_service.get_snapshot(project_id, snapshot_id, db)


@router.get(
    "/{project_id}/snapshots/{snapshot_id}/rows",
    response_model=VolumetrySnapshotRowResultsResponse,
    summary="Row-level volumetry results",
)
async def get_snapshot_rows(
    project_id: str,
    snapshot_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> VolumetrySnapshotRowResultsResponse:
    """Return paginated row-level volumetry metrics."""

    return await recalc_service.list_snapshot_rows(project_id, snapshot_id, page, page_size, db)


@router.get(
    "/{project_id}/snapshots/{snapshot_id}/consolidated",
    response_model=ConsolidatedMetrics,
    summary="Consolidated driver totals",
)
async def get_consolidated(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
) -> ConsolidatedMetrics:
    """
    Returns consolidated totals for:
    - OIC: messages/month, peak msgs/hour, peak packs/hour (PRD-030, PRD-031)
    - DI: workspace active, GB/month, pipeline hours (PRD-033)
    - Functions: invocations/month, execution units (PRD-034)
    - Streaming: volume, partition count (PRD-032)
    - Queue: request count (PRD-032)
    """
    return await recalc_service.get_consolidated_metrics(project_id, snapshot_id, db)
