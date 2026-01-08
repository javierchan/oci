from __future__ import annotations

from oci_inventory.export.graph import build_graph, derive_relationships_from_metadata, write_graph, write_mermaid


def test_build_graph_adds_compartment_edges(tmp_path) -> None:
    records = [
        {
            "ocid": "ocid1.instance.oc1..aaa",
            "resourceType": "Instance",
            "displayName": "vm-1",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"shape": "VM.Standard"}},
            "enrichStatus": "OK",
            "enrichError": None,
        }
    ]
    nodes, edges = build_graph(records, [])

    assert len(nodes) == 2
    assert edges[0]["relation_type"] == "IN_COMPARTMENT"

    nodes_path, edges_path = write_graph(tmp_path, nodes, edges)
    assert nodes_path.exists()
    assert edges_path.exists()

    mmd_path = write_mermaid(tmp_path, nodes, edges)
    assert mmd_path.read_text(encoding="utf-8").startswith("graph TD")
    assert mmd_path.name == "diagram_raw.mmd"


def test_derive_relationships_from_metadata_emits_vcn_and_subnet_edges() -> None:
    vcn_id = "ocid1.vcn.oc1..vcn"
    subnet_id = "ocid1.subnet.oc1..subnet"
    rtb_id = "ocid1.routetable.oc1..rtb"

    records = [
        {
            "ocid": vcn_id,
            "resourceType": "Vcn",
            "displayName": "vcn-1",
            "details": {"metadata": {}},
        },
        {
            "ocid": subnet_id,
            "resourceType": "Subnet",
            "displayName": "sn-1",
            "details": {"metadata": {"vcnId": vcn_id, "routeTableId": rtb_id}},
        },
        {
            "ocid": rtb_id,
            "resourceType": "RouteTable",
            "displayName": "rt-1",
            "details": {"metadata": {"vcnId": vcn_id}},
        },
    ]

    rels = derive_relationships_from_metadata(records)
    keys = {(r["source_ocid"], r["relation_type"], r["target_ocid"]) for r in rels}

    assert (subnet_id, "IN_VCN", vcn_id) in keys
    assert (subnet_id, "USES_ROUTE_TABLE", rtb_id) in keys
    assert (rtb_id, "IN_VCN", vcn_id) in keys
