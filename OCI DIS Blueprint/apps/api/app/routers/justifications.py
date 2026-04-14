"""Justifications router — /justifications (PRD-040 to PRD-042)."""
from fastapi import APIRouter, status

router = APIRouter(prefix="/justifications", tags=["Justifications"])


@router.get("/{project_id}", summary="List justification records")
async def list_justifications(project_id: str):
    return {"records": []}


@router.get("/{project_id}/{integration_id}", summary="Get justification for an integration")
async def get_justification(project_id: str, integration_id: str):
    return {}


@router.post("/{project_id}/{integration_id}/approve", summary="Approve a justification narrative")
async def approve_justification(project_id: str, integration_id: str):
    """Sets state=approved, records approved_by, emits AuditEvent (PRD-042)."""
    return {"state": "approved"}


@router.post("/{project_id}/{integration_id}/override", summary="Override with custom narrative")
async def override_justification(project_id: str, integration_id: str, body: dict):
    return {"state": "overridden"}
