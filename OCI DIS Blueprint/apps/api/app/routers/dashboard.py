"""Dashboard router — /dashboard (PRD-036 to PRD-039)."""

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
    """Return persisted technical dashboard snapshots for a project."""

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
    """
    Returns technical-only dashboard by default (PRD-036):
    - KPI strip: OIC msgs/month, peak packs/hour, DI workspace, DI GB, Functions units
    - Coverage and completeness charts
    - Pattern mix breakdown
    - Payload distribution
    - Technical risks (drill-through to catalog rows)
    - Maturity indicators
    """
    async with db.begin():
        return await dashboard_service.get_snapshot(project_id, snapshot_id, db)
