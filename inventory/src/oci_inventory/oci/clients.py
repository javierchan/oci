from __future__ import annotations

import importlib
import os
import threading
from typing import Any, List, Optional, Tuple

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

_CLIENT_CACHE_LOCK = threading.Lock()
_CLIENT_CACHE: dict[Tuple[str, Optional[str], Tuple[Any, ...]], Any] = {}


def _client_cache_enabled() -> bool:
    return (os.getenv("OCI_INV_DISABLE_CLIENT_CACHE") or "").strip().lower() not in {"1", "true", "yes"}


def _auth_cache_key(ctx: AuthContext) -> Tuple[Any, ...]:
    if ctx.config_dict is not None:
        cfg = ctx.config_dict
        return (
            "config",
            ctx.profile or "",
            ctx.tenancy_ocid or "",
            cfg.get("user"),
            cfg.get("fingerprint"),
            cfg.get("region"),
        )
    if ctx.signer is not None:
        return ("signer", ctx.method, ctx.tenancy_ocid or "", id(ctx.signer))
    return ("unknown", ctx.method, ctx.tenancy_ocid or "")


def _cached_client(client_cls: Any, ctx: AuthContext, region: Optional[str]) -> Any:
    if not _client_cache_enabled():
        return make_client(client_cls, ctx, region=region)
    key = (f"{getattr(client_cls, '__module__', '')}.{getattr(client_cls, '__name__', '')}", region, _auth_cache_key(ctx))
    with _CLIENT_CACHE_LOCK:
        cached = _CLIENT_CACHE.get(key)
    if cached is not None:
        return cached
    client = make_client(client_cls, ctx, region=region)
    with _CLIENT_CACHE_LOCK:
        _CLIENT_CACHE.setdefault(key, client)
    return client


def _load_client_class(module_name: str, class_name: str) -> Any:
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    try:  # pragma: no cover - optional module varies by SDK version
        module = importlib.import_module(module_name)
    except Exception as e:  # pragma: no cover
        raise AuthError(f"{module_name} not available in installed SDK: {e}") from e
    client_cls = getattr(module, class_name, None)
    if client_cls is None:  # pragma: no cover
        raise AuthError(f"{class_name} not available in {module_name}")
    return client_cls


def clear_client_cache() -> None:
    with _CLIENT_CACHE_LOCK:
        _CLIENT_CACHE.clear()


def get_identity_client(ctx: AuthContext, region: Optional[str] = None) -> Any:
    """
    Create IdentityClient with retry strategy, honoring region when provided.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.identity.IdentityClient, ctx, region=region)  # type: ignore[attr-defined]


def get_resource_search_client(ctx: AuthContext, region: str) -> Any:
    """
    Create ResourceSearchClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.resource_search.ResourceSearchClient, ctx, region=region)  # type: ignore[attr-defined]


def get_compute_client(ctx: AuthContext, region: str) -> Any:
    """
    Create ComputeClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.core.ComputeClient, ctx, region=region)  # type: ignore[attr-defined]


def get_compute_management_client(ctx: AuthContext, region: str) -> Any:
    """
    Create ComputeManagementClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.core.ComputeManagementClient, ctx, region=region)  # type: ignore[attr-defined]


def get_blockstorage_client(ctx: AuthContext, region: str) -> Any:
    """
    Create BlockstorageClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.core.BlockstorageClient, ctx, region=region)  # type: ignore[attr-defined]


def get_virtual_network_client(ctx: AuthContext, region: str) -> Any:
    """
    Create VirtualNetworkClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.core.VirtualNetworkClient, ctx, region=region)  # type: ignore[attr-defined]


def get_load_balancer_client(ctx: AuthContext, region: str) -> Any:
    """
    Create LoadBalancerClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.load_balancer.LoadBalancerClient, ctx, region=region)  # type: ignore[attr-defined]


def get_bastion_client(ctx: AuthContext, region: str) -> Any:
    """
    Create BastionClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.bastion.BastionClient, ctx, region=region)  # type: ignore[attr-defined]


