from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .graph import Edge, Node


@dataclass(frozen=True)
class ConceptNode:
    concept_id: str
    label: str
    lane: str
    compartment_id: str
    vcn_names: Tuple[str, ...]
    source_types: Tuple[str, ...]
    placement: str
    security_scope: Optional[str]
    count: int


@dataclass(frozen=True)
class WorkloadContext:
    compartment_ids: Tuple[str, ...]
    vcn_names_by_compartment: Mapping[str, Tuple[str, ...]]


# Gateway types: shown with specific labels, placed at VCN "edge"
_GATEWAY_TYPES: Mapping[str, str] = {
    "InternetGateway": "Internet Gateway",
    "NatGateway": "NAT Gateway",
    "ServiceGateway": "Service Gateway",
    "Drg": "DRG",
    "VirtualCircuit": "FastConnect",
    "IPSecConnection": "VPN Connection",
    "Cpe": "Customer Premises Equipment",
    "LocalPeeringGateway": "Local Peering Gateway",
    "RemotePeeringConnection": "Remote Peering Connection",
}

# Low-level objects that add noise without architectural value.
# Uses BARE type names (without category prefix). Match the exact OCI resource type
# as returned by the API (e.g. "DHCPOptions" not "DhcpOptions").
_ARCH_NOISE_NODETYPES: Set[str] = {
    # Networking internals
    "PrivateIp", "Vnic", "VnicAttachment", "Ipv6",
    "DrgRouteTable", "DrgRouteDistribution", "DrgRouteDistributionStatement",
    "DrgAttachment",  # attachment plumbing — DRG is the meaningful component
    "DHCPOptions", "DhcpOptions",  # both casing variants seen in the wild
    "RouteTable",
    "PublicIp", "PublicIpPool", "Byoiprange", "ByoipRange",
    "CrossConnect", "CrossConnectGroup",  # physical layer — FastConnect/VirtualCircuit is the concept
    # Internal DNS objects (DnsZone is kept — it's architectural; resolver/view are not)
    "DnsResolver", "DnsView", "DnsRrset",
    # Notification subscriptions (the Topic is the architectural concept, not the subscription)
    "OnsSubscription", "Subscription",
    # Storage implementation details
    "BootVolume", "BootVolumeBackup", "VolumeBackup", "VolumeGroupBackup",
    "ExportSet",
    # IAM credentials (not structural)
    "AuthToken", "ApiKey", "SwiftPassword", "CustomerSecretKey", "SmtpCredential",
    # DB implementation internals (part of DbSystem/ADB, not standalone concepts)
    "DbNode", "DbHome",
    # Compute implementation details
    "ConsoleHistory", "InstanceConsoleConnection",
    # Marketplace / subscription metadata
    "AppCatalogSubscription",
    # OCI internal / management
    "OsmhProfile", "OsmhSoftwareSource",
    # Tagging internals (TagNamespace is kept as IAM; defaults/keys are not)
    "TagDefault", "TagKey",
}

_NON_ARCH_TYPE_KEYWORDS = (
    "job",
    "run",
    "execution",
    "workrequest",
    "bootvolume",
    "boot volume",
    "volume backup",
    "backup",
    "snapshot",
)


def build_workload_context(
    *,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    workload_nodes: Sequence[Node],
) -> WorkloadContext:
    node_by_id = _node_by_id(nodes)
    vcn_name_by_id = _vcn_name_map(nodes)
    scope_compartments = _scope_compartment_ids(workload_nodes)
    scope_vcns = _scope_vcn_ids(workload_nodes, nodes=nodes, edges=edges)

    vcn_names_by_comp: Dict[str, Set[str]] = {}
    for vcn_id in scope_vcns:
        vcn_name = vcn_name_by_id.get(vcn_id)
        if not vcn_name:
            continue
        comp_id = str(node_by_id.get(vcn_id, {}).get("compartmentId") or "")
        if not comp_id or comp_id == "UNKNOWN":
            if scope_compartments:
                comp_id = sorted(scope_compartments)[0]
            else:
                comp_id = "UNKNOWN"
        vcn_names_by_comp.setdefault(comp_id, set()).add(_sanitize_label(vcn_name))

    ordered_compartments = tuple(sorted(scope_compartments)) if scope_compartments else ("UNKNOWN",)
    normalized_vcns = {
        comp_id: tuple(sorted(names))
        for comp_id, names in vcn_names_by_comp.items()
    }
    return WorkloadContext(
        compartment_ids=ordered_compartments,
        vcn_names_by_compartment=normalized_vcns,
    )


