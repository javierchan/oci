from __future__ import annotations

import json
import os
import re
import subprocess
import hashlib
import time
from dataclasses import dataclass
import logging
from pathlib import Path
from shutil import which
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .graph import Edge, Node
from .architecture_concepts import build_scope_concepts, build_workload_concepts, build_workload_context
from .diagram_utils import (
    _slugify,
    _short_ocid,
    _redact_ocids_for_label,
    _redact_ocids_for_id,
    _semantic_id_key,
    _get_meta,
    _node_metadata,
    _is_node_type,
    _mermaid_id,
    _unique_mermaid_id_factory,
    _friendly_type,
    _compact_label,
    _node_tag_label_suffix,
    _sanitize_edge_label,
    _mermaid_text_size,
    _edge_sort_key,
    _edge_single_target_map,
)
from ..normalize.transform import group_workload_candidates
from ..util.errors import ExportError

_NON_ARCH_LEAF_NODETYPES: Set[str] = {
    "VolumeBackup",
    "BootVolumeBackup",
    "VolumeGroupBackup",
    "OsmhSoftwareSource",
    "OsmhProfile",
    "network.Subnet",
    "Subnet",
    "network.RouteTable",
    "RouteTable",
    "network.SecurityList",
    "SecurityList",
    "network.DHCPOptions",
    "DHCPOptions",
    "CustomerDnsZone",
    "DnsResolver",
    "DnsView",
    "network.Vnic",
    "Vnic",
    "PrivateIp",
    "TagDefault",
    "TagNamespace",
}
MAX_MERMAID_TEXT_CHARS = 75000

# Edge relation types that are architecturally meaningful in network diagrams.
# Structural/administrative relations (IN_VCN, IN_SUBNET, IN_COMPARTMENT,
# USES_DHCP_OPTIONS, USES_ROUTE_TABLE, USES_SECURITY_LIST) are implicit from
# the subgraph layout and produce massive visual noise without adding value.
_NETWORK_DIAGRAM_EDGE_ALLOWLIST: Set[str] = {
    "ATTACHED_TO_DRG",
    "ATTACHED_TO_VCN",
    "USES_DRG",
    "EXPOSES_PUBLIC_IP",
    "ATTACHED_BOOT_VOLUME",
    "ATTACHED_VOLUME",
    "PEERED_WITH",
    "CONNECTED_TO",
    "ROUTES_TO_GATEWAY",
    "USES_NSG",
    "RESOLVES_TO_PRIVATE_IP",
    "ROUTES_TO_PRIVATE_IP",
}
LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-pass rendering context
# Set by write_diagram_projections before any diagram is generated.
# Not thread-safe; diagram generation is always sequential within a single pass.
# ---------------------------------------------------------------------------
DIAGRAM_THEMES = {"default", "dark", "forest", "neutral", "base"}
_RENDER_THEME: str = "default"
_RENDER_LABEL_TAG_KEYS: Optional[Tuple[str, ...]] = None

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

