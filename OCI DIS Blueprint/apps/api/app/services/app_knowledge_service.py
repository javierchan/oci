"""Grounded App workflow knowledge for the contextual assistant."""

from __future__ import annotations

import re
from typing import cast

from app.knowledge.builder import retrieve_knowledge


MARKDOWN_ROUTE_PATTERN = re.compile(r"\]\((/[^)\s]+)\)")
CSV_CLAIM_PATTERN = re.compile(r"\b(?:csv|comma[- ]separated)\b", re.IGNORECASE)
FEATURE_ASSERTION_PATTERN = re.compile(
    r"\b(?:can|allows?|supports?|lets? you|puede|permite|soporta)\b",
    re.IGNORECASE,
)


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _resolve_route(route: str, *, project_id: str | None, integration_id: str | None) -> str:
    resolved = route
    if project_id:
        resolved = resolved.replace("[projectId]", project_id)
    if integration_id:
        resolved = resolved.replace("[integrationId]", integration_id)
    return resolved


def build_app_knowledge_evidence(
    question: str,
    current_route: str,
    *,
    language: str,
    project_id: str | None,
    integration_id: str | None,
) -> dict[str, object]:
    """Retrieve bounded product facts and add a safe deterministic answer."""

    evidence = retrieve_knowledge(question, current_route)
    entries = [dict(item) for item in _as_list(evidence.get("entries")) if isinstance(item, dict)]
    for entry in entries:
        entry["routes"] = [
            _resolve_route(str(route), project_id=project_id, integration_id=integration_id)
            for route in _as_list(entry.get("routes"))
        ]
    evidence["entries"] = entries
    evidence["allowed_routes"] = sorted(
        {
            str(route)
            for entry in entries
            for route in cast(list[object], entry.get("routes") or [])
        }
    )
    evidence["answer_contract"] = {
        "authority": "app_knowledge",
        "rule": "Feature, workflow, route, and export claims must be present in these entries.",
        "unknown_fallback": "not_documented",
    }
    evidence["fallback_answer"] = deterministic_knowledge_answer(evidence, language=language)
    return evidence


def deterministic_knowledge_answer(evidence: dict[str, object], *, language: str) -> str:
    """Explain a documented workflow without provider inference."""

    entries = [item for item in _as_list(evidence.get("entries")) if isinstance(item, dict)]
    if not evidence.get("documented") or not entries:
        return (
            "No tengo esa capacidad documentada en OCI DIS Architect. Revisa [Projects](/projects) "
            "o agrega el contexto de la vista relacionada."
            if language == "es"
            else "I don't have that capability documented in OCI DIS Architect. Check "
            "[Projects](/projects) or add the related view as context."
        )
    entry = entries[0]
    name = str(entry.get("name") or "OCI DIS Architect")
    purpose = str(entry.get("purpose") or "")
    when_to_use = str(entry.get("when_to_use") or "")
    steps = [str(step) for step in _as_list(entry.get("steps"))][:4]
    routes = [str(route) for route in _as_list(entry.get("routes"))]
    route = routes[0] if routes else "/projects"
    if language == "es":
        intro = f"**{name}** existe para {purpose[:1].lower() + purpose[1:] if purpose else 'guiar este flujo gobernado'}."
        usage = f"**Cuándo usarlo:** {when_to_use}" if when_to_use else ""
        step_text = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
        return "\n\n".join(
            item for item in (intro, usage, f"**Cómo proceder**\n{step_text}" if step_text else "", f"**Siguiente paso:** [Abrir {name}]({route})") if item
        )
    intro = f"**{name}** exists to {purpose[:1].lower() + purpose[1:] if purpose else 'guide this governed workflow'}."
    usage = f"**When to use it:** {when_to_use}" if when_to_use else ""
    step_text = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    return "\n\n".join(
        item for item in (intro, usage, f"**How to proceed**\n{step_text}" if step_text else "", f"**Next action:** [Open {name}]({route})") if item
    )


def knowledge_grounding_failure(summary: str, evidence: dict[str, object]) -> str | None:
    """Reject unsupported App capabilities, routes, and export formats."""

    knowledge = evidence.get("app_knowledge")
    if not isinstance(knowledge, dict):
        # Unit-level normalizers and specialized agents may intentionally pass
        # bounded domain evidence without the App workflow contract. The real
        # support flow always injects app_knowledge before provider inference.
        return None
    allowed_routes = {str(route).rstrip("/") or "/" for route in _as_list(knowledge.get("allowed_routes"))}
    for route in MARKDOWN_ROUTE_PATTERN.findall(summary):
        candidate = route.split("?", 1)[0].rstrip("/") or "/"
        if candidate not in allowed_routes:
            return "unsupported_app_route"
    allowed_media = {str(item).casefold() for item in _as_list(knowledge.get("allowed_export_media_types"))}
    if CSV_CLAIM_PATTERN.search(summary) and not any("csv" in item for item in allowed_media):
        return "unsupported_export_format"
    normalized = summary.casefold()
    for entry in _as_list(knowledge.get("entries")):
        if not isinstance(entry, dict):
            continue
        for claim in _as_list(entry.get("unsupported_claims")):
            candidate = str(claim).casefold().strip()
            if candidate and candidate in normalized:
                return "unsupported_app_capability"
    app_redirect = evidence.get("app_redirect")
    is_governed_redirect = isinstance(app_redirect, dict) and app_redirect.get("required") is True
    if (
        FEATURE_ASSERTION_PATTERN.search(summary)
        and not knowledge.get("documented")
        and not is_governed_redirect
    ):
        return "undocumented_app_capability"
    return None
