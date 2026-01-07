from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from ..normalize.transform import normalize_relationships


EXCLUDED_FROM_HASH = {"collectedAt"}


def _clean_for_hash(obj: Any) -> Any:
    """
    Return an object suitable for deterministic hashing:
    - remove excluded keys from dicts
    - sort dict keys
    - keep lists order as-is (assumed deterministic upstream)
    """
    if isinstance(obj, dict):
        return {k: _clean_for_hash(v) for k, v in sorted(obj.items()) if k not in EXCLUDED_FROM_HASH}
    if isinstance(obj, list):
        return [_clean_for_hash(x) for x in obj]
    return obj


def stable_record_hash(record: Dict[str, Any]) -> str:
    """
    Compute a stable SHA256 hash of a normalized record, excluding transient fields
    such as collectedAt as required. Keys are sorted to ensure stability.
    """
    normalized = normalize_relationships(record)
    cleaned = _clean_for_hash(normalized)
    payload = json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
