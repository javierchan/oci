from __future__ import annotations

import hashlib

from pathlib import Path

from oci_inventory.export.diagram_projections import _render_edge, write_diagram_projections
from oci_inventory.export.graph import build_graph


def _build_graph_lists(
    scratch_dir: Path,
    records: list[dict],
    relationships: list[dict],
) -> tuple[list[dict], list[dict]]:
    graph = build_graph(records, relationships, scratch_dir=scratch_dir)
    nodes = graph.materialize_nodes()
    edges = graph.materialize_edges(filtered=True)
    graph.close()
    return nodes, edges


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

    nodes, edges = _build_graph_lists(tmp_path, records, [])
    paths = write_diagram_projections(tmp_path, nodes, edges)

    assert (tmp_path / "diagram.tenancy.mmd").exists()
    assert (tmp_path / "diagram.network.prod_vcn.mmd").exists()
    assert (tmp_path / "diagram.consolidated.architecture.mmd").exists()
    assert (tmp_path / "diagram.consolidated.flowchart.mmd").exists()

    # Sanity-check Mermaid structure.
    tenancy = (tmp_path / "diagram.tenancy.mmd").read_text(encoding="utf-8")
    assert tenancy.startswith("flowchart LR")
    assert "subgraph" in tenancy
    assert "Functional Overlays" not in tenancy
    assert "IN_COMPARTMENT" not in tenancy
    assert "Region: mx-queretaro-1" in tenancy
    assert "Instances (n=1)" in tenancy
    tenancy_lines = [line.strip() for line in tenancy.splitlines()]
    assert sum(1 for line in tenancy_lines if line.startswith("subgraph ")) == sum(
        1 for line in tenancy_lines if line == "end"
    )

    assert any(p.name == "diagram.network.prod_vcn.mmd" for p in paths)

    consolidated = (tmp_path / "diagram.consolidated.architecture.mmd").read_text(encoding="utf-8")
    assert consolidated.startswith("architecture-beta")
    assert "group comp_" in consolidated
    assert "service" in consolidated
    assert "|IN_COMPARTMENT|" not in consolidated
    assert "-.->" not in consolidated
    for line in consolidated.splitlines():
        if "-->" in line or "<--" in line:
            assert ":" in line

    flowchart = (tmp_path / "diagram.consolidated.flowchart.mmd").read_text(encoding="utf-8")
    assert flowchart.startswith("flowchart TD")


