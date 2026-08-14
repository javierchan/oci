"""Fail-closed authorization coverage for every protected API mutation."""

from __future__ import annotations

import re

from fastapi import HTTPException
import pytest

from app.main import app
from app.services.authz import authorize_mutation


UNSAFE_METHODS = {"post", "put", "patch", "delete"}


def _concrete_path(path_template: str) -> str:
    return re.sub(r"\{[^}]+\}", "sample", path_template)


def test_every_protected_mutation_has_explicit_policy() -> None:
    uncovered: list[str] = []
    schema = app.openapi()
    for path, operations in schema["paths"].items():
        if not path.startswith("/api/v1/") or path.startswith("/api/v1/auth/"):
            continue
        for method in UNSAFE_METHODS & set(operations):
            try:
                authorize_mutation(
                    method=method,
                    path=_concrete_path(path),
                    actor_role="Admin",
                    project_role="Owner",
                )
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {}
                if detail.get("error_code") == "MUTATION_POLICY_REQUIRED":
                    uncovered.append(f"{method.upper()} {path}")
                else:
                    raise
    assert uncovered == []


@pytest.mark.parametrize(
    ("method", "path", "app_role", "project_role", "error_code"),
    [
        ("PATCH", "/api/v1/catalog/project/integration", "Viewer", "Viewer", "ACTION_ROLE_REQUIRED"),
        ("PATCH", "/api/v1/catalog/project/integration", "Architect", "Viewer", "PROJECT_ROLE_REQUIRED"),
        ("DELETE", "/api/v1/projects/project", "Admin", "Contributor", "PROJECT_ROLE_REQUIRED"),
        ("POST", "/api/v1/justifications/templates", "Architect", None, "ADMIN_ROLE_REQUIRED"),
        ("POST", "/api/v1/unknown/mutation", "Admin", None, "MUTATION_POLICY_REQUIRED"),
    ],
)
def test_mutation_policy_denies_invalid_role_combinations(
    method: str,
    path: str,
    app_role: str,
    project_role: str | None,
    error_code: str,
) -> None:
    with pytest.raises(HTTPException) as raised:
        authorize_mutation(
            method=method,
            path=path,
            actor_role=app_role,
            project_role=project_role,
        )
    assert raised.value.status_code == 403
    assert raised.value.detail["error_code"] == error_code


@pytest.mark.parametrize(
    ("method", "path", "app_role", "project_role"),
    [
        ("POST", "/api/v1/imports/project", "Analyst", "Contributor"),
        ("PATCH", "/api/v1/catalog/project/integration", "Architect", "Contributor"),
        ("POST", "/api/v1/exports/project/xlsx", "Viewer", "Viewer"),
        ("POST", "/api/v1/support/conversations/current", "Viewer", None),
        ("DELETE", "/api/v1/projects/project", "Admin", "Owner"),
    ],
)
def test_mutation_policy_allows_governed_role_combinations(
    method: str,
    path: str,
    app_role: str,
    project_role: str | None,
) -> None:
    authorize_mutation(
        method=method,
        path=path,
        actor_role=app_role,
        project_role=project_role,
    )
