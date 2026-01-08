from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .graph import Edge, Node


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


def _node_tags(node: Node) -> Mapping[str, Any]:
    tags = node.get("tags")
    return tags if isinstance(tags, Mapping) else {}


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
    if shape == "round":
        return f"  {node_id}(({safe}))"
    if shape == "db":
        return f"  {node_id}[({safe})]"
    if shape == "hex":
        return f"  {node_id}{{{{{safe}}}}}"
    return f'  {node_id}["{safe}"]'


def _render_edge(src: str, dst: str, label: str | None = None) -> str:
    if label:
        safe = str(label).replace('"', "'")
        return f"  {src} -->|{safe}| {dst}"
    return f"  {src} --> {dst}"


def _render_node_with_class(node_id: str, label: str, *, cls: str, shape: str = "rect") -> List[str]:
    return [_render_node(node_id, label, shape=shape), f"  class {node_id} {cls}"]


def _summarize_many(nodes: Sequence[Node], *, title: str, keep: int = 2) -> Tuple[List[Node], Optional[str]]:
    if len(nodes) <= keep + 1:
        return list(nodes), None
    kept = list(nodes[:keep])
    remaining = len(nodes) - keep
    return kept, f"{title}... and {remaining} more"


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


def _workload_keys_from_tags(node: Node) -> List[str]:
    tags = _node_tags(node)
    freeform = tags.get("freeformTags")
    defined = tags.get("definedTags")

    candidates: List[str] = []

    if isinstance(freeform, Mapping):
        for k in ("workload", "application", "app", "service", "domain", "project", "team"):
            v = freeform.get(k)
            if isinstance(v, str) and v.strip():
                candidates.append(v.strip())

    # definedTags is usually {namespace: {key: value}}
    if isinstance(defined, Mapping):
        for ns_val in defined.values():
            if not isinstance(ns_val, Mapping):
                continue
            for k in ("workload", "application", "app", "service", "domain", "project", "team"):
                v = ns_val.get(k)
                if isinstance(v, str) and v.strip():
                    candidates.append(v.strip())

    # Normalize to unique, stable order
    out: List[str] = []
    seen: Set[str] = set()
    for c in candidates:
        key = c.strip()
        if not key:
            continue
        if key.lower() in seen:
            continue
        seen.add(key.lower())
        out.append(key)
    return out


def _workload_keys_from_name(node: Node) -> List[str]:
    name = str(node.get("name") or "").strip()
    if not name:
        return []

    lowered = name.lower()

    # Explicit workload keywords.
    known: List[Tuple[str, str]] = [
        ("mediaflow", "MediaFlow"),
        ("streamdistributionchannel", "StreamDistributionChannel"),
        ("stream_distribution", "StreamDistributionChannel"),
        ("stream-distribution", "StreamDistributionChannel"),
        ("contentbucket", "ContentDelivery"),
        ("content-bucket", "ContentDelivery"),
    ]
    for needle, wl in known:
        if needle in lowered:
            return [wl]

    # Heuristic: common prefix token before separator.
    token = re.split(r"[-_.:/\\s]+", name)[0].strip()
    if token and len(token) >= 3 and not token.lower().startswith("ocid"):
        # Title-case the token to be human readable.
        return [token[:1].upper() + token[1:]]

    return []


def _infer_workload_keys(node: Node) -> List[str]:
    # Prefer explicit tags, then fallback to name heuristics.
    keys = _workload_keys_from_tags(node)
    if keys:
        return keys
    return _workload_keys_from_name(node)


