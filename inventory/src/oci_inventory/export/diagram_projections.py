from __future__ import annotations

import json
import os
import re
import subprocess
import hashlib
import importlib
import time
import base64
from dataclasses import dataclass
import logging
from pathlib import Path
from shutil import which
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

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

ARCH_MAX_COMPARTMENTS = 2
ARCH_MAX_VCNS_PER_COMPARTMENT = 3
ARCH_MAX_WORKLOADS = 60
ARCH_MAX_VCNS = 60
ARCH_MAX_TIER_NODES = 8
ARCH_MIN_WORKLOAD_NODES = 5
ARCH_MAX_ARCH_NODES = 24
ARCH_MAX_ARCH_EDGES = 40
ARCH_MAX_ARCH_LANE_NODES = 3
ARCH_ARCH_IMAGE_PX = 36
ARCH_ARCH_OVERVIEW_PARTS = 10
ARCH_MAX_ARCH_OVERVIEW_SUBNETS = 8
ARCH_MAX_ARCH_PARTS = 400
ARCH_MAX_ARCH_GROUPS_PER_PART = 6
TENANCY_OVERVIEW_TOP_N = 15
CONSOLIDATED_OVERVIEW_TOP_N = 12
TENANCY_SPLIT_TOP_N = 30
CONSOLIDATED_SPLIT_TOP_N = 25
ARCH_TENANCY_TOP_N = 10
ARCH_LANE_TOP_N = 6
ARCH_CONSOLIDATED_TOP_N = 10

_ARCH_FILTER_NODETYPES: Set[str] = {
    "LogAnalyticsEntity",
    "Log",
    "LogGroup",
    "LogAnalyticsLogGroup",
    "ServiceConnector",
}

CONSOLIDATED_WORKLOAD_TOP_N = 8


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
    summary.setdefault("violations", [])
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


def _record_diagram_violation(
    summary: Optional[DiagramSummary],
    *,
    diagram: str,
    rule: str,
    detail: str,
) -> None:
    if summary is None:
        return
    summary["violations"].append(
        {
            "diagram": diagram,
            "rule": rule,
            "detail": detail,
        }
    )


def _compact_scope_label(value: str, *, max_len: int = 64) -> str:
    compact = " ".join(str(value or "").split())
    if not compact:
        return "unknown"
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3] + "..."


def _insert_scope_view_comments(
    lines: List[str],
    *,
    scope: str,
    view: str,
    part: Optional[str] = None,
) -> None:
    insert_at = 2 if len(lines) >= 2 else len(lines)
    comments = [f"%% Scope: {scope}", f"%% View: {view}"]
    if part:
        comments.append(f"%% Part: {part}")
    for idx, line in enumerate(comments):
        lines.insert(insert_at + idx, line)


def _insert_part_comment(lines: List[str], part: str) -> None:
    insert_at = 4 if len(lines) >= 4 else len(lines)
    lines.insert(insert_at, f"%% Part: {part}")


def _extract_scope_view(text: str) -> Tuple[str, str, str]:
    scope = ""
    view = ""
    part = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("%% Scope:"):
            scope = line[len("%% Scope:") :].strip()
        elif line.startswith("%% View:"):
            view = line[len("%% View:") :].strip()
        elif line.startswith("%% Part:"):
            part = line[len("%% Part:") :].strip()
    return scope, view, part


def _render_overlay_lanes(
    lines: List[str],
    *,
    scope_key: str,
    make_group_id: Callable[[str], str],
    overlay_nodes: Sequence[Node],
    edge_node_id_map: Mapping[str, str],
    indent: str = "    ",
) -> None:
    overlay_groups = _group_nodes_by_lane(overlay_nodes)
    overlay_groups = {k: v for k, v in overlay_groups.items() if k in {"iam", "security"}}
    if not overlay_groups:
        return

    overlay_id = make_group_id(f"{scope_key}:overlays")
    lines.append(f"{indent}subgraph {overlay_id}[\"Functional Overlays\"]")
    lines.append(f"{indent}  direction TB")
    for lane, lane_nodes in overlay_groups.items():
        lane_id = make_group_id(f"{scope_key}:overlays:{lane}")
        lane_label = _lane_label(lane)
        lines.append(f"{indent}  subgraph {lane_id}[\"{lane_label}\"]")
        lines.append(f"{indent}    direction TB")
        for n in lane_nodes:
            ocid = str(n.get("nodeId") or "")
            if not ocid:
                continue
            overlay_node_id = _mermaid_id(f"overlay:{scope_key}:{ocid}")
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
        lines.append(f"{indent}  end")
    lines.append(f"{indent}end")


def _render_overlay_summary(
    lines: List[str],
    *,
    scope_key: str,
    make_group_id: Callable[[str], str],
    overlay_nodes: Sequence[Node],
    indent: str = "    ",
) -> None:
    counts: Dict[str, int] = {"iam": 0, "security": 0}
    for n in overlay_nodes:
        lane = _lane_for_node(n)
        if lane in counts:
            counts[lane] += 1
    if not any(counts.values()):
        return

    overlay_id = make_group_id(f"{scope_key}:overlays")
    lines.append(f"{indent}subgraph {overlay_id}[\"Functional Overlays\"]")
    lines.append(f"{indent}  direction TB")
    for lane, count in counts.items():
        if count <= 0:
            continue
        lane_id = make_group_id(f"{scope_key}:overlays:{lane}")
        lane_label = _lane_label(lane)
        label = f"{lane_label} ({count})"
        cls = "policy" if lane == "iam" else "security"
        lines.extend(_render_node_with_class(lane_id, label, cls=cls, shape="rect"))
    lines.append(f"{indent}end")