ARCH_LANE_ORDER: Tuple[str, ...] = (
    "iam",
    "network",
    "app",
    "data",
    "security",
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

# Compression: if a subnet has >= this many nodes of the same aggregate type,
# render as a summary node "Type (n=X)" instead of individual nodes.
# Only applied when diagram depth < 3 (full detail).
NETWORK_COMPRESSION_THRESHOLD = 4

ARCH_MAX_COMPARTMENTS = 2
ARCH_MAX_VCNS_PER_COMPARTMENT = 3
ARCH_MAX_WORKLOADS = 60
ARCH_MAX_VCNS = 60
ARCH_MAX_TIER_NODES = 8
ARCH_MIN_WORKLOAD_NODES = 5
TENANCY_OVERVIEW_TOP_N = 15
CONSOLIDATED_OVERVIEW_TOP_N = 12
TENANCY_SPLIT_TOP_N = 30
CONSOLIDATED_SPLIT_TOP_N = 25
ARCH_TENANCY_TOP_N = 10
ARCH_LANE_TOP_N = 6
ARCH_CONSOLIDATED_TOP_N = 10
ARCH_COMPARTMENT_TOP_N = 12

_ARCH_FILTER_NODETYPES: Set[str] = {
    "LogAnalyticsEntity",
    "Log",
    "LogGroup",
    "LogAnalyticsLogGroup",
    "ServiceConnector",
    "OsmhSoftwareSource",
}

CONSOLIDATED_WORKLOAD_TOP_N = 8

@dataclass(frozen=True)
class _DerivedAttachment:
    resource_ocid: str
    vcn_ocid: Optional[str]
    subnet_ocid: Optional[str]

@dataclass(frozen=True)
class DiagramValidationIssue:
    file: str
    rule_id: str
    description: str

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
    compact = _redact_ocids_for_label(compact)
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
    safe_scope = _redact_ocids_for_label(scope)
    comments = [f"%% Scope: {safe_scope}", f"%% View: {view}"]
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


def _mermaid_label_for(node: Node) -> str:
    name = str(node.get("name") or "").strip()
    node_type = str(node.get("nodeType") or "").strip()

    if not name:
        name = _short_ocid(str(node.get("nodeId") or ""))
    # Replace OCID substrings in the label rather than wiping the entire name,
    # so labels like "DRG Attachment for ocid1.vlan..." → "DRG Attachment for Redacted".
    if "ocid1" in name:
        name = _redact_ocids_for_label(name)

    # If a placeholder compartment node was synthesized, avoid printing the full OCID.
    if _is_node_type(node, "Compartment") and name.startswith("ocid1"):
        name = f"Compartment {_short_ocid(name)}"

    if node_type and node_type != "Compartment":
        label = f"{name}<br>{_friendly_type(node_type)}"
    else:
        label = name

    # Append configured OCI tag values to the label (e.g., env=prod, workload=payments).
    tag_keys = _RENDER_LABEL_TAG_KEYS
    if tag_keys:
        tag_suffix = _node_tag_label_suffix(node, tag_keys)
        if tag_suffix:
            label = f"{label}<br>{tag_suffix}"

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
    # Styles vary by _RENDER_THEME; keep role-based class names stable across themes.
    theme = _RENDER_THEME
    if theme == "dark":
        return [
            "%% Styles (dark theme, role-based)",
            "classDef external stroke-width:2px,stroke-dasharray: 4 3,fill:#1e2a3a,color:#9ecfff;",
            "classDef region stroke-width:2px,stroke-dasharray: 2 2,fill:#1a1a2e,color:#aaa;",
            "classDef boundary stroke-width:2px,stroke-dasharray: 6 3,fill:#1e1e2e,color:#ccc;",
            "classDef compute stroke-width:2px,fill:#1a3a5c,stroke:#4a9eff,color:#fff;",
            "classDef network stroke-width:2px,fill:#1a3a2c,stroke:#4aff9e,color:#fff;",
            "classDef storage stroke-width:2px,fill:#3a1a1a,stroke:#ff9e4a,color:#fff;",
            "classDef policy stroke-width:2px,fill:#2c1a3a,stroke:#9e4aff,color:#fff;",
            "classDef summary stroke-dasharray: 3 3,fill:#222,color:#bbb;",
            "classDef prod stroke:#ff8800,stroke-width:4px,fill:#3a2000,color:#fff;",
            "classDef nonprod stroke:#888888,stroke-width:2px,stroke-dasharray: 5 5,fill:#2a2a2a,color:#ccc;",
            "classDef alert stroke:#ff4444,stroke-width:4px,fill:#3a0000,color:#fff;",
        ]
    if theme == "high_contrast":
        return [
            "%% Styles (high-contrast theme, role-based)",
            "classDef external stroke-width:3px,stroke-dasharray: 4 3,stroke:#000;",
            "classDef region stroke-width:3px,stroke-dasharray: 2 2,stroke:#000;",
            "classDef boundary stroke-width:3px,stroke-dasharray: 6 3,stroke:#000;",
            "classDef compute stroke-width:3px,fill:#ddeeff,stroke:#003399,color:#000;",
            "classDef network stroke-width:3px,fill:#ddffee,stroke:#006600,color:#000;",
            "classDef storage stroke-width:3px,fill:#fff0dd,stroke:#993300,color:#000;",
            "classDef policy stroke-width:3px,fill:#f0ddff,stroke:#660099,color:#000;",
            "classDef summary stroke-dasharray: 3 3,stroke-width:2px;",
            "classDef prod stroke:#cc4400,stroke-width:5px,fill:#ffe8d0;",
            "classDef nonprod stroke:#444444,stroke-width:3px,stroke-dasharray: 5 5,fill:#eeeeee;",
            "classDef alert stroke:#cc0000,stroke-width:5px,fill:#ffe0e0;",
        ]
    # default theme — subtle, role-based
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
    theme = _RENDER_THEME
    theme_fragment = ""
    if theme and theme != "default":
        theme_fragment = f", \"theme\": \"{theme}\""
    return (
        f"%%{{init: {{\"flowchart\": {{\"defaultRenderer\": \"elk\", "
        f"\"nodeSpacing\": 80, \"rankSpacing\": 80, \"wrappingWidth\": 260}}{theme_fragment}}} }}%%"
    )

def _vcn_label_compact(node: Node) -> str:
    name = _compact_label(str(node.get("name") or "VCN").strip(), max_len=48)
    return f"VCN: {name}"

def _subnet_label_compact(node: Node) -> str:
    meta = _node_metadata(node)
    name = _compact_label(str(node.get("name") or "Subnet").strip(), max_len=48)
    prohibit = _get_meta(meta, "prohibit_public_ip_on_vnic")
    vis = "private" if prohibit is True else "public" if prohibit is False else "subnet"
    return f"Subnet: {name} ({vis})"


_SUBNET_EXPAND_THRESHOLD = 5  # expand individual subnets only when count ≤ this


def _classify_subnet_tier(node: Node) -> str:
    """Return 'public', 'private', or 'db' for a Subnet node."""
    name = (node.get("name") or "").lower()
    if any(t in name for t in ("-bd-", "-db-", "database", "-data-", "_bd_", "_db_")):
        return "db"
    meta = _node_metadata(node)
    prohibit = _get_meta(meta, "prohibit_public_ip_on_vnic")
    if prohibit is False:
        return "public"
    return "private"


# Gateway types shown individually in VCN-level Resources breakdown
_VCN_LEVEL_GW_LABELS: List[Tuple[str, str]] = [
    ("InternetGateway", "IGW"),
    ("NatGateway", "NAT GW"),
    ("ServiceGateway", "Service GW"),
    ("Drg", "DRG"),
    ("LocalPeeringGateway", "LPG"),
    ("VirtualCircuit", "FastConnect"),
    ("IPSecConnection", "IPSec VPN"),
    ("NetworkSecurityGroup", "NSG"),
    ("LoadBalancer", "LBaaS"),
    ("NetworkLoadBalancer", "NLB"),
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

def _render_edge(src: str, dst: str, label: str | None = None, *, dotted: bool = False) -> str:
    arrow = "-.->" if dotted else "-->"
    if label and not dotted:
        safe = _sanitize_edge_label(label)
        if safe:
            return f"  {src} {arrow}|{safe}| {dst}"
    return f"  {src} {arrow} {dst}"

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
            lines.append(f"%% - {_redact_ocids_for_label(name)}")
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
    name = _redact_ocids_for_label(str(node.get("name") or "VCN").strip())
    if isinstance(cidr, str) and cidr:
        return f"VCN: {name} ({cidr})"
    return f"VCN: {name}"

def _subnet_label(node: Node) -> str:
    meta = _node_metadata(node)
    name = _redact_ocids_for_label(str(node.get("name") or "Subnet").strip())
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

            # Checkpoint: record position before writing compartment header so we can
            # roll back the whole block if it ends up empty.
            _comp_start = len(lines)
            lines.append(f"  subgraph {comp_id}[\"{comp_label}\"]")
            lines.append("    direction TB")
            _comp_content_start = len(lines)  # content starts here

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
                    # Render gateway type breakdown instead of generic category counts
                    _gw_counts: Dict[str, int] = {}
                    _non_gw: List[Node] = []
                    for _n in vcn_resources:
                        _matched = False
                        for _gw_type, _gw_lbl in _VCN_LEVEL_GW_LABELS:
                            if _is_node_type(_n, _gw_type):
                                _gw_counts[_gw_lbl] = _gw_counts.get(_gw_lbl, 0) + 1
                                _matched = True
                                break
                        if not _matched:
                            _non_gw.append(_n)
                    for _, _gw_lbl in _VCN_LEVEL_GW_LABELS:
                        if _gw_lbl not in _gw_counts:
                            continue
                        _gw_nid = _mermaid_id(f"summary:vcn:{vcn_ocid}:gw:{_gw_lbl}")
                        lines.extend(_render_node_with_class(_gw_nid, f"{_gw_lbl} ({_gw_counts[_gw_lbl]})", cls="summary network", shape="rect"))
                    if _non_gw:
                        _render_summary_nodes(f"vcn:{vcn_ocid}:other", _non_gw)
                    lines.append("      end")

                comp_subnets = [
                    n
                    for n in comp_nodes
                    if _is_node_type(n, "Subnet") and subnet_to_vcn.get(str(n.get("nodeId") or "")) == vcn_ocid
                ]
                if len(comp_subnets) <= _SUBNET_EXPAND_THRESHOLD:
                    # Expand subnets individually
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
                else:
                    # Too many subnets — render tier-summary nodes instead
                    _pub = [sn for sn in comp_subnets if _classify_subnet_tier(sn) == "public"]
                    _priv = [sn for sn in comp_subnets if _classify_subnet_tier(sn) == "private"]
                    _db = [sn for sn in comp_subnets if _classify_subnet_tier(sn) == "db"]
                    for _tier_label, _tier_subnets in [
                        ("Public Subnets", _pub),
                        ("Private Subnets", _priv),
                        ("DB Subnets", _db),
                    ]:
                        if not _tier_subnets:
                            continue
                        _tier_id = _mermaid_id(f"summary:subnet_tier:{vcn_ocid}:{_tier_label}")
                        lines.extend(_render_node_with_class(
                            _tier_id, f"{_tier_label} ({len(_tier_subnets)})", cls="summary network", shape="rect"
                        ))
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

            if len(lines) > _comp_content_start:
                # Has content — close the subgraph
                lines.append("  end")
            else:
                # Empty compartment — roll back the header
                del lines[_comp_start:]
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

        # If we have a subnet but no VCN, infer VCN from the subnet's own IN_VCN
        # edge or metadata. This fixes resources (ADB, PrivateIp, Vnic, etc.) that
        # have an IN_SUBNET edge but no direct IN_VCN edge.
        if subnet and not vcn:
            sn_node = node_by_id.get(subnet)
            if sn_node:
                sn_meta = _node_metadata(sn_node)
                inferred_vcn = (
                    edge_vcn_by_src.get(subnet)
                    or _get_meta(sn_meta, "vcn_id")
                    or _get_meta(sn_meta, "vcnId")
                )
                if isinstance(inferred_vcn, str) and inferred_vcn and inferred_vcn in node_by_id:
                    vcn = inferred_vcn

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
        safe = _arch_safe_label(wl_name, default="Workload")
        results.append((f"Workload: {safe}", len(wl_nodes)))
    return results

def _compact_overview_lines(
    *,
    nodes: Sequence[Node],
    title: str,
    top_n: int,
    include_workloads: bool = True,
    flow_direction: str = "LR",
) -> List[str]:
    lines: List[str] = [_flowchart_elk_init_line(), f"flowchart {flow_direction}"]
    _insert_scope_view_comments(lines, scope="tenancy", view="overview")
    lines.extend(_style_block_lines())
    lines.append(f"%% {title}")
    tenancy_label = _tenancy_label(nodes).replace('"', "'")
    tenancy_id = _mermaid_id(f"overview:{title}:tenancy")
    lines.append(f"subgraph {tenancy_id}[\"{tenancy_label}\"]")

    regions = _region_list(nodes)
    if regions:
        lines.append("  subgraph overview_regions[\"Regions\"]")
        for region in regions:
            node_id = _mermaid_id(f"overview:region:{region}")
            lines.extend(_render_node_with_class(node_id, f"Region: {region}", cls="region", shape="round"))
        lines.append("  end")

    # Build compartment resource-type breakdown for richer overview labels
    comp_type_counts: Dict[str, Dict[str, int]] = {}
    for n in nodes:
        if _is_node_type(n, "Compartment"):
            continue
        nt = str(n.get("nodeType") or "")
        if nt in _NON_ARCH_LEAF_NODETYPES:
            continue
        cid = str(n.get("compartmentId") or "")
        if not cid:
            continue
        comp_type_counts.setdefault(cid, {})
        comp_type_counts[cid][nt] = comp_type_counts[cid].get(nt, 0) + 1
    # Map compartment ID → label for the breakdown
    comp_label_by_id: Dict[str, str] = {}
    for n in nodes:
        if _is_node_type(n, "Compartment") and n.get("nodeId"):
            cid = str(n.get("nodeId") or "")
            comp_label_by_id[cid] = str(n.get("name") or cid)

    comp_items = _top_compartment_counts(nodes)
    top_comp, rest_comp = _overview_top_counts(comp_items, top_n)
    lines.append("  subgraph overview_compartments[\"Top Compartments\"]")
    for label, count in top_comp:
        node_id = _mermaid_id(f"overview:comp:{label}")
        lines.append(f"    {node_id}[\"{label} (n={count})\"]")
    if rest_comp:
        node_id = _mermaid_id("overview:comp:other")
        lines.append(f"    {node_id}[\"Other Compartments (n={rest_comp})\"]")
    lines.append("  end")

    # Compute summary section (non-trivial compute/data resources)
    _SUMMARY_TYPES = {
        "compute.Instance": "Instances",
        "Instance": "Instances",
        "AutonomousDatabase": "ADB",
        "security.Bastion": "Bastion",
        "Bastion": "Bastion",
        "network.Drg": "DRG",
        "Drg": "DRG",
        "IPSecConnection": "VPN",
        "VirtualCircuit": "FastConnect",
        "VmwareSddc": "OCVS",
        "OrmStack": "ORM Stack",
        "Bucket": "Object Storage",
    }
    summary_counts: Dict[str, int] = {}
    for n in nodes:
        nt = str(n.get("nodeType") or "")
        friendly = _SUMMARY_TYPES.get(nt)
        if friendly:
            summary_counts[friendly] = summary_counts.get(friendly, 0) + 1
    if summary_counts:
        lines.append("  subgraph overview_services[\"Key Services\"]")
        for friendly, count in sorted(summary_counts.items(), key=lambda x: -x[1]):
            node_id = _mermaid_id(f"overview:svc:{friendly}")
            lines.append(f"    {node_id}[\"{friendly}: {count}\"]")
        lines.append("  end")

    vcn_items = _top_vcn_counts(nodes)
    top_vcn, rest_vcn = _overview_top_counts(vcn_items, top_n)
    if top_vcn:
        lines.append("  subgraph overview_vcns[\"Top VCNs\"]")
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

def _build_drg_vcn_map(nodes: Sequence[Node]) -> Dict[str, List[Tuple[str, str]]]:
    """
    Build a mapping from DRG OCID → [(vcn_ocid, vcn_name), ...] using DrgAttachment metadata.
    Used to render cross-VCN peering connections in network diagrams.
    """
    vcn_names: Dict[str, str] = {
        str(n.get("nodeId") or ""): str(n.get("name") or "")
        for n in nodes
        if _is_node_type(n, "Vcn") and n.get("nodeId")
    }
    drg_to_vcns: Dict[str, List[Tuple[str, str]]] = {}
    for n in nodes:
        if not _is_node_type(n, "DrgAttachment"):
            continue
        meta = _node_metadata(n)
        drg_id = str(_get_meta(meta, "drg_id", "drgId") or "").strip()
        vcn_id = str(_get_meta(meta, "vcn_id", "vcnId") or "").strip()
        if not drg_id or not vcn_id:
            continue
        drg_to_vcns.setdefault(drg_id, [])
        existing = {pair[0] for pair in drg_to_vcns[drg_id]}
        if vcn_id not in existing:
            drg_to_vcns[drg_id].append((vcn_id, vcn_names.get(vcn_id, "")))
    return drg_to_vcns


def _write_drg_hub_views(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    summary: Optional[DiagramSummary] = None,
) -> List[Path]:
    """Generate a DRG Hub Connectivity diagram for each DRG that connects multiple VCNs or
    has IPSec/FastConnect attachments. Output: diagram.network.drg.{slug}.mmd"""
    summary = _ensure_diagram_summary(summary)
    drgs = [n for n in nodes if _is_node_type(n, "Drg")]
    if not drgs:
        return []

    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}
    drg_to_vcns = _build_drg_vcn_map(nodes)

    # Map DRG → [DrgAttachment nodes]
    # Also collect IPSec connections and VirtualCircuits attached via DrgAttachments
    edge_drg_by_src: Dict[str, str] = {}
    for edge in edges:
        if str(edge.get("relation_type") or "") in ("ATTACHED_TO_DRG", "USES_DRG"):
            src = str(edge.get("source_ocid") or "")
            dst = str(edge.get("target_ocid") or "")
            if src and dst:
                edge_drg_by_src.setdefault(src, dst)

    out_paths: List[Path] = []

    for drg in drgs:
        drg_ocid = str(drg.get("nodeId") or "")
        drg_name = str(drg.get("name") or "drg").strip() or "drg"

        vcn_pairs = drg_to_vcns.get(drg_ocid, [])
        # Find DrgAttachments, IPSecConnections, VirtualCircuits that reference this DRG
        attachments = [
            n for n in nodes
            if _is_node_type(n, "DrgAttachment", "IPSecConnection", "VirtualCircuit", "Cpe")
            and edge_drg_by_src.get(str(n.get("nodeId") or "")) == drg_ocid
        ]
        ipsec = [n for n in attachments if _is_node_type(n, "IPSecConnection")]
        vc = [n for n in attachments if _is_node_type(n, "VirtualCircuit")]
        cpes = [n for n in attachments if _is_node_type(n, "Cpe")]

        # Only generate a hub diagram if there are 2+ VCNs or external connections
        if len(vcn_pairs) < 2 and not ipsec and not vc:
            continue

        fname = f"diagram.network.drg.{_slugify(drg_name)}.mmd"
        path = outdir / fname

        reserved_ids = {_mermaid_id(str(n.get("nodeId") or "")) for n in nodes if n.get("nodeId")}
        make_group_id = _unique_mermaid_id_factory(reserved_ids)

        lines: List[str] = [_flowchart_elk_init_line(), "flowchart LR"]
        _insert_scope_view_comments(lines, scope=f"drg:{drg_name}", view="hub-connectivity")
        lines.extend(_style_block_lines())
        lines.append(f"%% DRG Hub: {drg_name}")

        # External nodes
        has_ipsec = bool(ipsec)
        has_vc = bool(vc)
        customer_net_id = ""
        if has_ipsec or has_vc or cpes:
            customer_net_id = _mermaid_id(f"external:customer_net:{drg_ocid}")
            lines.extend(_render_node_with_class(customer_net_id, "Customer / On-Premises Network", cls="external", shape="round"))
        internet_id = ""
        if has_ipsec:
            internet_id = _mermaid_id(f"external:internet:{drg_ocid}")
            lines.extend(_render_node_with_class(internet_id, "Internet", cls="external", shape="round"))

        # DRG hub node
        tenancy_label = _tenancy_label(nodes)
        tenancy_id = make_group_id(f"tenancy:drg:{drg_ocid}")
        lines.append(f"subgraph {tenancy_id}[\"{tenancy_label.replace(chr(34), chr(39))}\"]")
        lines.append("  direction TB")

        hub_group_id = make_group_id(f"drg:hub:{drg_ocid}")
        drg_label_safe = _compact_label(drg_name, max_len=40).replace('"', "'")
        lines.append(f"  subgraph {hub_group_id}[\"DRG Hub: {drg_label_safe}\"]")
        lines.append("    direction TB")

        drg_node_id = _mermaid_id(drg_ocid)
        lines.extend(_render_node_with_class(drg_node_id, f"{drg_name}<br>Drg", cls="network", shape="rect"))

        # IPSec connections
        for conn in sorted(ipsec, key=lambda n: str(n.get("name") or "")):
            nid = _mermaid_id(str(conn.get("nodeId") or ""))
            lines.extend(_render_node_with_class(nid, _mermaid_label_for(conn), cls="network", shape="rect"))
            lines.append(_render_edge(drg_node_id, nid, "IPSec VPN"))

        # FastConnect virtual circuits
        for circuit in sorted(vc, key=lambda n: str(n.get("name") or "")):
            nid = _mermaid_id(str(circuit.get("nodeId") or ""))
            lines.extend(_render_node_with_class(nid, _mermaid_label_for(circuit), cls="network", shape="rect"))
            lines.append(_render_edge(drg_node_id, nid, "FastConnect"))

        lines.append("  end")

        # VCN spokes
        vcns_group_id = make_group_id(f"drg:vcns:{drg_ocid}")
        lines.append(f"  subgraph {vcns_group_id}[\"Attached VCNs\"]")
        lines.append("    direction TB")
        for vcn_ocid, vcn_name in sorted(vcn_pairs, key=lambda p: p[1] or p[0]):
            vcn_node = node_by_id.get(vcn_ocid)
            vcn_label = _compact_label(vcn_name or vcn_ocid, max_len=40)
            if vcn_node:
                meta = _node_metadata(vcn_node)
                cidr = _get_meta(meta, "cidr_block", "cidrBlock", "cidrBlocks") or ""
                if isinstance(cidr, list):
                    cidr = ", ".join(str(c) for c in cidr[:2])
                if cidr:
                    vcn_label = f"{vcn_label}<br>{cidr}"
            vcn_id = _mermaid_id(vcn_ocid)
            lines.extend(_render_node_with_class(vcn_id, vcn_label, cls="network", shape="rect"))
            lines.append(_render_edge(drg_node_id, vcn_id, "VCN attachment"))
        lines.append("  end")

        lines.append("end")

        # External connectivity edges
        for conn in ipsec:
            nid = _mermaid_id(str(conn.get("nodeId") or ""))
            if customer_net_id:
                lines.append(_render_edge(nid, customer_net_id, "encrypted tunnel", dotted=True))
        for circuit in vc:
            nid = _mermaid_id(str(circuit.get("nodeId") or ""))
            if customer_net_id:
                lines.append(_render_edge(nid, customer_net_id, "private circuit", dotted=True))

        text = "\n".join(lines) + "\n"
        size = _mermaid_text_size(text)
        if size > MAX_MERMAID_TEXT_CHARS:
            LOG.warning("DRG hub diagram %s exceeds Mermaid limit (%s chars); skipping.", fname, size)
            _record_diagram_skip(summary, diagram=fname, kind="network", size=size, limit=MAX_MERMAID_TEXT_CHARS, reason="exceeds Mermaid size limit")
            continue

        path.write_text(text, encoding="utf-8")
        out_paths.append(path)

    return out_paths


def _compress_subnet_nodes(
    nodes: Sequence[Node],
    threshold: int = NETWORK_COMPRESSION_THRESHOLD,
) -> Tuple[List[Node], Dict[str, Tuple[str, int, Node]]]:
    """
    Split nodes into individually-rendered nodes and compressed summary groups.

    Returns:
        individual: nodes that should be rendered as individual diagram nodes.
        compressed: {aggregate_label -> (css_class, count, representative_node)}
            for groups that should be rendered as a single "Label (n=X)" summary node.
    """
    buckets: Dict[str, List[Node]] = {}
    for n in nodes:
        label = _tenancy_aggregate_label(n)
        buckets.setdefault(label, []).append(n)

    individual: List[Node] = []
    compressed: Dict[str, Tuple[str, int, Node]] = {}
    for label, group in sorted(buckets.items()):
        if len(group) >= threshold:
            rep = sorted(group, key=lambda n: (str(n.get("name") or ""), str(n.get("nodeId") or "")))[0]
            compressed[label] = (_node_class(rep), len(group), rep)
        else:
            individual.extend(group)
    return individual, compressed


def _write_network_views(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    depth: int = 3,
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

    # Build DRG→VCNs map once for cross-VCN peering edges.
    drg_to_vcns = _build_drg_vcn_map(nodes)

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
                and not _is_node_type(n, "Vcn", "Subnet", "Vnic", "PrivateIp")
            ]

            # At depth < 3, compress homogeneous resource groups into summary nodes.
            if depth < 3:
                individual_attached, compressed_groups = _compress_subnet_nodes(attached)
            else:
                individual_attached, compressed_groups = list(attached), {}

            for n in sorted(
                individual_attached,
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

            for agg_label, (agg_cls, agg_count, rep_node) in sorted(compressed_groups.items()):
                agg_node_id = _mermaid_id(f"compressed:{sn_ocid}:{agg_label}")
                agg_display = _compact_label(f"{agg_label} (n={agg_count})", max_len=48)
                lines.extend(_render_node_with_class(agg_node_id, agg_display, cls=agg_cls, shape="rect"))
                # Map all compressed resource OCIDs to this summary node so relationship edges resolve.
                for orig_n in nodes:
                    if (
                        attach_by_res.get(str(orig_n.get("nodeId") or ""))
                        and attach_by_res[str(orig_n.get("nodeId") or "")].subnet_ocid == sn_ocid
                        and _tenancy_aggregate_label(orig_n) == agg_label
                        and not _is_node_type(orig_n, "Vcn", "Subnet")
                    ):
                        raw_id = str(orig_n.get("nodeId") or "")
                        if raw_id:
                            rendered_node_ids.add(raw_id)
                            edge_node_id_map.setdefault(raw_id, agg_node_id)

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
            allowlist=_NETWORK_DIAGRAM_EDGE_ALLOWLIST,
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

        # Cross-VCN DRG peering: for each DRG attached to this VCN, find peer VCNs on the same DRG.
        for g in gateways:
            if not _is_node_type(g, "Drg"):
                continue
            drg_ocid = str(g.get("nodeId") or "")
            if not drg_ocid:
                continue
            peer_vcns = [
                (vcn_id, vcn_name)
                for vcn_id, vcn_name in drg_to_vcns.get(drg_ocid, [])
                if vcn_id != vcn_ocid
            ]
            if not peer_vcns:
                continue
            peer_labels = ", ".join(
                _compact_label(vcn_name or vcn_id, max_len=32)
                for vcn_id, vcn_name in sorted(peer_vcns, key=lambda p: p[1] or p[0])
            )
            drg_peers_id = _mermaid_id(f"external:drg_peers:{vcn_ocid}:{drg_ocid}")
            peer_display = _compact_label(f"Peered VCNs: {peer_labels}", max_len=64)
            lines.extend(_render_node_with_class(drg_peers_id, peer_display, cls="external", shape="round"))
            g_id = _mermaid_id(drg_ocid)
            lines.append(_render_edge(g_id, drg_peers_id, "DRG peering", dotted=True))

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
    depth: int = 3,
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
        safe_wl = _redact_ocids_for_label(wl_name)
        note_label = _sanitize_edge_label(f"Workload {safe_wl} split; see notes")
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

def _write_landing_zone_diagram(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    summary: Optional[DiagramSummary] = None,
) -> Optional[Path]:
    """Generate diagram.arch.landing_zone.mmd — an OCI Landing Zone style architecture diagram.

    Structure (top-to-bottom):
      Tenancy
        ├─ IAM section  (Users, Groups, DynGroups, Policies)
        ├─ Network Compartment  (VCNs with subnet tiers, gateways, DRG)
        ├─ Security Compartment (Vault, CloudGuard, Bastion, etc.)
        ├─ Compute/App Compartment (Instances, ADB, etc.)
        └─ Other Compartments
    """
    summary = _ensure_diagram_summary(summary)
    fname = "diagram.arch.landing_zone.mmd"
    path = outdir / fname

    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}
    reserved_ids = {_mermaid_id(str(n.get("nodeId") or "")) for n in nodes if n.get("nodeId")}
    make_group_id = _unique_mermaid_id_factory(reserved_ids)

    # --- Classify compartments by functional role ---
    _COMP_ROLE_KEYWORDS: Dict[str, str] = {
        "network": "network",
        "net": "network",
        "security": "security",
        "sec": "security",
        "database": "data",
        "db": "data",
        "data": "data",
        "app": "app",
        "compute": "app",
        "ocvs": "app",
        "workload": "app",
        "mgmt": "mgmt",
        "mgm": "mgmt",
        "management": "mgmt",
    }
    comp_nodes = [n for n in nodes if _is_node_type(n, "Compartment") and n.get("nodeId")]
    comp_role: Dict[str, str] = {}
    for c in comp_nodes:
        cid = str(c.get("nodeId") or "")
        cname = str(c.get("name") or "").lower()
        role = "other"
        for kw, r in _COMP_ROLE_KEYWORDS.items():
            if kw in cname:
                role = r
                break
        comp_role[cid] = role

    # Group nodes by compartment
    nodes_by_comp: Dict[str, List[Node]] = {}
    for n in nodes:
        if _is_node_type(n, "Compartment"):
            continue
        cid = str(n.get("compartmentId") or "")
        if cid:
            nodes_by_comp.setdefault(cid, []).append(n)

    # Group compartments by role
    comps_by_role: Dict[str, List[Node]] = {}
    for c in comp_nodes:
        cid = str(c.get("nodeId") or "")
        role = comp_role.get(cid, "other")
        comps_by_role.setdefault(role, []).append(c)

    # --- IAM nodes ---
    iam_types = {"User", "Group", "DynamicResourceGroup", "Policy"}
    iam_nodes = [n for n in nodes if str(n.get("nodeType") or "") in iam_types]

    # --- VCN / network data ---
    vcns = [n for n in nodes if _is_node_type(n, "Vcn")]
    subnets = [n for n in nodes if _is_node_type(n, "Subnet")]
    edge_vcn_by_src = _edge_single_target_map(edges, "IN_VCN")
    edge_subnet_by_src = _edge_single_target_map(edges, "IN_SUBNET")
    attachments = _derived_attachments(nodes, edges)
    attach_by_res: Dict[str, _DerivedAttachment] = {a.resource_ocid: a for a in attachments}

    subnet_to_vcn: Dict[str, str] = {}
    for sn in subnets:
        meta = _node_metadata(sn)
        sn_id = str(sn.get("nodeId") or "")
        vcn_id = edge_vcn_by_src.get(sn_id) or _get_meta(meta, "vcn_id")
        if isinstance(vcn_id, str) and vcn_id:
            subnet_to_vcn[sn_id] = vcn_id

    # Gateways keyed by VCN OCID. Exclude DrgAttachment (internal OCI artifact, not a
    # standalone gateway) and peering/crossconnect types to avoid clutter in the landing zone.
    _LZ_GATEWAY_EXCLUDE_TYPES = ("DrgAttachment", "CrossConnect", "CrossConnectGroup", "RemotePeeringConnection")
    gateways_by_vcn: Dict[str, List[Node]] = {}
    for n in nodes:
        if not _is_node_type(n, *_NETWORK_GATEWAY_NODETYPES):
            continue
        if _is_node_type(n, *_LZ_GATEWAY_EXCLUDE_TYPES):
            continue
        meta = _node_metadata(n)
        nid = str(n.get("nodeId") or "")
        att = attach_by_res.get(nid)
        vcn_ref = (
            edge_vcn_by_src.get(nid)
            or _get_meta(meta, "vcn_id")
            or (att.vcn_ocid if att else None)
        )
        if isinstance(vcn_ref, str) and vcn_ref:
            gateways_by_vcn.setdefault(vcn_ref, []).append(n)

    # Resources per subnet (excluding infra noise)
    _SUBNET_EXCLUDE = {"Vcn", "Subnet", "Vnic", "PrivateIp", "network.Vnic", "network.RouteTable",
                       "RouteTable", "network.SecurityList", "SecurityList", "network.DHCPOptions",
                       "DHCPOptions", "DnsResolver", "DnsView"}
    resources_by_subnet: Dict[str, List[Node]] = {}
    for n in nodes:
        nt = str(n.get("nodeType") or "")
        if nt in _SUBNET_EXCLUDE or _is_node_type(n, "Compartment"):
            continue
        ocid = str(n.get("nodeId") or "")
        att = attach_by_res.get(ocid)
        sn_id = att.subnet_ocid if att else edge_subnet_by_src.get(ocid)
        if sn_id:
            resources_by_subnet.setdefault(sn_id, []).append(n)

    # --- Build diagram lines ---
    lines: List[str] = [_flowchart_elk_init_line(), "flowchart TB"]
    _insert_scope_view_comments(lines, scope="tenancy", view="landing-zone")
    lines.extend(_style_block_lines())
    lines.append("%% OCI Landing Zone Architecture")
    lines.append("%% Compartment: Network | Security | App | Database | Other")

    # External Internet node
    has_igw = any(_is_node_type(n, "InternetGateway") for n in nodes)
    has_ipsec = any(_is_node_type(n, "IPSecConnection") for n in nodes)
    has_vc = any(_is_node_type(n, "VirtualCircuit") for n in nodes)

    if has_igw:
        internet_id = _mermaid_id("lz:external:internet")
        lines.extend(_render_node_with_class(internet_id, "Internet", cls="external", shape="round"))
    if has_ipsec or has_vc:
        onprem_id = _mermaid_id("lz:external:onprem")
        lines.extend(_render_node_with_class(onprem_id, "Customer / On-Premises", cls="external", shape="round"))

    tenancy_label = _tenancy_label(nodes).replace('"', "'")
    tenancy_group_id = make_group_id("lz:tenancy")
    lines.append(f"subgraph {tenancy_group_id}[\"{tenancy_label}\"]")
    lines.append("  direction TB")

    # IAM section
    if iam_nodes:
        iam_group_id = make_group_id("lz:iam")
        iam_counts: Dict[str, int] = {}
        for n in iam_nodes:
            nt = str(n.get("nodeType") or "")
            iam_counts[nt] = iam_counts.get(nt, 0) + 1
        iam_summary = ", ".join(f"{_friendly_type(t)}: {c}" for t, c in sorted(iam_counts.items(), key=lambda x: -x[1]))
        lines.append(f"  subgraph {iam_group_id}[\"IAM\"]")
        lines.append("    direction LR")
        iam_node_id = make_group_id("lz:iam:summary")
        lines.append(f"    {iam_node_id}[\"{iam_summary}\"]")
        lines.append("  end")

    # Network compartment(s)
    for comp in sorted(comps_by_role.get("network", []), key=lambda n: str(n.get("name") or "")):
        cid = str(comp.get("nodeId") or "")
        comp_label = _compact_label(str(comp.get("name") or "Network"), max_len=40).replace('"', "'")
        comp_group_id = make_group_id(f"lz:comp:network:{cid}")
        lines.append(f"  subgraph {comp_group_id}[\"Network: {comp_label}\"]")
        lines.append("    direction TB")

        vcns_in_comp = [v for v in vcns if str(v.get("compartmentId") or "") == cid]
        for vcn in sorted(vcns_in_comp, key=lambda n: str(n.get("name") or "")):
            vcn_ocid = str(vcn.get("nodeId") or "")
            vcn_name = str(vcn.get("name") or "VCN")
            vcn_meta = _node_metadata(vcn)
            cidr = _get_meta(vcn_meta, "cidr_block", "cidrBlock") or ""
            vcn_label = _compact_label(f"{vcn_name}", max_len=36).replace('"', "'")
            if cidr:
                vcn_label += f"<br>{cidr}"
            vcn_group_id = make_group_id(f"lz:vcn:{vcn_ocid}")
            lines.append(f"    subgraph {vcn_group_id}[\"{vcn_label}\"]")
            lines.append("      direction TB")

            # Gateways
            gateways = gateways_by_vcn.get(vcn_ocid, [])
            if gateways:
                gw_group_id = make_group_id(f"lz:vcn:{vcn_ocid}:gw")
                lines.append(f"      subgraph {gw_group_id}[\"Gateways\"]")
                lines.append("        direction LR")
                for gw in sorted(gateways, key=lambda n: str(n.get("nodeType") or "")):
                    gw_id = _mermaid_id(str(gw.get("nodeId") or ""))
                    gw_label = _compact_label(str(gw.get("name") or _friendly_type(str(gw.get("nodeType") or ""))), max_len=32)
                    lines.extend(_render_node_with_class(gw_id, gw_label, cls=_node_class(gw), shape=_node_shape(gw)))
                lines.append("      end")

            # Subnets grouped by tier (pub/priv/bd)
            vcn_subnets = [sn for sn in subnets if subnet_to_vcn.get(str(sn.get("nodeId") or "")) == vcn_ocid]
            # Tier classification
            def _subnet_tier(sn: Node) -> str:
                meta = _node_metadata(sn)
                is_pub = _get_meta(meta, "prohibit_internet_ingress", "prohibitInternetIngress")
                name_lower = str(sn.get("name") or "").lower()
                if "pub" in name_lower:
                    return "public"
                if "bd" in name_lower or "-bd-" in name_lower:
                    return "db"
                return "private"

            tiers: Dict[str, List[Node]] = {}
            for sn in sorted(vcn_subnets, key=lambda n: str(n.get("name") or "")):
                tier = _subnet_tier(sn)
                tiers.setdefault(tier, []).append(sn)

            for tier_name in ("public", "private", "db"):
                tier_subnets = tiers.get(tier_name, [])
                if not tier_subnets:
                    continue
                tier_group_id = make_group_id(f"lz:vcn:{vcn_ocid}:tier:{tier_name}")
                tier_display = tier_name.title() + " Subnets"
                lines.append(f"      subgraph {tier_group_id}[\"{tier_display}\"]")
                lines.append("        direction TB")
                # Show up to 4 subnets then summarize
                shown = tier_subnets[:4]
                rest_count = len(tier_subnets) - len(shown)
                for sn in shown:
                    sn_ocid = str(sn.get("nodeId") or "")
                    sn_meta = _node_metadata(sn)
                    sn_cidr = _get_meta(sn_meta, "cidr_block", "cidrBlock") or ""
                    sn_name = _compact_label(str(sn.get("name") or "Subnet"), max_len=28)
                    sn_label = f"{sn_name}"
                    if sn_cidr:
                        sn_label += f"<br>{sn_cidr}"
                    sn_id = _mermaid_id(sn_ocid)
                    lines.extend(_render_node_with_class(sn_id, sn_label, cls="network", shape="rect"))
                    # Resources in this subnet
                    sn_resources = resources_by_subnet.get(sn_ocid, [])
                    if sn_resources:
                        res_counts: Dict[str, int] = {}
                        for r in sn_resources:
                            rtype = _friendly_type(str(r.get("nodeType") or ""))
                            res_counts[rtype] = res_counts.get(rtype, 0) + 1
                        res_label = ", ".join(f"{t}:{c}" for t, c in sorted(res_counts.items(), key=lambda x: -x[1])[:3])
                        res_node_id = make_group_id(f"lz:subnet:{sn_ocid}:res")
                        lines.extend(_render_node_with_class(res_node_id, res_label, cls="compute", shape="rect"))
                if rest_count > 0:
                    rest_id = make_group_id(f"lz:vcn:{vcn_ocid}:tier:{tier_name}:rest")
                    lines.append(f"        {rest_id}[\"... +{rest_count} more subnets\"]")
                    lines.append(f"        class {rest_id} summary")
                lines.append("      end")

            lines.append("    end")  # vcn

        lines.append("  end")  # network comp

    # Security compartment(s)
    _SECURITY_TYPES = {"security.CloudGuardTarget", "CloudGuardTarget", "security.Bastion", "Bastion",
                       "SecurityZonesSecurityZone", "SecurityZonesSecurityRecipe", "VssHostScanRecipe",
                       "VssHostScanTarget", "LogGroup", "CloudGuardDetectorRecipe"}
    for comp in sorted(comps_by_role.get("security", []), key=lambda n: str(n.get("name") or "")):
        cid = str(comp.get("nodeId") or "")
        comp_label = _compact_label(str(comp.get("name") or "Security"), max_len=40).replace('"', "'")
        sec_group_id = make_group_id(f"lz:comp:sec:{cid}")
        lines.append(f"  subgraph {sec_group_id}[\"Security: {comp_label}\"]")
        lines.append("    direction TB")
        sec_nodes = [n for n in nodes_by_comp.get(cid, [])
                     if str(n.get("nodeType") or "") in _SECURITY_TYPES or "security" in str(n.get("nodeType") or "").lower()]
        if sec_nodes:
            for n in sorted(sec_nodes[:8], key=lambda n: str(n.get("name") or "")):
                nid = make_group_id(f"lz:sec:{str(n.get('nodeId') or '')}")
                lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls=_node_class(n), shape=_node_shape(n)))
        else:
            placeholder_id = make_group_id(f"lz:sec:placeholder:{cid}")
            lines.append(f"    {placeholder_id}[\"Security Services\"]")
        lines.append("  end")

    # App / Compute compartment(s)
    _APP_TYPES = {"compute.Instance", "Instance", "AutonomousDatabase", "Functions", "App",
                  "OrmStack", "security.Bastion", "Bastion", "VmwareSddc", "VmwareCluster"}
    for comp in sorted(comps_by_role.get("app", []), key=lambda n: str(n.get("name") or "")):
        cid = str(comp.get("nodeId") or "")
        comp_label = _compact_label(str(comp.get("name") or "App"), max_len=40).replace('"', "'")
        app_group_id = make_group_id(f"lz:comp:app:{cid}")
        lines.append(f"  subgraph {app_group_id}[\"App: {comp_label}\"]")
        lines.append("    direction LR")
        comp_resources = nodes_by_comp.get(cid, [])
        type_counts: Dict[str, int] = {}
        for n in comp_resources:
            nt = str(n.get("nodeType") or "")
            if nt in _NON_ARCH_LEAF_NODETYPES:
                continue
            ft = _friendly_type(nt)
            type_counts[ft] = type_counts.get(ft, 0) + 1
        if type_counts:
            for ft, cnt in sorted(type_counts.items(), key=lambda x: -x[1])[:8]:
                tc_id = make_group_id(f"lz:app:{cid}:{ft}")
                lines.extend(_render_node_with_class(tc_id, f"{ft}: {cnt}", cls="compute", shape="rect"))
        else:
            ph_id = make_group_id(f"lz:app:placeholder:{cid}")
            lines.append(f"    {ph_id}[\"Compute Services\"]")
        lines.append("  end")

    # Data compartment(s)
    for comp in sorted(comps_by_role.get("data", []), key=lambda n: str(n.get("name") or "")):
        cid = str(comp.get("nodeId") or "")
        comp_label = _compact_label(str(comp.get("name") or "Data"), max_len=40).replace('"', "'")
        data_group_id = make_group_id(f"lz:comp:data:{cid}")
        lines.append(f"  subgraph {data_group_id}[\"Database: {comp_label}\"]")
        lines.append("    direction LR")
        data_nodes = [n for n in nodes_by_comp.get(cid, [])
                      if not str(n.get("nodeType") or "") in _NON_ARCH_LEAF_NODETYPES]
        type_counts_d: Dict[str, int] = {}
        for n in data_nodes:
            ft = _friendly_type(str(n.get("nodeType") or ""))
            type_counts_d[ft] = type_counts_d.get(ft, 0) + 1
        if type_counts_d:
            for ft, cnt in sorted(type_counts_d.items(), key=lambda x: -x[1])[:6]:
                td_id = make_group_id(f"lz:data:{cid}:{ft}")
                lines.extend(_render_node_with_class(td_id, f"{ft}: {cnt}", cls="storage", shape="rect"))
        else:
            ph_id = make_group_id(f"lz:data:placeholder:{cid}")
            lines.append(f"    {ph_id}[\"Database Services\"]")
        lines.append("  end")

    # Other compartments (collapsed summary)
    other_comps = comps_by_role.get("other", []) + comps_by_role.get("mgmt", [])
    if other_comps:
        other_group_id = make_group_id("lz:comp:other")
        lines.append(f"  subgraph {other_group_id}[\"Other Compartments\"]")
        lines.append("    direction LR")
        for comp in sorted(other_comps, key=lambda n: str(n.get("name") or ""))[:6]:
            cid = str(comp.get("nodeId") or "")
            cname = _compact_label(str(comp.get("name") or "Compartment"), max_len=32)
            cnt = len([n for n in nodes_by_comp.get(cid, [])
                       if str(n.get("nodeType") or "") not in _NON_ARCH_LEAF_NODETYPES])
            oc_id = make_group_id(f"lz:other:{cid}")
            lines.append(f"    {oc_id}[\"{cname} ({cnt})\"]")
        lines.append("  end")

    lines.append("end")  # tenancy

    # Connectivity edges (inferred)
    if has_igw:
        for vcn in vcns:
            vcn_ocid = str(vcn.get("nodeId") or "")
            igw = next((g for g in gateways_by_vcn.get(vcn_ocid, []) if _is_node_type(g, "InternetGateway")), None)
            if igw:
                igw_id = _mermaid_id(str(igw.get("nodeId") or ""))
                lines.append(_render_edge(internet_id, igw_id, "Internet access", dotted=True))
                break  # one representative edge is enough
    if (has_ipsec or has_vc):
        drgs = [n for n in nodes if _is_node_type(n, "Drg")]
        for drg in drgs[:1]:
            drg_id = _mermaid_id(str(drg.get("nodeId") or ""))
            lines.append(_render_edge(onprem_id, drg_id, "VPN/FastConnect", dotted=True))

    text = "\n".join(lines) + "\n"
    size = _mermaid_text_size(text)
    if size > MAX_MERMAID_TEXT_CHARS:
        LOG.warning("Landing zone diagram %s exceeds Mermaid limit (%s chars); skipping.", fname, size)
        _record_diagram_skip(summary, diagram=fname, kind="consolidated", size=size, limit=MAX_MERMAID_TEXT_CHARS, reason="exceeds Mermaid size limit")
        return None

    path.write_text(text, encoding="utf-8")
    return path