def get_vault_client(ctx: AuthContext, region: str) -> Any:
    """
    Create KmsVaultClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.key_management.KmsVaultClient, ctx, region=region)  # type: ignore[attr-defined]


def get_secrets_client(ctx: AuthContext, region: str) -> Any:
    """
    Create SecretsClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.secrets.SecretsClient, ctx, region=region)  # type: ignore[attr-defined]


def get_cloud_guard_client(ctx: AuthContext, region: str) -> Any:
    """
    Create CloudGuardClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.cloud_guard.CloudGuardClient, ctx, region=region)  # type: ignore[attr-defined]


def get_dns_client(ctx: AuthContext, region: str) -> Any:
    """
    Create DnsClient in the specified region.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.dns.DnsClient, ctx, region=region)  # type: ignore[attr-defined]


def get_object_storage_client(ctx: AuthContext, region: str) -> Any:
    """Create ObjectStorageClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.object_storage.ObjectStorageClient, ctx, region=region)  # type: ignore[attr-defined]


def get_logging_management_client(ctx: AuthContext, region: str) -> Any:
    """Create LoggingManagementClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.logging.LoggingManagementClient, ctx, region=region)  # type: ignore[attr-defined]


def get_log_analytics_client(ctx: AuthContext, region: str) -> Any:
    """Create LogAnalyticsClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.log_analytics.LogAnalyticsClient, ctx, region=region)  # type: ignore[attr-defined]


def get_media_services_client(ctx: AuthContext, region: str) -> Any:
    """Create MediaServicesClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.media_services.MediaServicesClient, ctx, region=region)  # type: ignore[attr-defined]


def get_network_firewall_client(ctx: AuthContext, region: str) -> Any:
    """Create NetworkFirewallClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.network_firewall.NetworkFirewallClient, ctx, region=region)  # type: ignore[attr-defined]


def get_waf_client(ctx: AuthContext, region: str) -> Any:
    """Create WafClient in the specified region."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    return _cached_client(oci.waf.WafClient, ctx, region=region)  # type: ignore[attr-defined]


def get_access_governance_client(ctx: AuthContext, region: str) -> Any:
    """Create AccessGovernanceCPClient in the specified region."""
    return _cached_client(_load_client_class("oci.access_governance_cp", "AccessGovernanceCPClient"), ctx, region=region)


def get_ai_data_platform_client(ctx: AuthContext, region: str) -> Any:
    """Create AiDataPlatformClient in the specified region."""
    return _cached_client(_load_client_class("oci.ai_data_platform", "AiDataPlatformClient"), ctx, region=region)


def get_ai_language_client(ctx: AuthContext, region: str) -> Any:
    """Create AIServiceLanguageClient in the specified region."""
    return _cached_client(_load_client_class("oci.ai_language", "AIServiceLanguageClient"), ctx, region=region)


def get_ai_vision_client(ctx: AuthContext, region: str) -> Any:
    """Create AIServiceVisionClient in the specified region."""
    return _cached_client(_load_client_class("oci.ai_vision", "AIServiceVisionClient"), ctx, region=region)


def get_analytics_client(ctx: AuthContext, region: str) -> Any:
    """Create AnalyticsClient in the specified region."""
    return _cached_client(_load_client_class("oci.analytics", "AnalyticsClient"), ctx, region=region)


def get_api_gateway_client(ctx: AuthContext, region: str) -> Any:
    """Create ApiGatewayClient in the specified region."""
    return _cached_client(_load_client_class("oci.apigateway", "ApiGatewayClient"), ctx, region=region)


def get_api_gateway_gateway_client(ctx: AuthContext, region: str) -> Any:
    """Create GatewayClient in the specified region."""
    return _cached_client(_load_client_class("oci.apigateway", "GatewayClient"), ctx, region=region)