def _scan_guideline_violations(
    path: Path,
    *,
    nodes: Sequence[Node],
    summary: Optional[DiagramSummary],
) -> None:
    if summary is None:
        return
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        _record_diagram_violation(
            summary,
            diagram=path.name,
            rule="diagram_read_failed",
            detail="Unable to read diagram text for guideline checks.",
        )
        return

    ocid_hits = text.count("ocid1.")
    if ocid_hits:
        _record_diagram_violation(
            summary,
            diagram=path.name,
            rule="no_ocids_in_labels",
            detail=f"Detected {ocid_hits} ocid1.* occurrences in diagram text.",
        )

    if path.name == "diagram.consolidated.flowchart.mmd":
        scope, view, _part = _extract_scope_view(text)
        if scope != "tenancy":
            _record_diagram_violation(
                summary,
                diagram=path.name,
                rule="scope_comment",
                detail="Expected Scope: tenancy for consolidated flowchart.",
            )
        if view != "overview":
            _record_diagram_violation(
                summary,
                diagram=path.name,
                rule="view_comment",
                detail="Expected View: overview for consolidated flowchart.",
            )
        if "flowchart TD" not in text:
            _record_diagram_violation(
                summary,
                diagram=path.name,
                rule="consolidated_flowchart_direction",
                detail="Expected flowchart TD for consolidated flowchart output.",
            )
        if "%% Global Connectivity Map" in text:
            if any(token in text for token in ("Compartment:", "VCN:", "Subnet:")):
                _record_diagram_violation(
                    summary,
                    diagram=path.name,
                    rule="global_depth1_scope",
                    detail="Global map includes compartment/VCN/subnet labels at depth 1.",
                )
        if "%% Consolidated Summary Flowchart" in text:
            if "Region:" not in text:
                _record_diagram_violation(
                    summary,
                    diagram=path.name,
                    rule="summary_missing_region",
                    detail="Summary flowchart is missing Region labels.",
                )
            comp_count = len([n for n in nodes if _is_node_type(n, "Compartment")])
            if comp_count and "Compartment:" not in text:
                _record_diagram_violation(
                    summary,
                    diagram=path.name,
                    rule="summary_missing_compartment",
                    detail="Summary flowchart is missing Compartment labels.",
                )

    if path.name == "diagram.tenancy.mmd":
        scope, view, _part = _extract_scope_view(text)
        if scope != "tenancy":
            _record_diagram_violation(
                summary,
                diagram=path.name,
                rule="scope_comment",
                detail="Expected Scope: tenancy for tenancy diagram.",
            )
        if view != "overview":
            _record_diagram_violation(
                summary,
                diagram=path.name,
                rule="view_comment",
                detail="Expected View: overview for tenancy diagram.",
            )
        if "flowchart LR" not in text:
            _record_diagram_violation(
                summary,
                diagram=path.name,
                rule="tenancy_direction",
                detail="Expected flowchart LR for tenancy diagram.",
            )
    if path.name.startswith("diagram.network.") and path.name.endswith(".mmd"):
        scope, view, _part = _extract_scope_view(text)
        if not scope.startswith("vcn:"):
            _record_diagram_violation(
                summary,
                diagram=path.name,
                rule="scope_comment",
                detail="Expected Scope: vcn:<name> for network diagram.",
            )
        if view != "full-detail":
            _record_diagram_violation(
                summary,
                diagram=path.name,
                rule="view_comment",
                detail="Expected View: full-detail for network diagram.",
            )
    if path.name.startswith("diagram.workload.") and path.name.endswith(".mmd"):
        scope, view, part = _extract_scope_view(text)
        if not scope.startswith("workload:"):
            _record_diagram_violation(
                summary,
                diagram=path.name,
                rule="scope_comment",
                detail="Expected Scope: workload:<name> for workload diagram.",
            )
        if view not in {"full-detail", "overview"}:
            _record_diagram_violation(
                summary,
                diagram=path.name,
                rule="view_comment",
                detail="Expected View: full-detail or overview for workload diagram.",
            )
        if ".part" in path.name and not part:
            _record_diagram_violation(
                summary,
                diagram=path.name,
                rule="part_comment",
                detail="Expected Part: N/M comment for workload part diagram.",
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


def _semantic_id_key(value: str) -> str:
    return str(value or "")


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
    # Semantic, deterministic Mermaid node IDs (no hashed/hex IDs).
    clean = _semantic_id_key(key)
    full = _slugify(clean, max_len=512)
    max_len = 160
    slug = full[:max_len]
    if len(full) > max_len:
        suffix = full[-8:] or "suffix"
        head_len = max_len - (len(suffix) + 1)
        slug = f"{full[:head_len]}_{suffix}"
    if not slug:
        slug = "node"
    if not slug[0].isalpha():
        slug = f"n_{slug}"
    return slug


def _unique_mermaid_id_factory(reserved: Optional[Iterable[str]] = None) -> Callable[[str], str]:
    used: Set[str] = set(reserved or [])
    counts: Dict[str, int] = {}

    def _make(key: str) -> str:
        base = _mermaid_id(key)
        if base in used:
            count = counts.get(base, 1) + 1
            candidate = f"{base}_{count}"
            while candidate in used:
                count += 1
                candidate = f"{base}_{count}"
            counts[base] = count
            base = candidate
        else:
            counts[base] = 1
        used.add(base)
        return base

    return _make


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


def _flowchart_elk_init_line() -> str:
    return (
        "%%{init: {\"flowchart\": {\"defaultRenderer\": \"elk\", "
        "\"nodeSpacing\": 80, \"rankSpacing\": 80, \"wrappingWidth\": 260}} }%%"
    )


def _compact_label(value: str, *, max_len: int = 40) -> str:
    safe = str(value or "").replace('"', "'").strip()
    if len(safe) <= max_len:
        return safe
    return f"{safe[: max_len - 3].rstrip()}..."


def _vcn_label_compact(node: Node) -> str:
    name = _compact_label(str(node.get("name") or "VCN").strip(), max_len=48)
    return f"VCN: {name}"


def _subnet_label_compact(node: Node) -> str:
    meta = _node_metadata(node)
    name = _compact_label(str(node.get("name") or "Subnet").strip(), max_len=48)
    prohibit = _get_meta(meta, "prohibit_public_ip_on_vnic")
    vis = "private" if prohibit is True else "public" if prohibit is False else "subnet"
    return f"Subnet: {name} ({vis})"


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
    safe = safe.replace("|", " ")
    safe = safe.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    safe = safe.replace("[", "&#91;").replace("]", "&#93;")
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


def _render_node_with_class(node_id: str, label: str, *, cls: str, shape: str = "rect") -> List[str]:
    lines = [_render_node(node_id, label, shape=shape)]
    classes = [c for c in (cls or "").split() if c]
    for class_name in classes:
        lines.append(f"  class {node_id} {class_name}")
    return lines


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


def _compartment_alias_map(nodes: Sequence[Node]) -> Dict[str, str]:
    ids: Set[str] = set()
    for n in nodes:
        cid = str(n.get("compartmentId") or "")
        if cid:
            ids.add(cid)
        if _is_node_type(n, "Compartment") and n.get("nodeId"):
            ids.add(str(n.get("nodeId") or ""))
    ordered = sorted(ids)
    return {cid: f"Compartment-{i:02d}" for i, cid in enumerate(ordered, start=1)}


def _compartment_label_by_id(
    compartment_id: str,
    *,
    node_by_id: Mapping[str, Node],
    alias_by_id: Mapping[str, str],
) -> str:
    cid = str(compartment_id or "")
    if not cid or cid == "UNKNOWN":
        return "Compartment: Unknown"
    node = node_by_id.get(cid, {})
    name = str(node.get("name") or "").strip()
    if name and not name.startswith("ocid1"):
        alias = alias_by_id.get(cid)
        if alias:
            return f"Compartment: {name} ({alias})"
        return f"Compartment: {name}"
    alias = alias_by_id.get(cid)
    if alias:
        return f"Compartment: {alias}"
    if name:
        return f"Compartment: {name}"
    return "Compartment: Unknown"


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
    reserved_ids = {_mermaid_id(str(n.get("nodeId") or "")) for n in nodes if n.get("nodeId")}
    make_group_id = _unique_mermaid_id_factory(reserved_ids)
    lines: List[str] = [_flowchart_elk_init_line(), "flowchart TD"]
    _insert_scope_view_comments(lines, scope="tenancy", view="overview")
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
    reserved_ids = {_mermaid_id(str(n.get("nodeId") or "")) for n in nodes if n.get("nodeId")}
    make_group_id = _unique_mermaid_id_factory(reserved_ids)
    lines: List[str] = [_flowchart_elk_init_line(), "flowchart TD"]
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
    tenancy_id = make_group_id(f"flow:tenancy:{tenancy_label}")
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
        region_id = make_group_id(f"flow:region:{reg}")
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
            comp_id = make_group_id(f"flow:comp:{reg}:{cid}")
            lines.append(f"    subgraph {comp_id}[\"{comp_label}\"]")
            lines.append("      direction TB")

            comp_nodes = nodes_by_comp[cid]
            if depth == 2:
                comp_nodes = [n for n in comp_nodes if _include_for_depth2_local(n)]
            
            vcns = [n for n in comp_nodes if _is_node_type(n, "Vcn")]
            for vcn in sorted(vcns, key=lambda n: str(n.get("name") or "")):
                vcn_ocid = str(vcn.get("nodeId") or "")
                vcn_id = make_group_id(vcn_ocid)
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
                    sn_id = make_group_id(sn_ocid)
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


def _consolidated_flowchart_summary_lines(
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    depth: int = 3,
) -> List[str]:
    reserved_ids = {_mermaid_id(str(n.get("nodeId") or "")) for n in nodes if n.get("nodeId")}
    make_group_id = _unique_mermaid_id_factory(reserved_ids)
    lines: List[str] = [_flowchart_elk_init_line(), "flowchart TD"]
    _insert_scope_view_comments(lines, scope="tenancy", view="overview")
    lines.extend(_style_block_lines())
    lines.append("%% Consolidated Summary Flowchart")

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

    def _summary_counts(group_nodes: Sequence[Node]) -> Dict[str, int]:
        counts: Dict[str, int] = {"compute": 0, "network": 0, "storage": 0, "policy": 0, "other": 0}
        for n in group_nodes:
            if _is_node_type(n, "Compartment", "Vcn", "Subnet", "Vnic", "PrivateIp"):
                continue
            cls = _node_class(n)
            if cls not in counts:
                cls = "other"
            counts[cls] += 1
        return counts

    def _render_summary_nodes(scope: str, group_nodes: Sequence[Node]) -> None:
        counts = _summary_counts(group_nodes)
        order = [
            ("compute", "Compute"),
            ("network", "Network"),
            ("storage", "Storage"),
            ("policy", "Policy / IAM"),
            ("other", "Other"),
        ]
        for key, label in order:
            count = counts.get(key, 0)
            if count <= 0:
                continue
            node_id = _mermaid_id(f"summary:{scope}:{key}")
            cls = f"summary {key}" if key != "other" else "summary boundary"
            lines.extend(_render_node_with_class(node_id, f"{label} ({count})", cls=cls, shape="rect"))

    tenancy_label = _tenancy_label(nodes)
    tenancy_id = make_group_id(f"flow:tenancy:{tenancy_label}")
    lines.append(f"subgraph {tenancy_id}[\"{_compact_label(tenancy_label, max_len=64)}\"]")
    lines.append("  direction TB")

    region_id_map: Dict[str, str] = {}
    nodes_by_region: Dict[str, List[Node]] = {}
    for n in nodes:
        reg = str(n.get("region") or n.get("regionName") or "Global")
        nodes_by_region.setdefault(reg, []).append(n)

    for reg in sorted(nodes_by_region.keys()):
        region_id = make_group_id(f"flow:region:{reg}")
        region_id_map[reg] = region_id
        lines.extend(_render_node_with_class(region_id, f"Region: {reg}", cls="region", shape="round"))

        region_nodes = nodes_by_region[reg]
        nodes_by_comp: Dict[str, List[Node]] = {}
        for n in region_nodes:
            cid = str(n.get("compartmentId") or "")
            if not cid and _is_node_type(n, "Compartment"):
                cid = str(n.get("nodeId") or "")
            nodes_by_comp.setdefault(cid or "UNKNOWN", []).append(n)

        lines.append(f"  %% Region overlay: {reg}")
        for cid in sorted(nodes_by_comp.keys()):
            comp_node = node_by_id.get(cid, {"name": cid, "nodeType": "Compartment"})
            comp_name = _compact_label(str(comp_node.get("name") or cid), max_len=48)
            comp_label = _compartment_label({"name": comp_name})
            comp_id = make_group_id(f"flow:comp:{reg}:{cid}")
            lines.append(f"  subgraph {comp_id}[\"{comp_label}\"]")
            lines.append("    direction TB")

            comp_nodes = nodes_by_comp[cid]
            vcns = [n for n in comp_nodes if _is_node_type(n, "Vcn")]
            for vcn in sorted(vcns, key=lambda n: str(n.get("name") or "")):
                vcn_ocid = str(vcn.get("nodeId") or "")
                vcn_id = make_group_id(vcn_ocid)
                vcn_label = _vcn_label_compact(vcn)
                lines.append(f"    subgraph {vcn_id}[\"{vcn_label}\"]")
                lines.append("      direction TB")

                vcn_resources: List[Node] = []
                for n in comp_nodes:
                    ocid = str(n.get("nodeId") or "")
                    if not ocid or _is_node_type(n, "Vcn", "Subnet"):
                        continue
                    att = attach_by_res.get(ocid)
                    if att and att.vcn_ocid == vcn_ocid and not att.subnet_ocid:
                        vcn_resources.append(n)
                    elif not att:
                        meta = _node_metadata(n)
                        vcn_ref = edge_vcn_by_src.get(ocid) or _get_meta(meta, "vcn_id")
                        if vcn_ref == vcn_ocid:
                            vcn_resources.append(n)

                if vcn_resources:
                    vcn_level_id = make_group_id(f"flow:vcn:{vcn_ocid}:level")
                    lines.append(f"        subgraph {vcn_level_id}[\"VCN-level Resources\"]")
                    lines.append("          direction TB")
                    _render_summary_nodes(f"vcn:{vcn_ocid}", vcn_resources)
                    lines.append("      end")

                comp_subnets = [
                    n
                    for n in comp_nodes
                    if _is_node_type(n, "Subnet") and subnet_to_vcn.get(str(n.get("nodeId") or "")) == vcn_ocid
                ]
                for sn in sorted(comp_subnets, key=lambda n: str(n.get("name") or "")):
                    sn_ocid = str(sn.get("nodeId") or "")
                    sn_id = make_group_id(sn_ocid)
                    sn_label = _subnet_label_compact(sn)
                    lines.append(f"        subgraph {sn_id}[\"{sn_label}\"]")
                    lines.append("          direction TB")
                    attached = [
                        n
                        for n in comp_nodes
                        if attach_by_res.get(str(n.get("nodeId") or ""))
                        and attach_by_res[str(n.get("nodeId") or "")].subnet_ocid == sn_ocid
                        and not _is_node_type(n, "Vcn", "Subnet")
                    ]
                    _render_summary_nodes(f"subnet:{sn_ocid}", attached)
                    lines.append("      end")
                lines.append("    end")

            other_nodes = [
                n
                for n in comp_nodes
                if not _is_node_type(n, "Vcn", "Subnet", "Compartment")
                and not attach_by_res.get(str(n.get("nodeId") or ""))
            ]
            if other_nodes:
                out_id = make_group_id(f"flow:comp:{reg}:{cid}:out_vcn")
                lines.append(f"    subgraph {out_id}[\"Out-of-VCN Services\"]")
                lines.append("      direction TB")
                _render_summary_nodes(f"out:{reg}:{cid}", other_nodes)
                lines.append("    end")

            lines.append("  end")
    lines.append("end")

    for region_a, region_b in sorted(_rpc_region_links(nodes)):
        src = region_id_map.get(region_a)
        dst = region_id_map.get(region_b)
        if src and dst:
            lines.append(_render_edge(src, dst, label="RPC"))

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


def _overview_top_counts(items: Sequence[Tuple[str, int]], top_n: int) -> Tuple[List[Tuple[str, int]], int]:
    items = [(label, count) for label, count in items if count > 0]
    items.sort(key=lambda item: (-item[1], item[0]))
    top = items[:top_n]
    rest_count = sum(count for _label, count in items[top_n:])
    return top, rest_count


def _top_compartment_counts(nodes: Sequence[Node]) -> List[Tuple[str, int]]:
    comp_nodes = [n for n in nodes if _is_node_type(n, "Compartment") and n.get("nodeId")]
    comp_ids = {str(n.get("nodeId") or "") for n in comp_nodes}
    parents = _compartment_parent_map(nodes)
    alias_by_comp = _compartment_alias_map(nodes)
    node_by_id = {str(n.get("nodeId") or ""): n for n in comp_nodes if n.get("nodeId")}
    counts: Dict[str, int] = {}
    for n in nodes:
        if _is_node_type(n, "Compartment"):
            continue
        cid = str(n.get("compartmentId") or "")
        if not cid:
            continue
        root = _root_compartment_id(cid, parents) if cid in comp_ids or cid in parents else cid
        counts[root] = counts.get(root, 0) + 1
    results: List[Tuple[str, int]] = []
    for cid, count in counts.items():
        label = _compartment_label_by_id(cid, node_by_id=node_by_id, alias_by_id=alias_by_comp)
        results.append((_tenancy_safe_label("", label), count))
    return results


def _top_vcn_counts(nodes: Sequence[Node]) -> List[Tuple[str, int]]:
    counts: Dict[str, int] = {}
    for n in nodes:
        if not _is_node_type(n, "Vcn"):
            continue
        label = _vcn_label_compact(n)
        counts[label] = counts.get(label, 0) + 1
    return [(label, count) for label, count in counts.items()]


def _top_workload_counts(nodes: Sequence[Node]) -> List[Tuple[str, int]]:
    workload_candidates = [n for n in nodes if n.get("nodeId")]
    wl_groups = {k: list(v) for k, v in group_workload_candidates(workload_candidates).items()}
    results: List[Tuple[str, int]] = []
    for wl_name, wl_nodes in wl_groups.items():
        if not wl_nodes:
            continue
        results.append((f"Workload: {wl_name}", len(wl_nodes)))
    return results


def _compact_overview_lines(
    *,
    nodes: Sequence[Node],
    title: str,
    top_n: int,
    include_workloads: bool = True,
) -> List[str]:
    lines: List[str] = [_flowchart_elk_init_line(), "flowchart LR"]
    _insert_scope_view_comments(lines, scope="tenancy", view="overview")
    lines.extend(_style_block_lines())
    lines.append(f"%% {title}")
    tenancy_label = _tenancy_label(nodes).replace('"', "'")
    tenancy_id = _mermaid_id(f"overview:{title}:tenancy")
    lines.append(f"subgraph {tenancy_id}[\"{tenancy_label}\"]")
    lines.append("  direction LR")

    regions = _region_list(nodes)
    if regions:
        lines.append("  subgraph overview_regions[\"Regions\"]")
        lines.append("    direction LR")
        for region in regions:
            node_id = _mermaid_id(f"overview:region:{region}")
            lines.extend(_render_node_with_class(node_id, f"Region: {region}", cls="region", shape="round"))
        lines.append("  end")

    comp_items = _top_compartment_counts(nodes)
    top_comp, rest_comp = _overview_top_counts(comp_items, top_n)
    lines.append("  subgraph overview_compartments[\"Top Compartments\"]")
    lines.append("    direction TB")
    for label, count in top_comp:
        node_id = _mermaid_id(f"overview:comp:{label}")
        lines.append(f"    {node_id}[\"{label} (n={count})\"]")
    if rest_comp:
        node_id = _mermaid_id("overview:comp:other")
        lines.append(f"    {node_id}[\"Other Compartments (n={rest_comp})\"]")
    lines.append("  end")

    vcn_items = _top_vcn_counts(nodes)
    top_vcn, rest_vcn = _overview_top_counts(vcn_items, top_n)
    if top_vcn:
        lines.append("  subgraph overview_vcns[\"Top VCNs\"]")
        lines.append("    direction TB")
        for label, count in top_vcn:
            node_id = _mermaid_id(f"overview:vcn:{label}")
            lines.append(f"    {node_id}[\"{label} (n={count})\"]")
        if rest_vcn:
            node_id = _mermaid_id("overview:vcn:other")
            lines.append(f"    {node_id}[\"Other VCNs (n={rest_vcn})\"]")
        lines.append("  end")

    if include_workloads:
        wl_items = _top_workload_counts(nodes)
        top_wl, rest_wl = _overview_top_counts(wl_items, top_n)
        if top_wl:
            lines.append("  subgraph overview_workloads[\"Top Workloads\"]")
            lines.append("    direction TB")
            for label, count in top_wl:
                node_id = _mermaid_id(f"overview:wl:{label}")
                lines.append(f"    {node_id}[\"{label} (n={count})\"]")
            if rest_wl:
                node_id = _mermaid_id("overview:wl:other")
                lines.append(f"    {node_id}[\"Other Workloads (n={rest_wl})\"]")
            lines.append("  end")

    lines.append("end")
    return lines


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
    summary: Optional[DiagramSummary] = None,
    _requested_depth: Optional[int] = None,
    _allow_split: bool = True,
    _split_modes: Optional[Sequence[str]] = None,
    _split_scope_label: Optional[str] = None,
    _split_reason: Optional[str] = None,
    _split_purpose: Optional[str] = None,
) -> Path:
    # Scope: tenancy (overview). View: overview with aggregation for density.
    path = path or (outdir / "diagram.tenancy.mmd")
    summary = _ensure_diagram_summary(summary)
    lines = _compact_overview_lines(
        nodes=nodes,
        title="Tenancy Overview",
        top_n=TENANCY_OVERVIEW_TOP_N,
        include_workloads=False,
    )
    if _split_scope_label:
        lines.append(f"%% Split scope: {_split_scope_label}")
    if _split_reason:
        lines.append(f"%% Split rationale: {_split_reason}")
    if _split_purpose:
        lines.append(f"%% Split purpose: {_split_purpose}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path

    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}
    counters: Dict[str, int] = {}
    depth = max(1, min(depth, 3))
    requested_depth = depth if _requested_depth is None else _requested_depth
    alias_by_comp = _compartment_alias_map(nodes)

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

    lines: List[str] = [_flowchart_elk_init_line(), "flowchart LR"]
    _insert_scope_view_comments(lines, scope="tenancy", view="overview")
    lines.extend(_style_block_lines())
    if title:
        lines.append(f"%% {title}")
    if _split_scope_label:
        lines.append(f"%% Split scope: {_split_scope_label}")
    if _split_reason:
        lines.append(f"%% Split rationale: {_split_reason}")
    if _split_purpose:
        lines.append(f"%% Split purpose: {_split_purpose}")
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
        lines.append("  %% Region overlay (labels only)")
        for region in regions:
            region_label = _tenancy_safe_label("Region", region)
            region_id = _tenancy_mermaid_id("Region", region_label, counters)
            lines.append(f"  {region_id}[\"{region_label}\"]")

    comp_group_id = _tenancy_mermaid_id("Compartments", "Compartments", counters)
    lines.append(f"  subgraph {comp_group_id}[\"Compartments\"]")
    lines.append("    direction TB")

    vcn_node_ids: Dict[str, str] = {}
    comp_labels: Dict[str, str] = {
        cid: _compartment_label_by_id(cid, node_by_id=node_by_id, alias_by_id=alias_by_comp) for cid in top_level_ids
    }
    for cid in sorted(top_level_ids, key=lambda c: (comp_labels.get(c, ""), c)):
        comp_label = comp_labels.get(cid) or "Compartment: Unknown"
        comp_id = _tenancy_mermaid_id("Comp", comp_label, counters)
        lines.append(f"    subgraph {comp_id}[\"{comp_label}\"]")
        lines.append("      direction TB")

        if depth >= 2:
            comp_nodes_list = [n for n in nodes_by_root.get(cid, []) if not _is_node_type(n, "Compartment")]
            comp_vcns = [n for n in comp_nodes_list if _is_node_type(n, "Vcn") and n.get("nodeId")]
            for vcn in sorted(comp_vcns, key=lambda n: str(n.get("name") or "")):
                vcn_id = str(vcn.get("nodeId") or "")
                vcn_name = str(vcn.get("name") or "").strip()
                vcn_label = _tenancy_safe_label("VCN", vcn_name)
                vcn_group_id = _tenancy_mermaid_id("VCN", vcn_label, counters)
                lines.append(f"      subgraph {vcn_group_id}[\"{vcn_label}\"]")
                lines.append("        direction TB")
                vcn_node_id = _tenancy_mermaid_id("VCNNode", vcn_label, counters)
                lines.append(f"        {vcn_node_id}[\"{vcn_label}\"]")
                vcn_node_ids[vcn_id] = vcn_node_id

                if depth >= 3:
                    gateway_counts = gateways_by_vcn.get(vcn_id, {})
                    gateway_keys = {"InternetGateway", "ServiceGateway", "Drg"}
                    gateway_counts = {k: v for k, v in gateway_counts.items() if k in gateway_keys}
                    if gateway_counts:
                        edge_id = _tenancy_mermaid_id("Edge", f"{vcn_label}_edge", counters)
                        lines.append(f"        subgraph {edge_id}[\"Network Edge\"]")
                        lines.append("          direction TB")
                        for gw_label in sorted(gateway_counts.keys()):
                            count = gateway_counts[gw_label]
                            gw_id = _tenancy_mermaid_id("Gateway", f"{vcn_label}_{gw_label}", counters)
                            lines.append(f"          {gw_id}[\"{gw_label} (n={count})\"]")
                        lines.append("        end")

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
                    lines.append(f"        subgraph {subnet_group_id}[\"{subnet_label}\"]")
                    lines.append("          direction TB")

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
                            lines.append(f"          {agg_id}[\"{label} (n={count})\"]")

                    lines.append("        end")

                lines.append("      end")

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
                    lines.append(f"      subgraph {out_id}[\"Out-of-VCN\"]")
                    lines.append("        direction TB")
                    buckets: Dict[str, int] = {}
                    for n in out_nodes:
                        label = _tenancy_aggregate_label(n)
                        buckets[label] = buckets.get(label, 0) + 1
                    for label in sorted(buckets.keys()):
                        count = buckets[label]
                        agg_id = _tenancy_mermaid_id("Agg", f"{comp_label}_{label}", counters)
                        lines.append(f"        {agg_id}[\"{label} (n={count})\"]")
                    lines.append("      end")

            overlay_candidates = [
                n
                for n in comp_nodes_list
                if n.get("nodeId") and _lane_for_node(n) in {"iam", "security"}
            ]
            _render_overlay_summary(
                lines,
                scope_key=f"tenancy:{cid}",
                make_group_id=lambda key: _tenancy_mermaid_id("Overlay", key, counters),
                overlay_nodes=overlay_candidates,
                indent="      ",
            )

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

    size = _mermaid_text_size(lines)
    if size > MAX_MERMAID_TEXT_CHARS and _allow_split:
        split_modes = list(_split_modes) if _split_modes is not None else _split_mode_candidates(nodes, edges)
        split_mode, groups, remaining_modes = _next_split_groups(nodes, edges=edges, split_modes=split_modes)
        if split_mode and len(groups) > 1:
            part_paths: List[Path] = []
            for key, group_nodes in groups.items():
                if not group_nodes:
                    continue
                group_ids = {str(n.get("nodeId") or "") for n in group_nodes if n.get("nodeId")}
                group_edges = _filter_edges_for_nodes(edges, group_ids)
                slug = _slugify(key, max_len=32)
                part_path = outdir / f"diagram.tenancy.{split_mode}.{slug}.mmd"
                part_paths.append(
                    _write_tenancy_view(
                        outdir,
                        group_nodes,
                        group_edges,
                        depth=depth,
                        path=part_path,
                        legend_prefix=legend_prefix,
                        title=title,
                        summary=summary,
                        _requested_depth=depth,
                        _allow_split=True,
                        _split_modes=remaining_modes,
                        _split_scope_label=f"{_split_mode_label(split_mode)}={key}",
                        _split_reason=f"Split by {_split_mode_label(split_mode)} to keep tenancy view readable.",
                        _split_purpose=_split_mode_purpose(split_mode),
                    )
                )
            note = f"Tenancy diagram split by {_split_mode_label(split_mode)} due to Mermaid size limits."
            index_path = outdir / "diagram.tenancy.index.mmd"
            _write_split_index(
                index_path,
                note=note,
                part_paths=part_paths,
                title="Tenancy Split Index",
                scope="tenancy",
            )
            stub_lines: List[str] = [_flowchart_elk_init_line(), "flowchart LR"]
            _insert_scope_view_comments(stub_lines, scope="tenancy", view="overview")
            stub_lines.append(f"%% Split rationale: {note}")
            stub_lines.append(f"%% Split purpose: {_split_mode_purpose(split_mode)}")
            stub_lines.append(f"%% Split index: {index_path.name}")
            stub_lines.append("%% Overview: split group summary (top groups only).")
            stub_lines.append("subgraph tenancy_split_overview[\"Tenancy Split Overview\"]")
            stub_lines.append("  direction TB")
            group_counters: Dict[str, int] = {}
            top_groups, rest_count = _summarize_split_groups(
                groups,
                split_mode=split_mode,
                node_by_id=node_by_id,
                alias_by_comp=alias_by_comp,
                top_n=TENANCY_SPLIT_TOP_N,
            )
            for label, count in top_groups:
                node_id = _tenancy_mermaid_id("Split", label, group_counters)
                stub_lines.append(f"  {node_id}[\"{label} (n={count})\"]")
            if rest_count:
                node_id = _tenancy_mermaid_id("Split", "Other", group_counters)
                stub_lines.append(f"  {node_id}[\"Other (n={rest_count})\"]")
            stub_lines.append("end")
            stub_lines.append(f"%% See {index_path.name} for the full split list.")
            stub_path = path or (outdir / "diagram.tenancy.mmd")
            stub_path.write_text("\n".join(stub_lines).rstrip() + "\n", encoding="utf-8")
            _record_diagram_split(
                summary,
                diagram=stub_path.name,
                parts=sorted({p.name for p in part_paths}),
                size=size,
                limit=MAX_MERMAID_TEXT_CHARS,
                reason=f"split_{split_mode}",
            )
            return stub_path
    if size > MAX_MERMAID_TEXT_CHARS and depth > 1:
        LOG.warning(
            "Tenancy diagram exceeds Mermaid max text size (%s chars); reducing depth from %s to %s.",
            size,
            depth,
            depth - 1,
        )
        return _write_tenancy_view(
            outdir,
            nodes,
            edges,
            depth=depth - 1,
            path=path,
            legend_prefix=legend_prefix,
            title=title,
            summary=summary,
            _requested_depth=requested_depth,
            _allow_split=_allow_split,
            _split_modes=_split_modes,
            _split_scope_label=_split_scope_label,
            _split_reason=_split_reason,
            _split_purpose=_split_purpose,
        )
    if depth != requested_depth:
        lines.insert(
            1,
            (
                f"%% NOTE: tenancy depth reduced from {requested_depth} to {depth} "
                "to stay within Mermaid text size limits."
            ),
        )
    if size > MAX_MERMAID_TEXT_CHARS:
        LOG.warning(
            "Tenancy diagram exceeds Mermaid max text size (%s chars) at depth %s; diagram may not render.",
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

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_network_views(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    summary: Optional[DiagramSummary] = None,
) -> List[Path]:
    # Scope: VCN (full-detail). View: full-detail per VCN, split/skip on Mermaid limits.
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
    summary = _ensure_diagram_summary(summary)

    vcns_sorted = sorted(vcns, key=lambda n: str(n.get("name") or ""))

    for vcn in vcns_sorted:
        vcn_ocid = str(vcn.get("nodeId") or "")
        vcn_name = str(vcn.get("name") or "vcn").strip() or "vcn"
        fname = f"diagram.network.{_slugify(vcn_name)}.mmd"
        path = outdir / fname

        reserved_ids = {_mermaid_id(str(n.get("nodeId") or "")) for n in nodes if n.get("nodeId")}
        make_group_id = _unique_mermaid_id_factory(reserved_ids)
        rendered_node_ids: Set[str] = set()
        edge_node_id_map: Dict[str, str] = {}
        lines: List[str] = [_flowchart_elk_init_line(), "flowchart LR"]
        scope_name = _compact_scope_label(vcn_name, max_len=64)
        _insert_scope_view_comments(lines, scope=f"vcn:{scope_name}", view="full-detail")
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
        tenancy_id = make_group_id(f"tenancy:{vcn_ocid}")
        lines.append(f"subgraph {tenancy_id}[\"{tenancy_label_safe}\"]")
        lines.append("  direction TB")

        comp_id = str(vcn.get("compartmentId") or "") or "UNKNOWN"
        comp_label = (
            "Compartment: Unknown"
            if comp_id == "UNKNOWN"
            else _compartment_label(node_by_id.get(comp_id, {"name": comp_id}))
        )
        comp_label_safe = comp_label.replace('"', "'")
        comp_group_id = make_group_id(f"comp:{comp_id}:network:{vcn_ocid}")
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

        in_vcn_id = make_group_id(f"comp:{comp_id}:network:{vcn_ocid}:in_vcn")
        lines.append(f"    subgraph {in_vcn_id}[\"In-VCN\"]")
        lines.append("      direction TB")

        vcn_group_id = make_group_id(f"comp:{comp_id}:vcn:{vcn_ocid}:group")
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
            gw_id = make_group_id(f"vcn:{vcn_ocid}:gateways")
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
            vcn_level_id = make_group_id(f"vcn:{vcn_ocid}:vcn_level")
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
            sn_group_id = make_group_id(f"vcn:{vcn_ocid}:subnet:{sn_ocid}:group")
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
            unk_id = make_group_id(f"vcn:{vcn_ocid}:subnet:unknown")
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

        out_nodes: List[Node] = []
        for n in nodes:
            cid = str(n.get("compartmentId") or "")
            if cid != comp_id:
                continue
            if _is_node_type(n, "Vcn", "Subnet", *_NETWORK_GATEWAY_NODETYPES):
                continue
            ocid = str(n.get("nodeId") or "")
            if not ocid:
                continue
            att = attach_by_res.get(ocid)
            if att and (att.vcn_ocid or att.subnet_ocid):
                continue
            out_nodes.append(n)

        if out_nodes:
            out_id = make_group_id(f"comp:{comp_id}:network:{vcn_ocid}:out_vcn")
            lines.append(f"    subgraph {out_id}[\"Out-of-VCN\"]")
            lines.append("      direction TB")
            for n in sorted(out_nodes, key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or ""))):
                nid = _mermaid_id(str(n.get("nodeId") or ""))
                lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n)))
                if n.get("nodeId"):
                    raw_id = str(n.get("nodeId") or "")
                    rendered_node_ids.add(raw_id)
                    edge_node_id_map.setdefault(raw_id, nid)
            lines.append("    end")

        overlay_candidates = [
            n
            for n in nodes
            if str(n.get("compartmentId") or "") == comp_id
            and n.get("nodeId")
            and str(n.get("nodeId") or "") in rendered_node_ids
            and _lane_for_node(n) in {"iam", "security"}
        ]
        _render_overlay_lanes(
            lines,
            scope_key=f"network:{vcn_ocid}:comp:{comp_id}",
            make_group_id=make_group_id,
            overlay_nodes=overlay_candidates,
            edge_node_id_map=edge_node_id_map,
            indent="    ",
        )
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
    # Scope: workload (full-detail). View: full-detail per workload scope.
    reserved_ids = {_mermaid_id(str(n.get("nodeId") or "")) for n in nodes if n.get("nodeId")}
    make_group_id = _unique_mermaid_id_factory(reserved_ids)
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

    lines: List[str] = [_flowchart_elk_init_line(), "flowchart LR"]
    scope_name = _compact_scope_label(wl_name, max_len=64)
    _insert_scope_view_comments(lines, scope=f"workload:{scope_name}", view="full-detail")
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
    tenancy_id = make_group_id(f"tenancy:workload:{wl_name}")
    lines.append(f"subgraph {tenancy_id}[\"{tenancy_label_safe}\"]")
    lines.append("  direction TB")

    for cid in sorted(comps.keys()):
        comp_label = "Compartment: Unknown" if cid == "UNKNOWN" else _compartment_label(node_by_id.get(cid, {"name": cid}))
        comp_label_safe = comp_label.replace('"', "'")
        comp_group_id = make_group_id(f"workload:{wl_name}:comp:{cid}")
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

        in_vcn_id = make_group_id(f"workload:{wl_name}:comp:{cid}:in_vcn")
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
            vcn_group_id = make_group_id(f"workload:{wl_name}:comp:{cid}:vcn:{vcn_ocid}:group")
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
                vcn_level_id = make_group_id(f"workload:{wl_name}:comp:{cid}:vcn:{vcn_ocid}:vcn_level")
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
                sn_group_id = make_group_id(f"workload:{wl_name}:comp:{cid}:subnet:{sn_ocid}:group")
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
                unk_id = make_group_id(f"workload:{wl_name}:comp:{cid}:vcn:{vcn_ocid}:subnet:unknown")
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

        out_id = make_group_id(f"workload:{wl_name}:comp:{cid}:out_vcn")
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
            lane_id = make_group_id(f"workload:{wl_name}:comp:{cid}:lane:{lane}")
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
            overlay_id = make_group_id(f"workload:{wl_name}:comp:{cid}:overlays")
            lines.append(f"    subgraph {overlay_id}[\"Functional Overlays\"]")
            lines.append("      direction TB")
            for lane, lane_nodes in overlay_groups.items():
                lane_id = make_group_id(f"workload:{wl_name}:comp:{cid}:overlays:{lane}")
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
    # Scope: workload (full-detail). View: full-detail, split/skip on Mermaid limits.
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
            _insert_part_comment(part_lines, f"{index}/{total_parts}")
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

        note_lines = [_flowchart_elk_init_line(), "flowchart LR"]
        scope_name = _compact_scope_label(wl_name, max_len=64)
        _insert_scope_view_comments(
            note_lines,
            scope=f"workload:{scope_name}",
            view="overview",
            part="stub",
        )
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
    out.append(_write_tenancy_view(outdir, nodes, edges, depth=depth, summary=summary))
    out.extend(_write_network_views(outdir, nodes, edges, summary=summary))
    out.extend(_write_workload_views(outdir, nodes, edges, summary=summary))

    # Consolidated, end-user-friendly artifact: one Mermaid diagram that contains all the views.
    out.extend(
        _write_consolidated_flowchart(
            outdir,
            nodes,
            edges,
            depth=depth,
            summary=summary,
        )
    )
    if summary is not None:
        for path in out:
            _scan_guideline_violations(path, nodes=nodes, summary=summary)
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


