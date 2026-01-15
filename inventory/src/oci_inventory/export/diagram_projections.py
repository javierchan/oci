from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .graph import Edge, Node
from ..normalize.transform import group_workload_candidates
from ..util.errors import ExportError


_NON_ARCH_LEAF_NODETYPES: Set[str] = set()


_NETWORK_CONTROL_NODETYPES: Set[str] = {
    "network.RouteTable",
    "network.SecurityList",
    "network.NetworkSecurityGroup",
    "network.DhcpOptions",
    "RouteTable",
    "SecurityList",
    "NetworkSecurityGroup",
    "DhcpOptions",
}
_NETWORK_GATEWAY_NODETYPES: Tuple[str, ...] = (
    "InternetGateway",
    "NatGateway",
    "ServiceGateway",
    "Drg",
    "DrgAttachment",
    "VirtualCircuit",
    "IPSecConnection",
    "Cpe",
    "LocalPeeringGateway",
    "RemotePeeringConnection",
    "CrossConnect",
    "CrossConnectGroup",
)

_EDGE_RELATIONS_FOR_PROJECTIONS: Set[str] = set()
_ADMIN_RELATION_TYPES: Set[str] = {"IN_COMPARTMENT"}

_LANE_ORDER: Tuple[str, ...] = (
    "iam",
    "security",
    "network",
    "app",
    "data",
    "observability",
    "other",
)

_LANE_LABELS: Mapping[str, str] = {
    "iam": "IAM",
    "security": "Security",
    "network": "Network",
    "app": "App / Compute",
    "data": "Data / Storage",
    "observability": "Observability",
    "other": "Other",
}


@dataclass(frozen=True)
class _DerivedAttachment:
    resource_ocid: str
    vcn_ocid: Optional[str]
    subnet_ocid: Optional[str]


def _slugify(value: str, *, max_len: int = 48) -> str:
    v = (value or "").strip().lower()
    v = re.sub(r"[^a-z0-9]+", "_", v)
    v = re.sub(r"_+", "_", v).strip("_")
    if not v:
        return "unknown"
    return v[:max_len]


def _short_ocid(ocid: str) -> str:
    o = (ocid or "").strip()
    if o.startswith("ocid1") and len(o) > 18:
        return o[-8:]
    return o


def _get_meta(metadata: Mapping[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in metadata:
            return metadata[k]
        # Accept camelCase vs snake_case interchangeably.
        camel = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), k)
        snake = re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), k)
        if camel in metadata:
            return metadata[camel]
        if snake in metadata:
            return metadata[snake]
    return None


def _node_metadata(node: Node) -> Mapping[str, Any]:
    meta = node.get("metadata")
    return meta if isinstance(meta, Mapping) else {}


def _is_node_type(node: Node, *suffixes: str) -> bool:
    t = str(node.get("nodeType") or "")
    for s in suffixes:
        if t == s or t.endswith("." + s) or t.endswith(s):
            return True
    return False


def _mermaid_id(key: str) -> str:
    # Keep stable across runs while avoiding raw OCIDs in Mermaid node IDs.
    # Reuse the same 12-hex scheme as export.graph.
    import hashlib

    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return f"N{digest[:12]}"


def _friendly_type(node_type: str) -> str:
    t = (node_type or "").strip()
    if "." in t:
        return t.split(".")[-1]
    return t or "Resource"


def _mermaid_label_for(node: Node) -> str:
    name = str(node.get("name") or "").strip()
    node_type = str(node.get("nodeType") or "").strip()

    if not name:
        name = _short_ocid(str(node.get("nodeId") or ""))

    # If a placeholder compartment node was synthesized, avoid printing the full OCID.
    if _is_node_type(node, "Compartment") and name.startswith("ocid1"):
        name = f"Compartment {_short_ocid(name)}"

    if node_type and node_type != "Compartment":
        label = f"{name}<br>{_friendly_type(node_type)}"
    else:
        label = name

    return label.replace('"', "'")


def _is_iam_node(node: Node) -> bool:
    nt = str(node.get("nodeType") or "").lower()
    return any(k in nt for k in ("policy", "dynamicgroup", "dynamic_group", "group", "user", "identity", "domain"))


def _arch_node_label(node: Node) -> str:
    name = str(node.get("name") or "").strip()
    node_type = str(node.get("nodeType") or "").strip()

    if not name:
        name = _short_ocid(str(node.get("nodeId") or ""))

    if _is_node_type(node, "Compartment") and name.startswith("ocid1"):
        name = f"Compartment {_short_ocid(name)}"

    if node_type and node_type != "Compartment":
        return f"{name} {_friendly_type(node_type)}"
    return name


def _style_block_lines() -> List[str]:
    # Keep styling subtle and deterministic; do not depend on any theme.
    return [
        "%% Styles (subtle, role-based)",
        "classDef external stroke-width:2px,stroke-dasharray: 4 3;",
        "classDef boundary stroke-width:2px,stroke-dasharray: 6 3;",
        "classDef compute stroke-width:2px;",
        "classDef network stroke-width:2px;",
        "classDef storage stroke-width:2px;",
        "classDef policy stroke-width:2px;",
        "classDef summary stroke-dasharray: 3 3;",
    ]


def _node_class(node: Node) -> str:
    nt = str(node.get("nodeType") or "")
    cat = str(node.get("nodeCategory") or "")

    if nt in {"Internet", "Users", "OCI Services"}:
        return "external"
    if cat == "compute" or _is_node_type(node, "Instance", "InstancePool", "InstanceConfiguration"):
        return "compute"
    if cat == "network" or _is_node_type(
        node,
        "Vcn",
        "Subnet",
        "InternetGateway",
        "NatGateway",
        "ServiceGateway",
        "Drg",
        "DrgAttachment",
        "VirtualCircuit",
        "IPSecConnection",
        "Cpe",
        "LocalPeeringGateway",
        "RemotePeeringConnection",
    ):
        return "network"
    if _is_node_type(node, "Bucket", "Volume", "BlockVolume", "BootVolume"):
        return "storage"
    if _is_node_type(node, "Policy"):
        return "policy"
    return "boundary"


def _node_shape(node: Node, *, fallback: str = "rect") -> str:
    cls = _node_class(node)
    if cls == "external":
        return "round"
    if cls == "compute":
        return "round"
    if cls == "storage":
        return "db"
    if cls == "policy":
        return "hex"
    return fallback


def _render_node(node_id: str, label: str, *, shape: str = "rect") -> str:
    safe = str(label).replace('"', "'")
    # Mermaid flowchart node syntax uses bracket/paren pairs to denote shapes.
    # If the label contains those same delimiter characters, Mermaid can mis-parse
    # the node definition (e.g., label containing ")" inside a ((...)) node).
    # Use HTML entities so rendered output still reads naturally.
    if shape in {"round", "db"}:
        safe = safe.replace("(", "&#40;").replace(")", "&#41;")
    if shape == "hex":
        safe = safe.replace("{", "&#123;").replace("}", "&#125;")
    if shape == "round":
        return f"  {node_id}(({safe}))"
    if shape == "db":
        return f"  {node_id}[({safe})]"
    if shape == "hex":
        return f"  {node_id}{{{{{safe}}}}}"
    return f'  {node_id}["{safe}"]'


def _arch_label(value: str, *, max_len: Optional[int] = 32) -> str:
    import re

    safe = str(value).replace('"', "'").replace("_", " ")
    safe = re.sub(r"[^A-Za-z0-9 ]", " ", safe)
    safe = " ".join(safe.split())
    if not safe:
        return "Resource"
    if max_len and len(safe) > max_len:
        safe = safe[:max_len].rstrip()
    return safe


def _sanitize_edge_label(label: str) -> str:
    # Keep edge labels conservative to avoid Mermaid parse edge-cases.
    safe = str(label).replace('"', "'")
    for ch in ("|", "\n", "\r", "\t"):
        safe = safe.replace(ch, " ")
    for ch in ("<", ">", "{", "}", "[", "]", "(", ")"):
        safe = safe.replace(ch, "")
    return " ".join(safe.split())


def _render_edge(src: str, dst: str, label: str | None = None, *, dotted: bool = False) -> str:
    arrow = "-.->" if dotted else "-->"
    if label and not dotted:
        safe = _sanitize_edge_label(label)
        if safe:
            return f"  {src} {arrow}|{safe}| {dst}"
    return f"  {src} {arrow} {dst}"


def _render_arch_edge(src: str, dst: str, *, src_port: str = "R", dst_port: str = "L") -> str:
    return f"    {src}:{src_port} -- {dst_port}:{dst}"


def _edge_sort_key(edge: Edge) -> Tuple[str, str, str]:
    return (
        str(edge.get("relation_type") or ""),
        str(edge.get("source_ocid") or ""),
        str(edge.get("target_ocid") or ""),
    )


