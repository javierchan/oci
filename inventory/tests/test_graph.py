from __future__ import annotations

import json

from oci_inventory.cli import OUT_SCHEMA_VERSION, _coverage_metrics, _validate_outdir_schema
from oci_inventory.export.diagram_projections import write_diagram_projections
from oci_inventory.export.graph import (
    build_graph,
    derive_relationships_from_metadata,
    filter_edges_with_nodes,
    write_graph,
    write_mermaid,
)
from oci_inventory.export.jsonl import write_jsonl
from oci_inventory.normalize.schema import resolve_output_paths
from oci_inventory.normalize.transform import sort_relationships, stable_json_dumps


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


def test_filter_edges_with_nodes_drops_missing_targets() -> None:
    nodes = [
        {"nodeId": "ocid1.a", "nodeType": "Test", "nodeCategory": "other"},
        {"nodeId": "ocid1.b", "nodeType": "Test", "nodeCategory": "other"},
    ]
    edges = [
        {"source_ocid": "ocid1.a", "target_ocid": "ocid1.b", "relation_type": "REL"},
        {"source_ocid": "ocid1.a", "target_ocid": "ocid1.missing", "relation_type": "REL"},
    ]

    filtered, dropped = filter_edges_with_nodes(nodes, edges)

    assert dropped == 1
    assert len(filtered) == 1
    assert filtered[0]["target_ocid"] == "ocid1.b"


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


def test_derive_relationships_from_metadata_emits_security_and_firewall_edges() -> None:
    vcn_id = "ocid1.vcn.oc1..vcn"
    subnet_id = "ocid1.subnet.oc1..subnet"
    rtb_id = "ocid1.routetable.oc1..rtb"
    sl_id = "ocid1.securitylist.oc1..sl"
    nsg_id = "ocid1.nsg.oc1..nsg"
    vnic_id = "ocid1.vnic.oc1..vnic"
    firewall_id = "ocid1.networkfirewall.oc1..fw"

    records = [
        {"ocid": vcn_id, "resourceType": "Vcn", "details": {"metadata": {}}},
        {
            "ocid": subnet_id,
            "resourceType": "Subnet",
            "details": {"metadata": {"vcnId": vcn_id, "routeTableId": rtb_id, "securityListIds": [sl_id]}},
        },
        {"ocid": rtb_id, "resourceType": "RouteTable", "details": {"metadata": {"vcnId": vcn_id}}},
        {"ocid": sl_id, "resourceType": "SecurityList", "details": {"metadata": {"vcnId": vcn_id}}},
        {"ocid": nsg_id, "resourceType": "NetworkSecurityGroup", "details": {"metadata": {"vcnId": vcn_id}}},
        {"ocid": vnic_id, "resourceType": "Vnic", "details": {"metadata": {"subnetId": subnet_id, "nsgIds": [nsg_id]}}},
        {"ocid": firewall_id, "resourceType": "NetworkFirewall", "details": {"metadata": {"subnetId": subnet_id}}},
    ]

    rels = derive_relationships_from_metadata(records)
    keys = {(r["source_ocid"], r["relation_type"], r["target_ocid"]) for r in rels}

    assert (subnet_id, "USES_ROUTE_TABLE", rtb_id) in keys
    assert (subnet_id, "USES_SECURITY_LIST", sl_id) in keys
    assert (vnic_id, "USES_NSG", nsg_id) in keys
    assert (firewall_id, "PROTECTS_VNIC", vnic_id) in keys


def test_derive_relationships_from_metadata_emits_drg_attachment_edges() -> None:
    vcn_id = "ocid1.vcn.oc1..vcn"
    drg_id = "ocid1.drg.oc1..drg"
    attach_id = "ocid1.drgattachment.oc1..att"
    ipsec_id = "ocid1.ipsec.oc1..ipsec"

    records = [
        {"ocid": vcn_id, "resourceType": "Vcn", "details": {"metadata": {}}},
        {"ocid": drg_id, "resourceType": "Drg", "details": {"metadata": {}}},
        {
            "ocid": attach_id,
            "resourceType": "DrgAttachment",
            "details": {"metadata": {"drgId": drg_id, "vcnId": vcn_id}},
        },
        {"ocid": ipsec_id, "resourceType": "IPSecConnection", "details": {"metadata": {"drgId": drg_id}}},
    ]

    rels = derive_relationships_from_metadata(records)
    keys = {(r["source_ocid"], r["relation_type"], r["target_ocid"]) for r in rels}

    assert (attach_id, "ATTACHED_TO_DRG", drg_id) in keys
    assert (attach_id, "ATTACHED_TO_VCN", vcn_id) in keys
    assert (drg_id, "IN_VCN", vcn_id) in keys
    assert (ipsec_id, "USES_DRG", drg_id) in keys
    assert (ipsec_id, "IN_VCN", vcn_id) in keys