def build_workload_concepts(
    *,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    workload_nodes: Sequence[Node],
) -> List[ConceptNode]:
    node_by_id = _node_by_id(nodes)
    vcn_name_by_id = _vcn_name_map(nodes)
    scope_vcns = _scope_vcn_ids(workload_nodes, nodes=nodes, edges=edges)
    scope_compartments = _scope_compartment_ids(workload_nodes)

    scoped_ids: Set[str] = {str(n.get("nodeId") or "") for n in workload_nodes if n.get("nodeId")}
    for n in nodes:
        if not n.get("nodeId"):
            continue
        if _bare_type(n) not in _GATEWAY_TYPES:
            continue
        vcn_id = _node_vcn_id(n, nodes=nodes, edges=edges, node_by_id=node_by_id)
        if vcn_id and vcn_id in scope_vcns:
            scoped_ids.add(str(n.get("nodeId") or ""))

    buckets: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    for node_id in sorted(scoped_ids):
        node = node_by_id.get(node_id)
        if not node:
            continue
        if _is_non_arch_resource(node):
            continue
        lane, label = _concept_for_node(node)
        if not lane or not label:
            continue
        compartment_id = _node_compartment_id(node)
        if not compartment_id:
            compartment_id = next(iter(scope_compartments), "UNKNOWN")
        vcn_id = _node_vcn_id(node, nodes=nodes, edges=edges, node_by_id=node_by_id)
        vcn_name = vcn_name_by_id.get(vcn_id) if vcn_id else None
        vcn_names = {_sanitize_label(vcn_name)} if vcn_name else set()
        placement = _placement_for_node(node, vcn_id=vcn_id)
        security_scope = _security_scope_for_node(node, vcn_id=vcn_id)
        key = (compartment_id, lane, label, placement, security_scope or "none")
        bucket = buckets.setdefault(key, {
            "vcn_names": set(),
            "source_types": set(),
            "count": 0,
            "security_scope": security_scope,
        })
        bucket["count"] += 1
        bucket["source_types"].add(str(node.get("nodeType") or ""))
        bucket["vcn_names"].update(vcn_names)

    concepts: List[ConceptNode] = []
    for (compartment_id, lane, label, placement, _scope_key), data in sorted(buckets.items()):
        security_scope = data.get("security_scope")
        concept_id = _concept_id(compartment_id, lane, label, placement, security_scope)
        concepts.append(
            ConceptNode(
                concept_id=concept_id,
                label=label,
                lane=lane,
                compartment_id=compartment_id,
                vcn_names=tuple(sorted(data["vcn_names"])),
                source_types=tuple(sorted(data["source_types"])),
                placement=placement,
                security_scope=security_scope,
                count=int(data["count"]),
            )
        )
    return concepts


def build_scope_concepts(
    *,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    scope_nodes: Sequence[Node],
) -> List[ConceptNode]:
    return build_workload_concepts(nodes=nodes, edges=edges, workload_nodes=scope_nodes)


def _node_by_id(nodes: Sequence[Node]) -> Dict[str, Node]:
    return {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}


def _node_compartment_id(node: Node) -> str:
    return str(node.get("compartmentId") or "")


def _vcn_name_map(nodes: Sequence[Node]) -> Dict[str, str]:
    return {
        str(n.get("nodeId") or ""): str(n.get("name") or "")
        for n in nodes
        if n.get("nodeId") and str(n.get("nodeType") or "") in {"Vcn", "network.Vcn"}
    }


def _scope_compartment_ids(nodes: Sequence[Node]) -> Set[str]:
    comp_ids = {str(n.get("compartmentId") or "") for n in nodes if n.get("compartmentId")}
    return {cid for cid in comp_ids if cid}


def _edge_map(edges: Sequence[Edge], relation_type: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for edge in edges:
        if str(edge.get("relation_type") or "") != relation_type:
            continue
        src = str(edge.get("source_ocid") or "")
        tgt = str(edge.get("target_ocid") or "")
        if src and tgt:
            mapping[src] = tgt
    return mapping


def _node_metadata(node: Node) -> Mapping[str, object]:
    meta = node.get("metadata")
    return meta if isinstance(meta, Mapping) else {}


def _get_meta(metadata: Mapping[str, object], *keys: str) -> Optional[str]:
    for k in keys:
        if k in metadata:
            value = metadata[k]
            return str(value) if value is not None else None
        camel = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), k)
        snake = re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), k)
        if camel in metadata:
            value = metadata[camel]
            return str(value) if value is not None else None
        if snake in metadata:
            value = metadata[snake]
            return str(value) if value is not None else None
    return None


