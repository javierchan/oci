from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .graph import Edge, Node
from ..normalize.transform import group_workloads
from ..util.errors import ExportError


_NON_ARCH_LEAF_NODETYPES: Set[str] = {
    "network.Vnic",
    "Vnic",
    "PrivateIp",
    "Image",
    "compute.Image",
    "compute.BootVolume",
    "compute.BlockVolume",
    "BootVolume",
    "BlockVolume",
}


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

_EDGE_RELATIONS_FOR_PROJECTIONS: Set[str] = {
    "IN_VCN",
    "IN_SUBNET",
    "IN_VNIC",
    "USES_ROUTE_TABLE",
    "USES_SECURITY_LIST",
    "USES_NSG",
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


def _mermaid_label_for(node: Node) -> str:
    name = str(node.get("name") or "").strip()
    node_type = str(node.get("nodeType") or "").strip()

    if not name:
        name = _short_ocid(str(node.get("nodeId") or ""))

    # If a placeholder compartment node was synthesized, avoid printing the full OCID.
    if _is_node_type(node, "Compartment") and name.startswith("ocid1"):
        name = f"Compartment {_short_ocid(name)}"

    if node_type and node_type != "Compartment":
        label = f"{name}<br>{node_type}"
    else:
        label = name

    return label.replace('"', "'")


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
    if cat == "network" or _is_node_type(node, "Vcn", "Subnet", "InternetGateway", "NatGateway", "ServiceGateway"):
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


def _render_edge(src: str, dst: str, label: str | None = None, *, dotted: bool = False) -> str:
    arrow = "-.->" if dotted else "-->"
    if label:
        safe = str(label).replace('"', "'")
        return f"  {src} {arrow}|{safe}| {dst}"
    return f"  {src} {arrow} {dst}"


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
    allowlist: Set[str],
) -> List[str]:
    out: List[str] = []
    seen: Set[Tuple[str, str, str]] = set()
    for edge in sorted(edges, key=_edge_sort_key):
        rel = str(edge.get("relation_type") or "")
        if rel not in allowlist:
            continue
        src = str(edge.get("source_ocid") or "")
        dst = str(edge.get("target_ocid") or "")
        if not src or not dst:
            continue
        if src not in node_ids or dst not in node_ids:
            continue
        src_id = node_id_map.get(src, _mermaid_id(src))
        dst_id = node_id_map.get(dst, _mermaid_id(dst))
        key = (src_id, rel, dst_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(_render_edge(src_id, dst_id, rel))
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


def _derived_attachments(nodes: Sequence[Node], edges: Sequence[Edge] | None = None) -> List[_DerivedAttachment]:
    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}

    # Index VNICs to help attach instances -> subnet/vcn.
    vnic_meta_by_id: Dict[str, Mapping[str, Any]] = {}
    for n in nodes:
        if _is_node_type(n, "Vnic"):
            vnic_meta_by_id[str(n.get("nodeId") or "")] = _node_metadata(n)

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
    shown: List[Node] = []
    for n in nodes:
        nt = str(n.get("nodeType") or "")
        if nt in _NON_ARCH_LEAF_NODETYPES:
            continue
        # Tenancy view is high-level: omit network control-plane detail.
        if nt in _NETWORK_CONTROL_NODETYPES:
            continue
        shown.append(n)
    return shown


