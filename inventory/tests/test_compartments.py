from __future__ import annotations

import types

from oci_inventory.oci import compartments as comp_mod


class DummyIdentity:
    def __init__(self) -> None:
        self.calls = []

    def get_tenancy(self, tenancy):
        return types.SimpleNamespace(data=types.SimpleNamespace(id=tenancy, name="Root"))

    def list_compartments(
        self,
        tenancy,
        compartment_id_in_subtree=True,
        access_level="ANY",
        page=None,
        limit=1000,
    ):
        self.calls.append(page)
        if page is None:
            data = [
                types.SimpleNamespace(id="ocid2", name="B"),
                types.SimpleNamespace(id="ocid3", name="A"),
            ]
            headers = {"opc-next-page": "p2"}
        else:
            data = [
                types.SimpleNamespace(id="ocid4", name="A"),
                types.SimpleNamespace(id="ocid2", name="B"),
            ]
            headers = {}
        return types.SimpleNamespace(data=data, headers=headers)


def test_list_compartments_paginates_and_sorts(monkeypatch) -> None:
    identity = DummyIdentity()
    monkeypatch.setattr(comp_mod, "get_identity_client", lambda ctx: identity)

    results = comp_mod.list_compartments(ctx=object(), tenancy_ocid="ocid1.tenancy")

    assert results == [
        {"ocid": "ocid3", "name": "A"},
        {"ocid": "ocid4", "name": "A"},
        {"ocid": "ocid2", "name": "B"},
        {"ocid": "ocid1.tenancy", "name": "Root"},
    ]
    assert identity.calls == [None, "p2"]
