from __future__ import annotations

from oci_inventory.export.diagram_projections import _render_edge, write_diagram_projections
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
    assert consolidated.startswith("architecture-beta")
    assert "group network" in consolidated
    assert "group app" in consolidated


def test_network_view_uses_relationship_edges_for_attachments(tmp_path) -> None:
    vcn_id = "ocid1.vcn.oc1..edge"
    subnet_id = "ocid1.subnet.oc1..edge"
    rtb_id = "ocid1.routetable.oc1..edge"

    records = [
        {
            "ocid": vcn_id,
            "resourceType": "Vcn",
            "displayName": "Edge-VCN",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"cidr_block": "10.0.0.0/16"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": subnet_id,
            "resourceType": "Subnet",
            "displayName": "Public-Subnet-1",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"cidr_block": "10.0.1.0/24"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": rtb_id,
            "resourceType": "RouteTable",
            "displayName": "rt-1",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]

    relationships = [
        {"source_ocid": subnet_id, "relation_type": "IN_VCN", "target_ocid": vcn_id},
        {"source_ocid": subnet_id, "relation_type": "USES_ROUTE_TABLE", "target_ocid": rtb_id},
        {"source_ocid": rtb_id, "relation_type": "IN_VCN", "target_ocid": vcn_id},
    ]

    nodes, edges = build_graph(records, relationships)
    write_diagram_projections(tmp_path, nodes, edges)

    diagram = (tmp_path / "diagram.network.edge_vcn.mmd").read_text(encoding="utf-8")
    assert "Subnet: Public-Subnet-1" in diagram
    assert "USES_ROUTE_TABLE" in diagram


def test_consolidated_defines_workload_anchor_nodes(tmp_path) -> None:
    records = [
        {
            "ocid": "ocid1.instance.oc1..edge1",
            "resourceType": "Instance",
            "displayName": "edge-service-1",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": "ocid1.instance.oc1..edge2",
            "resourceType": "Instance",
            "displayName": "edge-service-2",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": "ocid1.instance.oc1..edge3",
            "resourceType": "Instance",
            "displayName": "edge-service-3",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]

    nodes, edges = build_graph(records, relationships=[])
    write_diagram_projections(tmp_path, nodes, edges)

    consolidated = (tmp_path / "diagram.consolidated.mmd").read_text(encoding="utf-8")
    assert "service WL_edge_ROOT(server)[Workload edge] in workloads" in consolidated


def test_render_edge_sanitizes_label() -> None:
    line = _render_edge("A", "B", 'bad|label (test) [x]<y>')
    assert "|bad label test xy|" in line
    assert "(" not in line
    assert "|" in line