def is_graphviz_available() -> bool:
    return which("dot") is not None


def _import_node_class(module_path: str, class_name: str) -> Optional[Any]:
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name, None)
    except Exception:
        return None


def _first_node_class(candidates: Sequence[Tuple[str, str]]) -> Optional[Any]:
    for module_path, class_name in candidates:
        cls = _import_node_class(module_path, class_name)
        if cls is not None:
            return cls
    return None


def _load_diagrams_classes() -> Optional[Tuple[Any, Any, Any, Dict[str, Any], Any]]:
    try:
        diagrams_mod = importlib.import_module("diagrams")
        Diagram = getattr(diagrams_mod, "Diagram")
        Cluster = getattr(diagrams_mod, "Cluster")
        Edge = getattr(diagrams_mod, "Edge")
    except Exception as exc:
        LOG.warning("Architecture diagrams skipped; diagrams library import failed: %s", exc)
        return None

    fallback = _first_node_class(
        [
            ("diagrams.generic.compute", "Rack"),
            ("diagrams.generic.compute", "Server"),
            ("diagrams.generic.storage", "Storage"),
        ]
    )
    if fallback is None:
        fallback = getattr(diagrams_mod, "Node", None)
    if fallback is None:
        LOG.warning("Architecture diagrams skipped; no usable node classes available.")
        return None

    lane_classes = {
        "network": _first_node_class(
            [
                ("diagrams.oci.network", "VirtualCloudNetwork"),
                ("diagrams.oci.network", "Subnet"),
                ("diagrams.oci.network", "RouteTable"),
                ("diagrams.oci.network", "InternetGateway"),
                ("diagrams.generic.network", "Router"),
                ("diagrams.generic.network", "Switch"),
            ]
        ),
        "security": _first_node_class(
            [
                ("diagrams.oci.security", "Firewall"),
                ("diagrams.oci.identity", "Policy"),
                ("diagrams.generic.security", "Firewall"),
            ]
        ),
        "iam": _first_node_class(
            [
                ("diagrams.oci.identity", "User"),
                ("diagrams.oci.identity", "Users"),
                ("diagrams.generic.user", "User"),
                ("diagrams.generic.user", "Users"),
            ]
        ),
        "app": _first_node_class(
            [
                ("diagrams.oci.compute", "Instance"),
                ("diagrams.oci.compute", "BareMetal"),
                ("diagrams.oci.functions", "Functions"),
                ("diagrams.generic.compute", "Rack"),
                ("diagrams.generic.compute", "Server"),
            ]
        ),
        "data": _first_node_class(
            [
                ("diagrams.oci.database", "AutonomousDatabase"),
                ("diagrams.oci.database", "Database"),
                ("diagrams.oci.storage", "ObjectStorage"),
                ("diagrams.oci.storage", "BlockStorage"),
                ("diagrams.generic.database", "SQL"),
                ("diagrams.generic.storage", "Storage"),
            ]
        ),
        "observability": _first_node_class(
            [
                ("diagrams.oci.monitoring", "Monitoring"),
                ("diagrams.oci.logging", "Logging"),
                ("diagrams.generic.monitoring", "Monitor"),
            ]
        ),
        "other": _first_node_class(
            [
                ("diagrams.generic.blank", "Blank"),
                ("diagrams.generic.storage", "Storage"),
            ]
        ),
    }
    lane_classes = {k: v for k, v in lane_classes.items() if v is not None}
    return Diagram, Cluster, Edge, lane_classes, fallback