def _write_tenancy_view(outdir: Path, nodes: Sequence[Node], edges: Sequence[Edge]) -> Path:
    path = outdir / "diagram.tenancy.mmd"

    shown_nodes = _tenancy_nodes_to_show(nodes)
    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}
    rendered_node_ids: Set[str] = set()
    edge_node_id_map: Dict[str, str] = {}

    # Group by compartmentId (or unknown). Keep both "shown" and "all" sets.
    comps_shown: Dict[str, List[Node]] = {}
    comps_all: Dict[str, List[Node]] = {}
    for n in nodes:
        cid = str(n.get("compartmentId") or "")
        if not cid and _is_node_type(n, "Compartment"):
            cid = str(n.get("nodeId") or "")
        comps_all.setdefault(cid or "UNKNOWN", []).append(n)
    for n in shown_nodes:
        cid = str(n.get("compartmentId") or "")
        if not cid and _is_node_type(n, "Compartment"):
            cid = str(n.get("nodeId") or "")
        comps_shown.setdefault(cid or "UNKNOWN", []).append(n)

    # Stable order.
    comp_ids = sorted(comps_all.keys())

    lines: List[str] = ["flowchart TD"]
    lines.extend(_style_block_lines())
    lines.append("%% ------------------ Tenancy / Compartments ------------------")
    lines.append("TEN_ROOT((Tenancy / Compartments))")
    lines.append("class TEN_ROOT boundary")

    # Render compartments as subgraphs.
    for cid in comp_ids:
        label = "Compartment: Unknown" if cid == "UNKNOWN" else _compartment_label(node_by_id.get(cid, {"name": cid}))
        sg_id = _mermaid_id(f"comp:{cid}")
        lines.append(f"  subgraph {sg_id}[\"{label.replace('"', "'")}\"]")
        lines.append("    direction TB")

        # Within compartment, keep only a high-signal subset.
        comp_nodes = sorted(
            comps_shown.get(cid, []),
            key=lambda n: (
                str(n.get("nodeCategory") or ""),
                str(n.get("nodeType") or ""),
                str(n.get("name") or ""),
            ),
        )
        # Cap the number of nodes per compartment to avoid unreadable diagrams.
        rendered_ocids: Set[str] = set()
        rendered = 0
        cap = 18
        for n in comp_nodes:
            # Skip the compartment node itself (boundary label already covers it).
            if _is_node_type(n, "Compartment"):
                continue
            if rendered >= cap:
                break
            nid = _mermaid_id(str(n.get("nodeId") or ""))
            if n.get("nodeId"):
                rendered_ocids.add(str(n.get("nodeId") or ""))
            cls = _node_class(n)
            shape = _node_shape(n)
            lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls=cls, shape=shape))
            if n.get("nodeId"):
                raw_id = str(n.get("nodeId") or "")
                rendered_node_ids.add(raw_id)
                edge_node_id_map.setdefault(raw_id, nid)
            rendered += 1

        # Summarize everything else in the compartment, including leaf/control-plane resources.
        all_nodes = [n for n in comps_all.get(cid, []) if not _is_node_type(n, "Compartment")]
        omitted = [
            n
            for n in all_nodes
            if str(n.get("nodeId") or "") and str(n.get("nodeId") or "") not in rendered_ocids
        ]
        if omitted:
            total_id = _mermaid_id(f"comp:{cid}:omitted_total")
            lines.extend(
                _render_node_with_class(
                    total_id,
                    f"Other resources (not shown): {len(omitted)}",
                    cls="summary",
                )
            )
            _render_omitted_type_summaries(lines, prefix=f"comp:{cid}", omitted_nodes=omitted, max_types=6)
        lines.append("  end")

    # Minimal flow hints across major roles.
    # Connect compute-like things to network and data resources within the same compartment.
    by_comp: Dict[str, Dict[str, List[Node]]] = {}
    for n in shown_nodes:
        cid = str(n.get("compartmentId") or "")
        by_comp.setdefault(cid or "UNKNOWN", {}).setdefault(str(n.get("nodeType") or ""), []).append(n)

    for cid, _typed in by_comp.items():
        compute_nodes = [
            n
            for n in shown_nodes
            if (str(n.get("compartmentId") or "") or "UNKNOWN") == cid and str(n.get("nodeCategory") or "") == "compute"
        ]
        vcn_nodes = [
            n
            for n in shown_nodes
            if (str(n.get("compartmentId") or "") or "UNKNOWN") == cid and _is_node_type(n, "Vcn")
        ]
        bucket_nodes = [
            n
            for n in shown_nodes
            if (str(n.get("compartmentId") or "") or "UNKNOWN") == cid and _is_node_type(n, "Bucket")
        ]

        for c in compute_nodes:
            c_id = _mermaid_id(str(c.get("nodeId") or ""))
            for vcn in vcn_nodes:
                v_id = _mermaid_id(str(vcn.get("nodeId") or ""))
                lines.append(_render_edge(c_id, v_id, "uses network inferred", dotted=True))
            for b in bucket_nodes:
                b_id = _mermaid_id(str(b.get("nodeId") or ""))
                lines.append(_render_edge(c_id, b_id, "reads/writes inferred", dotted=True))

    rel_lines = _render_relationship_edges(
        edges,
        node_ids=rendered_node_ids,
        node_id_map=edge_node_id_map,
        allowlist=_EDGE_RELATIONS_FOR_PROJECTIONS,
    )
    lines.extend(rel_lines)

    # Context links (root -> compartments)
    for cid in comp_ids:
        sg_id = _mermaid_id(f"comp:{cid}")
        lines.append(f"TEN_ROOT -.-> {sg_id}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_network_views(outdir: Path, nodes: Sequence[Node], edges: Sequence[Edge]) -> List[Path]:
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
    res_to_attach: Dict[str, _DerivedAttachment] = {a.resource_ocid: a for a in attachments}

    out_paths: List[Path] = []

    for vcn in sorted(vcns, key=lambda n: str(n.get("name") or "")):
        vcn_ocid = str(vcn.get("nodeId") or "")
        vcn_name = str(vcn.get("name") or "vcn").strip() or "vcn"
        fname = f"diagram.network.{_slugify(vcn_name)}.mmd"
        path = outdir / fname

        lines: List[str] = ["flowchart LR"]
        lines.extend(_style_block_lines())
        lines.append("%% ------------------ Network Topology ------------------")
        net_root = f"NET_{_slugify(vcn_name)}_ROOT"
        lines.append(f"{net_root}((Network Topology: {vcn_name}))")
        lines.append(f"class {net_root} boundary")

        internet_id = _mermaid_id("external:internet")
        lines.extend(_render_node_with_class(internet_id, "Internet", cls="external", shape="round"))

        vcn_id = _mermaid_id(vcn_ocid)
        rendered_node_ids: Set[str] = set()
        edge_node_id_map: Dict[str, str] = {}
        if vcn_ocid:
            rendered_node_ids.add(vcn_ocid)
            edge_node_id_map[vcn_ocid] = vcn_id
        lines.append(f"  subgraph {vcn_id}[\"{_vcn_label(vcn).replace('"', "'")}\"]")
        lines.append("    direction TB")

        # Gateways inside VCN.
        gateways = []
        for n in nodes:
            if not _is_node_type(n, "InternetGateway", "NatGateway", "ServiceGateway"):
                continue
            meta = _node_metadata(n)
            nid = str(n.get("nodeId") or "")
            vcn_ref = edge_vcn_by_src.get(nid) or _get_meta(meta, "vcn_id")
            if isinstance(vcn_ref, str) and vcn_ref == vcn_ocid:
                gateways.append(n)
        for g in sorted(gateways, key=lambda n: str(n.get("name") or "")):
            gid = _mermaid_id(str(g.get("nodeId") or ""))
            lines.extend(_render_node_with_class(gid, _mermaid_label_for(g), cls=_node_class(g), shape=_node_shape(g)))
            if g.get("nodeId"):
                rendered_node_ids.add(str(g.get("nodeId") or ""))

        # Network control-plane primitives (route tables, security lists, NSGs, DHCP).
        control = []
        for n in nodes:
            nt = str(n.get("nodeType") or "")
            if nt not in _NETWORK_CONTROL_NODETYPES:
                continue
            meta = _node_metadata(n)
            nid = str(n.get("nodeId") or "")
            vcn_ref = edge_vcn_by_src.get(nid) or _get_meta(meta, "vcn_id")
            if isinstance(vcn_ref, str) and vcn_ref == vcn_ocid:
                control.append(n)

        control_sorted = sorted(control, key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")))
        kept_control, omitted_control = _keep_and_omitted(control_sorted, keep=4)
        for n in kept_control:
            nid = _mermaid_id(str(n.get("nodeId") or ""))
            lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls="network", shape="rect"))
            if n.get("nodeId"):
                rendered_node_ids.add(str(n.get("nodeId") or ""))
        if omitted_control:
            sid = _mermaid_id(f"vcn:{vcn_ocid}:control_summary")
            lines.extend(
                _render_node_with_class(
                    sid,
                    f"Other network controls... and {len(omitted_control)} more",
                    cls="summary",
                )
            )

        # Subnets inside VCN.
        vcn_subnets = [sn for sn in subnets if subnet_to_vcn.get(str(sn.get("nodeId") or "")) == vcn_ocid]
        for sn in sorted(vcn_subnets, key=lambda n: str(n.get("name") or "")):
            sn_ocid = str(sn.get("nodeId") or "")
            sn_id = _mermaid_id(sn_ocid)
            if sn_ocid:
                rendered_node_ids.add(sn_ocid)
                edge_node_id_map.setdefault(sn_ocid, sn_id)
            lines.append(f"    subgraph {sn_id}[\"{_subnet_label(sn).replace('"', "'")}\"]")
            lines.append("      direction TB")

            # Workloads/resources attached to this subnet.
            attached: List[Node] = []
            for n in nodes:
                nt = str(n.get("nodeType") or "")
                if nt in _NON_ARCH_LEAF_NODETYPES:
                    continue
                if _is_node_type(n, "Subnet", "Vcn"):
                    continue
                att = res_to_attach.get(str(n.get("nodeId") or ""))
                if att and att.subnet_ocid == sn_ocid:
                    attached.append(n)

            key_nodes: List[Node] = []
            leaf_nodes: List[Node] = []
            for a in sorted(
                attached,
                key=lambda n: (
                    str(n.get("nodeCategory") or ""),
                    str(n.get("nodeType") or ""),
                    str(n.get("name") or ""),
                ),
            ):
                if str(a.get("nodeCategory") or "") in {"compute", "network", "security"} or _is_node_type(a, "Bucket", "Policy"):
                    key_nodes.append(a)
                else:
                    leaf_nodes.append(a)

            # Render key nodes with a cap.
            cap = 8
            for a in key_nodes[:cap]:
                aid = _mermaid_id(str(a.get("nodeId") or ""))
                lines.extend(_render_node_with_class(aid, _mermaid_label_for(a), cls=_node_class(a), shape=_node_shape(a)))
                if a.get("nodeId"):
                    rendered_node_ids.add(str(a.get("nodeId") or ""))

            if len(key_nodes) > cap:
                summary_id = _mermaid_id(f"subnet:{sn_ocid}:key_summary")
                lines.extend(
                    _render_node_with_class(
                        summary_id,
                        f"Other key resources... and {len(key_nodes) - cap} more",
                        cls="summary",
                    )
                )

            # Render leaf resources in aggregated form.
            if leaf_nodes:
                kept, summary = _summarize_many(leaf_nodes, title="Other leaf resources", keep=2)
                for a in kept:
                    aid = _mermaid_id(str(a.get("nodeId") or ""))
                    lines.extend(_render_node_with_class(aid, _mermaid_label_for(a), cls="boundary", shape="rect"))
                    if a.get("nodeId"):
                        rendered_node_ids.add(str(a.get("nodeId") or ""))
                if summary:
                    sid = _mermaid_id(f"subnet:{sn_ocid}:leaf_summary")
                    lines.extend(_render_node_with_class(sid, summary, cls="summary"))

            # Always include a compact IP/VNIC summary if present (these are often filtered out).
            ip_vnic_counts: Dict[str, int] = {"Vnic": 0, "PrivateIp": 0, "PublicIp": 0}
            for n in nodes:
                if not (_is_node_type(n, "Vnic") or _is_node_type(n, "PrivateIp") or _is_node_type(n, "PublicIp")):
                    continue
                att = res_to_attach.get(str(n.get("nodeId") or ""))
                if att and att.subnet_ocid == sn_ocid:
                    if _is_node_type(n, "Vnic"):
                        ip_vnic_counts["Vnic"] += 1
                    elif _is_node_type(n, "PrivateIp"):
                        ip_vnic_counts["PrivateIp"] += 1
                    elif _is_node_type(n, "PublicIp"):
                        ip_vnic_counts["PublicIp"] += 1

            if any(ip_vnic_counts.values()):
                sid = _mermaid_id(f"subnet:{sn_ocid}:ip_vnic")
                label = (
                    f"IPs / VNICs<br>VNICs: {ip_vnic_counts['Vnic']}, "
                    f"Private IPs: {ip_vnic_counts['PrivateIp']}, "
                    f"Public IPs: {ip_vnic_counts['PublicIp']}"
                )
                lines.extend(_render_node_with_class(sid, label, cls="summary", shape="rect"))

            lines.append("    end")

        lines.append("  end")

        rel_lines = _render_relationship_edges(
            edges,
            node_ids=rendered_node_ids,
            node_id_map=edge_node_id_map,
            allowlist=_EDGE_RELATIONS_FOR_PROJECTIONS,
        )
        lines.extend(rel_lines)

        # Flows: Internet -> IGW -> public subnets; private subnets -> NAT; private -> SGW.
        igw = next((g for g in gateways if _is_node_type(g, "InternetGateway")), None)
        nat = next((g for g in gateways if _is_node_type(g, "NatGateway")), None)
        sgw = next((g for g in gateways if _is_node_type(g, "ServiceGateway")), None)

        if igw is not None:
            igw_id = _mermaid_id(str(igw.get("nodeId") or ""))
            lines.append(_render_edge(internet_id, igw_id, "ingress/egress inferred", dotted=True))

        # Context link from view root.
        lines.append(f"{net_root} -.-> {vcn_id}")

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