def test_derive_relationships_from_metadata_emits_dhcp_and_public_ip_edges() -> None:
    vcn_id = "ocid1.vcn.oc1..vcn"
    subnet_id = "ocid1.subnet.oc1..subnet"
    dhcp_id = "ocid1.dhcpoptions.oc1..dhcp"
    nat_id = "ocid1.natgateway.oc1..nat"
    public_ip_id = "ocid1.publicip.oc1..pub"

    records = [
        {"ocid": vcn_id, "resourceType": "Vcn", "details": {"metadata": {}}},
        {"ocid": dhcp_id, "resourceType": "DhcpOptions", "details": {"metadata": {}}},
        {"ocid": nat_id, "resourceType": "NatGateway", "details": {"metadata": {"vcnId": vcn_id}}},
        {
            "ocid": subnet_id,
            "resourceType": "Subnet",
            "details": {"metadata": {"vcnId": vcn_id, "dhcpOptionsId": dhcp_id}},
        },
        {"ocid": public_ip_id, "resourceType": "PublicIp", "details": {"metadata": {"assignedEntityId": nat_id}}},
    ]

    rels = derive_relationships_from_metadata(records)
    keys = {(r["source_ocid"], r["relation_type"], r["target_ocid"]) for r in rels}

    assert (subnet_id, "USES_DHCP_OPTIONS", dhcp_id) in keys
    assert (public_ip_id, "ASSIGNED_TO", nat_id) in keys


def test_derive_relationships_from_metadata_emits_iam_scope_edges() -> None:
    comp_id = "ocid1.compartment.oc1..comp"
    policy_id = "ocid1.policy.oc1..policy"

    records = [
        {"ocid": policy_id, "resourceType": "Policy", "compartmentId": comp_id, "details": {"metadata": {}}},
    ]

    rels = derive_relationships_from_metadata(records)
    keys = {(r["source_ocid"], r["relation_type"], r["target_ocid"]) for r in rels}

    assert (policy_id, "IAM_SCOPE", comp_id) in keys


def test_derive_relationships_from_metadata_parses_policy_statement_compartment() -> None:
    comp_id = "ocid1.compartment.oc1..comp"
    policy_id = "ocid1.policy.oc1..policy"

    records = [
        {"ocid": comp_id, "resourceType": "Compartment", "displayName": "App"},
        {
            "ocid": policy_id,
            "resourceType": "Policy",
            "details": {"metadata": {"statements": ["Allow group X to read all-resources in compartment App"]}},
        },
    ]

    rels = derive_relationships_from_metadata(records)
    keys = {(r["source_ocid"], r["relation_type"], r["target_ocid"]) for r in rels}

    assert (policy_id, "IAM_SCOPE", comp_id) in keys


def test_derive_relationships_from_metadata_maps_load_balancer_backends() -> None:
    lb_id = "ocid1.loadbalancer.oc1..lb"
    pip_id = "ocid1.privateip.oc1..pip"

    records = [
        {"ocid": pip_id, "resourceType": "PrivateIp", "details": {"metadata": {"ipAddress": "10.0.0.10"}}},
        {
            "ocid": lb_id,
            "resourceType": "LoadBalancer",
            "details": {
                "metadata": {
                    "backendSets": {
                        "bs": {"backends": [{"ipAddress": "10.0.0.10", "port": 80}]},
                    }
                }
            },
        },
    ]

    rels = derive_relationships_from_metadata(records)
    keys = {(r["source_ocid"], r["relation_type"], r["target_ocid"]) for r in rels}

    assert (lb_id, "ROUTES_TO_PRIVATE_IP", pip_id) in keys