def _arch_lane_counts(nodes: Sequence[Node]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for n in nodes:
        if _is_node_type(n, "Compartment", "Vcn", "Subnet"):
            continue
        lane = _lane_for_node(n)
        if lane in {"tenancy"}:
            continue
        counts[lane] = counts.get(lane, 0) + 1
    return counts


def _arch_safe_label(value: str, *, default: str = "Unknown") -> str:
    safe = _compact_label(value, max_len=64)
    if not safe:
        return default
    if safe.startswith("ocid1") or "ocid1" in safe:
        return "Redacted"
    return safe


def _arch_compartment_label(label: str) -> str:
    safe = _compact_label(label, max_len=64)
    if "ocid1" in safe:
        return "Compartment: Redacted"
    return safe


def _arch_count_nodes(nodes: Sequence[Node]) -> int:
    count = 0
    for n in nodes:
        if _is_node_type(n, "Compartment"):
            continue
        count += 1
    return count


def _arch_is_gateway(node: Node) -> bool:
    return str(node.get("nodeType") or "") in _NETWORK_GATEWAY_NODETYPES


def _arch_is_load_balancer(node: Node) -> bool:
    t = str(node.get("nodeType") or "")
    return "LoadBalancer" in t or t in {"Nlb", "NetworkLoadBalancer", "ApiGateway", "Gateway"}


def _arch_is_database(node: Node) -> bool:
    t = str(node.get("nodeType") or "").lower()
    return any(k in t for k in ("database", "dbsystem", "autonomous", "mysql", "postgres", "nosql"))


def _arch_workload_name_is_generic(name: str) -> bool:
    low = name.lower().strip()
    if not low:
        return True
    if low.startswith("ocid1"):
        return True
    if len(low) <= 2:
        return True
    stop = {
        "vcn",
        "subnet",
        "network",
        "gateway",
        "security",
        "policy",
        "route",
        "dhcp",
        "compartment",
        "instance",
        "volume",
        "bucket",
        "database",
        "storage",
        "object",
        "oci",
        "default",
    }
    if low in stop:
        return True
    return False


def _arch_workload_has_tags(nodes: Sequence[Node]) -> bool:
    for n in nodes:
        tags = n.get("tags") or {}
        for bucket in ("definedTags", "freeformTags"):
            items = tags.get(bucket)
            if isinstance(items, dict) and items:
                for k in items.keys():
                    key = str(k).lower()
                    if any(token in key for token in ("workload", "application", "app", "service")):
                        return True
    return False


def _workload_summary_lines(
    nodes: Sequence[Node],
    *,
    top_n: int = CONSOLIDATED_WORKLOAD_TOP_N,
    prefix: str = "%% Workloads",
) -> List[str]:
    candidates = [n for n in nodes if n.get("nodeId")]
    groups = {k: list(v) for k, v in group_workload_candidates(candidates).items()}
    filtered: Dict[str, List[Node]] = {}
    for name, items in groups.items():
        if len(items) < ARCH_MIN_WORKLOAD_NODES:
            continue
        if _arch_workload_name_is_generic(name) and not _arch_workload_has_tags(items):
            continue
        filtered[name] = items
    if not filtered:
        return [f"{prefix}: (none)"]
    ranked = sorted(filtered.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))
    top = ranked[:top_n]
    rest = ranked[top_n:]
    parts = [f"{_compact_scope_label(name)} (n={len(items)})" for name, items in top]
    if rest:
        parts.append(f"Other (n={sum(len(items) for _, items in rest)})")
    return [f"{prefix}: " + ", ".join(parts)]


