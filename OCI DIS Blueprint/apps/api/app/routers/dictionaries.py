"""Dictionaries router — governed dropdown values."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.reference import DictionaryCategoryListResponse, DictionaryOptionListResponse
from app.services import reference_service

router = APIRouter(prefix="/dictionaries", tags=["Dictionaries"])


@router.get("/", response_model=DictionaryCategoryListResponse, summary="List all dictionary categories")
async def list_categories(db: AsyncSession = Depends(get_db)) -> DictionaryCategoryListResponse:
    return await reference_service.list_dictionary_categories(db)


@router.get("/{category}", response_model=DictionaryOptionListResponse, summary="List options for a category")
async def list_options(category: str, db: AsyncSession = Depends(get_db)) -> DictionaryOptionListResponse:
    return await reference_service.list_dictionary_options(category, db)