def get_api_gateway_deployment_client(ctx: AuthContext, region: str) -> Any:
    """Create DeploymentClient in the specified region."""
    return _cached_client(_load_client_class("oci.apigateway", "DeploymentClient"), ctx, region=region)


def get_artifacts_client(ctx: AuthContext, region: str) -> Any:
    """Create ArtifactsClient in the specified region."""
    return _cached_client(_load_client_class("oci.artifacts", "ArtifactsClient"), ctx, region=region)


def get_certificates_management_client(ctx: AuthContext, region: str) -> Any:
    """Create CertificatesManagementClient in the specified region."""
    return _cached_client(
        _load_client_class("oci.certificates_management", "CertificatesManagementClient"),
        ctx,
        region=region,
    )


def get_container_engine_client(ctx: AuthContext, region: str) -> Any:
    """Create ContainerEngineClient in the specified region."""
    return _cached_client(_load_client_class("oci.container_engine", "ContainerEngineClient"), ctx, region=region)


def get_container_instance_client(ctx: AuthContext, region: str) -> Any:
    """Create ContainerInstanceClient in the specified region."""
    return _cached_client(_load_client_class("oci.container_instances", "ContainerInstanceClient"), ctx, region=region)


def get_data_flow_client(ctx: AuthContext, region: str) -> Any:
    """Create DataFlowClient in the specified region."""
    return _cached_client(_load_client_class("oci.data_flow", "DataFlowClient"), ctx, region=region)


def get_data_integration_client(ctx: AuthContext, region: str) -> Any:
    """Create DataIntegrationClient in the specified region."""
    return _cached_client(_load_client_class("oci.data_integration", "DataIntegrationClient"), ctx, region=region)


def get_data_labeling_management_client(ctx: AuthContext, region: str) -> Any:
    """Create DataLabelingManagementClient in the specified region."""
    return _cached_client(
        _load_client_class("oci.data_labeling_service", "DataLabelingManagementClient"),
        ctx,
        region=region,
    )


def get_data_safe_client(ctx: AuthContext, region: str) -> Any:
    """Create DataSafeClient in the specified region."""
    return _cached_client(_load_client_class("oci.data_safe", "DataSafeClient"), ctx, region=region)


def get_data_science_client(ctx: AuthContext, region: str) -> Any:
    """Create DataScienceClient in the specified region."""
    return _cached_client(_load_client_class("oci.data_science", "DataScienceClient"), ctx, region=region)


def get_database_client(ctx: AuthContext, region: str) -> Any:
    """Create DatabaseClient in the specified region."""
    return _cached_client(_load_client_class("oci.database", "DatabaseClient"), ctx, region=region)


def get_database_tools_client(ctx: AuthContext, region: str) -> Any:
    """Create DatabaseToolsClient in the specified region."""
    return _cached_client(_load_client_class("oci.database_tools", "DatabaseToolsClient"), ctx, region=region)


def get_dashboard_client(ctx: AuthContext, region: str) -> Any:
    """Create DashboardClient in the specified region."""
    return _cached_client(_load_client_class("oci.dashboard_service", "DashboardClient"), ctx, region=region)


def get_dashboard_group_client(ctx: AuthContext, region: str) -> Any:
    """Create DashboardGroupClient in the specified region."""
    return _cached_client(_load_client_class("oci.dashboard_service", "DashboardGroupClient"), ctx, region=region)


def get_devops_client(ctx: AuthContext, region: str) -> Any:
    """Create DevopsClient in the specified region."""
    return _cached_client(_load_client_class("oci.devops", "DevopsClient"), ctx, region=region)


def get_email_client(ctx: AuthContext, region: str) -> Any:
    """Create EmailClient in the specified region."""
    return _cached_client(_load_client_class("oci.email", "EmailClient"), ctx, region=region)