def _node_vcn_id(
    node: Node,
    *,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
    node_by_id: Optional[Mapping[str, Node]] = None,
) -> Optional[str]:
    node_by_id = node_by_id or _node_by_id(nodes)
    node_id = str(node.get("nodeId") or "")
    node_type = str(node.get("nodeType") or "")
    if node_type in {"Vcn", "network.Vcn"} and node_id:
        return node_id

    meta = _node_metadata(node)
    vcn_id = _get_meta(meta, "vcn_id", "vcnId")
    if vcn_id:
        return vcn_id

    edge_vcn = _edge_map(edges, "IN_VCN")
    edge_subnet = _edge_map(edges, "IN_SUBNET")
    if node_id and node_id in edge_vcn:
        return edge_vcn[node_id]
    subnet_id = _get_meta(meta, "subnet_id", "subnetId") or edge_subnet.get(node_id)
    if subnet_id:
        subnet = node_by_id.get(subnet_id, {})
        subnet_meta = _node_metadata(subnet)
        subnet_vcn = _get_meta(subnet_meta, "vcn_id", "vcnId") or edge_vcn.get(subnet_id)
        if subnet_vcn:
            return subnet_vcn
    return None


def _scope_vcn_ids(
    workload_nodes: Sequence[Node],
    *,
    nodes: Sequence[Node],
    edges: Sequence[Edge],
) -> Set[str]:
    node_by_id = _node_by_id(nodes)
    vcn_ids = set()
    for n in workload_nodes:
        vcn_id = _node_vcn_id(n, nodes=nodes, edges=edges, node_by_id=node_by_id)
        if vcn_id:
            vcn_ids.add(vcn_id)
    return vcn_ids


def _bare_type(node: Node) -> str:
    """Return nodeType with category prefix stripped (e.g. 'network.NatGateway' → 'NatGateway')."""
    nt = str(node.get("nodeType") or "")
    return nt.split(".")[-1] if "." in nt else nt


def _is_non_arch_resource(node: Node) -> bool:
    bare = _bare_type(node)
    if bare in _ARCH_NOISE_NODETYPES:
        return True
    bare_lower = bare.lower()
    name_lower = str(node.get("name") or "").lower()
    for token in _NON_ARCH_TYPE_KEYWORDS:
        if token in bare_lower or token in name_lower:
            return True
    return False


def _concept_for_node(node: Node) -> Tuple[Optional[str], Optional[str]]:
    bare = _bare_type(node)
    bare_lower = bare.lower()
    name_lower = str(node.get("name") or "").lower()
    category = str(node.get("nodeCategory") or "").lower()

    # Structural containers: never shown
    if bare in {"Compartment", "Vcn", "Subnet"}:
        return None, None

    # --- NETWORK GATEWAYS (edge placement) ---
    if bare in _GATEWAY_TYPES:
        return "network", _GATEWAY_TYPES[bare]

    # --- LOAD BALANCERS ---
    if "loadbalancer" in bare_lower:
        if bare_lower.startswith("network"):
            return "network", "Network Load Balancer"
        return "network", "Load Balancer"

    # --- API GATEWAY ---
    if "apigateway" in bare_lower:
        return "network", "API Gateway"

    # --- NETWORK SECURITY (in-VCN, security lane) ---
    if "networksecuritygroup" in bare_lower:
        return "security", "NSG"
    if "securitylist" in bare_lower:
        return "security", "Security List"

    # --- VLAN ---
    if bare == "Vlan":
        return "network", "VLAN"

    # --- DNS ---
    if "dnszone" in bare_lower or "customerdnszone" in bare_lower:
        return "network", "DNS Zone"

    # --- FUNCTIONS APPLICATION ---
    if bare in {"Application", "FnApplication", "FunctionsApplication"}:
        return "app", "Functions"

    # --- OKE ---
    if "containerengine" in bare_lower and "cluster" in bare_lower:
        return "app", "OKE Cluster"
    if "containerengine" in bare_lower or "nodepool" in bare_lower:
        return "app", "OKE Node Pool"

    # --- WORKER NODES (name-based) ---
    if "worker" in name_lower and "node" in name_lower:
        return "app", "Worker Nodes"

    # --- ODI (name-based) ---
    if "odi" in name_lower and ("stack" in bare_lower or "marketplace" in bare_lower):
        return "app", "ODI Stack"
    if "odi" in name_lower and "instance" in bare_lower:
        return "app", "ODI Instance"

    # --- COMPUTE ---
    if bare in {"InstancePool", "InstanceConfiguration"}:
        return "app", "Instance Pool"
    if "baremetal" in bare_lower:
        return "app", "Bare Metal"
    if "function" in bare_lower:
        return "app", "Functions"
    if "instance" in bare_lower:
        return "app", "Compute Instance"

    # --- VMWARE OCVS ---
    if "vmware" in bare_lower or "esxi" in bare_lower or "sddc" in bare_lower:
        return "app", "VMware OCVS"

    # --- DATABASES ---
    if "autonomous" in bare_lower:
        return "data", "Autonomous Database"
    if "dbsystem" in bare_lower:
        return "data", "DB System"
    if "mysql" in bare_lower:
        return "data", "MySQL DB"
    if "postgres" in bare_lower:
        return "data", "PostgreSQL DB"
    if "nosql" in bare_lower:
        return "data", "NoSQL Table"
    if "database" in bare_lower:
        return "data", "Database"

    # --- STORAGE ---
    if "bucket" in bare_lower or "objectstorage" in bare_lower:
        return "data", "Object Storage"
    if "blockvolume" in bare_lower or bare_lower == "volume":
        return "data", "Block Volume"
    if "filesystem" in bare_lower or "mounttarget" in bare_lower:
        return "data", "File Storage"

    # --- SECURITY ---
    if "cloudguard" in bare_lower:
        return "security", "Cloud Guard"
    if "securityzone" in bare_lower:
        return "security", "Security Zone"
    if "vault" in bare_lower or "keymanagement" in bare_lower:
        return "security", "Vault / KMS"
    if "waas" in bare_lower or "waf" in bare_lower or "webapplicationfirewall" in bare_lower:
        return "security", "WAF"
    if "bastion" in bare_lower:
        return "security", "Bastion"
    if "certificate" in bare_lower:
        return "security", "Certificates"

    # --- OBSERVABILITY ---
    if "loganalytics" in bare_lower:
        return "observability", "Log Analytics"
    if "notification" in bare_lower or "onstopic" in bare_lower:
        return "observability", "Notifications"
    if "alarm" in bare_lower:
        return "observability", "Alarms"
    if "eventrule" in bare_lower or "eventcondition" in bare_lower:
        return "observability", "Events"
    if category == "observability" or any(t in bare_lower for t in ("log", "metric", "monitor")):
        return "observability", "Monitoring"

    # --- IAM ---
    if bare in {"User", "Group", "DynamicResourceGroup"}:
        return "iam", "IAM Principals"
    if bare == "Policy":
        return "iam", "IAM Policies"
    if "identitydomain" in bare_lower:
        return "iam", "Identity Domain"
    if "tagnamespace" in bare_lower:
        return "iam", "Tag Namespace"
    if category == "iam":
        return "iam", "IAM"

    # --- CATEGORY FALLBACKS with friendly type name ---
    friendly = _sanitize_label(_friendly_type(bare))
    if category in {"compute", "app"}:
        return "app", friendly or "App Service"
    if category in {"data", "storage"}:
        return "data", friendly or "Data Service"
    if category in {"security", "governance"}:
        return "security", friendly or "Security Control"
    if category == "network":
        return "network", friendly or "Network Service"

    # Catch-all: use friendly type name or drop
    return ("other", friendly) if friendly else (None, None)


