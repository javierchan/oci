"""Semantic, governed App knowledge for the contextual assistant."""

from __future__ import annotations

import re
from typing import cast

from app.core.config import get_genai_settings_for_use_case
from app.knowledge.builder import (
    load_derived_manifest,
    local_semantic_embedding,
    retrieve_semantic_knowledge,
)
from app.services.genai_client import generate_embeddings


MARKDOWN_ROUTE_PATTERN = re.compile(r"\]\((/[^)\s]+)\)")
CSV_CLAIM_PATTERN = re.compile(r"\b(?:csv|comma[- ]separated)\b", re.IGNORECASE)
FEATURE_ASSERTION_PATTERN = re.compile(
    r"\b(?:can|allows?|supports?|lets? you|puede|permite|soporta)\b",
    re.IGNORECASE,
)
CAPABILITY_ABSTENTION_PATTERN = re.compile(
    r"\b(?:not (?:a )?documented|is not documented|does not document|not supported by the documented|"
    r"no (?:es|esta|está) documentad[oa]|no figura como (?:una )?capacidad documentada|"
    r"no (?:se )?documenta (?:esa|esta) capacidad)\b",
    re.IGNORECASE,
)
NEXT_ACTION_PATTERN = re.compile(r"\*\*(?:Next action|Siguiente paso):\*\*", re.IGNORECASE)
CAPABILITY_QUERY_PATTERN = re.compile(
    r"^\s*(?:can\s+(?:i|we|one|users?|the\s+app|this\s+app)|"
    r"could\s+(?:i|we|one|users?)|does\s+(?:the\s+app|this\s+app)|"
    r"do\s+(?:i|we|users?)|is\s+it\s+possible|may\s+(?:i|we))\b|"
    r"^\s*(?:puedo|podemos|puede\s+(?:la\s+app|esta\s+app|un\s+usuario)|"
    r"permite\s+(?:la\s+app|esta\s+app)|es\s+posible)\b",
    re.IGNORECASE,
)
WORKFLOW_QUERY_PATTERN = re.compile(
    r"^\s*(?:how\s+(?:do|can|should)\b|what\s+(?:steps|process)\b)|"
    r"^\s*(?:c[oó]mo\s+(?:puedo|podemos|se|debo)\b|qu[eé]\s+pasos\b)",
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
    if "[" in resolved or "{" in resolved:
        return "/projects"
    return resolved


def _has_provider_vectors() -> bool:
    manifest = load_derived_manifest()
    units = _as_list(manifest.get("retrieval_units"))
    return any(
        isinstance(unit, dict) and isinstance(unit.get("provider_embedding"), list)
        for unit in units
    )


def explicit_intent_cue(question: str) -> str | None:
    """Return only high-signal query-shape cues; topic selection stays semantic."""

    if CAPABILITY_QUERY_PATTERN.search(question):
        return "capability_inquiry"
    if WORKFLOW_QUERY_PATTERN.search(question):
        return "workflow_guidance"
    return None


async def _semantic_query(question: str, current_route: str) -> dict[str, object]:
    """Embed once, prefer OCI vectors, and fall back without changing behavior."""

    embedding_space = "local"
    query_embedding = local_semantic_embedding(question)
    if _has_provider_vectors():
        result = await generate_embeddings(
            [question],
            get_genai_settings_for_use_case("support_assistant"),
            input_type="SEARCH_QUERY",
        )
        if result.status == "completed" and len(result.embeddings) == 1:
            query_embedding = result.embeddings[0]
            embedding_space = "provider"
    evidence = retrieve_semantic_knowledge(
        question,
        current_route,
        query_embedding=query_embedding,
        embedding_space=embedding_space,
        limit=5,
    )
    intent_cue = explicit_intent_cue(question)
    if intent_cue and evidence.get("mode") != "boundary":
        matches = [item for item in _as_list(evidence.get("matches")) if isinstance(item, dict)]
        intent_match = next(
            (item for item in matches if item.get("intent") == intent_cue),
            None,
        )
        if intent_match is not None:
            evidence["top_match"] = intent_match
            evidence["intent"] = intent_cue
            selected_section_id = str(intent_match.get("section_id") or "")
            entries = [item for item in _as_list(evidence.get("entries")) if isinstance(item, dict)]
            evidence["entries"] = sorted(
                entries,
                key=lambda item: str(item.get("id") or "") != selected_section_id,
            )
    return evidence


def _project_entries(
    evidence: dict[str, object],
    *,
    project_id: str | None,
    integration_id: str | None,
) -> list[dict[str, object]]:
    entries = [dict(item) for item in _as_list(evidence.get("entries")) if isinstance(item, dict)]
    for entry in entries:
        entry["routes"] = [
            _resolve_route(
                str(route),
                project_id=project_id,
                integration_id=integration_id,
            )
            for route in _as_list(entry.get("routes"))
        ]
    return entries


async def build_app_knowledge_evidence(
    question: str,
    current_route: str,
    *,
    language: str,
    project_id: str | None,
    integration_id: str | None,
    capability_inquiry: bool | None = None,
) -> dict[str, object]:
    """Retrieve the closest governed KB unit and build a provider-safe fallback."""

    del capability_inquiry
    evidence = await _semantic_query(question, current_route)
    entries = _project_entries(
        evidence,
        project_id=project_id,
        integration_id=integration_id,
    )
    evidence["entries"] = entries
    top_match = evidence.get("top_match")
    top = top_match if isinstance(top_match, dict) else {}
    if str(evidence.get("intent")) == "capability_inquiry":
        status = str(top.get("capability_status") or "not_documented")
        closest = entries[0] if entries else None
        evidence["capability_assessment"] = {
            "status": status,
            "reason": "The semantic match resolves to an explicit governed capability record.",
            "matched_actions": (
                [{"section_id": str(top.get("section_id") or ""), "action": str(top.get("answer") or "")}]
                if status == "documented"
                else []
            ),
            "matched_entries": entries[:1] if status == "documented" else [],
            "closest_entry": closest,
        }
    evidence["allowed_routes"] = sorted(
        {
            str(route)
            for entry in entries
            for route in cast(list[object], entry.get("routes") or [])
        }
    )
    evidence["answer_contract"] = {
        "authority": "app_knowledge",
        "rule": "Feature, workflow, route, and export claims must be present in the semantic KB result.",
        "unknown_fallback": "not_documented",
    }
    evidence["fallback_answer"] = deterministic_knowledge_answer(evidence, language=language)
    return evidence


def _entry_route(entry: dict[str, object]) -> str:
    routes = [str(route) for route in _as_list(entry.get("routes"))]
    return next((candidate for candidate in routes if candidate != "/"), routes[0] if routes else "/projects")


def deterministic_knowledge_answer(evidence: dict[str, object], *, language: str) -> str:
    """Explain the semantic decision when inference is unavailable or withheld."""

    top_match = evidence.get("top_match")
    top = top_match if isinstance(top_match, dict) else {}
    entries = [item for item in _as_list(evidence.get("entries")) if isinstance(item, dict)]
    entry = entries[0] if entries else {}
    intent = str(evidence.get("intent") or "concept_explanation")
    mode = str(evidence.get("mode") or "knowledge")
    name = str(entry.get("name") or "OCI DIS Architect")
    route = _entry_route(entry)
    if mode == "boundary":
        if language == "es":
            return (
                "No puedo ayudar con esa solicitud porque está fuera del alcance de OCI DIS Architect. "
                "Puedo explicar evidencia gobernada de integraciones, arquitectura, QA, Pricing o BOM & Cost.\n\n"
                "**Siguiente paso:** [Abrir Projects](/projects)"
            )
        return (
            "That request is outside OCI DIS Architect's scope. I can explain governed integration, "
            "architecture, QA, Pricing, or BOM & Cost evidence.\n\n"
            "**Next action:** [Open Projects](/projects)"
        )
    if intent == "capability_inquiry":
        assessment = evidence.get("capability_assessment")
        status = str(assessment.get("status") or "not_documented") if isinstance(assessment, dict) else "not_documented"
        action = str(top.get("answer") or "the requested capability")
        purpose = str(entry.get("purpose") or "")
        if status == "documented":
            if language == "es":
                return (
                    f"**Sí.** OCI DIS Architect documenta **{action}** en **{name}**.\n\n{purpose}\n\n"
                    f"**Siguiente paso:** [Abrir {name}]({route})"
                )
            return (
                f"**Yes.** OCI DIS Architect documents **{action}** in **{name}**.\n\n{purpose}\n\n"
                f"**Next action:** [Open {name}]({route})"
            )
        if language == "es":
            return (
                f"**No.** **{action}** no figura como una capacidad documentada de OCI DIS Architect.\n\n"
                f"**Siguiente paso:** [Abrir {name}]({route})"
            )
        return (
            f"**No.** **{action}** is not documented as an OCI DIS Architect capability.\n\n"
            f"**Next action:** [Open {name}]({route})"
        )
    if intent == "concept_explanation" and top.get("answer"):
        answer = str(top["answer"])
        prefix = "**Concepto:**" if language == "es" else "**Concept:**"
        action = "**Siguiente paso:**" if language == "es" else "**Next action:**"
        open_label = f"Abrir {name}" if language == "es" else f"Open {name}"
        return f"**{name}**\n\n{prefix} {answer}\n\n{action} [{open_label}]({route})"
    purpose = str(entry.get("purpose") or "")
    when_to_use = str(entry.get("when_to_use") or "")
    steps = [str(step) for step in _as_list(entry.get("steps"))][:4]
    if intent == "workflow_guidance" and steps:
        heading = "**Cómo proceder**" if language == "es" else "**How to proceed**"
        step_text = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
        action = "**Siguiente paso:**" if language == "es" else "**Next action:**"
        open_label = f"Abrir {name}" if language == "es" else f"Open {name}"
        return f"**{name}**\n\n{heading}\n{step_text}\n\n{action} [{open_label}]({route})"
    if language == "es":
        return (
            f"**{name}** existe para {purpose[:1].lower() + purpose[1:] if purpose else 'guiar este flujo gobernado'}.\n\n"
            f"**Cuándo usarlo:** {when_to_use}\n\n**Siguiente paso:** [Abrir {name}]({route})"
        )
    return (
        f"**{name}** exists to {purpose[:1].lower() + purpose[1:] if purpose else 'guide this governed workflow'}.\n\n"
        f"**When to use it:** {when_to_use}\n\n**Next action:** [Open {name}]({route})"
    )


def knowledge_grounding_failure(summary: str, evidence: dict[str, object]) -> str | None:
    """Reject unsupported App capabilities, routes, and export formats."""

    knowledge = evidence.get("app_knowledge")
    if not isinstance(knowledge, dict):
        return None
    allowed_routes = {str(route).rstrip("/") or "/" for route in _as_list(knowledge.get("allowed_routes"))}
    for route in MARKDOWN_ROUTE_PATTERN.findall(summary):
        candidate = route.split("?", 1)[0].rstrip("/") or "/"
        if candidate not in allowed_routes:
            return "unsupported_app_route"
    allowed_media = {str(item).casefold() for item in _as_list(knowledge.get("allowed_export_media_types"))}
    if CSV_CLAIM_PATTERN.search(summary) and not any("csv" in item for item in allowed_media):
        return "unsupported_export_format"
    assessment = knowledge.get("capability_assessment")
    if len(NEXT_ACTION_PATTERN.findall(summary)) != 1:
        return "invalid_next_action_count"
    if isinstance(assessment, dict) and assessment.get("status") == "not_documented":
        if not CAPABILITY_ABSTENTION_PATTERN.search(summary):
            return "undocumented_app_capability"
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
    if FEATURE_ASSERTION_PATTERN.search(summary) and not knowledge.get("documented") and not is_governed_redirect:
        return "undocumented_app_capability"
    return None
