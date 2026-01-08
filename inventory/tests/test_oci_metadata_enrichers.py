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
            tenancy_ocid=None,
        )
    )


def test_public_ip_enricher_calls_vcn_client(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _VcnClient:
        def get_public_ip(self, ocid: str) -> Any:
            assert ocid == "ocid1.publicip.oc1..aaaa"
            return SimpleNamespace(data={"id": ocid, "lifecycle_state": "AVAILABLE"})

    monkeypatch.setattr(meta.oci_clients, "get_virtual_network_client", lambda ctx, region: _VcnClient())

    enricher = get_enricher_for("PublicIp")
    res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.publicip.oc1..aaaa"})
    assert res.enrichStatus == "OK"
    assert res.details["metadata"]["id"] == "ocid1.publicip.oc1..aaaa"


def test_policy_enricher_calls_identity_client(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _IdentityClient:
        def get_policy(self, ocid: str) -> Any:
            assert ocid == "ocid1.policy.oc1..aaaa"
            return SimpleNamespace(data={"id": ocid, "statements": ["allow group X to read all-resources"]})

    monkeypatch.setattr(meta.oci_clients, "get_identity_client", lambda ctx, region=None: _IdentityClient())

    enricher = get_enricher_for("Policy")
    res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.policy.oc1..aaaa"})
    assert res.enrichStatus == "OK"
    assert res.details["metadata"]["id"] == "ocid1.policy.oc1..aaaa"


def test_dns_zone_enricher_calls_dns_client(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    class _DnsClient:
        def get_zone(self, ocid: str) -> Any:
            assert ocid == "ocid1.dnszone.oc1..aaaa"
            return SimpleNamespace(data={"id": ocid, "name": "example.com"})

    monkeypatch.setattr(meta.oci_clients, "get_dns_client", lambda ctx, region: _DnsClient())

    enricher = get_enricher_for("DnsZone")
    res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.dnszone.oc1..aaaa"})
    assert res.enrichStatus == "OK"
    assert res.details["metadata"]["name"] == "example.com"


def test_customer_dns_zone_aliases_dns_zone(monkeypatch: Any) -> None:
    _set_dummy_ctx()

    calls: Dict[str, int] = {"n": 0}

    class _DnsClient:
        def get_zone(self, ocid: str) -> Any:
            calls["n"] += 1
            return SimpleNamespace(data={"id": ocid})

    monkeypatch.setattr(meta.oci_clients, "get_dns_client", lambda ctx, region: _DnsClient())

    enricher = get_enricher_for("CustomerDnsZone")
    res = enricher.enrich({"region": "mx-queretaro-1", "ocid": "ocid1.dnszone.oc1..bbbb"})
    assert res.enrichStatus == "OK"
    assert calls["n"] == 1
