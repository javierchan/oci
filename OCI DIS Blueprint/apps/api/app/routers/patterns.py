"""Patterns router — served from seeded reference data."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.reference import PatternDefinitionResponse, PatternListResponse
from app.services import reference_service

router = APIRouter(prefix="/patterns", tags=["Patterns"])


@router.get("", response_model=PatternListResponse, include_in_schema=False)
@router.get("/", response_model=PatternListResponse, summary="List all integration patterns")
async def list_patterns(db: AsyncSession = Depends(get_db)) -> PatternListResponse:
    return await reference_service.list_patterns(db)


@router.get("/{pattern_id}", response_model=PatternDefinitionResponse, summary="Get a pattern by ID (e.g. #01)")
async def get_pattern(pattern_id: str, db: AsyncSession = Depends(get_db)) -> PatternDefinitionResponse:
    return await reference_service.get_pattern(pattern_id, db)
