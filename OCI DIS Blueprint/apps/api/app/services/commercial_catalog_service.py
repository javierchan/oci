"""Governed OCI commercial-document ingestion and release management.

Official documents provide commercial semantics. Public APIs provide current
PAYG prices and structured product metadata. Neither source can silently approve
a mapping or mutate an already published BOM.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
from io import BytesIO
import json
import re
from fastapi import HTTPException
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pricing_engine import QuantityBehavior, QuantityRule, normalize_quantity
from app.models import (
    CommercialBillingSemanticOverride,
    CommercialDocumentSnapshot,
    CommercialEvidenceReference,
    CommercialException,
    CommercialMappingCandidate,
    CommercialRelease,
    CommercialRuleFamily,
    CommercialSku,
    GovernanceChangeSet,
    GovernanceSourceArtifact,
    PriceCatalogSnapshot,
    PriceItem,
    ServiceProductSkuMapping,
    SkuCommercialConstraint,
    SkuCommercialRelationship,
    SkuCommercialTerm,
)
from app.services import audit_service, storage_service
from app.services.commercial_document_parser import (
    PRICE_LIST_SHEET,
    CommercialWorkbookRecord,
    parse_oci_commercial_workbook,
)


PARSER_VERSION = "oci-commercial-workbook-1.3.0"
GENERATOR_VERSION = "commercial-product-factory-1.2.0"
DOCUMENT_KIND = "oracle_localizable_price_list"
FIELD_AUTHORITY = {
    "contract_rate": "authorized_customer_rate_card",
    "public_payg_rate_and_tiers": "oracle_public_pricing_api",
    "commitment_minimum_billing_semantics": "oracle_localizable_price_list",
    "entitlements_and_prerequisites": "oracle_price_list_supplement",
    "price_type_decimal_availability_identity": "cloud_estimator_products",
    "metric_identity_and_display": "cloud_estimator_metrics",
    "estimator_composition_hints": "cloud_estimator_presets",
}
_MINUTE_PATTERN = re.compile(r"(?:one|1)[ -]minute minimum", re.IGNORECASE)
_INCREMENT_PATTERNS = (
    re.compile(
        r"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>GB|TB|MB|KB|OCPU|ECPU|requests?|messages?)\s+increments?",
        re.IGNORECASE,
    ),
    re.compile(
        r"increments?\s+of\s+(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>GB|TB|MB|KB|OCPU|ECPU|requests?|messages?)",
        re.IGNORECASE,
    ),
)


def _now() -> datetime:
    return datetime.now(UTC)


def _decimal_payload(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    return value


def _metadata_text_list(metadata: dict[str, object], key: str) -> list[str]:
    value = metadata.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _metadata_paths(metadata: dict[str, object]) -> list[list[str]]:
    value = metadata.get("product_paths")
    if not isinstance(value, list):
        return []
    return [
        [item for item in path if isinstance(item, str)]
        for path in value
        if isinstance(path, list)
    ]


def _metadata_object(metadata: dict[str, object], key: str) -> dict[str, object]:
    value = metadata.get(key)
    return value if isinstance(value, dict) else {}


def _structured_label(row: dict[str, object]) -> str | None:
    for key in ("name", "displayName", "display_name", "label", "title"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _structured_identifier(row: dict[str, object]) -> str | None:
    for key in ("id", "key", "metricId", "metric_id", "presetId", "preset_id"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _structured_product_summary(structured: dict[str, object] | None) -> dict[str, object]:
    """Keep reviewable Estimator identity without persisting the full source blob."""

    if not structured:
        return {}

    def summaries(value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        result: list[dict[str, object]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            identifier = _structured_identifier(item)
            label = _structured_label(item)
            if identifier or label:
                summary: dict[str, object] = {
                    key: field
                    for key, field in (("id", identifier), ("name", label))
                    if field
                }
                for key in (
                    "quantity",
                    "recommendedQuantity",
                    "minQuantity",
                    "allowZeroQuantity",
                    "weight",
                    "partNumber",
                ):
                    field = item.get(key)
                    if isinstance(field, (str, int, float, bool)):
                        summary[key] = field
                preset = item.get("preset")
                if isinstance(preset, dict):
                    preset_id = _structured_identifier(preset)
                    preset_name = _structured_label(preset)
                    summary["preset"] = {
                        key: field
                        for key, field in (("id", preset_id), ("name", preset_name))
                        if field
                    }
                result.append(summary)
        return result

    product_id = _structured_identifier(structured)
    product_name = _structured_label(structured)
    return {
        key: value
        for key, value in (
            ("id", product_id),
            ("name", product_name),
            ("metrics", summaries(structured.get("_governed_metrics"))),
            ("presets", summaries(structured.get("_governed_presets"))),
        )
        if value not in (None, [], {})
    }


def _string_list(value: object) -> list[str]:
    """Return only non-empty strings from persisted JSON list evidence."""

    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _price_state(value: object) -> str:
    if isinstance(value, Decimal):
        return "numeric"
    if value is None:
        return "blank"
    normalized = str(value).strip().casefold()
    if normalized == "-":
        return "not_offered"
    if normalized == "always free":
        return "always_free"
    if "additional information" in normalized:
        return "conditional_reference"
    return "textual_condition"


def _commercial_prices(record: CommercialWorkbookRecord) -> list[dict[str, object]]:
    return [
        {
            "term_type": term.term_type,
            "value": _decimal_payload(term.value),
            "value_state": term.value_state or _price_state(term.value),
            "source_cell": term.source_cell,
            "source_label": term.source_label,
        }
        for term in record.commercial_price_terms
    ]


def _price_type(metric_name: str | None, structured: dict[str, object] | None) -> str:
    if structured:
        for row in _walk_dicts(structured):
            value = row.get("priceType") or row.get("price_type")
            if isinstance(value, str) and value.strip():
                return value.strip().upper().replace("-", "_")
    normalized = (metric_name or "").casefold()
    if "utilized" in normalized and "hour" in normalized:
        return "HOUR_UTILIZED"
    if "per hour" in normalized or normalized.endswith(" hour"):
        return "HOUR"
    if "per day" in normalized or normalized.endswith(" day"):
        return "DAY"
    if "per month" in normalized or normalized.endswith(" month"):
        return "MONTH"
    return "PER_ITEM"


def _allow_decimal(structured: dict[str, object] | None, record: CommercialWorkbookRecord) -> bool | None:
    if structured:
        for row in _walk_dicts(structured):
            for key in ("allowDecimalQty", "allow_decimal_qty", "allowDecimalQuantity"):
                value = row.get(key)
                if isinstance(value, bool):
                    return value
    # A minimum is not evidence of the billing increment. For example, an
    # integer minimum can still apply to a continuously metered quantity.
    # Leave the value unresolved when the structured product catalog does not
    # explicitly publish decimal support.
    return None


def _walk_dicts(value: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if isinstance(value, dict):
        rows.append(value)
        for child in value.values():
            rows.extend(_walk_dicts(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_walk_dicts(child))
    return rows


async def _approved_structured_source_set(
    db: AsyncSession,
) -> tuple[
    GovernanceChangeSet | None,
    dict[str, dict[str, object]],
    dict[str, dict[str, object]],
]:
    """Load products, metrics, and presets from one approved atomic change set."""

    change_set = await db.scalar(
        select(GovernanceChangeSet)
        .where(
            GovernanceChangeSet.validation_status == "passed",
            GovernanceChangeSet.approval_status.in_(("approved", "not_required")),
            GovernanceChangeSet.status.in_(("promoted", "no_change")),
        )
        .order_by(
            GovernanceChangeSet.promoted_at.desc(),
            GovernanceChangeSet.created_at.desc(),
        )
    )
    if change_set is None:
        return None, {}, {}
    artifacts: dict[str, GovernanceSourceArtifact] = {}
    source_rows = list(
        (
            await db.scalars(
                select(GovernanceSourceArtifact).where(
                    GovernanceSourceArtifact.change_set_id == change_set.id,
                    GovernanceSourceArtifact.source_kind.in_(("products", "metrics", "presets")),
                    GovernanceSourceArtifact.retrieval_status == "verified",
                )
            )
        ).all()
    )
    artifacts = {artifact.source_kind: artifact for artifact in source_rows}

    products_artifact = artifacts.get("products")
    if products_artifact is None:
        return change_set, {}, {
            source_kind: {
                "artifact_id": artifact.id,
                "content_hash": artifact.content_hash,
                "record_count": artifact.record_count,
            }
            for source_kind, artifact in artifacts.items()
        }

    payloads = {
        source_kind: await asyncio.to_thread(
            storage_service.read_json, artifact.storage_reference
        )
        for source_kind, artifact in artifacts.items()
    }
    payload = payloads["products"]
    metric_rows = _walk_dicts(payloads.get("metrics", {}))
    preset_rows = _walk_dicts(payloads.get("presets", {}))

    def identity_index(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
        indexed_rows: dict[str, dict[str, object]] = {}
        for row in rows:
            for key in ("id", "key", "metricId", "metric_id", "presetId", "preset_id"):
                value = row.get(key)
                if isinstance(value, str) and value.strip():
                    indexed_rows.setdefault(value.strip(), row)
        return indexed_rows

    metric_index = identity_index(metric_rows)
    preset_index = identity_index(preset_rows)
    preset_memberships: dict[str, list[dict[str, object]]] = {}
    presets_payload = payloads.get("presets", {})
    preset_items = presets_payload.get("items") if isinstance(presets_payload, dict) else None
    for preset in preset_items if isinstance(preset_items, list) else []:
        if not isinstance(preset, dict):
            continue
        preset_identity = {
            "id": preset.get("id"),
            "name": preset.get("displayName") or preset.get("name"),
        }
        components = preset.get("presetItems")
        if not isinstance(components, list):
            continue
        for component in components:
            if not isinstance(component, dict):
                continue
            product = component.get("product")
            if not isinstance(product, dict):
                continue
            part_number = product.get("partNumber")
            if not isinstance(part_number, str) or not part_number.strip():
                continue
            preset_memberships.setdefault(part_number.strip().upper(), []).append(
                {
                    "id": f"{preset_identity.get('id')}:{product.get('id')}",
                    "name": product.get("displayName") or part_number,
                    "partNumber": part_number.strip().upper(),
                    "quantity": component.get("quantity"),
                    "recommendedQuantity": component.get("recommendedQuantity"),
                    "minQuantity": component.get("minQuantity"),
                    "allowZeroQuantity": component.get("allowZeroQuantity"),
                    "weight": component.get("weight"),
                    "preset": preset_identity,
                }
            )

    def referenced_values(row: dict[str, object], token: str) -> set[str]:
        references: set[str] = set()
        for key, value in row.items():
            if token not in key.casefold():
                continue
            if isinstance(value, str) and value.strip():
                references.add(value.strip())
            elif isinstance(value, list):
                references.update(
                    str(item).strip()
                    for item in value
                    if isinstance(item, (str, int)) and str(item).strip()
                )
        return references

    indexed: dict[str, dict[str, object]] = {}
    for row in _walk_dicts(payload):
        part_number = row.get("partNumber") or row.get("part_number")
        if isinstance(part_number, str) and part_number.strip():
            enriched = dict(row)
            metric_references = referenced_values(row, "metric")
            preset_references = referenced_values(row, "preset")
            enriched["_governed_metrics"] = [
                metric_index[reference]
                for reference in sorted(metric_references)
                if reference in metric_index
            ]
            referenced_presets = [
                preset_index[reference]
                for reference in sorted(preset_references)
                if reference in preset_index
            ]
            enriched["_governed_presets"] = [
                *referenced_presets,
                *preset_memberships.get(part_number.strip().upper(), []),
            ]
            indexed.setdefault(part_number.strip().upper(), enriched)
    return change_set, indexed, {
        source_kind: {
            "artifact_id": artifact.id,
            "content_hash": artifact.content_hash,
            "record_count": artifact.record_count,
        }
        for source_kind, artifact in artifacts.items()
    }


def _rule_semantics(
    *,
    formula_key: str,
    metric_pattern: str,
    price_type: str,
    behavior: str,
    increment: Decimal,
    minimum: Decimal,
    rounding: str,
    proration: str,
) -> dict[str, object]:
    return {
        "formula_key": formula_key,
        "metric_pattern": metric_pattern,
        "price_types": [price_type],
        "quantity_behavior": behavior,
        "quantity_increment": str(increment),
        "minimum_quantity": str(minimum),
        "aggregation_window": "calendar_month",
        "proration_policy": proration,
        "quote_rounding": rounding,
    }


def _rule_semantics_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _next_rule_version(rule: CommercialRuleFamily | None) -> str:
    if rule is None:
        return "1.0.0"
    try:
        major, minor, patch = (int(value) for value in rule.version.split(".", 2))
    except (TypeError, ValueError):
        return f"{rule.version}.1"
    return f"{major}.{minor}.{patch + 1}"


def _metric_scope(metric_name: str | None) -> tuple[str, str | None]:
    if not metric_name:
        return "unspecified", None
    unit = re.split(r"\s+per\s+", metric_name, flags=re.IGNORECASE)[0].strip()
    if "per hour" in metric_name.casefold():
        return "provisioned_capacity", unit or None
    if "per month" in metric_name.casefold():
        return "monthly_billed_quantity", unit or None
    return "billed_quantity", unit or None


def _constraints(record: CommercialWorkbookRecord) -> list[dict[str, object]]:
    constraints: list[dict[str, object]] = []
    price_evidence = next(
        (item for item in record.source_evidence if item.sheet == PRICE_LIST_SHEET),
        record.source_evidence[0],
    )
    minimum_cell = next(
        (
            cell.coordinate
            for cell in price_evidence.cells
            if record.metric_minimum is not None and str(cell.value) == str(record.metric_minimum)
        ),
        f"ROW{price_evidence.row}",
    )
    if isinstance(record.metric_minimum, Decimal):
        scope, unit = _metric_scope(record.metric)
        constraints.append(
            {
                "constraint_type": "metric_minimum",
                "scope": scope,
                "numeric_value": record.metric_minimum,
                "text_value": None,
                "unit": unit,
                "behavior": "minimum",
                "source_cell": minimum_cell,
            }
        )
    guidance = record.additional_information or ""
    if "billed per second" in guidance.casefold():
        constraints.append(
            {
                "constraint_type": "billing_granularity",
                "scope": "usage_time",
                "numeric_value": Decimal("1"),
                "text_value": "per second",
                "unit": "second",
                "behavior": "prorated",
                "source_cell": f"ROW{price_evidence.row}",
            }
        )
    if _MINUTE_PATTERN.search(guidance):
        constraints.append(
            {
                "constraint_type": "minimum_duration",
                "scope": "usage_time",
                "numeric_value": Decimal("60"),
                "text_value": "one-minute minimum",
                "unit": "second",
                "behavior": "minimum",
                "source_cell": f"ROW{price_evidence.row}",
            }
        )
    increment_matches = sorted(
        (
            match
            for pattern in _INCREMENT_PATTERNS
            for match in pattern.finditer(guidance)
        ),
        key=lambda match: match.start(),
    )
    for index, match in enumerate(increment_matches, start=1):
        context = guidance[max(0, match.start() - 80) : match.end() + 40].casefold()
        if "backup" in context:
            scope = "backup_storage_quantity"
        elif "storage" in context:
            scope = "database_storage_quantity"
        else:
            scope = "commercial_quantity"
        constraints.append(
            {
                "constraint_type": "purchase_increment",
                "scope": scope,
                "numeric_value": Decimal(match.group("value").replace(",", "")),
                "text_value": match.group(0),
                "unit": match.group("unit"),
                "behavior": "round_up",
                "source_cell": f"ROW{price_evidence.row}-{index}",
            }
        )
    for term in record.commercial_price_terms:
        label = (term.source_label or "").casefold()
        threshold_match = re.search(r"(?:first|greater than|over)\s+(\d[\d,]*)", label)
        if term.value_state == "free_tier" and threshold_match:
            constraints.append(
                {
                    "constraint_type": "free_tier_allowance",
                    "scope": "monthly_billed_quantity",
                    "numeric_value": Decimal(threshold_match.group(1).replace(",", "")),
                    "text_value": term.source_label,
                    "unit": _metric_scope(record.metric)[1],
                    "behavior": "subtract_before_pricing",
                    "source_cell": term.source_cell,
                }
            )
        elif term.value_state == "numeric" and threshold_match and (
            "greater than" in label or label.startswith("over ")
        ):
            constraints.append(
                {
                    "constraint_type": "paid_tier_start",
                    "scope": term.term_type,
                    "numeric_value": Decimal(threshold_match.group(1).replace(",", "")),
                    "text_value": term.source_label,
                    "unit": _metric_scope(record.metric)[1],
                    "behavior": "lower_exclusive",
                    "source_cell": term.source_cell,
                }
            )
        if term.term_type.endswith("_minimum") and isinstance(term.value, Decimal):
            constraints.append(
                {
                    "constraint_type": "commitment_minimum",
                    "scope": term.term_type.removesuffix("_minimum"),
                    "numeric_value": term.value,
                    "text_value": term.source_label,
                    "unit": record.metric or "Currency Unit",
                    "behavior": "eligibility_threshold",
                    "source_cell": term.source_cell,
                }
            )
    combined_guidance = "\n".join(
        value
        for value in (
            record.additional_information,
            record.included_entitlements,
            record.prerequisites,
        )
        if value and value.strip() != "-"
    )
    if "byol" in record.service_name.casefold() or "byol requirements" in combined_guidance.casefold():
        constraints.append(
            {
                "constraint_type": "license_eligibility",
                "scope": "byol",
                "numeric_value": None,
                "text_value": "Customer entitlement evidence is required for BYOL pricing.",
                "unit": None,
                "behavior": "block_without_evidence",
                "source_cell": f"ROW{price_evidence.row}",
            }
        )
    return constraints


def _meaningful_document_text(value: str | None) -> bool:
    return bool(value and value.strip() and value.strip() != "-")


def _family_key(price_type: str, metric_name: str | None) -> str:
    metric = re.sub(r"[^a-z0-9]+", "-", (metric_name or "unit").casefold()).strip("-")
    return f"{price_type.casefold()}::{metric[:80]}"


def _quantity_behavior(price_type: str, allow_decimal: bool | None) -> tuple[str, Decimal, str, str]:
    if allow_decimal is False:
        return "packaged", Decimal("1"), "ceil_increment", "not_prorated"
    if price_type in {"HOUR", "HOUR_UTILIZED", "DAY"}:
        return "continuous", Decimal("0.000001"), "metered", "prorated"
    if price_type == "MONTH" and allow_decimal is not True:
        return "fixed_capacity", Decimal("1"), "ceil_increment", "not_prorated"
    return "continuous", Decimal("0.000001"), "metered", "prorated"


def _commercial_decimal_availability(
    part_number: str,
    estimator_allow_decimal: bool | None,
    overrides: dict[str, bool | None],
) -> bool | None:
    """Apply documented billing semantics over estimator input hints."""

    return overrides.get(part_number.upper(), estimator_allow_decimal)


async def _approved_billing_semantic_overrides(
    db: AsyncSession,
) -> dict[str, bool | None]:
    """Load approved per-SKU billing semantics once for a generation request."""

    rows = (
        await db.scalars(
            select(CommercialBillingSemanticOverride).where(
                CommercialBillingSemanticOverride.status == "approved"
            )
        )
    ).all()
    return {row.part_number.upper(): row.allow_decimal_quantity for row in rows}


def _commercial_fixture_result(
    *,
    behavior: str,
    increment: Decimal,
    minimum: Decimal,
    price_type: str,
    api_items: list[PriceItem],
) -> tuple[bool, list[dict[str, object]]]:
    """Validate generated semantics against generic commercial invariants."""

    checks: list[dict[str, object]] = []

    def record_check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": passed, "detail": detail})

    try:
        rule = QuantityRule(behavior=QuantityBehavior(behavior), increment=increment, minimum=minimum)
        cases = (Decimal("0"), minimum, minimum + increment, minimum + increment * Decimal("1.5"))
        results = tuple(normalize_quantity(value, rule) for value in cases)
        generic_passed = results[0] == Decimal("0") and all(
            result >= minimum and result >= value
            for result, value in zip(results[1:], cases[1:], strict=True)
        )
    except (ArithmeticError, ValueError):
        generic_passed = False
    record_check(
        "quantity_normalization",
        generic_passed,
        "Zero remains inactive and positive demand respects increment/minimum.",
    )
    if api_items:
        supported_models = {"PAY_AS_YOU_GO", "ANNUAL_COMMITMENT", "ANNUAL_FLEX", "MONTHLY_FLEX"}
        models_passed = all(item.model in supported_models for item in api_items)
        record_check(
            "commercial_models",
            models_passed,
            "Every API price belongs to an explicitly supported purchase model.",
        )
    if price_type == "DAY":
        record_check(
            "day_metering",
            behavior == "continuous",
            "DAY-priced services must retain continuous metering semantics.",
        )
    return all(bool(check["passed"]) for check in checks), checks


async def _stable_sku(
    db: AsyncSession,
    *,
    part_number: str,
    display_name: str,
    service_category: str | None,
    source_product_id: str | None,
    products_artifact_id: str | None,
    product_hierarchy: tuple[str, ...] = (),
    product_paths: tuple[tuple[str, ...], ...] = (),
    structured_product: dict[str, object] | None = None,
    document_fingerprint: str | None = None,
) -> tuple[CommercialSku, dict[str, object] | None]:
    """Return the stable part-number identity without rewriting historical terms."""

    sku = await db.scalar(select(CommercialSku).where(CommercialSku.part_number == part_number))
    if sku is None:
        sku = CommercialSku(
            part_number=part_number,
            display_name=display_name,
            service_category=service_category,
            source_product_id=source_product_id,
            lifecycle_status="active",
            identity_metadata={
                "products_artifact_id": products_artifact_id,
                "product_hierarchy": list(product_hierarchy),
                "product_paths": [list(path) for path in product_paths],
                "structured_product": structured_product or {},
            },
        )
        db.add(sku)
        await db.flush()
        return sku, None

    # Identity metadata may be enriched, but immutable document terms retain the
    # exact source value that was current for each imported evidence snapshot.
    previous_hierarchy = _metadata_text_list(sku.identity_metadata, "product_hierarchy")
    current_hierarchy = list(product_hierarchy) or previous_hierarchy
    placement_drift: dict[str, object] | None = (
        {
            "part_number": part_number,
            "previous_product_hierarchy": previous_hierarchy,
            "current_product_hierarchy": current_hierarchy,
            "document_fingerprint": document_fingerprint,
        }
        if previous_hierarchy and current_hierarchy and previous_hierarchy != current_hierarchy
        else None
    )
    raw_history = sku.identity_metadata.get("canonical_placement_history")
    placement_history = (
        [item for item in raw_history if isinstance(item, dict)]
        if isinstance(raw_history, list)
        else []
    )
    if placement_drift is not None:
        history_entry = {
            "product_hierarchy": previous_hierarchy,
            "superseded_by_document_fingerprint": document_fingerprint,
        }
        if history_entry not in placement_history:
            placement_history.append(history_entry)
    sku.display_name = display_name or sku.display_name
    sku.service_category = service_category or sku.service_category
    sku.source_product_id = source_product_id or sku.source_product_id
    sku.identity_metadata = {
        **sku.identity_metadata,
        "products_artifact_id": products_artifact_id,
        "product_hierarchy": current_hierarchy,
        "product_paths": (
            [list(path) for path in product_paths]
            or _metadata_paths(sku.identity_metadata)
        ),
        "structured_product": structured_product or {},
        "canonical_placement_history": placement_history,
    }
    return sku, placement_drift


def _source_conflicts(
    record: CommercialWorkbookRecord | None,
    api_items: list[PriceItem],
    structured: dict[str, object] | None,
) -> list[tuple[str, str, dict[str, object]]]:
    """Find material disagreements while respecting field-level authority."""

    conflicts: list[tuple[str, str, dict[str, object]]] = []
    if record is not None and api_items:
        document_metric = (record.metric or "").strip().casefold()
        api_metrics = sorted({item.metric_name.strip() for item in api_items if item.metric_name.strip()})
        if document_metric and all(metric.casefold() != document_metric for metric in api_metrics):
            conflicts.append(
                (
                    "METRIC_SOURCE_CONFLICT",
                    "medium",
                    {
                        "document_metric": record.metric,
                        "api_metrics": api_metrics,
                        "authority": FIELD_AUTHORITY["metric_identity_and_display"],
                    },
                )
            )
    if record is not None and structured:
        document_name = record.service_name.strip().casefold()
        structured_name = str(structured.get("name") or structured.get("displayName") or "").strip()
        if structured_name and structured_name.casefold() != document_name:
            conflicts.append(
                (
                    "PRODUCT_IDENTITY_VARIANCE",
                    "low",
                    {
                        "document_name": record.service_name,
                        "structured_name": structured_name,
                        "authority": FIELD_AUTHORITY["price_type_decimal_availability_identity"],
                    },
                )
            )
    return conflicts


async def import_commercial_workbook(
    *, filename: str, contents: bytes, actor_id: str, db: AsyncSession
) -> dict[str, object]:
    """Persist one official workbook and generate reviewable commercial evidence."""

    content_hash = hashlib.sha256(contents).hexdigest()
    existing = await db.scalar(
        select(CommercialDocumentSnapshot).where(
            CommercialDocumentSnapshot.document_kind == DOCUMENT_KIND,
            CommercialDocumentSnapshot.content_hash == content_hash,
            CommercialDocumentSnapshot.parser_version == PARSER_VERSION,
        )
    )
    if existing is not None:
        return await commercial_workspace(db, document_id=existing.id)

    parsed = await asyncio.to_thread(parse_oci_commercial_workbook, BytesIO(contents))
    previous_document = await db.scalar(
        select(CommercialDocumentSnapshot)
        .where(CommercialDocumentSnapshot.document_kind == DOCUMENT_KIND)
        .order_by(CommercialDocumentSnapshot.created_at.desc())
    )
    if (
        previous_document is not None
        and previous_document.record_count >= 100
        and len(parsed.records) < previous_document.record_count * 0.8
    ):
        raise ValueError(
            "Commercial workbook SKU coverage dropped below 80% of the latest "
            f"governed snapshot ({len(parsed.records)} vs {previous_document.record_count}); "
            "review the Oracle workbook layout before importing"
        )
    storage_reference = await asyncio.to_thread(
        storage_service.put_bytes,
        f"governance/commercial-documents/{content_hash}/{storage_service.safe_filename(filename)}",
        contents,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        metadata={"sha256": content_hash, "document-kind": DOCUMENT_KIND},
    )
    change_set, structured_products, structured_artifacts = (
        await _approved_structured_source_set(db)
    )
    price_snapshot = (
        await db.get(PriceCatalogSnapshot, change_set.price_snapshot_id)
        if change_set is not None
        else None
    )
    if price_snapshot is None:
        price_snapshot = await db.scalar(
            select(PriceCatalogSnapshot)
            .where(
                PriceCatalogSnapshot.currency == "USD",
                PriceCatalogSnapshot.approval_status == "approved",
            )
            .order_by(PriceCatalogSnapshot.created_at.desc())
        )
    # Keep the document immutable even when no approved API snapshot exists.
    price_items: list[PriceItem] = []
    if price_snapshot is not None:
        price_items = list(
            (await db.scalars(select(PriceItem).where(PriceItem.snapshot_id == price_snapshot.id))).all()
        )
    price_by_part: dict[str, list[PriceItem]] = {}
    for price_item in price_items:
        price_by_part.setdefault(price_item.part_number.upper(), []).append(price_item)
    mappings = list(
        (await db.scalars(select(ServiceProductSkuMapping).where(ServiceProductSkuMapping.status == "approved"))).all()
    )
    mapping_by_part = {mapping.part_number.upper(): mapping for mapping in mappings if mapping.part_number}
    decimal_overrides = await _approved_billing_semantic_overrides(db)
    products_artifact_id = (
        str(structured_artifacts["products"]["artifact_id"])
        if "products" in structured_artifacts
        else None
    )

    document = CommercialDocumentSnapshot(
        document_kind=DOCUMENT_KIND,
        source_name="Oracle PaaS and IaaS Public Cloud Localizable Price List",
        source_url=None,
        original_filename=filename,
        storage_reference=storage_reference,
        content_hash=content_hash,
        parser_version=PARSER_VERSION,
        currency="USD",
        status="validating",
        record_count=len(parsed.records),
        retrieved_at=_now(),
        manifest={
            "field_authority": FIELD_AUTHORITY,
            "canonical_sku_count": len(parsed.records),
            "price_list_sku_count": parsed.price_record_count,
            "supplement_sku_count": parsed.supplement_record_count,
            "structured_artifacts": structured_artifacts,
            "price_snapshot_id": price_snapshot.id if price_snapshot else None,
            "governance_change_set_id": change_set.id if change_set else None,
            "hierarchy_mapped_sku_count": sum(
                1 for item in parsed.records if item.product_hierarchy
            ),
            "multi_location_sku_count": sum(
                1 for item in parsed.records if len(item.product_paths) > 1
            ),
        },
    )
    db.add(document)
    await db.flush()

    records_by_part = parsed.by_part_number()
    workbook_parts = set(records_by_part)
    api_parts = set(price_by_part)
    estimator_parts = set(structured_products)
    document.manifest = {
        **document.manifest,
        "source_reconciliation": {
            "workbook_sku_count": len(workbook_parts),
            "pricing_api_sku_count": len(api_parts),
            "estimator_product_sku_count": len(estimator_parts),
            "workbook_only_vs_pricing_api_count": len(workbook_parts - api_parts),
            "workbook_only_vs_pricing_api": sorted(workbook_parts - api_parts),
            "pricing_api_only_vs_workbook_count": len(api_parts - workbook_parts),
            "pricing_api_only_vs_workbook": sorted(api_parts - workbook_parts),
            "workbook_only_vs_estimator_count": len(workbook_parts - estimator_parts),
            "workbook_only_vs_estimator": sorted(workbook_parts - estimator_parts),
        },
    }
    all_parts = sorted(set(records_by_part) | set(price_by_part) | set(structured_products))
    exception_count = 0
    candidate_count = 0
    for part_number in all_parts:
        record = records_by_part.get(part_number)
        structured = structured_products.get(part_number)
        api_items = price_by_part.get(part_number, [])
        display_name = (
            record.service_name if record else None
        ) or (api_items[0].display_name if api_items else None) or str((structured or {}).get("name") or part_number)
        service_category = (
            record.service_category if record else None
        ) or (api_items[0].service_category if api_items else None)
        sku, placement_drift = await _stable_sku(
            db,
            part_number=part_number,
            display_name=display_name,
            service_category=service_category,
            source_product_id=str((structured or {}).get("id") or "") or None,
            products_artifact_id=products_artifact_id,
            product_hierarchy=record.product_hierarchy if record else (),
            product_paths=record.product_paths if record else (),
            structured_product=_structured_product_summary(structured),
            document_fingerprint=content_hash,
        )

        term: SkuCommercialTerm | None = None
        constraints: list[dict[str, object]] = []
        if record is not None:
            ptype = _price_type(record.metric, structured)
            decimal_allowed = _allow_decimal(structured, record)
            evidence_rows = [item.to_dict() for item in record.source_evidence]
            price_evidence = next(
                (item for item in record.source_evidence if item.sheet == PRICE_LIST_SHEET),
                record.source_evidence[0],
            )
            term = SkuCommercialTerm(
                document_snapshot_id=document.id,
                commercial_sku_id=sku.id,
                price_catalog_snapshot_id=price_snapshot.id if price_snapshot else None,
                part_number=part_number,
                service_name=record.service_name,
                service_category=record.service_category,
                commercial_prices=_commercial_prices(record),
                currency="USD",
                metric_name=record.metric,
                price_type=ptype,
                allow_decimal_quantity=decimal_allowed,
                availability=[],
                additional_information=record.additional_information,
                notes=record.notes,
                disposition="blocked_input_required",
                family_key=_family_key(ptype, record.metric),
                status="draft",
                confidence=0.95 if structured and api_items else 0.7,
                source_sheet=price_evidence.sheet,
                source_row=price_evidence.row,
                source_cells={"evidence": evidence_rows},
                extraction_metadata={
                    "parser_version": PARSER_VERSION,
                    "structured_artifacts": structured_artifacts,
                    "product_hierarchy": list(record.product_hierarchy),
                    "product_paths": [list(path) for path in record.product_paths],
                    "structured_product": _structured_product_summary(structured),
                },
            )
            db.add(term)
            await db.flush()
            constraints = _constraints(record)
            for constraint in constraints:
                db.add(
                    SkuCommercialConstraint(
                        term_id=term.id,
                        status="observed",
                        evidence_metadata={},
                        **constraint,
                    )
                )
            for source in record.source_evidence:
                db.add(
                    CommercialEvidenceReference(
                        entity_type="sku_commercial_term",
                        entity_id=term.id,
                        source_kind="price_list" if source.sheet == PRICE_LIST_SHEET else "supplement",
                        document_snapshot_id=document.id,
                        source_sheet=source.sheet,
                        source_row=source.row,
                        excerpt_hash=hashlib.sha256(
                            json.dumps(source.to_dict(), sort_keys=True, default=str).encode("utf-8")
                        ).hexdigest(),
                        evidence_metadata={"cells": [cell.to_dict() for cell in source.cells]},
                    )
                )
        else:
            ptype = api_items[0].price_type if api_items else _price_type(None, structured)
            decimal_allowed = None

        existing_mapping = mapping_by_part.get(part_number)
        numeric_price = bool(api_items) or bool(
            record and any(item["value_state"] == "numeric" for item in _commercial_prices(record))
        )
        always_free = bool(
            record and any(item["value_state"] == "always_free" for item in _commercial_prices(record))
        )
        has_prerequisite = bool(record and _meaningful_document_text(record.prerequisites))
        classification = (
            "included_non_billable"
            if always_free
            else "dependent_entitlement"
            if has_prerequisite and not numeric_price
            else "direct_metered"
            if api_items
            else "external_rate_card"
            if numeric_price
            else "blocked_input_required"
        )
        family_key = term.family_key if term else _family_key(ptype, record.metric if record else None)
        minimum = Decimal("0")
        minimum_scope: str | None = None
        for constraint in constraints:
            if constraint.get("constraint_type") != "metric_minimum":
                continue
            numeric_value = constraint.get("numeric_value")
            if isinstance(numeric_value, Decimal):
                minimum = numeric_value
            scope = constraint.get("scope")
            if isinstance(scope, str):
                minimum_scope = scope
        # products.json describes estimator input behavior, but the commercial
        # document controls billed metric semantics. API Gateway bills partial
        # million-call units, so an estimator whole-unit hint must not force a
        # ceiling into the governed BOM.
        decimal_allowed = _commercial_decimal_availability(
            part_number, decimal_allowed, decimal_overrides
        )
        behavior, increment, rounding, proration = _quantity_behavior(ptype, decimal_allowed)
        latest_rule = await db.scalar(
            select(CommercialRuleFamily).where(
                CommercialRuleFamily.family_key == family_key
            ).order_by(CommercialRuleFamily.created_at.desc())
        )
        formula_key = existing_mapping.formula_key if existing_mapping else "metered_quantity"
        metric_pattern = record.metric if record and record.metric else "Unspecified"
        semantics = _rule_semantics(
            formula_key=formula_key,
            metric_pattern=metric_pattern,
            price_type=ptype,
            behavior=behavior,
            increment=increment,
            minimum=minimum,
            rounding=rounding,
            proration=proration,
        )
        semantics_hash = _rule_semantics_hash(semantics)
        latest_hash = (
            str(latest_rule.evidence.get("semantics_hash")) if latest_rule is not None else None
        )
        rule = latest_rule if latest_hash == semantics_hash else None
        if rule is None:
            fixture_passed, fixture_checks = _commercial_fixture_result(
                behavior=behavior,
                increment=increment,
                minimum=minimum,
                price_type=ptype,
                api_items=api_items,
            )
            rule = CommercialRuleFamily(
                family_key=family_key,
                version=_next_rule_version(latest_rule),
                formula_key=formula_key,
                metric_pattern=metric_pattern,
                price_types=[ptype],
                quantity_behavior=behavior,
                quantity_increment=increment,
                minimum_quantity=minimum,
                aggregation_window="calendar_month",
                proration_policy=proration,
                quote_rounding=rounding,
                generator_version=GENERATOR_VERSION,
                status="ready_for_review" if fixture_passed else "blocked",
                fixture_status="passed" if fixture_passed else "failed",
                evidence={
                    "document_snapshot_id": document.id,
                    "part_number": part_number,
                    "semantics_hash": semantics_hash,
                    "structured_artifacts": structured_artifacts,
                    "supersedes_rule_id": latest_rule.id if latest_rule else None,
                    "fixture_checks": fixture_checks,
                },
            )
            db.add(rule)
            await db.flush()
            db.add(
                CommercialEvidenceReference(
                    entity_type="commercial_rule_family",
                    entity_id=rule.id,
                    source_kind="normalized_commercial_rule",
                    document_snapshot_id=document.id,
                    source_sheet=term.source_sheet if term else None,
                    source_row=term.source_row if term else None,
                    excerpt_hash=semantics_hash,
                    evidence_metadata={
                        "semantics": semantics,
                        "structured_artifacts": structured_artifacts,
                    },
                )
            )

        candidate = CommercialMappingCandidate(
            document_snapshot_id=document.id,
            commercial_sku_id=sku.id,
            term_id=term.id if term else None,
            price_item_id=api_items[0].id if api_items else None,
            existing_mapping_id=existing_mapping.id if existing_mapping else None,
            part_number=part_number,
            proposed_service_id=existing_mapping.service_id if existing_mapping else None,
            family_key=family_key,
            classification=classification,
            proposed_mapping={
                "price_type": ptype,
                "quantity_behavior": behavior,
                "quantity_increment": str(increment),
                "minimum_quantity": str(minimum),
                "minimum_scope": minimum_scope,
                "quote_rounding": rounding,
                "proration_policy": proration,
                "commercial_rule_family_id": rule.id,
                "field_authority": FIELD_AUTHORITY,
            },
            confidence=0.98 if existing_mapping and term and api_items else 0.75 if term and api_items else 0.4,
            generator_version=GENERATOR_VERSION,
            status="pending_review",
            reasons=[
                "Existing approved mapping matched by exact part number" if existing_mapping else "No existing service mapping",
                "Official document term present" if term else "Official document term missing",
                "Approved API price present" if api_items else "Approved API price missing",
            ],
        )
        db.add(candidate)
        await db.flush()
        candidate_count += 1

        exception_specs = _source_conflicts(record, api_items, structured)
        if placement_drift is not None:
            exception_specs.append(
                (
                    "CANONICAL_PRODUCT_PLACEMENT_DRIFT",
                    "medium",
                    placement_drift,
                )
            )
        if record is not None:
            exception_specs.extend(
                (
                    "REPEATED_SKU_SOURCE_CONFLICT",
                    "high",
                    {"part_number": part_number, **conflict},
                )
                for conflict in record.source_conflicts
            )
        if term is None:
            exception_specs.append(("DOCUMENT_TERM_MISSING", "high", {"part_number": part_number}))
        if numeric_price and not api_items:
            exception_specs.append(("API_PRICE_MISSING", "high", {"part_number": part_number}))
        if record and _meaningful_document_text(record.prerequisites):
            relationship = SkuCommercialRelationship(
                document_snapshot_id=document.id,
                source_term_id=term.id if term else None,
                source_commercial_sku_id=sku.id,
                target_commercial_sku_id=None,
                part_number=part_number,
                relationship_type="requires",
                target_part_number=None,
                target_name=record.prerequisites,
                guidance="Resolve the named prerequisite to an exact governed SKU before publication.",
                resolution_status="unresolved",
                confidence=0.35,
                status="needs_review",
                source_sheet=record.source_evidence[-1].sheet,
                source_row=record.source_evidence[-1].row,
                source_cell=f"ROW{record.source_evidence[-1].row}",
            )
            db.add(relationship)
            await db.flush()
            exception_specs.append(
                (
                    "DEPENDENCY_UNRESOLVED",
                    "high",
                    {
                        "relationship": record.prerequisites,
                        "relationship_id": relationship.id,
                    },
                )
            )
        if record and _meaningful_document_text(record.included_entitlements):
            db.add(
                SkuCommercialRelationship(
                    document_snapshot_id=document.id,
                    source_term_id=term.id if term else None,
                    source_commercial_sku_id=sku.id,
                    target_commercial_sku_id=None,
                    part_number=part_number,
                    relationship_type="includes",
                    target_part_number=None,
                    target_name=record.included_entitlements,
                    guidance="Informational entitlement; no independent SKU resolution is implied.",
                    resolution_status="documented",
                    confidence=0.8,
                    status="observed",
                    source_sheet=record.source_evidence[-1].sheet,
                    source_row=record.source_evidence[-1].row,
                    source_cell=f"ROW{record.source_evidence[-1].row}",
                )
            )
        for code, severity, details in exception_specs:
            db.add(
                CommercialException(
                    document_snapshot_id=document.id,
                    candidate_id=candidate.id,
                    part_number=part_number,
                    exception_code=code,
                    severity=severity,
                    status="open",
                    details=details,
                    proposed_resolution="Review official evidence and record an explicit governed decision.",
                )
            )
            exception_count += 1

    document.status = "review_required"
    document.manifest = {
        **document.manifest,
        "candidate_count": candidate_count,
        "exception_count": exception_count,
        "public_sku_count": len(set(price_by_part) | set(structured_products)),
        "coverage_complete": candidate_count == len(all_parts),
    }
    await audit_service.emit(
        event_type="commercial_document_imported",
        entity_type="commercial_document_snapshot",
        entity_id=document.id,
        actor_id=actor_id,
        old_value=None,
        new_value={
            "content_hash": content_hash,
            "record_count": document.record_count,
            "candidate_count": candidate_count,
            "exception_count": exception_count,
        },
        project_id=None,
        db=db,
    )
    await db.flush()
    return await commercial_workspace(db, document_id=document.id)


async def approve_document(document_id: str, actor_id: str, db: AsyncSession) -> dict[str, object]:
    document = await db.get(CommercialDocumentSnapshot, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail={"detail": "Commercial document not found", "error_code": "COMMERCIAL_DOCUMENT_NOT_FOUND"})
    if not bool(document.manifest.get("coverage_complete")):
        raise HTTPException(status_code=409, detail={"detail": "Every source SKU must have a candidate or exception", "error_code": "COMMERCIAL_DOCUMENT_COVERAGE_INCOMPLETE"})
    old_status = document.status
    document.status = "approved_evidence"
    document.approved_by = actor_id
    document.approved_at = _now()
    await audit_service.emit(
        "commercial_document_evidence_approved", "commercial_document_snapshot", document.id,
        actor_id, {"status": old_status}, {"status": document.status}, None, db,
    )
    await db.flush()
    return await commercial_workspace(db, document_id=document.id)


async def review_candidate(
    candidate_id: str, *, decision: str, rationale: str, actor_id: str, db: AsyncSession
) -> dict[str, object]:
    candidate = await db.get(CommercialMappingCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail={"detail": "Commercial candidate not found", "error_code": "COMMERCIAL_CANDIDATE_NOT_FOUND"})
    if decision not in {"approve", "reject", "keep_blocked"}:
        raise HTTPException(status_code=422, detail={"detail": "Unsupported candidate decision", "error_code": "COMMERCIAL_CANDIDATE_DECISION_INVALID"})
    document = await db.get(CommercialDocumentSnapshot, candidate.document_snapshot_id)
    if decision == "approve" and (document is None or document.status != "approved_evidence"):
        raise HTTPException(status_code=409, detail={"detail": "Approve the official document as evidence first", "error_code": "COMMERCIAL_DOCUMENT_APPROVAL_REQUIRED"})
    rule_id = candidate.proposed_mapping.get("commercial_rule_family_id")
    rule = (
        await db.get(CommercialRuleFamily, rule_id)
        if isinstance(rule_id, str)
        else None
    )
    if decision == "approve" and (
        rule is None or rule.fixture_status != "passed"
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The generated commercial rule fixture must pass before candidate approval",
                "error_code": "COMMERCIAL_RULE_FIXTURE_REQUIRED",
            },
        )
    term = await db.get(SkuCommercialTerm, candidate.term_id) if candidate.term_id else None
    if decision == "approve":
        open_exception_codes = set(
            (
                await db.scalars(
                    select(CommercialException.exception_code).where(
                        CommercialException.candidate_id == candidate.id,
                        CommercialException.status == "open",
                    )
                )
            ).all()
        )
        unresolved_relationship_statuses = set(
            (
                await db.scalars(
                    select(SkuCommercialRelationship.resolution_status).where(
                        SkuCommercialRelationship.document_snapshot_id
                        == candidate.document_snapshot_id,
                        SkuCommercialRelationship.part_number == candidate.part_number,
                        SkuCommercialRelationship.resolution_status.in_(
                            ("unresolved", "accepted_risk")
                        ),
                    )
                )
            ).all()
        )
        blockers = _catalog_finalization_blockers(
            candidate=candidate,
            rule=rule,
            term=term,
            open_exception_codes=open_exception_codes,
            unresolved_relationship_statuses=unresolved_relationship_statuses,
        )
        if blockers:
            raise HTTPException(
                status_code=409,
                detail={
                    "detail": "Resolve every deterministic commercial blocker before approval",
                    "error_code": "COMMERCIAL_CANDIDATE_APPROVAL_BLOCKED",
                    "blockers": blockers,
                },
            )
    old_status = candidate.status
    candidate.status = {"approve": "approved", "reject": "rejected", "keep_blocked": "blocked"}[decision]
    candidate.reviewed_by = actor_id
    candidate.reviewed_at = _now()
    candidate.reasons = [*candidate.reasons, f"Explicit review decision: {rationale}"]
    if candidate.term_id and decision == "approve":
        if term:
            term.status = "approved"
            term.disposition = candidate.classification
            term_constraints = list(
                (
                    await db.scalars(
                        select(SkuCommercialConstraint).where(
                            SkuCommercialConstraint.term_id == term.id
                        )
                    )
                ).all()
            )
            for constraint in term_constraints:
                constraint.status = "approved"
    if isinstance(rule_id, str) and decision == "approve":
        if rule and rule.fixture_status == "passed":
            rule.status = "approved"
            rule.approved_by = actor_id
            rule.approved_at = _now()
    await audit_service.emit(
        "commercial_candidate_reviewed", "commercial_mapping_candidate", candidate.id,
        actor_id, {"status": old_status}, {"status": candidate.status, "rationale": rationale}, None, db,
    )
    await db.flush()
    return await commercial_workspace(db, document_id=candidate.document_snapshot_id)


def _catalog_finalization_blockers(
    *,
    candidate: CommercialMappingCandidate,
    rule: CommercialRuleFamily | None,
    term: SkuCommercialTerm | None,
    open_exception_codes: set[str],
    unresolved_relationship_statuses: set[str],
) -> list[str]:
    """Return deterministic blockers for one global catalog disposition."""

    blockers: list[str] = []
    if candidate.classification not in {"direct_metered", "included_non_billable"}:
        blockers.append(f"classification:{candidate.classification}")
    if candidate.generator_version != GENERATOR_VERSION:
        blockers.append("candidate_generator_outdated")
    if term is None:
        blockers.append("document_term_missing")
    if candidate.classification == "direct_metered" and candidate.price_item_id is None:
        blockers.append("approved_api_price_missing")
    if rule is None:
        blockers.append("commercial_rule_missing")
    else:
        if rule.generator_version != GENERATOR_VERSION:
            blockers.append("rule_generator_outdated")
        if rule.fixture_status != "passed":
            blockers.append("commercial_fixture_not_passed")
    blockers.extend(f"open_exception:{code}" for code in sorted(open_exception_codes))
    blockers.extend(
        f"relationship_not_resolved:{status}"
        for status in sorted(unresolved_relationship_statuses)
    )
    return sorted(set(blockers))


async def finalize_catalog_review(
    document_id: str,
    *,
    rationale: str,
    actor_id: str,
    db: AsyncSession,
) -> dict[str, object]:
    """Record terminal dispositions for every SKU in one official catalog.

    This is an explicit administrator action, not autonomous agent approval. It
    approves only unambiguous candidates whose deterministic commercial fixture
    passes and blocks every other candidate with machine-readable reasons.
    """

    document = await db.get(CommercialDocumentSnapshot, document_id)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "Commercial document not found",
                "error_code": "COMMERCIAL_DOCUMENT_NOT_FOUND",
            },
        )
    if document.status != "approved_evidence":
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Approve the official document as evidence before finalizing the catalog review",
                "error_code": "COMMERCIAL_DOCUMENT_APPROVAL_REQUIRED",
            },
        )

    candidates = list(
        (
            await db.scalars(
                select(CommercialMappingCandidate).where(
                    CommercialMappingCandidate.document_snapshot_id == document.id
                )
            )
        ).all()
    )
    if not candidates:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The official document has no normalized SKU candidates",
                "error_code": "COMMERCIAL_CATALOG_EMPTY",
            },
        )

    # Candidate and rule generation is deterministic and does not grant approval.
    # Refresh stale generated semantics inside the same explicit Admin workflow so
    # the final disposition is evaluated against the current implementation, not
    # an obsolete generator version. Candidates without documentary terms remain
    # blocked by the finalization gates below.
    for candidate in candidates:
        if candidate.term_id and candidate.generator_version != GENERATOR_VERSION:
            await revalidate_candidate(
                candidate.id,
                actor_id,
                db,
                include_workspace=False,
            )
    await db.flush()

    rule_ids = {
        str(rule_id)
        for candidate in candidates
        if isinstance(
            rule_id := candidate.proposed_mapping.get("commercial_rule_family_id"), str
        )
    }
    rules = (
        list(
            (
                await db.scalars(
                    select(CommercialRuleFamily).where(
                        CommercialRuleFamily.id.in_(rule_ids)
                    )
                )
            ).all()
        )
        if rule_ids
        else []
    )
    rules_by_id = {rule.id: rule for rule in rules}
    term_ids = {candidate.term_id for candidate in candidates if candidate.term_id}
    terms = (
        list(
            (
                await db.scalars(
                    select(SkuCommercialTerm).where(SkuCommercialTerm.id.in_(term_ids))
                )
            ).all()
        )
        if term_ids
        else []
    )
    terms_by_id = {term.id: term for term in terms}
    open_exceptions = list(
        (
            await db.scalars(
                select(CommercialException).where(
                    CommercialException.document_snapshot_id == document.id,
                    CommercialException.status == "open",
                )
            )
        ).all()
    )
    exception_codes_by_part: dict[str, set[str]] = {}
    for commercial_exception in open_exceptions:
        if commercial_exception.part_number:
            exception_codes_by_part.setdefault(str(commercial_exception.part_number), set()).add(
                commercial_exception.exception_code
            )
    unresolved_relationships = list(
        (
            await db.scalars(
                select(SkuCommercialRelationship).where(
                    SkuCommercialRelationship.document_snapshot_id == document.id,
                    SkuCommercialRelationship.resolution_status.in_(
                        ("unresolved", "accepted_risk")
                    ),
                )
            )
        ).all()
    )
    relationship_statuses_by_part: dict[str, set[str]] = {}
    for relationship in unresolved_relationships:
        relationship_statuses_by_part.setdefault(relationship.part_number, set()).add(
            relationship.resolution_status
        )

    approved_count = 0
    blocked_count = 0
    unchanged_count = 0
    now = _now()
    finalization_reason = f"Explicit catalog finalization: {rationale}"
    for candidate in candidates:
        rule_id = candidate.proposed_mapping.get("commercial_rule_family_id")
        rule = rules_by_id.get(str(rule_id)) if isinstance(rule_id, str) else None
        term = terms_by_id.get(candidate.term_id) if candidate.term_id else None
        blockers = _catalog_finalization_blockers(
            candidate=candidate,
            rule=rule,
            term=term,
            open_exception_codes=exception_codes_by_part.get(candidate.part_number, set()),
            unresolved_relationship_statuses=relationship_statuses_by_part.get(
                candidate.part_number, set()
            ),
        )
        target_status = "blocked" if blockers else "approved"
        if target_status == "approved":
            approved_count += 1
        else:
            blocked_count += 1
        prior_blockers = _string_list(
            candidate.proposed_mapping.get("catalog_disposition_reasons")
        )
        candidate_changed = (
            candidate.status != target_status
            or candidate.reviewed_by != actor_id
            or prior_blockers != blockers
            or candidate.proposed_mapping.get("catalog_disposition") != target_status
        )
        if not candidate_changed:
            unchanged_count += 1
            continue
        candidate.status = target_status
        candidate.reviewed_by = actor_id
        candidate.reviewed_at = now
        candidate.proposed_mapping = {
            **candidate.proposed_mapping,
            "catalog_disposition": target_status,
            "catalog_disposition_reasons": blockers,
            "catalog_finalized_at": now.isoformat(),
        }
        existing_reasons = [
            reason
            for reason in candidate.reasons
            if not (
                isinstance(reason, str)
                and reason.startswith(
                    ("Explicit catalog finalization:", "Catalog blocker:")
                )
            )
        ]
        candidate.reasons = [
            *existing_reasons,
            *(f"Catalog blocker: {blocker}" for blocker in blockers),
            finalization_reason,
        ]

        if target_status == "approved":
            if term is not None:
                term.status = "approved"
                term.disposition = candidate.classification
                constraints = list(
                    (
                        await db.scalars(
                            select(SkuCommercialConstraint).where(
                                SkuCommercialConstraint.term_id == term.id
                            )
                        )
                    ).all()
                )
                for constraint in constraints:
                    constraint.status = "approved"
            if rule is not None:
                rule.status = "approved"
                rule.approved_by = actor_id
                rule.approved_at = now
        else:
            if term is not None:
                term.status = "blocked"
                term.disposition = candidate.classification

    if unchanged_count == len(candidates):
        return await commercial_workspace(db, document_id=document.id)

    document.manifest = {
        **document.manifest,
        "catalog_review": {
            "status": "finalized",
            "candidate_count": len(candidates),
            "approved_count": approved_count,
            "blocked_count": blocked_count,
            "finalized_by": actor_id,
            "finalized_at": now.isoformat(),
            "generator_version": GENERATOR_VERSION,
        },
    }
    await audit_service.emit(
        "commercial_catalog_review_finalized",
        "commercial_document_snapshot",
        document.id,
        actor_id,
        None,
        {
            "candidate_count": len(candidates),
            "approved_count": approved_count,
            "blocked_count": blocked_count,
            "pending_count": 0,
            "unchanged_count": unchanged_count,
            "rationale": rationale,
            "generator_version": GENERATOR_VERSION,
        },
        None,
        db,
    )
    await db.flush()
    return await commercial_workspace(db, document_id=document.id)


async def revalidate_candidate(
    candidate_id: str,
    actor_id: str,
    db: AsyncSession,
    *,
    include_workspace: bool = True,
) -> dict[str, object]:
    """Regenerate a derived candidate rule without mutating source evidence."""

    candidate = await db.get(CommercialMappingCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "Commercial candidate not found",
                "error_code": "COMMERCIAL_CANDIDATE_NOT_FOUND",
            },
        )
    term = await db.get(SkuCommercialTerm, candidate.term_id) if candidate.term_id else None
    document = await db.get(CommercialDocumentSnapshot, candidate.document_snapshot_id)
    if term is None or document is None:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "A persisted official commercial term is required for revalidation",
                "error_code": "COMMERCIAL_TERM_REQUIRED",
            },
        )
    existing_mapping = (
        await db.get(ServiceProductSkuMapping, candidate.existing_mapping_id)
        if candidate.existing_mapping_id
        else None
    )
    constraints = list(
        (
            await db.scalars(
                select(SkuCommercialConstraint).where(
                    SkuCommercialConstraint.term_id == term.id
                )
            )
        ).all()
    )
    api_items = list(
        (
            await db.scalars(
                select(PriceItem).where(
                    PriceItem.snapshot_id == term.price_catalog_snapshot_id,
                    PriceItem.part_number == candidate.part_number,
                )
            )
        ).all()
    ) if term.price_catalog_snapshot_id else []
    minimum = Decimal("0")
    minimum_scope: str | None = None
    for item in constraints:
        if item.constraint_type == "metric_minimum" and item.numeric_value is not None:
            minimum = Decimal(item.numeric_value)
            minimum_scope = item.scope
    price_type = term.price_type or (api_items[0].price_type if api_items else "PER_ITEM")
    decimal_overrides = await _approved_billing_semantic_overrides(db)
    decimal_allowed = _commercial_decimal_availability(
        candidate.part_number, term.allow_decimal_quantity, decimal_overrides
    )
    behavior, increment, rounding, proration = _quantity_behavior(
        price_type, decimal_allowed
    )
    formula_key = existing_mapping.formula_key if existing_mapping else "metered_quantity"
    metric_pattern = term.metric_name or "Unspecified"
    semantics = _rule_semantics(
        formula_key=formula_key,
        metric_pattern=metric_pattern,
        price_type=price_type,
        behavior=behavior,
        increment=increment,
        minimum=minimum,
        rounding=rounding,
        proration=proration,
    )
    semantics_hash = _rule_semantics_hash(semantics)
    latest_rule = await db.scalar(
        select(CommercialRuleFamily)
        .where(CommercialRuleFamily.family_key == term.family_key)
        .order_by(CommercialRuleFamily.created_at.desc())
    )
    latest_hash = (
        str(latest_rule.evidence.get("semantics_hash"))
        if latest_rule is not None
        else None
    )
    reuse_latest = bool(
        latest_rule is not None
        and latest_hash == semantics_hash
        and latest_rule.generator_version == GENERATOR_VERSION
        and latest_rule.fixture_status == "passed"
    )
    rule: CommercialRuleFamily
    if reuse_latest and latest_rule is not None:
        rule = latest_rule
    else:
        fixture_passed, fixture_checks = _commercial_fixture_result(
            behavior=behavior,
            increment=increment,
            minimum=minimum,
            price_type=price_type,
            api_items=api_items,
        )
        rule = CommercialRuleFamily(
            family_key=term.family_key or _family_key(price_type, term.metric_name),
            version=_next_rule_version(latest_rule),
            formula_key=formula_key,
            metric_pattern=metric_pattern,
            price_types=[price_type],
            quantity_behavior=behavior,
            quantity_increment=increment,
            minimum_quantity=minimum,
            aggregation_window="calendar_month",
            proration_policy=proration,
            quote_rounding=rounding,
            generator_version=GENERATOR_VERSION,
            status="ready_for_review" if fixture_passed else "blocked",
            fixture_status="passed" if fixture_passed else "failed",
            evidence={
                "document_snapshot_id": document.id,
                "part_number": candidate.part_number,
                "semantics_hash": semantics_hash,
                "structured_artifacts": document.manifest.get("structured_artifacts", {}),
                "supersedes_rule_id": latest_rule.id if latest_rule else None,
                "fixture_checks": fixture_checks,
                "revalidated": True,
            },
        )
        db.add(rule)
        await db.flush()
        db.add(
            CommercialEvidenceReference(
                entity_type="commercial_rule_family",
                entity_id=rule.id,
                source_kind="normalized_commercial_rule",
                document_snapshot_id=document.id,
                source_sheet=term.source_sheet,
                source_row=term.source_row,
                excerpt_hash=semantics_hash,
                evidence_metadata={
                    "semantics": semantics,
                    "structured_artifacts": document.manifest.get(
                        "structured_artifacts", {}
                    ),
                    "revalidated": True,
                },
            )
        )

    old_state = {
        "status": candidate.status,
        "generator_version": candidate.generator_version,
        "commercial_rule_family_id": candidate.proposed_mapping.get(
            "commercial_rule_family_id"
        ),
    }
    previous_rule_id = candidate.proposed_mapping.get("commercial_rule_family_id")
    preserve_approval = bool(
        candidate.status == "approved"
        and previous_rule_id == rule.id
        and candidate.generator_version == GENERATOR_VERSION
        and rule.fixture_status == "passed"
    )
    candidate.proposed_mapping = {
        **candidate.proposed_mapping,
        "price_type": price_type,
        "quantity_behavior": behavior,
        "quantity_increment": str(increment),
        "minimum_quantity": str(minimum),
        "minimum_scope": minimum_scope,
        "quote_rounding": rounding,
        "proration_policy": proration,
        "commercial_rule_family_id": rule.id,
        "field_authority": FIELD_AUTHORITY,
    }
    candidate.generator_version = GENERATOR_VERSION
    if not preserve_approval:
        candidate.status = "pending_review" if rule.fixture_status == "passed" else "blocked"
        candidate.reviewed_by = None
        candidate.reviewed_at = None
    revalidation_reason = f"Deterministically revalidated with {GENERATOR_VERSION}."
    if revalidation_reason not in candidate.reasons:
        candidate.reasons = [*candidate.reasons, revalidation_reason]
    await audit_service.emit(
        "commercial_candidate_revalidated",
        "commercial_mapping_candidate",
        candidate.id,
        actor_id,
        old_state,
        {
            "status": candidate.status,
            "generator_version": candidate.generator_version,
            "commercial_rule_family_id": rule.id,
            "fixture_status": rule.fixture_status,
        },
        None,
        db,
    )
    await db.flush()
    if not include_workspace:
        return {
            "candidate_id": candidate.id,
            "status": candidate.status,
            "generator_version": candidate.generator_version,
            "commercial_rule_family_id": rule.id,
            "fixture_status": rule.fixture_status,
        }
    return await commercial_workspace(db, document_id=candidate.document_snapshot_id)


async def review_exception(
    exception_id: str,
    *,
    decision: str,
    rationale: str,
    target_part_number: str | None,
    actor_id: str,
    db: AsyncSession,
) -> dict[str, object]:
    """Record a human decision without erasing the observed source discrepancy."""

    commercial_exception = await db.get(CommercialException, exception_id)
    if commercial_exception is None:
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "Commercial exception not found",
                "error_code": "COMMERCIAL_EXCEPTION_NOT_FOUND",
            },
        )
    if decision not in {"resolve", "accept_risk", "keep_open"}:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "Unsupported commercial exception decision",
                "error_code": "COMMERCIAL_EXCEPTION_DECISION_INVALID",
            },
        )
    document = await db.get(
        CommercialDocumentSnapshot, commercial_exception.document_snapshot_id
    )
    is_dependency = commercial_exception.exception_code == "DEPENDENCY_UNRESOLVED"
    if is_dependency and decision == "accept_risk":
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "A required OCI commercial dependency cannot be accepted as risk; resolve it to an approved exact SKU",
                "error_code": "COMMERCIAL_DEPENDENCY_REQUIRES_RESOLUTION",
            },
        )
    if decision in {"resolve", "accept_risk"} and (
        document is None or document.status != "approved_evidence"
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Approve the source document as evidence before closing exceptions",
                "error_code": "COMMERCIAL_DOCUMENT_APPROVAL_REQUIRED",
            },
        )
    old_status = commercial_exception.status
    resolved_target: CommercialSku | None = None
    if is_dependency and decision == "resolve":
        normalized_target = (target_part_number or "").strip().upper()
        if not normalized_target:
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "An exact target part number is required to resolve this dependency",
                    "error_code": "COMMERCIAL_DEPENDENCY_TARGET_REQUIRED",
                },
            )
        resolved_target = await db.scalar(
            select(CommercialSku).where(CommercialSku.part_number == normalized_target)
        )
        target_candidate = await db.scalar(
            select(CommercialMappingCandidate).where(
                CommercialMappingCandidate.document_snapshot_id
                == commercial_exception.document_snapshot_id,
                CommercialMappingCandidate.commercial_sku_id
                == (resolved_target.id if resolved_target else ""),
                CommercialMappingCandidate.status == "approved",
            )
        )
        if resolved_target is None or target_candidate is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "detail": "The target SKU must exist in the same official source set and have an approved commercial candidate",
                    "error_code": "COMMERCIAL_DEPENDENCY_TARGET_NOT_APPROVED",
                    "target_part_number": normalized_target,
                },
            )
    commercial_exception.status = {
        "resolve": "resolved",
        "accept_risk": "accepted_risk",
        "keep_open": "open",
    }[decision]
    commercial_exception.decision_rationale = rationale
    commercial_exception.reviewed_by = actor_id
    commercial_exception.reviewed_at = _now()
    relationship_id = commercial_exception.details.get("relationship_id")
    if isinstance(relationship_id, str):
        relationship = await db.get(SkuCommercialRelationship, relationship_id)
        if relationship is not None:
            if resolved_target is not None:
                relationship.target_commercial_sku_id = resolved_target.id
                relationship.target_part_number = resolved_target.part_number
            relationship.resolution_status = {
                "resolve": "resolved",
                "accept_risk": "accepted_risk",
                "keep_open": "unresolved",
            }[decision]
            relationship.status = {
                "resolve": "approved",
                "accept_risk": "accepted_risk",
                "keep_open": "needs_review",
            }[decision]
    await audit_service.emit(
        "commercial_exception_reviewed",
        "commercial_exception",
        commercial_exception.id,
        actor_id,
        {"status": old_status},
        {"status": commercial_exception.status, "rationale": rationale},
        None,
        db,
    )
    await db.flush()
    return await commercial_workspace(db, document_id=commercial_exception.document_snapshot_id)


async def promote_release(document_id: str, actor_id: str, db: AsyncSession) -> dict[str, object]:
    """Promote one atomic global catalog release plus its App quote scope."""

    document = await db.get(CommercialDocumentSnapshot, document_id)
    if document is None or document.status != "approved_evidence":
        raise HTTPException(status_code=409, detail={"detail": "Approved commercial document evidence is required", "error_code": "COMMERCIAL_DOCUMENT_APPROVAL_REQUIRED"})
    price_snapshot_id = document.manifest.get("price_snapshot_id")
    price_snapshot = await db.get(PriceCatalogSnapshot, str(price_snapshot_id)) if price_snapshot_id else None
    if price_snapshot is None or price_snapshot.approval_status != "approved":
        raise HTTPException(status_code=409, detail={"detail": "Approved public price snapshot is required", "error_code": "COMMERCIAL_PRICE_APPROVAL_REQUIRED"})
    change_set_id = document.manifest.get("governance_change_set_id")
    change_set = await db.get(GovernanceChangeSet, str(change_set_id)) if change_set_id else None
    required_artifacts = {"products", "metrics", "presets"}
    structured_artifacts = document.manifest.get("structured_artifacts", {})
    artifact_kinds = set(structured_artifacts) if isinstance(structured_artifacts, dict) else set()
    if (
        change_set is None
        or change_set.price_snapshot_id != price_snapshot.id
        or change_set.validation_status != "passed"
        or change_set.approval_status not in {"approved", "not_required"}
        or change_set.status not in {"promoted", "no_change"}
        or not required_artifacts.issubset(artifact_kinds)
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "One approved OCI change set containing products, metrics, presets, and the public price snapshot is required",
                "error_code": "COMMERCIAL_SOURCE_SET_INCOMPLETE",
                "missing_artifacts": sorted(required_artifacts - artifact_kinds),
            },
        )
    candidates = list(
        (
            await db.scalars(
                select(CommercialMappingCandidate).where(
                    CommercialMappingCandidate.document_snapshot_id == document.id
                )
            )
        ).all()
    )
    if not candidates:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The normalized commercial catalog is empty",
                "error_code": "COMMERCIAL_RELEASE_SCOPE_EMPTY",
            },
        )
    non_terminal_parts = sorted(
        candidate.part_number
        for candidate in candidates
        if candidate.status not in {"approved", "blocked"}
    )
    if non_terminal_parts:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Finalize every global catalog candidate before promotion",
                "error_code": "COMMERCIAL_CATALOG_REVIEW_INCOMPLETE",
                "pending_count": len(non_terminal_parts),
                "pending_part_numbers": non_terminal_parts[:50],
            },
        )

    catalog_parts = sorted({candidate.part_number for candidate in candidates})
    candidate_by_part = {candidate.part_number: candidate for candidate in candidates}
    approved_candidate_parts = {
        part
        for part, candidate in candidate_by_part.items()
        if candidate.status == "approved"
    }
    blocked_candidate_parts = set(catalog_parts) - approved_candidate_parts
    open_exceptions = list(
        (
            await db.scalars(
                select(CommercialException).where(
                    CommercialException.document_snapshot_id == document.id,
                    CommercialException.status == "open",
                )
            )
        ).all()
    )
    open_exception_parts = {
        str(item.part_number) for item in open_exceptions if item.part_number
    }
    unresolved_relationships = list(
        (
            await db.scalars(
                select(SkuCommercialRelationship).where(
                    SkuCommercialRelationship.document_snapshot_id == document.id,
                    SkuCommercialRelationship.resolution_status.in_(
                        ("unresolved", "accepted_risk")
                    ),
                )
            )
        ).all()
    )
    unresolved_relationship_parts = {
        str(item.part_number) for item in unresolved_relationships
    }
    selected_rule_ids_by_part = {
        candidate.part_number: str(candidate.proposed_mapping.get("commercial_rule_family_id"))
        for candidate in candidates
        if candidate.status == "approved"
        and isinstance(candidate.proposed_mapping.get("commercial_rule_family_id"), str)
    }
    selected_term_ids_by_part = {
        candidate.part_number: candidate.term_id
        for candidate in candidates
        if candidate.status == "approved" and candidate.term_id
    }
    selected_rule_ids = set(selected_rule_ids_by_part.values())
    approved_rules = list(
        (
            await db.scalars(
                select(CommercialRuleFamily).where(
                    CommercialRuleFamily.id.in_(selected_rule_ids),
                    CommercialRuleFamily.status == "approved",
                    CommercialRuleFamily.fixture_status == "passed",
                )
            )
        ).all()
    ) if selected_rule_ids else []
    approved_rules_by_id = {rule.id: rule for rule in approved_rules}
    approved_terms = list(
        (
            await db.scalars(
                select(SkuCommercialTerm).where(
                    SkuCommercialTerm.id.in_(set(selected_term_ids_by_part.values())),
                    SkuCommercialTerm.status == "approved",
                )
            )
        ).all()
    ) if selected_term_ids_by_part else []
    approved_terms_by_id = {term.id: term for term in approved_terms}
    exception_codes_by_part: dict[str, set[str]] = {}
    for commercial_exception in open_exceptions:
        if commercial_exception.part_number:
            exception_codes_by_part.setdefault(
                str(commercial_exception.part_number), set()
            ).add(commercial_exception.exception_code)
    relationship_statuses_by_part: dict[str, set[str]] = {}
    for relationship in unresolved_relationships:
        relationship_statuses_by_part.setdefault(relationship.part_number, set()).add(
            relationship.resolution_status
        )
    release_blockers = {
        part_number: _catalog_finalization_blockers(
            candidate=candidate_by_part[part_number],
            rule=approved_rules_by_id.get(selected_rule_ids_by_part.get(part_number, "")),
            term=approved_terms_by_id.get(selected_term_ids_by_part.get(part_number, "")),
            open_exception_codes=exception_codes_by_part.get(part_number, set()),
            unresolved_relationship_statuses=relationship_statuses_by_part.get(
                part_number, set()
            ),
        )
        for part_number in sorted(approved_candidate_parts)
    }
    release_blockers = {
        part_number: blockers
        for part_number, blockers in release_blockers.items()
        if blockers
    }
    quote_ready_parts = sorted(approved_candidate_parts - set(release_blockers))
    invalid_approved_parts = sorted(release_blockers)
    if invalid_approved_parts:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Approved candidates must have complete rules, terms, relationships, and exception state",
                "error_code": "COMMERCIAL_APPROVED_DISPOSITION_INVALID",
                "invalid_part_numbers": invalid_approved_parts[:50],
                "blockers": {
                    part_number: release_blockers[part_number]
                    for part_number in invalid_approved_parts[:50]
                },
            },
        )

    available_mappings = list(
        (
            await db.scalars(
                select(ServiceProductSkuMapping).where(
                    ServiceProductSkuMapping.status == "approved",
                    ServiceProductSkuMapping.part_number.is_not(None),
                )
            )
        ).all()
    )
    available_mapping_parts = sorted(
        {str(mapping.part_number) for mapping in available_mappings if mapping.part_number}
    )
    app_quote_parts = sorted(set(available_mapping_parts) & set(quote_ready_parts))
    excluded_mapping_parts = sorted(set(available_mapping_parts) - set(app_quote_parts))
    mapping_candidate_not_approved = set(available_mapping_parts) - approved_candidate_parts
    mapping_rule_not_approved = set(available_mapping_parts) - set(
        selected_rule_ids_by_part
    )
    mappings = [
        mapping
        for mapping in available_mappings
        if mapping.part_number and str(mapping.part_number) in app_quote_parts
    ]
    selected_mapping_ids_by_part: dict[str, list[str]] = {}
    for mapping in mappings:
        selected_mapping_ids_by_part.setdefault(str(mapping.part_number), []).append(mapping.id)
    selected_mapping_ids_by_part = {
        part_number: sorted(mapping_ids)
        for part_number, mapping_ids in sorted(selected_mapping_ids_by_part.items())
    }
    selected_rule_ids_by_part = {
        part: rule_id
        for part, rule_id in selected_rule_ids_by_part.items()
        if part in quote_ready_parts
    }
    selected_term_ids_by_part = {
        part: term_id
        for part, term_id in selected_term_ids_by_part.items()
        if part in quote_ready_parts
    }
    approved_rules = [
        rule
        for rule in approved_rules
        if rule.id in set(selected_rule_ids_by_part.values())
    ]
    candidate_hash_payload = "|".join(
        f"{candidate.part_number}:{candidate.status}:{candidate.generator_version}:"
        f"{json.dumps(candidate.proposed_mapping, sort_keys=True, default=str)}"
        for candidate in sorted(candidates, key=lambda value: value.part_number)
    )
    app_mapping_payload = "|".join(
        f"{item.id}:{item.version}:{item.updated_at.isoformat()}"
        for item in sorted(mappings, key=lambda value: value.id)
    )
    mapping_hash = hashlib.sha256(
        f"{candidate_hash_payload}::{app_mapping_payload}".encode()
    ).hexdigest()
    rule_hash = hashlib.sha256("|".join(f"{item.id}:{item.version}" for item in sorted(approved_rules, key=lambda value: value.id)).encode()).hexdigest()
    source_hashes = sorted(
        str(value.get("content_hash"))
        for value in structured_artifacts.values()
        if isinstance(value, dict) and value.get("content_hash")
    ) if isinstance(structured_artifacts, dict) else []
    evidence_hash = hashlib.sha256(
        ":".join([document.content_hash, price_snapshot.content_hash, *source_hashes]).encode()
    ).hexdigest()
    prior = list((await db.scalars(select(CommercialRelease).where(CommercialRelease.status == "approved"))).all())
    for item in prior:
        item.status = "superseded"
    release = CommercialRelease(
        version=f"commercial-{_now().strftime('%Y%m%d%H%M%S')}",
        price_catalog_snapshot_id=price_snapshot.id,
        document_snapshot_id=document.id,
        governance_change_set_id=change_set.id,
        mapping_set_hash=mapping_hash,
        rule_family_set_hash=rule_hash,
        evidence_hash=evidence_hash,
        status="approved",
        validation_status="passed",
        open_exception_count=0,
        release_metadata={
            "scope": "global_oci_catalog",
            # `part_numbers` is the exact allowlist consumed by the BOM. The
            # global catalog is represented separately so future App mappings
            # cannot enter an older release implicitly.
            "part_numbers": app_quote_parts,
            "catalog_part_numbers": catalog_parts,
            "approved_part_numbers": sorted(approved_candidate_parts),
            "quote_ready_part_numbers": quote_ready_parts,
            "blocked_part_numbers": sorted(blocked_candidate_parts),
            "catalog_candidate_count": len(catalog_parts),
            "terminal_disposition_count": len(catalog_parts),
            "quote_ready_count": len(quote_ready_parts),
            "blocked_count": len(blocked_candidate_parts),
            "available_mapping_parts": available_mapping_parts,
            "excluded_mapping_parts": excluded_mapping_parts,
            "included_mapping_count": len(app_quote_parts),
            "available_mapping_count": len(available_mapping_parts),
            "excluded_mapping_count": len(excluded_mapping_parts),
            "catalog_open_exception_count": len(open_exception_parts),
            "excluded_open_exception_count": len(
                blocked_candidate_parts & open_exception_parts
            ),
            "excluded_mapping_reasons": {
                part: (
                    ["not_in_global_catalog"]
                    if part not in candidate_by_part
                    else sorted(
                        reason
                        for reason, parts in (
                            ("candidate_not_approved", mapping_candidate_not_approved),
                            ("open_exception", open_exception_parts),
                            ("unresolved_relationship", unresolved_relationship_parts),
                            ("rule_not_approved", mapping_rule_not_approved),
                        )
                        if part in parts
                    )
                )
                for part in excluded_mapping_parts
            },
            "blocked_catalog_reasons": {
                part: (
                    _string_list(
                        candidate_by_part[part].proposed_mapping.get(
                            "catalog_disposition_reasons"
                        )
                    )
                    or _string_list(candidate_by_part[part].reasons)
                )
                for part in sorted(blocked_candidate_parts)
            },
            "blocked_reasons": {
                part: (
                    _string_list(
                        candidate_by_part[part].proposed_mapping.get(
                            "catalog_disposition_reasons"
                        )
                    )
                    or _string_list(candidate_by_part[part].reasons)
                )
                for part in sorted(blocked_candidate_parts)
            },
            "structured_artifacts": structured_artifacts,
            "mapping_ids_by_part": selected_mapping_ids_by_part,
            "term_ids_by_part": selected_term_ids_by_part,
            "rule_ids_by_part": selected_rule_ids_by_part,
        },
        approved_by=actor_id,
        approved_at=_now(),
    )
    db.add(release)
    await db.flush()
    await audit_service.emit(
        "commercial_release_promoted", "commercial_release", release.id, actor_id,
        None, {
            "version": release.version,
            "scope": "global_oci_catalog",
            "catalog_candidate_count": len(catalog_parts),
            "quote_ready_count": len(quote_ready_parts),
            "blocked_count": len(blocked_candidate_parts),
            "app_quote_scope_count": len(app_quote_parts),
            "excluded_mapping_count": len(excluded_mapping_parts),
            "evidence_hash": evidence_hash,
        }, None, db,
    )
    return await commercial_workspace(db, document_id=document.id)


async def commercial_workspace(
    db: AsyncSession, *, document_id: str | None = None, search: str | None = None,
    page: int = 1, page_size: int = 50, status: str = "all",
) -> dict[str, object]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    if document_id is None:
        document = await db.scalar(select(CommercialDocumentSnapshot).order_by(CommercialDocumentSnapshot.created_at.desc()))
    else:
        document = await db.get(CommercialDocumentSnapshot, document_id)
    if document is None:
        return {
            "document": None, "summary": {"skus": 0, "candidates": 0, "pending": 0, "exceptions": 0, "approved": 0, "blocked": 0},
            "candidates": [], "page": page, "page_size": page_size, "total": 0,
            "exceptions": [], "exceptions_page": page, "exceptions_page_size": page_size,
            "exceptions_total": 0, "releases": [], "field_authority": FIELD_AUTHORITY,
        }
    candidate_query = (
        select(CommercialMappingCandidate)
        .join(CommercialSku, CommercialSku.id == CommercialMappingCandidate.commercial_sku_id)
        .outerjoin(SkuCommercialTerm, SkuCommercialTerm.id == CommercialMappingCandidate.term_id)
        .where(CommercialMappingCandidate.document_snapshot_id == document.id)
    )
    if search:
        search_pattern = f"%{search.strip()}%"
        candidate_query = candidate_query.where(
            or_(
                CommercialMappingCandidate.part_number.ilike(search_pattern),
                CommercialSku.display_name.ilike(search_pattern),
                CommercialSku.service_category.ilike(search_pattern),
                cast(CommercialSku.identity_metadata, String).ilike(search_pattern),
                SkuCommercialTerm.metric_name.ilike(search_pattern),
                SkuCommercialTerm.service_name.ilike(search_pattern),
            )
        )
    if status != "all":
        candidate_query = candidate_query.where(CommercialMappingCandidate.status == status)
    total = int(await db.scalar(select(func.count()).select_from(candidate_query.subquery())) or 0)
    candidates = list(
        (
            await db.scalars(
                candidate_query.order_by(CommercialMappingCandidate.part_number)
                .offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
    )
    candidate_sku_ids = {item.commercial_sku_id for item in candidates}
    candidate_term_ids = {item.term_id for item in candidates if item.term_id}
    candidate_skus = (
        list(
            (
                await db.scalars(
                    select(CommercialSku).where(CommercialSku.id.in_(candidate_sku_ids))
                )
            ).all()
        )
        if candidate_sku_ids
        else []
    )
    candidate_terms = (
        list(
            (
                await db.scalars(
                    select(SkuCommercialTerm).where(SkuCommercialTerm.id.in_(candidate_term_ids))
                )
            ).all()
        )
        if candidate_term_ids
        else []
    )
    candidate_skus_by_id = {item.id: item for item in candidate_skus}
    candidate_terms_by_id = {item.id: item for item in candidate_terms}
    candidate_rule_ids = {
        str(rule_id)
        for item in candidates
        if isinstance(
            rule_id := item.proposed_mapping.get("commercial_rule_family_id"), str
        )
    }
    candidate_rules = (
        list(
            (
                await db.scalars(
                    select(CommercialRuleFamily).where(
                        CommercialRuleFamily.id.in_(candidate_rule_ids)
                    )
                )
            ).all()
        )
        if candidate_rule_ids
        else []
    )
    candidate_rules_by_id = {item.id: item for item in candidate_rules}
    exception_query = select(CommercialException).where(
        CommercialException.document_snapshot_id == document.id
    )
    if search:
        exception_query = exception_query.where(
            CommercialException.part_number.ilike(f"%{search.strip()}%")
        )
    exceptions_total = int(await db.scalar(select(func.count()).select_from(exception_query.subquery())) or 0)
    exceptions = list(
        (
            await db.scalars(
                exception_query.order_by(
                    CommercialException.severity, CommercialException.part_number
                ).offset((page - 1) * page_size).limit(page_size)
            )
        ).all()
    )
    releases = list((await db.scalars(select(CommercialRelease).where(CommercialRelease.document_snapshot_id == document.id).order_by(CommercialRelease.created_at.desc()))).all())
    total_candidates = await db.scalar(select(func.count()).select_from(CommercialMappingCandidate).where(CommercialMappingCandidate.document_snapshot_id == document.id)) or 0
    pending_candidates = await db.scalar(select(func.count()).select_from(CommercialMappingCandidate).where(CommercialMappingCandidate.document_snapshot_id == document.id, CommercialMappingCandidate.status == "pending_review")) or 0
    approved_candidates = await db.scalar(select(func.count()).select_from(CommercialMappingCandidate).where(CommercialMappingCandidate.document_snapshot_id == document.id, CommercialMappingCandidate.status == "approved")) or 0
    blocked_candidates = await db.scalar(select(func.count()).select_from(CommercialMappingCandidate).where(CommercialMappingCandidate.document_snapshot_id == document.id, CommercialMappingCandidate.status == "blocked")) or 0
    open_exceptions = await db.scalar(select(func.count()).select_from(CommercialException).where(CommercialException.document_snapshot_id == document.id, CommercialException.status == "open")) or 0
    return {
            "document": {
                "id": document.id,
                "source_name": document.source_name,
                "original_filename": document.original_filename,
                "content_hash": document.content_hash,
                "parser_version": document.parser_version,
                "status": document.status,
                "record_count": document.record_count,
                "retrieved_at": document.retrieved_at,
                "approved_by": document.approved_by,
                "approved_at": document.approved_at,
                "manifest": document.manifest,
            },
            "summary": {
                "skus": total_candidates,
                "candidates": total_candidates,
                "pending": pending_candidates,
                "approved": approved_candidates,
                "blocked": blocked_candidates,
                "exceptions": open_exceptions,
            },
            "page": page,
            "page_size": page_size,
            "total": total,
            "candidates": [
                {
                    "id": item.id,
                    "part_number": item.part_number,
                    "service_id": item.proposed_service_id,
                    "family_key": item.family_key,
                    "classification": item.classification,
                    "confidence": item.confidence,
                    "status": item.status,
                    "generator_version": item.generator_version,
                    "rule_status": (
                        candidate_rules_by_id[str(rule_id)].status
                        if isinstance(
                            rule_id := item.proposed_mapping.get(
                                "commercial_rule_family_id"
                            ),
                            str,
                        )
                        and str(rule_id) in candidate_rules_by_id
                        else None
                    ),
                    "rule_fixture_status": (
                        candidate_rules_by_id[str(rule_id)].fixture_status
                        if isinstance(
                            rule_id := item.proposed_mapping.get(
                                "commercial_rule_family_id"
                            ),
                            str,
                        )
                        and str(rule_id) in candidate_rules_by_id
                        else None
                    ),
                    "identity": {
                        "display_name": candidate_skus_by_id[item.commercial_sku_id].display_name,
                        "service_category": candidate_skus_by_id[item.commercial_sku_id].service_category,
                    },
                    "commercial_term": (
                        {
                            "service_name": candidate_terms_by_id[item.term_id].service_name,
                            "metric_name": candidate_terms_by_id[item.term_id].metric_name,
                            "price_type": candidate_terms_by_id[item.term_id].price_type,
                        }
                        if item.term_id and item.term_id in candidate_terms_by_id
                        else None
                    ),
                }
                for item in candidates
            ],
            "exceptions": [
                {
                    "id": item.id,
                    "candidate_id": item.candidate_id,
                    "part_number": item.part_number,
                    "code": item.exception_code,
                    "severity": item.severity,
                    "status": item.status,
                    "details": item.details,
                }
                for item in exceptions
            ],
            "exceptions_page": page,
            "exceptions_page_size": page_size,
            "exceptions_total": exceptions_total,
            "releases": [
                {
                    "id": item.id,
                    "version": item.version,
                    "status": item.status,
                    "validation_status": item.validation_status,
                    "open_exception_count": item.open_exception_count,
                    "approved_by": item.approved_by,
                    "approved_at": item.approved_at,
                    "metadata": item.release_metadata,
                }
                for item in releases
            ],
            "field_authority": FIELD_AUTHORITY,
        }


async def commercial_candidate_detail(candidate_id: str, db: AsyncSession) -> dict[str, object]:
    """Load the complete immutable evidence for one explicitly opened candidate."""

    candidate = await db.get(CommercialMappingCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail={"detail": "Commercial candidate not found", "error_code": "COMMERCIAL_CANDIDATE_NOT_FOUND"})
    sku = await db.get(CommercialSku, candidate.commercial_sku_id)
    term = await db.get(SkuCommercialTerm, candidate.term_id) if candidate.term_id else None
    if sku is None:
        raise HTTPException(status_code=404, detail={"detail": "Commercial SKU not found", "error_code": "COMMERCIAL_SKU_NOT_FOUND"})
    constraints = list((await db.scalars(select(SkuCommercialConstraint).where(SkuCommercialConstraint.term_id == candidate.term_id))).all()) if candidate.term_id else []
    relationships = list((await db.scalars(select(SkuCommercialRelationship).where(
        SkuCommercialRelationship.document_snapshot_id == candidate.document_snapshot_id,
        SkuCommercialRelationship.source_term_id == candidate.term_id,
    ))).all()) if candidate.term_id else []
    rule_id = candidate.proposed_mapping.get("commercial_rule_family_id")
    rule = await db.get(CommercialRuleFamily, rule_id) if isinstance(rule_id, str) else None
    product_paths = _metadata_paths(sku.identity_metadata)
    return {
        "id": candidate.id, "part_number": candidate.part_number,
        "service_id": candidate.proposed_service_id, "family_key": candidate.family_key,
        "classification": candidate.classification, "confidence": candidate.confidence,
        "status": candidate.status, "generator_version": candidate.generator_version,
        "rule_status": rule.status if rule else None,
        "rule_fixture_status": rule.fixture_status if rule else None,
        "identity": {
            "display_name": sku.display_name, "service_category": sku.service_category,
            "product_hierarchy": _metadata_text_list(sku.identity_metadata, "product_hierarchy"),
            "product_paths": product_paths, "official_location_count": len(product_paths),
            "structured_product": _metadata_object(sku.identity_metadata, "structured_product"),
        },
        "commercial_term": ({
            "service_name": term.service_name, "metric_name": term.metric_name,
            "price_type": term.price_type, "commercial_prices": term.commercial_prices,
            "additional_information": term.additional_information, "notes": term.notes,
            "source_sheet": term.source_sheet, "source_row": term.source_row,
            "constraints": [{
                "type": item.constraint_type, "scope": item.scope,
                "value": str(item.numeric_value) if item.numeric_value is not None else item.text_value,
                "unit": item.unit, "behavior": item.behavior,
            } for item in constraints],
        } if term else None),
        "composition": [{
            "relationship_type": item.relationship_type, "target_part_number": item.target_part_number,
            "target_name": item.target_name, "guidance": item.guidance,
            "resolution_status": item.resolution_status,
        } for item in relationships if _meaningful_document_text(item.target_name) or _meaningful_document_text(item.target_part_number)],
        "proposed_mapping": candidate.proposed_mapping, "reasons": candidate.reasons,
    }


async def commercial_agent_evidence(db: AsyncSession) -> dict[str, object]:
    """Return a bounded, read-only commercial dossier for governed agents."""

    document = await db.scalar(
        select(CommercialDocumentSnapshot).order_by(CommercialDocumentSnapshot.created_at.desc())
    )
    release = await db.scalar(
        select(CommercialRelease)
        .where(CommercialRelease.status == "approved")
        .order_by(CommercialRelease.approved_at.desc())
    )
    if document is None:
        return {
            "readiness": "unavailable",
            "release": None,
            "document": None,
            "open_exceptions": [],
            "commercial_release_scope": {
                "status": "unavailable",
                "included_part_count": 0,
                "available_mapping_part_count": 0,
                "excluded_mapping_part_count": 0,
                "excluded_mapping_parts": [],
                "excluded_mapping_reasons": {},
            },
            "candidate_revalidation": {
                "status": "unavailable",
                "count": 0,
                "items": [],
                "current_generator_version": GENERATOR_VERSION,
            },
            "field_authority": FIELD_AUTHORITY,
        }
    open_exception_count = await db.scalar(
        select(func.count())
        .select_from(CommercialException)
        .where(
            CommercialException.document_snapshot_id == document.id,
            CommercialException.status == "open",
        )
    ) or 0
    open_exceptions = list(
        (
            await db.scalars(
                select(CommercialException)
                .where(
                    CommercialException.document_snapshot_id == document.id,
                    CommercialException.status == "open",
                )
                .order_by(CommercialException.severity, CommercialException.part_number)
                .limit(20)
            )
        ).all()
    )
    candidates = list(
        (
            await db.scalars(
                select(CommercialMappingCandidate).where(
                    CommercialMappingCandidate.document_snapshot_id == document.id
                )
            )
        ).all()
    )
    candidate_rule_ids = {
        str(rule_id)
        for item in candidates
        if isinstance(
            rule_id := item.proposed_mapping.get("commercial_rule_family_id"), str
        )
    }
    rules = (
        list(
            (
                await db.scalars(
                    select(CommercialRuleFamily).where(
                        CommercialRuleFamily.id.in_(candidate_rule_ids)
                    )
                )
            ).all()
        )
        if candidate_rule_ids
        else []
    )
    rules_by_id = {item.id: item for item in rules}
    revalidation_items: list[dict[str, object]] = []
    for candidate in candidates:
        reasons: list[str] = []
        rule_id = candidate.proposed_mapping.get("commercial_rule_family_id")
        rule = rules_by_id.get(str(rule_id)) if isinstance(rule_id, str) else None
        if candidate.generator_version != GENERATOR_VERSION:
            reasons.append("candidate_generator_outdated")
        if rule is None:
            reasons.append("rule_missing")
        else:
            if rule.generator_version != GENERATOR_VERSION:
                reasons.append("rule_generator_outdated")
            if rule.fixture_status != "passed":
                reasons.append("fixture_not_passed")
        if reasons:
            revalidation_items.append(
                {
                    "candidate_id": candidate.id,
                    "part_number": candidate.part_number,
                    "reasons": reasons,
                }
            )
    release_metadata = release.release_metadata if release else {}
    included_parts = _string_list(release_metadata.get("part_numbers"))
    available_parts = _string_list(release_metadata.get("available_mapping_parts"))
    excluded_parts = _string_list(release_metadata.get("excluded_mapping_parts"))
    release_scope = {
        "status": (
            "unavailable"
            if release is None
            else "partial" if excluded_parts else "complete"
        ),
        "included_part_count": len(included_parts),
        "available_mapping_part_count": len(available_parts),
        "excluded_mapping_part_count": len(excluded_parts),
        "excluded_mapping_parts": excluded_parts[:50],
        "excluded_mapping_reasons": (
            release_metadata.get("excluded_mapping_reasons", {})
            if release
            else {}
        ),
    }
    return {
        "readiness": "approved_release" if release else "review_required",
        "document": {
            "id": document.id,
            "content_hash": document.content_hash,
            "status": document.status,
            "record_count": document.record_count,
            "parser_version": document.parser_version,
        },
        "release": (
            {
                "id": release.id,
                "version": release.version,
                "price_catalog_snapshot_id": release.price_catalog_snapshot_id,
                "mapping_set_hash": release.mapping_set_hash,
                "rule_family_set_hash": release.rule_family_set_hash,
                "validation_status": release.validation_status,
                "scope": release_metadata.get("scope"),
            }
            if release
            else None
        ),
        "open_exceptions": [
            {
                "part_number": item.part_number,
                "code": item.exception_code,
                "severity": item.severity,
                "proposed_resolution": item.proposed_resolution,
            }
            for item in open_exceptions
        ],
        "open_exception_count": open_exception_count,
        "commercial_release_scope": release_scope,
        "candidate_revalidation": {
            "status": "required" if revalidation_items else "clear",
            "count": len(revalidation_items),
            "items": revalidation_items[:20],
            "current_generator_version": GENERATOR_VERSION,
        },
        "field_authority": FIELD_AUTHORITY,
        "authority_statement": (
            "Deterministic approved releases are authoritative. Agents may explain or propose "
            "review actions but cannot approve terms, mappings, exceptions, prices, or BOM totals."
        ),
    }
