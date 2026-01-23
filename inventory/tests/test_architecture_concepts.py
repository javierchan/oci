from __future__ import annotations

import json

from oci_inventory.export.architecture_concepts import (
    build_workload_concepts,
    build_workload_context,
)
from oci_inventory.export.diagram_projections import (
    _write_architecture_drawio_compartment,
    _write_architecture_drawio_tenancy,
    _write_architecture_drawio_vcn,
    _write_architecture_drawio_workload,
    validate_architecture_diagrams,
)


def test_build_workload_concepts_filters_noise_and_sanitizes_labels() -> None:
    nodes = [
        {
            "nodeId": "ocid1.vcn.oc1..vcn",
            "nodeType": "Vcn",
            "name": "Prod-VCN",
            "compartmentId": "ocid1.compartment.oc1..comp",
        },
        {
            "nodeId": "ocid1.subnet.oc1..subnet",
            "nodeType": "Subnet",
            "name": "Public-Subnet",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "metadata": {"vcn_id": "ocid1.vcn.oc1..vcn"},
        },
        {
            "nodeId": "ocid1.instance.oc1..inst1",
            "nodeType": "Instance",
            "name": "odi-worker-20260123",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "metadata": {"subnet_id": "ocid1.subnet.oc1..subnet"},
        },
        {
            "nodeId": "ocid1.oke.oc1..cluster",
            "nodeType": "ContainerEngineCluster",
            "name": "prod-oke",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "metadata": {"vcn_id": "ocid1.vcn.oc1..vcn"},
        },
        {
            "nodeId": "ocid1.nodepool.oc1..np",
            "nodeType": "NodePool",
            "name": "worker-pool",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "metadata": {"vcn_id": "ocid1.vcn.oc1..vcn"},
        },
        {
            "nodeId": "ocid1.log.oc1..log",
            "nodeType": "Log",
            "name": "app-log",
            "compartmentId": "ocid1.compartment.oc1..comp",
        },
        {
            "nodeId": "ocid1.bucket.oc1..bucket",
            "nodeType": "Bucket",
            "name": "media-bucket",
            "compartmentId": "ocid1.compartment.oc1..comp",
        },
        {
            "nodeId": "ocid1.igw.oc1..igw",
            "nodeType": "InternetGateway",
            "name": "igw-prod",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "metadata": {"vcn_id": "ocid1.vcn.oc1..vcn"},
        },
        {
            "nodeId": "ocid1.bootvolume.oc1..boot",
            "nodeType": "BootVolume",
            "name": "boot-20260123",
            "compartmentId": "ocid1.compartment.oc1..comp",
        },
        {
            "nodeId": "ocid1.dataflowrun.oc1..run",
            "nodeType": "DataFlowRun",
            "name": "plan-job-20260123120000",
            "compartmentId": "ocid1.compartment.oc1..comp",
        },
    ]
    workload_nodes = list(nodes)

    concepts = build_workload_concepts(nodes=nodes, edges=[], workload_nodes=workload_nodes)

    labels = {c.label for c in concepts}
    assert "ODI Compute Nodes" in labels
    assert "OKE Cluster" in labels
    assert "Worker Nodes" in labels
    assert "Observability Suite" in labels
    assert "Object Storage" in labels
    assert "Internet Gateway" in labels

    for concept in concepts:
        assert "(n=" not in concept.label
        assert "ocid1" not in concept.label
        assert all("BootVolume" != t for t in concept.source_types)
        assert all("DataFlowRun" != t for t in concept.source_types)


def test_build_workload_context_reports_vcn_names_by_compartment() -> None:
    nodes = [
        {
            "nodeId": "ocid1.vcn.oc1..vcn",
            "nodeType": "Vcn",
            "name": "Prod-VCN",
            "compartmentId": "ocid1.compartment.oc1..comp",
        },
        {
            "nodeId": "ocid1.instance.oc1..inst1",
            "nodeType": "Instance",
            "name": "app-01",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "metadata": {"vcn_id": "ocid1.vcn.oc1..vcn"},
        },
    ]
    workload_nodes = [nodes[1]]

    context = build_workload_context(nodes=nodes, edges=[], workload_nodes=workload_nodes)

    assert "ocid1.compartment.oc1..comp" in context.vcn_names_by_compartment
    assert "Prod-VCN" in context.vcn_names_by_compartment["ocid1.compartment.oc1..comp"]


def test_drawio_workload_architecture_has_no_counts(tmp_path) -> None:
    nodes = [
        {
            "nodeId": "ocid1.compartment.oc1..comp",
            "nodeType": "Compartment",
            "name": "Prod",
        },
        {
            "nodeId": "ocid1.vcn.oc1..vcn",
            "nodeType": "Vcn",
            "name": "Prod-VCN",
            "compartmentId": "ocid1.compartment.oc1..comp",
        },
        {
            "nodeId": "ocid1.instance.oc1..inst1",
            "nodeType": "Instance",
            "name": "app-01",
            "compartmentId": "ocid1.compartment.oc1..comp",
            "metadata": {"vcn_id": "ocid1.vcn.oc1..vcn"},
        },
    ]
    path = _write_architecture_drawio_workload(
        tmp_path,
        workload="demo",
        nodes=nodes,
        edges=[],
        workload_nodes=[nodes[2]],
    )
    content = path.read_text(encoding="utf-8")
    assert "(n=" not in content
    assert "Compartment:" in content
    assert "VCN:" in content


