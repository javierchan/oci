"""Services router — /services (OCI service capability profiles)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models import ServiceCapabilityProfile

router = APIRouter(prefix="/services", tags=["Services"])


@router.get("/", summary="List all OCI service capability profiles")
async def list_services(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    rows = (
        await db.scalars(
            select(ServiceCapabilityProfile)
            .where(ServiceCapabilityProfile.is_active.is_(True))
            .order_by(
                ServiceCapabilityProfile.category,
                ServiceCapabilityProfile.service_id,
            )
        )
    ).all()
    results: list[dict[str, object]] = []
    for row in rows:
        payload = {column.key: getattr(row, column.key) for column in row.__table__.columns}
        payload.pop("_sa_instance_state", None)
        results.append(payload)
    return {"services": results, "total": len(results)}


@router.get("/{service_id}", summary="Get a service profile by service_id (e.g. OIC3)")
async def get_service(service_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    row = await db.scalar(
        select(ServiceCapabilityProfile).where(
            ServiceCapabilityProfile.service_id == service_id.upper()
        )
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "Service profile not found",
                "error_code": "SERVICE_NOT_FOUND",
            },
        )
    payload = {column.key: getattr(row, column.key) for column in row.__table__.columns}
    payload.pop("_sa_instance_state", None)
    return payload
