"""Assumptions router — versioned calculation assumptions."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.reference import AssumptionSetListResponse, AssumptionSetResponse
from app.services import reference_service

router = APIRouter(prefix="/assumptions", tags=["Assumptions"])


@router.get("/", response_model=AssumptionSetListResponse, summary="List assumption sets")
async def list_assumption_sets(db: AsyncSession = Depends(get_db)) -> AssumptionSetListResponse:
    return await reference_service.list_assumption_sets(db)


@router.get("/default", response_model=AssumptionSetResponse, summary="Get default assumption set")
async def get_default(db: AsyncSession = Depends(get_db)) -> AssumptionSetResponse:
    return await reference_service.get_default_assumption_set(db)


@router.get("/{version}", response_model=AssumptionSetResponse, summary="Get assumption set by version")
async def get_assumption_set(version: str, db: AsyncSession = Depends(get_db)) -> AssumptionSetResponse:
    return await reference_service.get_assumption_set(version, db)
