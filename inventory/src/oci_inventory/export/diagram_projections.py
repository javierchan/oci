from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
import logging
from pathlib import Path
from shutil import which
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .graph import Edge, Node
from ..normalize.transform import group_workload_candidates
from ..util.errors import ExportError


_NON_ARCH_LEAF_NODETYPES: Set[str] = set()
MAX_MERMAID_TEXT_CHARS = 50000
LOG = logging.getLogger(__name__)


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


DiagramSummary = Dict[str, List[Dict[str, Any]]]


def _ensure_diagram_summary(summary: Optional[DiagramSummary]) -> Optional[DiagramSummary]:
    if summary is None:
        return None
    summary.setdefault("skipped", [])
    summary.setdefault("split", [])
    return summary


def _record_diagram_skip(
    summary: Optional[DiagramSummary],
    *,
    diagram: str,
    kind: str,
    size: int,
    limit: int,
    reason: str,
) -> None:
    if summary is None:
        return
    summary["skipped"].append(
        {
            "diagram": diagram,
            "kind": kind,
            "size": size,
            "limit": limit,
            "reason": reason,
        }
    )


def _record_diagram_split(
    summary: Optional[DiagramSummary],
    *,
    diagram: str,
    parts: Sequence[str],
    size: int,
    limit: int,
    reason: str,
) -> None:
    if summary is None:
        return
    summary["split"].append(
        {
            "diagram": diagram,
            "parts": list(parts),
            "size": size,
            "limit": limit,
            "reason": reason,
        }
    )

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


def _extract_env_class(node: Node) -> str:
    """Detect environment (Production, Non-prod) from tags."""
    md = _node_metadata(node)
    # Search for common environment tags in both freeform and defined tags
    tags_dicts = [
        _get_meta(md, "freeformTags", "freeform_tags") or {},
        _get_meta(md, "definedTags", "defined_tags") or {},
    ]
    
    env_candidate = ""
    for tags in tags_dicts:
        for k, v in tags.items():
            k_lower = k.lower()
            # If it's a defined tag namespace, look inside
            if isinstance(v, dict) and any(x in k_lower for x in ("oracle", "tag", "env")):
                for sk, sv in v.items():
                    sk_lower = sk.lower()
                    if any(x in sk_lower for x in ("env", "stage", "lifecycle")):
                        env_candidate = str(sv).lower()
                        break
            elif any(x in k_lower for x in ("env", "stage", "lifecycle")):
                env_candidate = str(v).lower()
            
            if env_candidate:
                break
        if env_candidate:
            break
            
    if not env_candidate:
        return ""
    if "prod" in env_candidate:
        return "prod"
    if any(x in env_candidate for x in ("test", "dev", "stage", "staging", "lab")):
        return "nonprod"
    return ""


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
        "classDef region stroke-width:2px,stroke-dasharray: 2 2;",
        "classDef boundary stroke-width:2px,stroke-dasharray: 6 3;",
        "classDef compute stroke-width:2px;",
        "classDef network stroke-width:2px;",
        "classDef storage stroke-width:2px;",
        "classDef policy stroke-width:2px;",
        "classDef summary stroke-dasharray: 3 3;",
        "classDef prod stroke:#ff6600,stroke-width:4px;",
        "classDef nonprod stroke:#666666,stroke-width:2px,stroke-dasharray: 5 5;",
        "classDef alert stroke:#ff0000,stroke-width:4px,fill:#fff0f0;",
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


def _mermaid_text_size(lines: Sequence[str]) -> int:
    return sum(len(line) + 1 for line in lines)


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


def _filter_edges_for_nodes(edges: Sequence[Edge], node_ids: Set[str]) -> List[Edge]:
    if not node_ids:
        return []
    out: List[Edge] = []
    for edge in edges:
        src = str(edge.get("source_ocid") or "")
        dst = str(edge.get("target_ocid") or "")
        if src in node_ids and dst in node_ids:
            out.append(edge)
    return out


def _workload_scope_node_ids(
    wl_nodes: Sequence[Node],
    *,
    node_by_id: Mapping[str, Node],
    attach_by_res: Mapping[str, _DerivedAttachment],
    subnet_to_vcn: Mapping[str, str],
    edge_vcn_by_src: Mapping[str, str],
) -> Tuple[Set[str], Set[str]]:
    wl_ids: Set[str] = set()
    comp_ids: Set[str] = set()
    vcn_ids: Set[str] = set()
    subnet_ids: Set[str] = set()

    for n in wl_nodes:
        ocid = str(n.get("nodeId") or "")
        if ocid:
            wl_ids.add(ocid)
        cid = str(n.get("compartmentId") or "") or "UNKNOWN"
        comp_ids.add(cid)
        if not ocid:
            continue
        if _is_node_type(n, "Vcn"):
            vcn_ids.add(ocid)
        if _is_node_type(n, "Subnet"):
            subnet_ids.add(ocid)
        att = attach_by_res.get(ocid)
        if att:
            if att.subnet_ocid:
                subnet_ids.add(att.subnet_ocid)
            if att.vcn_ocid:
                vcn_ids.add(att.vcn_ocid)
        meta = _node_metadata(n)
        vcn_ref = edge_vcn_by_src.get(ocid) or _get_meta(meta, "vcn_id")
        if isinstance(vcn_ref, str) and vcn_ref:
            vcn_ids.add(vcn_ref)

    for sn_id in list(subnet_ids):
        vcn_id = subnet_to_vcn.get(sn_id)
        if vcn_id:
            vcn_ids.add(vcn_id)

    for sn_id, vcn_id in subnet_to_vcn.items():
        if vcn_id in vcn_ids:
            subnet_ids.add(sn_id)

    network_ids: Set[str] = set()
    for ocid, node in node_by_id.items():
        if not ocid:
            continue
        if not (_is_node_type(node, *_NETWORK_GATEWAY_NODETYPES) or _is_vcn_level_resource(node)):
            continue
        att = attach_by_res.get(ocid)
        vcn_ref = ""
        if att and att.vcn_ocid:
            vcn_ref = att.vcn_ocid
        else:
            meta = _node_metadata(node)
            vcn_ref = edge_vcn_by_src.get(ocid) or _get_meta(meta, "vcn_id") or ""
        if isinstance(vcn_ref, str) and vcn_ref in vcn_ids:
            network_ids.add(ocid)

    scope_node_ids = wl_ids | vcn_ids | subnet_ids | network_ids
    return scope_node_ids, comp_ids


def _select_scope_nodes(nodes: Sequence[Node], *, scope_node_ids: Set[str], comp_ids: Set[str]) -> List[Node]:
    out: List[Node] = []
    for n in nodes:
        ocid = str(n.get("nodeId") or "")
        if ocid and ocid in scope_node_ids:
            out.append(n)
            continue
        if _is_node_type(n, "Compartment") and ocid and ocid in comp_ids:
            out.append(n)
    return out


def _format_part_index(index: int, total: int) -> str:
    width = max(2, len(str(total)))
    return f"{index:0{width}d}"


def _split_note_lines(note: str, part_paths: Sequence[Path]) -> List[str]:
    lines = [f"%% NOTE: {note}"]
    if part_paths:
        lines.append("%% Split outputs:")
        seen: Set[str] = set()
        for p in part_paths:
            name = p.name
            if name in seen:
                continue
            seen.add(name)
            lines.append(f"%% - {name}")
    return lines


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


def _region_list(nodes: Sequence[Node]) -> List[str]:
    regions = {str(n.get("region") or "") for n in nodes if n.get("region")}
    return sorted(r for r in regions if r)


