from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..auth.providers import AuthContext
from ..normalize.transform import normalize_from_search_summary
from ..util.errors import map_oci_error
from ..util.pagination import paginate
from .clients import get_resource_search_client

try:
    import oci  # type: ignore
except Exception:  # pragma: no cover
    oci = None  # type: ignore


def _to_dict(obj: Any) -> Dict[str, Any]:
    """
    Convert OCI SDK model object to dict safely.
    """
    if obj is None:
        return {}
    def _json_safe(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: _json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_json_safe(v) for v in value]
        if isinstance(value, tuple):
            return [_json_safe(v) for v in value]
        return value

    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            return _json_safe(to_dict())
        except Exception:
            pass
    # Fallback: best-effort shallow conversion
    out: Dict[str, Any] = {}
    for k in dir(obj):
        if k.startswith("_"):
            continue
        try:
            v = getattr(obj, k)
        except Exception:
            continue
        if callable(v):
            continue
        # Avoid including class descriptors / metadata
        if k in ("swagger_types", "attribute_map"):
            continue
        out[k] = _json_safe(v)
    return out


def discover_in_region(ctx: AuthContext, region: str, query: str) -> List[Dict[str, Any]]:
    """
    Perform Structured Search in a single region and return a list of normalized records.
    - Default query should be 'query all resources' unless caller overrides.
    - Injects region into each record explicitly.
    - Paginates until no opc-next-page is returned.
    - Attaches the raw search summary onto the transient field 'searchSummary' for enrichment.
    """
    client = get_resource_search_client(ctx, region)
    details = oci.resource_search.models.StructuredSearchDetails(query=query)  # type: ignore[attr-defined]

    def fetch(page: Optional[str]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        try:
            resp = client.search_resources(search_details=details, page=page, limit=1000)  # type: ignore[attr-defined]
        except Exception as e:
            mapped = map_oci_error(e, f"OCI SDK error while searching resources in {region}")
            if mapped:
                raise mapped from e
            raise
        items = getattr(resp, "data", None)
        summaries = []
        if items and getattr(items, "items", None) is not None:
            items = items.items  # type: ignore[assignment]
        for it in items or []:
            summaries.append(_to_dict(it))
        next_page = getattr(resp, "headers", {}).get("opc-next-page")  # type: ignore[assignment]
        return summaries, next_page

    records: List[Dict[str, Any]] = []
    for summary in paginate(fetch):
        rec = normalize_from_search_summary(summary, region=region)
        # Attach raw summary for enricher use; will be removed before export
        rec["searchSummary"] = summary  # type: ignore[index]
        records.append(rec)  # type: ignore[arg-type]
    return records