def _derived_attachments(nodes: Sequence[Node]) -> List[_DerivedAttachment]:
    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}

    # Index VNICs to help attach instances -> subnet/vcn.
    vnic_meta_by_id: Dict[str, Mapping[str, Any]] = {}
    for n in nodes:
        if _is_node_type(n, "Vnic"):
            vnic_meta_by_id[str(n.get("nodeId") or "")] = _node_metadata(n)

    out: List[_DerivedAttachment] = []

    for n in nodes:
        ocid = str(n.get("nodeId") or "")
        if not ocid:
            continue

        meta = _node_metadata(n)

        vcn_id = _get_meta(meta, "vcn_id")
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

    # Group by compartmentId (or unknown).
    comps: Dict[str, List[Node]] = {}
    for n in shown_nodes:
        cid = str(n.get("compartmentId") or "")
        if not cid and _is_node_type(n, "Compartment"):
            cid = str(n.get("nodeId") or "")
        comps.setdefault(cid or "UNKNOWN", []).append(n)

    # Stable order.
    comp_ids = sorted(comps.keys())

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
            comps[cid],
            key=lambda n: (
                str(n.get("nodeCategory") or ""),
                str(n.get("nodeType") or ""),
                str(n.get("name") or ""),
            ),
        )
        # Cap the number of nodes per compartment to avoid unreadable diagrams.
        rendered = 0
        cap = 18
        for n in comp_nodes:
            # Skip the compartment node itself (boundary label already covers it).
            if _is_node_type(n, "Compartment"):
                continue
            if rendered >= cap:
                break
            nid = _mermaid_id(str(n.get("nodeId") or ""))
            cls = _node_class(n)
            shape = _node_shape(n)
            lines.extend(_render_node_with_class(nid, _mermaid_label_for(n), cls=cls, shape=shape))
            rendered += 1

        if len([n for n in comp_nodes if not _is_node_type(n, "Compartment")]) > cap:
            summary_id = _mermaid_id(f"comp:{cid}:summary")
            lines.extend(
                _render_node_with_class(
                    summary_id,
                    f"Other resources... and {len([n for n in comp_nodes if not _is_node_type(n, 'Compartment')]) - cap} more",
                    cls="summary",
                )
            )
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
                lines.append(_render_edge(c_id, v_id, "uses network"))
            for b in bucket_nodes:
                b_id = _mermaid_id(str(b.get("nodeId") or ""))
                lines.append(_render_edge(c_id, b_id, "reads/writes"))

    # Context links (root -> compartments)
    for cid in comp_ids:
        sg_id = _mermaid_id(f"comp:{cid}")
        lines.append(f"TEN_ROOT -.-> {sg_id}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_network_views(outdir: Path, nodes: Sequence[Node]) -> List[Path]:
    node_by_id: Dict[str, Node] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}

    vcns = [n for n in nodes if _is_node_type(n, "Vcn")]
    subnets = [n for n in nodes if _is_node_type(n, "Subnet")]

    # Map subnet -> vcn.
    subnet_to_vcn: Dict[str, str] = {}
    for sn in subnets:
        meta = _node_metadata(sn)
        vcn_id = _get_meta(meta, "vcn_id")
        if isinstance(vcn_id, str) and vcn_id:
            subnet_to_vcn[str(sn.get("nodeId") or "")] = vcn_id

    # Attach resources to vcn/subnet.
    attachments = _derived_attachments(nodes)
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
        lines.append(f"  subgraph {vcn_id}[\"{_vcn_label(vcn).replace('"', "'")}\"]")
        lines.append("    direction TB")

        # Gateways inside VCN.
        gateways = [
            n
            for n in nodes
            if _is_node_type(n, "InternetGateway", "NatGateway", "ServiceGateway")
            and str(_get_meta(_node_metadata(n), "vcn_id") or "") == vcn_ocid
        ]
        for g in sorted(gateways, key=lambda n: str(n.get("name") or "")):
            gid = _mermaid_id(str(g.get("nodeId") or ""))
            lines.extend(_render_node_with_class(gid, _mermaid_label_for(g), cls=_node_class(g), shape=_node_shape(g)))

        # Subnets inside VCN.
        vcn_subnets = [sn for sn in subnets if subnet_to_vcn.get(str(sn.get("nodeId") or "")) == vcn_ocid]
        for sn in sorted(vcn_subnets, key=lambda n: str(n.get("name") or "")):
            sn_ocid = str(sn.get("nodeId") or "")
            sn_id = _mermaid_id(sn_ocid)
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
                if summary:
                    sid = _mermaid_id(f"subnet:{sn_ocid}:leaf_summary")
                    lines.extend(_render_node_with_class(sid, summary, cls="summary"))

            lines.append("    end")

        lines.append("  end")

        # Flows: Internet -> IGW -> public subnets; private subnets -> NAT; private -> SGW.
        igw = next((g for g in gateways if _is_node_type(g, "InternetGateway")), None)
        nat = next((g for g in gateways if _is_node_type(g, "NatGateway")), None)
        sgw = next((g for g in gateways if _is_node_type(g, "ServiceGateway")), None)

        if igw is not None:
            igw_id = _mermaid_id(str(igw.get("nodeId") or ""))
            lines.append(_render_edge(internet_id, igw_id, "ingress/egress"))

        # Context link from view root.
        lines.append(f"{net_root} -.-> {vcn_id}")

        for sn in vcn_subnets:
            sn_ocid = str(sn.get("nodeId") or "")
            sn_id = _mermaid_id(sn_ocid)
            meta = _node_metadata(sn)
            prohibit = _get_meta(meta, "prohibit_public_ip_on_vnic")

            if prohibit is False and igw is not None:
                igw_id = _mermaid_id(str(igw.get("nodeId") or ""))
                lines.append(_render_edge(igw_id, sn_id, "routes"))

            if prohibit is True and nat is not None:
                nat_id = _mermaid_id(str(nat.get("nodeId") or ""))
                lines.append(_render_edge(sn_id, nat_id, "egress"))

            if prohibit is True and sgw is not None:
                sgw_id = _mermaid_id(str(sgw.get("nodeId") or ""))
                lines.append(_render_edge(sn_id, sgw_id, "OCI services"))

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out_paths.append(path)

    return out_paths