def _rpc_peer_region(node: Node, rpc_region_by_id: Mapping[str, str]) -> Optional[str]:
    meta = _node_metadata(node)
    peer_region = _get_meta(
        meta,
        "peer_region_name",
        "peer_region",
        "peerRegionName",
        "peerRegion",
    )
    if isinstance(peer_region, str) and peer_region:
        return peer_region
    peer_id = _get_meta(meta, "peer_id", "peerId", "peer_rpc_id", "peerRpcId")
    if isinstance(peer_id, str) and peer_id:
        return rpc_region_by_id.get(peer_id)
    return None


def _rpc_region_links(nodes: Sequence[Node]) -> Set[Tuple[str, str]]:
    rpc_region_by_id: Dict[str, str] = {
        str(n.get("nodeId") or ""): str(n.get("region") or "")
        for n in nodes
        if _is_node_type(n, "RemotePeeringConnection") and n.get("nodeId") and n.get("region")
    }
    links: Set[Tuple[str, str]] = set()
    for n in nodes:
        if not _is_node_type(n, "RemotePeeringConnection"):
            continue
        region = str(n.get("region") or "")
        if not region:
            continue
        peer_region = _rpc_peer_region(n, rpc_region_by_id)
        if not peer_region or peer_region == region:
            continue
        pair = tuple(sorted((region, peer_region)))
        links.add(pair)
    return links


def _global_flowchart_lines(nodes: Sequence[Node]) -> List[str]:
    regions = _region_list(nodes)
    lines: List[str] = ["flowchart TD"]
    lines.extend(_style_block_lines())
    lines.append("%% Global Connectivity Map")

    tenancy_label = _tenancy_label(nodes).replace('"', "'")
    tenancy_id = _mermaid_id("consolidated:global:tenancy")
    lines.append(f"subgraph {tenancy_id}[\"{tenancy_label}\"]")
    lines.append("  direction TB")

    region_nodes: Dict[str, str] = {}
    for region in regions:
        region_id = _mermaid_id(f"region:{region}")
        region_nodes[region] = region_id
        label = f"Region: {region}"
        lines.extend(_render_node_with_class(region_id, label, cls="region", shape="round"))
    lines.append("end")

    for region_a, region_b in sorted(_rpc_region_links(nodes)):
        src = region_nodes.get(region_a)
        dst = region_nodes.get(region_b)
        if not src or not dst:
            continue
        lines.append(_render_edge(src, dst, label="RPC"))

    return lines


def _detailed_flowchart_lines(
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    depth: int = 3,
) -> List[str]:
    lines: List[str] = ["flowchart TD"]
    lines.extend(_style_block_lines())
    lines.append("%% Detailed Hierarchical Flowchart")

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

    def _include_for_depth2_local(node: Node) -> bool:
        if _is_node_type(node, "Compartment"):
            return False
        if _is_node_type(node, "Vcn", "Subnet"):
            return True
        if _is_node_type(node, "Vnic"):
            return False
        ocid = str(node.get("nodeId") or "")
        if not ocid:
            return False
        if _is_node_type(node, *_NETWORK_GATEWAY_NODETYPES, "LoadBalancer"):
            return True
        att = attach_by_res.get(ocid)
        return bool(att and (att.vcn_ocid or att.subnet_ocid))

    rendered_node_ids: Set[str] = set()
    edge_node_id_map: Dict[str, str] = {}
    
    tenancy_label = _tenancy_label(nodes)
    tenancy_id = _mermaid_id(f"flow:tenancy:{tenancy_label}")
    lines.append(f"subgraph {tenancy_id}[\"{tenancy_label}\"]")
    lines.append("  direction TB")

    region_id_map: Dict[str, str] = {}

    def _get_node_classes(node: Node) -> str:
        classes = [_node_class(node)]
        env_cls = _extract_env_class(node)
        if env_cls:
            classes.append(env_cls)
        if node.get("enrichStatus") == "ERROR":
            classes.append("alert")
        return " ".join(classes)

    def _get_node_label(node: Node) -> str:
        label = _mermaid_label_for(node)
        if node.get("enrichStatus") == "ERROR":
            label = f"🔴 {label}"
        return label

    nodes_by_region: Dict[str, List[Node]] = {}
    for n in nodes:
        reg = str(n.get("region") or n.get("regionName") or "Global")
        nodes_by_region.setdefault(reg, []).append(n)

    for reg in sorted(nodes_by_region.keys()):
        region_id = _mermaid_id(f"flow:region:{reg}")
        region_id_map[reg] = region_id
        lines.append(f"  subgraph {region_id}[\"Region: {reg}\"]")
        lines.append("    direction TB")

        region_nodes = nodes_by_region[reg]
        nodes_by_comp: Dict[str, List[Node]] = {}
        for n in region_nodes:
            cid = str(n.get("compartmentId") or "")
            if not cid and _is_node_type(n, "Compartment"):
                cid = str(n.get("nodeId") or "")
            nodes_by_comp.setdefault(cid or "UNKNOWN", []).append(n)

        for cid in sorted(nodes_by_comp.keys()):
            comp_node = node_by_id.get(cid, {"name": cid, "nodeType": "Compartment"})
            comp_label = _compartment_label(comp_node)
            comp_id = _mermaid_id(f"flow:comp:{reg}:{cid}")
            lines.append(f"    subgraph {comp_id}[\"{comp_label}\"]")
            lines.append("      direction TB")

            comp_nodes = nodes_by_comp[cid]
            if depth == 2:
                comp_nodes = [n for n in comp_nodes if _include_for_depth2_local(n)]
            
            vcns = [n for n in comp_nodes if _is_node_type(n, "Vcn")]
            for vcn in sorted(vcns, key=lambda n: str(n.get("name") or "")):
                vcn_ocid = str(vcn.get("nodeId") or "")
                vcn_id = _mermaid_id(vcn_ocid)
                vcn_label = _vcn_label(vcn)
                lines.append(f"      subgraph {vcn_id}[\"{vcn_label}\"]")
                lines.append("        direction TB")

                # VCN Level resources
                vcn_resources = []
                for n in comp_nodes:
                    ocid = str(n.get("nodeId") or "")
                    if not ocid: continue
                    att = attach_by_res.get(ocid)
                    if att and att.vcn_ocid == vcn_ocid and not att.subnet_ocid:
                        vcn_resources.append(n)
                    elif not att:
                        meta = _node_metadata(n)
                        vcn_ref = edge_vcn_by_src.get(ocid) or _get_meta(meta, "vcn_id")
                        if vcn_ref == vcn_ocid:
                             vcn_resources.append(n)

                if vcn_resources:
                    for n in sorted(vcn_resources, key=lambda n: str(n.get("name") or "")):
                        if _is_node_type(n, "Vcn", "Subnet"): continue
                        nid = _mermaid_id(str(n.get("nodeId") or ""))
                        lines.extend(_render_node_with_class(nid, _get_node_label(n), cls=_get_node_classes(n), shape=_node_shape(n)))
                        rendered_node_ids.add(str(n.get("nodeId") or ""))
                        edge_node_id_map[str(n.get("nodeId") or "")] = nid

                # Subnets
                comp_subnets = [n for n in comp_nodes if _is_node_type(n, "Subnet") and subnet_to_vcn.get(str(n.get("nodeId") or "")) == vcn_ocid]
                for sn in sorted(comp_subnets, key=lambda n: str(n.get("name") or "")):
                    sn_ocid = str(sn.get("nodeId") or "")
                    sn_id = _mermaid_id(sn_ocid)
                    sn_label = _subnet_label(sn)
                    lines.append(f"        subgraph {sn_id}[\"{sn_label}\"]")
                    lines.append("          direction TB")

                    attached = [
                        n for n in comp_nodes
                        if attach_by_res.get(str(n.get("nodeId") or "")) 
                        and attach_by_res[str(n.get("nodeId") or "")].subnet_ocid == sn_ocid
                        and not _is_node_type(n, "Vcn", "Subnet")
                    ]
                    for n in sorted(attached, key=lambda n: str(n.get("name") or "")):
                        nid = _mermaid_id(str(n.get("nodeId") or ""))
                        lines.extend(_render_node_with_class(nid, _get_node_label(n), cls=_get_node_classes(n), shape=_node_shape(n)))
                        rendered_node_ids.add(str(n.get("nodeId") or ""))
                        edge_node_id_map[str(n.get("nodeId") or "")] = nid
                    
                    lines.append("        end")
                lines.append("      end")

            # Out of VCN or non-networked resources in compartment
            other_nodes = [
                n for n in comp_nodes 
                if not _is_node_type(n, "Vcn", "Subnet", "Compartment")
                and str(n.get("nodeId") or "") not in rendered_node_ids
            ]
            if other_nodes:
                for n in sorted(other_nodes, key=lambda n: str(n.get("name") or "")):
                     nid = _mermaid_id(str(n.get("nodeId") or ""))
                     lines.extend(_render_node_with_class(nid, _get_node_label(n), cls=_get_node_classes(n), shape=_node_shape(n)))
                     rendered_node_ids.add(str(n.get("nodeId") or ""))
                     edge_node_id_map[str(n.get("nodeId") or "")] = nid

            lines.append("      end")
        lines.append("    end")
    lines.append("  end")
    lines.append("end")

    # Add RPC links between regions
    for region_a, region_b in sorted(_rpc_region_links(nodes)):
        src = region_id_map.get(region_a)
        dst = region_id_map.get(region_b)
        if src and dst:
            lines.append(_render_edge(src, dst, label="RPC"))

    if depth >= 3:
        rel_lines = _render_relationship_edges(
            edges,
            node_ids=rendered_node_ids,
            node_id_map=edge_node_id_map,
            node_by_id=node_by_id,
            include_admin_edges=False,
        )
        lines.extend(rel_lines)

    return lines


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


