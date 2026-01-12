from __future__ import annotations

from typing import Any, List, Optional

from ..auth.providers import AuthContext, AuthError, get_tenancy_ocid, make_client
from ..util.errors import map_oci_error

try:
    import oci  # type: ignore
    import oci.bastion  # type: ignore
    import oci.cloud_guard  # type: ignore
    import oci.core  # type: ignore
    import oci.dns  # type: ignore
    import oci.identity  # type: ignore
    import oci.key_management  # type: ignore
    import oci.log_analytics  # type: ignore
    import oci.logging  # type: ignore
    import oci.load_balancer  # type: ignore
    import oci.media_services  # type: ignore
    import oci.network_firewall  # type: ignore
    import oci.object_storage  # type: ignore
    import oci.resource_search  # type: ignore
    import oci.secrets  # type: ignore
    import oci.waf  # type: ignore
except Exception:  # pragma: no cover - surfaced in CLI validate
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


def get_compute_client(ctx: AuthContext, region: str) -> Any:
    """
    Create ComputeClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.core.ComputeClient, ctx, region=region)  # type: ignore[attr-defined]


def get_compute_management_client(ctx: AuthContext, region: str) -> Any:
    """
    Create ComputeManagementClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.core.ComputeManagementClient, ctx, region=region)  # type: ignore[attr-defined]


def get_blockstorage_client(ctx: AuthContext, region: str) -> Any:
    """
    Create BlockstorageClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.core.BlockstorageClient, ctx, region=region)  # type: ignore[attr-defined]


def get_virtual_network_client(ctx: AuthContext, region: str) -> Any:
    """
    Create VirtualNetworkClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.core.VirtualNetworkClient, ctx, region=region)  # type: ignore[attr-defined]


def get_load_balancer_client(ctx: AuthContext, region: str) -> Any:
    """
    Create LoadBalancerClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.load_balancer.LoadBalancerClient, ctx, region=region)  # type: ignore[attr-defined]


def get_bastion_client(ctx: AuthContext, region: str) -> Any:
    """
    Create BastionClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.bastion.BastionClient, ctx, region=region)  # type: ignore[attr-defined]


def get_vault_client(ctx: AuthContext, region: str) -> Any:
    """
    Create KmsVaultClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.key_management.KmsVaultClient, ctx, region=region)  # type: ignore[attr-defined]


def get_secrets_client(ctx: AuthContext, region: str) -> Any:
    """
    Create SecretsClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.secrets.SecretsClient, ctx, region=region)  # type: ignore[attr-defined]


def get_cloud_guard_client(ctx: AuthContext, region: str) -> Any:
    """
    Create CloudGuardClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.cloud_guard.CloudGuardClient, ctx, region=region)  # type: ignore[attr-defined]


def get_dns_client(ctx: AuthContext, region: str) -> Any:
    """
    Create DnsClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.dns.DnsClient, ctx, region=region)  # type: ignore[attr-defined]


def get_object_storage_client(ctx: AuthContext, region: str) -> Any:
    """Create ObjectStorageClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.object_storage.ObjectStorageClient, ctx, region=region)  # type: ignore[attr-defined]


def get_logging_management_client(ctx: AuthContext, region: str) -> Any:
    """Create LoggingManagementClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.logging.LoggingManagementClient, ctx, region=region)  # type: ignore[attr-defined]


def get_log_analytics_client(ctx: AuthContext, region: str) -> Any:
    """Create LogAnalyticsClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.log_analytics.LogAnalyticsClient, ctx, region=region)  # type: ignore[attr-defined]


def get_media_services_client(ctx: AuthContext, region: str) -> Any:
    """Create MediaServicesClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.media_services.MediaServicesClient, ctx, region=region)  # type: ignore[attr-defined]


def get_network_firewall_client(ctx: AuthContext, region: str) -> Any:
    """Create NetworkFirewallClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.network_firewall.NetworkFirewallClient, ctx, region=region)  # type: ignore[attr-defined]


def get_waf_client(ctx: AuthContext, region: str) -> Any:
    """Create WafClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return make_client(oci.waf.WafClient, ctx, region=region)  # type: ignore[attr-defined]


def get_usage_api_client(ctx: AuthContext, region: Optional[str] = None) -> Any:
    """Create UsageapiClient (cost/usage read-only)."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    try:  # pragma: no cover - optional module varies by SDK version
        import importlib

        importlib.import_module("oci.usage_api")
    except Exception as e:  # pragma: no cover
        raise AuthError(f"oci.usage_api not available in installed SDK: {e}") from e
    return make_client(oci.usage_api.UsageapiClient, ctx, region=region)  # type: ignore[attr-defined]


def get_budget_client(ctx: AuthContext, region: Optional[str] = None) -> Any:
    """Create BudgetClient (read-only)."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    try:  # pragma: no cover - optional module varies by SDK version
        import importlib

        importlib.import_module("oci.budget")
    except Exception as e:  # pragma: no cover
        raise AuthError(f"oci.budget not available in installed SDK: {e}") from e
    return make_client(oci.budget.BudgetClient, ctx, region=region)  # type: ignore[attr-defined]


def get_osub_usage_client(ctx: AuthContext, region: Optional[str] = None) -> Any:
    """Create ComputedUsageClient for OneSubscription usage (read-only)."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    try:  # pragma: no cover - optional module varies by SDK version
        import importlib

        importlib.import_module("oci.osub_usage")
    except Exception as e:  # pragma: no cover
        raise AuthError(f"oci.osub_usage not available in installed SDK: {e}") from e
    return make_client(oci.osub_usage.ComputedUsageClient, ctx, region=region)  # type: ignore[attr-defined]


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
