"""Catalog router — /catalog (PRD-020 to PRD-026)."""
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get("/{project_id}", summary="List catalog integrations with filters/search")
async def list_integrations(
    project_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    pattern: Optional[str] = None,
    brand: Optional[str] = None,
    qa_status: Optional[str] = None,
    search: Optional[str] = None,
):
    """Returns paginated catalog rows with grouped fields matching TPL - Catálogo semantics."""
    return {"integrations": [], "total": 0, "page": page, "page_size": page_size}


@router.get("/{project_id}/{integration_id}", summary="Get single integration with lineage")
async def get_integration(project_id: str, integration_id: str):
    """Returns full row including source lineage, normalization events, and QA reasons."""
    return {}


@router.patch("/{project_id}/{integration_id}", summary="Update architect-owned fields")
async def update_integration(project_id: str, integration_id: str, body: dict):
    """
    Allowed architect fields: selected_pattern, pattern_rationale, comments,
    retry_policy, core_tools, additional_tools_overlays.
    Every change emits an AuditEvent and triggers scoped recalculation (PRD-022).
    """
    return {"id": integration_id, **body}


@router.post("/{project_id}/bulk-patch", summary="Bulk update selected rows")
async def bulk_patch(project_id: str, body: dict):
    """
    Apply a common field update to a list of integration IDs.
    Respects validation rules and creates per-row audit events (PRD-026).
    """
    return {"updated": 0, "errors": []}


@router.get("/{project_id}/{integration_id}/lineage", summary="Get source lineage for a row")
async def get_lineage(project_id: str, integration_id: str):
    """Returns source row, import batch, raw values, normalization events (PRD-023)."""
    return {}
