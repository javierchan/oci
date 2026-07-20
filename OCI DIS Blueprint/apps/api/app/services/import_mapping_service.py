"""Deterministic intake contracts for external workbook mapping review."""

from __future__ import annotations

import hashlib
from collections import Counter
from unicodedata import normalize

from app.core.calc_engine import HEADER_ALIASES


CONTRACT_VERSION = "1.1.0"
CONTRACT_ENFORCED_METADATA_KEY = "__mapping_contract_enforced__"
CONTRACT_METADATA_KEY = "__mapping_contract__"
EVIDENCE_ONLY = "evidence_only"

CANONICAL_FIELDS = tuple(HEADER_ALIASES.keys())
SEMANTIC_FIELDS = {"payload_per_execution_kb", "is_fan_out", "fan_out_targets"}
COMPLEXITY_ALIASES = {
    "muy alto": "High",
    "very high": "High",
    "alto": "High",
    "high": "High",
    "medio": "Medium",
    "medium": "Medium",
    "bajo": "Low",
    "low": "Low",
}


def normalize_header(value: str) -> str:
    collapsed = " ".join(value.strip().lower().replace("\n", " ").split())
    return normalize("NFKD", collapsed).encode("ascii", "ignore").decode("ascii")


def header_fingerprint(headers: dict[str, str]) -> str:
    source = "|".join(f"{index}:{normalize_header(label)}" for index, label in sorted(headers.items(), key=lambda item: int(item[0])))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _matches(alias: str, header: str) -> bool:
    return header == alias or header.startswith(f"{alias} ") or header.startswith(f"{alias}(") or header.startswith(f"{alias}:") or header.startswith(f"{alias}-")


def _proposed_target(header: str) -> str:
    normalized = normalize_header(header)
    for target, aliases in HEADER_ALIASES.items():
        if any(_matches(normalize_header(alias), normalized) for alias in aliases):
            return target
    return EVIDENCE_ONLY


def _sample_values(rows: list[dict[str, object]], header: str) -> list[str]:
    samples: list[str] = []
    for row in rows:
        value = row.get(header)
        if value in (None, ""):
            continue
        text = str(value).strip()
        if text and text not in samples:
            samples.append(text[:120])
        if len(samples) == 3:
            break
    return samples


def _question(identifier: str, prompt: str, reason: str, options: list[tuple[str, str]]) -> dict[str, object]:
    return {
        "id": identifier,
        "prompt": prompt,
        "reason": reason,
        "required": True,
        "options": [{"value": value, "label": label} for value, label in options],
    }


