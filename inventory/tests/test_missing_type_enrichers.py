from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict

import oci_inventory.enrich.oci_metadata as meta
from oci_inventory.auth.providers import AuthContext
from oci_inventory.enrich import get_enricher_for, set_enrich_context


def _set_dummy_ctx() -> None:
    set_enrich_context(
        AuthContext(
            method="unit",
            config_dict={},
            signer=None,
            profile=None,
            tenancy_ocid="ocid1.tenancy.oc1..aaaa",
        )
    )


def test_dhcpoptions_enricher_accepts_both_casings(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _VcnClient:
        def get_dhcp_options(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_virtual_network_client", lambda ctx, region: _VcnClient())

    for rtype in ("DHCPOptions", "DhcpOptions"):
        enricher = get_enricher_for(rtype)
        res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.dhcpoptions.oc1..aaaa"})
        assert res.enrichStatus == "OK"


def test_volume_enricher(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _BsClient:
        def get_volume(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_blockstorage_client", lambda ctx, region: _BsClient())

    enricher = get_enricher_for("Volume")
    res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.volume.oc1..aaaa"})
    assert res.enrichStatus == "OK"
    assert res.details["metadata"]["id"] == "ocid1.volume.oc1..aaaa"


def test_private_ip_enricher(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _VcnClient:
        def get_private_ip(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_virtual_network_client", lambda ctx, region: _VcnClient())

    enricher = get_enricher_for("PrivateIp")
    res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.privateip.oc1..aaaa"})
    assert res.enrichStatus == "OK"


def test_dns_resolver_and_view_enrichers(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _DnsClient:
        def get_resolver(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "resolver"})

        def get_view(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "view"})

    monkeypatch.setattr(meta.oci_clients, "get_dns_client", lambda ctx, region: _DnsClient())

    r = get_enricher_for("DnsResolver").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.dnsresolver.oc1..aaaa"})
    v = get_enricher_for("DnsView").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.dnsview.oc1..bbbb"})
    assert r.enrichStatus == "OK"
    assert v.enrichStatus == "OK"


def test_bucket_enricher_uses_namespace_and_display_name(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _ObjClient:
        def get_namespace(self) -> Any:
            return SimpleNamespace(data="myns")

        def get_bucket(self, namespace_name: str, bucket_name: str) -> Any:
            assert namespace_name == "myns"
            assert bucket_name == "my-bucket"
            return SimpleNamespace(data={"namespace": namespace_name, "name": bucket_name})

    monkeypatch.setattr(meta.oci_clients, "get_object_storage_client", lambda ctx, region: _ObjClient())

    enricher = get_enricher_for("Bucket")
    res = enricher.enrich({"region": "mx-queretaro-1", "displayName": "my-bucket"})
    assert res.enrichStatus == "OK"
    assert res.details["metadata"]["name"] == "my-bucket"


def test_log_group_enricher(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _LogClient:
        def get_log_group(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_logging_management_client", lambda ctx, region: _LogClient())

    enricher = get_enricher_for("LogGroup")
    res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.loggroup.oc1..aaaa"})
    assert res.enrichStatus == "OK"


def test_log_analytics_entity_enricher(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _LaClient:
        def list_namespaces(self, compartment_id: str) -> Any:
            assert compartment_id == "ocid1.tenancy.oc1..aaaa"
            return SimpleNamespace(data=SimpleNamespace(items=[SimpleNamespace(namespace_name="myns")]))

        def get_log_analytics_entity(self, namespace_name: str, log_analytics_entity_id: str) -> Any:
            assert namespace_name == "myns"
            return SimpleNamespace(data={"id": log_analytics_entity_id, "namespace": namespace_name})

    monkeypatch.setattr(meta.oci_clients, "get_log_analytics_client", lambda ctx, region: _LaClient())

    enricher = get_enricher_for("LogAnalyticsEntity")
    res = enricher.enrich(
        {
            "region": "mx-queretaro-1",
            "ocid": "ocid1.loganalyticsentity.oc1..aaaa",
            "compartmentId": "ocid1.compartment.oc1..aaaa",
        }
    )
    assert res.enrichStatus == "OK"


def test_media_services_enrichers(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _MediaClient:
        def get_media_workflow(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "workflow"})

        def get_media_asset(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "asset"})

        def get_stream_cdn_config(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "cdn"})

        def get_stream_distribution_channel(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "dist"})

        def get_stream_packaging_config(self, ocid: str) -> Any:
            return SimpleNamespace(data={"id": ocid, "kind": "pkg"})

    monkeypatch.setattr(meta.oci_clients, "get_media_services_client", lambda ctx, region: _MediaClient())

    assert get_enricher_for("MediaWorkflow").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.mediaworkflow.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("MediaAsset").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.mediaasset.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("StreamCdnConfig").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.streamcdnconfig.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("StreamDistributionChannel").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.streamdistributionchannel.oc1..aaaa"}).enrichStatus == "OK"
    assert get_enricher_for("StreamPackagingConfig").enrich({"region": "mx-queretaro-1", "ocid": "ocid1.streampackagingconfig.oc1..aaaa"}).enrichStatus == "OK"
