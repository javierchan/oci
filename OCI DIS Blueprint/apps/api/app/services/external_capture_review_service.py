"""Presentation-safe review facts for governed external capture drafts."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.core.calc_engine import HEADER_ALIASES, get_pattern_certification
from app.schemas.catalog import ManualIntegrationCreate
from app.services.import_mapping_service import normalize_header


REQUIRED_FIELD_LABELS = {
    "brand": "Brand",
    "business_process": "Business process",
    "interface_name": "Interface name",
    "source_system": "Source system",
    "destination_system": "Destination system",
    "selected_pattern": "Governed pattern",
}

QA_GUIDANCE: dict[str, tuple[str, str, str]] = {
    "INVALID_TRIGGER_TYPE": (
        "Trigger type is not governed",
        "The proposed trigger is missing or does not match the App vocabulary.",
        "Confirm the actual invocation mechanism and select the matching governed trigger.",
    ),
    "INVALID_PATTERN": (
        "Governed pattern is missing",
        "The proposal has no active governed pattern.",
        "Select a pattern supported by the observed source, destination, trigger, and transport evidence.",
    ),
    "MISSING_RATIONALE": (
        "Pattern rationale is incomplete",
        "The current rationale does not substantively connect the evidence to the selected pattern.",
        "Explain which observed flow characteristics support the selected pattern.",
    ),
    "MISSING_CORE_TOOLS": (
        "Core processing tools are missing",
        "No governed core-tool composition is present in the proposed record.",
        "Confirm the products that actually transport or process this integration.",
    ),
    "PATTERN_NOT_CERTIFIED": (
        "Pattern is not certified",
        "The selected pattern has no active certification contract.",
        "Select a certified pattern or govern its certification before approval.",
    ),
    "PATTERN_CORE_TOOLS_NOT_CERTIFIED": (
        "Core tools do not support the pattern",
        "The proposed tools do not match a certified composition for the selected pattern.",
        "Confirm the actual processing stack and align it with a certified pattern composition.",
    ),
    "PATTERN_OVERLAYS_NOT_CERTIFIED": (
        "Required architecture overlays are missing",
        "The selected pattern requires governed overlays that are not present in the proposal.",
        "Confirm and add the required storage, API, identity, observability, or catalog controls.",
    ),
    "MISSING_PAYLOAD": (
        "Payload evidence is missing",
        "No supported payload-per-execution value is available for this integration.",
        "Provide the payload for one execution in KB or keep downstream sizing explicitly low-confidence.",
    ),
    "MISSING_FAN_OUT_TARGETS": (
        "Fan-out scope is incomplete",
        "The flow indicates fan-out but does not identify a usable destination count.",
        "Confirm how many destinations receive each source event.",
    ),
    "SCATTER_GATHER_EXCEEDS_OIC_PARALLEL_LIMIT": (
        "Parallel fan-out exceeds the governed limit",
        "The proposed scatter-gather branch count exceeds the supported OIC parallel composition.",
        "Reduce or stage the parallel branches and revalidate the route.",
    ),
    "SAGA_SYNC_DURATION_RISK": (
        "Synchronous saga duration is unsafe",
        "The proposed synchronous route carries long-running saga risk.",
        "Confirm the latency budget and move the work to an asynchronous orchestration when required.",
    ),
    "STREAMING_PAYLOAD_EXCEEDS_1MB_LIMIT": (
        "Streaming payload exceeds the service limit",
        "The proposed payload is larger than the governed OCI Streaming message limit.",
        "Externalize the payload or select a transport that supports the observed size.",
    ),
    "FUNCTIONS_PAYLOAD_EXCEEDS_6MB_LIMIT": (
        "Functions payload exceeds the service limit",
        "The proposed payload is larger than the governed Oracle Functions request limit.",
        "Route the payload through a supported integration or object-storage path.",
    ),
    "QUEUE_PAYLOAD_EXCEEDS_256KB_LIMIT": (
        "Queue payload exceeds the service limit",
        "The proposed payload is larger than the governed OCI Queue message limit.",
        "Store the payload externally and queue a governed reference.",
    ),
    "REFERENCE_PATTERN_NEEDS_EXPLICIT_RATIONALE": (
        "Reference pattern needs explicit justification",
        "The selected reference pattern cannot be treated as implementation-ready without a specific rationale.",
        "Document why this reference pattern fits the observed integration route.",
    ),
    "BATCH_WINDOW_REQUIRED": (
        "Batch processing window is missing",
        "The scheduled or file-based flow has no processing, restart, or reconciliation window.",
        "Confirm the expected batch window and recovery behavior.",
    ),
    "TARGET_LATENCY_REQUIRED": (
        "Target latency is missing",
        "The asynchronous or protected route has no completion or callback expectation.",
        "Define the expected completion time or callback SLA.",
    ),
    "RETRY_POLICY_REQUIRED": (
        "Retry policy is missing",
        "The selected pattern requires bounded retry and terminal-failure behavior.",
        "Define attempts, backoff, terminal handling, and operational ownership.",
    ),
    "IDEMPOTENCY_REQUIRED": (
        "Idempotency evidence is missing",
        "The selected event or replay-capable pattern has no deduplication control.",
        "Confirm the idempotency key, retention window, and replay behavior.",
    ),
    "RETENTION_POLICY_REQUIRED": (
        "Retention policy is missing",
        "The selected data-movement pattern has no retention or cleanup evidence.",
        "Define retention, access expiry, reconciliation, and cleanup behavior.",
    ),
    "DATA_CLASSIFICATION_REQUIRED": (
        "Data classification is missing",
        "The payload has not been classified for security and retention controls.",
        "Confirm the data classification before architecture approval.",
    ),
    "BUSINESS_CRITICALITY_REQUIRED": (
        "Business criticality is missing",
        "The selected resilience pattern has no business-impact classification.",
        "Confirm the business criticality and recovery expectation.",
    ),
}

COMMERCIAL_HEADER_TOKENS = ("cost", "costo", "price", "precio", "usd")
DERIVED_DEMAND_HEADERS = {
    "ejecuciones total oic",
    "functions",
    "request object storage",
    "request oic",
}
EXTERNAL_SUPPORTED_ALIASES = {"patron", "pattern"}
SOURCE_TARGET_OVERRIDES = {
    "destination_technology_1": "destination_technology",
}
JSON_FENCE_PATTERN = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.IGNORECASE | re.DOTALL
)
EMBEDDED_JSON_FENCE_PATTERN = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```", re.IGNORECASE | re.DOTALL
)


def strip_formula_values(
    value: Any,
    *,
    path: str = "",
) -> tuple[Any, list[str]]:
    """Remove formula expressions from any operational payload recursively."""

    if isinstance(value, str) and value.lstrip().startswith("="):
        return None, [path or "$"]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        excluded: list[str] = []
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            clean_item, child_excluded = strip_formula_values(
                item,
                path=child_path,
            )
            cleaned[str(key)] = clean_item
            excluded.extend(child_excluded)
        return cleaned, excluded
    if isinstance(value, list):
        cleaned_items: list[Any] = []
        excluded = []
        for index, item in enumerate(value):
            child_path = f"{path}[{index}]" if path else f"[{index}]"
            clean_item, child_excluded = strip_formula_values(
                item,
                path=child_path,
            )
            if not child_excluded or clean_item is not None:
                cleaned_items.append(clean_item)
            excluded.extend(child_excluded)
        return cleaned_items, excluded
    return value, []


def evidence_hash(
    *,
    source_record: dict[str, Any],
    proposed_payload: dict[str, Any],
    normalized_values: dict[str, Any],
    pattern_assessment: dict[str, Any],
    validation_evidence: dict[str, Any],
    required_field_gaps: list[object],
    qa_preview: dict[str, Any],
) -> str:
    """Fingerprint every input that can change one row-level agent analysis."""

    payload = {
        "source_record": source_record,
        "proposed_payload": proposed_payload,
        "normalized_values": normalized_values,
        "pattern_assessment": pattern_assessment,
        "validation_evidence": validation_evidence,
        "required_field_gaps": required_field_gaps,
        "qa_preview": qa_preview,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_required_data_contract(
    proposed_payload: dict[str, Any],
    *,
    governed_options: dict[str, list[dict[str, object]]] | None = None,
    governed_patterns: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    """Expose the current schema and selected-pattern contract without case rules."""

    schema = ManualIntegrationCreate.model_json_schema()
    properties = schema.get("properties", {})
    accepted_fields = sorted(str(field) for field in properties)
    required_fields = sorted(str(field) for field in schema.get("required", []))
    selected_pattern = proposed_payload.get("selected_pattern")
    certification = get_pattern_certification(
        str(selected_pattern) if selected_pattern else None
    )
    pattern_contract: dict[str, object] | None = None
    if certification is not None:
        pattern_contract = {
            "pattern_id": certification.pattern_id,
            "name": certification.name,
            "required_evidence": list(certification.required_evidence),
            "approved_core_tool_groups": [
                list(group) for group in certification.approved_core_tool_groups
            ],
            "approved_overlay_groups": [
                list(group) for group in certification.approved_overlay_groups
            ],
            "validation_controls": list(certification.validation_controls),
            "summary": certification.summary,
        }
    return {
        "accepted_app_fields": accepted_fields,
        "required_app_fields": required_fields,
        "governed_options": governed_options or {},
        "governed_patterns": governed_patterns or [],
        "selected_pattern_contract": pattern_contract,
        "rule": (
            "The agent may detect semantic deviations beyond deterministic validation "
            "but may not invent a required value or treat an excluded source field as imported."
        ),
    }


def _source_target(normalized_header: str) -> str | None:
    """Resolve a source alias only when Capture Review has an App target."""

    matches: list[tuple[bool, int, str]] = []
    for canonical_field, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize_header(alias)
            if (
                normalized_header == normalized_alias
                or normalized_header.startswith(f"{normalized_alias} ")
                or normalized_header.startswith(f"{normalized_alias}(")
                or normalized_header.startswith(f"{normalized_alias}:")
                or normalized_header.startswith(f"{normalized_alias}-")
            ):
                matches.append(
                    (
                        normalized_header == normalized_alias,
                        len(normalized_alias),
                        canonical_field,
                    )
                )
    if matches:
        _, _, canonical_field = max(matches)
        target_field = SOURCE_TARGET_OVERRIDES.get(
            canonical_field,
            canonical_field,
        )
        return (
            target_field
            if target_field in ManualIntegrationCreate.model_fields
            else None
        )
    if normalized_header in EXTERNAL_SUPPORTED_ALIASES:
        return "selected_pattern"
    return None


def partition_source_record(
    source_record: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Keep supported source evidence visible and redact excluded values.

    The persisted source record remains immutable audit evidence. This projection
    prevents formulas, commercial outputs, derived workbook calculations, and
    unknown columns from appearing as App-supported imported fields.
    """

    supported: dict[str, Any] = {}
    ignored: list[dict[str, str]] = []
    for header, value in source_record.items():
        normalized = normalize_header(str(header))
        is_formula = isinstance(value, str) and value.lstrip().startswith("=")
        if is_formula:
            classification = (
                "commercial_formula"
                if any(token in normalized for token in COMMERCIAL_HEADER_TOKENS)
                else "formula"
            )
            reason = (
                "Commercial formula excluded from the App record; it is never evaluated or promoted."
                if classification == "commercial_formula"
                else "Formula excluded from the App record; only source inputs may populate governed fields."
            )
        elif any(token in normalized for token in COMMERCIAL_HEADER_TOKENS):
            classification = "commercial_value"
            reason = "Commercial source value is outside Capture Review and is not imported into the App record."
        elif normalized in DERIVED_DEMAND_HEADERS:
            classification = "derived_demand"
            reason = "Derived workbook demand is not a supported capture input and is excluded from the App record."
        elif _source_target(normalized) is None:
            classification = "unsupported"
            reason = "This source column has no governed App target and is excluded from the App record."
        else:
            supported[str(header)] = value
            continue
        ignored.append(
            {
                "source_header": str(header),
                "classification": classification,
                "reason": reason,
                "value_kind": "formula" if is_formula else "value",
            }
        )
    return supported, ignored