def get_events_client(ctx: AuthContext, region: str) -> Any:
    """Create EventsClient in the specified region."""
    return _cached_client(_load_client_class("oci.events", "EventsClient"), ctx, region=region)


def get_file_storage_client(ctx: AuthContext, region: str) -> Any:
    """Create FileStorageClient in the specified region."""
    return _cached_client(_load_client_class("oci.file_storage", "FileStorageClient"), ctx, region=region)


def get_fleet_apps_management_client(ctx: AuthContext, region: str) -> Any:
    """Create FleetAppsManagementAdminClient in the specified region."""
    return _cached_client(
        _load_client_class("oci.fleet_apps_management", "FleetAppsManagementAdminClient"),
        ctx,
        region=region,
    )


def get_functions_client(ctx: AuthContext, region: str) -> Any:
    """Create FunctionsManagementClient in the specified region."""
    return _cached_client(_load_client_class("oci.functions", "FunctionsManagementClient"), ctx, region=region)


def get_generative_ai_agent_client(ctx: AuthContext, region: str) -> Any:
    """Create GenerativeAiAgentClient in the specified region."""
    return _cached_client(_load_client_class("oci.generative_ai_agent", "GenerativeAiAgentClient"), ctx, region=region)


def get_identity_domains_client(ctx: AuthContext, region: Optional[str] = None) -> Any:
    """Create IdentityDomainsClient (identity domains) with optional region."""
    return _cached_client(_load_client_class("oci.identity_domains", "IdentityDomainsClient"), ctx, region=region)


def get_integration_client(ctx: AuthContext, region: str) -> Any:
    """Create IntegrationInstanceClient in the specified region."""
    return _cached_client(_load_client_class("oci.integration", "IntegrationInstanceClient"), ctx, region=region)


def get_visual_builder_client(ctx: AuthContext, region: str) -> Any:
    """Create VbInstanceClient in the specified region."""
    return _cached_client(_load_client_class("oci.visual_builder", "VbInstanceClient"), ctx, region=region)


def get_kms_management_client(ctx: AuthContext, region: str) -> Any:
    """Create KmsManagementClient in the specified region."""
    return _cached_client(_load_client_class("oci.key_management", "KmsManagementClient"), ctx, region=region)


def get_kms_hsm_client(ctx: AuthContext, region: str) -> Any:
    """Create KmsHsmClusterClient in the specified region."""
    return _cached_client(_load_client_class("oci.key_management", "KmsHsmClusterClient"), ctx, region=region)


def get_limits_client(ctx: AuthContext, region: Optional[str] = None) -> Any:
    """Create LimitsClient (global)."""
    return _cached_client(_load_client_class("oci.limits", "LimitsClient"), ctx, region=region)


def get_management_agent_client(ctx: AuthContext, region: str) -> Any:
    """Create ManagementAgentClient in the specified region."""
    return _cached_client(_load_client_class("oci.management_agent", "ManagementAgentClient"), ctx, region=region)


def get_monitoring_client(ctx: AuthContext, region: str) -> Any:
    """Create MonitoringClient in the specified region."""
    return _cached_client(_load_client_class("oci.monitoring", "MonitoringClient"), ctx, region=region)


def get_mysql_backup_client(ctx: AuthContext, region: str) -> Any:
    """Create DbBackupsClient in the specified region."""
    return _cached_client(_load_client_class("oci.mysql", "DbBackupsClient"), ctx, region=region)


def get_mysql_db_system_client(ctx: AuthContext, region: str) -> Any:
    """Create DbSystemClient in the specified region."""
    return _cached_client(_load_client_class("oci.mysql", "DbSystemClient"), ctx, region=region)


def get_oda_client(ctx: AuthContext, region: str) -> Any:
    """Create OdaClient in the specified region."""
    return _cached_client(_load_client_class("oci.oda", "OdaClient"), ctx, region=region)


