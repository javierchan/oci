from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import re
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

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
    def _split_resource_type_or_query(q: str) -> Optional[List[str]]:
        prefix = "query all resources where "
        low = q.strip().lower()
        if not low.startswith(prefix):
            return None
        where = q.strip()[len(prefix) :].strip()
        if " and " in where.lower():
            return None
        parts = re.split(r"\s+or\s+", where, flags=re.IGNORECASE)
        if len(parts) < 2:
            return None
        queries: List[str] = []
        for part in parts:
            m = re.fullmatch(r"resourceType\s*=\s*(['\"])([^'\"]+)\1\s*", part.strip(), flags=re.IGNORECASE)
            if not m:
                return None
            queries.append(f"{prefix}{part.strip()}")
        return queries

    def _iter_query(q: str) -> Iterable[Dict[str, Any]]:
        client = get_resource_search_client(ctx, region)
        details = oci.resource_search.models.StructuredSearchDetails(query=q)  # type: ignore[attr-defined]

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

    split_queries = _split_resource_type_or_query(query)
    if not split_queries:
        yield from _iter_query(query)
        return

    q: Queue[Any] = Queue(maxsize=1000)
    errors: Queue[BaseException] = Queue()
    sentinel = object()

    def _worker(qry: str) -> None:
        try:
            for rec in _iter_query(qry):
                q.put(rec)
        except BaseException as e:
            errors.put(e)
        finally:
            q.put(sentinel)

    max_workers = min(8, len(split_queries))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for qry in split_queries:
            executor.submit(_worker, qry)
        completed = 0
        while completed < len(split_queries):
            item = q.get()
            if item is sentinel:
                completed += 1
                continue
            if not errors.empty():
                raise errors.get()
            yield item  # type: ignore[misc]
        if not errors.empty():
            raise errors.get()


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
