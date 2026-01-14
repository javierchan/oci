from __future__ import annotations

import types

from oci_inventory.auth.providers import AuthContext
from oci_inventory.oci import clients


def test_client_cache_reuses_by_service_and_region(monkeypatch) -> None:
    class _FakeIdentityClient:
        pass

    fake_oci = types.SimpleNamespace(identity=types.SimpleNamespace(IdentityClient=_FakeIdentityClient))
    monkeypatch.setattr(clients, "oci", fake_oci)
    monkeypatch.delenv("OCI_INV_DISABLE_CLIENT_CACHE", raising=False)

    calls = []

    def _fake_make_client(client_cls, ctx, region=None):
        calls.append((client_cls, region))
        return object()

    monkeypatch.setattr(clients, "make_client", _fake_make_client)
    clients.clear_client_cache()

    ctx = AuthContext(
        method="config",
        config_dict={"tenancy": "ocid1.tenancy.oc1..test", "user": "user", "fingerprint": "fp"},
        signer=None,
        profile="DEFAULT",
        tenancy_ocid="ocid1.tenancy.oc1..test",
    )

    c1 = clients.get_identity_client(ctx, region="us-ashburn-1")
    c2 = clients.get_identity_client(ctx, region="us-ashburn-1")
    c3 = clients.get_identity_client(ctx, region="us-phoenix-1")

    assert c1 is c2
    assert c1 is not c3
    assert len(calls) == 2
