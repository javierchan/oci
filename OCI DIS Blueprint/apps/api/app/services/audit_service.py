"""Audit-event persistence helpers."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent
from app.schemas.audit import AuditEventListResponse, AuditEventResponse
from app.services.serializers import sanitize_for_json


async def emit(
    event_type: str,
    entity_type: str,
    entity_id: str,
    actor_id: str,
    old_value: Optional[dict[str, object]],
    new_value: Optional[dict[str, object]],
    project_id: Optional[str],
    db: AsyncSession,
    correlation_id: Optional[str] = None,
) -> AuditEvent:
    """Persist a single audit event without committing the surrounding transaction."""

    event = AuditEvent(
        project_id=project_id,
        actor_id=actor_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=correlation_id,
        old_value=sanitize_for_json(old_value) if old_value is not None else None,
        new_value=sanitize_for_json(new_value) if new_value is not None else None,
    )
    db.add(event)
    await db.flush()
    return event


def serialize_event(event: AuditEvent) -> AuditEventResponse:
    """Convert an audit event model into its response schema."""

    return AuditEventResponse(
        id=event.id,
        project_id=event.project_id,
        actor_id=event.actor_id,
        event_type=event.event_type,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        correlation_id=event.correlation_id,
        old_value=event.old_value,
        new_value=event.new_value,
        metadata=event.audit_metadata,
        created_at=event.created_at,
    )


async def list_events(
    project_id: str,
    db: AsyncSession,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    event_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> AuditEventListResponse:
    """Return paginated audit events matching the provided filters."""

    query = select(AuditEvent).where(AuditEvent.project_id == project_id)
    if entity_type:
        query = query.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditEvent.entity_id == entity_id)
    if actor_id:
        query = query.where(AuditEvent.actor_id == actor_id)
    if event_type:
        query = query.where(AuditEvent.event_type == event_type)

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    offset = (page - 1) * page_size
    result = await db.scalars(
        query.order_by(AuditEvent.created_at.desc()).offset(offset).limit(page_size)
    )
    return AuditEventListResponse(
        events=[serialize_event(event) for event in result.all()],
        total=total or 0,
        page=page,
        page_size=page_size,
    )