def _write_workload_views(outdir: Path, nodes: Sequence[Node], edges: Sequence[Edge]) -> List[Path]:
    # Identify candidate workloads using shared grouping logic.
    candidates: List[Node] = []
    for n in nodes:
        nt = str(n.get("nodeType") or "")
        if nt in _NON_ARCH_LEAF_NODETYPES:
            continue
        if _is_node_type(n, "Compartment"):
            continue
        candidates.append(n)

    wl_to_nodes = {k: list(v) for k, v in group_workloads(candidates).items()}

    if not wl_to_nodes:
        return []

    # Build attachments for optional network context.
    attachments = _derived_attachments(nodes, edges)
    attach_by_res: Dict[str, _DerivedAttachment] = {a.resource_ocid: a for a in attachments}

    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}

    out_paths: List[Path] = []

    for wl_name in sorted(wl_to_nodes.keys(), key=lambda s: s.lower()):
        wl_nodes = wl_to_nodes[wl_name]

        path = outdir / f"diagram.workload.{_slugify(wl_name)}.mmd"

        lines: List[str] = ["flowchart TD"]
        lines.extend(_style_block_lines())
        lines.append("%% ------------------ Workload / Application View ------------------")

        wl_root = f"WL_{_slugify(wl_name)}_ROOT"
        lines.append(f"{wl_root}((Workload View: {wl_name}))")
        lines.append(f"class {wl_root} boundary")

        users_id = _mermaid_id(f"external:users:{wl_name}")
        lines.extend(_render_node_with_class(users_id, "Users", cls="external", shape="round"))

        services_id = _mermaid_id(f"external:oci_services:{wl_name}")
        lines.extend(_render_node_with_class(services_id, "OCI Services", cls="external", shape="round"))

        rendered_node_ids: Set[str] = set()
        edge_node_id_map: Dict[str, str] = {}

        # Group by compartment.
        comps: Dict[str, List[Node]] = {}
        for n in wl_nodes:
            cid = str(n.get("compartmentId") or "") or "UNKNOWN"
            comps.setdefault(cid, []).append(n)

        for cid in sorted(comps.keys()):
            comp_label = "Compartment: Unknown" if cid == "UNKNOWN" else _compartment_label(node_by_id.get(cid, {"name": cid}))
            sg_id = _mermaid_id(f"workload:{wl_name}:comp:{cid}")
            lines.append(f"  subgraph {sg_id}[\"{comp_label.replace('"', "'")}\"]")
            lines.append("    direction TB")

            # Add optional VCN/subnet boundaries for nodes that have attachments.
            # Keep it simple: one level of VCN, then subnets.
            vcn_to_subnets: Dict[str, Set[str]] = {}
            for n in comps[cid]:
                att = attach_by_res.get(str(n.get("nodeId") or ""))
                if att and att.vcn_ocid:
                    if att.subnet_ocid:
                        vcn_to_subnets.setdefault(att.vcn_ocid, set()).add(att.subnet_ocid)
                    else:
                        vcn_to_subnets.setdefault(att.vcn_ocid, set())

            # Render resources not tied to a VCN/subnet.
            untied: List[Node] = []
            for n in comps[cid]:
                att = attach_by_res.get(str(n.get("nodeId") or ""))
                if not att or not att.vcn_ocid:
                    untied.append(n)

            # Split untied resources into key nodes and repetitive leaf nodes.
            untied_sorted = sorted(untied, key=_instance_first_sort_key)
            untied_key: List[Node] = []
            untied_leaf: List[Node] = []
            for u in untied_sorted:
                if _is_media_like(u) or str(u.get("nodeCategory") or "") == "other":
                    untied_leaf.append(u)
                else:
                    untied_key.append(u)

            for u in untied_key[:10]:
                uid = _mermaid_id(str(u.get("nodeId") or ""))
                lines.extend(_render_node_with_class(uid, _mermaid_label_for(u), cls=_node_class(u), shape=_node_shape(u)))
                if u.get("nodeId"):
                    rendered_node_ids.add(str(u.get("nodeId") or ""))

            if len(untied_key) > 10:
                sid = _mermaid_id(f"workload:{wl_name}:comp:{cid}:untied_key_summary")
                lines.extend(
                    _render_node_with_class(
                        sid,
                        f"Other key resources... and {len(untied_key) - 10} more",
                        cls="summary",
                    )
                )

            if untied_leaf:
                kept, summary = _summarize_many(untied_leaf, title="Other media/leaf items", keep=2)
                for u in kept:
                    uid = _mermaid_id(str(u.get("nodeId") or ""))
                    lines.extend(_render_node_with_class(uid, _mermaid_label_for(u), cls="boundary", shape="rect"))
                    if u.get("nodeId"):
                        rendered_node_ids.add(str(u.get("nodeId") or ""))
                if summary:
                    sid = _mermaid_id(f"workload:{wl_name}:comp:{cid}:untied_leaf_summary")
                    lines.extend(_render_node_with_class(sid, summary, cls="summary"))

            for vcn_ocid in sorted(vcn_to_subnets.keys()):
                vcn = node_by_id.get(vcn_ocid)
                vcn_label = _vcn_label(vcn) if vcn else f"VCN {_short_ocid(vcn_ocid)}"
                vcn_id = _mermaid_id(f"workload:{wl_name}:vcn:{vcn_ocid}")
                if vcn_ocid:
                    rendered_node_ids.add(vcn_ocid)
                    edge_node_id_map.setdefault(vcn_ocid, vcn_id)
                lines.append(f"    subgraph {vcn_id}[\"{vcn_label.replace('"', "'")}\"]")
                lines.append("      direction TB")

                for sn_ocid in sorted(vcn_to_subnets[vcn_ocid]):
                    sn = node_by_id.get(sn_ocid)
                    sn_label = _subnet_label(sn) if sn else f"Subnet {_short_ocid(sn_ocid)}"
                    sn_id = _mermaid_id(f"workload:{wl_name}:subnet:{sn_ocid}")
                    if sn_ocid:
                        rendered_node_ids.add(sn_ocid)
                        edge_node_id_map.setdefault(sn_ocid, sn_id)
                    lines.append(f"      subgraph {sn_id}[\"{sn_label.replace('"', "'")}\"]")
                    lines.append("        direction TB")

                    attached = [
                        n
                        for n in comps[cid]
                        if attach_by_res.get(str(n.get("nodeId") or ""))
                        and attach_by_res[str(n.get("nodeId") or "")].subnet_ocid == sn_ocid
                    ]

                    attached_sorted = sorted(
                        attached,
                        key=lambda n: (
                            str(n.get("nodeCategory") or ""),
                            str(n.get("nodeType") or ""),
                            str(n.get("name") or ""),
                        ),
                    )

                    key_nodes: List[Node] = []
                    leaf_nodes: List[Node] = []
                    for a in attached_sorted:
                        if _is_media_like(a):
                            leaf_nodes.append(a)
                        else:
                            key_nodes.append(a)

                    key_nodes_sorted = sorted(key_nodes, key=_instance_first_sort_key)

                    for a in key_nodes_sorted[:8]:
                        aid = _mermaid_id(str(a.get("nodeId") or ""))
                        lines.extend(_render_node_with_class(aid, _mermaid_label_for(a), cls=_node_class(a), shape=_node_shape(a)))
                        if a.get("nodeId"):
                            rendered_node_ids.add(str(a.get("nodeId") or ""))

                    if len(key_nodes_sorted) > 8:
                        sid = _mermaid_id(f"workload:{wl_name}:comp:{cid}:subnet:{sn_ocid}:key_summary")
                        lines.extend(
                            _render_node_with_class(
                                sid,
                                f"Other key resources... and {len(key_nodes_sorted) - 8} more",
                                cls="summary",
                            )
                        )

                    if leaf_nodes:
                        kept, summary = _summarize_many(leaf_nodes, title="Other media/leaf items", keep=2)
                        for a in kept:
                            aid = _mermaid_id(str(a.get("nodeId") or ""))
                            lines.extend(_render_node_with_class(aid, _mermaid_label_for(a), cls="boundary", shape="rect"))
                            if a.get("nodeId"):
                                rendered_node_ids.add(str(a.get("nodeId") or ""))
                        if summary:
                            sid = _mermaid_id(f"workload:{wl_name}:comp:{cid}:subnet:{sn_ocid}:leaf_summary")
                            lines.extend(_render_node_with_class(sid, summary, cls="summary"))

                    lines.append("      end")

                lines.append("    end")

            lines.append("  end")

        # Add workload-centric flows.
        # Users -> LoadBalancers / API-like entry points; compute -> buckets.
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

        for c in computes_sorted:
            c_id = _mermaid_id(str(c.get("nodeId") or ""))
            if not buckets:
                continue
            for b in buckets:
                b_id = _mermaid_id(str(b.get("nodeId") or ""))
                lines.append(_render_edge(c_id, b_id, "reads/writes inferred", dotted=True))

        for b in buckets:
            b_id = _mermaid_id(str(b.get("nodeId") or ""))
            lines.append(_render_edge(b_id, services_id, "Object Storage inferred", dotted=True))

        rel_lines = _render_relationship_edges(
            edges,
            node_ids=rendered_node_ids,
            node_id_map=edge_node_id_map,
            allowlist=_EDGE_RELATIONS_FOR_PROJECTIONS,
        )
        lines.extend(rel_lines)

        # Context links
        lines.append(f"{wl_root} -.-> {users_id}")
        lines.append(f"{wl_root} -.-> {services_id}")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out_paths.append(path)

    return out_paths


