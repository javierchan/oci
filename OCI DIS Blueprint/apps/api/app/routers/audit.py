"""Audit router — /audit (PRD-045)."""
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/{project_id}", summary="Query audit events")
async def list_audit_events(
    project_id: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    event_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """
    Queryable by project, import batch, row, user, and event type (PRD-014).
    Covers: imports, normalization, edits, recalculations, approvals, exports.
    """
    return {"events": [], "total": 0}