def _edge_single_target_map(edges: Sequence[Edge], relation_type: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for edge in sorted(edges, key=_edge_sort_key):
        if str(edge.get("relation_type") or "") != relation_type:
            continue
        src = str(edge.get("source_ocid") or "")
        dst = str(edge.get("target_ocid") or "")
        if not src or not dst:
            continue
        out.setdefault(src, dst)
    return out


def _render_relationship_edges(
    edges: Sequence[Edge],
    *,
    node_ids: Set[str],
    node_id_map: Mapping[str, str],
    allowlist: Optional[Set[str]] = None,
    node_by_id: Optional[Mapping[str, Node]] = None,
    include_admin_edges: bool = True,
    label_edges: bool = True,
) -> List[str]:
    out: List[str] = []
    seen: Set[Tuple[str, str]] = set()
    for edge in sorted(edges, key=_edge_sort_key):
        rel = str(edge.get("relation_type") or "")
        if allowlist is not None and rel not in allowlist:
            continue
        src = str(edge.get("source_ocid") or "")
        dst = str(edge.get("target_ocid") or "")
        if not src or not dst:
            continue
        label = rel
        if rel in _ADMIN_RELATION_TYPES:
            if not include_admin_edges:
                continue
            if node_by_id:
                src_node = node_by_id.get(src)
                if src_node and _is_iam_node(src_node):
                    label = "IAM scope"
        if src not in node_ids or dst not in node_ids:
            continue
        src_id = node_id_map.get(src, _mermaid_id(src))
        dst_id = node_id_map.get(dst, _mermaid_id(dst))
        key = (src_id, dst_id)
        if key in seen:
            continue
        seen.add(key)
        if not label_edges:
            label = ""
        out.append(_render_edge(src_id, dst_id, label))
    return out


def _render_arch_relationship_edges(
    edges: Sequence[Edge],
    *,
    node_ids: Set[str],
    node_id_map: Mapping[str, str],
    allowlist: Optional[Set[str]] = None,
    include_admin_edges: bool = True,
    seen_pairs: Optional[Set[Tuple[str, str]]] = None,
) -> List[str]:
    out: List[str] = []
    seen: Set[Tuple[str, str]] = set()
    for edge in sorted(edges, key=_edge_sort_key):
        rel = str(edge.get("relation_type") or "")
        if allowlist is not None and rel not in allowlist:
            continue
        src = str(edge.get("source_ocid") or "")
        dst = str(edge.get("target_ocid") or "")
        if not src or not dst:
            continue
        if rel in _ADMIN_RELATION_TYPES and not include_admin_edges:
            continue
        if src not in node_ids or dst not in node_ids:
            continue
        src_id = node_id_map.get(src)
        dst_id = node_id_map.get(dst)
        if not src_id or not dst_id:
            continue
        key = tuple(sorted((src_id, dst_id)))
        if key in seen:
            continue
        seen.add(key)
        if seen_pairs is not None:
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
        out.append(_render_arch_edge(src_id, dst_id))
    return out


def _render_node_with_class(node_id: str, label: str, *, cls: str, shape: str = "rect") -> List[str]:
    return [_render_node(node_id, label, shape=shape), f"  class {node_id} {cls}"]


def _summarize_many(nodes: Sequence[Node], *, title: str, keep: int = 2) -> Tuple[List[Node], Optional[str]]:
    if len(nodes) <= keep + 1:
        return list(nodes), None
    kept = list(nodes[:keep])
    remaining = len(nodes) - keep
    return kept, f"{title}... and {remaining} more"


def _keep_and_omitted(nodes: Sequence[Node], *, keep: int) -> Tuple[List[Node], List[Node]]:
    if keep <= 0:
        return [], list(nodes)
    if len(nodes) <= keep:
        return list(nodes), []
    return list(nodes[:keep]), list(nodes[keep:])


def _top_types(nodes: Sequence[Node]) -> List[Tuple[str, int]]:
    counts: Dict[str, int] = {}
    for n in nodes:
        t = str(n.get("nodeType") or "Unknown")
        counts[t] = counts.get(t, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def _stable_example_nodes_by_type(nodes: Sequence[Node], *, max_per_type: int = 1) -> Dict[str, List[Node]]:
    by_type: Dict[str, List[Node]] = {}
    for n in nodes:
        t = str(n.get("nodeType") or "Unknown")
        by_type.setdefault(t, []).append(n)
    out: Dict[str, List[Node]] = {}
    for t, items in by_type.items():
        items_sorted = sorted(items, key=lambda n: (str(n.get("name") or ""), str(n.get("nodeId") or "")))
        out[t] = items_sorted[: max(0, max_per_type)]
    return out


def _render_omitted_type_summaries(
    lines: List[str],
    *,
    prefix: str,
    omitted_nodes: Sequence[Node],
    max_types: int = 8,
    example_types: int = 3,
    examples_per_type: int = 1,
) -> None:
    if not omitted_nodes:
        return

    lines.append(f"  %% Omitted resources (by type) [{prefix}]")
    types = _top_types(omitted_nodes)
    shown_types = types[:max_types]
    remainder = sum(c for _, c in types[max_types:])

    example_map = _stable_example_nodes_by_type(omitted_nodes, max_per_type=examples_per_type)

    for idx, (t, c) in enumerate(shown_types):
        sid = _mermaid_id(f"{prefix}:type:{t}")
        lines.extend(_render_node_with_class(sid, f"{t}<br>{c} items", cls="summary", shape="rect"))
        if idx < example_types:
            for ex in example_map.get(t, []):
                ex_ocid = str(ex.get("nodeId") or "")
                if not ex_ocid:
                    continue
                ex_id = _mermaid_id(ex_ocid)
                lines.extend(
                    _render_node_with_class(ex_id, _mermaid_label_for(ex), cls=_node_class(ex), shape=_node_shape(ex))
                )
                lines.append(_render_edge(sid, ex_id, "example", dotted=True))

    if remainder:
        rid = _mermaid_id(f"{prefix}:type:remainder")
        lines.extend(_render_node_with_class(rid, f"Other types... and {remainder} more", cls="summary", shape="rect"))


def _render_omitted_by_compartment_summary(
    lines: List[str],
    *,
    prefix: str,
    omitted_nodes: Sequence[Node],
    node_by_id: Mapping[str, Node],
    max_compartments: int = 4,
    max_types_per_compartment: int = 4,
) -> None:
    if not omitted_nodes:
        return

    # Group omitted nodes by compartmentId.
    by_comp: Dict[str, List[Node]] = {}
    for n in omitted_nodes:
        cid = str(n.get("compartmentId") or "") or "UNKNOWN"
        by_comp.setdefault(cid, []).append(n)

    # Select top compartments by omitted volume.
    comp_ranked = sorted(by_comp.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:max_compartments]
    if not comp_ranked:
        return

    lines.append(f"  %% Omitted resources (top compartments) [{prefix}]")

    for cid, comp_nodes in comp_ranked:
        if cid == "UNKNOWN":
            comp_label = "Compartment: Unknown"
        else:
            comp_label = _compartment_label(node_by_id.get(cid, {"name": cid}))

        comp_id = _mermaid_id(f"{prefix}:comp:{cid}")
        lines.extend(
            _render_node_with_class(
                comp_id,
                f"{comp_label}<br>omitted: {len(comp_nodes)}",
                cls="summary",
                shape="rect",
            )
        )

        # Within compartment: show top omitted types.
        types = _top_types(comp_nodes)
        shown = types[:max_types_per_compartment]
        remainder = sum(c for _, c in types[max_types_per_compartment:])
        for t, c in shown:
            tid = _mermaid_id(f"{prefix}:comp:{cid}:type:{t}")
            lines.extend(_render_node_with_class(tid, f"{t}<br>{c} items", cls="summary", shape="rect"))
            lines.append(_render_edge(comp_id, tid, "", dotted=True))

        if remainder:
            rid = _mermaid_id(f"{prefix}:comp:{cid}:type:remainder")
            lines.extend(
                _render_node_with_class(
                    rid,
                    f"Other types... and {remainder} more",
                    cls="summary",
                    shape="rect",
                )
            )
            lines.append(_render_edge(comp_id, rid, "", dotted=True))


def _instance_first_sort_key(node: Node) -> Tuple[int, str, str, str]:
    return (
        0 if _is_node_type(node, "Instance") else 1,
        str(node.get("nodeCategory") or ""),
        str(node.get("nodeType") or ""),
        str(node.get("name") or ""),
    )


def _is_media_like(node: Node) -> bool:
    nt = str(node.get("nodeType") or "").lower()
    name = str(node.get("name") or "").lower()
    if "media" in nt:
        return True
    if name.startswith("output/"):
        return True
    if any(name.endswith(ext) for ext in (".mp4", ".m3u8", ".fmp4", ".ts", ".mpd", ".jpg", ".png")):
        return True
    return False


def _compartment_label(node: Node) -> str:
    name = str(node.get("name") or "").strip()
    if name.startswith("ocid1"):
        return f"Compartment {_short_ocid(name)}"
    return f"Compartment: {name}" if name else "Compartment"


def _vcn_label(node: Node) -> str:
    meta = _node_metadata(node)
    cidr = _get_meta(meta, "cidr_block")
    name = str(node.get("name") or "VCN").strip()
    if isinstance(cidr, str) and cidr:
        return f"VCN: {name} ({cidr})"
    return f"VCN: {name}"


def _subnet_label(node: Node) -> str:
    meta = _node_metadata(node)
    name = str(node.get("name") or "Subnet").strip()
    cidr = _get_meta(meta, "cidr_block")
    prohibit = _get_meta(meta, "prohibit_public_ip_on_vnic")
    vis = "private" if prohibit is True else "public" if prohibit is False else "subnet"
    if isinstance(cidr, str) and cidr:
        return f"Subnet: {name} ({vis}, {cidr})"
    return f"Subnet: {name} ({vis})"


def _is_vcn_level_resource(node: Node) -> bool:
    return _is_node_type(
        node,
        "RouteTable",
        "SecurityList",
        "NetworkSecurityGroup",
        "DhcpOptions",
        "InternetGateway",
        "NatGateway",
        "ServiceGateway",
        "Drg",
        "DrgAttachment",
        "VirtualCircuit",
        "IPSecConnection",
        "Cpe",
        "LocalPeeringGateway",
        "RemotePeeringConnection",
    )


def _tenancy_label(nodes: Sequence[Node]) -> str:
    roots: List[Node] = []
    for n in nodes:
        if not _is_node_type(n, "Compartment"):
            continue
        if n.get("compartmentId"):
            continue
        roots.append(n)
    if roots:
        roots_sorted = sorted(roots, key=lambda n: str(n.get("name") or ""))
        name = str(roots_sorted[0].get("name") or "").strip()
        if name:
            if name.startswith("ocid1"):
                return f"Tenancy {_short_ocid(name)}"
            return f"Tenancy: {name}"
    return "Tenancy"


def _legend_flowchart_lines(prefix: str) -> List[str]:
    legend_id = _mermaid_id(f"legend:{prefix}")
    lines: List[str] = [f"  subgraph {legend_id}[\"Legend\"]", "    direction TB"]
    items = [
        ("external", "External", "external", "round"),
        ("compute", "Compute", "compute", "round"),
        ("network", "Network", "network", "rect"),
        ("storage", "Storage", "storage", "db"),
        ("policy", "Policy / IAM", "policy", "hex"),
        ("overlay", "Overlay (dotted)", "boundary", "rect"),
        ("other", "Other / Boundary", "boundary", "rect"),
    ]
    for key, label, cls, shape in items:
        node_id = _mermaid_id(f"legend:{prefix}:{key}")
        lines.extend(_render_node_with_class(node_id, label, cls=cls, shape=shape))
    lines.append("  end")
    return lines


def _derived_attachments(nodes: Sequence[Node], edges: Sequence[Edge] | None = None) -> List[_DerivedAttachment]:
    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}

    # Index VNICs to help attach instances -> subnet/vcn.
    vnic_meta_by_id: Dict[str, Mapping[str, Any]] = {}
    for n in nodes:
        if _is_node_type(n, "Vnic"):
            vnic_meta_by_id[str(n.get("nodeId") or "")] = _node_metadata(n)
    vnic_by_instance: Dict[str, Dict[str, Optional[str]]] = {}
    for vnic_id in sorted(vnic_meta_by_id.keys()):
        vmeta = vnic_meta_by_id[vnic_id]
        inst_id = _get_meta(vmeta, "instance_id", "instanceId")
        if not isinstance(inst_id, str) or not inst_id:
            continue
        vcn_hint = _get_meta(vmeta, "vcn_id", "vcnId")
        subnet_hint = _get_meta(vmeta, "subnet_id", "subnetId")
        entry = vnic_by_instance.setdefault(inst_id, {"vcn_id": None, "subnet_id": None})
        if not entry["vcn_id"] and isinstance(vcn_hint, str):
            entry["vcn_id"] = vcn_hint
        if not entry["subnet_id"] and isinstance(subnet_hint, str):
            entry["subnet_id"] = subnet_hint

    edge_vcn_by_src: Dict[str, str] = {}
    edge_subnet_by_src: Dict[str, str] = {}
    if edges:
        for edge in sorted(edges, key=_edge_sort_key):
            rel = str(edge.get("relation_type") or "")
            src = str(edge.get("source_ocid") or "")
            dst = str(edge.get("target_ocid") or "")
            if not src or not dst:
                continue
            if rel == "IN_VCN":
                edge_vcn_by_src.setdefault(src, dst)
            elif rel == "IN_SUBNET":
                edge_subnet_by_src.setdefault(src, dst)

    out: List[_DerivedAttachment] = []

    for n in nodes:
        ocid = str(n.get("nodeId") or "")
        if not ocid:
            continue

        meta = _node_metadata(n)

        vcn_id = edge_vcn_by_src.get(ocid)
        subnet_id = edge_subnet_by_src.get(ocid)

        if not vcn_id:
            vcn_id = _get_meta(meta, "vcn_id")
        if not subnet_id:
            subnet_id = _get_meta(meta, "subnet_id")

        # Some resources reference multiple subnets.
        subnet_ids = _get_meta(meta, "subnet_ids")
        if not subnet_id and isinstance(subnet_ids, list) and subnet_ids:
            subnet_id = str(subnet_ids[0])

        # Instance attachment via primary VNIC.
        if _is_node_type(n, "Instance") and (not subnet_id or not vcn_id):
            pvnic = _get_meta(meta, "primary_vnic_id")
            if isinstance(pvnic, str) and pvnic in vnic_meta_by_id:
                vmeta = vnic_meta_by_id[pvnic]
                vcn_id = vcn_id or _get_meta(vmeta, "vcn_id")
                subnet_id = subnet_id or _get_meta(vmeta, "subnet_id")
            if (not subnet_id or not vcn_id) and ocid in vnic_by_instance:
                vmeta = vnic_by_instance.get(ocid) or {}
                vcn_id = vcn_id or vmeta.get("vcn_id")
                subnet_id = subnet_id or vmeta.get("subnet_id")

        # VNIC itself: include for downstream inference (not necessarily rendered).
        if _is_node_type(n, "Vnic"):
            vcn_id = vcn_id or _get_meta(meta, "vcn_id")
            subnet_id = subnet_id or _get_meta(meta, "subnet_id")

        # Some resources have direct subnetId/vcnId fields.
        if not vcn_id:
            vcn_id = _get_meta(meta, "vcnId")
        if not subnet_id:
            subnet_id = _get_meta(meta, "subnetId")

        vcn = str(vcn_id) if isinstance(vcn_id, str) and vcn_id else None
        subnet = str(subnet_id) if isinstance(subnet_id, str) and subnet_id else None

        # Only keep attachments that actually reference known nodes.
        if vcn and vcn not in node_by_id:
            vcn = None
        if subnet and subnet not in node_by_id:
            subnet = None

        out.append(_DerivedAttachment(resource_ocid=ocid, vcn_ocid=vcn, subnet_ocid=subnet))

    return out


def _tenancy_nodes_to_show(nodes: Sequence[Node]) -> List[Node]:
    return list(nodes)


def _write_tenancy_view(outdir: Path, nodes: Sequence[Node], edges: Sequence[Edge]) -> Path:
    path = outdir / "diagram.tenancy.mmd"

    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}
    rendered_node_ids: Set[str] = set()
    edge_node_id_map: Dict[str, str] = {}
    gateway_nodes = [n for n in nodes if n.get("nodeId") and _is_node_type(n, *_NETWORK_GATEWAY_NODETYPES)]
    has_internet = any(_is_node_type(n, "InternetGateway", "NatGateway") for n in gateway_nodes)
    has_service = any(_is_node_type(n, "ServiceGateway") for n in gateway_nodes)
    has_customer_net = any(_is_node_type(n, "Drg", "VirtualCircuit", "IPSecConnection", "Cpe") for n in gateway_nodes)

    # Group by compartmentId (or unknown).
    comps_all: Dict[str, List[Node]] = {}
    for n in nodes:
        cid = str(n.get("compartmentId") or "")
        if not cid and _is_node_type(n, "Compartment"):
            cid = str(n.get("nodeId") or "")
        comps_all.setdefault(cid or "UNKNOWN", []).append(n)

    # Stable order.
    comp_ids = sorted(comps_all.keys())

    vcns = [n for n in nodes if _is_node_type(n, "Vcn")]
    subnets = [n for n in nodes if _is_node_type(n, "Subnet")]
    edge_vcn_by_src = _edge_single_target_map(edges, "IN_VCN") if edges else {}

    subnet_to_vcn: Dict[str, str] = {}
    for sn in subnets:
        meta = _node_metadata(sn)
        sn_id = str(sn.get("nodeId") or "")
        vcn_id = edge_vcn_by_src.get(sn_id) or _get_meta(meta, "vcn_id")
        if isinstance(vcn_id, str) and vcn_id:
            subnet_to_vcn[sn_id] = vcn_id

    attachments = _derived_attachments(nodes, edges)
    attach_by_res: Dict[str, _DerivedAttachment] = {a.resource_ocid: a for a in attachments}

    lines: List[str] = ["flowchart LR"]
    lines.extend(_style_block_lines())
    lines.append("%% ------------------ Tenancy / Compartments ------------------")

    internet_id = ""
    oci_services_id = ""
    customer_net_id = ""
    if has_internet:
        internet_id = _mermaid_id("external:internet")
        lines.extend(_render_node_with_class(internet_id, "Internet", cls="external", shape="round"))
    if has_service:
        oci_services_id = _mermaid_id("external:oci_services")
        lines.extend(_render_node_with_class(oci_services_id, "OCI Services", cls="external", shape="round"))
    if has_customer_net:
        customer_net_id = _mermaid_id("external:customer_network")
        lines.extend(_render_node_with_class(customer_net_id, "Customer Network", cls="external", shape="round"))

    tenancy_label = _tenancy_label(nodes)
    tenancy_label_safe = tenancy_label.replace('"', "'")
    tenancy_id = _mermaid_id("tenancy")
    lines.append(f"subgraph {tenancy_id}[\"{tenancy_label_safe}\"]")
    lines.append("  direction TB")

    for cid in comp_ids:
        comp_label = (
            "Compartment: Unknown"
            if cid == "UNKNOWN"
            else _compartment_label(node_by_id.get(cid, {"name": cid}))
        )
        comp_label_safe = comp_label.replace('"', "'")
        comp_group_id = _mermaid_id(f"comp:{cid}")
        lines.append(f"  subgraph {comp_group_id}[\"{comp_label_safe}\"]")
        lines.append("    direction TB")

        comp_node = node_by_id.get(cid)
        if comp_node and comp_node.get("nodeId"):
            comp_node_id = _mermaid_id(str(comp_node.get("nodeId") or ""))
            lines.extend(
                _render_node_with_class(
                    comp_node_id,
                    _mermaid_label_for(comp_node),
                    cls=_node_class(comp_node),
                    shape=_node_shape(comp_node),
                )
            )
            raw_id = str(comp_node.get("nodeId") or "")
            rendered_node_ids.add(raw_id)
            edge_node_id_map.setdefault(raw_id, comp_node_id)

        comp_nodes = [n for n in comps_all.get(cid, []) if not _is_node_type(n, "Compartment")]

        in_vcn_id = _mermaid_id(f"comp:{cid}:in_vcn")
        lines.append(f"    subgraph {in_vcn_id}[\"In-VCN\"]")
        lines.append("      direction TB")

        comp_vcn_ids: Set[str] = {
            str(n.get("nodeId") or "")
            for n in comp_nodes
            if _is_node_type(n, "Vcn") and n.get("nodeId")
        }
        for n in comp_nodes:
            att = attach_by_res.get(str(n.get("nodeId") or ""))
            if att and att.vcn_ocid:
                comp_vcn_ids.add(att.vcn_ocid)

        for vcn_id in sorted(comp_vcn_ids):
            if not vcn_id:
                continue
            vcn_node = node_by_id.get(vcn_id, {"name": vcn_id, "nodeType": "Vcn"})
            vcn_label_safe = _vcn_label(vcn_node).replace('"', "'")
            vcn_group_id = _mermaid_id(f"comp:{cid}:vcn:{vcn_id}:group")
            lines.append(f"      subgraph {vcn_group_id}[\"{vcn_label_safe}\"]")
            lines.append("        direction TB")

            vcn_node_id = _mermaid_id(vcn_id)
            lines.extend(
                _render_node_with_class(
                    vcn_node_id,
                    _mermaid_label_for(vcn_node),
                    cls=_node_class(vcn_node),
                    shape=_node_shape(vcn_node),
                )
            )
            rendered_node_ids.add(vcn_id)
            edge_node_id_map.setdefault(vcn_id, vcn_node_id)

            vcn_level_nodes: List[Node] = []
            unknown_subnet_nodes: List[Node] = []
            for n in comp_nodes:
                if _is_node_type(n, "Vcn", "Subnet"):
                    continue
                ocid = str(n.get("nodeId") or "")
                att = attach_by_res.get(ocid)
                if not att or att.vcn_ocid != vcn_id:
                    continue
                if att.subnet_ocid:
                    continue
                if _is_vcn_level_resource(n):
                    vcn_level_nodes.append(n)
                else:
                    unknown_subnet_nodes.append(n)

            if vcn_level_nodes:
                vcn_level_id = _mermaid_id(f"comp:{cid}:vcn:{vcn_id}:vcn_level")
                lines.append(f"        subgraph {vcn_level_id}[\"VCN-level Resources\"]")
                lines.append("          direction TB")
                for n in sorted(
                    vcn_level_nodes,
                    key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")),
                ):
                    nid = _mermaid_id(str(n.get("nodeId") or ""))
                    lines.extend(
                        _render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n))
                    )
                    if n.get("nodeId"):
                        raw_id = str(n.get("nodeId") or "")
                        rendered_node_ids.add(raw_id)
                        edge_node_id_map.setdefault(raw_id, nid)
                lines.append("        end")

            vcn_subnets = [sn for sn in subnets if subnet_to_vcn.get(str(sn.get("nodeId") or "")) == vcn_id]
            for sn in sorted(vcn_subnets, key=lambda n: str(n.get("name") or "")):
                sn_ocid = str(sn.get("nodeId") or "")
                subnet_label_safe = _subnet_label(sn).replace('"', "'")
                sn_group_id = _mermaid_id(f"comp:{cid}:subnet:{sn_ocid}:group")
                lines.append(f"        subgraph {sn_group_id}[\"{subnet_label_safe}\"]")
                lines.append("          direction TB")

                sn_node_id = _mermaid_id(sn_ocid)
                lines.extend(
                    _render_node_with_class(
                        sn_node_id,
                        _mermaid_label_for(sn),
                        cls=_node_class(sn),
                        shape=_node_shape(sn),
                    )
                )
                if sn_ocid:
                    rendered_node_ids.add(sn_ocid)
                    edge_node_id_map.setdefault(sn_ocid, sn_node_id)

                attached = [
                    n
                    for n in comp_nodes
                    if attach_by_res.get(str(n.get("nodeId") or ""))
                    and attach_by_res[str(n.get("nodeId") or "")].subnet_ocid == sn_ocid
                    and not _is_node_type(n, "Vcn", "Subnet")
                ]
                for n in sorted(
                    attached,
                    key=lambda n: (
                        str(n.get("nodeCategory") or ""),
                        str(n.get("nodeType") or ""),
                        str(n.get("name") or ""),
                    ),
                ):
                    nid = _mermaid_id(str(n.get("nodeId") or ""))
                    lines.extend(
                        _render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n))
                    )
                    if n.get("nodeId"):
                        raw_id = str(n.get("nodeId") or "")
                        rendered_node_ids.add(raw_id)
                        edge_node_id_map.setdefault(raw_id, nid)
                lines.append("        end")

            if unknown_subnet_nodes:
                unk_id = _mermaid_id(f"comp:{cid}:vcn:{vcn_id}:subnet:unknown")
                lines.append(f"        subgraph {unk_id}[\"Subnet: Unknown\"]")
                lines.append("          direction TB")
                for n in sorted(
                    unknown_subnet_nodes,
                    key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")),
                ):
                    nid = _mermaid_id(str(n.get("nodeId") or ""))
                    lines.extend(
                        _render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n))
                    )
                    if n.get("nodeId"):
                        raw_id = str(n.get("nodeId") or "")
                        rendered_node_ids.add(raw_id)
                        edge_node_id_map.setdefault(raw_id, nid)
                lines.append("        end")

            lines.append("      end")

        lines.append("    end")

        out_id = _mermaid_id(f"comp:{cid}:out_vcn")
        lines.append(f"    subgraph {out_id}[\"Out-of-VCN Services\"]")
        lines.append("      direction TB")

        out_nodes = []
        for n in comp_nodes:
            if _is_node_type(n, "Vcn", "Subnet"):
                continue
            ocid = str(n.get("nodeId") or "")
            att = attach_by_res.get(ocid)
            if att and att.vcn_ocid:
                continue
            out_nodes.append(n)

        lane_groups = _group_nodes_by_lane(out_nodes)
        for lane, lane_nodes in lane_groups.items():
            lane_id = _mermaid_id(f"comp:{cid}:out_vcn:lane:{lane}")
            lines.append(f"      subgraph {lane_id}[\"{_lane_label(lane)}\"]")
            lines.append("        direction TB")
            for n in sorted(
                lane_nodes,
                key=lambda n: (str(n.get("nodeCategory") or ""), str(n.get("nodeType") or ""), str(n.get("name") or "")),
            ):
                nid = _mermaid_id(str(n.get("nodeId") or ""))
                lines.extend(
                    _render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n))
                )
                if n.get("nodeId"):
                    raw_id = str(n.get("nodeId") or "")
                    rendered_node_ids.add(raw_id)
                    edge_node_id_map.setdefault(raw_id, nid)
            lines.append("      end")

        lines.append("    end")

        overlay_nodes = [n for n in comp_nodes if n.get("nodeId")]
        overlay_groups = _group_nodes_by_lane(overlay_nodes)
        if overlay_groups:
            overlay_id = _mermaid_id(f"comp:{cid}:overlays")
            lines.append(f"    subgraph {overlay_id}[\"Functional Overlays\"]")
            lines.append("      direction TB")
            for lane, lane_nodes in overlay_groups.items():
                lane_id = _mermaid_id(f"comp:{cid}:overlays:{lane}")
                lines.append(f"      subgraph {lane_id}[\"{_lane_label(lane)}\"]")
                lines.append("        direction TB")
                for n in sorted(
                    lane_nodes,
                    key=lambda n: (str(n.get("nodeCategory") or ""), str(n.get("nodeType") or ""), str(n.get("name") or "")),
                ):
                    ocid = str(n.get("nodeId") or "")
                    if not ocid:
                        continue
                    overlay_node_id = _mermaid_id(f"overlay:{cid}:{ocid}")
                    lines.extend(
                        _render_node_with_class(
                            overlay_node_id,
                            _mermaid_label_for(n),
                            cls=_node_class(n),
                            shape=_node_shape(n),
                        )
                    )
                    canonical_id = edge_node_id_map.get(ocid)
                    if canonical_id:
                        lines.append(_render_edge(overlay_node_id, canonical_id, dotted=True))
                lines.append("      end")
            lines.append("    end")

        lines.append("  end")

    lines.extend(_legend_flowchart_lines("tenancy"))

    rel_lines = _render_relationship_edges(
        edges,
        node_ids=rendered_node_ids,
        node_id_map=edge_node_id_map,
        node_by_id=node_by_id,
        include_admin_edges=True,
    )
    lines.extend(rel_lines)

    if gateway_nodes:
        for n in gateway_nodes:
            ocid = str(n.get("nodeId") or "")
            if not ocid:
                continue
            gid = edge_node_id_map.get(ocid)
            if not gid:
                continue
            if _is_node_type(n, "InternetGateway") and internet_id:
                lines.append(_render_edge(internet_id, gid, "ingress/egress inferred", dotted=True))
            if _is_node_type(n, "NatGateway") and internet_id:
                lines.append(_render_edge(gid, internet_id, "egress inferred", dotted=True))
            if _is_node_type(n, "ServiceGateway") and oci_services_id:
                lines.append(_render_edge(gid, oci_services_id, "OCI services inferred", dotted=True))
            if _is_node_type(n, "Drg", "VirtualCircuit", "IPSecConnection", "Cpe") and customer_net_id:
                lines.append(_render_edge(gid, customer_net_id, "customer network inferred", dotted=True))

    lines.append("end")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_network_views(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    max_vcns: Optional[int] = None,
) -> List[Path]:
    if max_vcns == 0:
        return []
    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}

    vcns = [n for n in nodes if _is_node_type(n, "Vcn")]
    subnets = [n for n in nodes if _is_node_type(n, "Subnet")]

    edge_vcn_by_src = _edge_single_target_map(edges, "IN_VCN")

    # Map subnet -> vcn.
    subnet_to_vcn: Dict[str, str] = {}
    for sn in subnets:
        meta = _node_metadata(sn)
        sn_id = str(sn.get("nodeId") or "")
        vcn_id = edge_vcn_by_src.get(sn_id) or _get_meta(meta, "vcn_id")
        if isinstance(vcn_id, str) and vcn_id:
            subnet_to_vcn[sn_id] = vcn_id

    # Attach resources to vcn/subnet.
    attachments = _derived_attachments(nodes, edges)
    attach_by_res: Dict[str, _DerivedAttachment] = {a.resource_ocid: a for a in attachments}

    gateways_by_vcn: Dict[str, List[Node]] = {}
    for n in nodes:
        if not _is_node_type(n, *_NETWORK_GATEWAY_NODETYPES):
            continue
        meta = _node_metadata(n)
        nid = str(n.get("nodeId") or "")
        vcn_ref = edge_vcn_by_src.get(nid) or _get_meta(meta, "vcn_id")
        if isinstance(vcn_ref, str) and vcn_ref:
            gateways_by_vcn.setdefault(vcn_ref, []).append(n)

    out_paths: List[Path] = []

    vcns_sorted = sorted(vcns, key=lambda n: str(n.get("name") or ""))
    if max_vcns is not None and max_vcns > 0 and len(vcns_sorted) > max_vcns:
        vcn_scores: Dict[str, int] = {}
        for sn_id, vcn_id in subnet_to_vcn.items():
            vcn_scores[vcn_id] = vcn_scores.get(vcn_id, 0) + 1
        for att in attachments:
            if att.vcn_ocid:
                vcn_scores[att.vcn_ocid] = vcn_scores.get(att.vcn_ocid, 0) + 1
        vcns_scored = sorted(
            vcns_sorted,
            key=lambda n: (-vcn_scores.get(str(n.get("nodeId") or ""), 0), str(n.get("name") or "")),
        )
        vcns_sorted = sorted(vcns_scored[:max_vcns], key=lambda n: str(n.get("name") or ""))

    for vcn in vcns_sorted:
        vcn_ocid = str(vcn.get("nodeId") or "")
        vcn_name = str(vcn.get("name") or "vcn").strip() or "vcn"
        fname = f"diagram.network.{_slugify(vcn_name)}.mmd"
        path = outdir / fname

        rendered_node_ids: Set[str] = set()
        edge_node_id_map: Dict[str, str] = {}
        lines: List[str] = ["flowchart LR"]
        lines.extend(_style_block_lines())
        lines.append("%% ------------------ Network Topology ------------------")

        internet_id = _mermaid_id(f"external:internet:{vcn_name}")
        lines.extend(_render_node_with_class(internet_id, "Internet", cls="external", shape="round"))

        gateways: List[Node] = gateways_by_vcn.get(vcn_ocid, [])

        has_sgw = any(_is_node_type(g, "ServiceGateway") for g in gateways)
        oci_services_id = ""
        if has_sgw:
            oci_services_id = _mermaid_id(f"external:oci_services:{vcn_name}")
            lines.extend(_render_node_with_class(oci_services_id, "OCI Services", cls="external", shape="round"))
        has_customer_net = any(_is_node_type(g, "Drg", "VirtualCircuit", "IPSecConnection", "Cpe") for g in gateways)
        customer_net_id = ""
        if has_customer_net:
            customer_net_id = _mermaid_id(f"external:customer_network:{vcn_name}")
            lines.extend(_render_node_with_class(customer_net_id, "Customer Network", cls="external", shape="round"))

        tenancy_label = _tenancy_label(nodes)
        tenancy_label_safe = tenancy_label.replace('"', "'")
        tenancy_id = _mermaid_id(f"tenancy:{vcn_ocid}")
        lines.append(f"subgraph {tenancy_id}[\"{tenancy_label_safe}\"]")
        lines.append("  direction TB")

        comp_id = str(vcn.get("compartmentId") or "") or "UNKNOWN"
        comp_label = (
            "Compartment: Unknown"
            if comp_id == "UNKNOWN"
            else _compartment_label(node_by_id.get(comp_id, {"name": comp_id}))
        )
        comp_label_safe = comp_label.replace('"', "'")
        comp_group_id = _mermaid_id(f"comp:{comp_id}:network:{vcn_ocid}")
        lines.append(f"  subgraph {comp_group_id}[\"{comp_label_safe}\"]")
        lines.append("    direction TB")

        comp_node = node_by_id.get(comp_id)
        if comp_node and comp_node.get("nodeId"):
            comp_node_id = _mermaid_id(str(comp_node.get("nodeId") or ""))
            lines.extend(
                _render_node_with_class(
                    comp_node_id,
                    _mermaid_label_for(comp_node),
                    cls=_node_class(comp_node),
                    shape=_node_shape(comp_node),
                )
            )
            raw_id = str(comp_node.get("nodeId") or "")
            rendered_node_ids.add(raw_id)
            edge_node_id_map.setdefault(raw_id, comp_node_id)

        in_vcn_id = _mermaid_id(f"comp:{comp_id}:network:{vcn_ocid}:in_vcn")
        lines.append(f"    subgraph {in_vcn_id}[\"In-VCN\"]")
        lines.append("      direction TB")

        vcn_group_id = _mermaid_id(f"comp:{comp_id}:vcn:{vcn_ocid}:group")
        vcn_label_safe = _vcn_label(vcn).replace('"', "'")
        lines.append(f"      subgraph {vcn_group_id}[\"{vcn_label_safe}\"]")
        lines.append("        direction TB")

        vcn_node_id = _mermaid_id(vcn_ocid)
        lines.extend(
            _render_node_with_class(
                vcn_node_id,
                _mermaid_label_for(vcn),
                cls=_node_class(vcn),
                shape=_node_shape(vcn),
            )
        )
        if vcn_ocid:
            rendered_node_ids.add(vcn_ocid)
            edge_node_id_map.setdefault(vcn_ocid, vcn_node_id)

        if gateways:
            gw_id = _mermaid_id(f"vcn:{vcn_ocid}:gateways")
            lines.append(f"        subgraph {gw_id}[\"Gateways\"]")
            lines.append("          direction TB")
            for g in sorted(gateways, key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or ""))):
                gid = _mermaid_id(str(g.get("nodeId") or ""))
                lines.extend(_render_node_with_class(gid, _mermaid_label_for(g), cls=_node_class(g), shape=_node_shape(g)))
                if g.get("nodeId"):
                    raw_id = str(g.get("nodeId") or "")
                    rendered_node_ids.add(raw_id)
                    edge_node_id_map.setdefault(raw_id, gid)
            lines.append("        end")

        vcn_level_nodes: List[Node] = []
        unknown_subnet_nodes: List[Node] = []
        for n in nodes:
            if _is_node_type(n, "Vcn", "Subnet"):
                continue
            ocid = str(n.get("nodeId") or "")
            if not ocid:
                continue
            att = attach_by_res.get(ocid)
            if att and att.vcn_ocid == vcn_ocid:
                if att.subnet_ocid:
                    continue
                if _is_node_type(n, *_NETWORK_GATEWAY_NODETYPES):
                    continue
                if _is_vcn_level_resource(n):
                    vcn_level_nodes.append(n)
                else:
                    unknown_subnet_nodes.append(n)
                continue
            meta = _node_metadata(n)
            vcn_ref = edge_vcn_by_src.get(ocid) or _get_meta(meta, "vcn_id")
            if isinstance(vcn_ref, str) and vcn_ref == vcn_ocid:
                if _is_node_type(n, *_NETWORK_GATEWAY_NODETYPES):
                    continue
                if _is_vcn_level_resource(n):
                    vcn_level_nodes.append(n)
                else:
                    unknown_subnet_nodes.append(n)

        if vcn_level_nodes:
            vcn_level_id = _mermaid_id(f"vcn:{vcn_ocid}:vcn_level")
            lines.append(f"        subgraph {vcn_level_id}[\"VCN-level Resources\"]")
            lines.append("          direction TB")
            for n in sorted(
                vcn_level_nodes,
                key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")),
            ):
                nid = _mermaid_id(str(n.get("nodeId") or ""))
                lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n)))
                if n.get("nodeId"):
                    raw_id = str(n.get("nodeId") or "")
                    rendered_node_ids.add(raw_id)
                    edge_node_id_map.setdefault(raw_id, nid)
            lines.append("        end")

        vcn_subnets = [sn for sn in subnets if subnet_to_vcn.get(str(sn.get("nodeId") or "")) == vcn_ocid]
        for sn in sorted(vcn_subnets, key=lambda n: str(n.get("name") or "")):
            sn_ocid = str(sn.get("nodeId") or "")
            sn_group_id = _mermaid_id(f"vcn:{vcn_ocid}:subnet:{sn_ocid}:group")
            subnet_label_safe = _subnet_label(sn).replace('"', "'")
            lines.append(f"        subgraph {sn_group_id}[\"{subnet_label_safe}\"]")
            lines.append("          direction TB")

            sn_node_id = _mermaid_id(sn_ocid)
            lines.extend(
                _render_node_with_class(
                    sn_node_id,
                    _mermaid_label_for(sn),
                    cls=_node_class(sn),
                    shape=_node_shape(sn),
                )
            )
            if sn_ocid:
                rendered_node_ids.add(sn_ocid)
                edge_node_id_map.setdefault(sn_ocid, sn_node_id)

            attached = [
                n
                for n in nodes
                if attach_by_res.get(str(n.get("nodeId") or ""))
                and attach_by_res[str(n.get("nodeId") or "")].subnet_ocid == sn_ocid
                and not _is_node_type(n, "Vcn", "Subnet")
            ]
            for n in sorted(
                attached,
                key=lambda n: (
                    str(n.get("nodeCategory") or ""),
                    str(n.get("nodeType") or ""),
                    str(n.get("name") or ""),
                ),
            ):
                nid = _mermaid_id(str(n.get("nodeId") or ""))
                lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n)))
                if n.get("nodeId"):
                    raw_id = str(n.get("nodeId") or "")
                    rendered_node_ids.add(raw_id)
                    edge_node_id_map.setdefault(raw_id, nid)

            lines.append("        end")

        if unknown_subnet_nodes:
            unk_id = _mermaid_id(f"vcn:{vcn_ocid}:subnet:unknown")
            lines.append(f"        subgraph {unk_id}[\"Subnet: Unknown\"]")
            lines.append("          direction TB")
            for n in sorted(
                unknown_subnet_nodes,
                key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")),
            ):
                nid = _mermaid_id(str(n.get("nodeId") or ""))
                lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n)))
                if n.get("nodeId"):
                    raw_id = str(n.get("nodeId") or "")
                    rendered_node_ids.add(raw_id)
                    edge_node_id_map.setdefault(raw_id, nid)
            lines.append("        end")

        lines.append("      end")
        lines.append("    end")
        lines.append("  end")

        lines.extend(_legend_flowchart_lines(f"network:{vcn_ocid}"))
        lines.append("end")

        rel_lines = _render_relationship_edges(
            edges,
            node_ids=rendered_node_ids,
            node_id_map=edge_node_id_map,
            node_by_id=node_by_id,
            include_admin_edges=True,
        )
        lines.extend(rel_lines)

        igw = next((g for g in gateways if _is_node_type(g, "InternetGateway")), None)
        nat = next((g for g in gateways if _is_node_type(g, "NatGateway")), None)
        sgw = next((g for g in gateways if _is_node_type(g, "ServiceGateway")), None)

        if igw is not None:
            igw_id = _mermaid_id(str(igw.get("nodeId") or ""))
            lines.append(_render_edge(internet_id, igw_id, "ingress/egress inferred", dotted=True))
        if nat is not None:
            nat_id = _mermaid_id(str(nat.get("nodeId") or ""))
            lines.append(_render_edge(nat_id, internet_id, "egress inferred", dotted=True))
        if sgw is not None and oci_services_id:
            sgw_id = _mermaid_id(str(sgw.get("nodeId") or ""))
            lines.append(_render_edge(sgw_id, oci_services_id, "OCI services inferred", dotted=True))
        if customer_net_id:
            for g in gateways:
                if not _is_node_type(g, "Drg", "VirtualCircuit", "IPSecConnection", "Cpe"):
                    continue
                g_id = _mermaid_id(str(g.get("nodeId") or ""))
                lines.append(_render_edge(g_id, customer_net_id, "customer network inferred", dotted=True))

        for sn in vcn_subnets:
            sn_ocid = str(sn.get("nodeId") or "")
            sn_id = _mermaid_id(sn_ocid)
            meta = _node_metadata(sn)
            prohibit = _get_meta(meta, "prohibit_public_ip_on_vnic")

            if prohibit is False and igw is not None:
                igw_id = _mermaid_id(str(igw.get("nodeId") or ""))
                lines.append(_render_edge(igw_id, sn_id, "routes inferred", dotted=True))

            if prohibit is True and nat is not None:
                nat_id = _mermaid_id(str(nat.get("nodeId") or ""))
                lines.append(_render_edge(sn_id, nat_id, "egress inferred", dotted=True))

            if prohibit is True and sgw is not None:
                sgw_id = _mermaid_id(str(sgw.get("nodeId") or ""))
                lines.append(_render_edge(sn_id, sgw_id, "OCI services inferred", dotted=True))

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out_paths.append(path)

    return out_paths


