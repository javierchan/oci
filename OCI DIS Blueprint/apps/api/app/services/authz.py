"""Service-layer authorization helpers for governed role-scoped actions."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException

ROLE_ALIASES = {
    "admin": "Admin",
    "architect": "Architect",
    "analyst": "Analyst",
    "viewer": "Viewer",
}


def normalize_role(actor_role: str | None) -> str:
    """Return the canonical role name for user-supplied role headers."""

    return ROLE_ALIASES.get((actor_role or "").strip().lower(), "")


def require_roles(actor_role: str | None, allowed_roles: Iterable[str], *, error_code: str) -> None:
    """Require one of the allowed roles for a service-layer operation."""

    normalized = normalize_role(actor_role)
    allowed = {normalize_role(role) for role in allowed_roles}
    if normalized not in allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "detail": f"Role required: {', '.join(sorted(role for role in allowed if role))}",
                "error_code": error_code,
            },
        )


def require_admin(actor_role: str | None) -> None:
    """Require an admin-scoped actor role for mutation endpoints."""

    require_roles(actor_role, {"Admin"}, error_code="ADMIN_ROLE_REQUIRED")


def require_ai_review_read(actor_role: str | None) -> None:
    """Allow all product roles to inspect AI review evidence."""

    require_roles(
        actor_role,
        {"Admin", "Architect", "Analyst", "Viewer"},
        error_code="AI_REVIEW_READ_ROLE_REQUIRED",
    )


def require_ai_review_run(actor_role: str | None) -> None:
    """Require a role that can create governed review jobs."""

    require_roles(
        actor_role,
        {"Admin", "Architect", "Analyst"},
        error_code="AI_REVIEW_RUN_ROLE_REQUIRED",
    )


def require_ai_review_mutation(actor_role: str | None) -> None:
    """Require a role that can accept/apply AI review governance actions."""

    require_roles(
        actor_role,
        {"Admin", "Architect"},
        error_code="AI_REVIEW_MUTATION_ROLE_REQUIRED",
    )