def write_diagram_projections(outdir: Path, nodes: Sequence[Node], edges: Sequence[Edge]) -> List[Path]:
    # Edges drive placement and relationship hints in projections.
    out: List[Path] = []
    out.append(_write_tenancy_view(outdir, nodes, edges))
    out.extend(_write_network_views(outdir, nodes, edges))
    out.extend(_write_workload_views(outdir, nodes, edges))

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

    # Heuristic lane classification for "other" types.
    low = t.lower()
    if any(k in low for k in ("policy", "dynamicgroup", "dynamic_group", "group", "user", "identity")):
        return "iam"
    if any(k in low for k in ("bucket", "database", "dbsystem", "stream", "queue", "topic")):
        return "data"
    if any(k in low for k in ("alarm", "event", "notification", "log", "metric")):
        return "observability"

    return "other"


def _write_consolidated_mermaid(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    diagram_paths: Sequence[Path],
) -> Path:
    consolidated = outdir / "diagram.consolidated.mmd"

    # Landing-page consolidated diagram (swimlanes). This does NOT attempt to show all
    # resources; it shows key resources + summaries and points to detailed per-view
    # diagrams (network/workload) via stable anchor nodes.

    # Deterministic ordering of view artifacts.
    def _order_key(p: Path) -> Tuple[int, str]:
        n = p.name
        if n == "diagram.tenancy.mmd":
            return (0, n)
        if n.startswith("diagram.network."):
            return (1, n)
        if n.startswith("diagram.workload."):
            return (2, n)
        return (9, n)

    mmds = [p for p in diagram_paths if p.suffix == ".mmd" and p.exists() and p.name != consolidated.name]
    mmds_sorted = sorted(mmds, key=_order_key)
    workload_views = [
        p.name[len("diagram.workload.") : -len(".mmd")]
        for p in mmds_sorted
        if p.name.startswith("diagram.workload.") and p.name.endswith(".mmd")
    ]

    # Index nodes for selection.
    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if str(n.get("nodeId") or "")}
    edge_vcn_by_src = _edge_single_target_map(edges, "IN_VCN")

    def _vcn_ref_for(node: Node) -> str:
        nid = str(node.get("nodeId") or "")
        meta = _node_metadata(node)
        ref = edge_vcn_by_src.get(nid) or _get_meta(meta, "vcn_id")
        return str(ref or "")
    comp_nodes = [n for n in nodes if _is_node_type(n, "Compartment")]
    comp_nodes_sorted = sorted(comp_nodes, key=lambda n: str(n.get("nodeId") or ""))

    # Lane buckets.
    lanes: Dict[str, List[Node]] = {"iam": [], "network": [], "security": [], "app": [], "data": [], "observability": [], "other": []}
    for n in nodes:
        lane = _lane_for_node(n)
        if lane in lanes:
            lanes[lane].append(n)

    # Precompute which OCIDs are explicitly represented on the landing page so that the
    # coverage summary doesn't double-count resources rendered in other swimlanes.
    represented_ocids: Set[str] = set()

    for c in comp_nodes_sorted[:8]:
        cid = str(c.get("nodeId") or "")
        if cid:
            represented_ocids.add(cid)

    iam_nodes = sorted(lanes["iam"], key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")))
    iam_kept, _ = _keep_and_omitted(iam_nodes, keep=6)
    for n in iam_kept:
        if n.get("nodeId"):
            represented_ocids.add(str(n.get("nodeId") or ""))

    sec_nodes = sorted(lanes["security"], key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")))
    sec_kept, _ = _keep_and_omitted(sec_nodes, keep=6)
    for n in sec_kept:
        if n.get("nodeId"):
            represented_ocids.add(str(n.get("nodeId") or ""))

    app_nodes = sorted(lanes["app"], key=_instance_first_sort_key)
    app_kept, _ = _keep_and_omitted(app_nodes, keep=8)
    for n in app_kept:
        if n.get("nodeId"):
            represented_ocids.add(str(n.get("nodeId") or ""))

    data_nodes = sorted(lanes["data"], key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")))
    data_kept, _ = _keep_and_omitted(data_nodes, keep=8)
    for n in data_kept:
        if n.get("nodeId"):
            represented_ocids.add(str(n.get("nodeId") or ""))

    obs_nodes = sorted(lanes["observability"], key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")))
    obs_kept, _ = _keep_and_omitted(obs_nodes, keep=6)
    for n in obs_kept:
        if n.get("nodeId"):
            represented_ocids.add(str(n.get("nodeId") or ""))

    # Network lane represents VCNs even when they only appear as a subgraph label.
    vcn_nodes = [n for n in nodes if _is_node_type(n, "Vcn")]
    vcn_sorted = sorted(vcn_nodes, key=lambda n: str(n.get("name") or ""))
    for vcn in vcn_sorted[:4]:
        vcn_ocid = str(vcn.get("nodeId") or "")
        if vcn_ocid:
            represented_ocids.add(vcn_ocid)
        for gtype in ("InternetGateway", "NatGateway", "ServiceGateway"):
            gws = []
            for n in nodes:
                if not _is_node_type(n, gtype):
                    continue
                vcn_ref = _vcn_ref_for(n)
                if vcn_ref:
                    if vcn_ref == vcn_ocid:
                        gws.append(n)
                    continue
                if str(n.get("compartmentId") or "") == str(vcn.get("compartmentId") or ""):
                    gws.append(n)
            if gws and gws[0].get("nodeId"):
                represented_ocids.add(str(gws[0].get("nodeId") or ""))
        subs = [n for n in nodes if _is_node_type(n, "Subnet") and _vcn_ref_for(n) == vcn_ocid]
        subs_sorted = sorted(subs, key=lambda n: str(n.get("name") or ""))
        kept_subs, _ = _keep_and_omitted(subs_sorted, keep=2)
        for sn in kept_subs:
            if sn.get("nodeId"):
                represented_ocids.add(str(sn.get("nodeId") or ""))

    # Stable, small external anchors.
    internet_id = _mermaid_id("external:internet")
    users_id = _mermaid_id("external:users")

    lines: List[str] = ["flowchart LR"]
    lines.extend(_style_block_lines())
    lines.append("%% ------------------ Consolidated Landing Page (Swimlanes) ------------------")

    # Legend lane
    lines.append('subgraph LEGEND["Legend"]')
    lines.append("  direction TB")
    lines.extend(_render_node_with_class(users_id, "Users", cls="external", shape="round"))
    lines.extend(_render_node_with_class(internet_id, "Internet", cls="external", shape="round"))
    leg_app = _mermaid_id("legend:app")
    leg_data = _mermaid_id("legend:data")
    lines.extend(_render_node_with_class(leg_app, "App / Compute", cls="compute", shape="round"))
    lines.extend(_render_node_with_class(leg_data, "Data Store", cls="storage", shape="db"))
    lines.append(_render_edge(users_id, leg_app, "requests"))
    lines.append(_render_edge(leg_app, leg_data, "reads/writes"))
    lines.append(_render_edge(users_id, internet_id, "context", dotted=True))
    lines.append("end")

    # Tenancy lane
    lines.append('subgraph TENANCY["Tenancy"]')
    lines.append("  direction TB")
    lines.append("  TEN_ROOT((Tenancy))")
    lines.append("  class TEN_ROOT boundary")

    # Track which concrete resources we explicitly render in the landing page.
    rendered_ocids: Set[str] = set()

    for c in comp_nodes_sorted[:8]:
        cid = str(c.get("nodeId") or "")
        nid = _mermaid_id(f"comp:{cid}")
        lines.extend(_render_node_with_class(nid, _mermaid_label_for(c), cls="boundary", shape="rect"))
        lines.append(_render_edge("TEN_ROOT", nid, "contains", dotted=True))
        if cid:
            rendered_ocids.add(cid)
    if len(comp_nodes_sorted) > 8:
        sid = _mermaid_id("compartments:more")
        lines.extend(_render_node_with_class(sid, f"Other compartments... and {len(comp_nodes_sorted) - 8} more", cls="summary"))
        lines.append(_render_edge("TEN_ROOT", sid, "contains", dotted=True))

    # Coverage summary: show which resource types are present but not explicitly rendered.
    # This keeps the landing page readable while ensuring no resource type disappears entirely.
    lines.append("  COV_ROOT((Inventory Coverage))")
    lines.append("  class COV_ROOT summary")
    omitted_for_coverage = [
        n
        for n in nodes
        if str(n.get("nodeId") or "")
        and str(n.get("nodeId") or "") not in represented_ocids
        and not _is_node_type(n, "Compartment")
    ]
    _render_omitted_type_summaries(lines, prefix="consolidated", omitted_nodes=omitted_for_coverage, max_types=8)
    _render_omitted_by_compartment_summary(
        lines,
        prefix="consolidated",
        omitted_nodes=omitted_for_coverage,
        node_by_id=node_by_id,
        max_compartments=4,
        max_types_per_compartment=4,
    )
    lines.append(_render_edge("TEN_ROOT", "COV_ROOT", "coverage", dotted=True))
    lines.append("end")

    # IAM lane (key IAM primitives only)
    lines.append('subgraph IAM["IAM"]')
    lines.append("  direction TB")
    lines.append("  IAM_ROOT((IAM))")
    lines.append("  class IAM_ROOT boundary")
    iam_nodes = sorted(lanes["iam"], key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")))
    kept, omitted = _keep_and_omitted(iam_nodes, keep=6)
    for n in kept:
        nid = _mermaid_id(str(n.get("nodeId") or ""))
        if n.get("nodeId"):
            rendered_ocids.add(str(n.get("nodeId") or ""))
        lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls="policy", shape="rect"))
        lines.append(_render_edge("IAM_ROOT", nid, "", dotted=True))
    if omitted:
        sid = _mermaid_id("iam:summary")
        lines.extend(_render_node_with_class(sid, f"Other IAM resources... and {len(omitted)} more", cls="summary"))
        lines.append(_render_edge("IAM_ROOT", sid, "", dotted=True))
    lines.append("end")

    # Network lane (VCNs + gateways + top subnets)
    lines.append('subgraph NETWORK["Network"]')
    lines.append("  direction TB")
    lines.append("  NET_ROOT((Network))")
    lines.append("  class NET_ROOT boundary")
    vcn_nodes = [n for n in nodes if _is_node_type(n, "Vcn")]
    vcn_sorted = sorted(vcn_nodes, key=lambda n: str(n.get("name") or ""))
    for vcn in vcn_sorted[:4]:
        vcn_ocid = str(vcn.get("nodeId") or "")
        vcn_slug = _slugify(str(vcn.get("name") or _short_ocid(vcn_ocid)))
        vcn_root = f"NET_{vcn_slug}_ROOT"
        vcn_label = _vcn_label(vcn)
        lines.append(f'  {vcn_root}(("Network View: {vcn_slug}"))')
        lines.append(f"  class {vcn_root} boundary")
        vcn_block = _mermaid_id(f"vcn:{vcn_ocid}")
        if vcn_ocid:
            rendered_ocids.add(vcn_ocid)
        lines.append(f'  subgraph {vcn_block}["{vcn_label.replace("\"", "'")}"]')
        lines.append("    direction TB")
        # Gateways
        for gtype, lab in (("InternetGateway", "IGW"), ("NatGateway", "NAT"), ("ServiceGateway", "Service GW")):
            gws = []
            for n in nodes:
                if not _is_node_type(n, gtype):
                    continue
                vcn_ref = _vcn_ref_for(n)
                if vcn_ref:
                    if vcn_ref == vcn_ocid:
                        gws.append(n)
                    continue
                if str(n.get("compartmentId") or "") == str(vcn.get("compartmentId") or ""):
                    gws.append(n)
            if gws:
                gid = _mermaid_id(str(gws[0].get("nodeId") or f"{vcn_ocid}:{gtype}"))
                if gws[0].get("nodeId"):
                    rendered_ocids.add(str(gws[0].get("nodeId") or ""))
                lines.extend(_render_node_with_class(gid, f"{lab}<br>{gtype}", cls="network", shape="rect"))
        # Subnets for this VCN
        subs = [n for n in nodes if _is_node_type(n, "Subnet") and _vcn_ref_for(n) == vcn_ocid]
        subs_sorted = sorted(subs, key=lambda n: str(n.get("name") or ""))
        kept_subs, subs_summary = _summarize_many(subs_sorted, title="Other subnets", keep=2)
        for sn in kept_subs:
            sid = _mermaid_id(str(sn.get("nodeId") or ""))
            if sn.get("nodeId"):
                rendered_ocids.add(str(sn.get("nodeId") or ""))
            lines.extend(_render_node_with_class(sid, _subnet_label(sn).replace('"', "'"), cls="network", shape="rect"))
        if subs_summary:
            sid = _mermaid_id(f"subnets:{vcn_ocid}:summary")
            lines.extend(_render_node_with_class(sid, subs_summary, cls="summary"))
        lines.append("  end")
        lines.append(_render_edge("NET_ROOT", vcn_root, "", dotted=True))
    if len(vcn_sorted) > 4:
        sid = _mermaid_id("vcn:summary")
        lines.extend(_render_node_with_class(sid, f"Other VCNs... and {len(vcn_sorted) - 4} more", cls="summary"))
        lines.append(_render_edge("NET_ROOT", sid, "", dotted=True))
    lines.append("end")

    # Security lane
    lines.append('subgraph SECURITY["Security"]')
    lines.append("  direction TB")
    lines.append("  SEC_ROOT((Security))")
    lines.append("  class SEC_ROOT boundary")
    sec_nodes = sorted(lanes["security"], key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")))
    kept, omitted = _keep_and_omitted(sec_nodes, keep=6)
    for n in kept:
        nid = _mermaid_id(str(n.get("nodeId") or ""))
        if n.get("nodeId"):
            rendered_ocids.add(str(n.get("nodeId") or ""))
        lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls="boundary", shape="rect"))
        lines.append(_render_edge("SEC_ROOT", nid, "", dotted=True))
    if omitted:
        sid = _mermaid_id("security:summary")
        lines.extend(_render_node_with_class(sid, f"Other security resources... and {len(omitted)} more", cls="summary"))
        lines.append(_render_edge("SEC_ROOT", sid, "", dotted=True))
    lines.append("end")

    # App lane
    lines.append('subgraph APP["App"]')
    lines.append("  direction TB")
    lines.append("  APP_ROOT((App))")
    lines.append("  class APP_ROOT boundary")
    app_nodes = sorted(lanes["app"], key=_instance_first_sort_key)
    kept, omitted = _keep_and_omitted(app_nodes, keep=8)
    app_entry_first: Optional[str] = None
    app_entry_preferred: Optional[str] = None
    for n in kept:
        nid = _mermaid_id(str(n.get("nodeId") or ""))
        if n.get("nodeId"):
            rendered_ocids.add(str(n.get("nodeId") or ""))
        if app_entry_first is None:
            app_entry_first = nid
        if app_entry_preferred is None and _is_node_type(n, "Instance"):
            app_entry_preferred = nid
        lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n)))
        lines.append(_render_edge("APP_ROOT", nid, "", dotted=True))
    app_entry = app_entry_preferred or app_entry_first
    if omitted:
        sid = _mermaid_id("app:summary")
        lines.extend(_render_node_with_class(sid, f"Other app/compute resources... and {len(omitted)} more", cls="summary"))
        lines.append(_render_edge("APP_ROOT", sid, "", dotted=True))
    lines.append("end")

    # Data lane
    lines.append('subgraph DATA["Data"]')
    lines.append("  direction TB")
    lines.append("  DATA_ROOT((Data))")
    lines.append("  class DATA_ROOT boundary")
    data_nodes = sorted(lanes["data"], key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")))
    kept, omitted = _keep_and_omitted(data_nodes, keep=8)
    first_data: Optional[str] = None
    for n in kept:
        nid = _mermaid_id(str(n.get("nodeId") or ""))
        if n.get("nodeId"):
            rendered_ocids.add(str(n.get("nodeId") or ""))
        if first_data is None:
            first_data = nid
        lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls="storage", shape="db"))
        lines.append(_render_edge("DATA_ROOT", nid, "", dotted=True))
    if omitted:
        sid = _mermaid_id("data:summary")
        lines.extend(_render_node_with_class(sid, f"Other data resources... and {len(omitted)} more", cls="summary"))
        lines.append(_render_edge("DATA_ROOT", sid, "", dotted=True))
    lines.append("end")

    # Observability lane
    lines.append('subgraph OBS["Observability"]')
    lines.append("  direction TB")
    lines.append("  OBS_ROOT((Observability))")
    lines.append("  class OBS_ROOT boundary")
    obs_nodes = sorted(lanes["observability"], key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")))
    kept, omitted = _keep_and_omitted(obs_nodes, keep=6)
    for n in kept:
        nid = _mermaid_id(str(n.get("nodeId") or ""))
        if n.get("nodeId"):
            rendered_ocids.add(str(n.get("nodeId") or ""))
        lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls="boundary", shape="rect"))
        lines.append(_render_edge("OBS_ROOT", nid, "", dotted=True))
    if omitted:
        sid = _mermaid_id("obs:summary")
        lines.extend(_render_node_with_class(sid, f"Other observability resources... and {len(omitted)} more", cls="summary"))
        lines.append(_render_edge("OBS_ROOT", sid, "", dotted=True))
    lines.append("end")

    # Workload anchors (explicit nodes referenced by context links).
    if workload_views:
        lines.append('subgraph WORKLOADS["Workload Views"]')
        lines.append("  direction TB")
        lines.append("  WL_ROOT((Workloads))")
        lines.append("  class WL_ROOT boundary")
        for wl in workload_views:
            wl_id = f"WL_{_slugify(wl)}_ROOT"
            wl_label = f"Workload View: {wl}".replace('"', "'")
            lines.extend(_render_node_with_class(wl_id, wl_label, cls="summary", shape="rect"))
            lines.append(_render_edge("WL_ROOT", wl_id, "", dotted=True))
        lines.append("end")

    # Minimal cross-lane story flows.
    if app_entry:
        lines.append(_render_edge(users_id, app_entry, "requests inferred", dotted=True))
    if app_entry and first_data:
        lines.append(_render_edge(app_entry, first_data, "reads/writes inferred", dotted=True))

    # Keep prior-style context links to detailed view anchors.
    for p in mmds_sorted:
        if p.name.startswith("diagram.network."):
            vcn = p.name[len("diagram.network.") : -len(".mmd")]
            lines.append(f"TEN_ROOT -.-> NET_{_slugify(vcn)}_ROOT")
        if p.name.startswith("diagram.workload."):
            wl = p.name[len("diagram.workload.") : -len(".mmd")]
            lines.append(f"TEN_ROOT -.-> WL_{_slugify(wl)}_ROOT")

    consolidated.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return consolidated