def _write_workload_views(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    max_workloads: Optional[int] = None,
) -> List[Path]:
    if max_workloads == 0:
        return []
    # Identify candidate workloads using shared grouping logic.
    candidates: List[Node] = []
    for n in nodes:
        nt = str(n.get("nodeType") or "")
        if nt in _NON_ARCH_LEAF_NODETYPES:
            continue
        if _is_node_type(n, "Compartment"):
            continue
        candidates.append(n)

    wl_to_nodes = {k: list(v) for k, v in group_workload_candidates(candidates).items()}

    if not wl_to_nodes:
        return []

    # Build attachments for optional network context.
    attachments = _derived_attachments(nodes, edges)
    attach_by_res: Dict[str, _DerivedAttachment] = {a.resource_ocid: a for a in attachments}

    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}
    subnets = [n for n in nodes if _is_node_type(n, "Subnet")]
    edge_vcn_by_src = _edge_single_target_map(edges, "IN_VCN")

    subnet_to_vcn: Dict[str, str] = {}
    for sn in subnets:
        meta = _node_metadata(sn)
        sn_id = str(sn.get("nodeId") or "")
        vcn_id = edge_vcn_by_src.get(sn_id) or _get_meta(meta, "vcn_id")
        if isinstance(vcn_id, str) and vcn_id:
            subnet_to_vcn[sn_id] = vcn_id

    out_paths: List[Path] = []

    wl_items = list(wl_to_nodes.items())
    if max_workloads is not None and max_workloads > 0 and len(wl_items) > max_workloads:
        wl_items = sorted(wl_items, key=lambda kv: (-len(kv[1]), kv[0].lower()))[:max_workloads]
    wl_items = sorted(wl_items, key=lambda kv: kv[0].lower())

    for wl_name, wl_nodes in wl_items:

        wl_comp_ids: Set[str] = set()
        for n in wl_nodes:
            cid = str(n.get("compartmentId") or "") or "UNKNOWN"
            wl_comp_ids.add(cid)

        comps: Dict[str, List[Node]] = {}
        for n in nodes:
            cid = str(n.get("compartmentId") or "")
            if not cid and _is_node_type(n, "Compartment"):
                cid = str(n.get("nodeId") or "")
            cid = cid or "UNKNOWN"
            if cid in wl_comp_ids:
                comps.setdefault(cid, []).append(n)

        gateway_nodes = [
            n
            for comp_nodes in comps.values()
            for n in comp_nodes
            if n.get("nodeId") and _is_node_type(n, *_NETWORK_GATEWAY_NODETYPES)
        ]
        has_internet = any(_is_node_type(n, "InternetGateway", "NatGateway") for n in gateway_nodes)
        has_customer_net = any(_is_node_type(n, "Drg", "VirtualCircuit", "IPSecConnection", "Cpe") for n in gateway_nodes)

        path = outdir / f"diagram.workload.{_slugify(wl_name)}.mmd"

        lines: List[str] = ["flowchart LR"]
        lines.extend(_style_block_lines())
        lines.append("%% ------------------ Workload / Application View ------------------")

        users_id = _mermaid_id(f"external:users:{wl_name}")
        lines.extend(_render_node_with_class(users_id, "Users", cls="external", shape="round"))

        services_id = _mermaid_id(f"external:oci_services:{wl_name}")
        lines.extend(_render_node_with_class(services_id, "OCI Services", cls="external", shape="round"))
        internet_id = ""
        customer_net_id = ""
        if has_internet:
            internet_id = _mermaid_id(f"external:internet:{wl_name}")
            lines.extend(_render_node_with_class(internet_id, "Internet", cls="external", shape="round"))
        if has_customer_net:
            customer_net_id = _mermaid_id(f"external:customer_network:{wl_name}")
            lines.extend(_render_node_with_class(customer_net_id, "Customer Network", cls="external", shape="round"))

        rendered_node_ids: Set[str] = set()
        edge_node_id_map: Dict[str, str] = {}

        tenancy_label = _tenancy_label(nodes)
        tenancy_label_safe = tenancy_label.replace('"', "'")
        tenancy_id = _mermaid_id(f"tenancy:workload:{wl_name}")
        lines.append(f"subgraph {tenancy_id}[\"{tenancy_label_safe}\"]")
        lines.append("  direction TB")

        for cid in sorted(comps.keys()):
            comp_label = "Compartment: Unknown" if cid == "UNKNOWN" else _compartment_label(node_by_id.get(cid, {"name": cid}))
            comp_label_safe = comp_label.replace('"', "'")
            comp_group_id = _mermaid_id(f"workload:{wl_name}:comp:{cid}")
            lines.append(f"  subgraph {comp_group_id}[\"{comp_label_safe}\"]")
            lines.append("    direction TB")

            comp_node = node_by_id.get(cid)
            if comp_node and comp_node.get("nodeId"):
                comp_node_id = _mermaid_id(str(comp_node.get("nodeId") or ""))
                lines.extend(
                    _render_node_with_class(
                        comp_node_id,
                        _mermaid_label_for(comp_node),
                        cls=_node_class(comp_node),
                        shape=_node_shape(comp_node),
                    )
                )
                raw_id = str(comp_node.get("nodeId") or "")
                rendered_node_ids.add(raw_id)
                edge_node_id_map.setdefault(raw_id, comp_node_id)

            comp_nodes = [n for n in comps[cid] if not _is_node_type(n, "Compartment")]

            in_vcn_id = _mermaid_id(f"workload:{wl_name}:comp:{cid}:in_vcn")
            lines.append(f"    subgraph {in_vcn_id}[\"In-VCN\"]")
            lines.append("      direction TB")

            comp_vcn_ids: Set[str] = set()
            for n in comp_nodes:
                if _is_node_type(n, "Vcn") and n.get("nodeId"):
                    comp_vcn_ids.add(str(n.get("nodeId") or ""))
                att = attach_by_res.get(str(n.get("nodeId") or ""))
                if att and att.vcn_ocid:
                    comp_vcn_ids.add(att.vcn_ocid)

            for vcn_ocid in sorted(comp_vcn_ids):
                if not vcn_ocid:
                    continue
                vcn_node = node_by_id.get(vcn_ocid, {"name": vcn_ocid, "nodeType": "Vcn"})
                vcn_label_safe = _vcn_label(vcn_node).replace('"', "'")
                vcn_group_id = _mermaid_id(f"workload:{wl_name}:comp:{cid}:vcn:{vcn_ocid}:group")
                lines.append(f"      subgraph {vcn_group_id}[\"{vcn_label_safe}\"]")
                lines.append("        direction TB")

                vcn_node_id = _mermaid_id(vcn_ocid)
                lines.extend(
                    _render_node_with_class(
                        vcn_node_id,
                        _mermaid_label_for(vcn_node),
                        cls=_node_class(vcn_node),
                        shape=_node_shape(vcn_node),
                    )
                )
                if vcn_ocid:
                    rendered_node_ids.add(vcn_ocid)
                    edge_node_id_map.setdefault(vcn_ocid, vcn_node_id)

                vcn_level_nodes: List[Node] = []
                unknown_subnet_nodes: List[Node] = []
                for n in comp_nodes:
                    if _is_node_type(n, "Vcn", "Subnet"):
                        continue
                    ocid = str(n.get("nodeId") or "")
                    if not ocid:
                        continue
                    att = attach_by_res.get(ocid)
                    if att and att.vcn_ocid == vcn_ocid:
                        if att.subnet_ocid:
                            continue
                        if _is_vcn_level_resource(n):
                            vcn_level_nodes.append(n)
                        else:
                            unknown_subnet_nodes.append(n)
                        continue
                    meta = _node_metadata(n)
                    vcn_ref = edge_vcn_by_src.get(ocid) or _get_meta(meta, "vcn_id")
                    if isinstance(vcn_ref, str) and vcn_ref == vcn_ocid:
                        if _is_vcn_level_resource(n):
                            vcn_level_nodes.append(n)
                        else:
                            unknown_subnet_nodes.append(n)

                if vcn_level_nodes:
                    vcn_level_id = _mermaid_id(f"workload:{wl_name}:comp:{cid}:vcn:{vcn_ocid}:vcn_level")
                    lines.append(f"        subgraph {vcn_level_id}[\"VCN-level Resources\"]")
                    lines.append("          direction TB")
                    for n in sorted(
                        vcn_level_nodes,
                        key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")),
                    ):
                        nid = _mermaid_id(str(n.get("nodeId") or ""))
                        lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n)))
                        if n.get("nodeId"):
                            raw_id = str(n.get("nodeId") or "")
                            rendered_node_ids.add(raw_id)
                            edge_node_id_map.setdefault(raw_id, nid)
                    lines.append("        end")

                vcn_subnet_ids: Set[str] = set()
                for n in comp_nodes:
                    if _is_node_type(n, "Subnet") and n.get("nodeId"):
                        sn_id = str(n.get("nodeId") or "")
                        if subnet_to_vcn.get(sn_id) == vcn_ocid:
                            vcn_subnet_ids.add(sn_id)
                    att = attach_by_res.get(str(n.get("nodeId") or ""))
                    if att and att.subnet_ocid:
                        vcn_subnet_ids.add(att.subnet_ocid)

                for sn_ocid in sorted(vcn_subnet_ids):
                    sn = node_by_id.get(sn_ocid, {"name": sn_ocid, "nodeType": "Subnet"})
                    subnet_label_safe = _subnet_label(sn).replace('"', "'")
                    sn_group_id = _mermaid_id(f"workload:{wl_name}:comp:{cid}:subnet:{sn_ocid}:group")
                    lines.append(f"        subgraph {sn_group_id}[\"{subnet_label_safe}\"]")
                    lines.append("          direction TB")

                    sn_node_id = _mermaid_id(sn_ocid)
                    lines.extend(
                        _render_node_with_class(
                            sn_node_id,
                            _mermaid_label_for(sn),
                            cls=_node_class(sn),
                            shape=_node_shape(sn),
                        )
                    )
                    if sn_ocid:
                        rendered_node_ids.add(sn_ocid)
                        edge_node_id_map.setdefault(sn_ocid, sn_node_id)

                    attached = [
                        n
                        for n in comp_nodes
                        if attach_by_res.get(str(n.get("nodeId") or ""))
                        and attach_by_res[str(n.get("nodeId") or "")].subnet_ocid == sn_ocid
                        and not _is_node_type(n, "Vcn", "Subnet")
                    ]
                    for n in sorted(
                        attached,
                        key=lambda n: (
                            str(n.get("nodeCategory") or ""),
                            str(n.get("nodeType") or ""),
                            str(n.get("name") or ""),
                        ),
                    ):
                        nid = _mermaid_id(str(n.get("nodeId") or ""))
                        lines.extend(
                            _render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n))
                        )
                        if n.get("nodeId"):
                            raw_id = str(n.get("nodeId") or "")
                            rendered_node_ids.add(raw_id)
                            edge_node_id_map.setdefault(raw_id, nid)

                    lines.append("        end")

                if unknown_subnet_nodes:
                    unk_id = _mermaid_id(f"workload:{wl_name}:comp:{cid}:vcn:{vcn_ocid}:subnet:unknown")
                    lines.append(f"        subgraph {unk_id}[\"Subnet: Unknown\"]")
                    lines.append("          direction TB")
                    for n in sorted(
                        unknown_subnet_nodes,
                        key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")),
                    ):
                        nid = _mermaid_id(str(n.get("nodeId") or ""))
                        lines.extend(
                            _render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n))
                        )
                        if n.get("nodeId"):
                            raw_id = str(n.get("nodeId") or "")
                            rendered_node_ids.add(raw_id)
                            edge_node_id_map.setdefault(raw_id, nid)
                    lines.append("        end")

                lines.append("      end")

            lines.append("    end")

            out_id = _mermaid_id(f"workload:{wl_name}:comp:{cid}:out_vcn")
            lines.append(f"    subgraph {out_id}[\"Out-of-VCN Services\"]")
            lines.append("      direction TB")

            out_nodes: List[Node] = []
            for n in comp_nodes:
                if _is_node_type(n, "Vcn", "Subnet"):
                    continue
                ocid = str(n.get("nodeId") or "")
                att = attach_by_res.get(ocid)
                if att and att.vcn_ocid:
                    continue
                out_nodes.append(n)

            lane_groups = _group_nodes_by_lane(out_nodes)
            for lane, lane_nodes in lane_groups.items():
                lane_id = _mermaid_id(f"workload:{wl_name}:comp:{cid}:lane:{lane}")
                lines.append(f"      subgraph {lane_id}[\"{_lane_label(lane)}\"]")
                lines.append("        direction TB")
                for n in sorted(
                    lane_nodes,
                    key=lambda n: (str(n.get("nodeCategory") or ""), str(n.get("nodeType") or ""), str(n.get("name") or "")),
                ):
                    nid = _mermaid_id(str(n.get("nodeId") or ""))
                    lines.extend(
                        _render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n))
                    )
                    if n.get("nodeId"):
                        raw_id = str(n.get("nodeId") or "")
                        rendered_node_ids.add(raw_id)
                        edge_node_id_map.setdefault(raw_id, nid)
                lines.append("      end")

            lines.append("    end")

            overlay_nodes = [n for n in comp_nodes if n.get("nodeId")]
            overlay_groups = _group_nodes_by_lane(overlay_nodes)
            if overlay_groups:
                overlay_id = _mermaid_id(f"workload:{wl_name}:comp:{cid}:overlays")
                lines.append(f"    subgraph {overlay_id}[\"Functional Overlays\"]")
                lines.append("      direction TB")
                for lane, lane_nodes in overlay_groups.items():
                    lane_id = _mermaid_id(f"workload:{wl_name}:comp:{cid}:overlays:{lane}")
                    lines.append(f"      subgraph {lane_id}[\"{_lane_label(lane)}\"]")
                    lines.append("        direction TB")
                    for n in sorted(
                        lane_nodes,
                        key=lambda n: (str(n.get("nodeCategory") or ""), str(n.get("nodeType") or ""), str(n.get("name") or "")),
                    ):
                        ocid = str(n.get("nodeId") or "")
                        if not ocid:
                            continue
                        overlay_node_id = _mermaid_id(f"overlay:{wl_name}:{cid}:{ocid}")
                        lines.extend(
                            _render_node_with_class(
                                overlay_node_id,
                                _mermaid_label_for(n),
                                cls=_node_class(n),
                                shape=_node_shape(n),
                            )
                        )
                        canonical_id = edge_node_id_map.get(ocid)
                        if canonical_id:
                            lines.append(_render_edge(overlay_node_id, canonical_id, dotted=True))
                    lines.append("      end")
                lines.append("    end")

            lines.append("  end")

        # Add workload-centric flows.
        # Users -> LoadBalancers / API-like entry points; compute -> buckets.
        flow_added = False
        lbs = [
            n
            for n in wl_nodes
            if "loadbalancer" in str(n.get("nodeType") or "").lower() or "loadbalancer" in str(n.get("name") or "").lower()
        ]
        computes = [n for n in wl_nodes if str(n.get("nodeCategory") or "") == "compute" or _is_node_type(n, "Instance")]
        computes_sorted = sorted(computes, key=_instance_first_sort_key)
        buckets = [n for n in wl_nodes if _is_node_type(n, "Bucket") or "bucket" in str(n.get("nodeType") or "").lower()]

        for lb in lbs:
            lb_id = _mermaid_id(str(lb.get("nodeId") or ""))
            lines.append(_render_edge(users_id, lb_id, "requests inferred", dotted=True))
            for c in computes_sorted:
                c_id = _mermaid_id(str(c.get("nodeId") or ""))
                lines.append(_render_edge(lb_id, c_id, "forwards inferred", dotted=True))
            flow_added = True

        for c in computes_sorted:
            c_id = _mermaid_id(str(c.get("nodeId") or ""))
            if not buckets:
                continue
            for b in buckets:
                b_id = _mermaid_id(str(b.get("nodeId") or ""))
                lines.append(_render_edge(c_id, b_id, "reads/writes inferred", dotted=True))
                flow_added = True

        for b in buckets:
            b_id = _mermaid_id(str(b.get("nodeId") or ""))
            lines.append(_render_edge(b_id, services_id, "Object Storage inferred", dotted=True))
            flow_added = True

        if not flow_added:
            rel_present = False
            for edge in edges:
                rel = str(edge.get("relation_type") or "")
                if rel in _ADMIN_RELATION_TYPES:
                    continue
                src = str(edge.get("source_ocid") or "")
                dst = str(edge.get("target_ocid") or "")
                if src in rendered_node_ids and dst in rendered_node_ids:
                    rel_present = True
                    break
            if not rel_present:
                fallback_nodes = [
                    n for n in wl_nodes if n.get("nodeId") and not _is_node_type(n, "Compartment")
                ]
                fallback_nodes = sorted(
                    fallback_nodes,
                    key=lambda n: (str(n.get("nodeCategory") or ""), str(n.get("nodeType") or ""), str(n.get("name") or "")),
                )
                if fallback_nodes:
                    target_id = _mermaid_id(str(fallback_nodes[0].get("nodeId") or ""))
                    lines.append(_render_edge(users_id, target_id, "entry inferred", dotted=True))

        rel_lines = _render_relationship_edges(
            edges,
            node_ids=rendered_node_ids,
            node_id_map=edge_node_id_map,
            node_by_id=node_by_id,
            include_admin_edges=True,
        )
        lines.extend(rel_lines)

        if gateway_nodes:
            for n in gateway_nodes:
                ocid = str(n.get("nodeId") or "")
                if not ocid:
                    continue
                gid = edge_node_id_map.get(ocid)
                if not gid:
                    continue
                if _is_node_type(n, "InternetGateway") and internet_id:
                    lines.append(_render_edge(internet_id, gid, "ingress/egress inferred", dotted=True))
                if _is_node_type(n, "NatGateway") and internet_id:
                    lines.append(_render_edge(gid, internet_id, "egress inferred", dotted=True))
                if _is_node_type(n, "ServiceGateway"):
                    lines.append(_render_edge(gid, services_id, "OCI services inferred", dotted=True))
                if _is_node_type(n, "Drg", "VirtualCircuit", "IPSecConnection", "Cpe") and customer_net_id:
                    lines.append(_render_edge(gid, customer_net_id, "customer network inferred", dotted=True))

        lines.extend(_legend_flowchart_lines(f"workload:{wl_name}"))
        lines.append("end")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out_paths.append(path)

    return out_paths


