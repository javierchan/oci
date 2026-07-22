"""Grounded App workflow knowledge for the contextual assistant."""

from __future__ import annotations

import re
from typing import cast

from app.knowledge.builder import load_knowledge_base, retrieve_knowledge
from app.services.support_routing_service import CAPABILITY_INQUIRY_PATTERN


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
CAPABILITY_NOISE = frozenset(
    {
        "automatic", "automated", "can", "configure", "could", "does", "have", "provide",
        "set", "setup", "support", "supported", "when", "puedo", "podemos", "permite",
        "soporta", "ofrece", "configurar", "crear", "cuando", "do", "that", "this", "it",
        "anything", "something",
    }
)
CAPABILITY_ACTION_TOKENS = frozenset(
    {
        "add", "approve", "archive", "cancel", "choose", "create", "deactivate", "design",
        "download", "edit", "execute", "export", "filter", "finalize", "generate", "inspect",
        "list", "monitor", "open", "plan", "promote", "publish", "recalculate", "remove",
        "resolve", "review", "run", "select", "synchronize", "upload",
    }
)
NEXT_ACTION_PATTERN = re.compile(
    r"\*\*(?:Next action|Siguiente paso):\*\*",
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
    # A source citation and next action must always be executable. A scoped KB
    # route without the required entity context safely falls back to Projects.
    if "[" in resolved or "{" in resolved:
        return "/projects"
    return resolved


def _tokens(value: object) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value).casefold())
        if len(token) > 1 and token not in CAPABILITY_NOISE
    }


def _closest_capability_entry(
    question_tokens: set[str],
    *,
    fallback_entries: list[dict[str, object]],
    project_id: str | None,
    integration_id: str | None,
) -> dict[str, object] | None:
    """Choose the nearest documented workflow by semantic evidence, not route order."""

    ranked: list[tuple[int, str, dict[str, object]]] = []
    for raw in _as_list(load_knowledge_base().get("sections")):
        if not isinstance(raw, dict):
            continue
        section = dict(raw)
        section_tokens = _tokens(
            " ".join(
                str(section.get(field) or "")
                for field in (
                    "id",
                    "name",
                    "purpose",
                    "when_to_use",
                    "keywords",
                    "supported_actions",
                )
            )
        )
        overlap = len(question_tokens & section_tokens)
        if not overlap:
            continue
        section["routes"] = [
            _resolve_route(str(route), project_id=project_id, integration_id=integration_id)
            for route in _as_list(section.get("routes"))
        ]
        ranked.append((-overlap, str(section.get("name") or ""), section))
    if ranked:
        ranked.sort(key=lambda item: (item[0], item[1]))
        return ranked[0][2]
    return fallback_entries[0] if fallback_entries else None


def _capability_assessment(
    question: str,
    *,
    project_id: str | None,
    integration_id: str | None,
    closest_entries: list[dict[str, object]],
) -> dict[str, object]:
    """Match a capability question only against explicit supported actions."""

    question_tokens = _tokens(question)
    matches: list[tuple[float, int, dict[str, object], str]] = []
    for raw in _as_list(load_knowledge_base().get("sections")):
        if not isinstance(raw, dict):
            continue
        section = dict(raw)
        section_tokens = _tokens(
            " ".join(
                str(section.get(field) or "")
                for field in ("id", "name", "purpose", "when_to_use", "keywords")
            )
        )
        for raw_action in _as_list(section.get("supported_actions")):
            action = str(raw_action)
            action_tokens = _tokens(action)
            overlap = len(question_tokens & action_tokens)
            if not action_tokens or not overlap:
                continue
            coverage = overlap / len(action_tokens)
            # Require either a complete short action match or enough shared
            # meaning to avoid treating a generic word such as "cost" as proof.
            has_action_and_section_anchor = bool(
                question_tokens & action_tokens & CAPABILITY_ACTION_TOKENS
                and question_tokens & section_tokens
            )
            if coverage >= 0.6 or (overlap >= 2 and coverage >= 0.4) or has_action_and_section_anchor:
                matches.append((coverage, overlap, section, action))
    matches.sort(key=lambda item: (-item[0], -item[1], str(item[2].get("name") or "")))
    if not question_tokens:
        return {
            "status": "ambiguous",
            "reason": "The requested App action is not specific enough to verify.",
            "matched_actions": [],
            "closest_entry": closest_entries[0] if closest_entries else None,
        }
    closest_entry = _closest_capability_entry(
        question_tokens,
        fallback_entries=closest_entries,
        project_id=project_id,
        integration_id=integration_id,
    )
    if matches:
        best_score = matches[0][0:2]
        selected = [item for item in matches if item[0:2] == best_score][:3]
        matched_entries: list[dict[str, object]] = []
        matched_actions: list[dict[str, str]] = []
        seen_sections: set[str] = set()
        for _, _, section, action in selected:
            section_id = str(section.get("id") or "")
            matched_actions.append({"section_id": section_id, "action": action})
            if section_id in seen_sections:
                continue
            seen_sections.add(section_id)
            projected = dict(section)
            projected["routes"] = [
                _resolve_route(str(route), project_id=project_id, integration_id=integration_id)
                for route in _as_list(section.get("routes"))
            ]
            matched_entries.append(projected)
        return {
            "status": "documented",
            "reason": "The requested action matches an explicit supported_actions entry.",
            "matched_actions": matched_actions,
            "matched_entries": matched_entries,
            "closest_entry": matched_entries[0],
        }
    return {
        "status": "not_documented",
        "reason": "No supported_actions entry matches the requested capability.",
        "matched_actions": [],
        "closest_entry": closest_entry,
    }