def test_consolidated_subnet_group_id_scoped_by_vcn(tmp_path) -> None:
    vcn_id = "ocid1.vcn.oc1..vcn"
    subnet_id = "ocid1.subnet.oc1..subnet"
    comp_id = "ocid1.compartment.oc1..comp"
    records = [
        {
            "ocid": vcn_id,
            "resourceType": "Vcn",
            "displayName": "Prod-VCN",
            "region": "mx-queretaro-1",
            "compartmentId": comp_id,
            "details": {"metadata": {"cidr_block": "10.0.0.0/16"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": subnet_id,
            "resourceType": "Subnet",
            "displayName": "Public-Subnet-1",
            "region": "mx-queretaro-1",
            "compartmentId": comp_id,
            "details": {"metadata": {"vcn_id": vcn_id, "cidr_block": "10.0.1.0/24"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]

    nodes, edges = _build_graph_lists(tmp_path, records, [])
    write_diagram_projections(tmp_path, nodes, edges)

    consolidated = (tmp_path / "diagram.consolidated.architecture.mmd").read_text(encoding="utf-8")
    digest = hashlib.sha1(f"{comp_id}:{vcn_id}:{subnet_id}".encode("utf-8")).hexdigest()[:10]
    assert f"group subnet_{digest}" in consolidated


def test_consolidated_architecture_dedupes_vcn_groups(tmp_path) -> None:
    vcn_id = "ocid1.vcn.oc1..vcn"
    records = [
        {
            "ocid": vcn_id,
            "resourceType": "Vcn",
            "displayName": "Shared-VCN",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp-a",
            "details": {"metadata": {"cidr_block": "10.0.0.0/16"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": "ocid1.instance.oc1..inst",
            "resourceType": "Instance",
            "displayName": "consumer",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp-b",
            "details": {"metadata": {"vcn_id": vcn_id}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]

    nodes, edges = _build_graph_lists(tmp_path, records, [])
    write_diagram_projections(tmp_path, nodes, edges)

    consolidated = (tmp_path / "diagram.consolidated.architecture.mmd").read_text(encoding="utf-8")
    digest = hashlib.sha1(vcn_id.encode("utf-8")).hexdigest()[:10]
    assert consolidated.count(f"group vcn_{digest}") == 1


def test_consolidated_flowchart_depth_excludes_edges(tmp_path) -> None:
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
        }
    ]

    nodes, edges = _build_graph_lists(tmp_path, records, [])
    write_diagram_projections(tmp_path, nodes, edges, diagram_depth=1)

    consolidated = (tmp_path / "diagram.consolidated.flowchart.mmd").read_text(encoding="utf-8")
    assert consolidated.startswith("flowchart TD")
    assert "-->" not in consolidated


def test_consolidated_flowchart_auto_reduces_depth_when_too_large(tmp_path, monkeypatch) -> None:
    from oci_inventory.export import diagram_projections

    monkeypatch.setattr(diagram_projections, "MAX_MERMAID_TEXT_CHARS", 10)
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
        }
    ]

    nodes, edges = _build_graph_lists(tmp_path, records, [])
    write_diagram_projections(tmp_path, nodes, edges, diagram_depth=3)

    flowchart = (tmp_path / "diagram.consolidated.flowchart.mmd").read_text(encoding="utf-8")
    assert "NOTE: consolidated depth reduced" in flowchart


def test_consolidated_architecture_splits_before_depth_reduction(tmp_path, monkeypatch) -> None:
    from oci_inventory.export import diagram_projections

    monkeypatch.setattr(diagram_projections, "MAX_MERMAID_TEXT_CHARS", 10)
    records = [
        {
            "ocid": "ocid1.vcn.oc1..vcn1",
            "resourceType": "Vcn",
            "displayName": "VCN-ASH",
            "region": "us-ashburn-1",
            "compartmentId": "ocid1.compartment.oc1..comp1",
            "details": {"metadata": {"cidr_block": "10.0.0.0/16"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": "ocid1.vcn.oc1..vcn2",
            "resourceType": "Vcn",
            "displayName": "VCN-PHX",
            "region": "us-phoenix-1",
            "compartmentId": "ocid1.compartment.oc1..comp2",
            "details": {"metadata": {"cidr_block": "10.1.0.0/16"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]

    nodes, edges = _build_graph_lists(tmp_path, records, [])
    write_diagram_projections(tmp_path, nodes, edges, diagram_depth=3)

    consolidated = (tmp_path / "diagram.consolidated.architecture.mmd").read_text(encoding="utf-8")
    assert "NOTE: Consolidated diagram split by region" in consolidated
    part_paths = sorted(tmp_path.glob("diagram.consolidated.architecture.region.*.mmd"))
    assert len(part_paths) == 2
    for part_path in part_paths:
        part_text = part_path.read_text(encoding="utf-8")
        assert "Depth reduced from 3 to 1" in part_text


def test_consolidated_architecture_depth2_aggregates_network_attached(tmp_path) -> None:
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
            "details": {"metadata": {"vcn_id": "ocid1.vcn.oc1..vcn", "cidr_block": "10.0.1.0/24"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": "ocid1.instance.oc1..inst1",
            "resourceType": "Instance",
            "displayName": "edge-service-1",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"vcn_id": "ocid1.vcn.oc1..vcn", "subnet_id": "ocid1.subnet.oc1..subnet"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": "ocid1.instance.oc1..inst2",
            "resourceType": "Instance",
            "displayName": "edge-service-2",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"vcn_id": "ocid1.vcn.oc1..vcn", "subnet_id": "ocid1.subnet.oc1..subnet"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": "ocid1.bucket.oc1..bucket",
            "resourceType": "Bucket",
            "displayName": "object-store",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]

    nodes, edges = _build_graph_lists(tmp_path, records, [])
    write_diagram_projections(tmp_path, nodes, edges, diagram_depth=2)

    consolidated = (tmp_path / "diagram.consolidated.architecture.mmd").read_text(encoding="utf-8")
    assert "edge-service-1" not in consolidated
    assert "edge-service-2" not in consolidated
    assert "Out-of-VCN Services" not in consolidated
    assert "Bucket" not in consolidated


def test_network_view_uses_relationship_edges_for_attachments(tmp_path) -> None:
    vcn_id = "ocid1.vcn.oc1..edge"
    subnet_id = "ocid1.subnet.oc1..edge"
    rtb_id = "ocid1.routetable.oc1..edge"
    drg_id = "ocid1.drg.oc1..edge"

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
        {
            "ocid": drg_id,
            "resourceType": "Drg",
            "displayName": "edge-drg",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"vcn_id": vcn_id}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]

    relationships = [
        {"source_ocid": subnet_id, "relation_type": "IN_VCN", "target_ocid": vcn_id},
        {"source_ocid": subnet_id, "relation_type": "USES_ROUTE_TABLE", "target_ocid": rtb_id},
        {"source_ocid": rtb_id, "relation_type": "IN_VCN", "target_ocid": vcn_id},
        {"source_ocid": drg_id, "relation_type": "IN_VCN", "target_ocid": vcn_id},
    ]

    nodes, edges = _build_graph_lists(tmp_path, records, list(relationships))
    write_diagram_projections(tmp_path, nodes, edges)

    diagram = (tmp_path / "diagram.network.edge_vcn.mmd").read_text(encoding="utf-8")
    assert "Subnet: Public-Subnet-1" in diagram
    assert "USES_ROUTE_TABLE" in diagram
    assert "Customer Network" in diagram


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

    nodes, edges = _build_graph_lists(tmp_path, records, [])
    write_diagram_projections(tmp_path, nodes, edges)

    consolidated = (tmp_path / "diagram.consolidated.architecture.mmd").read_text(encoding="utf-8")
    assert "edge service 1 Instance" in consolidated


def test_render_edge_sanitizes_label() -> None:
    line = _render_edge("A", "B", 'bad|label (test) [x]<y>')
    assert "|bad label test xy|" in line
    assert "(" not in line
    assert "|" in line


def test_write_diagram_projections_skips_large_views(tmp_path, monkeypatch) -> None:
    from oci_inventory.export import diagram_projections

    monkeypatch.setattr(diagram_projections, "MAX_MERMAID_TEXT_CHARS", 10)
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
            "ocid": "ocid1.instance.oc1..inst",
            "resourceType": "Instance",
            "displayName": "mediaflow-api-01",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"vcn_id": "ocid1.vcn.oc1..vcn"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]

    nodes, edges = _build_graph_lists(tmp_path, records, [])
    paths = write_diagram_projections(tmp_path, nodes, edges)

    assert (tmp_path / "diagram.tenancy.mmd").exists()
    assert (tmp_path / "diagram.consolidated.architecture.mmd").exists()
    assert not any(p.name.startswith("diagram.network.") for p in paths)
    assert not any(p.name.startswith("diagram.workload.") for p in paths)