def write_diagram_projections(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    max_network_views: Optional[int] = None,
    max_workload_views: Optional[int] = None,
) -> List[Path]:
    # Edges drive placement and relationship hints in projections.
    out: List[Path] = []
    out.append(_write_tenancy_view(outdir, nodes, edges))
    out.extend(_write_network_views(outdir, nodes, edges, max_vcns=max_network_views))
    out.extend(_write_workload_views(outdir, nodes, edges, max_workloads=max_workload_views))

    # Consolidated, end-user-friendly artifact: one Mermaid diagram that contains all the views.
    out.append(_write_consolidated_mermaid(outdir, nodes, edges, out))
    return out


def is_mmdc_available() -> bool:
    return which("mmdc") is not None


def validate_mermaid_diagrams_with_mmdc(outdir: Path, *, glob_pattern: str = "diagram*.mmd") -> List[Path]:
    """Validate Mermaid diagrams by rendering each one with `mmdc`.

    Mermaid CLI doesn't provide a pure "parse-only" mode; rendering is used as a
    deterministic syntax validation step.

    Returns the validated input paths (sorted).
    """

    mmdc = which("mmdc")
    if not mmdc:
        raise ExportError(
            "Mermaid diagram validation requested but 'mmdc' was not found on PATH. "
            "Install Mermaid CLI and retry: npm install -g @mermaid-js/mermaid-cli"
        )

    paths = sorted([p for p in outdir.glob(glob_pattern) if p.is_file()])
    if not paths:
        return []

    with tempfile.TemporaryDirectory(prefix="oci-inv-mmdc-") as td:
        tmp_dir = Path(td)
        for p in paths:
            out_svg = tmp_dir / f"{p.stem}.svg"
            proc = subprocess.run(
                [mmdc, "-i", str(p), "-o", str(out_svg)],
                text=True,
                capture_output=True,
            )
            if proc.returncode != 0:
                stderr = (proc.stderr or "").strip()
                stdout = (proc.stdout or "").strip()
                detail = stderr or stdout or f"mmdc exited with code {proc.returncode}"
                raise ExportError(f"Mermaid validation failed for {p.name}: {detail}")

    return paths


