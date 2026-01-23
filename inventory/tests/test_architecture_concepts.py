from __future__ import annotations

from oci_inventory.export.architecture_concepts import (
    build_workload_concepts,
    build_workload_context,
)
from oci_inventory.export.diagram_projections import (
    _write_architecture_drawio_compartment,
    _write_architecture_drawio_tenancy,
    _write_architecture_drawio_vcn,
    _write_architecture_drawio_workload,
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