def _write_workload_views(outdir: Path, nodes: Sequence[Node]) -> List[Path]:
    # Identify candidate workloads.
    wl_to_nodes: Dict[str, List[Node]] = {}
    for n in nodes:
        nt = str(n.get("nodeType") or "")
        if nt in _NON_ARCH_LEAF_NODETYPES:
            continue
        if _is_node_type(n, "Compartment"):
            continue

        for wl in _infer_workload_keys(n):
            wl_to_nodes.setdefault(wl, []).append(n)

    # Keep only meaningful groups.
    wl_to_nodes = {k: v for k, v in wl_to_nodes.items() if len(v) >= 2}

    if not wl_to_nodes:
        return []

    # Build attachments for optional network context.
    attachments = _derived_attachments(nodes)
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
            untied_sorted = sorted(untied, key=lambda n: (str(n.get("nodeType") or ""), str(n.get("name") or "")))
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
                if summary:
                    sid = _mermaid_id(f"workload:{wl_name}:comp:{cid}:untied_leaf_summary")
                    lines.extend(_render_node_with_class(sid, summary, cls="summary"))

            for vcn_ocid in sorted(vcn_to_subnets.keys()):
                vcn = node_by_id.get(vcn_ocid)
                vcn_label = _vcn_label(vcn) if vcn else f"VCN {_short_ocid(vcn_ocid)}"
                vcn_id = _mermaid_id(f"workload:{wl_name}:vcn:{vcn_ocid}")
                lines.append(f"    subgraph {vcn_id}[\"{vcn_label.replace('"', "'")}\"]")
                lines.append("      direction TB")

                for sn_ocid in sorted(vcn_to_subnets[vcn_ocid]):
                    sn = node_by_id.get(sn_ocid)
                    sn_label = _subnet_label(sn) if sn else f"Subnet {_short_ocid(sn_ocid)}"
                    sn_id = _mermaid_id(f"workload:{wl_name}:subnet:{sn_ocid}")
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

                    for a in key_nodes[:8]:
                        aid = _mermaid_id(str(a.get("nodeId") or ""))
                        lines.extend(_render_node_with_class(aid, _mermaid_label_for(a), cls=_node_class(a), shape=_node_shape(a)))

                    if len(key_nodes) > 8:
                        sid = _mermaid_id(f"workload:{wl_name}:comp:{cid}:subnet:{sn_ocid}:key_summary")
                        lines.extend(
                            _render_node_with_class(
                                sid,
                                f"Other key resources... and {len(key_nodes) - 8} more",
                                cls="summary",
                            )
                        )

                    if leaf_nodes:
                        kept, summary = _summarize_many(leaf_nodes, title="Other media/leaf items", keep=2)
                        for a in kept:
                            aid = _mermaid_id(str(a.get("nodeId") or ""))
                            lines.extend(_render_node_with_class(aid, _mermaid_label_for(a), cls="boundary", shape="rect"))
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
        buckets = [n for n in wl_nodes if _is_node_type(n, "Bucket") or "bucket" in str(n.get("nodeType") or "").lower()]

        for lb in lbs:
            lb_id = _mermaid_id(str(lb.get("nodeId") or ""))
            lines.append(_render_edge(users_id, lb_id, "requests"))
            for c in computes:
                c_id = _mermaid_id(str(c.get("nodeId") or ""))
                lines.append(_render_edge(lb_id, c_id, "forwards"))

        for c in computes:
            c_id = _mermaid_id(str(c.get("nodeId") or ""))
            if not buckets:
                continue
            for b in buckets:
                b_id = _mermaid_id(str(b.get("nodeId") or ""))
                lines.append(_render_edge(c_id, b_id, "reads/writes"))

        for b in buckets:
            b_id = _mermaid_id(str(b.get("nodeId") or ""))
            lines.append(_render_edge(b_id, services_id, "Object Storage"))

        # Context links
        lines.append(f"{wl_root} -.-> {users_id}")
        lines.append(f"{wl_root} -.-> {services_id}")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        out_paths.append(path)

    return out_paths