def write_diagram_projections(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    diagram_depth: Optional[int] = None,
    diagram_depth_tenancy: Optional[int] = None,
    diagram_depth_network: Optional[int] = None,
    diagram_depth_workload: Optional[int] = None,
    diagram_depth_consolidated: Optional[int] = None,
    diagram_theme: Optional[str] = None,
    diagram_node_label_tags: Optional[Sequence[str]] = None,
    summary: Optional[DiagramSummary] = None,
    enable_tenancy: bool = True,
    enable_network: bool = True,
    enable_workload: bool = True,
    enable_consolidated: bool = True,
) -> List[Path]:
    # Edges drive placement and relationship hints in projections.
    # Per-type depth overrides take precedence over the global diagram_depth.
    global _RENDER_THEME, _RENDER_LABEL_TAG_KEYS
    _RENDER_THEME = diagram_theme if diagram_theme in DIAGRAM_THEMES else "default"
    _RENDER_LABEL_TAG_KEYS = tuple(diagram_node_label_tags) if diagram_node_label_tags else None
    depth = int(diagram_depth or 3)
    depth_tenancy = int(diagram_depth_tenancy or depth)
    depth_network = int(diagram_depth_network or depth)
    depth_workload = int(diagram_depth_workload or depth)
    depth_consolidated = int(diagram_depth_consolidated or depth)
    out: List[Path] = []
    summary = _ensure_diagram_summary(summary)
    if enable_tenancy:
        out.append(_write_tenancy_view(outdir, nodes, edges, depth=depth_tenancy, summary=summary))
    if enable_network:
        out.extend(_write_network_views(outdir, nodes, edges, depth=depth_network, summary=summary))
        out.extend(_write_drg_hub_views(outdir, nodes, edges, summary=summary))
    if enable_workload:
        out.extend(_write_workload_views(outdir, nodes, edges, depth=depth_workload, summary=summary))
    if enable_consolidated:
        # Consolidated, end-user-friendly artifact: one Mermaid diagram that contains all the views.
        out.extend(
            _write_consolidated_flowchart(
                outdir,
                nodes,
                edges,
                depth=depth_consolidated,
                summary=summary,
            )
        )
        # Landing Zone architecture diagram: OCI reference architecture style.
        lz_path = _write_landing_zone_diagram(outdir, nodes, edges, summary=summary)
        if lz_path:
            out.append(lz_path)
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