def _trigger(
    *,
    code: str,
    kind: str,
    title: str,
    evidence: str,
    required_decision: str,
    blocks_approval: bool,
) -> dict[str, object]:
    return {
        "code": code,
        "kind": kind,
        "title": title,
        "evidence": evidence,
        "required_decision": required_decision,
        "blocks_approval": blocks_approval,
    }


def build_review_triggers(
    *,
    required_field_gaps: list[object],
    qa_preview: dict[str, Any],
    pattern_assessment: dict[str, Any],
    normalized_values: dict[str, Any],
) -> list[dict[str, object]]:
    """Build bounded facts that OCI GenAI can explain without inventing evidence."""

    triggers: list[dict[str, object]] = []
    seen: set[str] = set()
    for field_value in required_field_gaps:
        field = str(field_value)
        label = REQUIRED_FIELD_LABELS.get(field, field.replace("_", " ").title())
        code = f"REQUIRED_FIELD:{field}"
        triggers.append(
            _trigger(
                code=code,
                kind="required_gap",
                title=f"{label} is missing",
                evidence=f"The proposed App record has no supported value for {label}.",
                required_decision=f"Provide verified {label.lower()} evidence or reject this proposal.",
                blocks_approval=True,
            )
        )
        seen.add(code)

    for field, detail_value in normalized_values.items():
        detail = detail_value if isinstance(detail_value, dict) else {}
        if str(detail.get("action", "")).casefold() != "unresolved":
            continue
        code = f"NORMALIZATION_UNRESOLVED:{field}"
        if code in seen:
            continue
        label = REQUIRED_FIELD_LABELS.get(field, field.replace("_", " ").title())
        source = str(detail.get("source", "")).strip() or "blank/TBD source evidence"
        triggers.append(
            _trigger(
                code=code,
                kind="normalization_gap",
                title=f"{label} could not be normalized",
                evidence=f"The source value '{source}' has no governed normalized value.",
                required_decision=f"Confirm the intended {label.lower()} using the active App dictionary.",
                blocks_approval=False,
            )
        )
        seen.add(code)

    source_pattern_value = pattern_assessment.get("source_pattern")
    recommended_pattern_value = pattern_assessment.get("recommended_pattern")
    source_pattern = (
        source_pattern_value.strip()
        if isinstance(source_pattern_value, str)
        else ""
    )
    recommended_pattern = (
        recommended_pattern_value.strip()
        if isinstance(recommended_pattern_value, str)
        else ""
    )
    if source_pattern and recommended_pattern and source_pattern != recommended_pattern:
        code = "PATTERN_RECOMMENDATION_CHANGED"
        triggers.append(
            _trigger(
                code=code,
                kind="pattern_review",
                title="Pattern recommendation differs from the source",
                evidence=f"The source identifies {source_pattern}; the proposal recommends {recommended_pattern}.",
                required_decision="Review the observed route evidence and confirm which governed pattern is correct.",
                blocks_approval=False,
            )
        )
        seen.add(code)

    qa_reasons = qa_preview.get("reasons", [])
    for reason_value in qa_reasons if isinstance(qa_reasons, list) else []:
        reason = str(reason_value)
        if reason == "REQUIRED_CAPTURE_EVIDENCE_MISSING" and required_field_gaps:
            continue
        if reason in seen:
            continue
        title, evidence, action = QA_GUIDANCE.get(
            reason,
            (
                reason.replace("_", " ").title(),
                f"Deterministic QA reported {reason}.",
                "Review the governed QA evidence and resolve the reported control.",
            ),
        )
        triggers.append(
            _trigger(
                code=reason,
                kind="qa_control",
                title=title,
                evidence=evidence,
                required_decision=action,
                blocks_approval=False,
            )
        )
        seen.add(reason)

    if not triggers:
        triggers.append(
            _trigger(
                code="EXPLICIT_ARCHITECT_REVIEW_REQUIRED",
                kind="governance",
                title="Architect confirmation is required",
                evidence="The proposal was derived from external customer evidence and has not been approved.",
                required_decision="Confirm the source interpretation and governed pattern before promotion.",
                blocks_approval=False,
            )
        )
    return triggers


