"""Dashboard router — /dashboard (PRD-036 to PRD-039)."""
from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/{project_id}/snapshots", summary="List dashboard snapshots")
async def list_dashboard_snapshots(project_id: str):
    return {"snapshots": []}


@router.get("/{project_id}/snapshots/{snapshot_id}", summary="Get dashboard snapshot")
async def get_dashboard_snapshot(project_id: str, snapshot_id: str):
    """
    Returns technical-only dashboard by default (PRD-036):
    - KPI strip: OIC msgs/month, peak packs/hour, DI workspace, DI GB, Functions units
    - Coverage and completeness charts
    - Pattern mix breakdown
    - Payload distribution
    - Technical risks (drill-through to catalog rows)
    - Maturity indicators
    """
    return {
        "mode": "technical",
        "kpi_strip": {},
        "charts": {},
        "risks": [],
    }
