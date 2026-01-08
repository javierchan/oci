from __future__ import annotations

from oci_inventory.export.graph import build_graph, write_graph, write_mermaid


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