def build_app_knowledge_evidence(
    question: str,
    current_route: str,
    *,
    language: str,
    project_id: str | None,
    integration_id: str | None,
    capability_inquiry: bool | None = None,
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
    is_capability_inquiry = (
        bool(CAPABILITY_INQUIRY_PATTERN.search(question))
        if capability_inquiry is None
        else capability_inquiry
    )
    if is_capability_inquiry:
        evidence["capability_assessment"] = _capability_assessment(
            question,
            project_id=project_id,
            integration_id=integration_id,
            closest_entries=entries,
        )
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
    assessment = evidence.get("capability_assessment")
    if isinstance(assessment, dict):
        status = str(assessment.get("status") or "")
        closest = assessment.get("closest_entry")
        closest_entry = closest if isinstance(closest, dict) else (entries[0] if entries else {})
        name = str(closest_entry.get("name") or "Projects")
        purpose = str(closest_entry.get("purpose") or "")
        routes = [str(route) for route in _as_list(closest_entry.get("routes"))]
        route = next((candidate for candidate in routes if candidate != "/"), routes[0] if routes else "/projects")
        matched_actions = [
            str(item.get("action"))
            for item in _as_list(assessment.get("matched_actions"))
            if isinstance(item, dict) and item.get("action")
        ]
        if status == "documented" and matched_actions:
            if len(matched_actions) == 1:
                action = matched_actions[0]
            else:
                action = ", ".join(matched_actions[:-1]) + f", and {matched_actions[-1]}"
            if language == "es":
                return (
                    f"**Sí.** OCI DIS Architect documenta **{action}** en **{name}**.\n\n"
                    f"{purpose}\n\n**Siguiente paso:** [Abrir {name}]({route})"
                )
            return (
                f"**Yes.** OCI DIS Architect documents **{action}** in **{name}**.\n\n"
                f"{purpose}\n\n**Next action:** [Open {name}]({route})"
            )
        if status == "not_documented":
            if language == "es":
                return (
                    "**No.** Esa capacidad no está documentada en OCI DIS Architect.\n\n"
                    f"La alternativa más cercana es **{name}**: {purpose}\n\n"
                    f"**Siguiente paso:** [Abrir {name}]({route})"
                )
            return (
                "**No.** That capability is not documented in OCI DIS Architect.\n\n"
                f"The closest available workflow is **{name}**: {purpose}\n\n"
                f"**Next action:** [Open {name}]({route})"
            )
        if status == "ambiguous":
            return (
                "**Necesito una precisión:** ¿qué acción de la App quieres verificar? Por ejemplo, importar un workbook, exportar un BOM o revisar QA."
                if language == "es"
                else "**I need one detail:** which App action do you want to verify? For example, importing a workbook, exporting a BOM, or reviewing QA."
            )
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
    assessment = knowledge.get("capability_assessment")
    if isinstance(assessment, dict) and assessment.get("status") == "ambiguous":
        if summary.count("?") != 1:
            return "invalid_capability_clarification"
    elif len(NEXT_ACTION_PATTERN.findall(summary)) != 1:
        return "invalid_next_action_count"
    if isinstance(assessment, dict) and assessment.get("status") == "not_documented":
        if not CAPABILITY_ABSTENTION_PATTERN.search(summary):
            return "undocumented_app_capability"
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
