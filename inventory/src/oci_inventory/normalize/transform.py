from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Tuple

from .schema import CANONICAL_FIELD_ORDER, CSV_REPORT_FIELDS, NormalizedRecord
from ..util.time import utc_now_iso


def _get(d: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in d:
            return d[k]
    return None


def normalize_from_search_summary(
    summary: Dict[str, Any],
    region: str,
    collected_at: str | None = None,
) -> NormalizedRecord:
    """
    Build a NormalizedRecord from an OCI Resource Search summary dict.
    The function is defensive to handle both snake_case and camelCase keys.
    """
    ocid = _get(summary, "identifier", "ocid", "id")
    rtype = _get(summary, "resource_type", "resourceType")
    display_name = _get(summary, "display_name", "displayName")
    compartment_id = _get(summary, "compartment_id", "compartmentId")
    lifecycle_state = _get(summary, "lifecycle_state", "lifecycleState")
    time_created = _get(summary, "time_created", "timeCreated")
    defined_tags = _get(summary, "defined_tags", "definedTags")
    freeform_tags = _get(summary, "freeform_tags", "freeformTags")

    record: NormalizedRecord = {
        "ocid": ocid,
        "resourceType": rtype,
        "displayName": display_name,
        "compartmentId": compartment_id,
        "region": region,
        "lifecycleState": lifecycle_state,
        "timeCreated": time_created,
        "definedTags": defined_tags,
        "freeformTags": freeform_tags,
        "collectedAt": collected_at or utc_now_iso(seconds=True),
        # enrichment fields will be added by enricher workflow
        "enrichStatus": "PENDING",
        "enrichError": None,
        "details": {},
        "relationships": [],
    }
    return record


def canonicalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a shallow copy of record with fields ordered according to CANONICAL_FIELD_ORDER.
    Fields not in the canonical list are appended in sorted order.
    """
    out: Dict[str, Any] = {}
    for k in CANONICAL_FIELD_ORDER:
        if k in record:
            out[k] = record[k]
    # Append remaining keys sorted
    remaining = sorted(k for k in record.keys() if k not in out)
    for k in remaining:
        out[k] = record[k]
    return out


def stable_json_dumps(obj: Any) -> str:
    """
    Dump JSON with sort_keys=True and separators to ensure stable output.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def report_rows(records: Iterable[NormalizedRecord]) -> List[List[str]]:
    """
    Build CSV rows (including header) for the report fields.
    """
    header = CSV_REPORT_FIELDS[:]
    rows: List[List[str]] = [header]
    for rec in records:
        row: List[str] = []
        for f in header:
            val = rec.get(f)  # type: ignore[assignment]
            if val is None:
                row.append("")
            else:
                row.append(str(val))
        rows.append(row)
    return rows