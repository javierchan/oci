"""Assumptions router — /assumptions."""
from fastapi import APIRouter

router = APIRouter(prefix="/assumptions", tags=["Assumptions"])


@router.get("/", summary="List assumption sets")
async def list_assumption_sets():
    return {"assumption_sets": []}


@router.get("/{version}", summary="Get assumption set by version")
async def get_assumption_set(version: str):
    return {}


@router.get("/default", summary="Get default assumption set")
async def get_default():
    return {}
