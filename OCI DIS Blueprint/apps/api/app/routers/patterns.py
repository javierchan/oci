"""Patterns router — /patterns."""
from fastapi import APIRouter

router = APIRouter(prefix="/patterns", tags=["Patterns"])


@router.get("/", summary="List all integration patterns")
async def list_patterns():
    return {"patterns": []}


@router.get("/{pattern_id}", summary="Get a pattern by ID (e.g. #01)")
async def get_pattern(pattern_id: str):
    return {}
