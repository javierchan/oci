"""Semantic, governed App knowledge for the contextual assistant."""

from __future__ import annotations

import re
from typing import cast

from app.core.config import get_genai_settings_for_use_case
from app.knowledge.builder import (
    load_derived_manifest,
    local_semantic_embedding,
    provider_embedding_errors,
    retrieve_semantic_knowledge,
)
from app.services.genai_client import generate_embeddings


MARKDOWN_ROUTE_PATTERN = re.compile(r"\]\((/[^)\s]+)\)")
CSV_CLAIM_PATTERN = re.compile(r"\b(?:csv|comma[- ]separated)\b", re.IGNORECASE)
CSV_ABSTENTION_PATTERN = re.compile(
    r"\bcsv\b.{0,48}\b(?:not supported|not available|not documented|"
    r"no (?:est[aá]|es) soportad[oa])\b|"
    r"\b(?:no|not)\b.{0,48}\bcsv\b",
    re.IGNORECASE,
)
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
CAPABILITY_POSITIVE_ASSERTION_PATTERN = re.compile(
    r"^\s*(?:\*{0,2})?(?:yes|s[ií])(?:[.!,:*]|\s)|"
    r"\b(?:the|this)\s+app\s+(?:supports?|allows?|can)\b|"
    r"\bla\s+app\s+(?:soporta|permite|puede)\b",
    re.IGNORECASE,
)
NEXT_ACTION_PATTERN = re.compile(r"\*\*Next action:\*\*", re.IGNORECASE)
CAPABILITY_QUERY_PATTERN = re.compile(
    r"^\s*(?:can\s+(?:i|we|one|users?|the\s+app|this\s+app)|"
    r"could\s+(?:i|we|one|users?)|does\s+(?:the\s+app|this\s+app)|"
    r"do\s+(?:i|we|users?)|is\s+it\s+possible|may\s+(?:i|we))\b|"
    r"^\s*(?:qu[eé]\s+puedo|puedo|podemos|puede\s+(?:la\s+app|esta\s+app|un\s+usuario)|"
    r"permite\s+(?:la\s+app|esta\s+app)|es\s+posible)\b",
    re.IGNORECASE,
)
WORKFLOW_QUERY_PATTERN = re.compile(
    r"^\s*(?:how\s+(?:do|can|should)\b|what\s+(?:steps|process)\b|when\s+(?:do|should|can)\b)|"
    r"^\s*(?:c[oó]mo\b|qu[eé]\s+pasos\b|cu[aá]ndo\s+(?:debo|uso|usar|conviene)\b)",
    re.IGNORECASE,
)
CONCEPT_QUERY_PATTERN = re.compile(
    r"^\s*(?:what\s+(?:is|are|does|represents?)\b|explain\b|why\s+does\b)|"
    r"^\s*(?:qu[eé]\s+(?:es|son|hace|hacen|significa|representa|resuelve)\b|"
    r"para\s+qu[eé]\s+sirve\b|explica\b)",
    re.IGNORECASE,
)
TECHNICAL_API_QUERY_PATTERN = re.compile(
    r"\b(api|endpoint|rest|http|curl|request|response|payload json|openapi|"
    r"m[eé]todo http|desarrollador|integraci[oó]n t[eé]cnica)\b",
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


def _provider_model(manifest: dict[str, object]) -> str:
    spaces = manifest.get("embedding_spaces")
    provider = spaces.get("provider") if isinstance(spaces, dict) else None
    return str(provider.get("model") or "") if isinstance(provider, dict) else ""


def explicit_intent_cue(question: str) -> str | None:
    """Return only high-signal query-shape cues; topic selection stays semantic."""

    if CAPABILITY_QUERY_PATTERN.search(question):
        return "capability_inquiry"
    if WORKFLOW_QUERY_PATTERN.search(question):
        return "workflow_guidance"
    if CONCEPT_QUERY_PATTERN.search(question):
        return "concept_explanation"
    return None


async def _semantic_query(question: str, current_route: str) -> dict[str, object]:
    """Embed once; a configured OCI runtime must not silently change vector space."""

    intent_cue = explicit_intent_cue(question)
    embedding_space = "local"
    query_embedding = local_semantic_embedding(question)
    settings = get_genai_settings_for_use_case("support_assistant")
    provider_configured = bool(settings.OCI_GENAI_PROJECT_ID.strip())
    manifest = load_derived_manifest()
    manifest_errors = provider_embedding_errors(
        manifest,
        expected_model=(
            settings.OCI_GENAI_EMBEDDING_MODEL_NAME
            if provider_configured
            else _provider_model(manifest)
        ),
    )
    provider_vectors_available = not manifest_errors
    if provider_configured:
        if manifest_errors:
            raise RuntimeError(
                "provider_embedding_manifest_unavailable:"
                + "; ".join(manifest_errors)
            )
    if provider_vectors_available:
        result = await generate_embeddings(
            [question],
            settings,
            input_type="SEARCH_QUERY",
        )
        if result.status == "completed" and len(result.embeddings) == 1:
            query_embedding = result.embeddings[0]
            embedding_space = "provider"
        elif provider_configured:
            raise RuntimeError(
                f"provider_query_embedding_failed:{result.error or result.status}"
            )
    evidence = retrieve_semantic_knowledge(
        question,
        current_route,
        query_embedding=query_embedding,
        embedding_space=embedding_space,
        intent_hint=intent_cue,
        limit=5,
    )
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
        entry.pop("purpose_es", None)
        entry.pop("when_to_use_es", None)
        entry.pop("steps_es", None)
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

    del capability_inquiry, language
    language = "en"
    evidence = await _semantic_query(question, current_route)
    entries = _project_entries(
        evidence,
        project_id=project_id,
        integration_id=integration_id,
    )
    if not TECHNICAL_API_QUERY_PATTERN.search(question):
        for entry in entries:
            entry.pop("endpoints", None)
            entry.pop("entities", None)
            exports = [
                {"media_types": item.get("media_types", [])}
                for item in _as_list(entry.get("exports"))
                if isinstance(item, dict)
            ]
            if exports:
                entry["exports"] = exports
    evidence["entries"] = entries
    evidence["matches"] = [
        {
            key: item[key]
            for key in (
                "id",
                "kind",
                "section_id",
                "text",
                "intent",
                "mode",
                "capability_status",
                "answer",
                "similarity",
            )
            if key in item
        }
        for item in _as_list(evidence.get("matches"))
        if isinstance(item, dict)
    ]
    if isinstance(evidence.get("top_match"), dict):
        current_top_id = str(cast(dict[str, object], evidence["top_match"]).get("id") or "")
        filtered_matches = cast(list[dict[str, object]], evidence["matches"])
        evidence["top_match"] = next(
            (
                item
                for item in filtered_matches
                if item.get("id") == current_top_id
            ),
            filtered_matches[0] if filtered_matches else {},
        )
    top_match = evidence.get("top_match")
    top = top_match if isinstance(top_match, dict) else {}
    if top.get("answer"):
        evidence["answer_focus"] = {
            "status": "complete_for_current_question",
            "answer": str(top["answer"]),
            "rule": "Explain this bounded answer naturally without adding undocumented artifacts or behavior.",
        }
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


def _localized_entry_value(
    entry: dict[str, object],
    field: str,
    *,
    language: str,
) -> object:
    """Return the canonical English knowledge value.

    ``language`` remains in the internal call contract for backward compatibility,
    but governed App output is English-only.
    """

    _ = language
    return entry.get(field)


def deterministic_knowledge_answer(evidence: dict[str, object], *, language: str) -> str:
    """Explain the semantic decision when inference is unavailable or withheld."""

    _ = language

    top_match = evidence.get("top_match")
    top = top_match if isinstance(top_match, dict) else {}
    entries = [item for item in _as_list(evidence.get("entries")) if isinstance(item, dict)]
    entry = entries[0] if entries else {}
    intent = str(evidence.get("intent") or "concept_explanation")
    mode = str(evidence.get("mode") or "knowledge")
    name = str(entry.get("name") or "OCI DIS Architect")
    route = _entry_route(entry)
    if mode == "boundary":
        return (
            "That request is outside OCI DIS Architect's scope. I can explain governed integration, "
            "architecture, QA, Pricing, or BOM & Cost evidence.\n\n"
            "**Next action:** [Open Projects](/projects)"
        )
    if intent == "capability_inquiry":
        assessment = evidence.get("capability_assessment")
        status = str(assessment.get("status") or "not_documented") if isinstance(assessment, dict) else "not_documented"
        action = str(top.get("answer") or "the requested capability")
        purpose = str(_localized_entry_value(entry, "purpose", language=language) or "")
        if status == "documented":
            return (
                f"**Yes.** OCI DIS Architect documents **{action}** in **{name}**.\n\n{purpose}\n\n"
                f"**Next action:** [Open {name}]({route})"
            )
        return (
            f"**No.** **{action}** is not documented as an OCI DIS Architect capability.\n\n"
            f"**Next action:** [Open {name}]({route})"
        )
    if intent == "concept_explanation" and top.get("answer"):
        answer = str(top["answer"])
        prefix = "**Concept:**"
        action = "**Next action:**"
        open_label = f"Open {name}"
        return f"**{name}**\n\n{prefix} {answer}\n\n{action} [{open_label}]({route})"
    purpose = str(_localized_entry_value(entry, "purpose", language=language) or "")
    when_to_use = str(
        _localized_entry_value(entry, "when_to_use", language=language) or ""
    )
    steps = [
        str(step)
        for step in _as_list(_localized_entry_value(entry, "steps", language=language))
    ][:4]
    if intent == "workflow_guidance" and steps:
        heading = "**How to proceed**"
        step_text = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
        action = "**Next action:**"
        open_label = f"Open {name}"
        return f"**{name}**\n\n{heading}\n{step_text}\n\n{action} [{open_label}]({route})"
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
    assessment = knowledge.get("capability_assessment")
    is_documented_abstention = (
        isinstance(assessment, dict)
        and assessment.get("status") == "not_documented"
        and bool(CAPABILITY_ABSTENTION_PATTERN.search(summary))
    )
    allowed_media = {str(item).casefold() for item in _as_list(knowledge.get("allowed_export_media_types"))}
    if (
        CSV_CLAIM_PATTERN.search(summary)
        and not any("csv" in item for item in allowed_media)
        and not CSV_ABSTENTION_PATTERN.search(summary)
        and not is_documented_abstention
    ):
        return "unsupported_export_format"
    if len(NEXT_ACTION_PATTERN.findall(summary)) != 1:
        return "invalid_next_action_count"
    if isinstance(assessment, dict) and assessment.get("status") == "not_documented":
        if CAPABILITY_POSITIVE_ASSERTION_PATTERN.search(summary):
            return "unsupported_app_capability"
        # The capability assessment is already the authoritative semantic
        # decision. Do not require one exact abstention phrase from the model;
        # natural denials remain valid as long as they do not assert support.
        is_documented_abstention = True
    normalized = summary.casefold()
    if not is_documented_abstention:
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