def test_drawio_tenancy_vcn_compartment_have_no_counts(tmp_path) -> None:
    nodes = [
        {
            "nodeId": "ocid1.compartment.oc1..root",
            "nodeType": "Compartment",
            "name": "TenancyRoot",
        },
        {
            "nodeId": "ocid1.compartment.oc1..app",
            "nodeType": "Compartment",
            "name": "App",
            "compartmentId": "ocid1.compartment.oc1..root",
        },
        {
            "nodeId": "ocid1.vcn.oc1..vcn",
            "nodeType": "Vcn",
            "name": "Prod-VCN",
            "compartmentId": "ocid1.compartment.oc1..app",
        },
        {
            "nodeId": "ocid1.subnet.oc1..subnet",
            "nodeType": "Subnet",
            "name": "Public-Subnet",
            "compartmentId": "ocid1.compartment.oc1..app",
            "metadata": {"vcn_id": "ocid1.vcn.oc1..vcn"},
        },
        {
            "nodeId": "ocid1.instance.oc1..inst1",
            "nodeType": "Instance",
            "name": "app-01",
            "compartmentId": "ocid1.compartment.oc1..app",
            "metadata": {"vcn_id": "ocid1.vcn.oc1..vcn"},
        },
    ]
    tenancy_path = _write_architecture_drawio_tenancy(tmp_path, nodes)
    vcn_path = _write_architecture_drawio_vcn(tmp_path, vcn_name="Prod-VCN", vcn_nodes=nodes)
    comp_path = _write_architecture_drawio_compartment(
        tmp_path,
        compartment_label="Compartment: App",
        comp_nodes=nodes,
        top_n=5,
    )

    for path in (tenancy_path, vcn_path, comp_path):
        content = path.read_text(encoding="utf-8")
        assert "(n=" not in content


def test_validate_architecture_svgs_passes_minimum_rules(tmp_path) -> None:
    arch_dir = tmp_path / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    svg = """<svg>
<text>Tenancy: Demo</text>
<text>Compartment: App</text>
<text>VCN: DemoVCN</text>
<text>Network</text>
<text>App / Compute</text>
<text>Data / Storage</text>
<text>Security</text>
<text>Observability</text>
<text>Other</text>
</svg>
"""
    (arch_dir / "diagram.arch.tenancy.svg").write_text(svg, encoding="utf-8")
    nodes = [
        {"nodeId": "ocid1.compartment.oc1..root", "nodeType": "Compartment", "name": "TenancyRoot"},
        {"nodeId": "ocid1.vcn.oc1..vcn", "nodeType": "Vcn", "name": "DemoVCN"},
    ]
    issues = validate_architecture_diagrams(tmp_path, nodes=nodes, edges=[])
    assert issues == []


def test_validate_architecture_svgs_flags_missing_security_overlay(tmp_path) -> None:
    arch_dir = tmp_path / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    svg = """<svg>
<text>Tenancy: Demo</text>
<text>Compartment: App</text>
<text>VCN: DemoVCN</text>
<text>Network</text>
<text>App / Compute</text>
<text>Data / Storage</text>
<text>Security</text>
<text>Observability</text>
<text>Other</text>
</svg>
"""
    (arch_dir / "diagram.arch.tenancy.svg").write_text(svg, encoding="utf-8")
    nodes = [
        {"nodeId": "ocid1.compartment.oc1..root", "nodeType": "Compartment", "name": "TenancyRoot"},
        {"nodeId": "ocid1.vcn.oc1..vcn", "nodeType": "Vcn", "name": "DemoVCN"},
        {
            "nodeId": "ocid1.policy.oc1..policy",
            "nodeType": "Policy",
            "name": "root-policy",
            "nodeCategory": "iam",
            "compartmentId": "ocid1.compartment.oc1..root",
        },
    ]
    issues = validate_architecture_diagrams(tmp_path, nodes=nodes, edges=[])
    assert any(issue.rule_id == "ARCH_OVERLAY_TENANCY_MISSING" for issue in issues)


def test_cmd_rebuild_creates_diagrams_dir(tmp_path, monkeypatch) -> None:
    from oci_inventory.cli import cmd_rebuild
    from oci_inventory.config import RunConfig
    import oci_inventory.report as report

    monkeypatch.setattr(report, "write_run_report_md", lambda **_: None)
    monkeypatch.setattr(report, "write_cost_report_md", lambda **_: None)

    outdir = tmp_path
    inventory_dir = outdir / "inventory"
    graph_dir = outdir / "graph"
    inventory_dir.mkdir(parents=True, exist_ok=True)
    graph_dir.mkdir(parents=True, exist_ok=True)

    inventory_record = {
        "ocid": "ocid1.instance.oc1..demo",
        "resourceType": "Instance",
        "region": "us-ashburn-1",
        "collectedAt": "2026-01-01T00:00:00Z",
        "enrichStatus": "OK",
        "details": {},
        "relationships": [],
    }
    (inventory_dir / "inventory.jsonl").write_text(
        json.dumps(inventory_record) + "\n",
        encoding="utf-8",
    )
    node = {
        "nodeId": "ocid1.compartment.oc1..root",
        "nodeType": "Compartment",
        "nodeCategory": "identity",
        "name": "TenancyRoot",
        "region": "us-ashburn-1",
        "compartmentId": "",
        "metadata": {},
        "tags": {},
        "enrichStatus": "OK",
        "enrichError": "",
    }
    (graph_dir / "graph_nodes.jsonl").write_text(
        json.dumps(node) + "\n",
        encoding="utf-8",
    )
    (graph_dir / "graph_edges.jsonl").write_text("", encoding="utf-8")

    cfg = RunConfig(
        outdir=outdir,
        diagrams=True,
        architecture_diagrams=False,
        validate_diagrams=False,
        diagram_depth=1,
        cost_report=False,
        genai_summary=False,
    )

    result = cmd_rebuild(cfg)
    assert result == 0
    assert (outdir / "diagrams").is_dir()
    assert (outdir / "diagrams" / "tenancy" / "diagram.tenancy.mmd").is_file()