def contract_items(contract: dict[str, object], key: str) -> list[dict[str, object]]:
    """Return only object entries from an untrusted persisted contract payload."""

    value = contract.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def build_mapping_contract(
    headers: dict[str, str],
    rows: list[dict[str, object]],
    formula_columns: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Build a safe, reviewable proposal without applying a semantic inference."""

    formulas_by_header = {
        str(item.get("source_header", "")): item
        for item in (formula_columns or [])
        if item.get("source_header")
    }
    fields: list[dict[str, object]] = []
    questions: list[dict[str, object]] = []
    proposed_targets: set[str] = set()
    for index, header in sorted(headers.items(), key=lambda item: int(item[0])):
        formula_evidence = formulas_by_header.get(header)
        protects_column = bool(
            formula_evidence and formula_evidence.get("operational_policy") == "evidence_only"
        )
        target = EVIDENCE_ONLY if protects_column else _proposed_target(header)
        if target in proposed_targets:
            target = EVIDENCE_ONLY
        if target != EVIDENCE_ONLY:
            proposed_targets.add(target)
        field: dict[str, object] = {
                "source_index": index,
                "source_header": header,
                "target_field": target,
                "proposed_target": target,
                "confidence": "high" if target != EVIDENCE_ONLY or formula_evidence else "low",
                "sample_values": _sample_values(rows, header),
            }
        if formula_evidence:
            field.update(
                {
                    "formula_policy": formula_evidence.get("operational_policy", "formula_rows_only"),
                    "formula_classification": formula_evidence.get("classification", "needs_review"),
                    "formula_count": formula_evidence.get("formula_count", 0),
                }
            )
        fields.append(field)

        normalized = normalize_header(header)
        if (
            target in {"payload_per_execution_kb", EVIDENCE_ONLY}
            and ("tamano" in normalized or "size" in normalized)
        ):
            questions.append(
                _question(
                    f"payload:{index}",
                    f"Does '{header}' represent the payload of one operation?",
                    "The App only uses this field for payload per execution. Mapping an aggregate here would distort sizing and cost.",
                    [("per_operation", "Yes, one operation"), ("evidence_only", "No, retain as evidence only")],
                )
            )
        if "volumetr" in normalized or "volume" in normalized:
            questions.append(
                _question(
                    f"aggregate:{index}",
                    f"What does '{header}' measure?",
                    "Aggregate volumes need a period and fan-out interpretation before they can become governed demand.",
                    [
                        ("monthly_operations", "Operations per month"),
                        ("daily_operations", "Operations per day"),
                        ("already_includes_fanout", "Aggregate already includes destinations"),
                        ("evidence_only", "Keep as evidence only"),
                    ],
                )
            )
        if "ejecuciones total" in normalized or "total executions" in normalized:
            questions.append(
                _question(
                    f"execution_total:{index}",
                    f"What period and scope does '{header}' represent?",
                    "A total execution count can mean daily frequency, monthly demand, or a fan-out aggregate. The App must not guess because each interpretation produces different sizing.",
                    [
                        ("daily_operations", "Operations per day"),
                        ("monthly_operations", "Operations per month"),
                        ("includes_fanout", "Aggregate includes fan-out destinations"),
                        ("evidence_only", "Keep as evidence only"),
                    ],
                )
            )

    complexity_field = next((field for field in fields if field["target_field"] == "complexity"), None)
    if complexity_field:
        values = Counter(
            normalize_header(str(row.get(str(complexity_field["source_header"]), "")))
            for row in rows
            if row.get(str(complexity_field["source_header"])) not in (None, "")
        )
        unknown = sorted(value for value in values if value and value not in {"low", "medium", "high", "bajo", "medio", "alto"})
        for value in unknown[:5]:
            questions.append(
                _question(
                    f"complexity:{value}",
                    f"How should complexity value '{value}' be governed?",
                    "Complexity must use the App dictionary and cannot become a new global option through import.",
                    [
                        ("High", "High"),
                        ("Medium", "Medium"),
                        ("Low", "Low"),
                        ("evidence_only", "Keep as evidence only"),
                    ],
                )
            )

    return {
        "version": CONTRACT_VERSION,
        "header_fingerprint": header_fingerprint(headers),
        "fields": fields,
        "questions": questions,
        "answers": {},
        "source_kind": "external_workbook",
        "formula_columns": formula_columns or [],
        "formula_policy": "preserve_without_execution",
    }


def validate_contract_update(
    contract: dict[str, object],
    fields: list[dict[str, str]],
    answers: dict[str, str],
    *,
    require_complete: bool = True,
) -> dict[str, object]:
    """Validate user choices against the staged source contract and return a new contract."""

    contract_fields = contract_items(contract, "fields")
    available = {str(item["source_header"]): item for item in contract_fields}
    targets: set[str] = set()
    updated_fields: list[dict[str, object]] = []
    for selected in fields:
        source_header = selected["source_header"]
        target_field = selected["target_field"]
        base = available.get(source_header)
        if base is None:
            raise ValueError(f"Unknown source header '{source_header}'.")
        if target_field not in CANONICAL_FIELDS and target_field != EVIDENCE_ONLY:
            raise ValueError(f"Unsupported target field '{target_field}'.")
        if base.get("formula_policy") == "evidence_only" and target_field != EVIDENCE_ONLY:
            raise ValueError(
                f"Formula column '{source_header}' is immutable evidence and cannot be operationalized. Map its source inputs instead."
            )
        if target_field != EVIDENCE_ONLY and target_field in targets:
            raise ValueError(f"Only one source column can map to '{target_field}'.")
        if target_field != EVIDENCE_ONLY:
            targets.add(target_field)
        updated_fields.append({**base, "target_field": target_field})

    if require_complete and len(updated_fields) != len(available):
        raise ValueError("Every source column must be classified before approval.")

    if not require_complete:
        selected_by_header = {str(item["source_header"]): item for item in updated_fields}
        updated_fields = [
            selected_by_header.get(str(item["source_header"]), item)
            for item in contract_fields
        ]

    questions = contract_items(contract, "questions")
    required_ids = {str(item["id"]) for item in questions if item.get("required")}
    missing = sorted(identifier for identifier in required_ids if not answers.get(identifier))
    if require_complete and missing:
        raise ValueError(f"Answer required mapping guidance before approval: {', '.join(missing)}.")

    payload_questions = [item for item in questions if str(item.get("id", "")).startswith("payload:")]
    for question in payload_questions:
        index = str(question["id"]).split(":", 1)[1]
        field = next((item for item in updated_fields if str(item["source_index"]) == index), None)
        if field and answers.get(str(question["id"])) not in {None, "", "per_operation"}:
            field["target_field"] = EVIDENCE_ONLY

    dictionary_aliases: dict[str, str] = {}
    for identifier, answer in answers.items():
        if identifier.startswith("complexity:") and answer != EVIDENCE_ONLY:
            dictionary_aliases[identifier.split(":", 1)[1]] = answer

    return {
        **contract,
        "fields": updated_fields,
        "answers": answers,
        "dictionary_aliases": dictionary_aliases,
        "status": "approved" if require_complete else "mapping_review",
    }


def approved_header_map(header_map: dict[str, str], contract: dict[str, object]) -> dict[str, str]:
    """Make approved user mappings authoritative over automatic header aliases."""

    mapped = dict(header_map)
    mapped[CONTRACT_ENFORCED_METADATA_KEY] = "true"
    mapped[CONTRACT_METADATA_KEY] = "approved"
    for field in CANONICAL_FIELDS:
        mapped[field] = "-1"
    for item in contract_items(contract, "fields"):
        target = str(item.get("target_field", EVIDENCE_ONLY))
        index = str(item.get("source_index", "-1"))
        if target in CANONICAL_FIELDS:
            mapped[target] = index
    return mapped


def apply_contract_values(raw_data: dict[str, object], contract: dict[str, object]) -> dict[str, object]:
    """Create a working copy for catalog materialization; never mutate source evidence."""

    values = dict(raw_data)
    for item in contract_items(contract, "fields"):
        target = str(item.get("target_field", EVIDENCE_ONLY))
        source = str(item.get("source_header", ""))
        if target in CANONICAL_FIELDS and source in raw_data:
            values[target] = raw_data[source]

    aliases = contract.get("dictionary_aliases", {})
    if isinstance(aliases, dict) and values.get("complexity") not in (None, ""):
        normalized = normalize_header(str(values["complexity"]))
        if normalized in aliases:
            values["complexity"] = aliases[normalized]
    return values


def operational_targets_for_sources(
    contract: dict[str, object],
    source_headers: set[str],
) -> set[str]:
    """Resolve approved targets whose source cells are protected formula evidence."""

    return {
        str(item.get("target_field"))
        for item in contract_items(contract, "fields")
        if str(item.get("source_header", "")) in source_headers
        and str(item.get("target_field", EVIDENCE_ONLY)) in CANONICAL_FIELDS
    }
