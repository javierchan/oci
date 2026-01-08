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


def _metadata_details(record: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    details: Dict[str, Any] = {"metadata": metadata}
    if "searchSummary" in record:
        details["searchSummary"] = record["searchSummary"]
    return details


def _sdk_data_to_dict(resp: Any) -> Dict[str, Any]:
    data = getattr(resp, "data", resp)
    return sanitize_for_json(data)


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
    return _sdk_data_to_dict(client.get_subnet(_record_ocid(record)))


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
    return _sdk_data_to_dict(client.get_log_analytics_entity(_record_ocid(record)))


def _fetch_media_workflow(record: Dict[str, Any]) -> Dict[str, Any]:
    ctx = get_enrich_context()
    client = oci_clients.get_media_services_client(ctx, _record_region(record))
    return _sdk_data_to_dict(client.get_media_workflow(_record_ocid(record)))


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
        "DhcpOptions": _fetch_dhcp_options,
        "DHCPOptions": _fetch_dhcp_options,
        "PrivateIp": _fetch_private_ip,
        # Block Storage
        "Volume": _fetch_volume,
        "PublicIp": _fetch_public_ip,
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
        "StreamCdnConfig": _fetch_stream_cdn_config,
        "StreamDistributionChannel": _fetch_stream_distribution_channel,
        "StreamPackagingConfig": _fetch_stream_packaging_config,
        # Security
        "Bastion": _fetch_bastion,
        "Vault": _fetch_vault,
        "Secret": _fetch_secret,
        "CloudGuardTarget": _fetch_cloud_guard_target,
    }

    for resource_type, fetch in mapping.items():
        register_enricher(
            resource_type,
            lambda rt=resource_type, fn=fetch: SDKMetadataEnricher(rt, fn),
        )
