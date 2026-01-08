from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from ..normalize.transform import stable_json_dumps
from ..util.serialization import sanitize_for_json

Node = Dict[str, Any]
Edge = Dict[str, Any]


COMPUTE_TYPES = {
    "Instance",
    "Image",
    "BootVolume",
    "BlockVolume",
    "InstanceConfiguration",
    "InstancePool",
}
NETWORK_TYPES = {
    "Vcn",
    "Subnet",
    "Vnic",
    "NetworkSecurityGroup",
    "SecurityList",
    "RouteTable",
    "InternetGateway",
    "NatGateway",
    "ServiceGateway",
    "DhcpOptions",
}
SECURITY_TYPES = {
    "Bastion",
    "Vault",
    "Secret",
    "CloudGuardTarget",
}


def _node_category(resource_type: str) -> str:
    if resource_type in COMPUTE_TYPES:
        return "compute"
    if resource_type in NETWORK_TYPES:
        return "network"
    if resource_type in SECURITY_TYPES:
        return "security"
    if resource_type == "Compartment":
        return "compartment"
    return "other"


def _node_type(resource_type: str) -> str:
    category = _node_category(resource_type)
    if category in {"compute", "network", "security"}:
        return f"{category}.{resource_type}"
    return resource_type


def _node_label(record: Dict[str, Any]) -> str:
    name = record.get("displayName") or record.get("name")
    if not name:
        name = record.get("resourceType") or record.get("nodeType") or record.get("ocid")
    return str(name)


def _compartment_node(ocid: str) -> Node:
    return {
        "nodeId": ocid,
        "nodeType": "Compartment",
        "nodeCategory": "compartment",
        "name": ocid,
        "region": None,
        "compartmentId": None,
        "metadata": {},
        "tags": {},
        "enrichStatus": "UNKNOWN",
        "enrichError": None,
    }


def _record_to_node(record: Dict[str, Any]) -> Node:
    resource_type = str(record.get("resourceType") or "Unknown")
    details = record.get("details") or {}
    metadata = details.get("metadata") or {}
    tags = {
        "definedTags": record.get("definedTags"),
        "freeformTags": record.get("freeformTags"),
    }
    return {
        "nodeId": str(record.get("ocid") or ""),
        "nodeType": _node_type(resource_type),
        "nodeCategory": _node_category(resource_type),
        "name": _node_label(record),
        "region": record.get("region"),
        "compartmentId": record.get("compartmentId"),
        "metadata": sanitize_for_json(metadata),
        "tags": sanitize_for_json(tags),
        "enrichStatus": record.get("enrichStatus"),
        "enrichError": record.get("enrichError"),
    }


def _edge_key(edge: Edge) -> Tuple[str, str, str]:
    return (
        str(edge.get("source_ocid") or ""),
        str(edge.get("relation_type") or ""),
        str(edge.get("target_ocid") or ""),
    )


def build_graph(
    records: Iterable[Dict[str, Any]],
    relationships: Sequence[Dict[str, str]],
) -> Tuple[List[Node], List[Edge]]:
    nodes_by_id: Dict[str, Node] = {}
    edges: List[Edge] = []

    for rec in records:
        ocid = str(rec.get("ocid") or "")
        if not ocid:
            continue
        node = _record_to_node(rec)
        nodes_by_id[ocid] = node

        comp_id = rec.get("compartmentId")
        if comp_id:
            comp_id = str(comp_id)
            if comp_id not in nodes_by_id:
                nodes_by_id[comp_id] = _compartment_node(comp_id)
            edges.append(
                {
                    "source_ocid": ocid,
                    "target_ocid": comp_id,
                    "relation_type": "IN_COMPARTMENT",
                    "source_type": node.get("nodeType"),
                    "target_type": "Compartment",
                    "region": rec.get("region"),
                }
            )

    for rel in relationships:
        edges.append(
            {
                "source_ocid": rel.get("source_ocid"),
                "target_ocid": rel.get("target_ocid"),
                "relation_type": rel.get("relation_type"),
                "source_type": nodes_by_id.get(rel.get("source_ocid") or "", {}).get("nodeType"),
                "target_type": nodes_by_id.get(rel.get("target_ocid") or "", {}).get("nodeType"),
                "region": None,
            }
        )

    # Deduplicate edges deterministically
    dedup: Dict[Tuple[str, str, str], Edge] = {}
    for edge in edges:
        dedup[_edge_key(edge)] = edge
    edges_out = [dedup[k] for k in sorted(dedup.keys())]

    nodes_out = [nodes_by_id[k] for k in sorted(nodes_by_id.keys())]
    return nodes_out, edges_out


def write_graph(outdir: Path, nodes: List[Node], edges: List[Edge]) -> Tuple[Path, Path]:
    nodes_path = outdir / "graph_nodes.jsonl"
    edges_path = outdir / "graph_edges.jsonl"
    with nodes_path.open("w", encoding="utf-8") as f:
        for node in nodes:
            f.write(stable_json_dumps(node))
            f.write("\n")
    with edges_path.open("w", encoding="utf-8") as f:
        for edge in edges:
            f.write(stable_json_dumps(edge))
            f.write("\n")
    return nodes_path, edges_path


def _mermaid_id(ocid: str) -> str:
    digest = hashlib.sha1(ocid.encode("utf-8")).hexdigest()
    return f"N{digest[:12]}"


def _mermaid_label(node: Node) -> str:
    name = str(node.get("name") or node.get("nodeId") or "")
    node_type = str(node.get("nodeType") or "")
    label = f"{name}\\n{node_type}".strip()
    return label.replace('"', "'")


def write_mermaid(outdir: Path, nodes: List[Node], edges: List[Edge]) -> Path:
    # Raw graph export is intentionally noisy and intended for debugging.
    # Keep it as a separate artifact from any architectural projections.
    path = outdir / "diagram_raw.mmd"
    lines: List[str] = ["graph TD"]
    for node in nodes:
        node_id = _mermaid_id(str(node.get("nodeId") or ""))
        label = _mermaid_label(node)
        lines.append(f'  {node_id}["{label}"]')
    for edge in edges:
        src = _mermaid_id(str(edge.get("source_ocid") or ""))
        tgt = _mermaid_id(str(edge.get("target_ocid") or ""))
        rel = str(edge.get("relation_type") or "")
        if rel:
            lines.append(f"  {src} -->|{rel}| {tgt}")
        else:
            lines.append(f"  {src} --> {tgt}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
