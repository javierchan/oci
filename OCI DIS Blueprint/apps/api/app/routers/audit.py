"""Audit router — query the structured audit trail."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.audit import AuditEventListResponse
from app.services import audit_service

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/{project_id}", response_model=AuditEventListResponse, summary="Query audit events")
async def list_audit_events(
    project_id: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    event_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> AuditEventListResponse:
    return await audit_service.list_events(
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        event_type=event_type,
        page=page,
        page_size=page_size,
        db=db,
    )
