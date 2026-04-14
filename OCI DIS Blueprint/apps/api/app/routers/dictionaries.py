"""Dictionaries router — /dictionaries."""
from fastapi import APIRouter

router = APIRouter(prefix="/dictionaries", tags=["Dictionaries"])


@router.get("/", summary="List all dictionary categories")
async def list_categories():
    return {"categories": []}


@router.get("/{category}", summary="List options for a category")
async def list_options(category: str):
    return {"category": category, "options": []}
