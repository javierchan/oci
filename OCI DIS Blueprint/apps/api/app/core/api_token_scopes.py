"""Governed read-only capability scopes for external API tokens."""

from __future__ import annotations

from dataclasses import dataclass


LEGACY_API_READ_SCOPE = "api:read"


@dataclass(frozen=True, slots=True)
class ApiTokenScopeDefinition:
    code: str
    label: str
    description: str


API_TOKEN_SCOPE_CATALOG = (
    ApiTokenScopeDefinition("identity:read", "Identity", "Read the token owner's App identity."),
    ApiTokenScopeDefinition("projects:read", "Projects", "List and inspect authorized projects."),
    ApiTokenScopeDefinition(
        "integrations:read",
        "Integrations",
        "Read imports, capture evidence, catalog records, lineage, and topology.",
    ),
    ApiTokenScopeDefinition(
        "architecture:read",
        "Architecture",
        "Read dashboards, volumetry, justifications, and architecture reviews.",
    ),
    ApiTokenScopeDefinition(
        "commercial:read",
        "BOM & pricing",
        "Read deployment scenarios, selectable products, pricing evidence, and BOM snapshots.",
    ),
    ApiTokenScopeDefinition(
        "governance:read",
        "Governance",
        "Read patterns, dictionaries, assumptions, and Service Product rules.",
    ),
    ApiTokenScopeDefinition("audit:read", "Audit", "Read project audit events."),
    ApiTokenScopeDefinition("exports:read", "Exports", "Read export metadata and download artifacts."),
    ApiTokenScopeDefinition("agents:read", "Agents", "Read authorized agent definitions and runs."),
)

ALL_API_TOKEN_SCOPES = frozenset(item.code for item in API_TOKEN_SCOPE_CATALOG)


def required_scope_for_path(path: str) -> str | None:
    """Map one safe API path to its least-privilege read capability."""

    if path == "/api/v1/auth/me":
        return "identity:read"
    if path.startswith("/api/v1/catalog/") or path.startswith("/api/v1/imports/"):
        return "integrations:read"
    if path.startswith((
        "/api/v1/dashboard/",
        "/api/v1/volumetry/",
        "/api/v1/justifications/",
        "/api/v1/ai-reviews/",
        "/api/v1/recalculate/",
    )):
        return "architecture:read"
    if path.startswith("/api/v1/pricing/"):
        return "commercial:read"
    if path.startswith((
        "/api/v1/patterns/",
        "/api/v1/dictionaries/",
        "/api/v1/assumptions/",
        "/api/v1/service-products",
    )):
        return "governance:read"
    if path.startswith("/api/v1/audit/"):
        return "audit:read"
    if path.startswith("/api/v1/exports/"):
        return "exports:read"
    if path.startswith("/api/v1/agents"):
        return "agents:read"
    if path.startswith("/api/v1/projects/"):
        nested_commercial = (
            "/bom-",
            "/deployment-scenarios",
            "/selectable-products",
        )
        if any(fragment in path for fragment in nested_commercial):
            return "commercial:read"
        if "/external-capture/" in path:
            return "integrations:read"
        return "projects:read"
    return None
