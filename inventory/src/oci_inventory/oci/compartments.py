from __future__ import annotations

from typing import Dict, List, Optional

from ..auth.providers import AuthContext
from ..util.errors import map_oci_error
from .clients import get_identity_client


def list_compartments(ctx: AuthContext, tenancy_ocid: Optional[str] = None) -> List[Dict[str, str]]:
    """
    List compartments in the tenancy (including root), returning a deterministic, minimal schema:
      [{"ocid": "...", "name": "..."}]

    - Requires tenancy OCID (from auth context or explicit arg).
    - Includes compartments in subtree with access_level ANY.
    - Handles pagination.
    - Sorted by name then ocid for deterministic output.
    """
    identity = get_identity_client(ctx)
    ten = tenancy_ocid
    if not ten:
        from ..auth.providers import get_tenancy_ocid

        ten = get_tenancy_ocid(ctx)
    if not ten:
        raise ValueError("Tenancy OCID is required to list compartments")

    # list compartments (not including root) + add root explicitly
    results: List[Dict[str, str]] = []

    # Root tenancy
    try:
        ten_detail = identity.get_tenancy(ten).data  # type: ignore[attr-defined]
    except Exception as e:
        mapped = map_oci_error(e, "OCI SDK error while fetching tenancy details")
        if mapped:
            raise mapped from e
        raise
    results.append({"ocid": ten_detail.id, "name": ten_detail.name})

    page: Optional[str] = None
    while True:
        try:
            resp = identity.list_compartments(
                ten,
                compartment_id_in_subtree=True,
                access_level="ANY",
                page=page,
                limit=1000,
            )  # type: ignore[attr-defined]
        except Exception as e:
            mapped = map_oci_error(e, "OCI SDK error while listing compartments")
            if mapped:
                raise mapped from e
            raise
        for item in getattr(resp, "data", []):
            results.append({"ocid": item.id, "name": item.name})
        # pagination via header
        page = getattr(resp, "headers", {}).get("opc-next-page")  # type: ignore[assignment]
        if not page:
            break

    # Deduplicate and sort deterministically
    unique = {(r["ocid"], r["name"]): r for r in results}
    out = list(unique.values())
    out.sort(key=lambda r: (r["name"] or "", r["ocid"] or ""))
    return out
