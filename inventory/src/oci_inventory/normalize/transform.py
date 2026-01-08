from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from ..util.time import utc_now_iso
from .schema import CANONICAL_FIELD_ORDER, CSV_REPORT_FIELDS, NormalizedRecord

WORKLOAD_TAG_KEYS: Tuple[str, ...] = (
    "app",
    "application",
    "service",
    "workload",
    "project",
    "stack",
)

WORKLOAD_NAME_KEYWORDS: Tuple[str, ...] = (
    "media",
    "stream",
    "cdn",
    "edge",
    "demo",
    "sandbox",
)

WORKLOAD_PREFIX_EXCLUDE: Tuple[str, ...] = (
    "prod",
    "production",
    "dev",
    "test",
    "stage",
    "staging",
)


def _get(d: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in d:
            return d[k]
    return None


def _record_name_for_workload(record: Mapping[str, Any]) -> str:
    name = str(record.get("displayName") or record.get("name") or "").strip()
    if name:
        return name
    details = record.get("details")
    if not isinstance(details, Mapping):
        return ""
    metadata = details.get("metadata")
    if not isinstance(metadata, Mapping):
        return ""
    for key in ("display_name", "displayName", "name"):
        val = metadata.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _workload_tag_values(record: Mapping[str, Any]) -> Dict[str, str]:
    values: Dict[str, str] = {}

    def _collect(tag_map: Mapping[str, Any]) -> None:
        for k, v in tag_map.items():
            ks = str(k or "").strip().lower()
            vs = str(v or "").strip()
            if not ks or not vs:
                continue
            if ks in WORKLOAD_TAG_KEYS:
                values.setdefault(ks, vs)

    freeform = record.get("freeformTags")
    defined = record.get("definedTags")

    if not isinstance(freeform, Mapping) or not isinstance(defined, Mapping):
        tags = record.get("tags")
        if isinstance(tags, Mapping):
            if not isinstance(freeform, Mapping):
                freeform = tags.get("freeformTags")
            if not isinstance(defined, Mapping):
                defined = tags.get("definedTags")

    if isinstance(freeform, Mapping):
        _collect(freeform)

    if isinstance(defined, Mapping):
        for ns_val in defined.values():
            if isinstance(ns_val, Mapping):
                _collect(ns_val)

    return values


def _prefix_token(name: str) -> str:
    s = (name or "").strip()
    if not s:
        return ""
    for sep in ("-", "_", "."):
        if sep in s:
            token = s.split(sep, 1)[0].strip()
            if len(token) >= 3:
                return token
    return ""


def _workload_key_candidates(record: Mapping[str, Any]) -> List[str]:
    name = _record_name_for_workload(record)
    tags = _workload_tag_values(record)

    candidates: List[str] = []

    for k in WORKLOAD_TAG_KEYS:
        v = tags.get(k)
        if v:
            candidates.append(v)

    nlow = (name or "").lower()
    for kw in WORKLOAD_NAME_KEYWORDS:
        if kw in nlow:
            candidates.append(kw)

    pt = _prefix_token(name)
    if pt:
        candidates.append(pt)

    out: List[str] = []
    seen: set[str] = set()
    for c in candidates:
        c2 = (c or "").strip()
        if not c2:
            continue
        key = c2.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c2)
    return out


def group_workloads(
    records: Sequence[Mapping[str, Any]],
    *,
    min_size: int = 3,
) -> Dict[str, List[Mapping[str, Any]]]:
    prefix_counts: Dict[str, int] = {}
    for r in records:
        t = _prefix_token(_record_name_for_workload(r))
        if t:
            prefix_counts[t.lower()] = prefix_counts.get(t.lower(), 0) + 1

    def _is_eligible_prefix(token: str) -> bool:
        return prefix_counts.get(token.lower(), 0) >= 3

    groups: Dict[str, List[Mapping[str, Any]]] = {}
    for r in records:
        cands = _workload_key_candidates(r)
        chosen = ""
        for c in cands:
            cl = c.lower()
            if cl in WORKLOAD_NAME_KEYWORDS:
                chosen = c
                break
            if _is_eligible_prefix(c):
                chosen = c
                break
            if " " in c or len(c) >= 4:
                if cl not in WORKLOAD_PREFIX_EXCLUDE:
                    chosen = c
                    break
        if not chosen:
            continue
        groups.setdefault(chosen, []).append(r)

    out = {k: v for k, v in groups.items() if len(v) >= min_size}
    return dict(sorted(out.items(), key=lambda kv: (-len(kv[1]), kv[0].lower())))


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


def sort_relationships(relationships: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort relationships deterministically by (source_ocid, relation_type, target_ocid).
    """
    def _key(rel: Dict[str, Any]) -> Tuple[str, str, str]:
        return (
            str(rel.get("source_ocid") or ""),
            str(rel.get("relation_type") or ""),
            str(rel.get("target_ocid") or ""),
        )

    return sorted((dict(r) for r in relationships), key=_key)


def normalize_relationships(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a shallow copy with relationships sorted deterministically, if present.
    """
    out = dict(record)
    rels = out.get("relationships")
    if isinstance(rels, list):
        out["relationships"] = sort_relationships(rels)
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