def _placement_for_node(node: Node, *, vcn_id: Optional[str]) -> str:
    bare = _bare_type(node)
    bare_lower = bare.lower()
    if bare in _GATEWAY_TYPES:
        return "edge"
    if vcn_id:
        return "in_vcn"
    category = str(node.get("nodeCategory") or "").lower()
    if category in {"observability", "iam", "security", "governance"}:
        return "out_of_vcn"
    if any(t in bare_lower for t in (
        "bucket", "objectstorage", "filesystem", "mounttarget",
        "vault", "keymanagement", "cloudguard", "securityzone",
        "loganalytics", "notification", "alarm", "eventrule",
        "dnszone", "customerdnszone", "tagnamespace",
    )):
        return "out_of_vcn"
    return "unknown"


def _security_scope_for_node(node: Node, *, vcn_id: Optional[str]) -> Optional[str]:
    # Overlay pattern removed — security/IAM items render in their own lanes
    return None


def _concept_id(
    compartment_id: str,
    lane: str,
    label: str,
    placement: str,
    security_scope: Optional[str],
) -> str:
    scope = security_scope or "none"
    base = f"{compartment_id}:{lane}:{placement}:{scope}:{label}".lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base[:96] if base else "concept"


def _friendly_type(value: str) -> str:
    if not value:
        return ""
    if "." in value:
        value = value.split(".")[-1]
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    return spaced.replace("_", " ").strip()


def _sanitize_label(value: str) -> str:
    if not value:
        return ""
    if "ocid1" in value:
        return "Redacted"
    cleaned = value
    cleaned = re.sub(r"\(n=[^)]*\)", "", cleaned)
    cleaned = re.sub(r"\d{4}-\d{2}-\d{2}(?:[T _-]?\d{2}[:_-]?\d{2}[:_-]?\d{2})?", "", cleaned)
    cleaned = re.sub(r"\d{8,14}", "", cleaned)
    cleaned = re.sub(r"[-_ ]{2,}", " ", cleaned)
    return cleaned.strip(" -_") or value
