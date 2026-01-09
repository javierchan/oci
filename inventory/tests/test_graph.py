from __future__ import annotations

import json

from oci_inventory.cli import _coverage_metrics, _validate_outdir_schema
from oci_inventory.export.graph import build_graph, derive_relationships_from_metadata, write_graph, write_mermaid
from oci_inventory.normalize.transform import sort_relationships


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


def test_build_graph_sets_region_on_relationship_edges() -> None:
    inst_id = "ocid1.instance.oc1..inst"
    subnet_id = "ocid1.subnet.oc1..subnet"
    records = [
        {
            "ocid": inst_id,
            "resourceType": "Instance",
            "displayName": "vm-1",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": subnet_id,
            "resourceType": "Subnet",
            "displayName": "sn-1",
            "region": "mx-queretaro-1",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "details": {"metadata": {}},
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]
    rels = [{"source_ocid": inst_id, "relation_type": "IN_SUBNET", "target_ocid": subnet_id}]
    _, edges = build_graph(records, rels)
    rel_edge = next(e for e in edges if e.get("relation_type") == "IN_SUBNET")
    assert rel_edge["region"] == "mx-queretaro-1"


def test_sort_relationships_dedupes_edges() -> None:
    rels = [
        {"source_ocid": "ocid1.a", "relation_type": "IN_VCN", "target_ocid": "ocid1.b"},
        {"source_ocid": "ocid1.a", "relation_type": "IN_VCN", "target_ocid": "ocid1.b"},
    ]
    out = sort_relationships(rels)
    assert len(out) == 1


def test_coverage_metrics_include_type_status_matrix() -> None:
    records = [
        {"resourceType": "Instance", "enrichStatus": "OK"},
        {"resourceType": "Instance", "enrichStatus": "ERROR"},
        {"resourceType": "Subnet", "enrichStatus": "OK"},
    ]
    metrics = _coverage_metrics(records)
    matrix = metrics["counts_by_resource_type_and_status"]
    assert matrix["Instance"]["OK"] == 1
    assert matrix["Instance"]["ERROR"] == 1
    assert matrix["Subnet"]["OK"] == 1


def test_validate_outdir_schema_accepts_minimal_artifacts(tmp_path) -> None:
    outdir = tmp_path
    inv = outdir / "inventory.jsonl"
    rels = outdir / "relationships.jsonl"
    nodes = outdir / "graph_nodes.jsonl"
    edges = outdir / "graph_edges.jsonl"
    summary = outdir / "run_summary.json"

    inv_record = {
        "ocid": "ocid1.instance.oc1..inst",
        "resourceType": "Instance",
        "region": "mx-queretaro-1",
        "collectedAt": "2026-01-08T23:47:48+00:00",
        "enrichStatus": "OK",
        "details": {},
        "relationships": [
            {"source_ocid": "ocid1.instance.oc1..inst", "relation_type": "IN_COMPARTMENT", "target_ocid": "ocid1.compartment.oc1..comp"}
        ],
    }
    inv.write_text(json.dumps(inv_record) + "\n", encoding="utf-8")

    rels.write_text(
        json.dumps(
            {
                "source_ocid": "ocid1.instance.oc1..inst",
                "relation_type": "IN_COMPARTMENT",
                "target_ocid": "ocid1.compartment.oc1..comp",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    node_instance = {
        "nodeId": "ocid1.instance.oc1..inst",
        "nodeType": "Instance",
        "nodeCategory": "compute",
        "name": "vm-1",
        "region": "mx-queretaro-1",
        "compartmentId": "ocid1.compartment.oc1..comp",
        "metadata": {},
        "tags": {"definedTags": {}, "freeformTags": {}},
        "enrichStatus": "OK",
        "enrichError": None,
    }
    node_comp = {
        "nodeId": "ocid1.compartment.oc1..comp",
        "nodeType": "Compartment",
        "nodeCategory": "compartment",
        "name": "ocid1.compartment.oc1..comp",
        "region": None,
        "compartmentId": None,
        "metadata": {},
        "tags": {"definedTags": {}, "freeformTags": {}},
        "enrichStatus": None,
        "enrichError": None,
    }
    nodes.write_text(json.dumps(node_instance) + "\n" + json.dumps(node_comp) + "\n", encoding="utf-8")

    edge = {
        "source_ocid": "ocid1.instance.oc1..inst",
        "target_ocid": "ocid1.compartment.oc1..comp",
        "relation_type": "IN_COMPARTMENT",
        "source_type": "Instance",
        "target_type": "Compartment",
        "region": "mx-queretaro-1",
    }
    edges.write_text(json.dumps(edge) + "\n", encoding="utf-8")

    summary.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "total_discovered": 1,
                "enriched_ok": 1,
                "not_implemented": 0,
                "errors": 0,
                "counts_by_resource_type": {"Instance": 1},
                "counts_by_enrich_status": {"OK": 1},
                "counts_by_resource_type_and_status": {"Instance": {"OK": 1}},
            }
        ),
        encoding="utf-8",
    )

    result = _validate_outdir_schema(outdir)
    assert result.errors == []