def get_ons_control_plane_client(ctx: AuthContext, region: str) -> Any:
    """Create NotificationControlPlaneClient in the specified region."""
    return _cached_client(_load_client_class("oci.ons", "NotificationControlPlaneClient"), ctx, region=region)


def get_ons_data_plane_client(ctx: AuthContext, region: str) -> Any:
    """Create NotificationDataPlaneClient in the specified region."""
    return _cached_client(_load_client_class("oci.ons", "NotificationDataPlaneClient"), ctx, region=region)


def get_resource_manager_client(ctx: AuthContext, region: str) -> Any:
    """Create ResourceManagerClient in the specified region."""
    return _cached_client(_load_client_class("oci.resource_manager", "ResourceManagerClient"), ctx, region=region)


def get_osmh_lifecycle_environment_client(ctx: AuthContext, region: str) -> Any:
    """Create LifecycleEnvironmentClient in the specified region."""
    return _cached_client(
        _load_client_class("oci.os_management_hub", "LifecycleEnvironmentClient"),
        ctx,
        region=region,
    )


def get_osmh_managed_instance_group_client(ctx: AuthContext, region: str) -> Any:
    """Create ManagedInstanceGroupClient in the specified region."""
    return _cached_client(
        _load_client_class("oci.os_management_hub", "ManagedInstanceGroupClient"),
        ctx,
        region=region,
    )


def get_osmh_profile_client(ctx: AuthContext, region: str) -> Any:
    """Create OnboardingClient in the specified region."""
    return _cached_client(_load_client_class("oci.os_management_hub", "OnboardingClient"), ctx, region=region)


def get_osmh_scheduled_job_client(ctx: AuthContext, region: str) -> Any:
    """Create ScheduledJobClient in the specified region."""
    return _cached_client(_load_client_class("oci.os_management_hub", "ScheduledJobClient"), ctx, region=region)


def get_osmh_software_source_client(ctx: AuthContext, region: str) -> Any:
    """Create SoftwareSourceClient in the specified region."""
    return _cached_client(_load_client_class("oci.os_management_hub", "SoftwareSourceClient"), ctx, region=region)


def get_postgresql_client(ctx: AuthContext, region: str) -> Any:
    """Create PostgresqlClient in the specified region."""
    return _cached_client(_load_client_class("oci.psql", "PostgresqlClient"), ctx, region=region)


def get_recovery_client(ctx: AuthContext, region: str) -> Any:
    """Create DatabaseRecoveryClient in the specified region."""
    return _cached_client(_load_client_class("oci.recovery", "DatabaseRecoveryClient"), ctx, region=region)


def get_resource_scheduler_client(ctx: AuthContext, region: str) -> Any:
    """Create ScheduleClient in the specified region."""
    return _cached_client(_load_client_class("oci.resource_scheduler", "ScheduleClient"), ctx, region=region)


def get_security_attribute_client(ctx: AuthContext, region: str) -> Any:
    """Create SecurityAttributeClient in the specified region."""
    return _cached_client(_load_client_class("oci.security_attribute", "SecurityAttributeClient"), ctx, region=region)


def get_service_connector_client(ctx: AuthContext, region: str) -> Any:
    """Create ServiceConnectorClient in the specified region."""
    return _cached_client(_load_client_class("oci.sch", "ServiceConnectorClient"), ctx, region=region)


def get_stream_admin_client(ctx: AuthContext, region: str) -> Any:
    """Create StreamAdminClient in the specified region."""
    return _cached_client(_load_client_class("oci.streaming", "StreamAdminClient"), ctx, region=region)


def get_vaults_client(ctx: AuthContext, region: str) -> Any:
    """Create VaultsClient in the specified region."""
    return _cached_client(_load_client_class("oci.vault", "VaultsClient"), ctx, region=region)


def get_vn_monitoring_client(ctx: AuthContext, region: str) -> Any:
    """Create VnMonitoringClient in the specified region."""
    return _cached_client(_load_client_class("oci.vn_monitoring", "VnMonitoringClient"), ctx, region=region)