def _arch_select_top_groups(
    groups: Mapping[str, Sequence[Node]],
    *,
    limit: int,
) -> Tuple[List[Tuple[str, Sequence[Node]]], List[Tuple[str, Sequence[Node]]]]:
    ranked = sorted(
        groups.items(),
        key=lambda kv: (-_arch_count_nodes(list(kv[1])), str(kv[0]).lower()),
    )
    top = ranked[:limit]
    rest = ranked[limit:]
    return top, rest


def _arch_node_for_lane(
    lane: str,
    label: str,
    *,
    lane_classes: Mapping[str, Any],
    fallback: Any,
) -> Any:
    cls = lane_classes.get(lane) or fallback
    return cls(label)


def _arch_node_label(node: Node) -> str:
    name = _compact_label(str(node.get("name") or ""), max_len=48)
    if not name:
        name = _friendly_type(str(node.get("nodeType") or "Resource"))
    if name.startswith("ocid1") or "ocid1" in name:
        name = _friendly_type(str(node.get("nodeType") or "Resource"))
    return name


def _arch_lane_summaries(nodes: Sequence[Node]) -> Dict[str, Dict[str, int]]:
    summaries: Dict[str, Dict[str, int]] = {}
    for node in nodes:
        if not node.get("nodeId"):
            continue
        if _is_node_type(node, "Compartment", "Vcn", "Subnet"):
            continue
        lane = _lane_for_node(node)
        label = _arch_node_label(node)
        if not label:
            continue
        summaries.setdefault(lane, {})
        summaries[lane][label] = summaries[lane].get(label, 0) + 1
    return summaries


def _arch_lane_top(labels: Dict[str, int], top_n: int) -> Tuple[List[Tuple[str, int]], int]:
    items = sorted(labels.items(), key=lambda item: (-item[1], item[0]))
    top = items[:top_n]
    rest = sum(count for _label, count in items[top_n:])
    return top, rest


def _arch_short_hash(values: Sequence[str]) -> str:
    digest = hashlib.sha1()
    for value in values:
        digest.update(value.encode("utf-8", errors="ignore"))
        digest.update(b"|")
    return digest.hexdigest()[:8]


def _arch_graph_attrs() -> Tuple[Dict[str, str], Dict[str, str]]:
    graph_attr = {
        "rankdir": "LR",
        "splines": "polyline",
        "concentrate": "true",
        "nodesep": "0.1",
        "ranksep": "0.15",
        "pad": "0.2",
        "ratio": "compress",
        "pack": "true",
        "packmode": "graph",
        "fontsize": "9",
    }
    node_attr = {
        "fixedsize": "true",
        "width": "1.0",
        "height": "0.5",
        "imagescale": "true",
        "labelloc": "b",
        "imagepos": "tc",
        "fontsize": "8",
        "margin": "0.03,0.02",
    }
    return graph_attr, node_attr


def _arch_invisible_chain(nodes: Sequence[Any], Edge: Any) -> None:
    if len(nodes) < 2:
        return
    for left, right in zip(nodes, nodes[1:]):
        left >> Edge(style="invis") >> right


def _split_group_display_label(
    *,
    split_mode: str,
    key: str,
    node_by_id: Mapping[str, Node],
    alias_by_comp: Mapping[str, str],
) -> str:
    label = key
    if key.startswith("ocid1") or key in node_by_id:
        label = _compartment_label_by_id(key, node_by_id=node_by_id, alias_by_id=alias_by_comp)
    label = _tenancy_safe_label(_split_mode_label(split_mode), label)
    return label


def _summarize_split_groups(
    groups: Mapping[str, Sequence[Node]],
    *,
    split_mode: str,
    node_by_id: Mapping[str, Node],
    alias_by_comp: Mapping[str, str],
    top_n: int,
) -> Tuple[List[Tuple[str, int]], int]:
    items: List[Tuple[str, int]] = []
    for key, group_nodes in groups.items():
        label = _split_group_display_label(
            split_mode=split_mode,
            key=key,
            node_by_id=node_by_id,
            alias_by_comp=alias_by_comp,
        )
        count = len([n for n in group_nodes if n.get("nodeId") and not _is_node_type(n, "Compartment")])
        items.append((label, count))
    items.sort(key=lambda item: (-item[1], item[0].lower()))
    top = items[: max(0, top_n)]
    rest = items[max(0, top_n) :]
    rest_count = sum(count for _, count in rest)
    return top, rest_count