def _tenancy_safe_label(prefix: str, name: str) -> str:
    clean = (name or "").strip()
    if not clean or clean.startswith("ocid1"):
        clean = "Unknown"
    if prefix:
        return f"{prefix}: {clean}"
    return clean


def _tenancy_mermaid_id(prefix: str, label: str, counters: Dict[str, int]) -> str:
    base = _slugify(label, max_len=48)
    base = re.sub(r"[^A-Za-z0-9_]", "_", base)
    if not base:
        base = "unknown"
    key = f"{prefix}_{base}"
    counters[key] = counters.get(key, 0) + 1
    if counters[key] > 1:
        return f"{key}_{counters[key]}"
    return key


def _tenancy_aggregate_label(node: Node) -> str:
    nt = str(node.get("nodeType") or "")
    nt_lower = nt.lower()
    cat = str(node.get("nodeCategory") or "").lower()

    if cat == "compute" or _is_node_type(node, "Instance"):
        return "Instances"
    if _is_node_type(node, "Volume", "BlockVolume", "BootVolume", "VolumeGroup"):
        return "Block Storage"
    if _is_node_type(node, "LogAnalyticsEntity", "Alarm", "Metric"):
        return "Observability Suite"
    if _is_node_type(node, "AutonomousDatabase", "AutonomousDb") or (
        "autonomous" in nt_lower and ("db" in nt_lower or "database" in nt_lower)
    ):
        return "Autonomous DBs"
    if _is_node_type(node, "ExadataVmCluster", "ExadataVMCluster", "VmCluster") or (
        "exadata" in nt_lower and "cluster" in nt_lower
    ):
        return "Exadata VM Clusters"
    if nt:
        return _friendly_type(nt)
    return "Resource"


