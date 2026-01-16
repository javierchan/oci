from __future__ import annotations

from typing import Any, Callable, Dict

from ..oci import clients as oci_clients
from ..util.serialization import sanitize_for_json
from . import get_enrich_context, register_enricher
from .base import Enricher, EnrichResult

FetchFunc = Callable[[Dict[str, Any]], Dict[str, Any]]


def _record_region(record: Dict[str, Any]) -> str:
    region = str(record.get("region") or "")
    if not region:
        raise ValueError("Record is missing region")
    return region


def _record_display_name(record: Dict[str, Any]) -> str:
    name = str(record.get("displayName") or "")
    if not name:
        raise ValueError("Record is missing displayName")
    return name


def _record_ocid(record: Dict[str, Any]) -> str:
    ocid = str(record.get("ocid") or "")
    if not ocid:
        raise ValueError("Record is missing ocid")
    return ocid


def _record_compartment_id(record: Dict[str, Any]) -> str:
    compartment_id = str(record.get("compartmentId") or "")
    if not compartment_id:
        raise ValueError("Record is missing compartmentId")
    return compartment_id


def _metadata_details(record: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    _merge_search_summary_metadata(record, metadata)
    details: Dict[str, Any] = {"metadata": metadata}
    if "searchSummary" in record:
        details["searchSummary"] = record["searchSummary"]
    return details


def _search_summary_value(record: Dict[str, Any], *keys: str) -> str | None:
    summary = record.get("searchSummary")
    if not isinstance(summary, dict):
        return None
    for key in keys:
        value = summary.get(key)
        if isinstance(value, str) and value:
            return value
    extra = summary.get("additional_details") or summary.get("additionalDetails")
    if isinstance(extra, dict):
        for key in keys:
            value = extra.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _search_summary_entry(record: Dict[str, Any], *keys: str) -> Any | None:
    summary = record.get("searchSummary")
    if not isinstance(summary, dict):
        return None
    for key in keys:
        if key in summary and summary[key] is not None:
            return summary[key]
    extra = summary.get("additional_details") or summary.get("additionalDetails")
    if isinstance(extra, dict):
        for key in keys:
            if key in extra and extra[key] is not None:
                return extra[key]
    return None


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _metadata_has_value(metadata: Dict[str, Any], *keys: str) -> bool:
    for key in keys:
        for candidate in {key, _to_camel(key), _to_snake(key)}:
            if candidate in metadata and not _is_missing_value(metadata.get(candidate)):
                return True
    return False


def _to_snake(key: str) -> str:
    return "".join([("_" + ch.lower()) if ch.isupper() else ch for ch in key]).lstrip("_")


def _to_camel(key: str) -> str:
    parts = key.split("_")
    return "".join([p[:1].upper() + p[1:] if i > 0 else p for i, p in enumerate(parts)])


def _merge_search_summary_metadata(record: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    if not isinstance(metadata, dict):
        return
    keys = {
        "vcnId": ("vcnId", "vcn_id", "networkId", "network_id"),
        "vcnIds": ("vcnIds", "vcn_ids"),
        "subnetId": ("subnetId", "subnet_id"),
        "subnetIds": ("subnetIds", "subnet_ids"),
        "dhcpOptionsId": ("dhcpOptionsId", "dhcp_options_id"),
        "routeTableId": ("routeTableId", "route_table_id"),
        "securityListIds": ("securityListIds", "security_list_ids"),
        "nsgIds": ("nsgIds", "nsg_ids", "networkSecurityGroupIds", "network_security_group_ids"),
        "drgId": ("drgId", "drg_id", "gatewayId", "gateway_id"),
        "assignedEntityId": ("assignedEntityId", "assigned_entity_id"),
    }
    for canonical, aliases in keys.items():
        if _metadata_has_value(metadata, *aliases):
            continue
        value = _search_summary_entry(record, *aliases)
        if _is_missing_value(value):
            continue
        snake = _to_snake(canonical)
        camel = _to_camel(canonical)
        metadata.setdefault(snake, value)
        metadata.setdefault(camel, value)


def _sdk_data_to_dict(resp: Any) -> Dict[str, Any]:
    data = getattr(resp, "data", resp)
    return sanitize_for_json(data)


def _fetch_by_ocid(
    record: Dict[str, Any],
    client_factory: Callable[[Any, str], Any],
    method_name: str,
) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = client_factory(ctx, _record_region(record))
    method = getattr(client, method_name, None)
    if method is None:
        raise ValueError(f"{client.__class__.__name__} missing {method_name}")
    return _sdk_data_to_dict(method(_record_ocid(record)))


class SDKMetadataEnricher(Enricher):
    def __init__(self, resource_type: str, fetch: Callable[[Dict[str, Any]], Dict[str, Any]]) -> None:
        self.resource_type = resource_type
        self._fetch = fetch

    def enrich(self, record: Dict[str, Any]) -> EnrichResult:
        try:
            metadata = self._fetch(record)
            return EnrichResult(
                details=_metadata_details(record, metadata),
                relationships=[],
                enrichStatus="OK",
                enrichError=None,
            )
        except Exception as e:
            return EnrichResult(
                details=_metadata_details(record, {}),
                relationships=[],
                enrichStatus="ERROR",
                enrichError=str(e),
            )


def _fetch_instance(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_compute_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_instance(_record_ocid(record)))


def _fetch_image(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_compute_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_image(_record_ocid(record)))


def _fetch_instance_configuration(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_compute_management_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_instance_configuration(_record_ocid(record)))


def _fetch_instance_pool(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_compute_management_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_instance_pool(_record_ocid(record)))


def _fetch_boot_volume(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_blockstorage_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_boot_volume(_record_ocid(record)))


def _fetch_block_volume(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_blockstorage_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_volume(_record_ocid(record)))


def _fetch_vcn(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_vcn(_record_ocid(record)))


def _fetch_subnet(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    metadata = _sdk_data_to_dict(client.get_subnet(_record_ocid(record)))
    if not (metadata.get("dhcp_options_id") or metadata.get("dhcpOptionsId")):
        dhcp_id = _search_summary_value(record, "dhcpOptionsId", "dhcp_options_id")
        if dhcp_id:
            metadata.setdefault("dhcp_options_id", dhcp_id)
            metadata.setdefault("dhcpOptionsId", dhcp_id)
    return metadata


def _fetch_vnic(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_vnic(_record_ocid(record)))


def _fetch_nsg(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_network_security_group(_record_ocid(record)))


def _fetch_security_list(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_security_list(_record_ocid(record)))


def _fetch_route_table(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_route_table(_record_ocid(record)))


def _fetch_internet_gateway(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_internet_gateway(_record_ocid(record)))


def _fetch_nat_gateway(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_nat_gateway(_record_ocid(record)))


def _fetch_service_gateway(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_service_gateway(_record_ocid(record)))


def _fetch_drg(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_drg(_record_ocid(record)))


def _fetch_drg_attachment(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_drg_attachment(_record_ocid(record)))


def _fetch_ip_sec_connection(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_ip_sec_connection(_record_ocid(record)))


def _fetch_virtual_circuit(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_virtual_circuit(_record_ocid(record)))


def _fetch_cpe(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_cpe(_record_ocid(record)))


def _fetch_local_peering_gateway(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_local_peering_gateway(_record_ocid(record)))


def _fetch_remote_peering_connection(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_remote_peering_connection(_record_ocid(record)))


def _fetch_cross_connect(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_cross_connect(_record_ocid(record)))


def _fetch_cross_connect_group(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_cross_connect_group(_record_ocid(record)))


def _fetch_dhcp_options(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_dhcp_options(_record_ocid(record)))


def _fetch_private_ip(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_private_ip(_record_ocid(record)))


def _fetch_volume(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_blockstorage_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_volume(_record_ocid(record)))


def _fetch_bucket(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_object_storage_client(ctx, _record_region(record))
    namespace = getattr(client.get_namespace(), "data", None)
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("Object Storage namespace is missing/invalid")
    bucket_name = _record_display_name(record)
    return _sdk_data_to_dict(client.get_bucket(namespace, bucket_name))


def _fetch_dns_resolver(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_dns_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_resolver(_record_ocid(record)))


def _fetch_dns_view(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_dns_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_view(_record_ocid(record)))


def _fetch_log_group(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_logging_management_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_log_group(_record_ocid(record)))


def _fetch_log_analytics_entity(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_log_analytics_client(ctx, _record_region(record))
    from ..auth.providers import get_tenancy_ocid

    tenancy_ocid = get_tenancy_ocid(ctx)
    if not tenancy_ocid:
        raise ValueError("Unable to resolve tenancy OCID for Log Analytics")

    namespaces_resp = client.list_namespaces(tenancy_ocid)
    namespaces_data = getattr(namespaces_resp, "data", namespaces_resp)
    namespaces_items: list[Any]
    if isinstance(namespaces_data, list):
        namespaces_items = namespaces_data
    elif hasattr(namespaces_data, "items") and isinstance(getattr(namespaces_data, "items"), list):
        namespaces_items = getattr(namespaces_data, "items")
    elif isinstance(namespaces_data, dict) and isinstance(namespaces_data.get("items"), list):
        namespaces_items = namespaces_data["items"]
    else:
        raise ValueError("Log Analytics namespaces response is invalid")

    namespace_names: list[str] = []
    for item in namespaces_items:
        if isinstance(item, str) and item:
            namespace_names.append(item)
            continue

        name = getattr(item, "namespace_name", None)
        if isinstance(name, str) and name:
            namespace_names.append(name)

    namespace_names = sorted(set(namespace_names))
    if len(namespace_names) != 1:
        raise ValueError(f"Unable to resolve Log Analytics namespace (count={len(namespace_names)})")

    namespace_name = namespace_names[0]
    return _sdk_data_to_dict(client.get_log_analytics_entity(namespace_name, _record_ocid(record)))


def _fetch_media_workflow(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_media_services_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_media_workflow(_record_ocid(record)))


def _fetch_media_asset(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_media_services_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_media_asset(_record_ocid(record)))


def _fetch_stream_cdn_config(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_media_services_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_stream_cdn_config(_record_ocid(record)))


def _fetch_stream_distribution_channel(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_media_services_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_stream_distribution_channel(_record_ocid(record)))


def _fetch_stream_packaging_config(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_media_services_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_stream_packaging_config(_record_ocid(record)))


def _fetch_public_ip(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_virtual_network_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_public_ip(_record_ocid(record)))


def _fetch_load_balancer(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_load_balancer_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_load_balancer(_record_ocid(record)))


def _fetch_policy(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    # Identity is effectively global but the SDK still accepts a region.
    client = oci_clients.get_identity_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_policy(_record_ocid(record)))


def _fetch_dns_zone(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_dns_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_zone(_record_ocid(record)))


def _fetch_bastion(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_bastion_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_bastion(_record_ocid(record)))


def _fetch_vault(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_vault_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_vault(_record_ocid(record)))


def _fetch_secret(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_secrets_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_secret(_record_ocid(record)))


def _fetch_cloud_guard_target(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_cloud_guard_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_target(_record_ocid(record)))


def _fetch_network_firewall(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_network_firewall_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_network_firewall(_record_ocid(record)))


def _fetch_network_firewall_policy(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_network_firewall_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_network_firewall_policy(_record_ocid(record)))


def _fetch_web_app_firewall(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_waf_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_web_app_firewall(_record_ocid(record)))


def _fetch_web_app_firewall_policy(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_waf_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_web_app_firewall_policy(_record_ocid(record)))


def _fetch_agcs_governance_instance(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_access_governance_client, "get_governance_instance")


def _fetch_ai_data_platform(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_ai_data_platform_client, "get_ai_data_platform")


def _fetch_ai_language_project(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_ai_language_client, "get_project")


def _fetch_ai_vision_model(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_ai_vision_client, "get_model")


def _fetch_ai_vision_project(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_ai_vision_client, "get_project")


def _fetch_alarm(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_monitoring_client, "get_alarm")


def _fetch_analytics_instance(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_analytics_client, "get_analytics_instance")


def _fetch_api_deployment(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_api_gateway_deployment_client, "get_deployment")


def _fetch_api_gateway(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_api_gateway_gateway_client, "get_gateway")


def _fetch_api_gateway_api(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_api_gateway_client, "get_api")


def _fetch_autonomous_database(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_database_client, "get_autonomous_database")


def _fetch_boot_volume_backup(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_blockstorage_client, "get_boot_volume_backup")


def _fetch_budget(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_budget_client, "get_budget")


def _fetch_certificate(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_certificates_management_client, "get_certificate")


def _fetch_certificate_authority(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_certificates_management_client, "get_certificate_authority")


def _fetch_cloud_guard_detector_recipe(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_cloud_guard_client, "get_detector_recipe")


def _fetch_cloud_guard_managed_list(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_cloud_guard_client, "get_managed_list")


def _fetch_cloud_guard_responder_recipe(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_cloud_guard_client, "get_responder_recipe")


def _fetch_cloud_guard_saved_query(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_cloud_guard_client, "get_saved_query")


def _fetch_cloud_guard_security_recipe(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_cloud_guard_client, "get_security_recipe")


def _fetch_cloud_guard_security_zone(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_cloud_guard_client, "get_security_zone")


def _fetch_cluster(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_container_engine_client, "get_cluster")


def _fetch_compartment(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_identity_client, "get_compartment")


def _fetch_connect_harness(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_stream_admin_client, "get_connect_harness")


def _fetch_console_dashboard(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_dashboard_client, "get_dashboard")


def _fetch_console_dashboard_group(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_dashboard_group_client, "get_dashboard_group")


def _fetch_container(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_container_instance_client, "get_container")


def _fetch_container_image(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_artifacts_client, "get_container_image")


def _fetch_container_instance(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_container_instance_client, "get_container_instance")


def _fetch_container_repo(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_artifacts_client, "get_container_repository")


def _fetch_dis_workspace(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_integration_client, "get_workspace")


def _fetch_data_flow_application(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_flow_client, "get_application")


def _fetch_data_flow_run(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_flow_client, "get_run")


def _fetch_data_labeling_dataset(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_labeling_management_client, "get_dataset")


def _fetch_data_safe_audit_profile(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_safe_client, "get_audit_profile")


def _fetch_data_safe_report_definition(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_safe_client, "get_report_definition")


def _fetch_data_safe_security_assessment(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_safe_client, "get_security_assessment")


def _fetch_data_safe_user_assessment(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_safe_client, "get_user_assessment")


def _fetch_data_science_job(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_science_client, "get_job")


def _fetch_data_science_job_run(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_science_client, "get_job_run")


def _fetch_data_science_model(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_science_client, "get_model")


def _fetch_data_science_model_deployment(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_science_client, "get_model_deployment")


def _fetch_data_science_model_version_set(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_science_client, "get_model_version_set")


def _fetch_data_science_notebook_session(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_science_client, "get_notebook_session")


def _fetch_data_science_project(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_data_science_client, "get_project")


def _fetch_database_tools_private_endpoint(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_database_tools_client, "get_database_tools_private_endpoint")


def _fetch_db_node(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_database_client, "get_db_node")


def _fetch_dedicated_vm_host(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_compute_client, "get_dedicated_vm_host")


def _fetch_devops_build_pipeline_stage(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_devops_client, "get_build_pipeline_stage")


def _fetch_devops_build_run(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_devops_client, "get_build_run")


def _fetch_devops_deploy_artifact(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_devops_client, "get_deploy_artifact")


def _fetch_devops_project(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_devops_client, "get_project")


def _fetch_devops_repository(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_devops_client, "get_repository")


def _fetch_drg_route_distribution(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_virtual_network_client, "get_drg_route_distribution")


def _fetch_drg_route_table(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_virtual_network_client, "get_drg_route_table")


def _fetch_dynamic_resource_group(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_identity_client, "get_dynamic_group")


def _fetch_group(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_identity_client, "get_group")


def _fetch_email_dkim(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_email_client, "get_dkim")


def _fetch_email_domain(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_email_client, "get_email_domain")


def _fetch_email_sender(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_email_client, "get_sender")


def _fetch_event_rule(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_events_client, "get_rule")


def _fetch_fams_platform_configuration(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_fleet_apps_management_client, "get_platform_configuration")


def _fetch_file_system(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_file_storage_client, "get_file_system")


def _fetch_functions_application(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_functions_client, "get_application")


def _fetch_functions_function(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_functions_client, "get_function")


def _fetch_genai_agent(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_generative_ai_agent_client, "get_agent")


def _fetch_genai_data_ingestion_job(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_generative_ai_agent_client, "get_data_ingestion_job")


def _fetch_genai_data_source(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_generative_ai_agent_client, "get_data_source")


def _fetch_genai_agent_endpoint(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_generative_ai_agent_client, "get_agent_endpoint")


def _fetch_genai_knowledge_base(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_generative_ai_agent_client, "get_knowledge_base")


def _fetch_http_redirect(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_waas_redirect_client, "get_http_redirect")


def _fetch_identity_domain_app(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_identity_domains_client, "get_app")


def _fetch_identity_provider(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_identity_client, "get_identity_provider")


def _fetch_integration_instance(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_integration_client, "get_integration_instance")


def _fetch_kms_key(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_kms_management_client, "get_key")


def _fetch_kms_hsm_cluster(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_kms_hsm_client, "get_hsm_cluster")


def _fetch_kms_hsm_partition(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_kms_hsm_client, "get_hsm_partition")


def _fetch_log(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_logging_management_client, "get_log")


def _fetch_log_saved_search(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_logging_management_client, "get_log_saved_search")


def _fetch_management_agent_install_key(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_management_agent_client, "get_management_agent_install_key")


def _fetch_mysql_backup(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_mysql_backup_client, "get_backup")


def _fetch_mysql_db_system(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_mysql_db_system_client, "get_db_system")


def _fetch_oda_instance(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_oda_client, "get_oda_instance")


def _fetch_ons_subscription(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_ons_data_plane_client, "get_subscription")


def _fetch_ons_topic(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_ons_control_plane_client, "get_topic")


def _fetch_orm_config_source_provider(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_resource_manager_client, "get_configuration_source_provider")


def _fetch_orm_job(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_resource_manager_client, "get_job")


def _fetch_orm_private_endpoint(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_resource_manager_client, "get_private_endpoint")


def _fetch_orm_stack(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_resource_manager_client, "get_stack")


def _fetch_orm_template(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_resource_manager_client, "get_template")


def _fetch_osmh_lifecycle_environment(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_osmh_lifecycle_environment_client, "get_lifecycle_environment")


def _fetch_osmh_managed_instance_group(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_osmh_managed_instance_group_client, "get_managed_instance_group")


def _fetch_osmh_profile(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_osmh_profile_client, "get_profile")


def _fetch_osmh_scheduled_job(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_osmh_scheduled_job_client, "get_scheduled_job")


def _fetch_osmh_software_source(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_osmh_software_source_client, "get_software_source")


def _fetch_path_analyzer_test(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_vn_monitoring_client, "get_path_analyzer_test")


def _fetch_pluggable_database(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_database_client, "get_pluggable_database")


def _fetch_postgresql_configuration(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_postgresql_client, "get_configuration")


def _fetch_protected_database(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_recovery_client, "get_protected_database")


def _fetch_recovery_service_subnet(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_recovery_client, "get_recovery_service_subnet")


def _fetch_resource_schedule(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_resource_scheduler_client, "get_schedule")


def _fetch_security_attribute_namespace(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_security_attribute_client, "get_security_attribute_namespace")


def _fetch_service_connector(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_service_connector_client, "get_service_connector")


def _fetch_stream(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_stream_admin_client, "get_stream")


def _fetch_tag_default(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_identity_client, "get_tag_default")


def _fetch_tag_namespace(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_identity_client, "get_tag_namespace")


def _fetch_user(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_identity_client, "get_user")


def _fetch_vault_secret(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_vaults_client, "get_secret")


def _fetch_visual_builder_instance(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_visual_builder_client, "get_vb_instance")


def _fetch_volume_backup(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_blockstorage_client, "get_volume_backup")


def _fetch_volume_backup_policy(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_blockstorage_client, "get_volume_backup_policy")


def _fetch_volume_group(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_blockstorage_client, "get_volume_group")


def _fetch_volume_group_backup(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_blockstorage_client, "get_volume_group_backup")


def _fetch_vss_host_scan_recipe(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_vulnerability_scanning_client, "get_host_scan_recipe")


def _fetch_vss_host_scan_target(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_vulnerability_scanning_client, "get_host_scan_target")


def _fetch_waas_certificate(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_waas_client, "get_certificate")


def _fetch_zpr_policy(record: Dict[str, Any]) -> Dict[str, Any]:
    return _fetch_by_ocid(record, oci_clients.get_zpr_client, "get_zpr_policy")


def register_metadata_enrichers() -> None:
    mapping: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
        # Compute
        "Instance": _fetch_instance,
        "Image": _fetch_image,
        "BootVolume": _fetch_boot_volume,
        "BlockVolume": _fetch_block_volume,
        "InstanceConfiguration": _fetch_instance_configuration,
        "InstancePool": _fetch_instance_pool,
        # Networking
        "Vcn": _fetch_vcn,
        "Subnet": _fetch_subnet,
        "Vnic": _fetch_vnic,
        "NetworkSecurityGroup": _fetch_nsg,
        "SecurityList": _fetch_security_list,
        "RouteTable": _fetch_route_table,
        "InternetGateway": _fetch_internet_gateway,
        "NatGateway": _fetch_nat_gateway,
        "ServiceGateway": _fetch_service_gateway,
        "Drg": _fetch_drg,
        "DrgAttachment": _fetch_drg_attachment,
        "IPSecConnection": _fetch_ip_sec_connection,
        "IpSecConnection": _fetch_ip_sec_connection,
        "VirtualCircuit": _fetch_virtual_circuit,
        "Cpe": _fetch_cpe,
        "LocalPeeringGateway": _fetch_local_peering_gateway,
        "RemotePeeringConnection": _fetch_remote_peering_connection,
        "CrossConnect": _fetch_cross_connect,
        "CrossConnectGroup": _fetch_cross_connect_group,
        "DhcpOptions": _fetch_dhcp_options,
        "DHCPOptions": _fetch_dhcp_options,
        "PrivateIp": _fetch_private_ip,
        # Block Storage
        "Volume": _fetch_volume,
        "PublicIp": _fetch_public_ip,
        "LoadBalancer": _fetch_load_balancer,
        # Identity
        "Policy": _fetch_policy,
        # DNS (Resource Search can surface this as different type strings)
        "DnsZone": _fetch_dns_zone,
        "CustomerDnsZone": _fetch_dns_zone,
        "DnsResolver": _fetch_dns_resolver,
        "DnsView": _fetch_dns_view,
        # Object Storage
        "Bucket": _fetch_bucket,
        # Logging
        "LogGroup": _fetch_log_group,
        # Log Analytics
        "LogAnalyticsEntity": _fetch_log_analytics_entity,
        # Media Services (Streaming + Media Workflows)
        "MediaWorkflow": _fetch_media_workflow,
        "MediaAsset": _fetch_media_asset,
        "StreamCdnConfig": _fetch_stream_cdn_config,
        "StreamDistributionChannel": _fetch_stream_distribution_channel,
        "StreamPackagingConfig": _fetch_stream_packaging_config,
        # Security
        "Bastion": _fetch_bastion,
        "Vault": _fetch_vault,
        "Secret": _fetch_secret,
        "CloudGuardTarget": _fetch_cloud_guard_target,
        "NetworkFirewall": _fetch_network_firewall,
        "NetworkFirewallPolicy": _fetch_network_firewall_policy,
        "WebAppFirewall": _fetch_web_app_firewall,
        "WebAppFirewallPolicy": _fetch_web_app_firewall_policy,
        # Access governance
        "AgcsGovernanceInstance": _fetch_agcs_governance_instance,
        # AI services
        "AiDataPlatform": _fetch_ai_data_platform,
        "AiLanguageProject": _fetch_ai_language_project,
        "AiVisionModel": _fetch_ai_vision_model,
        "AiVisionProject": _fetch_ai_vision_project,
        # Analytics
        "AnalyticsInstance": _fetch_analytics_instance,
        # Alarms
        "Alarm": _fetch_alarm,
        # API Gateway
        "ApiDeployment": _fetch_api_deployment,
        "ApiGateway": _fetch_api_gateway,
        "ApiGatewayApi": _fetch_api_gateway_api,
        # Budgets
        "Budget": _fetch_budget,
        # Certificates
        "Certificate": _fetch_certificate,
        "CertificateAuthority": _fetch_certificate_authority,
        # Cloud Guard + Security Zones
        "CloudGuardDetectorRecipe": _fetch_cloud_guard_detector_recipe,
        "CloudGuardManagedList": _fetch_cloud_guard_managed_list,
        "CloudGuardResponderRecipe": _fetch_cloud_guard_responder_recipe,
        "CloudGuardSavedQuery": _fetch_cloud_guard_saved_query,
        "SecurityZonesSecurityRecipe": _fetch_cloud_guard_security_recipe,
        "SecurityZonesSecurityZone": _fetch_cloud_guard_security_zone,
        # Container Engine + Instances + Registry
        "ClustersCluster": _fetch_cluster,
        "ConnectHarness": _fetch_connect_harness,
        "ConsoleDashboard": _fetch_console_dashboard,
        "ConsoleDashboardGroup": _fetch_console_dashboard_group,
        "Container": _fetch_container,
        "ContainerImage": _fetch_container_image,
        "ContainerInstance": _fetch_container_instance,
        "ContainerRepo": _fetch_container_repo,
        # Data Integration + Flow + Labeling
        "DISWorkspace": _fetch_dis_workspace,
        "DataFlowApplication": _fetch_data_flow_application,
        "DataFlowRun": _fetch_data_flow_run,
        "DataLabelingDataset": _fetch_data_labeling_dataset,
        # Data Safe
        "DataSafeAuditProfile": _fetch_data_safe_audit_profile,
        "DataSafeReportDefinition": _fetch_data_safe_report_definition,
        "DataSafeSecurityAssessment": _fetch_data_safe_security_assessment,
        "DataSafeUserAssessment": _fetch_data_safe_user_assessment,
        # Data Science
        "DataScienceJob": _fetch_data_science_job,
        "DataScienceJobRun": _fetch_data_science_job_run,
        "DataScienceModel": _fetch_data_science_model,
        "DataScienceModelDeployment": _fetch_data_science_model_deployment,
        "DataScienceModelVersionSet": _fetch_data_science_model_version_set,
        "DataScienceNotebookSession": _fetch_data_science_notebook_session,
        "DataScienceProject": _fetch_data_science_project,
        # Database + tools
        "AutonomousDatabase": _fetch_autonomous_database,
        "DatabaseToolsPrivateEndpoint": _fetch_database_tools_private_endpoint,
        "DbNode": _fetch_db_node,
        "DedicatedVmHost": _fetch_dedicated_vm_host,
        "PluggableDatabase": _fetch_pluggable_database,
        # DevOps
        "DevOpsBuildPipelineStage": _fetch_devops_build_pipeline_stage,
        "DevOpsBuildRun": _fetch_devops_build_run,
        "DevOpsDeployArtifact": _fetch_devops_deploy_artifact,
        "DevOpsProject": _fetch_devops_project,
        "DevOpsRepository": _fetch_devops_repository,
        # Dynamic groups + IAM
        "Compartment": _fetch_compartment,
        "DynamicResourceGroup": _fetch_dynamic_resource_group,
        "Group": _fetch_group,
        "IdentityProvider": _fetch_identity_provider,
        "User": _fetch_user,
        # Email Delivery
        "EmailDkim": _fetch_email_dkim,
        "EmailDomain": _fetch_email_domain,
        "EmailSender": _fetch_email_sender,
        # Events
        "EventRule": _fetch_event_rule,
        # Fleet Apps Management
        "Famsplatformconfiguration": _fetch_fams_platform_configuration,
        # File Storage
        "FileSystem": _fetch_file_system,
        # Functions
        "FunctionsApplication": _fetch_functions_application,
        "FunctionsFunction": _fetch_functions_function,
        # Generative AI Agent
        "GenAiAgent": _fetch_genai_agent,
        "GenAiAgentDataIngestionJob": _fetch_genai_data_ingestion_job,
        "GenAiAgentDataSource": _fetch_genai_data_source,
        "GenAiAgentEndpoint": _fetch_genai_agent_endpoint,
        "GenAiAgentKnowledgeBase": _fetch_genai_knowledge_base,
        # HTTP redirect + WAAS
        "HttpRedirect": _fetch_http_redirect,
        "WaasCertificate": _fetch_waas_certificate,
        # Identity Domains
        "App": _fetch_identity_domain_app,
        # Integration + Visual Builder
        "IntegrationInstance": _fetch_integration_instance,
        "VisualBuilderInstance": _fetch_visual_builder_instance,
        # Key management
        "Key": _fetch_kms_key,
        "KmsHsmCluster": _fetch_kms_hsm_cluster,
        "KmsHsmPartition": _fetch_kms_hsm_partition,
        # Logging
        "Log": _fetch_log,
        "LogSavedSearch": _fetch_log_saved_search,
        # Management Agent
        "ManagementAgentInstallKey": _fetch_management_agent_install_key,
        # MySQL
        "MysqlBackup": _fetch_mysql_backup,
        "MysqlDbSystem": _fetch_mysql_db_system,
        # Networking route tables
        "DrgRouteDistribution": _fetch_drg_route_distribution,
        "DrgRouteTable": _fetch_drg_route_table,
        # Notifications
        "OnsSubscription": _fetch_ons_subscription,
        "OnsTopic": _fetch_ons_topic,
        # ODA
        "OdaInstance": _fetch_oda_instance,
        # Resource Manager
        "OrmConfigSourceProvider": _fetch_orm_config_source_provider,
        "OrmJob": _fetch_orm_job,
        "OrmPrivateEndpoint": _fetch_orm_private_endpoint,
        "OrmStack": _fetch_orm_stack,
        "OrmTemplate": _fetch_orm_template,
        # OS Management Hub
        "OsmhLifecycleEnvironment": _fetch_osmh_lifecycle_environment,
        "OsmhManagedInstanceGroup": _fetch_osmh_managed_instance_group,
        "OsmhProfile": _fetch_osmh_profile,
        "OsmhScheduledJob": _fetch_osmh_scheduled_job,
        "OsmhSoftwareSource": _fetch_osmh_software_source,
        # Path Analyzer
        "PathAnalyzerTest": _fetch_path_analyzer_test,
        # PostgreSQL
        "PostgresqlConfiguration": _fetch_postgresql_configuration,
        # Recovery Service
        "ProtectedDatabase": _fetch_protected_database,
        "RecoveryServiceSubnet": _fetch_recovery_service_subnet,
        # Resource Scheduler
        "ResourceSchedule": _fetch_resource_schedule,
        # Security attributes
        "SecurityAttributeNamespace": _fetch_security_attribute_namespace,
        # Service Connector Hub
        "ServiceConnector": _fetch_service_connector,
        # Streaming
        "Stream": _fetch_stream,
        # Tags
        "TagDefault": _fetch_tag_default,
        "TagNamespace": _fetch_tag_namespace,
        # Vault secret
        "VaultSecret": _fetch_vault_secret,
        # Volume backups/groups
        "BootVolumeBackup": _fetch_boot_volume_backup,
        "VolumeBackup": _fetch_volume_backup,
        "VolumeBackupPolicy": _fetch_volume_backup_policy,
        "VolumeGroup": _fetch_volume_group,
        "VolumeGroupBackup": _fetch_volume_group_backup,
        # Vulnerability Scanning Service
        "VssHostScanRecipe": _fetch_vss_host_scan_recipe,
        "VssHostScanTarget": _fetch_vss_host_scan_target,
        # Zero Trust
        "ZprPolicy": _fetch_zpr_policy,
    }
    # TODO: SDK 2.164.2 does not expose get_* APIs for these resource types yet:
    # - LimitsIncreaseRequest
    # - ProcessAutomationInstance
    # - QueryServiceProject

    for resource_type, fetch in mapping.items():
        register_enricher(
            resource_type,
            lambda rt=resource_type, fn=fetch: SDKMetadataEnricher(rt, fn),
        )