def _write_split_index(
    path: Path,
    *,
    note: str,
    part_paths: Sequence[Path],
    title: str,
    scope: str,
) -> Path:
    lines = [_flowchart_elk_init_line(), "flowchart LR"]
    _insert_scope_view_comments(lines, scope=scope, view="overview")
    lines.append(f"%% {title}")
    lines.append(f"%% {note}")
    lines.append("%% Split outputs:")
    for part in sorted({p.name for p in part_paths}):
        lines.append(f"%% - {part}")
    notice_id = _mermaid_id(f"split:index:{path.name}")
    lines.append(f"{notice_id}[\"Split index: {len(part_paths)} diagram(s).\"]")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def _arch_inline_svg_images(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return

    def _replace(match: re.Match[str]) -> str:
        raw_path = match.group(1)
        if raw_path.startswith("data:"):
            return match.group(0)
        img_path = Path(raw_path)
        if not img_path.exists():
            return match.group(0)
        try:
            data = img_path.read_bytes()
        except Exception:
            return match.group(0)
        b64 = base64.b64encode(data).decode("ascii")
        return f'xlink:href="data:image/png;base64,{b64}"'

    updated = re.sub(r'xlink:href="([^"]+)"', _replace, text)
    if ARCH_ARCH_IMAGE_PX:
        def _resize_tag(match: re.Match[str]) -> str:
            tag = match.group(0)
            tag = re.sub(r'\swidth="\d+px"', f' width="{ARCH_ARCH_IMAGE_PX}px"', tag)
            tag = re.sub(r'\sheight="\d+px"', f' height="{ARCH_ARCH_IMAGE_PX}px"', tag)
            if 'width="' not in tag:
                tag = tag.replace("<image", f'<image width="{ARCH_ARCH_IMAGE_PX}px"', 1)
            if 'height="' not in tag:
                tag = tag.replace("<image", f'<image height="{ARCH_ARCH_IMAGE_PX}px"', 1)
            return tag

        updated = re.sub(r"<image[^>]*>", _resize_tag, updated)
    if updated != text:
        try:
            path.write_text(updated, encoding="utf-8")
        except Exception:
            return


def _chunked(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    if size <= 0:
        size = 1
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]


def _arch_add_legend(
    Cluster: Any,
    *,
    lane_classes: Mapping[str, Any],
    fallback: Any,
    title: str,
    scope: str,
    counts: Mapping[str, int],
    part_label: Optional[str] = None,
) -> None:
    with Cluster("Legend"):
        _arch_node_for_lane(
            "other",
            title,
            lane_classes=lane_classes,
            fallback=fallback,
        )
        _arch_node_for_lane(
            "other",
            f"Scope: {scope}",
            lane_classes=lane_classes,
            fallback=fallback,
        )
        if part_label:
            _arch_node_for_lane(
                "other",
                f"Part: {part_label}",
                lane_classes=lane_classes,
                fallback=fallback,
            )
        for lane in sorted(counts.keys()):
            _arch_node_for_lane(
                "other",
                f"{_lane_label(lane)}: {counts[lane]}",
                lane_classes=lane_classes,
                fallback=fallback,
            )


def _arch_split_by_lanes(
    nodes_by_id: Mapping[str, Node],
    node_ids: Sequence[str],
    *,
    max_nodes: int,
    max_lane_nodes: int,
) -> List[List[str]]:
    lane_groups: Dict[str, List[str]] = {}
    for node_id in node_ids:
        node = nodes_by_id.get(node_id)
        if not node:
            continue
        lane = _lane_for_node(node)
        lane_groups.setdefault(lane, []).append(node_id)
    parts: List[List[str]] = []
    lane_chunk = max_nodes
    if max_lane_nodes > 0:
        lane_chunk = min(max_nodes, max_lane_nodes)
    for lane in sorted(lane_groups.keys()):
        lane_ids = sorted(lane_groups[lane])
        for chunk in _chunked(lane_ids, lane_chunk):
            parts.append(list(chunk))
    return parts


def _arch_split_with_budget(
    nodes_by_id: Mapping[str, Node],
    edges: Sequence[Edge],
    node_ids: Sequence[str],
    *,
    max_nodes: int,
    max_edges: int,
    max_lane_nodes: int,
) -> List[List[str]]:
    if not node_ids:
        return []
    unique_ids = sorted(set(node_ids))
    parts: List[List[str]] = []
    chunk_size = max_nodes
    while True:
        parts = _arch_split_by_lanes(
            nodes_by_id,
            unique_ids,
            max_nodes=chunk_size,
            max_lane_nodes=max_lane_nodes,
        )
        if not parts:
            break
        oversized = False
        for part in parts:
            part_edges = _filter_edges_for_nodes(edges, set(part))
            if len(part) > max_nodes or len(part_edges) > max_edges:
                oversized = True
                break
        if not oversized or chunk_size <= 1:
            break
        chunk_size = max(1, chunk_size // 2)
    return parts


def _arch_split_vcn_parts(
    vcn_nodes: Sequence[Node],
    vcn_edges: Sequence[Edge],
    *,
    max_nodes: int,
) -> List[List[str]]:
    nodes_by_id = {str(n.get("nodeId") or ""): n for n in vcn_nodes if n.get("nodeId")}
    subnet_nodes = [n for n in vcn_nodes if _is_node_type(n, "Subnet") and n.get("nodeId")]
    subnet_ids = [str(n.get("nodeId") or "") for n in subnet_nodes]
    attachments = _derived_attachments(vcn_nodes, vcn_edges)
    attach_by_res = {a.resource_ocid: a for a in attachments}

    gateway_ids = sorted(
        str(n.get("nodeId") or "")
        for n in vcn_nodes
        if n.get("nodeId") and _arch_is_gateway(n)
    )

    groups: List[Tuple[str, List[str]]] = []
    for subnet_id in sorted(subnet_ids):
        attached = [
            str(n.get("nodeId") or "")
            for n in vcn_nodes
            if n.get("nodeId")
            and attach_by_res.get(str(n.get("nodeId") or ""))
            and attach_by_res[str(n.get("nodeId") or "")].subnet_ocid == subnet_id
            and not _is_node_type(n, "Vcn", "Subnet", "Compartment")
        ]
        group_ids = [subnet_id] + sorted({*attached})
        groups.append((f"subnet:{subnet_id}", group_ids))

    other_ids = [
        str(n.get("nodeId") or "")
        for n in vcn_nodes
        if n.get("nodeId")
        and not _is_node_type(n, "Vcn", "Subnet", "Compartment")
        and str(n.get("nodeId") or "") not in subnet_ids
        and str(n.get("nodeId") or "") not in {nid for _, ids in groups for nid in ids}
        and str(n.get("nodeId") or "") not in gateway_ids
    ]
    if other_ids:
        groups.append(("out-of-subnet", sorted(other_ids)))

    def _pack_groups() -> List[List[str]]:
        packed: List[List[str]] = []
        current: List[str] = []
        current_groups = 0
        for _label, group_ids in groups:
            base_ids = sorted(set(group_ids))
            if not base_ids:
                continue
            # If a single group is too large, split it first.
            group_parts = _arch_split_with_budget(
                nodes_by_id,
                vcn_edges,
                base_ids,
                max_nodes=max_nodes,
                max_edges=ARCH_MAX_ARCH_EDGES,
                max_lane_nodes=ARCH_MAX_ARCH_LANE_NODES,
            )
            for sub_ids in group_parts:
                if not sub_ids:
                    continue
                candidate = sorted(set(current + sub_ids))
                candidate_edges = _filter_edges_for_nodes(vcn_edges, set(candidate))
                if current and (
                    len(candidate) > max_nodes
                    or len(candidate_edges) > ARCH_MAX_ARCH_EDGES
                    or (ARCH_MAX_ARCH_GROUPS_PER_PART and current_groups >= ARCH_MAX_ARCH_GROUPS_PER_PART)
                ):
                    packed.append(current)
                    current = []
                    current_groups = 0
                current = sorted(set(current + sub_ids))
                current_groups += 1
        if current:
            packed.append(current)
        return packed

    parts = _pack_groups()
    if gateway_ids:
        parts = [sorted(set(part + gateway_ids)) for part in parts]

    if not parts:
        all_ids = sorted(nodes_by_id.keys())
        if len(all_ids) <= max_nodes:
            parts = [all_ids]
        else:
            parts = _arch_split_with_budget(
                nodes_by_id,
                vcn_edges,
                all_ids,
                max_nodes=max_nodes,
                max_edges=ARCH_MAX_ARCH_EDGES,
                max_lane_nodes=ARCH_MAX_ARCH_LANE_NODES,
            )
    return parts


def _render_architecture_tenancy(
    Diagram: Any,
    Cluster: Any,
    Edge: Any,
    lane_classes: Mapping[str, Any],
    fallback: Any,
    *,
    outdir: Path,
    nodes: Sequence[Node],
) -> Optional[Path]:
    tenancy_label = _tenancy_label(nodes)
    comp_items = _top_compartment_counts(nodes)
    top_compartments, rest_compartments = _overview_top_counts(comp_items, ARCH_TENANCY_TOP_N)
    vcn_items = _top_vcn_counts(nodes)
    top_vcns, rest_vcns = _overview_top_counts(vcn_items, ARCH_TENANCY_TOP_N)
    lane_summaries = _arch_lane_summaries(nodes)

    arch_dir = outdir / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    path = arch_dir / "diagram.arch.tenancy.svg"
    filename = str(path.with_suffix(""))
    graph_attr, node_attr = _arch_graph_attrs()
    with Diagram(
        f"{tenancy_label} Architecture (Overview)",
        filename=filename,
        outformat="svg",
        show=False,
        graph_attr=graph_attr,
        node_attr=node_attr,
    ):
        _arch_add_legend(
            Cluster,
            lane_classes=lane_classes,
            fallback=fallback,
            title="Tenancy Architecture (Overview)",
            scope="tenancy",
            counts=_arch_lane_counts(nodes),
        )
        with Cluster(f"Tenancy: {tenancy_label}"):
            zone_anchors: List[Any] = []
            with Cluster("Top Compartments"):
                row_nodes: List[Any] = []
                for label, count in top_compartments:
                    row_nodes.append(
                        _arch_node_for_lane(
                            "other",
                            f"{label} (n={count})",
                            lane_classes=lane_classes,
                            fallback=fallback,
                        )
                    )
                if rest_compartments:
                    row_nodes.append(
                        _arch_node_for_lane(
                            "other",
                            f"Other Compartments (n={rest_compartments})",
                            lane_classes=lane_classes,
                            fallback=fallback,
                        )
                    )
                if row_nodes:
                    zone_anchors.append(row_nodes[0])
                    _arch_invisible_chain(row_nodes, Edge)

            with Cluster("Top VCNs"):
                row_nodes = []
                for label, count in top_vcns:
                    row_nodes.append(
                        _arch_node_for_lane(
                            "network",
                            f"{label} (n={count})",
                            lane_classes=lane_classes,
                            fallback=fallback,
                        )
                    )
                if rest_vcns:
                    row_nodes.append(
                        _arch_node_for_lane(
                            "network",
                            f"Other VCNs (n={rest_vcns})",
                            lane_classes=lane_classes,
                            fallback=fallback,
                        )
                    )
                if row_nodes:
                    zone_anchors.append(row_nodes[0])
                    _arch_invisible_chain(row_nodes, Edge)

            with Cluster("Service Lanes"):
                lane_anchors: List[Any] = []
                for lane in _LANE_ORDER:
                    labels = lane_summaries.get(lane)
                    if not labels:
                        continue
                    top_labels, rest = _arch_lane_top(labels, ARCH_LANE_TOP_N)
                    with Cluster(_lane_label(lane), graph_attr={"rank": "same"}):
                        lane_nodes: List[Any] = []
                        for label, count in top_labels:
                            lane_nodes.append(
                                _arch_node_for_lane(
                                    lane,
                                    f"{label} (n={count})",
                                    lane_classes=lane_classes,
                                    fallback=fallback,
                                )
                            )
                        if rest:
                            lane_nodes.append(
                                _arch_node_for_lane(
                                    lane,
                                    f"Other (n={rest})",
                                    lane_classes=lane_classes,
                                    fallback=fallback,
                                )
                            )
                        if lane_nodes:
                            lane_anchors.append(lane_nodes[0])
                            _arch_invisible_chain(lane_nodes, Edge)
                if lane_anchors:
                    zone_anchors.append(lane_anchors[0])
                    _arch_invisible_chain(lane_anchors, Edge)

            _arch_invisible_chain(zone_anchors, Edge)
    return path


def _render_architecture_vcn(
    Diagram: Any,
    Cluster: Any,
    Edge: Any,
    lane_classes: Mapping[str, Any],
    fallback: Any,
    *,
    outdir: Path,
    vcn_name: str,
    vcn_nodes: Sequence[Node],
    vcn_edges: Sequence[Edge],
    vcn_suffix: str,
    part_idx: Optional[int] = None,
    part_total: Optional[int] = None,
) -> Optional[Path]:
    if not vcn_nodes:
        return None
    vcn_label = _compact_label(vcn_name, max_len=64) or "VCN"
    arch_dir = outdir / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    suffix = f".{vcn_suffix}" if vcn_suffix else ""
    path = arch_dir / f"diagram.arch.vcn.{_slugify(vcn_label)}{suffix}.svg"
    filename = str(path.with_suffix(""))
    graph_attr, node_attr = _arch_graph_attrs()
    title = f"VCN Architecture: {vcn_label} (Curated)"
    with Diagram(
        title,
        filename=filename,
        outformat="svg",
        show=False,
        graph_attr=graph_attr,
        node_attr=node_attr,
    ):
        _arch_add_legend(
            Cluster,
            lane_classes=lane_classes,
            fallback=fallback,
            title="VCN Architecture (Curated Overview)",
            scope=f"vcn:{vcn_label}",
            counts=_arch_lane_counts(vcn_nodes),
        )
        with Cluster(f"VCN Scope: {vcn_label}"):
            zone_anchors: List[Any] = []
            with Cluster("Network Components"):
                row_nodes: List[Any] = []
                subnets = [n for n in vcn_nodes if _is_node_type(n, "Subnet")]
                gateways = [n for n in vcn_nodes if _arch_is_gateway(n)]
                if subnets:
                    row_nodes.append(
                        _arch_node_for_lane(
                            "network",
                            f"Subnets (n={len(subnets)})",
                            lane_classes=lane_classes,
                            fallback=fallback,
                        )
                    )
                if gateways:
                    row_nodes.append(
                        _arch_node_for_lane(
                            "network",
                            f"Gateways (n={len(gateways)})",
                            lane_classes=lane_classes,
                            fallback=fallback,
                        )
                    )
                if row_nodes:
                    zone_anchors.append(row_nodes[0])
                    _arch_invisible_chain(row_nodes, Edge)

            with Cluster("Service Lanes"):
                lane_summaries = _arch_lane_summaries(vcn_nodes)
                lane_anchors: List[Any] = []
                for lane in _LANE_ORDER:
                    labels = lane_summaries.get(lane)
                    if not labels:
                        continue
                    top_labels, rest = _arch_lane_top(labels, ARCH_LANE_TOP_N)
                    with Cluster(_lane_label(lane), graph_attr={"rank": "same"}):
                        lane_nodes: List[Any] = []
                        for label, count in top_labels:
                            lane_nodes.append(
                                _arch_node_for_lane(
                                    lane,
                                    f"{label} (n={count})",
                                    lane_classes=lane_classes,
                                    fallback=fallback,
                                )
                            )
                        if rest:
                            lane_nodes.append(
                                _arch_node_for_lane(
                                    lane,
                                    f"Other (n={rest})",
                                    lane_classes=lane_classes,
                                    fallback=fallback,
                                )
                            )
                        if lane_nodes:
                            lane_anchors.append(lane_nodes[0])
                            _arch_invisible_chain(lane_nodes, Edge)
                if lane_anchors:
                    zone_anchors.append(lane_anchors[0])
                    _arch_invisible_chain(lane_anchors, Edge)

            _arch_invisible_chain(zone_anchors, Edge)
    return path


def _render_architecture_workload(
    Diagram: Any,
    Cluster: Any,
    Edge: Any,
    lane_classes: Mapping[str, Any],
    fallback: Any,
    *,
    outdir: Path,
    workload: str,
    workload_nodes: Sequence[Node],
    workload_edges: Sequence[Edge],
    workload_suffix: str,
    part_idx: Optional[int] = None,
    part_total: Optional[int] = None,
) -> Optional[Path]:
    if not workload_nodes:
        return None
    wl_label = _arch_safe_label(_compact_label(workload, max_len=64), default="Workload")
    arch_dir = outdir / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    suffix = f".{workload_suffix}" if workload_suffix else ""
    path = arch_dir / f"diagram.arch.workload.{_slugify(wl_label)}{suffix}.svg"
    filename = str(path.with_suffix(""))
    graph_attr, node_attr = _arch_graph_attrs()
    title = f"Workload Architecture: {wl_label} (Curated)"
    with Diagram(
        title,
        filename=filename,
        outformat="svg",
        show=False,
        graph_attr=graph_attr,
        node_attr=node_attr,
    ):
        _arch_add_legend(
            Cluster,
            lane_classes=lane_classes,
            fallback=fallback,
            title="Workload Architecture (Curated Overview)",
            scope=f"workload:{wl_label}",
            counts=_arch_lane_counts(workload_nodes),
        )
        with Cluster(f"Workload Scope: {wl_label}"):
            zone_anchors: List[Any] = []
            with Cluster("Service Lanes"):
                lane_summaries = _arch_lane_summaries(workload_nodes)
                lane_anchors: List[Any] = []
                for lane in _LANE_ORDER:
                    labels = lane_summaries.get(lane)
                    if not labels:
                        continue
                    top_labels, rest = _arch_lane_top(labels, ARCH_LANE_TOP_N)
                    with Cluster(_lane_label(lane), graph_attr={"rank": "same"}):
                        lane_nodes: List[Any] = []
                        for label, count in top_labels:
                            lane_nodes.append(
                                _arch_node_for_lane(
                                    lane,
                                    f"{label} (n={count})",
                                    lane_classes=lane_classes,
                                    fallback=fallback,
                                )
                            )
                        if rest:
                            lane_nodes.append(
                                _arch_node_for_lane(
                                    lane,
                                    f"Other (n={rest})",
                                    lane_classes=lane_classes,
                                    fallback=fallback,
                                )
                            )
                        if lane_nodes:
                            lane_anchors.append(lane_nodes[0])
                            _arch_invisible_chain(lane_nodes, Edge)
                if lane_anchors:
                    zone_anchors.append(lane_anchors[0])
                    _arch_invisible_chain(lane_anchors, Edge)
            _arch_invisible_chain(zone_anchors, Edge)
    return path


def _render_architecture_vcn_overview(
    Diagram: Any,
    Cluster: Any,
    Edge: Any,
    lane_classes: Mapping[str, Any],
    fallback: Any,
    *,
    outdir: Path,
    vcn_name: str,
    vcn_nodes: Sequence[Node],
    vcn_edges: Sequence[Edge],
    vcn_suffix: str,
    part_count: int,
) -> Optional[Path]:
    if not vcn_nodes:
        return None
    vcn_label = _compact_label(vcn_name, max_len=64) or "VCN"
    arch_dir = outdir / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    path = arch_dir / f"diagram.arch.vcn.{_slugify(vcn_label)}.{vcn_suffix}.overview.svg"
    filename = str(path.with_suffix(""))
    graph_attr, node_attr = _arch_graph_attrs()
    title = f"VCN Architecture: {vcn_label} (Overview)"
    with Diagram(
        title,
        filename=filename,
        outformat="svg",
        show=False,
        graph_attr=graph_attr,
        node_attr=node_attr,
    ):
        _arch_add_legend(
            Cluster,
            lane_classes=lane_classes,
            fallback=fallback,
            title="VCN Architecture (Overview)",
            scope=f"vcn:{vcn_label}",
            counts=_arch_lane_counts(vcn_nodes),
            part_label=f"parts={part_count}",
        )
        with Cluster(f"VCN: {vcn_label} (Overview)"):
            row_nodes: List[Any] = []
            subnets = sorted(
                (n for n in vcn_nodes if _is_node_type(n, "Subnet")),
                key=lambda n: str(n.get("name") or n.get("nodeId") or ""),
            )
            if len(subnets) > ARCH_MAX_ARCH_OVERVIEW_SUBNETS:
                shown_subnets = subnets[:ARCH_MAX_ARCH_OVERVIEW_SUBNETS]
                remainder = len(subnets) - len(shown_subnets)
            else:
                shown_subnets = subnets
                remainder = 0
            attachments = _derived_attachments(vcn_nodes, vcn_edges)
            attach_by_res = {a.resource_ocid: a for a in attachments}
            for sn in shown_subnets:
                sn_id = str(sn.get("nodeId") or "")
                sn_label = _subnet_label_compact(sn)
                attached = [
                    n
                    for n in vcn_nodes
                    if n.get("nodeId")
                    and attach_by_res.get(str(n.get("nodeId") or ""))
                    and attach_by_res[str(n.get("nodeId") or "")].subnet_ocid == sn_id
                    and not _is_node_type(n, "Vcn", "Subnet", "Compartment")
                ]
                label = f"{sn_label} (n={len(attached)})"
                row_nodes.append(
                    _arch_node_for_lane(
                        "network",
                        label,
                        lane_classes=lane_classes,
                        fallback=fallback,
                    )
                )
            if remainder:
                row_nodes.append(
                    _arch_node_for_lane(
                        "network",
                        f"Other Subnets (n={remainder})",
                        lane_classes=lane_classes,
                        fallback=fallback,
                    )
                )
            gateways = [n for n in vcn_nodes if _arch_is_gateway(n)]
            if gateways:
                row_nodes.append(
                    _arch_node_for_lane(
                        "network",
                        f"Gateways (n={len(gateways)})",
                        lane_classes=lane_classes,
                        fallback=fallback,
                    )
                )
            other_nodes = [
                n
                for n in vcn_nodes
                if n.get("nodeId")
                and not _is_node_type(n, "Vcn", "Subnet", "Compartment")
                and str(n.get("nodeId") or "") not in {str(sn.get("nodeId") or "") for sn in subnets}
            ]
            if other_nodes:
                row_nodes.append(
                    _arch_node_for_lane(
                        "other",
                        f"Out-of-Subnet (n={len(other_nodes)})",
                        lane_classes=lane_classes,
                        fallback=fallback,
                    )
                )
            row_nodes.append(
                _arch_node_for_lane(
                    "other",
                    f"Parts: {part_count}",
                    lane_classes=lane_classes,
                    fallback=fallback,
                )
            )
            _arch_invisible_chain(row_nodes, Edge)
    return path


def _render_architecture_workload_overview(
    Diagram: Any,
    Cluster: Any,
    Edge: Any,
    lane_classes: Mapping[str, Any],
    fallback: Any,
    *,
    outdir: Path,
    workload: str,
    workload_nodes: Sequence[Node],
    workload_suffix: str,
    part_count: int,
) -> Optional[Path]:
    if not workload_nodes:
        return None
    wl_label = _arch_safe_label(_compact_label(workload, max_len=64), default="Workload")
    arch_dir = outdir / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    path = arch_dir / f"diagram.arch.workload.{_slugify(wl_label)}.{workload_suffix}.overview.svg"
    filename = str(path.with_suffix(""))
    graph_attr, node_attr = _arch_graph_attrs()
    title = f"Workload Architecture: {wl_label} (Overview)"
    with Diagram(
        title,
        filename=filename,
        outformat="svg",
        show=False,
        graph_attr=graph_attr,
        node_attr=node_attr,
    ):
        _arch_add_legend(
            Cluster,
            lane_classes=lane_classes,
            fallback=fallback,
            title="Workload Architecture (Overview)",
            scope=f"workload:{wl_label}",
            counts=_arch_lane_counts(workload_nodes),
            part_label=f"parts={part_count}",
        )
        with Cluster(f"Workload: {wl_label} (Overview)"):
            counts = _arch_lane_counts(workload_nodes)
            row_nodes: List[Any] = []
            for lane in sorted(counts.keys()):
                label = f"{_lane_label(lane)} (n={counts[lane]})"
                row_nodes.append(
                    _arch_node_for_lane(
                        lane,
                        label,
                        lane_classes=lane_classes,
                        fallback=fallback,
                    )
                )
            row_nodes.append(
                _arch_node_for_lane(
                    "other",
                    f"Parts: {part_count}",
                    lane_classes=lane_classes,
                    fallback=fallback,
                )
            )
            _arch_invisible_chain(row_nodes, Edge)
    return path

def write_architecture_diagrams(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    summary: Optional[DiagramSummary] = None,
) -> List[Path]:
    if not is_graphviz_available():
        LOG.warning("Architecture diagrams skipped; Graphviz 'dot' not found on PATH.")
        return []

    loaded = _load_diagrams_classes()
    if loaded is None:
        return []
    Diagram, Cluster, Edge, lane_classes, fallback = loaded

    filtered_nodes = [n for n in nodes if str(n.get("nodeType") or "") not in _ARCH_FILTER_NODETYPES]
    filtered_edges = _filter_edges_for_nodes(
        edges,
        {str(n.get("nodeId") or "") for n in filtered_nodes if n.get("nodeId")},
    )

    out_paths: List[Path] = []
    summary = _ensure_diagram_summary(summary)
    tenancy_path = _render_architecture_tenancy(
        Diagram,
        Cluster,
        Edge,
        lane_classes,
        fallback,
        outdir=outdir,
        nodes=filtered_nodes,
    )
    if tenancy_path is not None:
        _arch_inline_svg_images(tenancy_path)
        out_paths.append(tenancy_path)

    vcn_groups = _group_nodes_by_vcn(filtered_nodes, filtered_edges)
    top_vcns, other_vcns = _arch_select_top_groups(vcn_groups, limit=ARCH_MAX_VCNS)
    if other_vcns:
        LOG.info(
            "Architecture diagrams capped VCN views at %s (skipped %s).",
            ARCH_MAX_VCNS,
            len(other_vcns),
        )
        _record_diagram_skip(
            summary,
            diagram="architecture.vcn",
            kind="vcn",
            size=len(other_vcns),
            limit=ARCH_MAX_VCNS,
            reason="limit",
        )
    for vcn_id, group_nodes in top_vcns:
        vcn_name = ""
        for n in group_nodes:
            if _is_node_type(n, "Vcn"):
                vcn_name = str(n.get("name") or "")
                break
        if not vcn_name:
            vcn_name = "VCN"
        node_ids = [str(n.get("nodeId") or "") for n in group_nodes if n.get("nodeId")]
        node_ids = [nid for nid in node_ids if nid]
        vcn_suffix = _arch_short_hash([vcn_id] if vcn_id else sorted(node_ids))
        vcn_edges = _filter_edges_for_nodes(filtered_edges, set(node_ids))
        try:
            path = _render_architecture_vcn(
                Diagram,
                Cluster,
                Edge,
                lane_classes,
                fallback,
                outdir=outdir,
                vcn_name=vcn_name,
                vcn_nodes=group_nodes,
                vcn_edges=vcn_edges,
                vcn_suffix=vcn_suffix,
            )
        except Exception as exc:
            LOG.warning(
                "Architecture VCN diagram failed for %s: %s",
                vcn_name,
                exc,
            )
            continue
        if path is not None:
            _arch_inline_svg_images(path)
            out_paths.append(path)

    workload_candidates = [n for n in filtered_nodes if n.get("nodeId")]
    wl_groups = {k: list(v) for k, v in group_workload_candidates(workload_candidates).items()}
    filtered_wl: Dict[str, List[Node]] = {}
    for wl_name, wl_nodes in wl_groups.items():
        if len(wl_nodes) < ARCH_MIN_WORKLOAD_NODES:
            continue
        if _arch_workload_name_is_generic(wl_name) and not _arch_workload_has_tags(wl_nodes):
            continue
        filtered_wl[wl_name] = wl_nodes
    workload_ranked: List[Tuple[str, List[Node], int]] = []
    for wl_name, wl_nodes in filtered_wl.items():
        node_ids = {str(n.get("nodeId") or "") for n in wl_nodes if n.get("nodeId")}
        wl_edges = _filter_edges_for_nodes(filtered_edges, node_ids)
        workload_ranked.append((wl_name, wl_nodes, len(wl_edges)))
    workload_ranked.sort(
        key=lambda item: (-item[2], -_arch_count_nodes(item[1]), str(item[0]).lower())
    )
    top_wl = [(name, nodes) for name, nodes, _cnt in workload_ranked[:ARCH_MAX_WORKLOADS]]
    other_wl = [(name, nodes) for name, nodes, _cnt in workload_ranked[ARCH_MAX_WORKLOADS:]]
    if other_wl:
        LOG.info(
            "Architecture diagrams capped workload views at %s (skipped %s).",
            ARCH_MAX_WORKLOADS,
            len(other_wl),
        )
        _record_diagram_skip(
            summary,
            diagram="architecture.workload",
            kind="workload",
            size=len(other_wl),
            limit=ARCH_MAX_WORKLOADS,
            reason="limit",
        )
    for wl_name, wl_nodes in top_wl:
        node_ids = [str(n.get("nodeId") or "") for n in wl_nodes if n.get("nodeId")]
        node_ids = [nid for nid in node_ids if nid]
        workload_suffix = _arch_short_hash([wl_name] + sorted(node_ids))
        workload_edges = _filter_edges_for_nodes(filtered_edges, set(node_ids))
        try:
            path = _render_architecture_workload(
                Diagram,
                Cluster,
                Edge,
                lane_classes,
                fallback,
                outdir=outdir,
                workload=wl_name,
                workload_nodes=wl_nodes,
                workload_edges=workload_edges,
                workload_suffix=workload_suffix,
            )
        except Exception as exc:
            LOG.warning(
                "Architecture workload diagram failed for %s: %s",
                wl_name,
                exc,
            )
            continue
        if path is not None:
            _arch_inline_svg_images(path)
            out_paths.append(path)
    return out_paths


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

    cache_dir = outdir / ".mmdc_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = outdir / ".mmdc_cache.json"

    def _load_cache() -> Dict[str, Any]:
        if not cache_path.exists():
            return {"version": 1, "files": {}}
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {"version": 1, "files": {}}
        if not isinstance(data, dict):
            return {"version": 1, "files": {}}
        files = data.get("files")
        if not isinstance(files, dict):
            data["files"] = {}
        data.setdefault("version", 1)
        return data

    def _cache_key(path: Path) -> str:
        try:
            return str(path.relative_to(outdir))
        except Exception:
            return path.name

    cache = _load_cache()
    cache_files: Dict[str, Any] = cache.get("files", {})

    def _sha1(path: Path) -> str:
        digest = hashlib.sha1()
        digest.update(path.read_bytes())
        return digest.hexdigest()

    def _should_validate(path: Path, digest: str) -> bool:
        key = _cache_key(path)
        cached = cache_files.get(key) or {}
        out_svg = cache_dir / f"{path.stem}.svg"
        if not out_svg.exists():
            return True
        return cached.get("sha1") != digest

    def _run_validation(path: Path) -> Tuple[Path, str, str, Optional[str]]:
        digest = _sha1(path)
        if not _should_validate(path, digest):
            return path, _cache_key(path), digest, None
        out_svg = cache_dir / f"{path.stem}.svg"
        backoffs = (0.5, 1.0, 2.0)
        attempts = 1 + len(backoffs)
        for idx in range(attempts):
            proc = subprocess.run(
                [mmdc, "-i", str(path), "-o", str(out_svg)],
                text=True,
                capture_output=True,
            )
            if proc.returncode == 0:
                return path, _cache_key(path), digest, None
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            detail = stderr or stdout or f"mmdc exited with code {proc.returncode}"
            retryable = any(
                token in detail.lower()
                for token in ("protocol error", "connection closed", "target closed", "page has been closed")
            )
            if retryable and idx < len(backoffs):
                LOG.warning(
                    "Mermaid validation retry %s/%s for %s due to transient mmdc error.",
                    idx + 1,
                    attempts - 1,
                    path.name,
                )
                time.sleep(backoffs[idx])
                continue
            return path, _cache_key(path), digest, detail
        return path, _cache_key(path), digest, None

    max_workers = min(8, os.cpu_count() or 4)
    errors: List[Tuple[str, str]] = []
    results: List[Tuple[Path, str, str]] = []
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_run_validation, p): p for p in paths}
        for fut in as_completed(futures):
            path, key, digest, err = fut.result()
            if err:
                errors.append((path.name, err))
            else:
                results.append((path, key, digest))

    if errors:
        errors.sort(key=lambda item: item[0])
        name, detail = errors[0]
        raise ExportError(f"Mermaid validation failed for {name}: {detail}")

    for _path, key, digest in results:
        cache_files[key] = {"sha1": digest}
    cache["files"] = cache_files
    cache_path.write_text(json.dumps(cache, sort_keys=True, indent=2), encoding="utf-8")

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


