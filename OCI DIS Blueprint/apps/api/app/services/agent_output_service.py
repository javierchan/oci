"""Normalize, ground, and structure governed agent outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, cast

from app.agents.registry import AgentDefinition
from app.schemas.agent import AgentOutputBrief, AgentOutputQuality
from app.services.serializers import sanitize_for_json


MARKDOWN_TABLE_PATTERN = re.compile(r"(?m)^\s*\|?.+\|.+\|\s*$")
TABLE_DIVIDER_PATTERN = re.compile(r"(?m)^\s*\|?\s*:?-{3,}.*\|\s*$")
INTERNAL_PLACEHOLDER_PATTERN = re.compile(
    r"\[(?:redacted|tool|system|assistant|internal)[^\]]*\]", re.IGNORECASE
)
META_REASONING_PATTERN = re.compile(
    r"(?:^|[.!?]\s+)(?:the user|user asks|the system|the assistant|we need(?: to)?|we must|need to answer|need answer|"
    r"need explain|need mention|we should|it should|i need to|i should|we have evidence|we have tool output|we have tool data|we saw|"
    r"the tool returned|the system returned|the tool result|the tool gave|the question|the prompt asks|"
    r"follow rules|our task is|provide details|provide steps|pricing model|also mention|also might|it returned|"
    r"the answer(?: must| was| is)|the fallback answer|so we must|then next actions|we include evidence|"
    r"next concrete actions|should cite|use that)\b",
    re.IGNORECASE,
)
FINAL_ANSWER_MARKER_PATTERN = re.compile(
    r"(?:let['’]?s\s+(?:produce|draft)|final\s+answer|respuesta\s+final)\s*[:.]?\s*",
    re.IGNORECASE,
)
FINAL_ANSWER_HEADING_PATTERN = re.compile(
    r"(?im)^\s*(?:\*{0,2})?(?:cómo\s+.+|qué\s+encontr[ée]|lo\s+que\s+encontr[ée]|"
    r"respuesta|answer|here(?:'s| is))(?:\*{0,2})?\s*$"
)
SUPPORT_DRAFT_INSTRUCTION_PATTERN = re.compile(
    r"(?:^|[.!?]\s+)(?:"
    r"(?:must|should)\s+(?:use|avoid|provide|include|mention|cite|answer|reply|respond)\b|"
    r"(?:the\s+)?(?:answer|response)\s+should\b|"
    r"avoid\s+(?:markdown\s+)?tables?\b|"
    r"no\s+(?:markdown\s+)?tables?\b|"
    r"provide\s+(?:a\s+)?(?:navigation|validation|evidence|citations?|next actions?|"
    r"guidance|how\s+(?:the\s+)?user\s+can\s+validate)\b|"
    r"mention\s+(?:the\s+)?next actions?\b|"
    r"use\s+(?:attached\s+)?citations?(?:\s+with\s+href)?\b|"
    r"use\s+plain\s+language\b|"
    r"use\s+(?:simple|short|plain)\s+paragraphs?\b|"
    r"(?:also\s+)?after\s+(?:the\s+)?answer\b|"
    r"so\s+(?:give|provide|write|return)\s+(?:a\s+)?(?:direct|concise|final)\s+answer\b|"
    r"ensure\s+(?:there\s+is\s+)?no\s+summary\b|"
    r"we(?:['’]ll|\s+will)\s+follow\s+(?:the\s+)?style\b|"
    r"let['’]?s\s+(?:craft|draft|produce|write|compose)\b"
    r")",
    re.IGNORECASE,
)
SUPPORT_INTERNAL_NARRATION_PATTERN = re.compile(
    r"(?:^|[.!?]\s+)(?:the user asks?|user asks?|the system(?: says| asks| requires)|"
    r"we need(?: to)?\s+(?:answer|respond|provide|explain)|we must\s+(?:answer|respond|provide|explain)|"
    r"we have (?:tool|system) (?:output|data|evidence)|the tool (?:returned|gave)|"
    r"our task is|system instructions?|private reasoning)\b",
    re.IGNORECASE,
)
APPLIED_ACTION_PATTERN = re.compile(
    r"\b(?:i|we|the agent|the app)\s+(?:have\s+)?(?:applied|changed|updated|deployed|"
    r"approved|published|saved|deleted|created)\b",
    re.IGNORECASE,
)
HIGH_RISK_NUMBER_PATTERN = re.compile(
    r"(?<![\w.-])(?:USD\s*)?\$?\d[\d,]*(?:\.\d+)?%?(?![\w.-])",
    re.IGNORECASE,
)
PART_NUMBER_PATTERN = re.compile(r"\bB\d{5,}\b", re.IGNORECASE)
POSITIVE_VERIFICATION_PATTERN = re.compile(
    r"\b(?:verified|current|up[ -]?to[ -]?date|officially recognized|within parameters|"
    r"no issues|all services)\b",
    re.IGNORECASE,
)
COMMERCIAL_CLAIM_PATTERN = re.compile(
    r"(?:\$|\bUSD\b|\bprice\b|\bdiscount\b|\bcontract total\b|\bmonthly total\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GovernedAgentOutput:
    """Final presentation-safe output plus auditable quality metadata."""

    summary: str
    brief: AgentOutputBrief
    quality: AgentOutputQuality


def _text(value: object) -> str:
    return str(value).strip() if value not in (None, "") else ""


def _number(value: object) -> float:
    """Return a bounded JSON number for deterministic presentation."""

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _dicts(value: object) -> list[dict[str, object]]:
    return [cast(dict[str, object], item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: object, *, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        candidate = _text(item)
        if candidate and candidate not in result:
            result.append(candidate)
        if len(result) >= limit:
            break
    return result


def _object_strings(value: object, *keys: str, limit: int = 5) -> list[str]:
    result: list[str] = []
    for item in _dicts(value):
        for key in keys:
            candidate = _text(item.get(key))
            if candidate:
                result.append(candidate)
                break
        if len(result) >= limit:
            break
    return result


def _word_limit(definition: AgentDefinition) -> int:
    if definition.type == "architecture_review":
        return 160
    if definition.type == "support_assistant":
        # The App assistant covers the whole product, so a short fixed cap must
        # not replace a valid, grounded explanation with a canned fallback.
        # Provider token limits and persisted-message limits remain the hard
        # technical bounds; this only rejects pathological verbosity.
        return 1200
    return 180


def _confidence(value: object, *, default: Literal["high", "medium", "low"]) -> Literal["high", "medium", "low"]:
    candidate = _text(value).casefold()
    return cast(Literal["high", "medium", "low"], candidate) if candidate in {"high", "medium", "low"} else default


def normalize_agent_summary(value: str | None, *, preserve_markdown: bool = False) -> str:
    """Remove presentation markup without trying to rescue unsafe reasoning."""

    if not value:
        return ""
    normalized = value.replace("\r", "").strip()
    if not preserve_markdown:
        normalized = re.sub(r"\*\*(.+?)\*\*", r"\1", normalized)
        normalized = re.sub(r"__(.+?)__", r"\1", normalized)
        normalized = normalized.replace("`", "")
        normalized = re.sub(r"(?m)^#{1,6}\s+", "", normalized)
    normalized = re.sub(r"(?m)^\s*[-*]\s+", "- ", normalized)
    normalized = re.sub(r"(?m)^(\s*\d+[.)])\s*\n+\s*(?=\S)", r"\1 ", normalized)
    normalized = re.sub(r"(?m)^(\s*[-•])\s*\n+\s*(?=\S)", r"\1 ", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def support_output_contains_internal_reasoning(value: str) -> bool:
    """Detect deliberation that must never cross the support presentation boundary."""

    return bool(
        SUPPORT_DRAFT_INSTRUCTION_PATTERN.search(value)
        or SUPPORT_INTERNAL_NARRATION_PATTERN.search(value)
    )


def _remove_support_meta_reasoning(value: str) -> str:
    """Remove incidental model deliberation from a user-visible support answer.

    OCI's tool-capable model can occasionally prefix an otherwise useful answer
    with a planning sentence (for example, ``The user asks ...``). That text is
    not evidence or an answer for the user. Strip only those complete sentences
    for the conversational assistant; all remaining content still passes the
    shared grounding checks below.
    """

    # Some tool-capable models mark the transition to their final answer. Keep
    # the user-visible suffix and never surface the deliberation before it.
    marker = FINAL_ANSWER_MARKER_PATTERN.search(value)
    if marker is not None:
        value = value[marker.end() :]
    else:
        heading = FINAL_ANSWER_HEADING_PATTERN.search(value)
        if heading is not None:
            value = value[heading.start() :]
    sentences = re.split(r"(?<=[.!?])(?:\s+|\n+)", value.strip())
    visible = []
    for sentence in sentences:
        cleaned = re.sub(r"(?i)^\s*so:\s*", "", sentence).strip()
        if cleaned and not META_REASONING_PATTERN.search(cleaned):
            visible.append(cleaned)
    return "\n\n".join(visible).strip()


def _remove_support_internal_placeholder_sentences(value: str) -> str:
    """Drop redacted model sentences without discarding an otherwise useful answer."""

    sentences = re.split(r"(?<=[.!?])(?:\s+|\n+)", value.strip())
    return "\n\n".join(
        sentence.strip()
        for sentence in sentences
        if sentence.strip() and not INTERNAL_PLACEHOLDER_PATTERN.search(sentence)
    ).strip()


def _evidence_text(evidence: dict[str, object]) -> str:
    return str(sanitize_for_json(evidence)).casefold().replace(",", "")


def _numbers_are_grounded(summary: str, evidence: dict[str, object]) -> bool:
    serialized = _evidence_text(evidence)
    for match in HIGH_RISK_NUMBER_PATTERN.findall(summary):
        normalized = match.casefold().replace("usd", "").replace("$", "").replace(",", "").strip()
        digits = re.sub(r"[^0-9]", "", normalized)
        if not ("$" in match or "%" in match or "usd" in match.casefold() or len(digits) >= 3):
            continue
        if normalized.rstrip("%") not in serialized and normalized not in serialized:
            return False
    return True


def _part_numbers_are_grounded(summary: str, evidence: dict[str, object]) -> bool:
    serialized = _evidence_text(evidence)
    return all(part_number.casefold() in serialized for part_number in PART_NUMBER_PATTERN.findall(summary))


def _grounding_failure(
    definition: AgentDefinition,
    raw_summary: str,
    normalized_summary: str,
    evidence: dict[str, object],
) -> str | None:
    if not normalized_summary:
        return "empty_provider_summary"
    if (
        definition.type != "support_assistant"
        and MARKDOWN_TABLE_PATTERN.search(raw_summary)
        and TABLE_DIVIDER_PATTERN.search(raw_summary)
    ):
        return "markdown_table"
    if META_REASONING_PATTERN.search(raw_summary):
        return "internal_reasoning"
    if INTERNAL_PLACEHOLDER_PATTERN.search(raw_summary):
        return "internal_placeholder"
    if APPLIED_ACTION_PATTERN.search(normalized_summary):
        return "unverified_mutation_claim"
    if len(normalized_summary.split()) > _word_limit(definition):
        return "word_limit_exceeded"
    if not _numbers_are_grounded(normalized_summary, evidence):
        return "unsupported_numeric_claim"
    if not _part_numbers_are_grounded(normalized_summary, evidence):
        return "unsupported_sku_claim"
    if definition.type == "support_assistant":
        question = _text(evidence.get("current_question")).casefold()
        answer = normalized_summary.casefold()
        if "oci dis" in question and not re.search(r"\boci\s+dis\b|\barchitect\b|\bapp\b", answer):
            return "answer_not_relevant"
    if definition.type == "service_verification":
        sources_checked = evidence.get("sources_checked")
        if (not isinstance(sources_checked, int) or sources_checked < 1) and POSITIVE_VERIFICATION_PATTERN.search(
            normalized_summary
        ):
            return "verification_without_sources"
    if definition.type == "bom_scenario" and COMMERCIAL_CLAIM_PATTERN.search(normalized_summary):
        if not any(key in evidence for key in ("contract_total", "monthly_total", "price_snapshot")):
            return "commercial_claim_without_priced_evidence"
    return None


def _workspace_candidate(evidence: dict[str, object]) -> dict[str, object]:
    integration_workspace = _dict(evidence.get("recommendation_workspace"))
    candidates = _dicts(integration_workspace.get("candidates"))
    recommended_id = _text(integration_workspace.get("recommended_candidate_id"))
    if recommended_id:
        selected = next((item for item in candidates if _text(item.get("id")) == recommended_id), None)
        if selected is not None:
            return selected
    action_workspace = _dict(evidence.get("action_workspace"))
    action_candidates = _dicts(action_workspace.get("candidates"))
    if action_candidates:
        return action_candidates[0]
    return candidates[0] if candidates else {}


def _review_brief(definition: AgentDefinition, evidence: dict[str, object]) -> AgentOutputBrief:
    decision = _dict(evidence.get("decision_brief"))
    candidate = _workspace_candidate(evidence)
    findings = _dicts(evidence.get("findings"))
    first_finding = findings[0] if findings else {}
    headline = (
        _text(candidate.get("title"))
        or _text(decision.get("headline"))
        or _text(first_finding.get("title"))
        or f"{definition.name} completed"
    )
    finding = (
        _text(candidate.get("summary"))
        or _text(decision.get("primary_risk"))
        or _text(first_finding.get("summary"))
        or _text(evidence.get("summary"))
        or "Governed evidence is available for review."
    )
    impact = _strings(candidate.get("expected_impact"), limit=3)
    why = _text(candidate.get("why")) or (impact[0] if impact else _text(decision.get("primary_risk"))) or finding
    actions = (
        _strings(candidate.get("implementation_steps"), limit=4)
        or _strings(candidate.get("what_to_change"), limit=4)
        or [_text(decision.get("recommended_next_action"))]
    )
    actions = [item for item in actions if item]
    validation = _strings(candidate.get("validation_plan"), limit=4)
    evidence_ids = _strings(candidate.get("evidence_ids"), limit=8)
    if not evidence_ids:
        evidence_ids = [_text(item.get("id")) for item in _dicts(evidence.get("evidence"))[:8] if _text(item.get("id"))]
    return AgentOutputBrief(
        headline=headline,
        finding=finding,
        why=why,
        next_actions=actions or ["Open the affected App workspace and review the governed evidence."],
        validation=validation or ["Re-run the same governed review after the evidence or draft changes."],
        evidence_ids=evidence_ids,
        confidence=_confidence(candidate.get("confidence"), default="high" if evidence_ids else "medium"),
    )


def _verification_brief(definition: AgentDefinition, evidence: dict[str, object]) -> AgentOutputBrief:
    sources = evidence.get("sources_checked") if isinstance(evidence.get("sources_checked"), int) else 0
    changes = evidence.get("changes_detected") if isinstance(evidence.get("changes_detected"), int) else 0
    findings = _dicts(evidence.get("findings"))
    headline = (
        "Official-source changes require review"
        if changes
        else "Official-source verification completed"
        if sources
        else "Official-source evidence is incomplete"
    )
    actions = _object_strings(evidence.get("recommendations"), "recommended_action", "summary", "title")
    if not actions:
        actions = _object_strings(evidence.get("findings"), "recommended_action", "summary", "title")
    return AgentOutputBrief(
        headline=headline,
        finding=f"{sources} allowlisted source(s) checked; {changes} reviewable change(s) detected.",
        why=(
            _text(findings[0].get("summary"))
            if findings
            else "Only evidence retrieved from registered Oracle sources can support a governed rule change."
        ),
        next_actions=actions or ["Review source availability and rerun verification before asserting freshness."],
        validation=["Require explicit Admin approval before any finding changes governed Service Product rules."],
        evidence_ids=[_text(item.get("id")) for item in findings[:8] if _text(item.get("id"))],
        confidence="high" if sources and not changes else "medium" if sources else "low",
    )


def _import_brief(evidence: dict[str, object]) -> AgentOutputBrief:
    findings = _dicts(evidence.get("findings"))
    priority = next(
        (item for item in findings if _text(item.get("severity")).casefold() in {"critical", "high"}),
        findings[0] if findings else {},
    )
    included = evidence.get("included_count", 0)
    excluded = evidence.get("excluded_count", 0)
    next_action = _text(evidence.get("recommended_next_action"))
    return AgentOutputBrief(
        headline=_text(priority.get("title")) or "Import quality is ready for catalog governance",
        finding=_text(priority.get("summary")) or f"{included} row(s) included and {excluded} row(s) excluded.",
        why="Import gaps propagate into QA, volumetry, design recommendations, and BOM confidence.",
        next_actions=[next_action] if next_action else ["Review the governed catalog before recalculation."],
        validation=["Rerun Import Quality and confirm high-priority findings are closed before sign-off."],
        evidence_ids=[_text(evidence.get("batch_id"))] if _text(evidence.get("batch_id")) else [],
        confidence="high" if not findings else "medium",
    )


def _bom_brief(evidence: dict[str, object]) -> AgentOutputBrief:
    current_bom = _dict(evidence.get("current_bom"))
    if current_bom.get("ready_for_use") is True:
        currency = _text(current_bom.get("currency")) or "USD"
        contract_total = _number(current_bom.get("contract_total"))
        environments = _strings(current_bom.get("environment_names"), limit=8)
        return AgentOutputBrief(
            headline="Published BOM is ready for governed use",
            finding=(
                f"{current_bom.get('coverage_pct', 0)}% coverage across {current_bom.get('line_item_count', 0)} "
                f"line(s) in {', '.join(environments) or 'the approved environment plan'}; contract total is "
                f"{currency} {contract_total:,.2f}."
            ),
            why="The published BOM uses the latest technical snapshot, an approved deployment scenario, and has no unresolved commercial lines.",
            next_actions=["Keep this baseline unless architecture, environment timing, SKU selection, or approved price evidence changes."],
            validation=[
                "Confirm the current technical snapshot and publication state before client use.",
                "Regenerate and compare a separate snapshot after any governed input changes.",
            ],
            evidence_ids=[
                item
                for item in (
                    _text(current_bom.get("snapshot_id")),
                    _text(current_bom.get("scenario_id")),
                    _text(current_bom.get("technical_snapshot_id")),
                )
                if item
            ],
            confidence="high",
        )
    services = _strings(evidence.get("detected_services"), limit=8)
    questions = _strings(evidence.get("required_questions"), limit=4)
    warnings = _strings(evidence.get("warnings"), limit=3)
    coverage = _dicts(evidence.get("commercial_coverage"))
    blocked = [item for item in coverage if _text(item.get("readiness")).casefold() not in {"ready", "included"}]
    return AgentOutputBrief(
        headline="Complete the deployment scenario before BOM approval" if questions or blocked else "BOM scenario is ready for governed pricing",
        finding=f"{len(services)} product(s) detected; {len(questions)} client input question(s) remain.",
        why=(
            _text(blocked[0].get("guidance"))
            if blocked
            else warnings[0]
            if warnings
            else "Real-unit quantities and approved SKU mappings determine the commercial result."
        ),
        next_actions=questions or ["Create the scenario, generate the BOM, and inspect its immutable line provenance."],
        validation=[
            "Generate a new BOM snapshot and require 100% price and quantity coverage before publication.",
            "Verify environment, SKU, metric, quantity, period, and price provenance for every material line.",
        ],
        evidence_ids=services,
        confidence=_confidence(evidence.get("confidence"), default="medium"),
    )


def build_agent_brief(definition: AgentDefinition, evidence: dict[str, object]) -> AgentOutputBrief:
    """Build the same what/why/how/validate hierarchy for every agent."""

    if definition.type == "service_verification":
        return _verification_brief(definition, evidence)
    if definition.type == "import_quality":
        return _import_brief(evidence)
    if definition.type == "bom_scenario":
        return _bom_brief(evidence)
    if definition.type == "support_assistant":
        answer = _text(evidence.get("fallback_answer"))
        return AgentOutputBrief(
            headline="Answer from governed App context",
            finding=answer or "The App context does not contain enough evidence for a specific answer.",
            why="The assistant uses bounded App evidence and does not treat previous model answers as facts.",
            next_actions=[_text(evidence.get("recommended_next_action")) or "Add the relevant App context and ask again."],
            validation=["Open the cited App route and verify the governed record."],
            evidence_ids=[],
            confidence="high" if answer else "low",
        )
    return _review_brief(definition, evidence)


def _fallback_summary(definition: AgentDefinition, brief: AgentOutputBrief) -> str:
    # A conversational fallback is already a user-facing answer.  Do not wrap
    # it in internal-looking headings or an unrelated generic next action.
    if definition.type == "support_assistant":
        return brief.finding
    action = brief.next_actions[0] if brief.next_actions else "Review the governed evidence."
    return f"{brief.headline}\n\n{brief.finding}\n\nNext action: {action}"


def _evidence_completeness(brief: AgentOutputBrief, evidence: dict[str, object]) -> int:
    score = 0
    score += 20 if evidence else 0
    score += 15 if brief.finding else 0
    score += 15 if brief.why else 0
    score += 20 if brief.next_actions else 0
    score += 15 if brief.validation else 0
    score += 15 if brief.evidence_ids else 0
    return min(score, 100)


def govern_agent_output(
    definition: AgentDefinition,
    candidate_summary: str | None,
    evidence: dict[str, object],
) -> GovernedAgentOutput:
    """Return a presentation-safe summary and deterministic structured brief."""

    raw_summary = candidate_summary or ""
    support_draft_instructions = bool(
        definition.type == "support_assistant"
        and SUPPORT_DRAFT_INSTRUCTION_PATTERN.search(raw_summary)
    )
    if definition.type == "support_assistant":
        raw_summary = _remove_support_meta_reasoning(raw_summary)
        raw_summary = _remove_support_internal_placeholder_sentences(raw_summary)
    normalized_summary = normalize_agent_summary(
        raw_summary,
        preserve_markdown=definition.type == "support_assistant",
    )
    failure = (
        "internal_reasoning"
        if support_draft_instructions
        else _grounding_failure(definition, raw_summary, normalized_summary, evidence)
    )
    brief = build_agent_brief(definition, evidence)
    fallback_used = failure is not None
    summary = _fallback_summary(definition, brief) if fallback_used else normalized_summary
    quality = AgentOutputQuality(
        normalized=bool(raw_summary and normalized_summary != raw_summary.strip()),
        grounded=not fallback_used,
        fallback_used=fallback_used,
        fallback_reason=failure,
        evidence_completeness_pct=_evidence_completeness(brief, evidence),
    )
    return GovernedAgentOutput(summary=summary, brief=brief, quality=quality)
