from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..auth.providers import AuthContext, AuthError, get_tenancy_ocid, make_client
from ..util.errors import map_oci_error


try:
    import oci  # type: ignore
except Exception as e:  # pragma: no cover - surfaced in CLI validate
    oci = None  # type: ignore


def get_identity_client(ctx: AuthContext, region: Optional[str] = None) -> Any:
    """
    Create IdentityClient with retry strategy, honoring region when provided.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.identity.IdentityClient, ctx, region=region)  # type: ignore[attr-defined]


def get_resource_search_client(ctx: AuthContext, region: str) -> Any:
    """
    Create ResourceSearchClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.resource_search.ResourceSearchClient, ctx, region=region)  # type: ignore[attr-defined]


def list_region_subscriptions(ctx: AuthContext) -> List[str]:
    """
    Return a list of subscribed region identifiers (e.g., 'us-ashburn-1').

    Uses IdentityClient.list_region_subscriptions requiring tenancy OCID.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")

    tenancy = get_tenancy_ocid(ctx)
    if not tenancy:
        raise AuthError(
            "Tenancy OCID is required to list region subscriptions. Provide via --tenancy or config profile."
        )

    # Identity client can be created without explicit region; the SDK will route accordingly,
    # but to be safe, let region be None here (make_client will select from ctx or env).
    identity = get_identity_client(ctx)
    try:
        subs = identity.list_region_subscriptions(tenancy)  # type: ignore[attr-defined]
    except Exception as e:
        mapped = map_oci_error(e, "OCI SDK error while listing region subscriptions")
        if mapped:
            raise mapped from e
        raise
    # Each item has region_name / region_key; we use region_name (identifier)
    regions = [rs.region_name for rs in getattr(subs, "data", [])]
    # Deterministic order
    regions = sorted(set(regions))
    return regions