def summarize_review_triggers(triggers: list[dict[str, object]]) -> str:
    """Return a concise factual status while leaving interpretation to the agent."""

    blockers = [trigger for trigger in triggers if trigger["blocks_approval"] is True]
    if blockers:
        first = str(blockers[0]["title"])
        additional = len(triggers) - 1
        suffix = (
            f" {additional} additional review decision(s) remain."
            if additional
            else ""
        )
        return f"Approval is blocked: {first}.{suffix}"
    if len(triggers) == 1:
        return f"Architect review is required: {triggers[0]['title']}."
    return (
        f"Required fields are complete, but {len(triggers)} architecture "
        "evidence decisions still require review."
    )


def _dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _strings(value: object, *, limit: int = 20) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        candidate = str(item).strip()
        if candidate and candidate not in result:
            result.append(candidate)
        if len(result) >= limit:
            break
    return result


def _source_scalar_values(value: object) -> list[object]:
    if isinstance(value, dict):
        result: list[object] = []
        for item in value.values():
            result.extend(_source_scalar_values(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_source_scalar_values(item))
        return result
    return [] if value is None else [value]


def _candidate_is_grounded(candidate: object, focused_row: dict[str, object]) -> bool:
    if candidate is None or isinstance(candidate, bool):
        return True
    evidence_values = _source_scalar_values(
        {
            "source": focused_row.get("supported_source_evidence", {}),
            "proposed": focused_row.get("data_received", {}),
        }
    )
    if isinstance(candidate, (int, float)):
        return any(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and float(value) == float(candidate)
            for value in evidence_values
        )
    if isinstance(candidate, list):
        return all(_candidate_is_grounded(item, focused_row) for item in candidate)
    if isinstance(candidate, dict):
        return all(
            _candidate_is_grounded(item, focused_row)
            for item in candidate.values()
        )
    normalized = normalize_header(str(candidate))
    if not normalized:
        return True
    for value in evidence_values:
        evidence_text = normalize_header(str(value))
        if normalized == evidence_text or normalized in evidence_text:
            return True
        candidate_tokens = set(normalized.split())
        evidence_tokens = set(evidence_text.split())
        if candidate_tokens and len(candidate_tokens & evidence_tokens) >= min(
            2, len(candidate_tokens)
        ):
            return True
    return False


def _decode_agent_json(candidate_summary: str) -> dict[str, object] | None:
    """Decode one JSON object while tolerating bounded provider prose wrappers."""

    match = JSON_FENCE_PATTERN.match(candidate_summary)
    candidates = [match.group(1)] if match else [candidate_summary]
    embedded_match = EMBEDDED_JSON_FENCE_PATTERN.search(candidate_summary)
    if embedded_match is not None:
        candidates.append(embedded_match.group(1))
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            decoded = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            for index, character in enumerate(candidate):
                if character != "{":
                    continue
                try:
                    decoded, _ = decoder.raw_decode(candidate[index:])
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(decoded, dict):
                    return decoded
            continue
        if isinstance(decoded, dict):
            return decoded
    return None


def parse_agent_correction(
    candidate_summary: str,
    evidence: dict[str, object],
) -> dict[str, object] | None:
    """Parse and constrain one model-authored row correction proposal.

    The model may reason about arbitrary deviations, but the executable patch is
    restricted to current App fields, valid field types, formula-free values,
    and values grounded in the supplied row evidence. Rejected suggestions become
    explicit human decisions instead of silently entering the correction draft.
    """

    focused_row = evidence.get("focused_row")
    if not isinstance(focused_row, dict):
        return None
    decoded = _decode_agent_json(candidate_summary)
    if decoded is None:
        return None

    explanation = str(decoded.get("explanation", "")).strip()
    if not explanation:
        return None
    deviations: list[dict[str, object]] = []
    for item in _dicts(decoded.get("deviations"))[:20]:
        issue = str(item.get("issue", "")).strip()
        evidence_text = str(item.get("evidence", "")).strip()
        proposed_action = str(item.get("proposed_action", "")).strip()
        if not issue or not evidence_text or not proposed_action:
            continue
        deviations.append(
            {
                "source_field": str(item.get("source_field", "")).strip() or None,
                "target_field": str(item.get("target_field", "")).strip() or None,
                "issue": issue,
                "evidence": evidence_text,
                "proposed_action": proposed_action,
                "confidence": (
                    str(item.get("confidence", "")).casefold()
                    if str(item.get("confidence", "")).casefold()
                    in {"high", "medium", "low"}
                    else "medium"
                ),
            }
        )

    required_decisions = _strings(decoded.get("required_decisions"))
    proposed_patch_value = decoded.get("proposed_patch")
    proposed_patch = (
        proposed_patch_value if isinstance(proposed_patch_value, dict) else {}
    )
    accepted_fields = set(ManualIntegrationCreate.model_fields)
    safe_patch: dict[str, object] = {}
    rejected_patch_fields: list[str] = []
    no_op_patch_fields: list[str] = []
    data_received_value = focused_row.get("data_received")
    data_received = (
        data_received_value if isinstance(data_received_value, dict) else {}
    )
    current_proposed_record_value = data_received.get("proposed_app_record")
    current_proposed_record = (
        current_proposed_record_value
        if isinstance(current_proposed_record_value, dict)
        else {}
    )
    for field, candidate in proposed_patch.items():
        if field not in accepted_fields:
            rejected_patch_fields.append(str(field))
            required_decisions.append(
                f"'{field}' has no supported App target; confirm whether it should remain excluded."
            )
            continue
        cleaned, formula_paths = strip_formula_values(candidate, path=str(field))
        if formula_paths:
            rejected_patch_fields.append(str(field))
            required_decisions.append(
                f"'{field}' contained a formula and was excluded from the correction draft."
            )
            continue
        if not _candidate_is_grounded(cleaned, focused_row):
            rejected_patch_fields.append(str(field))
            required_decisions.append(
                f"Provide source evidence for the proposed '{field}' value before mapping it."
            )
            continue
        annotation = ManualIntegrationCreate.model_fields[str(field)].annotation
        try:
            validated: object = TypeAdapter(annotation).validate_python(cleaned)
        except ValidationError:
            rejected_patch_fields.append(str(field))
            required_decisions.append(
                f"The proposed '{field}' value does not satisfy the current App field type."
            )
            continue
        if (
            str(field) in current_proposed_record
            and current_proposed_record[str(field)] == validated
        ):
            no_op_patch_fields.append(str(field))
            continue
        safe_patch[str(field)] = validated

    known_ignored_headers = {
        str(item.get("source_header"))
        for item in _dicts(focused_row.get("ignored_source_fields"))
    }
    excluded_fields = [
        header
        for header in _strings(decoded.get("excluded_fields"))
        if header in known_ignored_headers
    ]
    return {
        "explanation": explanation,
        "deviations": deviations,
        "proposed_patch": safe_patch,
        "excluded_fields": excluded_fields,
        "required_decisions": list(dict.fromkeys(required_decisions)),
        "rejected_patch_fields": sorted(set(rejected_patch_fields)),
        "no_op_patch_fields": sorted(set(no_op_patch_fields)),
    }