def _diagram_title(path: Path) -> str:
    name = path.name
    if name == "diagram.tenancy.mmd":
        return "Tenancy / Compartments"
    if name.startswith("diagram.network.") and name.endswith(".mmd"):
        vcn = name[len("diagram.network.") : -len(".mmd")]
        return f"Network Topology: {vcn}"
    if name.startswith("diagram.workload.") and name.endswith(".mmd"):
        wl = name[len("diagram.workload.") : -len(".mmd")]
        return f"Workload View: {wl}"
    if name.endswith(".mmd"):
        return name
    return name


def _lane_label(lane: str) -> str:
    return _LANE_LABELS.get(lane, lane.title())


def _group_nodes_by_lane(nodes: Iterable[Node]) -> Dict[str, List[Node]]:
    grouped: Dict[str, List[Node]] = {lane: [] for lane in _LANE_ORDER}
    for n in nodes:
        lane = _lane_for_node(n)
        if lane not in grouped:
            lane = "other"
        grouped[lane].append(n)

    out: Dict[str, List[Node]] = {}
    for lane in _LANE_ORDER:
        items = grouped.get(lane) or []
        if not items:
            continue
        out[lane] = sorted(items, key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")))
    return out


def _lane_for_node(node: Node) -> str:
    if _is_node_type(node, "Compartment"):
        return "tenancy"

    t = str(node.get("nodeType") or "")
    cat = str(node.get("nodeCategory") or "")

    if cat == "network" or t.startswith("network."):
        return "network"
    if cat == "security" or _is_node_type(node, "Vault", "Secret", "CloudGuardTarget", "Bastion"):
        return "security"
    if cat == "compute" or _is_node_type(node, "Instance", "OkeCluster", "Function"):
        return "app"
    if cat == "storage":
        return "data"

    # Heuristic lane classification for "other" types.
    low = t.lower()
    if any(k in low for k in ("policy", "dynamicgroup", "dynamic_group", "group", "user", "identity", "domain")):
        return "iam"
    if any(k in low for k in ("drg", "peering", "ipsec", "vpn", "virtualcircuit", "fastconnect", "gateway", "cpe")):
        return "network"
    if any(k in low for k in ("securityzone", "cloudguard", "vault", "secret", "nsg", "securitylist")):
        return "security"
    if any(k in low for k in ("bucket", "database", "dbsystem", "stream", "queue", "topic")):
        return "data"
    if any(k in low for k in ("alarm", "event", "notification", "log", "metric", "loganalytics")):
        return "observability"
    if _is_media_like(node):
        return "data"

    return "other"


def _write_consolidated_mermaid(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    diagram_paths: Sequence[Path],
) -> Path:
    consolidated = outdir / "diagram.consolidated.mmd"
    # Architecture diagram (architecture-beta). Full-detail OCI containment view.

    def _service_id(prefix: str, value: str) -> str:
        import hashlib

        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
        return f"{prefix}{digest[:10]}"

    def _service_icon(node: Node) -> str:
        cls = _node_class(node)
        if cls in {"network", "external"}:
            return "cloud"
        if cls == "storage":
            return "database"
        return "server"

    lines: List[str] = ["architecture-beta"]
    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}
    subnets = [n for n in nodes if _is_node_type(n, "Subnet")]
    edge_vcn_by_src = _edge_single_target_map(edges, "IN_VCN")

    subnet_to_vcn: Dict[str, str] = {}
    for sn in subnets:
        meta = _node_metadata(sn)
        sn_id = str(sn.get("nodeId") or "")
        vcn_id = edge_vcn_by_src.get(sn_id) or _get_meta(meta, "vcn_id")
        if isinstance(vcn_id, str) and vcn_id:
            subnet_to_vcn[sn_id] = vcn_id

    attachments = _derived_attachments(nodes, edges)
    attach_by_res: Dict[str, _DerivedAttachment] = {a.resource_ocid: a for a in attachments}

    rendered_node_ids: Set[str] = set()
    node_service_ids: Dict[str, str] = {}
    gateway_service_ids: Dict[str, str] = {}
    seen_arch_edges: Set[Tuple[str, str]] = set()

    def _add_service(node: Node, parent_id: str) -> None:
        ocid = str(node.get("nodeId") or "")
        if not ocid or ocid in node_service_ids:
            return
        sid = _service_id("node_", ocid)
        label = _arch_label(_arch_node_label(node), max_len=None)
        icon = _service_icon(node)
        lines.append(f"    service {sid}({icon})[{label}] in {parent_id}")
        node_service_ids[ocid] = sid
        if _is_node_type(node, *_NETWORK_GATEWAY_NODETYPES):
            gateway_service_ids[ocid] = sid
        rendered_node_ids.add(ocid)

    def _add_arch_edge(src_id: str, dst_id: str) -> None:
        key = tuple(sorted((src_id, dst_id)))
        if key in seen_arch_edges:
            return
        seen_arch_edges.add(key)
        lines.append(_render_arch_edge(src_id, dst_id))

    tenancy_label = _tenancy_label(nodes)
    tenancy_id = _service_id("tenancy_", tenancy_label)
    lines.append(f"    group {tenancy_id}(cloud)[{_arch_label(tenancy_label, max_len=80)}]")

    nodes_by_comp: Dict[str, List[Node]] = {}
    for n in nodes:
        cid = str(n.get("compartmentId") or "")
        if not cid and _is_node_type(n, "Compartment"):
            cid = str(n.get("nodeId") or "")
        nodes_by_comp.setdefault(cid or "UNKNOWN", []).append(n)

    for cid in sorted(nodes_by_comp.keys()):
        comp_label = "Compartment: Unknown" if cid == "UNKNOWN" else _compartment_label(node_by_id.get(cid, {"name": cid}))
        comp_group_id = _service_id("comp_", cid)
        lines.append(f"    group {comp_group_id}(cloud)[{_arch_label(comp_label, max_len=80)}] in {tenancy_id}")

        comp_node = node_by_id.get(cid)
        if comp_node and comp_node.get("nodeId"):
            _add_service(comp_node, comp_group_id)

        network_lane_id = _service_id("lane_network_", f"{cid}:network")
        lines.append(f"    group {network_lane_id}(cloud)[{_arch_label('Network', max_len=24)}] in {comp_group_id}")

        in_group_id = _service_id("invcn_", cid)
        out_group_id = _service_id("outvcn_", cid)
        lines.append(f"    group {in_group_id}(cloud)[{_arch_label('In-VCN', max_len=24)}] in {network_lane_id}")
        lines.append(f"    group {out_group_id}(cloud)[{_arch_label('Out-of-VCN Services', max_len=48)}] in {comp_group_id}")

        comp_nodes = [n for n in nodes_by_comp[cid] if not _is_node_type(n, "Compartment")]

        comp_vcn_ids: Set[str] = set()
        for n in comp_nodes:
            if _is_node_type(n, "Vcn") and n.get("nodeId"):
                comp_vcn_ids.add(str(n.get("nodeId") or ""))
            att = attach_by_res.get(str(n.get("nodeId") or ""))
            if att and att.vcn_ocid:
                comp_vcn_ids.add(att.vcn_ocid)

        for vcn_ocid in sorted(comp_vcn_ids):
            if not vcn_ocid:
                continue
            vcn_node = node_by_id.get(vcn_ocid, {"name": vcn_ocid, "nodeType": "Vcn"})
            vcn_group_id = _service_id("vcn_", vcn_ocid)
            lines.append(f"    group {vcn_group_id}(cloud)[{_arch_label(_vcn_label(vcn_node), max_len=80)}] in {in_group_id}")
            _add_service(vcn_node, vcn_group_id)

            gateway_nodes: List[Node] = []
            vcn_level_nodes: List[Node] = []
            unknown_subnet_nodes: List[Node] = []
            for n in comp_nodes:
                if _is_node_type(n, "Vcn", "Subnet"):
                    continue
                ocid = str(n.get("nodeId") or "")
                if not ocid:
                    continue
                att = attach_by_res.get(ocid)
                vcn_match = False
                if att and att.vcn_ocid == vcn_ocid:
                    vcn_match = True
                    if att.subnet_ocid:
                        continue
                else:
                    meta = _node_metadata(n)
                    vcn_ref = edge_vcn_by_src.get(ocid) or _get_meta(meta, "vcn_id")
                    if isinstance(vcn_ref, str) and vcn_ref == vcn_ocid:
                        vcn_match = True
                if not vcn_match:
                    continue
                if _is_node_type(n, *_NETWORK_GATEWAY_NODETYPES):
                    gateway_nodes.append(n)
                elif _is_vcn_level_resource(n):
                    vcn_level_nodes.append(n)
                else:
                    unknown_subnet_nodes.append(n)

            if gateway_nodes:
                gateways_id = _service_id("gateways_", vcn_ocid)
                lines.append(f"    group {gateways_id}(cloud)[{_arch_label('Gateways', max_len=24)}] in {vcn_group_id}")
                for n in sorted(gateway_nodes, key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or ""))):
                    _add_service(n, gateways_id)

            if vcn_level_nodes:
                vcn_level_id = _service_id("vcn_level_", vcn_ocid)
                lines.append(
                    f"    group {vcn_level_id}(cloud)[{_arch_label('VCN-level Resources', max_len=48)}] in {vcn_group_id}"
                )
                for n in sorted(vcn_level_nodes, key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or ""))):
                    _add_service(n, vcn_level_id)

            vcn_subnet_ids: Set[str] = set()
            for n in comp_nodes:
                if _is_node_type(n, "Subnet") and n.get("nodeId"):
                    sn_id = str(n.get("nodeId") or "")
                    if subnet_to_vcn.get(sn_id) == vcn_ocid:
                        vcn_subnet_ids.add(sn_id)
                att = attach_by_res.get(str(n.get("nodeId") or ""))
                if att and att.subnet_ocid:
                    vcn_subnet_ids.add(att.subnet_ocid)

            for sn_ocid in sorted(vcn_subnet_ids):
                sn = node_by_id.get(sn_ocid, {"name": sn_ocid, "nodeType": "Subnet"})
                subnet_group_id = _service_id("subnet_", f"{cid}:{vcn_ocid}:{sn_ocid}")
                lines.append(f"    group {subnet_group_id}(cloud)[{_arch_label(_subnet_label(sn), max_len=80)}] in {vcn_group_id}")
                _add_service(sn, subnet_group_id)

                attached = [
                    n
                    for n in comp_nodes
                    if attach_by_res.get(str(n.get("nodeId") or ""))
                    and attach_by_res[str(n.get("nodeId") or "")].subnet_ocid == sn_ocid
                    and not _is_node_type(n, "Vcn", "Subnet")
                ]
                for n in sorted(
                    attached,
                    key=lambda n: (
                        str(n.get("nodeCategory") or ""),
                        str(n.get("nodeType") or ""),
                        str(n.get("name") or ""),
                    ),
                ):
                    _add_service(n, subnet_group_id)

            if unknown_subnet_nodes:
                unknown_id = _service_id("subnet_unknown_", f"{cid}:{vcn_ocid}")
                lines.append(f"    group {unknown_id}(cloud)[{_arch_label('Subnet: Unknown', max_len=40)}] in {vcn_group_id}")
                for n in sorted(unknown_subnet_nodes, key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or ""))):
                    _add_service(n, unknown_id)

        out_nodes: List[Node] = []
        for n in comp_nodes:
            if _is_node_type(n, "Vcn", "Subnet"):
                continue
            ocid = str(n.get("nodeId") or "")
            att = attach_by_res.get(ocid)
            if att and att.vcn_ocid:
                continue
            out_nodes.append(n)

        lane_groups = _group_nodes_by_lane(out_nodes)
        for lane, lane_nodes in lane_groups.items():
            lane_group_id = _service_id(f"lane_out_{lane}_", f"{cid}:{lane}")
            lines.append(f"    group {lane_group_id}(cloud)[{_arch_label(_lane_label(lane), max_len=40)}] in {out_group_id}")
            for n in sorted(
                lane_nodes,
                key=lambda n: (str(n.get("nodeCategory") or ""), str(n.get("nodeType") or ""), str(n.get("name") or "")),
            ):
                _add_service(n, lane_group_id)

        overlay_nodes = [n for n in comp_nodes if n.get("nodeId")]
        overlay_groups = _group_nodes_by_lane(overlay_nodes)
        if overlay_groups:
            overlay_id = _service_id("overlay_", f"{cid}:overlays")
            lines.append(
                f"    group {overlay_id}(cloud)[{_arch_label('Functional Overlays', max_len=40)}] in {comp_group_id}"
            )
            for lane, lane_nodes in overlay_groups.items():
                lane_id = _service_id("overlay_lane_", f"{cid}:{lane}")
                lines.append(
                    f"    group {lane_id}(cloud)[{_arch_label(_lane_label(lane), max_len=40)}] in {overlay_id}"
                )
                for n in sorted(
                    lane_nodes,
                    key=lambda n: (str(n.get("nodeCategory") or ""), str(n.get("nodeType") or ""), str(n.get("name") or "")),
                ):
                    ocid = str(n.get("nodeId") or "")
                    if not ocid:
                        continue
                    canonical_id = node_service_ids.get(ocid)
                    if not canonical_id:
                        continue
                    overlay_sid = _service_id("overlay_node_", f"{cid}:{lane}:{ocid}")
                    label = _arch_label(_arch_node_label(n), max_len=None)
                    icon = _service_icon(n)
                    lines.append(f"    service {overlay_sid}({icon})[{label}] in {lane_id}")
                    _add_arch_edge(overlay_sid, canonical_id)

    external_group_id = ""
    internet_id = ""
    oci_services_id = ""
    customer_net_id = ""

    if gateway_service_ids:
        external_group_id = _service_id("external_", "external")
        lines.append(f"    group {external_group_id}(cloud)[{_arch_label('External', max_len=24)}] in {tenancy_id}")

        has_internet = False
        has_service = False
        has_customer_net = False
        for ocid, sid in gateway_service_ids.items():
            node = node_by_id.get(ocid, {})
            if _is_node_type(node, "InternetGateway", "NatGateway"):
                has_internet = True
            if _is_node_type(node, "ServiceGateway"):
                has_service = True
            if _is_node_type(node, "Drg", "VirtualCircuit", "IPSecConnection", "Cpe"):
                has_customer_net = True

        if has_internet:
            internet_id = _service_id("internet_", "internet")
            lines.append(f"    service {internet_id}(cloud)[{_arch_label('Internet', max_len=24)}] in {external_group_id}")
        if has_service:
            oci_services_id = _service_id("oci_services_", "oci_services")
            lines.append(f"    service {oci_services_id}(cloud)[{_arch_label('OCI Services', max_len=24)}] in {external_group_id}")
        if has_customer_net:
            customer_net_id = _service_id("customer_net_", "customer_net")
            lines.append(f"    service {customer_net_id}(cloud)[{_arch_label('Customer Network', max_len=32)}] in {external_group_id}")

    legend_id = _service_id("legend_", "legend")
    lines.append(f"    group {legend_id}(cloud)[{_arch_label('Legend', max_len=24)}] in {tenancy_id}")
    legend_items = [
        ("External", "cloud"),
        ("Compute", "server"),
        ("Network", "cloud"),
        ("Storage", "database"),
        ("Policy / IAM", "server"),
        ("Overlay", "cloud"),
        ("Other", "server"),
    ]
    for label, icon in legend_items:
        sid = _service_id("legend_item_", label)
        lines.append(f"    service {sid}({icon})[{_arch_label(label, max_len=24)}] in {legend_id}")

    if gateway_service_ids:
        for ocid, sid in gateway_service_ids.items():
            node = node_by_id.get(ocid, {})
            if _is_node_type(node, "InternetGateway") and internet_id:
                _add_arch_edge(internet_id, sid)
            if _is_node_type(node, "NatGateway") and internet_id:
                _add_arch_edge(sid, internet_id)
            if _is_node_type(node, "ServiceGateway") and oci_services_id:
                _add_arch_edge(sid, oci_services_id)
            if _is_node_type(node, "Drg", "VirtualCircuit", "IPSecConnection", "Cpe") and customer_net_id:
                _add_arch_edge(sid, customer_net_id)

    rel_lines = _render_arch_relationship_edges(
        edges,
        node_ids=rendered_node_ids,
        node_id_map=node_service_ids,
        include_admin_edges=True,
        seen_pairs=seen_arch_edges,
    )
    lines.extend(rel_lines)

    consolidated.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return consolidated
