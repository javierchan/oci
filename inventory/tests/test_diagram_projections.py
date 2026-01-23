from __future__ import annotations

from pathlib import Path

from oci_inventory.export.diagram_projections import (
    _render_edge,
    _semantic_id_key,
    _slugify,
    write_diagram_projections,
)
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
    assert (tmp_path / "diagram.consolidated.flowchart.mmd").exists()

    # Sanity-check Mermaid structure.
    tenancy = (tmp_path / "diagram.tenancy.mmd").read_text(encoding="utf-8")
    assert "flowchart LR" in tenancy.splitlines()[1]
    assert "%% Scope: tenancy" in tenancy
    assert "%% View: overview" in tenancy
    assert "subgraph" in tenancy
    assert "Functional Overlays" not in tenancy
    assert "IN_COMPARTMENT" not in tenancy
    assert "Region: mx-queretaro-1" in tenancy
    assert "Top Compartments" in tenancy
    assert "Top VCNs" in tenancy
    tenancy_lines = [line.strip() for line in tenancy.splitlines()]
    assert sum(1 for line in tenancy_lines if line.startswith("subgraph ")) == sum(
        1 for line in tenancy_lines if line == "end"
    )

    assert any(p.name == "diagram.network.prod_vcn.mmd" for p in paths)

    network = (tmp_path / "diagram.network.prod_vcn.mmd").read_text(encoding="utf-8")
    assert "%% Scope: vcn:Prod-VCN" in network
    assert "%% View: full-detail" in network

    flowchart = (tmp_path / "diagram.consolidated.flowchart.mmd").read_text(encoding="utf-8")
    assert any(line.strip() == "flowchart TD" for line in flowchart.splitlines())
    assert "%% Scope: tenancy" in flowchart
    assert "%% View: overview" in flowchart


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
    assert "flowchart TD" in consolidated.splitlines()[1]
    assert "-->" not in consolidated


def test_consolidated_flowchart_splits_by_vcn_when_too_large(tmp_path, monkeypatch) -> None:
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
    assert "Consolidated diagram split; see split outputs." in flowchart
    assert "diagram.consolidated.flowchart.index.mmd" in flowchart
    part_paths = sorted(tmp_path.glob("diagram.consolidated.flowchart.vcn.*.mmd"))
    assert len(part_paths) == 2


def test_diagram_guideline_checks_flag_ocid_labels(tmp_path) -> None:
    records = [
        {
            "ocid": "ocid1.vcn.oc1..vcn",
            "resourceType": "Vcn",
            "displayName": "team-ocid1.test-vcn",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"cidr_block": "10.0.0.0/16"}},
            "enrichStatus": "OK",
            "enrichError": None,
        }
    ]

    nodes, edges = _build_graph_lists(tmp_path, records, [])
    summary: dict = {}
    write_diagram_projections(tmp_path, nodes, edges, summary=summary)

    violations = summary.get("violations") or []
    assert any(v.get("rule") == "no_ocids_in_labels" for v in violations)


def test_workload_diagram_includes_scope_view_comments(tmp_path) -> None:
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
            "ocid": "ocid1.instance.oc1..inst1",
            "resourceType": "Instance",
            "displayName": "demo-app-1",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"vcn_id": "ocid1.vcn.oc1..vcn", "subnet_id": "ocid1.subnet.oc1..subnet"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": "ocid1.instance.oc1..inst2",
            "resourceType": "Instance",
            "displayName": "demo-app-2",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"vcn_id": "ocid1.vcn.oc1..vcn", "subnet_id": "ocid1.subnet.oc1..subnet"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": "ocid1.instance.oc1..inst3",
            "resourceType": "Instance",
            "displayName": "demo-app-3",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {"vcn_id": "ocid1.vcn.oc1..vcn", "subnet_id": "ocid1.subnet.oc1..subnet"}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]

    nodes, edges = _build_graph_lists(tmp_path, records, [])
    write_diagram_projections(tmp_path, nodes, edges)

    workload_path = tmp_path / "diagram.workload.demo.mmd"
    assert workload_path.exists()
    workload = workload_path.read_text(encoding="utf-8")
    assert "%% Scope: workload:demo" in workload
    assert "%% View: full-detail" in workload




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
    assert (tmp_path / "diagram.consolidated.flowchart.mmd").exists()
    assert not any(p.name.startswith("diagram.network.") for p in paths)
    assert not any(p.name.startswith("diagram.workload.") for p in paths)
