from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..auth.providers import AuthContext
from ..normalize.transform import normalize_from_search_summary
from ..util.errors import map_oci_error
from ..util.pagination import paginate
from ..util.serialization import sanitize_for_json
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
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            return sanitize_for_json(to_dict())
        except Exception:
            pass
    # Fast path for OCI SDK models with attribute maps.
    attr_map = getattr(obj, "attribute_map", None)
    swagger_types = getattr(obj, "swagger_types", None)
    if isinstance(attr_map, dict) and isinstance(swagger_types, dict):
        out: Dict[str, Any] = {}
        for attr in attr_map.keys():
            try:
                out[attr] = sanitize_for_json(getattr(obj, attr))
            except Exception:
                continue
        return out
    # Fallback: prefer instance dict to avoid expensive dir() scanning.
    data = getattr(obj, "__dict__", None)
    if isinstance(data, dict):
        out: Dict[str, Any] = {}
        for k, v in data.items():
            if k.startswith("_"):
                continue
            if k in ("swagger_types", "attribute_map"):
                continue
            out[k] = sanitize_for_json(v)
        return out
    return {}


def iter_discover_in_region(
    ctx: AuthContext,
    region: str,
    query: str,
    *,
    collected_at: Optional[str] = None,
) -> Iterable[Dict[str, Any]]:
    """
    Perform Structured Search in a single region and yield normalized records.
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

    for summary in paginate(fetch):
        rec = normalize_from_search_summary(summary, region=region, collected_at=collected_at)
        # Attach raw summary for enricher use; will be removed before export
        rec["searchSummary"] = summary  # type: ignore[index]
        yield rec  # type: ignore[misc]


def discover_in_region(
    ctx: AuthContext,
    region: str,
    query: str,
    *,
    collected_at: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Perform Structured Search in a single region and return a list of normalized records.
    """
    return list(iter_discover_in_region(ctx, region, query, collected_at=collected_at))