def _arch_safe_label(value: str, *, default: str = "Unknown") -> str:
    safe = _compact_label(value, max_len=64)
    safe = re.sub(r"\(n=[^)]*\)", "", safe).strip()
    if not safe:
        return default
    if safe.startswith("ocid1") or "ocid1" in safe:
        return "Redacted"
    return safe

def _arch_compartment_label(label: str) -> str:
    safe = _compact_label(label, max_len=64)
    safe = re.sub(r"\(n=[^)]*\)", "", safe).strip()
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

def _concept_lane_labels(concepts: Sequence[Any], *, lane: str, limit: int) -> Tuple[List[str], int]:
    items = [c for c in concepts if c.lane == lane]
    items.sort(key=lambda c: (-c.count, c.label))
    labels = [c.label for c in items]
    top = labels[:limit]
    rest = max(0, len(labels) - len(top))
    return top, rest

def _concepts_for_scope(
    concepts: Sequence[Any],
    *,
    lane: str,
    placement: Optional[str] = None,
    compartment_id: Optional[str] = None,
    compartment_ids: Optional[Set[str]] = None,
    vcn_name: Optional[str] = None,
) -> List[Any]:
    normalized_vcn = _normalize_concept_label(vcn_name) if vcn_name else None
    items: List[Any] = []
    for c in concepts:
        if c.lane != lane:
            continue
        if placement and c.placement != placement:
            continue
        if compartment_id and c.compartment_id != compartment_id:
            continue
        if compartment_ids and c.compartment_id not in compartment_ids:
            continue
        # Exclude only if the concept has explicit VCN names AND this VCN is not among them.
        # If vcn_names is empty (VCN resolution failed), keep the concept so VCN-scoped
        # architecture diagrams don't appear empty.
        if normalized_vcn and c.vcn_names and normalized_vcn not in c.vcn_names:
            continue
        items.append(c)
    items.sort(key=lambda c: (-c.count, c.label))
    return items

