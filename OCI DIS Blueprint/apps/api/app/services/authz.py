"""Service-layer authorization helpers for governed role-scoped actions."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re

from fastapi import HTTPException

ROLE_ALIASES = {
    "admin": "Admin",
    "architect": "Architect",
    "analyst": "Analyst",
    "viewer": "Viewer",
}

PROJECT_ROLE_ALIASES = {
    "owner": "Owner",
    "contributor": "Contributor",
    "viewer": "Viewer",
}


@dataclass(frozen=True, slots=True)
class MutationPolicy:
    """One explicit API mutation authorization rule.

    Policies are evaluated in declaration order. Every protected unsafe request
    must match a rule; an uncovered mutation is rejected instead of inheriting a
    permissive default.
    """

    methods: frozenset[str]
    path_pattern: re.Pattern[str]
    app_roles: frozenset[str]
    project_roles: frozenset[str] | None = None
    project_context_required: bool = True
    error_code: str = "ACTION_ROLE_REQUIRED"


ALL_APP_ROLES = frozenset({"Admin", "Architect", "Analyst", "Viewer"})
PROJECT_WRITERS = frozenset({"Owner", "Contributor"})
PROJECT_OWNERS = frozenset({"Owner"})
PROJECT_READERS = frozenset({"Owner", "Contributor", "Viewer"})
DESIGNERS = frozenset({"Admin", "Architect"})
CONTRIBUTORS = frozenset({"Admin", "Architect", "Analyst"})
ADMINS = frozenset({"Admin"})


def _policy(
    methods: Iterable[str],
    pattern: str,
    app_roles: frozenset[str],
    *,
    project_roles: frozenset[str] | None = None,
    project_context_required: bool = True,
    error_code: str = "ACTION_ROLE_REQUIRED",
) -> MutationPolicy:
    return MutationPolicy(
        methods=frozenset(method.upper() for method in methods),
        path_pattern=re.compile(pattern),
        app_roles=app_roles,
        project_roles=project_roles,
        project_context_required=project_context_required,
        error_code=error_code,
    )


# Central HTTP mutation policy. Route-local and service-owned checks remain as
# defense in depth, but this registry guarantees that a missing local check can
# never make a protected mutation permissive.
MUTATION_POLICIES: tuple[MutationPolicy, ...] = (
    # Personal assistant state and export generation are valid Viewer actions.
    _policy({"POST", "DELETE"}, r"^/api/v1/support/", ALL_APP_ROLES),
    _policy({"POST"}, r"^/api/v1/exports/[^/]+/(?:xlsx|pdf|json)$", ALL_APP_ROLES, project_roles=PROJECT_READERS),
    _policy({"POST"}, r"^/api/v1/catalog/[^/]+/estimate$", ALL_APP_ROLES, project_roles=PROJECT_READERS),
    _policy({"POST"}, r"^/api/v1/ai-reviews/projects/[^/]+/integrations/[^/]+/simulate-draft$", ALL_APP_ROLES, project_roles=PROJECT_READERS),

    # Global governance and platform administration.
    _policy({"POST", "PATCH", "DELETE"}, r"^/api/v1/(?:patterns|dictionaries|assumptions)(?:/|$)", ADMINS, error_code="ADMIN_ROLE_REQUIRED"),
    _policy({"POST", "PATCH", "PUT", "DELETE"}, r"^/api/v1/admin/", ADMINS, error_code="ADMIN_ROLE_REQUIRED"),
    _policy({"POST", "PATCH", "DELETE"}, r"^/api/v1/pricing/", ADMINS, error_code="ADMIN_ROLE_REQUIRED"),
    _policy({"POST", "PATCH", "DELETE"}, r"^/api/v1/service-products/", ADMINS, error_code="ADMIN_ROLE_REQUIRED"),
    _policy({"POST", "PATCH", "DELETE"}, r"^/api/v1/justifications/templates(?:/|$)", ADMINS, error_code="ADMIN_ROLE_REQUIRED"),
    _policy({"POST"}, r"^/api/v1/agents/knowledge-maintenance/", ADMINS, error_code="ADMIN_ROLE_REQUIRED"),

    # Agent execution. Definition-specific service checks narrow this further.
    _policy({"POST"}, r"^/api/v1/agents/runs$", CONTRIBUTORS),
    _policy(
        {"POST"},
        r"^/api/v1/agents/runs/[^/]+/cancel$",
        CONTRIBUTORS,
        project_roles=PROJECT_WRITERS,
        project_context_required=False,
    ),
    _policy(
        {"POST"},
        r"^/api/v1/agents/runs/[^/]+/approvals/[^/]+(?:/execute)?$",
        DESIGNERS,
        project_roles=PROJECT_WRITERS,
        project_context_required=False,
    ),

    # Project creation and lifecycle. Lifecycle operations require ownership.
    _policy({"POST"}, r"^/api/v1/projects/$", CONTRIBUTORS),
    _policy({"PATCH", "POST"}, r"^/api/v1/projects/[^/]+(?:/archive)?$", CONTRIBUTORS, project_roles=PROJECT_OWNERS, error_code="PROJECT_OWNER_REQUIRED"),
    _policy({"DELETE"}, r"^/api/v1/projects/[^/]+$", DESIGNERS, project_roles=PROJECT_OWNERS, error_code="PROJECT_OWNER_REQUIRED"),

    # Imports and agent-led correction are Analyst work; project Viewers cannot mutate.
    _policy({"POST", "PATCH", "DELETE"}, r"^/api/v1/imports/", CONTRIBUTORS, project_roles=PROJECT_WRITERS),

    # Catalog capture/bulk QA is contributor work; architect-owned row decisions
    # and destructive removal require Architect or Admin.
    _policy({"POST"}, r"^/api/v1/catalog/[^/]+(?:/refresh-qa|/bulk-patch)?$", CONTRIBUTORS, project_roles=PROJECT_WRITERS),
    _policy({"PATCH", "DELETE"}, r"^/api/v1/catalog/[^/]+/[^/]+$", DESIGNERS, project_roles=PROJECT_WRITERS),
    _policy({"POST"}, r"^/api/v1/recalculate/", CONTRIBUTORS, project_roles=PROJECT_WRITERS),

    # Architecture approvals and governed justifications.
    _policy({"POST", "DELETE"}, r"^/api/v1/justifications/[^/]+/[^/]+(?:/(?:approve|override))?$", DESIGNERS, project_roles=PROJECT_WRITERS),
    _policy({"POST"}, r"^/api/v1/ai-reviews/projects/[^/]+$", CONTRIBUTORS, project_roles=PROJECT_WRITERS),
    _policy({"POST"}, r"^/api/v1/ai-reviews/projects/[^/]+/baseline$", DESIGNERS, project_roles=PROJECT_WRITERS),
    _policy({"POST"}, r"^/api/v1/ai-reviews/[^/]+/(?:findings/[^/]+/(?:accept|apply-patch)|recommendations/[^/]+/select-draft)$", DESIGNERS, project_roles=PROJECT_WRITERS),

    # BOM planning: Analysts may draft/run; Architects approve and publish.
    _policy({"POST"}, r"^/api/v1/projects/[^/]+/deployment-scenarios(?:/agent)?$", CONTRIBUTORS, project_roles=PROJECT_WRITERS),
    _policy({"POST"}, r"^/api/v1/projects/[^/]+/deployment-scenarios/[^/]+/approve$", DESIGNERS, project_roles=PROJECT_WRITERS),
    _policy({"POST"}, r"^/api/v1/projects/[^/]+/bom-jobs$", CONTRIBUTORS, project_roles=PROJECT_WRITERS),
    _policy({"POST"}, r"^/api/v1/projects/[^/]+/bom-snapshots/[^/]+/review$", DESIGNERS, project_roles=PROJECT_WRITERS),

    # External import/correction review and project coordination.
    _policy({"POST"}, r"^/api/v1/projects/[^/]+/external-capture/sessions(?:/[^/]+/(?:drafts/bulk|corrections/apply))?$", CONTRIBUTORS, project_roles=PROJECT_WRITERS),
    _policy({"PATCH"}, r"^/api/v1/projects/[^/]+/external-capture/sessions/[^/]+/drafts/[^/]+$", CONTRIBUTORS, project_roles=PROJECT_WRITERS),
    _policy({"POST"}, r"^/api/v1/projects/[^/]+/external-capture/sessions/[^/]+/drafts/[^/]+/(?:review|promote)$", DESIGNERS, project_roles=PROJECT_WRITERS),
    _policy({"POST", "PATCH", "DELETE"}, r"^/api/v1/projects/[^/]+/(?:saved-views|attention-tasks)(?:/[^/]+)?$", CONTRIBUTORS, project_roles=PROJECT_WRITERS),
)


def normalize_role(actor_role: str | None) -> str:
    """Return the canonical role name for user-supplied role headers."""

    return ROLE_ALIASES.get((actor_role or "").strip().lower(), "")


def normalize_project_role(project_role: str | None) -> str:
    """Return a canonical project membership role or an empty value."""

    return PROJECT_ROLE_ALIASES.get((project_role or "").strip().lower(), "")


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


def authorize_mutation(
    *,
    method: str,
    path: str,
    actor_role: str | None,
    project_role: str | None,
) -> None:
    """Authorize one protected unsafe HTTP request through the central policy.

    Safe requests are governed by authentication, project membership, token
    scopes, and existing read-role checks. Unsafe requests must match exactly one
    explicit policy and satisfy both the App and project role boundaries.
    """

    normalized_method = method.upper()
    if normalized_method in {"GET", "HEAD", "OPTIONS"}:
        return
    policy = next(
        (
            candidate
            for candidate in MUTATION_POLICIES
            if normalized_method in candidate.methods and candidate.path_pattern.match(path)
        ),
        None,
    )
    if policy is None:
        raise HTTPException(
            status_code=403,
            detail={
                "detail": "This mutation has no governed authorization policy.",
                "error_code": "MUTATION_POLICY_REQUIRED",
            },
        )
    require_roles(actor_role, policy.app_roles, error_code=policy.error_code)
    if policy.project_roles is None:
        return
    normalized_project_role = normalize_project_role(project_role)
    if not normalized_project_role and not policy.project_context_required:
        return
    if normalized_project_role not in policy.project_roles:
        raise HTTPException(
            status_code=403,
            detail={
                "detail": "The project membership does not grant this action.",
                "error_code": "PROJECT_ROLE_REQUIRED",
                "allowed_project_roles": sorted(policy.project_roles),
            },
        )


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
