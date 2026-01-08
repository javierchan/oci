from __future__ import annotations

from oci_inventory.export.diagram_projections import write_diagram_projections
from oci_inventory.export.graph import build_graph


def test_write_diagram_projections_creates_views(tmp_path) -> None:
    records = [
        {
            "ocid": "ocid1.vcn.oc1..vcn",
            "resourceType": "Vcn",
            "displayName": "Prod-VCN",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"cidr_block": "10.0.0.0/16"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": "ocid1.subnet.oc1..subnet",
            "resourceType": "Subnet",
            "displayName": "Public-Subnet-1",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {
                "metadata": {
                    "vcn_id": "ocid1.vcn.oc1..vcn",
                    "cidr_block": "10.0.1.0/24",
                    "prohibit_public_ip_on_vnic": False,
                }
            },
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": "ocid1.instance.oc1..inst",
            "resourceType": "Instance",
            "displayName": "mediaflow-api-01",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"vcn_id": "ocid1.vcn.oc1..vcn", "subnet_id": "ocid1.subnet.oc1..subnet"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]

    nodes, edges = build_graph(records, relationships=[])
    paths = write_diagram_projections(tmp_path, nodes, edges)

    assert (tmp_path / "diagram.tenancy.mmd").exists()
    assert (tmp_path / "diagram.network.prod_vcn.mmd").exists()
    assert (tmp_path / "diagram.consolidated.mmd").exists()

    # Sanity-check Mermaid structure.
    tenancy = (tmp_path / "diagram.tenancy.mmd").read_text(encoding="utf-8")
    assert tenancy.startswith("flowchart")
    assert "subgraph" in tenancy

    assert any(p.name == "diagram.network.prod_vcn.mmd" for p in paths)

    consolidated = (tmp_path / "diagram.consolidated.mmd").read_text(encoding="utf-8")
    assert consolidated.startswith("flowchart")
    assert "subgraph" in consolidated
    assert "TEN_ROOT" in consolidated