def get_vulnerability_scanning_client(ctx: AuthContext, region: str) -> Any:
    """Create VulnerabilityScanningClient in the specified region."""
    return _cached_client(
        _load_client_class("oci.vulnerability_scanning", "VulnerabilityScanningClient"),
        ctx,
        region=region,
    )


def get_waas_client(ctx: AuthContext, region: str) -> Any:
    """Create WaasClient in the specified region."""
    return _cached_client(_load_client_class("oci.waas", "WaasClient"), ctx, region=region)


def get_waas_redirect_client(ctx: AuthContext, region: str) -> Any:
    """Create RedirectClient in the specified region."""
    return _cached_client(_load_client_class("oci.waas", "RedirectClient"), ctx, region=region)


def get_zpr_client(ctx: AuthContext, region: str) -> Any:
    """Create ZprClient in the specified region."""
    return _cached_client(_load_client_class("oci.zpr", "ZprClient"), ctx, region=region)


def get_usage_api_client(ctx: AuthContext, region: Optional[str] = None) -> Any:
    """Create UsageapiClient (cost/usage read-only)."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    try:  # pragma: no cover - optional module varies by SDK version
        import importlib

        importlib.import_module("oci.usage_api")
    except Exception as e:  # pragma: no cover
        raise AuthError(f"oci.usage_api not available in installed SDK: {e}") from e
    return _cached_client(oci.usage_api.UsageapiClient, ctx, region=region)  # type: ignore[attr-defined]


def get_budget_client(ctx: AuthContext, region: Optional[str] = None) -> Any:
    """Create BudgetClient (read-only)."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    try:  # pragma: no cover - optional module varies by SDK version
        import importlib

        importlib.import_module("oci.budget")
    except Exception as e:  # pragma: no cover
        raise AuthError(f"oci.budget not available in installed SDK: {e}") from e
    return _cached_client(oci.budget.BudgetClient, ctx, region=region)  # type: ignore[attr-defined]


def get_osub_usage_client(ctx: AuthContext, region: Optional[str] = None) -> Any:
    """Create ComputedUsageClient for OneSubscription usage (read-only)."""
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    try:  # pragma: no cover - optional module varies by SDK version
        import importlib

        importlib.import_module("oci.osub_usage")
    except Exception as e:  # pragma: no cover
        raise AuthError(f"oci.osub_usage not available in installed SDK: {e}") from e
    return _cached_client(oci.osub_usage.ComputedUsageClient, ctx, region=region)  # type: ignore[attr-defined]


def get_home_region_name(ctx: AuthContext) -> Optional[str]:
    """
    Resolve the tenancy home region name from region subscriptions.
    Returns region_name (e.g., "us-ashburn-1") or None if unavailable.
    """
    if oci is None:  # pragma: no cover
        raise AuthError("oci Python SDK not installed.")
    tenancy = get_tenancy_ocid(ctx)
    if not tenancy:
        raise AuthError("Tenancy OCID is required to resolve home region.")

    identity = get_identity_client(ctx)
    try:
        ten = identity.get_tenancy(tenancy).data  # type: ignore[attr-defined]
    except Exception as e:
        mapped = map_oci_error(e, "OCI SDK error while fetching tenancy details")
        if mapped:
            raise mapped from e
        raise
    home_key = getattr(ten, "home_region_key", None) or getattr(ten, "homeRegionKey", None)
    if not home_key:
        return None

    try:
        subs = identity.list_region_subscriptions(tenancy)  # type: ignore[attr-defined]
    except Exception as e:
        mapped = map_oci_error(e, "OCI SDK error while listing region subscriptions")
        if mapped:
            raise mapped from e
        raise

    for rs in getattr(subs, "data", []) or []:
        if getattr(rs, "region_key", None) == home_key:
            return getattr(rs, "region_name", None)
    return None


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