def _write_tenancy_view(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    depth: int = 3,
    path: Optional[Path] = None,
    legend_prefix: str = "tenancy",
    title: Optional[str] = None,
) -> Path:
    path = path or (outdir / "diagram.tenancy.mmd")

    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}
    counters: Dict[str, int] = {}
    depth = max(1, min(depth, 3))

    comp_nodes = [n for n in nodes if _is_node_type(n, "Compartment") and n.get("nodeId")]
    comp_ids = {str(n.get("nodeId") or "") for n in comp_nodes}
    parents = _compartment_parent_map(nodes)
    root_ids = {cid for cid in comp_ids if cid not in parents}
    top_level_ids: Set[str] = {cid for cid, parent in parents.items() if parent in root_ids}

    if not top_level_ids:
        top_level_ids = set(comp_ids)

    nodes_by_root: Dict[str, List[Node]] = {}
    for n in nodes:
        cid = str(n.get("compartmentId") or "")
        if not cid and _is_node_type(n, "Compartment"):
            cid = str(n.get("nodeId") or "")
        if not cid:
            root = "UNKNOWN"
        else:
            root = _root_compartment_id(cid, parents)
        nodes_by_root.setdefault(root, []).append(n)

    if root_ids:
        for root_id in root_ids:
            if any(n for n in nodes_by_root.get(root_id, []) if not _is_node_type(n, "Compartment")):
                top_level_ids.add(root_id)

    regions = _region_list(nodes)

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

    gateways_by_vcn: Dict[str, Dict[str, int]] = {}
    for n in nodes:
        if not _is_node_type(n, *_NETWORK_GATEWAY_NODETYPES):
            continue
        meta = _node_metadata(n)
        nid = str(n.get("nodeId") or "")
        vcn_ref = edge_vcn_by_src.get(nid) or _get_meta(meta, "vcn_id")
        if not isinstance(vcn_ref, str) or not vcn_ref:
            continue
        label = _friendly_type(str(n.get("nodeType") or "Gateway"))
        gateways_by_vcn.setdefault(vcn_ref, {})
        gateways_by_vcn[vcn_ref][label] = gateways_by_vcn[vcn_ref].get(label, 0) + 1

    lines: List[str] = ["flowchart LR"]
    lines.extend(_style_block_lines())
    if title:
        lines.append(f"%% {title}")
    lines.append("%% ------------------ Tenancy / Regions / Compartments ------------------")

    tenancy_name = ""
    for n in comp_nodes:
        if n.get("compartmentId"):
            continue
        name = str(n.get("name") or "").strip()
        if name and not name.startswith("ocid1"):
            tenancy_name = name
            break
    tenancy_label = "Tenancy" if not tenancy_name else f"Tenancy: {tenancy_name}"
    tenancy_label = _tenancy_safe_label("", tenancy_label)
    tenancy_id = _tenancy_mermaid_id("Tenancy", tenancy_label, counters)
    lines.append(f"subgraph {tenancy_id}[\"{tenancy_label}\"]")
    lines.append("  direction LR")

    if regions:
        for region in regions:
            region_label = _tenancy_safe_label("Region", region)
            region_id = _tenancy_mermaid_id("Region", region_label, counters)
            lines.append(f"  {region_id}[\"{region_label}\"]")

    vcn_node_ids: Dict[str, str] = {}
    for cid in sorted(top_level_ids):
        comp_node = node_by_id.get(cid, {"name": cid})
        comp_name = str(comp_node.get("name") or "").strip()
        comp_label = _tenancy_safe_label("Compartment", comp_name)
        comp_id = _tenancy_mermaid_id("Comp", comp_label, counters)
        lines.append(f"  subgraph {comp_id}[\"{comp_label}\"]")
        lines.append("    direction TB")

        if depth >= 2:
            comp_nodes_list = [n for n in nodes_by_root.get(cid, []) if not _is_node_type(n, "Compartment")]
            comp_vcns = [n for n in comp_nodes_list if _is_node_type(n, "Vcn") and n.get("nodeId")]
            for vcn in sorted(comp_vcns, key=lambda n: str(n.get("name") or "")):
                vcn_id = str(vcn.get("nodeId") or "")
                vcn_name = str(vcn.get("name") or "").strip()
                vcn_label = _tenancy_safe_label("VCN", vcn_name)
                vcn_group_id = _tenancy_mermaid_id("VCN", vcn_label, counters)
                lines.append(f"    subgraph {vcn_group_id}[\"{vcn_label}\"]")
                lines.append("      direction TB")
                vcn_node_id = _tenancy_mermaid_id("VCNNode", vcn_label, counters)
                lines.append(f"      {vcn_node_id}[\"{vcn_label}\"]")
                vcn_node_ids[vcn_id] = vcn_node_id

                if depth >= 3:
                    gateway_counts = gateways_by_vcn.get(vcn_id, {})
                    gateway_keys = {"InternetGateway", "ServiceGateway", "Drg"}
                    gateway_counts = {k: v for k, v in gateway_counts.items() if k in gateway_keys}
                    if gateway_counts:
                        edge_id = _tenancy_mermaid_id("Edge", f"{vcn_label}_edge", counters)
                        lines.append(f"      subgraph {edge_id}[\"Network Edge\"]")
                        lines.append("        direction TB")
                        for gw_label in sorted(gateway_counts.keys()):
                            count = gateway_counts[gw_label]
                            gw_id = _tenancy_mermaid_id("Gateway", f"{vcn_label}_{gw_label}", counters)
                            lines.append(f"        {gw_id}[\"{gw_label} (n={count})\"]")
                        lines.append("      end")

                vcn_subnets = [
                    sn
                    for sn in comp_nodes_list
                    if _is_node_type(sn, "Subnet")
                    and subnet_to_vcn.get(str(sn.get("nodeId") or "")) == vcn_id
                ]
                for sn in sorted(vcn_subnets, key=lambda n: str(n.get("name") or "")):
                    sn_ocid = str(sn.get("nodeId") or "")
                    sn_name = str(sn.get("name") or "").strip()
                    subnet_label = _tenancy_safe_label("Subnet", sn_name)
                    subnet_group_id = _tenancy_mermaid_id("Subnet", subnet_label, counters)
                    lines.append(f"      subgraph {subnet_group_id}[\"{subnet_label}\"]")
                    lines.append("        direction TB")

                    if depth >= 3:
                        attached = [
                            n
                            for n in comp_nodes_list
                            if attach_by_res.get(str(n.get("nodeId") or ""))
                            and attach_by_res[str(n.get("nodeId") or "")].subnet_ocid == sn_ocid
                            and not _is_node_type(n, "Vcn", "Subnet", *_NETWORK_GATEWAY_NODETYPES)
                        ]
                        buckets: Dict[str, int] = {}
                        for n in attached:
                            label = _tenancy_aggregate_label(n)
                            buckets[label] = buckets.get(label, 0) + 1
                        for label in sorted(buckets.keys()):
                            count = buckets[label]
                            agg_id = _tenancy_mermaid_id("Agg", f"{subnet_label}_{label}", counters)
                            lines.append(f"        {agg_id}[\"{label} (n={count})\"]")

                    lines.append("      end")

                lines.append("    end")

            if depth >= 3:
                out_nodes: List[Node] = []
                for n in comp_nodes_list:
                    if _is_node_type(n, "Vcn", "Subnet", *_NETWORK_GATEWAY_NODETYPES):
                        continue
                    ocid = str(n.get("nodeId") or "")
                    att = attach_by_res.get(ocid)
                    if att and att.subnet_ocid:
                        continue
                    out_nodes.append(n)

                if out_nodes:
                    out_id = _tenancy_mermaid_id("OutOfVcn", f"{comp_label}_out", counters)
                    lines.append(f"    subgraph {out_id}[\"Out-of-VCN\"]")
                    lines.append("      direction TB")
                    buckets: Dict[str, int] = {}
                    for n in out_nodes:
                        label = _tenancy_aggregate_label(n)
                        buckets[label] = buckets.get(label, 0) + 1
                    for label in sorted(buckets.keys()):
                        count = buckets[label]
                        agg_id = _tenancy_mermaid_id("Agg", f"{comp_label}_{label}", counters)
                        lines.append(f"      {agg_id}[\"{label} (n={count})\"]")
                    lines.append("    end")

        lines.append("  end")

    lines.append("end")

    if depth >= 3:
        external_id = _tenancy_mermaid_id("External", "External", counters)
        lines.append(f"subgraph {external_id}[\"External\"]")
        lines.append("  direction TB")
        internet_id = _tenancy_mermaid_id("External", "Internet", counters)
        oci_services_id = _tenancy_mermaid_id("External", "OCI Services", counters)
        customer_net_id = _tenancy_mermaid_id("External", "Customer Network", counters)
        lines.append(f"  {internet_id}[\"Internet\"]")
        lines.append(f"  {oci_services_id}[\"OCI Services\"]")
        lines.append(f"  {customer_net_id}[\"Customer Network\"]")
        lines.append("end")

        for vcn in vcns:
            vcn_id = str(vcn.get("nodeId") or "")
            if not vcn_id:
                continue
            gateways = gateways_by_vcn.get(vcn_id, {})
            if not gateways:
                continue
            vcn_node_id = vcn_node_ids.get(vcn_id)
            if not vcn_node_id:
                continue
            if "InternetGateway" in gateways:
                lines.append(_render_edge(vcn_node_id, internet_id, "IGW", dotted=False))
            if "ServiceGateway" in gateways:
                lines.append(_render_edge(vcn_node_id, oci_services_id, "SGW", dotted=False))
            if "Drg" in gateways:
                lines.append(_render_edge(vcn_node_id, customer_net_id, "DRG", dotted=False))

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_network_views(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    summary: Optional[DiagramSummary] = None,
) -> List[Path]:
    summary = _ensure_diagram_summary(summary)
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
            include_admin_edges=False,
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

        size = _mermaid_text_size(lines)
        if size > MAX_MERMAID_TEXT_CHARS:
            _record_diagram_skip(
                summary,
                diagram=path.name,
                kind="network",
                size=size,
                limit=MAX_MERMAID_TEXT_CHARS,
                reason="exceeds_mermaid_limit",
            )
            continue
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out_paths.append(path)

    return out_paths


def _build_workload_diagram_lines(
    *,
    wl_name: str,
    wl_nodes: Sequence[Node],
    nodes: Sequence[Node],
    edges: Sequence[Edge],
) -> List[str]:
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
            fallback_nodes = [n for n in wl_nodes if n.get("nodeId") and not _is_node_type(n, "Compartment")]
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
        include_admin_edges=False,
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
    return lines