def test_derive_relationships_from_metadata_maps_waf_and_firewall_policy() -> None:
    lb_id = "ocid1.loadbalancer.oc1..lb"
    waf_id = "ocid1.webappfirewall.oc1..waf"
    policy_id = "ocid1.networkfirewallpolicy.oc1..pol"
    fw_id = "ocid1.networkfirewall.oc1..fw"

    records = [
        {"ocid": lb_id, "resourceType": "LoadBalancer", "details": {"metadata": {}}},
        {"ocid": policy_id, "resourceType": "NetworkFirewallPolicy", "details": {"metadata": {}}},
        {
            "ocid": waf_id,
            "resourceType": "WebAppFirewall",
            "details": {"metadata": {"loadBalancerId": lb_id}},
        },
        {
            "ocid": fw_id,
            "resourceType": "NetworkFirewall",
            "details": {"metadata": {"networkFirewallPolicyId": policy_id}},
        },
    ]

    rels = derive_relationships_from_metadata(records)
    keys = {(r["source_ocid"], r["relation_type"], r["target_ocid"]) for r in rels}

    assert (waf_id, "PROTECTS_LOAD_BALANCER", lb_id) in keys
    assert (fw_id, "USES_FIREWALL_POLICY", policy_id) in keys


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
    paths = resolve_output_paths(outdir)
    inv = paths.inventory_jsonl
    rels = paths.relationships_jsonl
    nodes = paths.graph_nodes_jsonl
    edges = paths.graph_edges_jsonl
    summary = paths.run_summary_json

    inv.parent.mkdir(parents=True, exist_ok=True)
    rels.parent.mkdir(parents=True, exist_ok=True)
    nodes.parent.mkdir(parents=True, exist_ok=True)
    edges.parent.mkdir(parents=True, exist_ok=True)

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


def test_validate_outdir_schema_allows_missing_graph_when_disabled(tmp_path) -> None:
    outdir = tmp_path
    paths = resolve_output_paths(outdir)
    inv = paths.inventory_jsonl
    rels = paths.relationships_jsonl
    summary = paths.run_summary_json

    inv.parent.mkdir(parents=True, exist_ok=True)
    rels.parent.mkdir(parents=True, exist_ok=True)

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

    result = _validate_outdir_schema(outdir, expect_graph=False)
    assert result.errors == []


def test_offline_pipeline_writes_schema_artifacts(tmp_path) -> None:
    outdir = tmp_path
    collected_at = "2026-01-09T05:35:29+00:00"
    vcn_id = "ocid1.vcn.oc1..vcn"
    inst_id = "ocid1.instance.oc1..inst"
    comp_id = "ocid1.compartment.oc1..comp"

    relationships = [
        {"source_ocid": inst_id, "relation_type": "IN_VCN", "target_ocid": vcn_id},
    ]

    records = [
        {
            "ocid": vcn_id,
            "resourceType": "Vcn",
            "displayName": "vcn-1",
            "region": "mx-queretaro-1",
            "compartmentId": comp_id,
            "details": {"metadata": {"cidr_block": "10.0.0.0/16"}},
            "relationships": [],
            "collectedAt": collected_at,
            "enrichStatus": "OK",
            "enrichError": None,
        },
        {
            "ocid": inst_id,
            "resourceType": "Instance",
            "displayName": "app-1",
            "region": "mx-queretaro-1",
            "compartmentId": comp_id,
            "details": {"metadata": {"vcn_id": vcn_id}},
            "relationships": list(relationships),
            "collectedAt": collected_at,
            "enrichStatus": "OK",
            "enrichError": None,
        },
    ]

    paths = resolve_output_paths(outdir)
    paths.inventory_dir.mkdir(parents=True, exist_ok=True)
    paths.graph_dir.mkdir(parents=True, exist_ok=True)
    paths.diagrams_dir.mkdir(parents=True, exist_ok=True)
    paths.diagrams_raw_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(records, paths.inventory_jsonl)

    rels_path = paths.relationships_jsonl
    rels_path.write_text(
        "\n".join(stable_json_dumps(r) for r in sort_relationships(relationships)) + "\n",
        encoding="utf-8",
    )

    metrics = _coverage_metrics(records)
    summary = dict(metrics)
    summary["schema_version"] = OUT_SCHEMA_VERSION
    paths.run_summary_json.write_text(stable_json_dumps(summary), encoding="utf-8")

    nodes, edges = build_graph(records, relationships)
    write_graph(paths.graph_dir, nodes, edges)
    write_mermaid(paths.diagrams_raw_dir, nodes, edges)
    write_diagram_projections(paths.diagrams_dir, nodes, edges)

    result = _validate_outdir_schema(outdir)
    assert result.errors == []