def _collect_compartment_ids_for_nodes(nodes: Sequence[Node], parents: Mapping[str, str]) -> Set[str]:
    comp_ids: Set[str] = set()
    for n in nodes:
        cid = str(n.get("compartmentId") or "")
        if not cid and _is_node_type(n, "Compartment"):
            cid = str(n.get("nodeId") or "")
        if not cid:
            continue
        current = cid
        seen: Set[str] = set()
        while current and current not in seen:
            comp_ids.add(current)
            seen.add(current)
            current = parents.get(current, "")
    return comp_ids


def _attach_compartment_nodes(
    groups: Dict[str, List[Node]],
    *,
    nodes: Sequence[Node],
    parents: Mapping[str, str],
) -> Dict[str, List[Node]]:
    comp_nodes = {str(n.get("nodeId") or ""): n for n in nodes if _is_node_type(n, "Compartment") and n.get("nodeId")}
    out: Dict[str, List[Node]] = {}
    for key in sorted(groups.keys()):
        group_nodes = list(groups[key])
        comp_ids = _collect_compartment_ids_for_nodes(group_nodes, parents)
        existing = {str(n.get("nodeId") or "") for n in group_nodes if n.get("nodeId")}
        for cid in sorted(comp_ids):
            comp_node = comp_nodes.get(cid)
            if not comp_node:
                continue
            node_id = str(comp_node.get("nodeId") or "")
            if node_id and node_id not in existing:
                group_nodes.append(comp_node)
                existing.add(node_id)
        out[key] = group_nodes
    return out