def _write_workload_views(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    summary: Optional[DiagramSummary] = None,
) -> List[Path]:
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

    summary = _ensure_diagram_summary(summary)
    out_paths: List[Path] = []

    wl_items = sorted(wl_to_nodes.items(), key=lambda kv: kv[0].lower())

    for wl_name, wl_nodes in wl_items:
        base_name = f"diagram.workload.{_slugify(wl_name)}.mmd"
        base_path = outdir / base_name

        scope_node_ids, comp_ids = _workload_scope_node_ids(
            wl_nodes,
            node_by_id=node_by_id,
            attach_by_res=attach_by_res,
            subnet_to_vcn=subnet_to_vcn,
            edge_vcn_by_src=edge_vcn_by_src,
        )
        scope_nodes = _select_scope_nodes(nodes, scope_node_ids=scope_node_ids, comp_ids=comp_ids)
        scope_edges = _filter_edges_for_nodes(edges, scope_node_ids)
        lines = _build_workload_diagram_lines(
            wl_name=wl_name,
            wl_nodes=wl_nodes,
            nodes=scope_nodes,
            edges=scope_edges,
        )
        size = _mermaid_text_size(lines)
        if size <= MAX_MERMAID_TEXT_CHARS:
            base_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            out_paths.append(base_path)
            continue

        wl_nodes_sorted = sorted(
            [n for n in wl_nodes if n.get("nodeId")],
            key=lambda n: (
                str(n.get("nodeCategory") or ""),
                str(n.get("nodeType") or ""),
                str(n.get("name") or ""),
                str(n.get("nodeId") or ""),
            ),
        )
        wl_missing_ids = [n for n in wl_nodes if not n.get("nodeId")]

        parts: List[Tuple[List[str], int]] = []
        skipped_nodes: List[Node] = []
        if wl_nodes_sorted:
            estimated_chunk = max(
                1,
                int(len(wl_nodes_sorted) * MAX_MERMAID_TEXT_CHARS / max(size, 1)),
            )
            idx = 0
            while idx < len(wl_nodes_sorted):
                chunk = min(estimated_chunk, len(wl_nodes_sorted) - idx)
                chunk = max(1, chunk)
                part_lines: Optional[List[str]] = None
                part_size = 0
                while True:
                    subset = wl_nodes_sorted[idx : idx + chunk]
                    part_nodes = subset + wl_missing_ids
                    part_scope_ids, part_comp_ids = _workload_scope_node_ids(
                        part_nodes,
                        node_by_id=node_by_id,
                        attach_by_res=attach_by_res,
                        subnet_to_vcn=subnet_to_vcn,
                        edge_vcn_by_src=edge_vcn_by_src,
                    )
                    part_scope_nodes = _select_scope_nodes(
                        nodes,
                        scope_node_ids=part_scope_ids,
                        comp_ids=part_comp_ids,
                    )
                    part_edges = _filter_edges_for_nodes(edges, part_scope_ids)
                    part_lines = _build_workload_diagram_lines(
                        wl_name=wl_name,
                        wl_nodes=part_nodes,
                        nodes=part_scope_nodes,
                        edges=part_edges,
                    )
                    part_size = _mermaid_text_size(part_lines)
                    if part_size <= MAX_MERMAID_TEXT_CHARS or chunk == 1:
                        break
                    chunk = max(1, chunk // 2)
                if part_size > MAX_MERMAID_TEXT_CHARS or not part_lines:
                    skipped_nodes.append(wl_nodes_sorted[idx])
                    idx += 1
                    continue
                parts.append((part_lines, part_size))
                idx += chunk

        if not parts:
            _record_diagram_skip(
                summary,
                diagram=base_name,
                kind="workload",
                size=size,
                limit=MAX_MERMAID_TEXT_CHARS,
                reason="exceeds_mermaid_limit",
            )
            continue

        part_paths: List[Path] = []
        total_parts = len(parts)
        for index, (part_lines, _part_size) in enumerate(parts, start=1):
            suffix = _format_part_index(index, total_parts)
            part_name = f"diagram.workload.{_slugify(wl_name)}.part{suffix}.mmd"
            part_path = outdir / part_name
            part_path.write_text("\n".join(part_lines) + "\n", encoding="utf-8")
            part_paths.append(part_path)
            out_paths.append(part_path)

        _record_diagram_split(
            summary,
            diagram=base_name,
            parts=[p.name for p in part_paths],
            size=size,
            limit=MAX_MERMAID_TEXT_CHARS,
            reason="split_mermaid_limit",
        )

        note_lines = ["flowchart LR"]
        note_lines.extend(
            _split_note_lines(
                f"Workload diagram split into {total_parts} parts due to Mermaid size limits.",
                part_paths,
            )
        )
        note_id = _mermaid_id(f"workload:split:{wl_name}")
        note_label = _sanitize_edge_label(f"Workload {wl_name} split; see notes")
        note_lines.append(f"  {note_id}[\"{note_label}\"]")
        base_path.write_text("\n".join(note_lines) + "\n", encoding="utf-8")
        out_paths.append(base_path)

        for n in skipped_nodes:
            hint = _short_ocid(str(n.get("nodeId") or ""))
            _record_diagram_skip(
                summary,
                diagram=f"{base_name} (node {hint or 'unknown'})",
                kind="workload",
                size=size,
                limit=MAX_MERMAID_TEXT_CHARS,
                reason="single_node_exceeds_limit",
            )

    return out_paths


def write_diagram_projections(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    diagram_depth: Optional[int] = None,
    summary: Optional[DiagramSummary] = None,
) -> List[Path]:
    # Edges drive placement and relationship hints in projections.
    depth = int(diagram_depth or 3)
    out: List[Path] = []
    summary = _ensure_diagram_summary(summary)
    out.append(_write_tenancy_view(outdir, nodes, edges, depth=depth))
    out.extend(_write_network_views(outdir, nodes, edges, summary=summary))
    out.extend(_write_workload_views(outdir, nodes, edges, summary=summary))

    # Consolidated, end-user-friendly artifact: one Mermaid diagram that contains all the views.
    out.extend(
        _write_consolidated_mermaid(
            outdir,
            nodes,
            edges,
            out,
            depth=depth,
            summary=summary,
        )
    )
    out.extend(
        _write_consolidated_flowchart(
            outdir,
            nodes,
            edges,
            depth=depth,
            summary=summary,
        )
    )
    if summary:
        skipped = summary.get("skipped", [])
        split = summary.get("split", [])
        if skipped:
            LOG.warning(
                "Skipped %s diagram(s) due to Mermaid size limits (see report for details).",
                len(skipped),
            )
        if split:
            LOG.info(
                "Split %s diagram(s) due to Mermaid size limits.",
                len(split),
            )
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


def _compartment_parent_map(nodes: Sequence[Node]) -> Dict[str, str]:
    parents: Dict[str, str] = {}
    for n in nodes:
        if not _is_node_type(n, "Compartment"):
            continue
        ocid = str(n.get("nodeId") or "")
        if not ocid:
            continue
        parent = str(n.get("compartmentId") or "")
        if not parent:
            meta = _node_metadata(n)
            parent = str(_get_meta(meta, "compartment_id", "compartmentId") or "")
        if parent and parent != ocid:
            parents[ocid] = parent
    return parents


def _root_compartment_id(ocid: str, parents: Mapping[str, str]) -> str:
    if not ocid:
        return "UNKNOWN"
    current = ocid
    seen: Set[str] = set()
    while current in parents and current not in seen:
        seen.add(current)
        current = parents[current]
    return current or ocid


def _group_nodes_by_root_compartment(nodes: Sequence[Node]) -> Dict[str, List[Node]]:
    parents = _compartment_parent_map(nodes)
    grouped: Dict[str, List[Node]] = {}
    for n in nodes:
        cid = str(n.get("compartmentId") or "")
        if not cid and _is_node_type(n, "Compartment"):
            cid = str(n.get("nodeId") or "")
        root = _root_compartment_id(cid, parents) if cid else "UNKNOWN"
        grouped.setdefault(root, []).append(n)
    return {k: grouped[k] for k in sorted(grouped.keys())}


def _consolidated_split_groups(nodes: Sequence[Node]) -> Tuple[str, Dict[str, List[Node]]]:
    regions = sorted({str(n.get("region") or "") for n in nodes if n.get("region")})
    if len(regions) > 1:
        groups: Dict[str, List[Node]] = {r: [] for r in regions}
        for n in nodes:
            region = str(n.get("region") or "")
            if region in groups:
                groups[region].append(n)
        for region, group_nodes in groups.items():
            comp_ids = {
                str(n.get("compartmentId") or "")
                for n in group_nodes
                if str(n.get("compartmentId") or "")
            }
            if not comp_ids:
                continue
            for n in nodes:
                if not _is_node_type(n, "Compartment"):
                    continue
                if str(n.get("nodeId") or "") in comp_ids:
                    group_nodes.append(n)
        return "region", {k: groups[k] for k in sorted(groups.keys())}
    return "compartment", _group_nodes_by_root_compartment(nodes)


def _write_consolidated_stub(
    path: Path,
    *,
    kind: str,
    note: str,
    part_paths: Sequence[Path],
    tenancy_label: str,
) -> Path:
    if kind == "architecture":
        lines = ["architecture-beta"]
        lines.extend(_split_note_lines(note, part_paths))
        tenancy_id = _mermaid_id(f"consolidated:stub:{tenancy_label}")
        lines.append(f"    group {tenancy_id}(cloud)[{_arch_label(tenancy_label, max_len=80)}]")
        notice_id = _mermaid_id(f"consolidated:stub:notice:{tenancy_label}")
        lines.append(
            f"    service {notice_id}(server)[{_arch_label('See split diagrams for full detail', max_len=64)}] in {tenancy_id}"
        )
    else:
        lines = ["flowchart TB"]
        lines.extend(_split_note_lines(note, part_paths))
        notice_id = _mermaid_id(f"consolidated:stub:notice:{tenancy_label}")
        label = _sanitize_edge_label("Consolidated diagram split; see split outputs.")
        lines.append(f"  {notice_id}[\"{label}\"]")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _write_consolidated_mermaid(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    diagram_paths: Sequence[Path],
    *,
    depth: int = 3,
    _requested_depth: Optional[int] = None,
    path: Optional[Path] = None,
    summary: Optional[DiagramSummary] = None,
    _allow_split: bool = True,
) -> List[Path]:
    consolidated = path or (outdir / "diagram.consolidated.architecture.mmd")
    # Architecture diagram (architecture-beta). Full-detail OCI containment view.
    requested_depth = depth if _requested_depth is None else _requested_depth
    tenancy_label = _tenancy_label(nodes)

    if depth <= 1:
        note = "Depth 1 renders only the global flowchart (tenancy + regions)."
        if depth != requested_depth:
            note = f"Depth reduced from {requested_depth} to {depth}. {note}"
        stub_path = _write_consolidated_stub(
            consolidated,
            kind="architecture",
            note=note,
            part_paths=[],
            tenancy_label=tenancy_label,
        )
        return [stub_path]

    def _service_id(prefix: str, value: str) -> str:
        import hashlib

        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
        return f"{prefix}{digest[:10]}"

    def _service_icon(node: Node) -> str:
        nt = str(node.get("nodeType") or "").lower()
        cat = str(node.get("nodeCategory") or "").lower()
        
        if nt in {"vcn", "subnet", "drg", "internetgateway", "natgateway", "servicegateway", "localpeeringgateway", "remotepeeringconnection"}:
            return "network"
        if nt in {"instance", "instancepool", "containerinstance"} or cat == "compute":
            return "compute"
        if nt in {"bucket", "volume", "blockvolume", "bootvolume", "filesystem"}:
            return "storage"
        if "database" in nt or "db" in nt or cat == "storage":
             return "database"
        if nt in {"streampool", "stream", "queue"}:
            return "queue"
        if nt in {"policy", "user", "group", "identity"} or cat == "policy":
            return "identity"
        if nt in {"topic", "subscription", "ons"}:
            return "notification"
        if nt in {"loadbalancer", "networkloadbalancer"}:
            return "loadbalancer"
        if nt in {"waf", "securitylist", "nsg", "vault", "key"} or cat == "security":
            return "security"
        if "gateway" in nt:
            return "cloud"
        if "function" in nt:
            return "server"
            
        cls = _node_class(node)
        if cls == "external":
            return "cloud"
        if cls == "storage":
            return "database"
        return "server"

    include_workloads = depth >= 2
    include_edges = depth >= 3
    aggregate_workloads = depth == 2
    include_out_of_vcn = depth >= 3
    include_vcn_level = depth >= 3

    lines: List[str] = ["architecture-beta"]
    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}
    vcn_owner_by_id: Dict[str, str] = {
        str(n.get("nodeId") or ""): str(n.get("compartmentId") or "") or "UNKNOWN"
        for n in nodes
        if _is_node_type(n, "Vcn") and n.get("nodeId")
    }
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

    def _resource_type_label(node: Node) -> str:
        raw = str(node.get("resourceType") or node.get("nodeType") or "").strip()
        return _friendly_type(raw) if raw else "Resource"

    def _category_label(node: Node) -> str:
        cat = str(node.get("nodeCategory") or "")
        if cat == "compute":
            return "Compute"
        if cat == "network":
            return "Network"
        if cat == "storage":
            return "Storage"
        if cat == "security":
            return "Security"
        if cat == "policy":
            return "Policy"
        return "Other"

    def _aggregate_icon(node: Node, *, use_categories: bool) -> str:
        if use_categories:
            cat = str(node.get("nodeCategory") or "")
            return _service_icon({"nodeCategory": cat})
        return _service_icon(node)

    def _add_aggregate_services(nodes_to_add: Sequence[Node], parent_id: str, *, use_categories: bool) -> None:
        counts: Dict[Tuple[str, str], int] = {}
        for n in nodes_to_add:
            ocid = str(n.get("nodeId") or "")
            if not ocid:
                continue
            label = _category_label(n) if use_categories else _resource_type_label(n)
            icon = _aggregate_icon(n, use_categories=use_categories)
            counts[(label, icon)] = counts.get((label, icon), 0) + 1
        for label, icon in sorted(counts.keys()):
            count = counts[(label, icon)]
            agg_label = f"{label} (n={count})"
            sid = _service_id("agg_", f"{parent_id}:{label}")
            lines.append(f"    service {sid}({icon})[{_arch_label(agg_label, max_len=64)}] in {parent_id}")

    def _include_for_depth2(node: Node) -> bool:
        if _is_node_type(node, "Compartment"):
            return False
        if _is_node_type(node, "Vcn", "Subnet"):
            return True
        if _is_node_type(node, "Vnic"):
            return False
        ocid = str(node.get("nodeId") or "")
        if not ocid:
            return False
        if _is_node_type(node, *_NETWORK_GATEWAY_NODETYPES, "LoadBalancer"):
            return True
        att = attach_by_res.get(ocid)
        return bool(att and (att.vcn_ocid or att.subnet_ocid))

    def _add_service(node: Node, parent_id: str) -> None:
        ocid = str(node.get("nodeId") or "")
        if not ocid or ocid in node_service_ids:
            return
        sid = _service_id("node_", ocid)
        
        raw_label = _arch_node_label(node)
        # Apply health badge if enrichment failed
        if node.get("enrichStatus") == "ERROR":
            raw_label = f"🔴 {raw_label}"
            
        label = _arch_label(raw_label, max_len=None)
        icon = _service_icon(node)
        lines.append(f"    service {sid}({icon})[{label}] in {parent_id}")
        
        # Apply Environment Class
        env_class = _extract_env_class(node)
        if env_class:
            lines.append(f"    class {sid} {env_class}")
        if node.get("enrichStatus") == "ERROR":
             lines.append(f"    class {sid} alert")
             
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

    tenancy_id = _service_id("tenancy_", tenancy_label)
    lines.append(f"    group {tenancy_id}(cloud)[{_arch_label(tenancy_label, max_len=80)}]")

    # Identify On-Prem / Hybrid nodes (Hybrid Cloud boundary)
    on_prem_nodes = [n for n in nodes if _is_node_type(n, "Cpe", "IpSecConnection")]
    if on_prem_nodes:
        on_prem_id = _service_id("customer_dc_", "customer_dc")
        lines.append(f"    group {on_prem_id}(cloud)[{_arch_label('Customer Data Center', max_len=40)}]")
        for n in on_prem_nodes:
            _add_service(n, on_prem_id)

    nodes_by_region: Dict[str, List[Node]] = {}
    for n in nodes:
        # Some resources like Compartments might not have a region at discovery time
        # if they are global or inherited.
        reg = str(n.get("region") or n.get("regionName") or "Global")
        nodes_by_region.setdefault(reg, []).append(n)

    perim_types = {"Waf", "ApiGateway", "Bastion", "NetworkFirewall"}

    for reg in sorted(nodes_by_region.keys()):
        region_id = _service_id("region_", reg)
        lines.append(f"    group {region_id}(cloud)[{_arch_label('Region: ' + reg, max_len=80)}] in {tenancy_id}")

        region_nodes = nodes_by_region[reg]
        
        # Hub-and-Spoke Detection within region
        hub_vcn_ids: Set[str] = set()
        drg_vcn_map: Dict[str, Set[str]] = {}
        for n in region_nodes:
            if _is_node_type(n, "DrgAttachment"):
                md = _node_metadata(n)
                d_id = _get_meta(md, "drg_id")
                v_id = _get_meta(md, "vcn_id")
                if d_id and v_id:
                    drg_vcn_map.setdefault(d_id, set()).add(v_id)
        
        for v_ids in drg_vcn_map.values():
            if len(v_ids) > 1:
                # Potential hub scenario. If a VCN name contains 'hub' or has a Firewall, mark it.
                for vid in v_ids:
                    node = node_by_id.get(vid, {})
                    name = str(node.get("name") or "").lower()
                    if "hub" in name or "transit" in name or "shared" in name:
                        hub_vcn_ids.add(vid)

        # Security Perimeter (Oracle Pattern)
        perimeter_nodes = [n for n in region_nodes if _is_node_type(n, *perim_types)]
        if perimeter_nodes:
             perimeter_id = _service_id("perimeter_", f"{reg}:perimeter")
             lines.append(f"    group {perimeter_id}(cloud)[{_arch_label('Security Perimeter', max_len=40)}] in {region_id}")
             for n in perimeter_nodes:
                 _add_service(n, perimeter_id)

        region_nodes = nodes_by_region[reg]
        nodes_by_comp: Dict[str, List[Node]] = {}
        for n in region_nodes:
            cid = str(n.get("compartmentId") or "")
            if not cid and _is_node_type(n, "Compartment"):
                cid = str(n.get("nodeId") or "")
            nodes_by_comp.setdefault(cid or "UNKNOWN", []).append(n)

        comp_use_categories: Dict[str, bool] = {}
        if aggregate_workloads:
            for cid, comp_nodes in nodes_by_comp.items():
                candidates = [
                    n
                    for n in comp_nodes
                    if _include_for_depth2(n) and not _is_node_type(n, "Vcn", "Subnet")
                ]
                type_labels = {_resource_type_label(n) for n in candidates}
                comp_use_categories[cid] = len(type_labels) > 5

        for cid in sorted(nodes_by_comp.keys()):
            comp_label = "Compartment: Unknown" if cid == "UNKNOWN" else _compartment_label(node_by_id.get(cid, {"name": cid}))
            comp_group_id = _service_id("comp_", f"{reg}:{cid}")
            lines.append(f"    group {comp_group_id}(cloud)[{_arch_label(comp_label, max_len=80)}] in {region_id}")

            comp_node = node_by_id.get(cid)
            if comp_node and comp_node.get("nodeId"):
                _add_service(comp_node, comp_group_id)

            network_lane_id = _service_id("lane_network_", f"{reg}:{cid}:network")
            lines.append(f"    group {network_lane_id}(cloud)[{_arch_label('Network', max_len=24)}] in {comp_group_id}")

            in_group_id = _service_id("invcn_", f"{reg}:{cid}")
            lines.append(f"    group {in_group_id}(cloud)[{_arch_label('In-VCN', max_len=24)}] in {network_lane_id}")
            out_group_id = ""
            if include_out_of_vcn:
                out_group_id = _service_id("outvcn_", f"{reg}:{cid}")
                lines.append(
                    f"    group {out_group_id}(cloud)[{_arch_label('Out-of-VCN Services', max_len=48)}] in {comp_group_id}"
                )

            comp_nodes = [n for n in nodes_by_comp[cid] if not _is_node_type(n, "Compartment")]
            if aggregate_workloads:
                comp_nodes = [n for n in comp_nodes if _include_for_depth2(n)]
            elif not include_workloads:
                comp_nodes = [
                    n
                    for n in comp_nodes
                    if _is_node_type(n, "Vcn", "Subnet", *_NETWORK_GATEWAY_NODETYPES)
                ]

            comp_vcn_ids: List[str] = sorted(list({
                str(n.get("nodeId") or "")
                for n in comp_nodes
                if _is_node_type(n, "Vcn") and n.get("nodeId")
            }))
            
            # Sort VCNs: Hubs first, then Spokes
            comp_vcn_ids.sort(key=lambda x: (0 if x in hub_vcn_ids else 1, x))

            for vcn_ocid in comp_vcn_ids:
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
                    if aggregate_workloads:
                        _add_aggregate_services(
                            gateway_nodes,
                            gateways_id,
                            use_categories=comp_use_categories.get(cid, False),
                        )
                    else:
                        for n in sorted(gateway_nodes, key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or ""))):
                            _add_service(n, gateways_id)

                if vcn_level_nodes and include_vcn_level:
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
                    if att and att.subnet_ocid and att.vcn_ocid == vcn_ocid:
                        vcn_subnet_ids.add(att.subnet_ocid)

                for sn_ocid in sorted(vcn_subnet_ids):
                    sn = node_by_id.get(sn_ocid, {"name": sn_ocid, "nodeType": "Subnet"})
                    subnet_group_id = _service_id("subnet_", f"{cid}:{vcn_ocid}:{sn_ocid}")
                    lines.append(f"    group {subnet_group_id}(cloud)[{_arch_label(_subnet_label(sn), max_len=80)}] in {vcn_group_id}")
                    _add_service(sn, subnet_group_id)

                    if include_workloads:
                        attached = [
                            n
                            for n in comp_nodes
                            if attach_by_res.get(str(n.get("nodeId") or ""))
                            and attach_by_res[str(n.get("nodeId") or "")].subnet_ocid == sn_ocid
                            and not _is_node_type(n, "Vcn", "Subnet")
                        ]
                        if aggregate_workloads:
                            _add_aggregate_services(
                                attached,
                                subnet_group_id,
                                use_categories=comp_use_categories.get(cid, False),
                            )
                        else:
                            # Map to AD/FD if present
                            nodes_by_ad: Dict[str, List[Node]] = {}
                            for n in attached:
                                meta = _node_metadata(n)
                                ad_name = str(n.get("availabilityDomain") or _get_meta(meta, "availability_domain") or "Regional").strip()
                                nodes_by_ad.setdefault(ad_name, []).append(n)
                            
                            for ad_name in sorted(nodes_by_ad.keys()):
                                if ad_name == "Regional":
                                    for n in sorted(nodes_by_ad[ad_name], key=lambda x: str(x.get("name") or "")):
                                        _add_service(n, subnet_group_id)
                                else:
                                    ad_id = _service_id("ad_", f"{subnet_group_id}:{ad_name}")
                                    lines.append(f"    group {ad_id}(server)[{_arch_label(ad_name, max_len=40)}] in {subnet_group_id}")
                                    for n in sorted(nodes_by_ad[ad_name], key=lambda x: str(x.get("name") or "")):
                                        _add_service(n, ad_id)

                if unknown_subnet_nodes:
                    unknown_id = _service_id("subnet_unknown_", f"{cid}:{vcn_ocid}")
                    lines.append(f"    group {unknown_id}(cloud)[{_arch_label('Subnet: Unknown', max_len=40)}] in {vcn_group_id}")
                    if aggregate_workloads:
                        _add_aggregate_services(
                            unknown_subnet_nodes,
                            unknown_id,
                            use_categories=comp_use_categories.get(cid, False),
                        )
                    else:
                        for n in sorted(unknown_subnet_nodes, key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or ""))):
                            _add_service(n, unknown_id)

        out_nodes: List[Node] = []
        for n in comp_nodes:
            if _is_node_type(n, "Vcn", "Subnet"):
                continue
            ocid = str(n.get("nodeId") or "")
            att = attach_by_res.get(ocid)
            if att and att.vcn_ocid and vcn_owner_by_id.get(att.vcn_ocid) == cid:
                continue
            out_nodes.append(n)

        if include_out_of_vcn:
            lane_groups = _group_nodes_by_lane(out_nodes)
            for lane, lane_nodes in lane_groups.items():
                lane_group_id = _service_id(f"lane_out_{lane}_", f"{cid}:{lane}")
                lines.append(
                    f"    group {lane_group_id}(cloud)[{_arch_label(_lane_label(lane), max_len=40)}] in {out_group_id}"
                )
                for n in sorted(
                    lane_nodes,
                    key=lambda n: (
                        str(n.get("nodeCategory") or ""),
                        str(n.get("nodeType") or ""),
                        str(n.get("name") or ""),
                    ),
                ):
                    _add_service(n, lane_group_id)

        if include_edges:
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
                        key=lambda n: (
                            str(n.get("nodeCategory") or ""),
                            str(n.get("nodeType") or ""),
                            str(n.get("name") or ""),
                        ),
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

    if include_edges and gateway_service_ids:
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

    if include_edges:
        rel_lines = _render_arch_relationship_edges(
            edges,
            node_ids=rendered_node_ids,
            node_id_map=node_service_ids,
            include_admin_edges=False,
            seen_pairs=seen_arch_edges,
        )
        lines.extend(rel_lines)

    size = _mermaid_text_size(lines)
    if size > MAX_MERMAID_TEXT_CHARS and _allow_split:
        split_mode, groups = _consolidated_split_groups(nodes)
        if len(groups) > 1:
            part_paths: List[Path] = []
            for key, group_nodes in groups.items():
                if not group_nodes:
                    continue
                group_ids = {str(n.get("nodeId") or "") for n in group_nodes if n.get("nodeId")}
                group_edges = _filter_edges_for_nodes(edges, group_ids)
                slug = _slugify(key, max_len=32)
                part_path = outdir / f"diagram.consolidated.architecture.{split_mode}.{slug}.mmd"
                part_paths.extend(
                    _write_consolidated_mermaid(
                        outdir,
                        group_nodes,
                        group_edges,
                        diagram_paths,
                        depth=depth,
                        _requested_depth=depth,
                        path=part_path,
                        summary=summary,
                        _allow_split=False,
                    )
                )
            note = f"Consolidated diagram split by {split_mode} due to Mermaid size limits."
            stub_path = _write_consolidated_stub(
                consolidated,
                kind="architecture",
                note=note,
                part_paths=part_paths,
                tenancy_label=tenancy_label,
            )
            _record_diagram_split(
                summary,
                diagram=consolidated.name,
                parts=sorted({p.name for p in part_paths}),
                size=size,
                limit=MAX_MERMAID_TEXT_CHARS,
                reason=f"split_{split_mode}",
            )
            return [stub_path] + part_paths
    if size > MAX_MERMAID_TEXT_CHARS and depth > 1:
        LOG.warning(
            "Architecture consolidated diagram exceeds Mermaid max text size (%s chars); reducing depth from %s to %s.",
            size,
            depth,
            depth - 1,
        )
        return _write_consolidated_mermaid(
            outdir,
            nodes,
            edges,
            diagram_paths,
            depth=depth - 1,
            _requested_depth=requested_depth,
            path=consolidated,
            summary=summary,
            _allow_split=_allow_split,
        )
    if depth != requested_depth:
        lines.insert(
            1,
            (
                f"%% NOTE: consolidated depth reduced from {requested_depth} to {depth} "
                "to stay within Mermaid text size limits."
            ),
        )
    if size > MAX_MERMAID_TEXT_CHARS:
        LOG.warning(
            "Architecture consolidated diagram exceeds Mermaid max text size (%s chars) at depth %s; diagram may not render.",
            size,
            depth,
        )
        lines.insert(
            1,
            (
                f"%% WARNING: diagram text size {size} exceeds Mermaid limit {MAX_MERMAID_TEXT_CHARS} "
                "and may not render."
            ),
        )
    consolidated.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return [consolidated]