def _security_overlay_items(
    concepts: Sequence[Any],
    *,
    scope: str,
    compartment_id: Optional[str] = None,
    compartment_ids: Optional[Set[str]] = None,
    vcn_name: Optional[str] = None,
) -> List[Any]:
    normalized_vcn = _normalize_concept_label(vcn_name) if vcn_name else None
    items: List[Any] = []
    for c in concepts:
        if getattr(c, "security_scope", None) != scope:
            continue
        if scope != "vcn" and compartment_id and getattr(c, "compartment_id", None) != compartment_id:
            continue
        if scope != "vcn" and compartment_ids and getattr(c, "compartment_id", None) not in compartment_ids:
            continue
        if normalized_vcn and normalized_vcn not in getattr(c, "vcn_names", ()):
            continue
        items.append(c)
    items.sort(key=lambda c: (-getattr(c, "count", 0), getattr(c, "label", "")))
    return items

def _has_security_overlay(concepts: Sequence[Any]) -> bool:
    return any(getattr(c, "security_scope", None) for c in concepts)

def _normalize_concept_label(value: Optional[str]) -> str:
    if not value:
        return ""
    cleaned = str(value)
    if "ocid1" in cleaned:
        cleaned = "Redacted"
    cleaned = re.sub(r"\(n=[^)]*\)", "", cleaned)
    cleaned = re.sub(r"\d{4}-\d{2}-\d{2}(?:[T _-]?\d{2}[:_-]?\d{2}[:_-]?\d{2})?", "", cleaned)
    cleaned = re.sub(r"\d{8,14}", "", cleaned)
    cleaned = re.sub(r"[-_ ]{2,}", " ", cleaned)
    return cleaned.strip(" -_") or str(value)

def _arch_short_hash(values: Sequence[str]) -> str:
    digest = hashlib.sha1()
    for value in values:
        digest.update(value.encode("utf-8", errors="ignore"))
        digest.update(b"|")
    return digest.hexdigest()[:8]

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
        lines.append(f"%% - {_redact_ocids_for_label(part)}")
    notice_id = _mermaid_id(f"split:index:{path.name}")
    lines.append(f"{notice_id}[\"Split index: {len(part_paths)} diagram(s).\"]")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path

def _chunked(items: Sequence[str], size: int) -> Iterable[Sequence[str]]:
    if size <= 0:
        size = 1
    for idx in range(0, len(items), size):
        yield items[idx : idx + size]

