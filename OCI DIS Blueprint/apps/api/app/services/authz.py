"""Minimal service-layer authorization helpers for governed admin actions."""

from __future__ import annotations

from fastapi import HTTPException


def require_admin(actor_role: str | None) -> None:
    """Require an admin-scoped actor role for mutation endpoints."""

    if (actor_role or "").strip().lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail={"detail": "Admin role required", "error_code": "ADMIN_ROLE_REQUIRED"},
        )
