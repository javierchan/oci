from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

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
    "DHCPOptions",
    "Drg",
    "DrgAttachment",
    "IPSecConnection",
    "IpSecConnection",
    "VirtualCircuit",
    "Cpe",
    "LocalPeeringGateway",
    "RemotePeeringConnection",
    "CrossConnect",
    "CrossConnectGroup",
    "LoadBalancer",
    "PublicIp",
}
SECURITY_TYPES = {
    "Bastion",
    "Vault",
    "Secret",
    "CloudGuardTarget",
    "NetworkFirewall",
    "NetworkFirewallPolicy",
    "WebAppFirewall",
    "WebAppFirewallPolicy",
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


def _record_metadata(record: Mapping[str, Any]) -> Mapping[str, Any]:
    details = record.get("details") if isinstance(record, Mapping) else None
    if not isinstance(details, Mapping):
        return {}
    md = details.get("metadata")
    return md if isinstance(md, Mapping) else {}


def _get_meta(metadata: Mapping[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in metadata:
            return metadata[k]
        # Accept camelCase vs snake_case interchangeably.
        camel = "".join([w[:1].upper() + w[1:] if i > 0 else w for i, w in enumerate(k.split("_"))])
        snake = "".join([("_" + ch.lower()) if ch.isupper() else ch for ch in k]).lstrip("_")
        if camel in metadata:
            return metadata[camel]
        if snake in metadata:
            return metadata[snake]
    return None


@dataclass(frozen=True)
class RelationshipIndex:
    ocids: Set[str]
    compartment_name_to_ocid: Dict[str, str]
    subnet_to_vnics: Dict[str, Set[str]]
    private_ip_by_addr: Dict[str, str]
    public_ip_by_addr: Dict[str, str]
    drg_to_vcns: Dict[str, Set[str]]


def build_relationship_index(records: Iterable[Dict[str, Any]]) -> RelationshipIndex:
    ocids: Set[str] = set()
    compartment_name_to_ocid: Dict[str, str] = {}
    subnet_to_vnics: Dict[str, Set[str]] = {}
    private_ip_by_addr: Dict[str, str] = {}
    public_ip_by_addr: Dict[str, str] = {}
    drg_to_vcns: Dict[str, Set[str]] = {}

    for r in records:
        ocid = str(r.get("ocid") or "")
        if ocid:
            ocids.add(ocid)
        comp_id = str(r.get("compartmentId") or "")
        if comp_id:
            ocids.add(comp_id)

        rtype = str(r.get("resourceType") or "")
        if rtype == "Compartment":
            name = str(r.get("displayName") or r.get("name") or "").strip()
            if name and ocid:
                compartment_name_to_ocid.setdefault(name.lower(), ocid)

        if rtype == "Vnic":
            md = _record_metadata(r)
            subnet_id = _get_meta(md, "subnet_id", "subnetId")
            if isinstance(subnet_id, str) and subnet_id:
                subnet_to_vnics.setdefault(subnet_id, set()).add(ocid)

        if rtype in {"PrivateIp", "PublicIp"}:
            md = _record_metadata(r)
            ip = _get_meta(md, "ip_address", "ipAddress")
            if isinstance(ip, str) and ip and ocid:
                if rtype == "PrivateIp":
                    private_ip_by_addr.setdefault(ip, ocid)
                else:
                    public_ip_by_addr.setdefault(ip, ocid)

        if rtype == "DrgAttachment":
            md = _record_metadata(r)
            drg_id = _get_meta(md, "drg_id", "drgId")
            vcn_id = _get_meta(md, "vcn_id", "vcnId", "network_id", "networkId")
            if isinstance(drg_id, str) and drg_id and isinstance(vcn_id, str) and vcn_id:
                drg_to_vcns.setdefault(drg_id, set()).add(vcn_id)

    return RelationshipIndex(
        ocids=ocids,
        compartment_name_to_ocid=compartment_name_to_ocid,
        subnet_to_vnics=subnet_to_vnics,
        private_ip_by_addr=private_ip_by_addr,
        public_ip_by_addr=public_ip_by_addr,
        drg_to_vcns=drg_to_vcns,
    )


def iter_relationships_for_record(
    record: Dict[str, Any],
    index: RelationshipIndex,
) -> Iterable[Dict[str, str]]:
    out: List[Dict[str, str]] = []

    def _emit(src: str, rel: str, dst: str) -> None:
        if not src or not dst or not rel:
            return
        if src not in index.ocids or dst not in index.ocids:
            return
        out.append({"source_ocid": src, "relation_type": rel, "target_ocid": dst})

    def _collect_ids(value: Any) -> List[str]:
        if isinstance(value, (list, tuple, set)):
            return [v for v in value if isinstance(v, str) and v]
        if isinstance(value, str) and value:
            return [value]
        return []

    network_child_types = {
        "Subnet",
        "RouteTable",
        "SecurityList",
        "NetworkSecurityGroup",
        "DhcpOptions",
        "DHCPOptions",
        "InternetGateway",
        "NatGateway",
        "ServiceGateway",
        "Drg",
        "DrgAttachment",
        "IPSecConnection",
        "IpSecConnection",
        "VirtualCircuit",
        "Cpe",
        "LocalPeeringGateway",
        "RemotePeeringConnection",
        "CrossConnect",
        "CrossConnectGroup",
        "LoadBalancer",
    }

    firewall_types = {
        "NetworkFirewall",
        "NetworkFirewallPolicy",
        "WebAppFirewall",
        "WebAppFirewallPolicy",
        "Firewall",
    }

    iam_types = {
        "Policy",
        "DynamicGroup",
        "Group",
        "User",
        "IdentityDomain",
        "IdentityDomainUser",
        "IdentityDomainGroup",
    }

    src = str(record.get("ocid") or "")
    if not src:
        return out
    rt = str(record.get("resourceType") or "")
    md = _record_metadata(record)

    vcn_ids = _collect_ids(_get_meta(md, "vcn_id", "vcnId", "vcn_ids", "vcnIds"))
    for vcn_id in vcn_ids:
        _emit(src, "IN_VCN", vcn_id)

    subnet_ids = _collect_ids(_get_meta(md, "subnet_id", "subnetId", "subnet_ids", "subnetIds"))
    for subnet_id in subnet_ids:
        _emit(src, "IN_SUBNET", subnet_id)

    vnic_ids = _collect_ids(_get_meta(md, "vnic_id", "vnicId", "vnic_ids", "vnicIds"))
    for vnic_id in vnic_ids:
        _emit(src, "IN_VNIC", vnic_id)

    rt_id = _get_meta(md, "route_table_id", "routeTableId")
    if isinstance(rt_id, str) and rt_id:
        _emit(src, "USES_ROUTE_TABLE", rt_id)

    sl_ids = _get_meta(md, "security_list_ids", "securityListIds")
    for sl_id in _collect_ids(sl_ids):
        _emit(src, "USES_SECURITY_LIST", sl_id)

    nsg_ids = _get_meta(md, "nsg_ids", "nsgIds", "network_security_group_ids", "networkSecurityGroupIds")
    for nsg_id in _collect_ids(nsg_ids):
        _emit(src, "USES_NSG", nsg_id)

    dhcp_id = _get_meta(md, "dhcp_options_id", "dhcpOptionsId")
    if isinstance(dhcp_id, str) and dhcp_id:
        _emit(src, "USES_DHCP_OPTIONS", dhcp_id)

    drg_id = _get_meta(md, "drg_id", "drgId", "gateway_id", "gatewayId")
    if isinstance(drg_id, str) and drg_id:
        _emit(src, "USES_DRG", drg_id)
        for vcn_id in sorted(index.drg_to_vcns.get(drg_id, set())):
            _emit(src, "IN_VCN", vcn_id)

    if rt == "Drg" and src in index.drg_to_vcns:
        for vcn_id in sorted(index.drg_to_vcns.get(src, set())):
            _emit(src, "IN_VCN", vcn_id)

    if rt == "DrgAttachment":
        drg_id = _get_meta(md, "drg_id", "drgId")
        if isinstance(drg_id, str) and drg_id:
            _emit(src, "ATTACHED_TO_DRG", drg_id)
        vcn_id = _get_meta(md, "vcn_id", "vcnId", "network_id", "networkId")
        if isinstance(vcn_id, str) and vcn_id:
            _emit(src, "ATTACHED_TO_VCN", vcn_id)

    assigned_id = _get_meta(md, "assigned_entity_id", "assignedEntityId")
    for target_id in _collect_ids(assigned_id):
        _emit(src, "ASSIGNED_TO", target_id)

    private_ip_id = _get_meta(md, "private_ip_id", "privateIpId")
    for target_id in _collect_ids(private_ip_id):
        _emit(src, "ASSIGNED_TO", target_id)

    # Network object placement
    if rt in network_child_types:
        vcn_id = _get_meta(md, "vcn_id", "vcnId")
        if isinstance(vcn_id, str) and vcn_id:
            _emit(src, "IN_VCN", vcn_id)

    # Subnet wiring
    if rt == "Subnet":
        route_table_id = _get_meta(md, "route_table_id", "routeTableId")
        if isinstance(route_table_id, str) and route_table_id:
            _emit(src, "USES_ROUTE_TABLE", route_table_id)

        sl_ids = _get_meta(md, "security_list_ids", "securityListIds")
        if isinstance(sl_ids, list):
            for sid in sl_ids:
                if isinstance(sid, str) and sid:
                    _emit(src, "USES_SECURITY_LIST", sid)

        nsg_ids = _get_meta(md, "nsg_ids", "nsgIds")
        if isinstance(nsg_ids, list):
            for nid in nsg_ids:
                if isinstance(nid, str) and nid:
                    _emit(src, "USES_NSG", nid)

    # VNIC wiring
    if rt == "Vnic":
        subnet_id = _get_meta(md, "subnet_id", "subnetId")
        if isinstance(subnet_id, str) and subnet_id:
            _emit(src, "IN_SUBNET", subnet_id)
        nsg_ids = _get_meta(md, "nsg_ids", "nsgIds")
        if isinstance(nsg_ids, list):
            for nid in nsg_ids:
                if isinstance(nid, str) and nid:
                    _emit(src, "USES_NSG", nid)

    if rt in firewall_types:
        for subnet_id in subnet_ids:
            for vnic_id in sorted(index.subnet_to_vnics.get(subnet_id, set())):
                _emit(src, "PROTECTS_VNIC", vnic_id)

    if rt in iam_types:
        comp_id = str(record.get("compartmentId") or "")
        if comp_id:
            _emit(src, "IAM_SCOPE", comp_id)
        statements = _get_meta(md, "statements")
        if isinstance(statements, list):
            for stmt in statements:
                if not isinstance(stmt, str):
                    continue
                stmt_lower = stmt.lower()
                for ocid_match in re.findall(r"ocid1\\.compartment[\\w.:-]+", stmt_lower):
                    _emit(src, "IAM_SCOPE", ocid_match)
                if "in compartment" not in stmt_lower:
                    continue
                tail = stmt_lower.split("in compartment", 1)[1].strip()
                tail = re.split(r"\\bwhere\\b|\\bwith\\b|\\b,\\b", tail, maxsplit=1)[0]
                name = tail.strip().strip('"').strip("'")
                if not name:
                    continue
                ocid = index.compartment_name_to_ocid.get(name)
                if ocid:
                    _emit(src, "IAM_SCOPE", ocid)

    if rt == "LoadBalancer":
        subnet_refs = _collect_ids(_get_meta(md, "subnet_ids", "subnetIds"))
        for subnet_id in subnet_refs:
            _emit(src, "IN_SUBNET", subnet_id)

        lb_ip_addrs = _get_meta(md, "ip_addresses", "ipAddresses")
        if isinstance(lb_ip_addrs, list):
            for entry in lb_ip_addrs:
                if not isinstance(entry, dict):
                    continue
                ip_addr = entry.get("ipAddress") or entry.get("ip_address")
                if isinstance(ip_addr, str) and ip_addr in index.public_ip_by_addr:
                    _emit(src, "EXPOSES_PUBLIC_IP", index.public_ip_by_addr[ip_addr])

        backend_sets = md.get("backendSets") if isinstance(md, dict) else None
        if backend_sets is None:
            backend_sets = md.get("backend_sets") if isinstance(md, dict) else None
        if isinstance(backend_sets, dict):
            for bs in backend_sets.values():
                if not isinstance(bs, dict):
                    continue
                backends = bs.get("backends")
                if not isinstance(backends, list):
                    continue
                for backend in backends:
                    if not isinstance(backend, dict):
                        continue
                    ip_addr = backend.get("ipAddress") or backend.get("ip_address")
                    if isinstance(ip_addr, str) and ip_addr in index.private_ip_by_addr:
                        _emit(src, "ROUTES_TO_PRIVATE_IP", index.private_ip_by_addr[ip_addr])

    if rt in {"WebAppFirewall", "WebAppFirewallPolicy"}:
        lb_id = _get_meta(md, "load_balancer_id", "loadBalancerId")
        for target_id in _collect_ids(lb_id):
            _emit(src, "PROTECTS_LOAD_BALANCER", target_id)

    if rt == "NetworkFirewall":
        policy_id = _get_meta(md, "network_firewall_policy_id", "networkFirewallPolicyId")
        for target_id in _collect_ids(policy_id):
            _emit(src, "USES_FIREWALL_POLICY", target_id)

    return out


def derive_relationships_from_metadata(records: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Derive additional relationships from existing record metadata.

    This is deterministic and offline (no new OCI calls). It is intended to enrich
    the graph with architecture-relevant edges when enrichers did not provide any.

    Only emits edges when both source and target OCIDs exist in the provided
    records to avoid creating dangling references.
    """

    recs = list(records)
    index = build_relationship_index(recs)
    out: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str]] = set()
    for r in recs:
        for rel in iter_relationships_for_record(r, index):
            key = (rel.get("source_ocid", ""), rel.get("relation_type", ""), rel.get("target_ocid", ""))
            if key in seen:
                continue
            seen.add(key)
            out.append(rel)

    return sorted(out, key=lambda r: (r.get("source_ocid", ""), r.get("relation_type", ""), r.get("target_ocid", "")))


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
    relationships: Iterable[Dict[str, str]],
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
        src = rel.get("source_ocid")
        src_node = nodes_by_id.get(src or "", {})
        edges.append(
            {
                "source_ocid": src,
                "target_ocid": rel.get("target_ocid"),
                "relation_type": rel.get("relation_type"),
                "source_type": src_node.get("nodeType"),
                "target_type": nodes_by_id.get(rel.get("target_ocid") or "", {}).get("nodeType"),
                "region": src_node.get("region"),
            }
        )

    # Deduplicate edges deterministically
    dedup: Dict[Tuple[str, str, str], Edge] = {}
    for edge in edges:
        dedup[_edge_key(edge)] = edge
    edges_out = [dedup[k] for k in sorted(dedup.keys())]

    nodes_out = [nodes_by_id[k] for k in sorted(nodes_by_id.keys())]
    return nodes_out, edges_out


def filter_edges_with_nodes(nodes: Sequence[Node], edges: Sequence[Edge]) -> Tuple[List[Edge], int]:
    node_ids = {str(node.get("nodeId") or "") for node in nodes if node.get("nodeId")}
    filtered = [
        edge
        for edge in edges
        if str(edge.get("source_ocid") or "") in node_ids
        and str(edge.get("target_ocid") or "") in node_ids
    ]
    return filtered, len(edges) - len(filtered)


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
    with path.open("w", encoding="utf-8") as f:
        f.write("graph TD\n")
        for node in nodes:
            node_id = _mermaid_id(str(node.get("nodeId") or ""))
            label = _mermaid_label(node)
            f.write(f'  {node_id}["{label}"]\n')
        for edge in edges:
            src = _mermaid_id(str(edge.get("source_ocid") or ""))
            tgt = _mermaid_id(str(edge.get("target_ocid") or ""))
            rel = str(edge.get("relation_type") or "")
            if rel:
                f.write(f"  {src} -->|{rel}| {tgt}\n")
            else:
                f.write(f"  {src} --> {tgt}\n")
    return path