def write_diagram_projections(outdir: Path, nodes: Sequence[Node], edges: Sequence[Edge]) -> List[Path]:
    # edges are currently unused for projections, but intentionally accepted to keep the API stable
    # for future relationship-driven rendering.
    out: List[Path] = []
    out.append(_write_tenancy_view(outdir, nodes, edges))
    out.extend(_write_network_views(outdir, nodes))
    out.extend(_write_workload_views(outdir, nodes))

    # Consolidated, end-user-friendly artifact: one Mermaid diagram that contains all the views.
    out.append(_write_consolidated_mermaid(outdir, out))
    return out


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


def _write_consolidated_mermaid(outdir: Path, diagram_paths: Sequence[Path]) -> Path:
    consolidated = outdir / "diagram.consolidated.mmd"

    # Deterministic ordering: tenancy first, then networks, then workloads.
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

    # Mermaid IDs used by our generators are stable 12-hex hashes like Nxxxxxxxxxxxx.
    # When combining diagrams into a single Mermaid graph, prefix IDs per view to avoid collisions.
    id_pat = re.compile(r"\bN[0-9a-f]{12}\b")

    def _view_prefix(p: Path) -> str:
        n = p.name
        if n == "diagram.tenancy.mmd":
            return "TEN_"
        if n.startswith("diagram.network.") and n.endswith(".mmd"):
            vcn = n[len("diagram.network.") : -len(".mmd")]
            return f"NET_{_slugify(vcn)}_"
        if n.startswith("diagram.workload.") and n.endswith(".mmd"):
            wl = n[len("diagram.workload.") : -len(".mmd")]
            return f"WL_{_slugify(wl)}_"
        return "VIEW_"

    lines: List[str] = ["flowchart TD"]
    lines.extend(_style_block_lines())
    lines.append("%% ------------------ Consolidated Architecture Views ------------------")

    for p in mmds_sorted:
        title = _diagram_title(p).replace('"', "'")
        prefix = _view_prefix(p)
        sg_id = f"{prefix}ROOT"
        lines.append(f"  %% ---- {title} ----")
        lines.append(f"  subgraph {sg_id}[\"{title}\"]")

        raw = p.read_text(encoding="utf-8").splitlines()
        # Drop leading diagram header if present.
        if raw and (raw[0].strip().startswith("graph") or raw[0].strip().startswith("flowchart")):
            raw = raw[1:]

        for line in raw:
            stripped = line.strip()
            # Drop style definitions from embedded views; consolidated defines them once.
            if stripped.startswith("classDef") or stripped.startswith("%% Styles"):
                continue
            # Preserve blank lines for readability.
            if not stripped:
                lines.append("")
                continue

            # Prefix all generated IDs (nodes/subgraphs) for collision safety.
            lines.append(id_pat.sub(lambda m: prefix + m.group(0), line))

        lines.append("  end")

    # High-level context links (Tenancy -> each view root), if tenancy root exists.
    has_tenancy = any(p.name == "diagram.tenancy.mmd" for p in mmds_sorted)
    if has_tenancy:
        for p in mmds_sorted:
            if p.name.startswith("diagram.network."):
                vcn = p.name[len("diagram.network.") : -len(".mmd")]
                lines.append(f"TEN_ROOT -.-> NET_{_slugify(vcn)}_ROOT")
            if p.name.startswith("diagram.workload."):
                wl = p.name[len("diagram.workload.") : -len(".mmd")]
                lines.append(f"TEN_ROOT -.-> WL_{_slugify(wl)}_ROOT")

    consolidated.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return consolidated
