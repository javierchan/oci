"""Dashboard router — technical dashboard snapshot browsing endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.dashboard import DashboardSnapshotListResponse, DashboardSnapshotResponse
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/{project_id}/snapshots",
    response_model=DashboardSnapshotListResponse,
    summary="List dashboard snapshots",
)
async def list_dashboard_snapshots(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> DashboardSnapshotListResponse:
    async with db.begin():
        return await dashboard_service.list_snapshots(project_id, db)


@router.get(
    "/{project_id}/snapshots/{snapshot_id}",
    response_model=DashboardSnapshotResponse,
    summary="Get dashboard snapshot",
)
async def get_dashboard_snapshot(
    project_id: str,
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
) -> DashboardSnapshotResponse:
    async with db.begin():
        return await dashboard_service.get_snapshot(project_id, snapshot_id, db)