def _group_nodes_by_region(nodes: Sequence[Node]) -> Dict[str, List[Node]]:
    parents = _compartment_parent_map(nodes)
    regions = sorted({str(n.get("region") or "") for n in nodes if n.get("region")})
    groups: Dict[str, List[Node]] = {r: [] for r in regions}
    groups.setdefault("Global", [])
    for n in nodes:
        region = str(n.get("region") or "")
        if region in groups:
            groups[region].append(n)
        else:
            groups["Global"].append(n)
    return _attach_compartment_nodes(groups, nodes=nodes, parents=parents)


def _level1_compartment_id(ocid: str, parents: Mapping[str, str]) -> str:
    if not ocid:
        return "UNKNOWN"
    current = ocid
    seen: Set[str] = set()
    chain: List[str] = []
    while current in parents and current not in seen:
        seen.add(current)
        chain.append(current)
        current = parents[current]
    if not chain:
        return ocid
    return chain[-1]


def _group_nodes_by_level1_compartment(nodes: Sequence[Node]) -> Dict[str, List[Node]]:
    parents = _compartment_parent_map(nodes)
    grouped: Dict[str, List[Node]] = {}
    for n in nodes:
        cid = str(n.get("compartmentId") or "")
        if not cid and _is_node_type(n, "Compartment"):
            cid = str(n.get("nodeId") or "")
        level1 = _level1_compartment_id(cid, parents) if cid else "UNKNOWN"
        grouped.setdefault(level1, []).append(n)
    return _attach_compartment_nodes(grouped, nodes=nodes, parents=parents)


def _group_nodes_by_vcn(nodes: Sequence[Node], edges: Optional[Sequence[Edge]] = None) -> Dict[str, List[Node]]:
    parents = _compartment_parent_map(nodes)
    edge_vcn_by_src: Dict[str, str] = {}
    attach_by_res: Dict[str, _DerivedAttachment] = {}
    if edges is not None:
        edge_vcn_by_src = _edge_single_target_map(edges, "IN_VCN")
        attachments = _derived_attachments(nodes, edges)
        attach_by_res = {a.resource_ocid: a for a in attachments}
    groups: Dict[str, List[Node]] = {}
    for n in nodes:
        ocid = str(n.get("nodeId") or "")
        if _is_node_type(n, "Vcn") and ocid:
            groups.setdefault(ocid, []).append(n)
            continue
        vcn_id = ""
        if ocid:
            att = attach_by_res.get(ocid)
            if att and att.vcn_ocid:
                vcn_id = att.vcn_ocid
            if not vcn_id:
                vcn_id = edge_vcn_by_src.get(ocid, "")
        if not vcn_id:
            meta = _node_metadata(n)
            vcn_id = str(_get_meta(meta, "vcn_id") or "")
        if vcn_id:
            groups.setdefault(vcn_id, []).append(n)
        else:
            groups.setdefault("NO_VCN", []).append(n)
    return _attach_compartment_nodes(groups, nodes=nodes, parents=parents)


def _consolidated_split_groups(
    nodes: Sequence[Node],
    *,
    edges: Optional[Sequence[Edge]] = None,
    mode: str,
) -> Dict[str, List[Node]]:
    if mode == "region":
        return _group_nodes_by_region(nodes)
    if mode == "root_compartment":
        parents = _compartment_parent_map(nodes)
        groups = _group_nodes_by_root_compartment(nodes)
        return _attach_compartment_nodes(groups, nodes=nodes, parents=parents)
    if mode == "level1_compartment":
        return _group_nodes_by_level1_compartment(nodes)
    if mode == "vcn":
        return _group_nodes_by_vcn(nodes, edges)
    return _group_nodes_by_root_compartment(nodes)


def _split_mode_candidates(nodes: Sequence[Node], edges: Optional[Sequence[Edge]] = None) -> List[str]:
    modes: List[str] = []
    regions = {str(n.get("region") or "") for n in nodes if n.get("region")}
    if len(regions) > 1:
        modes.append("region")
    modes.append("root_compartment")
    modes.append("level1_compartment")
    vcn_count = len([n for n in nodes if _is_node_type(n, "Vcn") and n.get("nodeId")])
    if vcn_count > 1 or edges:
        modes.append("vcn")
    return modes


def _split_mode_label(mode: str) -> str:
    labels = {
        "region": "region",
        "root_compartment": "root compartment",
        "level1_compartment": "level-1 compartment",
        "vcn": "VCN",
    }
    return labels.get(mode, mode)


def _split_mode_purpose(mode: str) -> str:
    return {
        "region": "Show regional footprint and high-level topology for a single region.",
        "root_compartment": "Show ownership boundaries and network layout per top-level compartment.",
        "level1_compartment": "Show functional compartment slices with consistent topology and counts.",
        "vcn": "Show network layout within a single VCN (subnets, gateways, and counts).",
    }.get(mode, "Provide a smaller, readable slice of the full diagram.")


def _next_split_groups(
    nodes: Sequence[Node],
    *,
    edges: Optional[Sequence[Edge]],
    split_modes: Sequence[str],
) -> Tuple[Optional[str], Dict[str, List[Node]], List[str]]:
    for idx, mode in enumerate(split_modes):
        groups = _consolidated_split_groups(nodes, edges=edges, mode=mode)
        groups = {k: groups[k] for k in sorted(groups.keys()) if groups[k]}
        if len(groups) > 1:
            return mode, groups, list(split_modes[idx + 1 :])
    return None, {}, []


def _write_consolidated_stub(
    path: Path,
    *,
    note: str,
    part_paths: Sequence[Path],
    tenancy_label: str,
    nodes: Sequence[Node],
    purpose: Optional[str] = None,
    groups: Optional[Mapping[str, Sequence[Node]]] = None,
    split_mode: Optional[str] = None,
) -> Path:
    lines = _compact_overview_lines(
        nodes=nodes,
        title="Consolidated Overview",
        top_n=CONSOLIDATED_OVERVIEW_TOP_N,
        include_workloads=True,
    )
    if purpose:
        lines.append(f"%% Split purpose: {purpose}")
    index_path = path.with_name("diagram.consolidated.flowchart.index.mmd")
    _write_split_index(
        index_path,
        note=note,
        part_paths=part_paths,
        title="Consolidated Split Index",
        scope="tenancy",
    )
    lines.append(f"%% Split index: {index_path.name}")
    lines.append(f"%% {note}")
    notice_id = _mermaid_id("consolidated:stub:notice")
    label = _sanitize_edge_label("Consolidated diagram split; see split outputs.")
    lines.append(f"{notice_id}[\"{label}\"]")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


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
    _split_modes: Optional[Sequence[str]] = None,
    _split_scope_label: Optional[str] = None,
    _split_reason: Optional[str] = None,
    _split_purpose: Optional[str] = None,
) -> List[Path]:
    # Scope: tenancy (overview). View: overview with global map (depth 1) or summary hierarchy (depth >1).
    path = path or (outdir / "diagram.consolidated.flowchart.mmd")
    requested_depth = depth if _requested_depth is None else _requested_depth
    if depth > 1:
        lines = _consolidated_flowchart_summary_lines(nodes, edges, depth=depth)
    else:
        lines = _global_flowchart_lines(nodes)
    lines.extend(_workload_summary_lines(nodes, prefix="%% Workloads (top)"))
    
    size = _mermaid_text_size(lines)
    if size > MAX_MERMAID_TEXT_CHARS and _allow_split:
        split_modes = list(_split_modes) if _split_modes is not None else _split_mode_candidates(nodes, edges)
        split_mode, groups, remaining_modes = _next_split_groups(nodes, edges=edges, split_modes=split_modes)
        if split_mode and len(groups) > 1:
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
                        _allow_split=True,
                        _split_modes=remaining_modes,
                        _split_scope_label=f"{_split_mode_label(split_mode)}={key}",
                        _split_reason=f"Split by {_split_mode_label(split_mode)} to keep consolidated view readable.",
                        _split_purpose=_split_mode_purpose(split_mode),
                    )
                )
            note = f"Consolidated diagram split by {_split_mode_label(split_mode)} due to Mermaid size limits."
            stub_path = _write_consolidated_stub(
                path,
                note=note,
                part_paths=part_paths,
                tenancy_label=_tenancy_label(nodes),
                nodes=nodes,
                purpose=_split_mode_purpose(split_mode),
                groups=groups,
                split_mode=split_mode,
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
            _split_scope_label=_split_scope_label,
            _split_reason=_split_reason,
            _split_purpose=_split_purpose,
        )
    insert_at = 1 if lines else 0
    if requested_depth > 1:
        lines.insert(insert_at, "%% NOTE: global map renders at depth 1 (tenancy + regions).")
        insert_at += 1
    if _split_scope_label:
        lines.insert(insert_at, f"%% Split scope: {_split_scope_label}")
        insert_at += 1
    if _split_reason:
        lines.insert(insert_at, f"%% Split rationale: {_split_reason}")
        insert_at += 1
    if _split_purpose:
        lines.insert(insert_at, f"%% Split purpose: {_split_purpose}")
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