def _write_consolidated_flowchart(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    depth: int = 3,
    _requested_depth: Optional[int] = None,
    path: Optional[Path] = None,
    summary: Optional[DiagramSummary] = None,
    _allow_split: bool = True,
) -> List[Path]:
    path = path or (outdir / "diagram.consolidated.flowchart.mmd")
    requested_depth = depth if _requested_depth is None else _requested_depth
    if depth > 1:
        lines = _detailed_flowchart_lines(nodes, edges, depth=depth)
    else:
        lines = _global_flowchart_lines(nodes)
    
    size = _mermaid_text_size(lines)
    if size > MAX_MERMAID_TEXT_CHARS and _allow_split:
        split_mode, groups = _consolidated_split_groups(nodes)
        if len(groups) > 1:
            part_paths: List[Path] = []
            for key, group_nodes in groups.items():
                if not group_nodes:
                    continue
                group_ids = {str(n.get("nodeId") or "") for n in group_nodes if n.get("nodeId")}
                group_edges = _filter_edges_for_nodes(edges, group_ids)
                slug = _slugify(key, max_len=32)
                part_path = outdir / f"diagram.consolidated.flowchart.{split_mode}.{slug}.mmd"
                part_paths.extend(
                    _write_consolidated_flowchart(
                        outdir,
                        group_nodes,
                        group_edges,
                        depth=depth,
                        _requested_depth=depth,
                        path=part_path,
                        summary=summary,
                        _allow_split=False,
                    )
                )
            note = f"Consolidated diagram split by {split_mode} due to Mermaid size limits."
            stub_path = _write_consolidated_stub(
                path,
                kind="flowchart",
                note=note,
                part_paths=part_paths,
                tenancy_label=_tenancy_label(nodes),
            )
            _record_diagram_split(
                summary,
                diagram=path.name,
                parts=sorted({p.name for p in part_paths}),
                size=size,
                limit=MAX_MERMAID_TEXT_CHARS,
                reason=f"split_{split_mode}",
            )
            return [stub_path] + part_paths
    if size > MAX_MERMAID_TEXT_CHARS and depth > 1:
        LOG.warning(
            "Flowchart consolidated diagram exceeds Mermaid max text size (%s chars); reducing depth from %s to %s.",
            size,
            depth,
            depth - 1,
        )
        return _write_consolidated_flowchart(
            outdir,
            nodes,
            edges,
            depth=depth - 1,
            _requested_depth=requested_depth,
            path=path,
            summary=summary,
            _allow_split=_allow_split,
        )
    insert_at = 1 if lines else 0
    if requested_depth > 1:
        lines.insert(insert_at, "%% NOTE: global map renders at depth 1 (tenancy + regions).")
        insert_at += 1
    if depth != requested_depth:
        lines.insert(
            insert_at,
            (
                f"%% NOTE: consolidated depth reduced from {requested_depth} to {depth} "
                "to stay within Mermaid text size limits."
            ),
        )
        insert_at += 1
    if size > MAX_MERMAID_TEXT_CHARS:
        LOG.warning(
            "Flowchart consolidated diagram exceeds Mermaid max text size (%s chars) at depth %s; diagram may not render.",
            size,
            depth,
        )
        lines.insert(
            insert_at,
            (
                f"%% WARNING: diagram text size {size} exceeds Mermaid limit {MAX_MERMAID_TEXT_CHARS} "
                "and may not render."
            ),
        )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return [path]