def _arch_mermaid_label(value: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        return "Unknown"
    # text = _redact_ocids_for_label(text)
    return text.replace('"', "'")

def _arch_mermaid_container_desc(placement: str) -> str:
    if placement == "in_vcn":
        return "In VCN"
    if placement == "out_of_vcn":
        return "Tenancy Service"
    if placement == "edge":
        return "Edge Connectivity"
    return "Service"

def _arch_overlay_concepts(
    concepts: Sequence[Any],
    *,
    scope: str,
    compartment_id: Optional[str] = None,
    vcn_name: Optional[str] = None,
) -> List[Any]:
    items = [c for c in concepts if c.security_scope == scope]
    if compartment_id:
        items = [c for c in items if c.compartment_id == compartment_id]
    if vcn_name:
        normalized_vcn = _normalize_concept_label(vcn_name)
        items = [c for c in items if normalized_vcn in c.vcn_names]
    items.sort(key=lambda c: (-c.count, c.label))
    return items

def _render_arch_mermaid_c4_lanes(
    lines: List[str],
    *,
    make_id: Callable[[str], str],
    concepts: Sequence[Any],
    placement: str,
    compartment_id: Optional[str] = None,
    vcn_name: Optional[str] = None,
    indent: str = "    ",
) -> None:
    for lane in ARCH_LANE_ORDER:
        lane_items = _concepts_for_scope(
            concepts,
            lane=lane,
            placement=placement,
            compartment_id=compartment_id,
            vcn_name=vcn_name,
        )
        if not lane_items:
            continue
        # Merge concepts with the same label (can appear once per sub-compartment when
        # no compartment_id filter is applied at the tenancy level).
        _label_map: Dict[str, Tuple[Any, int]] = {}
        for _c in lane_items:
            if _c.label in _label_map:
                _first, _total = _label_map[_c.label]
                _label_map[_c.label] = (_first, _total + _c.count)
            else:
                _label_map[_c.label] = (_c, _c.count)
        merged_items = sorted(_label_map.values(), key=lambda x: (-x[1], x[0].label))
        lane_id = make_id(f"lane:{placement}:{lane}:{compartment_id}:{vcn_name}")
        lines.append(f'{indent}Container_Boundary({lane_id}, "{_lane_label(lane)}") {{')
        for concept, total_count in merged_items[:ARCH_LANE_TOP_N]:
            node_id = make_id(f"concept:{concept.concept_id}")
            base_label = _arch_mermaid_label(concept.label)
            label = f"{base_label} ({total_count})" if total_count > 1 else base_label
            desc = _arch_mermaid_container_desc(concept.placement)
            lines.append(
                f'{indent}  Container({node_id}, "{label}", "{_lane_label(lane)}", "{desc}")'
            )
        if len(merged_items) > ARCH_LANE_TOP_N:
            other_id = make_id(f"concept:{lane}:other:{placement}:{compartment_id}:{vcn_name}")
            desc = _arch_mermaid_container_desc(placement)
            lines.append(
                f'{indent}  Container({other_id}, "Other Services", "{_lane_label(lane)}", "{desc}")'
            )
        lines.append(f"{indent}}}")

def _arch_c4_has_lanes(
    *,
    concepts: Sequence[Any],
    placement: str,
    compartment_id: Optional[str] = None,
    vcn_name: Optional[str] = None,
) -> bool:
    for lane in ARCH_LANE_ORDER:
        lane_items = _concepts_for_scope(
            concepts,
            lane=lane,
            placement=placement,
            compartment_id=compartment_id,
            vcn_name=vcn_name,
        )
        if lane_items:
            return True
    return False

def _append_c4_placeholder(
    lines: List[str],
    *,
    make_id: Callable[[str], str],
    key: str,
    indent: str,
    label: str = "No scoped services",
) -> None:
    placeholder_id = make_id(f"placeholder:{key}")
    lines.append(f'{indent}Container({placeholder_id}, "{label}", "Other", "Service")')

def _render_arch_mermaid_flowchart_lanes(
    lines: List[str],
    *,
    make_id: Callable[[str], str],
    concepts: Sequence[Any],
    placement: str,
    compartment_id: Optional[str] = None,
    vcn_name: Optional[str] = None,
    indent: str = "    ",
) -> None:
    for lane in ARCH_LANE_ORDER:
        lane_items = _concepts_for_scope(
            concepts,
            lane=lane,
            placement=placement,
            compartment_id=compartment_id,
            vcn_name=vcn_name,
        )
        if not lane_items:
            continue
        lane_id = make_id(f"lane:{placement}:{lane}:{compartment_id}:{vcn_name}")
        lines.append(f'{indent}subgraph {lane_id}["{_lane_label(lane)}"]')
        for concept in lane_items[:ARCH_LANE_TOP_N]:
            node_id = make_id(f"concept:{concept.concept_id}")
            label = _arch_mermaid_label(concept.label)
            lines.append(f'{indent}  {node_id}["{label}"]')
        if len(lane_items) > ARCH_LANE_TOP_N:
            other_id = make_id(f"concept:{lane}:other:{placement}:{compartment_id}:{vcn_name}")
            lines.append(f'{indent}  {other_id}["Other Services"]')
        lines.append(f"{indent}end")

def _write_architecture_mermaid_tenancy(
    outdir: Path,
    *,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
) -> Path:
    arch_dir = outdir / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    path = arch_dir / "diagram.arch.tenancy.mmd"
    lines: List[str] = ["C4Container", "title Tenancy Architecture (Mermaid)"]
    _insert_scope_view_comments(lines, scope="architecture:tenancy", view="c4-container")

    make_id = _unique_mermaid_id_factory()
    tenancy_label = _arch_mermaid_label(_tenancy_label(nodes))
    lines.append(f'System_Boundary({make_id("tenancy")}, "{tenancy_label}") {{')

    comp_groups = _group_nodes_by_level1_compartment(nodes)
    top_comp_groups, _other_comp_groups = _arch_select_top_groups(
        comp_groups,
        limit=ARCH_TENANCY_TOP_N,
    )
    node_by_id = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}
    alias_by_comp = _compartment_alias_map(nodes)
    for comp_id, comp_nodes in top_comp_groups:
        comp_label = _compartment_label_by_id(comp_id, node_by_id=node_by_id, alias_by_id=alias_by_comp)
        comp_label = _arch_mermaid_label(_tenancy_safe_label("", comp_label))
        comp_boundary = make_id(f"compartment:{comp_id}")
        lines.append(f'  System_Boundary({comp_boundary}, "{comp_label}") {{')
        concepts = build_scope_concepts(nodes=nodes, edges=edges, scope_nodes=comp_nodes)
        comp_has_content = False

        vcn_groups = _group_nodes_by_vcn(comp_nodes, edges)
        top_vcns, _other_vcns = _arch_select_top_groups(vcn_groups, limit=ARCH_MAX_VCNS_PER_COMPARTMENT)
        for vcn_id, vcn_nodes in top_vcns:
            if vcn_id == "NO_VCN":
                continue
            vcn_label = "VCN"
            for n in vcn_nodes:
                if _is_node_type(n, "Vcn") and n.get("name"):
                    vcn_label = str(n.get("name") or "")
                    break
            vcn_label = _arch_mermaid_label(_normalize_concept_label(_compact_label(vcn_label, max_len=64)))
            vcn_boundary = make_id(f"vcn:{vcn_id}")
            # No compartment_id filter for in_vcn/edge — VCN resources span multiple sub-compartments
            vcn_has_lanes = _arch_c4_has_lanes(
                concepts=concepts,
                placement="in_vcn",
                vcn_name=vcn_label,
            ) or _arch_c4_has_lanes(
                concepts=concepts,
                placement="edge",
                vcn_name=vcn_label,
            )
            overlay_items = _arch_overlay_concepts(
                concepts,
                scope="vcn",
                vcn_name=vcn_label,
            )
            lines.append(f'    Container_Boundary({vcn_boundary}, "VCN: {vcn_label}") {{')
            if vcn_has_lanes:
                _render_arch_mermaid_c4_lanes(
                    lines,
                    make_id=make_id,
                    concepts=concepts,
                    placement="in_vcn",
                    vcn_name=vcn_label,
                    indent="      ",
                )
                _render_arch_mermaid_c4_lanes(
                    lines,
                    make_id=make_id,
                    concepts=concepts,
                    placement="edge",
                    vcn_name=vcn_label,
                    indent="      ",
                )
            if overlay_items:
                overlay_id = make_id(f"overlay:vcn:{vcn_label}")
                lines.append(f'      Container_Boundary({overlay_id}, "IAM / Security Overlay") {{')
                for concept in overlay_items[:ARCH_LANE_TOP_N]:
                    node_id = make_id(f"overlay:{concept.concept_id}")
                    label = _arch_mermaid_label(concept.label)
                    lines.append(
                        f'        Container({node_id}, "{label}", "Security", "Security Overlay")'
                    )
                lines.append("      }")
            if not vcn_has_lanes and not overlay_items:
                _append_c4_placeholder(
                    lines,
                    make_id=make_id,
                    key=f"vcn:{vcn_label}",
                    indent="      ",
                )
            lines.append("    }")
            comp_has_content = True

        if _arch_c4_has_lanes(concepts=concepts, placement="out_of_vcn"):
            _render_arch_mermaid_c4_lanes(
                lines,
                make_id=make_id,
                concepts=concepts,
                placement="out_of_vcn",
                indent="    ",
            )
            comp_has_content = True
        if _arch_c4_has_lanes(concepts=concepts, placement="unknown"):
            _render_arch_mermaid_c4_lanes(
                lines,
                make_id=make_id,
                concepts=concepts,
                placement="unknown",
                indent="    ",
            )
            comp_has_content = True
        overlay_items = _arch_overlay_concepts(concepts, scope="compartment")
        if overlay_items:
            overlay_id = make_id(f"overlay:compartment:{comp_id}")
            lines.append(f'    Container_Boundary({overlay_id}, "IAM / Security Overlay") {{')
            for concept in overlay_items[:ARCH_LANE_TOP_N]:
                node_id = make_id(f"overlay:{concept.concept_id}")
                label = _arch_mermaid_label(concept.label)
                lines.append(
                    f'      Container({node_id}, "{label}", "Security", "Security Overlay")'
                )
            lines.append("    }")
            comp_has_content = True
        if not comp_has_content:
            _append_c4_placeholder(
                lines,
                make_id=make_id,
                key=f"compartment:{comp_id}",
                indent="    ",
            )
        lines.append("  }")

    tenancy_overlay = _arch_overlay_concepts(build_scope_concepts(nodes=nodes, edges=edges, scope_nodes=nodes), scope="tenancy")
    if tenancy_overlay:
        overlay_id = make_id("overlay:tenancy")
        lines.append(f'  Container_Boundary({overlay_id}, "IAM / Security Overlay") {{')
        for concept in tenancy_overlay[:ARCH_LANE_TOP_N]:
            node_id = make_id(f"overlay:{concept.concept_id}")
            label = _arch_mermaid_label(concept.label)
            lines.append(f'    Container({node_id}, "{label}", "Security", "Security Overlay")')
        lines.append("  }")

    lines.append("}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path

def _write_architecture_mermaid_vcn(
    outdir: Path,
    *,
    vcn_label: str,
    vcn_nodes: Sequence[Node],
    vcn_edges: Sequence[Edge],
    suffix: Optional[str] = None,
) -> Path:
    arch_dir = outdir / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(vcn_label)
    suffix_label = f".{suffix}" if suffix else ""
    path = arch_dir / f"diagram.arch.vcn.{slug}{suffix_label}.mmd"
    lines: List[str] = [
        "C4Container",
        f"title VCN Architecture: {vcn_label} (Mermaid)",
    ]
    _insert_scope_view_comments(lines, scope=f"architecture:vcn:{vcn_label}", view="c4-container")
    make_id = _unique_mermaid_id_factory()

    node_by_id = {str(n.get("nodeId") or ""): n for n in vcn_nodes if n.get("nodeId")}
    alias_by_comp = _compartment_alias_map(vcn_nodes)
    all_comp_ids = {str(n.get("compartmentId") or "") for n in vcn_nodes if n.get("compartmentId")}
    all_comp_ids.discard("")
    # Use the VCN node's own compartment for the boundary label; fall back to alphabetical first.
    vcn_comp_id = next(
        (str(n.get("compartmentId") or "") for n in vcn_nodes if _is_node_type(n, "Vcn")),
        sorted(all_comp_ids)[0] if all_comp_ids else "",
    )
    tenancy_label = _arch_mermaid_label(_tenancy_label(vcn_nodes))
    comp_label = _compartment_label_by_id(vcn_comp_id, node_by_id=node_by_id, alias_by_id=alias_by_comp)
    comp_label = _arch_mermaid_label(_tenancy_safe_label("", comp_label))
    lines.append(f'System_Boundary({make_id("tenancy")}, "{tenancy_label}") {{')
    comp_boundary = make_id(f"compartment:{vcn_comp_id}")
    lines.append(f'  System_Boundary({comp_boundary}, "{comp_label}") {{')
    concepts = build_scope_concepts(nodes=vcn_nodes, edges=vcn_edges, scope_nodes=vcn_nodes)
    comp_has_content = False
    vcn_boundary = make_id(f"vcn:{vcn_comp_id}:{vcn_label}")
    # For in_vcn/edge placements do NOT restrict by compartment — resources using this VCN
    # may live in different compartments (e.g., App/DB compartments vs. Network compartment).
    # The vcn_name filter is sufficient to scope the results to this VCN.
    vcn_has_lanes = _arch_c4_has_lanes(
        concepts=concepts,
        placement="in_vcn",
        vcn_name=vcn_label,
    ) or _arch_c4_has_lanes(
        concepts=concepts,
        placement="edge",
        vcn_name=vcn_label,
    )
    overlay_items = _arch_overlay_concepts(
        concepts,
        scope="vcn",
        vcn_name=vcn_label,
    )
    lines.append(f'    Container_Boundary({vcn_boundary}, "VCN: {vcn_label}") {{')
    if vcn_has_lanes:
        _render_arch_mermaid_c4_lanes(
            lines,
            make_id=make_id,
            concepts=concepts,
            placement="in_vcn",
            vcn_name=vcn_label,
            indent="      ",
        )
        _render_arch_mermaid_c4_lanes(
            lines,
            make_id=make_id,
            concepts=concepts,
            placement="edge",
            vcn_name=vcn_label,
            indent="      ",
        )
    if overlay_items:
        overlay_id = make_id(f"overlay:vcn:{vcn_comp_id}:{vcn_label}")
        lines.append(f'      Container_Boundary({overlay_id}, "IAM / Security Overlay") {{')
        for concept in overlay_items[:ARCH_LANE_TOP_N]:
            node_id = make_id(f"overlay:{concept.concept_id}")
            label = _arch_mermaid_label(concept.label)
            lines.append(
                f'        Container({node_id}, "{label}", "Security", "Security Overlay")'
            )
        lines.append("      }")
    if not vcn_has_lanes and not overlay_items:
        _append_c4_placeholder(
            lines,
            make_id=make_id,
            key=f"vcn:{vcn_comp_id}:{vcn_label}",
            indent="      ",
        )
    lines.append("    }")
    comp_has_content = True
    if _arch_c4_has_lanes(concepts=concepts, placement="out_of_vcn", compartment_id=vcn_comp_id):
        _render_arch_mermaid_c4_lanes(
            lines,
            make_id=make_id,
            concepts=concepts,
            placement="out_of_vcn",
            compartment_id=vcn_comp_id,
            indent="    ",
        )
        comp_has_content = True
    if _arch_c4_has_lanes(concepts=concepts, placement="unknown", compartment_id=vcn_comp_id):
        _render_arch_mermaid_c4_lanes(
            lines,
            make_id=make_id,
            concepts=concepts,
            placement="unknown",
            compartment_id=vcn_comp_id,
            indent="    ",
        )
        comp_has_content = True
    overlay_items = _arch_overlay_concepts(concepts, scope="compartment", compartment_id=vcn_comp_id)
    if overlay_items:
        overlay_id = make_id(f"overlay:compartment:{vcn_comp_id}")
        lines.append(f'    Container_Boundary({overlay_id}, "IAM / Security Overlay") {{')
        for concept in overlay_items[:ARCH_LANE_TOP_N]:
            node_id = make_id(f"overlay:{concept.concept_id}")
            label = _arch_mermaid_label(concept.label)
            lines.append(
                f'      Container({node_id}, "{label}", "Security", "Security Overlay")'
            )
        lines.append("    }")
        comp_has_content = True
    if not comp_has_content:
        _append_c4_placeholder(
            lines,
            make_id=make_id,
            key=f"compartment:{vcn_comp_id}",
            indent="    ",
        )
    lines.append("  }")
    lines.append("}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path

def _write_architecture_mermaid_workload(
    outdir: Path,
    *,
    workload: str,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    workload_nodes: Sequence[Node],
    suffix: Optional[str] = None,
) -> Path:
    arch_dir = outdir / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(workload)
    suffix_label = f".{suffix}" if suffix else ""
    path = arch_dir / f"diagram.arch.workload.{slug}{suffix_label}.mmd"
    lines: List[str] = [
        "C4Container",
        f"title Workload Architecture: {workload} (Mermaid)",
    ]
    _insert_scope_view_comments(lines, scope=f"architecture:workload:{workload}", view="c4-container")
    make_id = _unique_mermaid_id_factory()

    tenancy_label = _arch_mermaid_label(_tenancy_label(nodes))
    lines.append(f'System_Boundary({make_id("tenancy")}, "{tenancy_label}") {{')
    context = build_workload_context(nodes=nodes, edges=edges, workload_nodes=workload_nodes)
    concepts = build_workload_concepts(nodes=nodes, edges=edges, workload_nodes=workload_nodes)
    node_by_id = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}
    alias_by_comp = _compartment_alias_map(nodes)

    for comp_id in context.compartment_ids:
        comp_label = _compartment_label_by_id(comp_id, node_by_id=node_by_id, alias_by_id=alias_by_comp)
        comp_label = _arch_mermaid_label(_tenancy_safe_label("", comp_label))
        comp_boundary = make_id(f"compartment:{comp_id}")
        lines.append(f'  System_Boundary({comp_boundary}, "{comp_label}") {{')
        comp_has_content = False
        vcns = context.vcn_names_by_compartment.get(comp_id) or ()
        for vcn_name in vcns:
            vcn_boundary = make_id(f"vcn:{comp_id}:{vcn_name}")
            vcn_has_lanes = _arch_c4_has_lanes(
                concepts=concepts,
                placement="in_vcn",
                compartment_id=comp_id,
                vcn_name=vcn_name,
            ) or _arch_c4_has_lanes(
                concepts=concepts,
                placement="edge",
                compartment_id=comp_id,
                vcn_name=vcn_name,
            )
            overlay_items = _arch_overlay_concepts(
                concepts,
                scope="vcn",
                compartment_id=comp_id,
                vcn_name=vcn_name,
            )
            lines.append(f'    Container_Boundary({vcn_boundary}, "VCN: {vcn_name}") {{')
            if vcn_has_lanes:
                _render_arch_mermaid_c4_lanes(
                    lines,
                    make_id=make_id,
                    concepts=concepts,
                    placement="in_vcn",
                    compartment_id=comp_id,
                    vcn_name=vcn_name,
                    indent="      ",
                )
                _render_arch_mermaid_c4_lanes(
                    lines,
                    make_id=make_id,
                    concepts=concepts,
                    placement="edge",
                    compartment_id=comp_id,
                    vcn_name=vcn_name,
                    indent="      ",
                )
            if overlay_items:
                overlay_id = make_id(f"overlay:vcn:{comp_id}:{vcn_name}")
                lines.append(f'      Container_Boundary({overlay_id}, "IAM / Security Overlay") {{')
                for concept in overlay_items[:ARCH_LANE_TOP_N]:
                    node_id = make_id(f"overlay:{concept.concept_id}")
                    label = _arch_mermaid_label(concept.label)
                    lines.append(
                        f'        Container({node_id}, "{label}", "Security", "Security Overlay")'
                    )
                lines.append("      }")
            if not vcn_has_lanes and not overlay_items:
                _append_c4_placeholder(
                    lines,
                    make_id=make_id,
                    key=f"vcn:{comp_id}:{vcn_name}",
                    indent="      ",
                )
            lines.append("    }")
            comp_has_content = True

        if _arch_c4_has_lanes(concepts=concepts, placement="out_of_vcn", compartment_id=comp_id):
            _render_arch_mermaid_c4_lanes(
                lines,
                make_id=make_id,
                concepts=concepts,
                placement="out_of_vcn",
                compartment_id=comp_id,
                indent="    ",
            )
            comp_has_content = True
        if _arch_c4_has_lanes(concepts=concepts, placement="unknown", compartment_id=comp_id):
            _render_arch_mermaid_c4_lanes(
                lines,
                make_id=make_id,
                concepts=concepts,
                placement="unknown",
                compartment_id=comp_id,
                indent="    ",
            )
            comp_has_content = True
        overlay_items = _arch_overlay_concepts(concepts, scope="compartment", compartment_id=comp_id)
        if overlay_items:
            overlay_id = make_id(f"overlay:compartment:{comp_id}")
            lines.append(f'    Container_Boundary({overlay_id}, "IAM / Security Overlay") {{')
            for concept in overlay_items[:ARCH_LANE_TOP_N]:
                node_id = make_id(f"overlay:{concept.concept_id}")
                label = _arch_mermaid_label(concept.label)
                lines.append(
                    f'      Container({node_id}, "{label}", "Security", "Security Overlay")'
                )
            lines.append("    }")
            comp_has_content = True
        if not comp_has_content:
            _append_c4_placeholder(
                lines,
                make_id=make_id,
                key=f"compartment:{comp_id}",
                indent="    ",
            )
        lines.append("  }")

    tenancy_overlay = _arch_overlay_concepts(concepts, scope="tenancy")
    if tenancy_overlay:
        overlay_id = make_id("overlay:tenancy")
        lines.append(f'  Container_Boundary({overlay_id}, "IAM / Security Overlay") {{')
        for concept in tenancy_overlay[:ARCH_LANE_TOP_N]:
            node_id = make_id(f"overlay:{concept.concept_id}")
            label = _arch_mermaid_label(concept.label)
            lines.append(f'    Container({node_id}, "{label}", "Security", "Security Overlay")')
        lines.append("  }")

    lines.append("}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path

def _write_architecture_mermaid_compartment(
    outdir: Path,
    *,
    compartment_label: str,
    comp_nodes: Sequence[Node],
    comp_edges: Sequence[Edge],
) -> Path:
    arch_dir = outdir / "architecture"
    arch_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(compartment_label)
    path = arch_dir / f"diagram.arch.compartment.{slug}.mmd"
    lines: List[str] = [
        "C4Container",
        f"title Compartment Architecture: {compartment_label} (Mermaid)",
    ]
    _insert_scope_view_comments(lines, scope=f"architecture:compartment:{compartment_label}", view="c4-container")
    make_id = _unique_mermaid_id_factory()

    tenancy_label = _arch_mermaid_label(_tenancy_label(comp_nodes))
    comp_label = _arch_mermaid_label(_tenancy_safe_label("", compartment_label))
    concepts = build_scope_concepts(nodes=comp_nodes, edges=comp_edges, scope_nodes=comp_nodes)
    comp_ids = [str(n.get("compartmentId") or "") for n in comp_nodes if n.get("compartmentId")]
    comp_id = sorted({cid for cid in comp_ids if cid})[0] if comp_ids else ""
    lines.append(f'System_Boundary({make_id("tenancy")}, "{tenancy_label}") {{')
    comp_boundary = make_id(f"compartment:{comp_id or compartment_label}")
    lines.append(f'  System_Boundary({comp_boundary}, "{comp_label}") {{')
    comp_has_content = False
    vcn_groups = _group_nodes_by_vcn(comp_nodes, comp_edges)
    top_vcns, _other_vcns = _arch_select_top_groups(vcn_groups, limit=ARCH_MAX_VCNS_PER_COMPARTMENT)
    for vcn_id, vcn_nodes in top_vcns:
        vcn_label = "VCN"
        for n in vcn_nodes:
            if _is_node_type(n, "Vcn") and n.get("name"):
                vcn_label = str(n.get("name") or "")
                break
        vcn_label = _arch_mermaid_label(_normalize_concept_label(_compact_label(vcn_label, max_len=64)))
        vcn_boundary = make_id(f"vcn:{vcn_id}")
        vcn_has_lanes = _arch_c4_has_lanes(
            concepts=concepts,
            placement="in_vcn",
            compartment_id=comp_id,
            vcn_name=vcn_label,
        ) or _arch_c4_has_lanes(
            concepts=concepts,
            placement="edge",
            compartment_id=comp_id,
            vcn_name=vcn_label,
        )
        overlay_items = _arch_overlay_concepts(
            concepts,
            scope="vcn",
            compartment_id=comp_id,
            vcn_name=vcn_label,
        )
        lines.append(f'    Container_Boundary({vcn_boundary}, "VCN: {vcn_label}") {{')
        if vcn_has_lanes:
            _render_arch_mermaid_c4_lanes(
                lines,
                make_id=make_id,
                concepts=concepts,
                placement="in_vcn",
                compartment_id=comp_id,
                vcn_name=vcn_label,
                indent="      ",
            )
            _render_arch_mermaid_c4_lanes(
                lines,
                make_id=make_id,
                concepts=concepts,
                placement="edge",
                compartment_id=comp_id,
                vcn_name=vcn_label,
                indent="      ",
            )
        if overlay_items:
            overlay_id = make_id(f"overlay:vcn:{vcn_id}")
            lines.append(f'      Container_Boundary({overlay_id}, "IAM / Security Overlay") {{')
            for concept in overlay_items[:ARCH_LANE_TOP_N]:
                node_id = make_id(f"overlay:{concept.concept_id}")
                label = _arch_mermaid_label(concept.label)
                lines.append(
                    f'        Container({node_id}, "{label}", "Security", "Security Overlay")'
                )
            lines.append("      }")
        if not vcn_has_lanes and not overlay_items:
            _append_c4_placeholder(
                lines,
                make_id=make_id,
                key=f"vcn:{vcn_id}",
                indent="      ",
            )
        lines.append("    }")
        comp_has_content = True
    if _arch_c4_has_lanes(concepts=concepts, placement="out_of_vcn", compartment_id=comp_id):
        _render_arch_mermaid_c4_lanes(
            lines,
            make_id=make_id,
            concepts=concepts,
            placement="out_of_vcn",
            compartment_id=comp_id,
            indent="    ",
        )
        comp_has_content = True
    if _arch_c4_has_lanes(concepts=concepts, placement="unknown", compartment_id=comp_id):
        _render_arch_mermaid_c4_lanes(
            lines,
            make_id=make_id,
            concepts=concepts,
            placement="unknown",
            compartment_id=comp_id,
            indent="    ",
        )
        comp_has_content = True
    overlay_items = _arch_overlay_concepts(
        concepts,
        scope="compartment",
        compartment_id=comp_id,
    )
    if overlay_items:
        overlay_id = make_id(f"overlay:compartment:{comp_id or compartment_label}")
        lines.append(f'    Container_Boundary({overlay_id}, "IAM / Security Overlay") {{')
        for concept in overlay_items[:ARCH_LANE_TOP_N]:
            node_id = make_id(f"overlay:{concept.concept_id}")
            label = _arch_mermaid_label(concept.label)
            lines.append(
                f'      Container({node_id}, "{label}", "Security", "Security Overlay")'
            )
        lines.append("    }")
        comp_has_content = True
    if not comp_has_content:
        _append_c4_placeholder(
            lines,
            make_id=make_id,
            key=f"compartment:{comp_id or compartment_label}",
            indent="    ",
        )
    lines.append("  }")
    lines.append("}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path

def write_architecture_diagrams(
    outdir: Path,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    *,
    summary: Optional[DiagramSummary] = None,
) -> List[Path]:
    arch_dir = outdir / "architecture"
    if arch_dir.exists():
        for path in arch_dir.glob("diagram.arch.*"):
            if path.is_file():
                path.unlink()
    else:
        arch_dir.mkdir(parents=True, exist_ok=True)

    filtered_nodes = [n for n in nodes if str(n.get("nodeType") or "") not in _ARCH_FILTER_NODETYPES]
    filtered_edges = _filter_edges_for_nodes(
        edges,
        {str(n.get("nodeId") or "") for n in filtered_nodes if n.get("nodeId")},
    )

    out_paths: List[Path] = []
    summary = _ensure_diagram_summary(summary)
    out_paths.append(
        _write_architecture_mermaid_tenancy(outdir, nodes=filtered_nodes, edges=filtered_edges)
    )

    comp_groups = _group_nodes_by_level1_compartment(filtered_nodes)
    if comp_groups:
        node_by_id = {str(n.get("nodeId") or ""): n for n in filtered_nodes if n.get("nodeId")}
        alias_by_comp = _compartment_alias_map(filtered_nodes)
        for comp_id in sorted(comp_groups.keys()):
            comp_nodes = comp_groups.get(comp_id) or []
            if not comp_nodes:
                continue
            label = _compartment_label_by_id(comp_id, node_by_id=node_by_id, alias_by_id=alias_by_comp)
            label = _tenancy_safe_label("", label)
            comp_edges = _filter_edges_for_nodes(
                filtered_edges,
                {str(n.get("nodeId") or "") for n in comp_nodes if n.get("nodeId")},
            )
            out_paths.append(
                _write_architecture_mermaid_compartment(
                    outdir,
                    compartment_label=label,
                    comp_nodes=comp_nodes,
                    comp_edges=comp_edges,
                )
            )

    vcn_groups = {
        vcn_id: group_nodes
        for vcn_id, group_nodes in _group_nodes_by_vcn(filtered_nodes, filtered_edges).items()
        if vcn_id != "NO_VCN"
    }
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
        out_paths.append(
            _write_architecture_mermaid_vcn(
                outdir,
                vcn_label=vcn_name,
                vcn_nodes=group_nodes,
                vcn_edges=vcn_edges,
                suffix=vcn_suffix,
            )
        )

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
        out_paths.append(
            _write_architecture_mermaid_workload(
                outdir,
                workload=wl_name,
                nodes=filtered_nodes,
                edges=filtered_edges,
                workload_nodes=wl_nodes,
                suffix=workload_suffix,
            )
        )
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

def _arch_vcn_group_map(nodes: Sequence[Node], edges: Sequence[Edge]) -> Dict[str, List[Dict[str, Any]]]:
    groups = _group_nodes_by_vcn(nodes, edges)
    mapping: Dict[str, List[Dict[str, Any]]] = {}
    for vcn_id, vcn_nodes in groups.items():
        if vcn_id == "NO_VCN":
            continue
        vcn_label = "VCN"
        for n in vcn_nodes:
            if _is_node_type(n, "Vcn") and n.get("name"):
                vcn_label = str(n.get("name") or "")
                break
        vcn_label = _normalize_concept_label(_compact_label(vcn_label, max_len=64) or "VCN")
        slug = _slugify(vcn_label)
        node_ids = {str(n.get("nodeId") or "") for n in vcn_nodes if n.get("nodeId")}
        vcn_edges = _filter_edges_for_nodes(edges, node_ids)
        vcn_suffix = _arch_short_hash([vcn_id] if vcn_id else sorted(node_ids))
        mapping.setdefault(slug, []).append(
            {
                "label": vcn_label,
                "nodes": vcn_nodes,
                "edges": vcn_edges,
                "suffix": vcn_suffix,
            }
        )
    return mapping

def _arch_workload_group_map(nodes: Sequence[Node]) -> Dict[str, List[Dict[str, Any]]]:
    workload_candidates = [n for n in nodes if n.get("nodeId")]
    wl_groups = {k: list(v) for k, v in group_workload_candidates(workload_candidates).items()}
    mapping: Dict[str, List[Dict[str, Any]]] = {}
    for wl_name, wl_nodes in wl_groups.items():
        wl_label = _arch_safe_label(_compact_label(wl_name, max_len=64), default="Workload")
        slug = _slugify(wl_label)
        node_ids = sorted({str(n.get("nodeId") or "") for n in wl_nodes if n.get("nodeId")})
        workload_suffix = _arch_short_hash([wl_name] + node_ids)
        mapping.setdefault(slug, []).append(
            {
                "label": wl_label,
                "nodes": wl_nodes,
                "suffix": workload_suffix,
            }
        )
    return mapping

def validate_architecture_diagrams(
    outdir: Path,
    *,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
) -> List[DiagramValidationIssue]:
    arch_dir = outdir / "architecture"
    issues: List[DiagramValidationIssue] = []
    if not arch_dir.exists():
        issues.append(
            DiagramValidationIssue(
                file=str(arch_dir),
                rule_id="ARCH_OUTPUT_MISSING",
                description="Architecture diagrams directory is missing.",
            )
        )
        return issues

    mmd_paths = sorted([p for p in arch_dir.glob("diagram.arch.*.mmd") if p.is_file()])
    if not mmd_paths:
        issues.append(
            DiagramValidationIssue(
                file=str(arch_dir),
                rule_id="ARCH_OUTPUT_MISSING",
                description="No curated architecture Mermaid diagrams found for validation.",
            )
        )
        return issues

    filtered_nodes = [n for n in nodes if str(n.get("nodeType") or "") not in _ARCH_FILTER_NODETYPES]
    filtered_edges = _filter_edges_for_nodes(
        edges,
        {str(n.get("nodeId") or "") for n in filtered_nodes if n.get("nodeId")},
    )
    workload_map = _arch_workload_group_map(filtered_nodes)
    lane_labels = [
        _LANE_LABELS[lane]
        for lane in ARCH_LANE_ORDER
        if lane in _LANE_LABELS
    ]

    def _has_label(text: str, needle: str) -> bool:
        return needle in text

    def _extract_suffix(base: str) -> Tuple[str, str]:
        parts = base.split(".")
        if len(parts) > 1 and len(parts[-1]) == 8 and all(ch in "0123456789abcdef" for ch in parts[-1]):
            return ".".join(parts[:-1]), parts[-1]
        return base, ""

    for path in mmd_paths:
        text = path.read_text(encoding="utf-8")
        name = path.name
        file_label = str(path)

        if not _has_label(text, "Tenancy"):
            issues.append(
                DiagramValidationIssue(
                    file=file_label,
                    rule_id="ARCH_LABEL_TENANCY_MISSING",
                    description="Missing tenancy label in architecture Mermaid diagram.",
                )
            )
        if not _has_label(text, "Compartment:"):
            issues.append(
                DiagramValidationIssue(
                    file=file_label,
                    rule_id="ARCH_LABEL_COMPARTMENT_MISSING",
                    description="Missing compartment label in architecture Mermaid diagram.",
                )
            )

        if name == "diagram.arch.tenancy.mmd":
            if not any(label in text for label in lane_labels):
                issues.append(
                    DiagramValidationIssue(
                        file=file_label,
                        rule_id="ARCH_LANES_MISSING",
                        description="No lane labels found in architecture Mermaid diagram.",
                    )
                )
            continue

        if name.startswith("diagram.arch.vcn.") and name.endswith(".mmd"):
            if not _has_label(text, "VCN:"):
                issues.append(
                    DiagramValidationIssue(
                        file=file_label,
                        rule_id="ARCH_LABEL_VCN_MISSING",
                        description="Missing VCN label in architecture Mermaid diagram.",
                    )
                )
            continue

        if name.startswith("diagram.arch.compartment.") and name.endswith(".mmd"):
            if not _has_label(text, "VCN:") and any(_is_node_type(n, "Vcn") for n in filtered_nodes):
                issues.append(
                    DiagramValidationIssue(
                        file=file_label,
                        rule_id="ARCH_LABEL_VCN_MISSING",
                        description="Missing VCN label in architecture Mermaid diagram.",
                    )
                )
            continue

        if name.startswith("diagram.arch.workload.") and name.endswith(".mmd"):
            base = name[len("diagram.arch.workload.") : -len(".mmd")]
            slug, suffix = _extract_suffix(base)
            candidates = workload_map.get(slug) or []
            if suffix:
                candidates = [entry for entry in candidates if entry.get("suffix") == suffix]
            if candidates:
                entry = candidates[0]
                context = build_workload_context(
                    nodes=filtered_nodes,
                    edges=filtered_edges,
                    workload_nodes=entry["nodes"],
                )
                expects_vcn = any(context.vcn_names_by_compartment.values())
                if expects_vcn and not _has_label(text, "VCN:"):
                    issues.append(
                        DiagramValidationIssue(
                            file=file_label,
                            rule_id="ARCH_LABEL_VCN_MISSING",
                            description="Missing VCN label in architecture Mermaid diagram.",
                        )
                    )
            if not _has_label(text, "Workload Architecture:"):
                issues.append(
                    DiagramValidationIssue(
                        file=file_label,
                        rule_id="ARCH_LABEL_WORKLOAD_MISSING",
                        description="Missing workload title in architecture Mermaid diagram.",
                    )
                )

    issues.sort(key=lambda i: (i.file, i.rule_id, i.description))
    if issues:
        report_path = arch_dir / "diagram.validation.json"
        payload = [
            {"file": issue.file, "rule_id": issue.rule_id, "description": issue.description}
            for issue in issues
        ]
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        for issue in issues:
            LOG.warning(
                "Architecture diagram validation issue: %s | %s | %s",
                issue.file,
                issue.rule_id,
                issue.description,
            )
    return issues

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
        flow_direction="TD",
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
        safe_scope = _redact_ocids_for_label(_split_scope_label)
        lines.insert(insert_at, f"%% Split scope: {safe_scope}")
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
