from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .normalize.schema import resolve_output_paths
from .normalize.transform import group_workload_candidates

REPORT_GUIDELINES_PATHS = ("docs/report_guidelines.md",)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _truncate(s: str, max_len: int = 240) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _counts_by_key(records: Iterable[Dict[str, Any]], key: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in records:
        v = str(r.get(key) or "")
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


_ENRICH_ERROR_CATEGORY_ORDER = (
    "NOT_AUTHORIZED",
    "NOT_FOUND",
    "THROTTLING",
    "SERVICE_ERROR",
    "OTHER",
)
_ENRICH_ERROR_CATEGORY_LABELS = {
    "NOT_AUTHORIZED": "NotAuthorized",
    "NOT_FOUND": "NotFound",
    "THROTTLING": "Throttling",
    "SERVICE_ERROR": "ServiceError",
    "OTHER": "Other",
}


def _classify_enrich_error(msg: str) -> str:
    text = (msg or "").strip().lower()
    if not text:
        return "OTHER"
    # OCI SDK sometimes returns NotAuthorizedOrNotFound; treat as NotAuthorized to avoid under-reporting IAM gaps.
    if "notauthorizedornotfound" in text:
        return "NOT_AUTHORIZED"
    if any(
        token in text
        for token in (
            "notauthorized",
            "not authorized",
            "unauthorized",
            "forbidden",
            "not authenticated",
            "authorization failed",
            "status: 401",
            "status 401",
            "status: 403",
            "status 403",
        )
    ):
        return "NOT_AUTHORIZED"
    if any(
        token in text
        for token in (
            "notfound",
            "not found",
            "status: 404",
            "status 404",
            "no such",
            "does not exist",
        )
    ):
        return "NOT_FOUND"
    if any(
        token in text
        for token in (
            "toomanyrequests",
            "too many requests",
            "throttle",
            "throttl",
            "rate limit",
            "limit exceeded",
            "status: 429",
            "status 429",
        )
    ):
        return "THROTTLING"
    if any(
        token in text
        for token in (
            "serviceerror",
            "internal server error",
            "service unavailable",
            "bad gateway",
            "status: 500",
            "status 500",
            "status: 502",
            "status 502",
            "status: 503",
            "status 503",
            "status: 504",
            "status 504",
        )
    ):
        return "SERVICE_ERROR"
    return "OTHER"


def _summarize_enrich_errors(
    records: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    by_category: Dict[str, int] = {k: 0 for k in _ENRICH_ERROR_CATEGORY_ORDER}
    by_category_types: Dict[str, Dict[str, int]] = {k: {} for k in _ENRICH_ERROR_CATEGORY_ORDER}
    total = 0
    for r in records:
        if str(r.get("enrichStatus") or "") != "ERROR":
            continue
        total += 1
        msg = str(r.get("enrichError") or "")
        category = _classify_enrich_error(msg)
        by_category[category] = by_category.get(category, 0) + 1
        rtype = _record_type(r)
        if rtype:
            cat_types = by_category_types.setdefault(category, {})
            cat_types[rtype] = cat_types.get(rtype, 0) + 1
    return {
        "total": total,
        "by_category": by_category,
        "by_category_types": by_category_types,
    }


def _norm_name(s: Optional[str]) -> str:
    return (s or "").strip()


def _record_name(record: Dict[str, Any]) -> str:
    name = _norm_name(str(record.get("displayName") or ""))
    if name:
        return name
    details = record.get("details") or {}
    metadata = details.get("metadata") or {}
    name2 = _norm_name(str(metadata.get("display_name") or metadata.get("displayName") or metadata.get("name") or ""))
    return name2


def _record_type(record: Dict[str, Any]) -> str:
    return str(record.get("resourceType") or "")


def _record_region(record: Dict[str, Any]) -> str:
    return str(record.get("region") or "")


def _record_compartment_id(record: Dict[str, Any]) -> str:
    return str(record.get("compartmentId") or "")


def _record_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    details = record.get("details") or {}
    md = details.get("metadata") or {}
    return md if isinstance(md, dict) else {}


def _compartment_name_map(records: Sequence[Dict[str, Any]]) -> Dict[str, str]:
    # Best-effort mapping using discovered Compartment resources.
    out: Dict[str, str] = {}
    for r in records:
        if _record_type(r) != "Compartment":
            continue
        ocid = str(r.get("ocid") or "")
        name = _record_name(r)
        if ocid and name:
            out[ocid] = name
    return out


def _compartment_alias_map(compartment_ids: Sequence[str]) -> Dict[str, str]:
    # Deterministic aliasing to avoid printing raw OCIDs in the main report.
    ids = sorted({cid for cid in compartment_ids if cid})
    return {cid: f"Compartment-{i:02d}" for i, cid in enumerate(ids, start=1)}


def _compartment_label(
    compartment_id: str,
    *,
    alias_by_id: Dict[str, str],
    name_by_id: Dict[str, str],
) -> str:
    cid = str(compartment_id or "")
    alias = alias_by_id.get(cid, "Compartment")
    name = name_by_id.get(cid, "")
    if name:
        return f"{name} ({alias})"
    return alias


def _infer_subnet_exposure(metadata: Dict[str, Any]) -> str:
    # OCI Subnet has prohibit_public_ip_on_vnic. If False, instances may get public IPs.
    v = metadata.get("prohibit_public_ip_on_vnic")
    if not isinstance(v, bool):
        v = metadata.get("prohibitPublicIpOnVnic")
    if isinstance(v, bool):
        return "Private" if v else "Public"
    return "Unknown"


def _infer_subnet_exposure_from_name(name: str) -> Optional[str]:
    n = (name or "").lower()
    if "public" in n:
        return "Public"
    if "private" in n:
        return "Private"
    return None


def _infer_compartment_role_hint(name: str) -> Optional[str]:
    n = (name or "").lower()
    if not n:
        return None
    if "sandbox" in n or "demo" in n or "lab" in n:
        return "sandbox/dev"
    if "prod" in n or "production" in n:
        return "production"
    if "shared" in n or "platform" in n:
        return "shared services"
    if "network" in n or "vcn" in n:
        return "networking"
    if "security" in n or "sec" in n or "guard" in n:
        return "security"
    if "data" in n or "db" in n:
        return "data"
    return None


def _describe_workload(name: str, records: Sequence[Dict[str, Any]]) -> str:
    # Short, deterministic description using only observed resource types / naming.
    types = {_record_type(r) for r in records if _record_type(r)}
    n = (name or "").lower()
    media_types = {
        "MediaWorkflow",
        "StreamCdnConfig",
        "StreamDistributionChannel",
        "StreamPackagingConfig",
        "MediaAsset",
    }
    if types.intersection(media_types) or "media" in n or "stream" in n or "cdn" in n:
        return "Media/streaming workflow components"
    if "edge" in n and "Instance" in types:
        return "Edge compute component (VM-centric)"
    if "dns" in n or "CustomerDnsZone" in types or "DnsResolver" in types:
        return "Networking/DNS components"
    if "Instance" in types:
        return "Compute-centric component"
    if "Bucket" in types:
        return "Data/storage-centric component"
    return "Workload cluster inferred from names/tags"


def _summarize_policy_name(name: str) -> Optional[str]:
    # Reader-friendly, name-derived hint (no statement parsing).
    n = (name or "").lower()
    if not n:
        return None
    if "object" in n or "bucket" in n:
        return "Object Storage access"
    if "media" in n or "stream" in n or "speech" in n:
        return "Media/AI service prerequisites or access"
    if "network" in n or "vcn" in n:
        return "Networking access"
    if "read" in n:
        return "Read access"
    if "manage" in n or "admin" in n:
        return "Administrative access"
    return None


def _infer_bucket_purpose(name: str) -> Optional[str]:
    n = (name or "").lower()
    if not n:
        return None
    # Conservative keyword-based hints only.
    if "log" in n or "audit" in n:
        return "logs"
    if "backup" in n or "bkp" in n or "snapshot" in n:
        return "backups"
    if "media" in n or "stream" in n or "vod" in n:
        return "media/content"
    if "tmp" in n or "temp" in n:
        return "temporary"
    return None


def _top_n(d: Dict[str, int], n: int) -> List[Tuple[str, int]]:
    return sorted(((k, int(v)) for k, v in d.items()), key=lambda kv: (-kv[1], kv[0]))[:n]


def _md_cell(value: str) -> str:
    # Keep tables robust across Markdown renderers (Obsidian/CommonMark).
    # - Escape pipe characters to avoid accidental column splits.
    # - Replace newlines with <br> to keep rows intact.
    # - Strip outer whitespace for stability.
    v = (value or "").replace("\n", "<br>").strip()
    v = v.replace("|", "\\|")
    return v


def _md_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> List[str]:
    # Minimal Markdown table helper (deterministic; no alignment tricks).
    hdr = [_md_cell(str(h)) for h in headers]
    out: List[str] = []
    out.append("| " + " | ".join(hdr) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for r in rows:
        rr = [_md_cell(str(c)) for c in r]
        out.append("| " + " | ".join(rr) + " |")
    return out


def _short_id_from_ocid(ocid: str) -> str:
    # Stable, non-reversible identifier to help correlate report rows with CSV rows
    # without printing raw OCIDs.
    v = (ocid or "").strip()
    if not v:
        return ""
    return hashlib.sha1(v.encode("utf-8")).hexdigest()[:8]


def _count_csv_rows(path: Path) -> Optional[int]:
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            return sum(1 for _ in reader)
    except Exception:
        return None


def _read_jsonl(path: Path, *, max_rows: int = 50_000) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= max_rows:
                    break
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if isinstance(obj, dict):
                    out.append(obj)
    except Exception:
        return []
    return out


def _graph_artifact_summary(outdir: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not outdir:
        return None
    paths = resolve_output_paths(outdir)
    nodes_path = paths.graph_nodes_jsonl
    edges_path = paths.graph_edges_jsonl
    if not nodes_path.is_file() or not edges_path.is_file():
        return None

    nodes = _read_jsonl(nodes_path)
    edges = _read_jsonl(edges_path)
    if not nodes and not edges:
        return None

    node_ids = {str(n.get("nodeId") or "") for n in nodes if str(n.get("nodeId") or "")}

    node_type_counts: Dict[str, int] = {}
    node_cat_counts: Dict[str, int] = {}
    for n in nodes:
        nt = str(n.get("nodeType") or "")
        nc = str(n.get("nodeCategory") or "")
        if nt:
            node_type_counts[nt] = node_type_counts.get(nt, 0) + 1
        if nc:
            node_cat_counts[nc] = node_cat_counts.get(nc, 0) + 1

    rel_counts: Dict[str, int] = {}
    endpoints_ok = 0
    total_edges = 0
    for e in edges:
        rt = str(e.get("relation_type") or "")
        if rt:
            rel_counts[rt] = rel_counts.get(rt, 0) + 1
        src = str(e.get("source_ocid") or "")
        dst = str(e.get("target_ocid") or "")
        total_edges += 1
        if src in node_ids and dst in node_ids:
            endpoints_ok += 1

    return {
        "nodes_path": str(nodes_path),
        "edges_path": str(edges_path),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_type_counts": node_type_counts,
        "node_category_counts": node_cat_counts,
        "relation_type_counts": rel_counts,
        "endpoints_ok": endpoints_ok,
        "total_edges": total_edges,
        "nodes": nodes,
        "edges": edges,
    }


def _graph_health_summary(graph_summary: Dict[str, Any]) -> Dict[str, Any]:
    nodes = graph_summary.get("nodes") or []
    edges = graph_summary.get("edges") or []
    node_by_id: Dict[str, Dict[str, Any]] = {str(n.get("nodeId") or ""): n for n in nodes if n.get("nodeId")}

    def _label(node: Dict[str, Any]) -> str:
        name = str(node.get("name") or "").strip()
        ocid = str(node.get("nodeId") or "")
        suffix = _short_id_from_ocid(ocid)
        if name:
            return f"{name} ({suffix})" if suffix else name
        return f"{str(node.get('nodeType') or 'Resource')} {suffix}".strip()

    route_table_sources: Set[str] = set()
    gateway_sources: Set[str] = set()
    gateway_types = {
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
    }
    for e in edges:
        rel = str(e.get("relation_type") or "")
        src = str(e.get("source_ocid") or "")
        if not src:
            continue
        if rel == "USES_ROUTE_TABLE":
            route_table_sources.add(src)
        if rel == "IN_VCN":
            src_node = node_by_id.get(src)
            if src_node and str(src_node.get("nodeType") or "") in gateway_types:
                gateway_sources.add(src)

    gateway_vcn_ids: Set[str] = set()
    for e in edges:
        rel = str(e.get("relation_type") or "")
        if rel != "IN_VCN":
            continue
        src = str(e.get("source_ocid") or "")
        dst = str(e.get("target_ocid") or "")
        if src in gateway_sources and dst:
            gateway_vcn_ids.add(dst)

    anomalies: List[str] = []
    for n in nodes:
        if str(n.get("nodeType") or "") != "Subnet":
            continue
        subnet_id = str(n.get("nodeId") or "")
        if subnet_id and subnet_id not in route_table_sources:
            anomalies.append(f"Subnet missing route table association: {_label(n)}.")

    for n in nodes:
        if str(n.get("nodeType") or "") != "Vcn":
            continue
        vcn_id = str(n.get("nodeId") or "")
        if vcn_id and vcn_id not in gateway_vcn_ids:
            anomalies.append(f"VCN has no attached gateways: {_label(n)}.")

    return {
        "anomalies": anomalies,
    }


def _pct(n: int, d: int) -> str:
    if d <= 0:
        return "0%"
    return f"{int(round((n / d) * 100.0))}%"


def _record_workload_groups(records: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    return {k: list(v) for k, v in group_workload_candidates(records).items()}


def build_architecture_facts(
    *,
    discovered_records: Sequence[Dict[str, Any]],
    subscribed_regions: Sequence[str],
    requested_regions: Optional[Sequence[str]],
    excluded_regions: Sequence[Dict[str, str]],
    metrics: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    # Compact, redaction-friendly facts intended for optional GenAI summary.
    types = [_record_type(r) for r in discovered_records if _record_type(r)]
    type_counts: Dict[str, int] = {}
    for t in types:
        type_counts[t] = type_counts.get(t, 0) + 1

    comp_counts: Dict[str, int] = {}
    for r in discovered_records:
        cid = _record_compartment_id(r)
        if not cid:
            continue
        comp_counts[cid] = comp_counts.get(cid, 0) + 1

    name_by_comp = _compartment_name_map(discovered_records)
    alias_by_comp = _compartment_alias_map(list(comp_counts.keys()))
    top_comp = _top_n(comp_counts, 8)
    top_comp_pretty = [
        f"{_compartment_label(cid, alias_by_id=alias_by_comp, name_by_id=name_by_comp)}: {count}"
        for cid, count in top_comp
    ]

    workloads = _record_workload_groups(discovered_records)

    facts: Dict[str, Any] = {
        "Scope": "queried resources only (see Execution Metadata for query)",
        "Regions (subscribed)": ", ".join(list(subscribed_regions)),
        "Regions (requested)": ", ".join(list(requested_regions)) if requested_regions else "(all subscribed)",
        "Regions (excluded)": ", ".join(sorted({str(x.get('region') or '') for x in excluded_regions if x.get('region')}))
        if excluded_regions
        else "none",
        "Total records": str(len(discovered_records)),
        "Top resource types": ", ".join([f"{k}={v}" for k, v in _top_n(type_counts, 10)]),
        "Top compartments": "; ".join(top_comp_pretty) if top_comp_pretty else "(none)",
        "Workload candidates": ", ".join(list(workloads.keys())[:8]) if workloads else "(none confidently inferred)",
    }
    if metrics and isinstance(metrics, dict):
        cbes = metrics.get("counts_by_enrich_status") or {}
        if isinstance(cbes, dict) and cbes:
            facts["Enrichment status"] = ", ".join([f"{k}={cbes[k]}" for k in sorted(cbes.keys())])
    return facts


def render_run_report_md(
    *,
    status: str,
    cfg_dict: Dict[str, Any],
    started_at: str,
    finished_at: str,
    executive_summary: Optional[str] = None,
    executive_summary_error: Optional[str] = None,
    subscribed_regions: List[str],
    requested_regions: Optional[List[str]],
    excluded_regions: List[Dict[str, str]],
    discovered_records: List[Dict[str, Any]],
    metrics: Optional[Dict[str, Any]],
    diff_warning: Optional[str] = None,
    fatal_error: Optional[str] = None,
    diagram_summary: Optional[Dict[str, Any]] = None,
) -> str:
    duration_note = ""
    try:
        start_dt = datetime.fromisoformat(started_at)
        end_dt = datetime.fromisoformat(finished_at)
        duration = end_dt - start_dt
        duration_note = f"Duration: {duration}\n"
    except Exception:
        pass

    # ---------- Architecture assessment (primary report) ----------
    lines: List[str] = []
    lines.append("# OCI Inventory Architectural Assessment")
    lines.append("")

    # Audience note: keep it short, formal, and factual.
    lines.append(
        "This report summarizes the OCI resources **observed in scope** by a read-only inventory run and presents a lightweight architectural view "
        "(tenancy partitioning, network layout, workload/service groupings, data stores, and governance signals). "
        "It concludes with an **Execution Metadata** appendix containing the original run details."
    )
    lines.append("")

    types_in_scope = {_record_type(r) for r in discovered_records if _record_type(r)}
    counts_by_region = _counts_by_key(discovered_records, "region")
    regions_observed = [r for r in counts_by_region.keys() if r]

    # Compartment labeling (avoid raw OCIDs in the main body)
    comp_ids = [_record_compartment_id(r) for r in discovered_records if _record_compartment_id(r)]
    comp_counts: Dict[str, int] = {}
    for cid in comp_ids:
        comp_counts[cid] = comp_counts.get(cid, 0) + 1
    name_by_comp = _compartment_name_map(discovered_records)
    alias_by_comp = _compartment_alias_map(list(comp_counts.keys()))

    # Workload clustering (best-effort)
    workloads = _record_workload_groups(discovered_records)

    # Core resource counts
    vcn_recs = [r for r in discovered_records if _record_type(r) == "Vcn"]
    subnet_recs = [r for r in discovered_records if _record_type(r) == "Subnet"]
    igw_recs = [r for r in discovered_records if _record_type(r) == "InternetGateway"]
    nat_recs = [r for r in discovered_records if _record_type(r) == "NatGateway"]
    sgw_recs = [r for r in discovered_records if _record_type(r) == "ServiceGateway"]
    nsg_recs = [r for r in discovered_records if _record_type(r) == "NetworkSecurityGroup"]
    inst_recs = [r for r in discovered_records if _record_type(r) == "Instance"]
    bucket_recs = [r for r in discovered_records if _record_type(r) == "Bucket"]
    vol_recs = [r for r in discovered_records if _record_type(r) in {"BootVolume", "BlockVolume", "Volume"}]
    policy_recs = [r for r in discovered_records if _record_type(r) == "Policy"]
    log_group_recs = [r for r in discovered_records if _record_type(r) == "LogGroup"]
    loga_entity_recs = [r for r in discovered_records if _record_type(r) == "LogAnalyticsEntity"]

    media_types = {
        "MediaWorkflow",
        "StreamCdnConfig",
        "StreamDistributionChannel",
        "StreamPackagingConfig",
    }
    media_recs = [r for r in discovered_records if _record_type(r) in media_types]

    # At-a-glance table (CIO-friendly, deterministic)
    ok = 0
    not_impl = 0
    err = 0
    if metrics and isinstance(metrics, dict):
        cbes = metrics.get("counts_by_enrich_status") or {}
        if isinstance(cbes, dict):
            ok = int(cbes.get("OK", 0) or 0)
            not_impl = int(cbes.get("NOT_IMPLEMENTED", 0) or 0)
            err = int(cbes.get("ERROR", 0) or 0)
    total_cov = ok + not_impl + err

    scope_regions = regions_observed or (list(requested_regions) if requested_regions else list(subscribed_regions))
    scope_regions_txt = ", ".join(scope_regions) if scope_regions else "(none)"

    public_subnets = 0
    private_subnets = 0
    unknown_subnets = 0
    for sn in subnet_recs:
        md = _record_metadata(sn)
        exposure = _infer_subnet_exposure(md)
        if exposure == "Unknown":
            by_name = _infer_subnet_exposure_from_name(_record_name(sn))
            exposure = by_name or "Unknown"
        if exposure.startswith("Public"):
            public_subnets += 1
        elif exposure.startswith("Private"):
            private_subnets += 1
        else:
            unknown_subnets += 1

    lines.append("## At a Glance")
    lines.append("")
    lines.extend(
        _md_table(
            ["Metric", "Value"],
            [
                ["Status", f"**{status}**"],
                ["Regions in scope", scope_regions_txt],
                ["Resources discovered", str(len(discovered_records))],
                ["Compartments observed", str(len(comp_counts))],
                ["Network", f"VCNs={len(vcn_recs)}, Subnets={len(subnet_recs)} (Public={public_subnets}, Private={private_subnets}, Unknown={unknown_subnets})"],
                ["Compute", f"Instances={len(inst_recs)}"],
                ["Data", f"Buckets={len(bucket_recs)}, Volumes={len(vol_recs)}"],
                ["Governance", f"Policies={len(policy_recs)}"],
                ["Observability", f"Log Groups={len(log_group_recs)}, Log Analytics Entities={len(loga_entity_recs)}"],
                ["Enrichment coverage", f"OK={ok}, NOT_IMPLEMENTED={not_impl}, ERROR={err} (OK%={_pct(ok, total_cov)})"],
            ],
        )
    )
    lines.append("")

    # Graph artifacts (nodes/edges) summary, if present.
    outdir = Path(str(cfg_dict.get("outdir") or "")).expanduser() if cfg_dict.get("outdir") else None
    paths = resolve_output_paths(outdir) if outdir else None
    graph_summary = _graph_artifact_summary(outdir)
    if graph_summary:
        lines.append("## Graph Artifacts (Summary)")
        lines.append(
            "This section summarizes `graph/graph_nodes.jsonl` and `graph/graph_edges.jsonl` generated for this run."
        )
        lines.append("")

        node_rows: List[List[str]] = []
        for k, v in _top_n(graph_summary.get("node_category_counts", {}), 10):
            node_rows.append([k or "(unknown)", str(v)])
        if node_rows:
            lines.append("Node categories:")
            lines.append("")
            lines.extend(_md_table(["Category", "Count"], node_rows))
            lines.append("")

        type_rows: List[List[str]] = []
        for k, v in _top_n(graph_summary.get("node_type_counts", {}), 10):
            type_rows.append([k or "(unknown)", str(v)])
        if type_rows:
            lines.append("Top node types:")
            lines.append("")
            lines.extend(_md_table(["Node type", "Count"], type_rows))
            lines.append("")

        rel_rows: List[List[str]] = []
        for k, v in _top_n(graph_summary.get("relation_type_counts", {}), 20):
            rel_rows.append([k or "(unknown)", str(v)])
        if rel_rows:
            lines.append("Edge relation types:")
            lines.append("")
            lines.extend(_md_table(["Relation", "Count"], rel_rows))
            lines.append("")

        endpoints_ok = int(graph_summary.get("endpoints_ok") or 0)
        total_edges = int(graph_summary.get("total_edges") or 0)
        lines.append(f"Graph integrity: {endpoints_ok}/{total_edges} edges reference known node IDs.")
        lines.append("")

    # Graph Health
    lines.append("## Graph Health")
    if graph_summary:
        endpoints_ok = int(graph_summary.get("endpoints_ok") or 0)
        total_edges = int(graph_summary.get("total_edges") or 0)
        lines.append(f"Edge endpoints valid: {endpoints_ok}/{total_edges}.")
        health = _graph_health_summary(graph_summary)
        anomalies = health.get("anomalies") or []
        if anomalies:
            lines.append("Detected anomalies:")
            for item in anomalies:
                lines.append(f"- {item}")
        else:
            lines.append("No anomalies detected.")
    else:
        lines.append("Graph artifacts not available for this run.")
    lines.append("")

    # Executive Summary (architecture)
    lines.append("## Executive Summary")
    if executive_summary:
        # When enabled, GenAI summary is expected to be architecture-focused and redacted.
        summary = executive_summary.strip()
        # Avoid duplicated headings when the model includes its own section header.
        for prefix in ("## Executive Summary", "# Executive Summary"):
            if summary.startswith(prefix):
                summary = summary[len(prefix) :].lstrip("\n ")
                break
        lines.append(summary)
    else:
        region_phrase = (
            ", ".join(regions_observed)
            if regions_observed
            else (
                ", ".join(list(requested_regions))
                if requested_regions
                else ", ".join(list(subscribed_regions))
            )
        )
        lines.append(
            f"This inventory scope contains **{len(discovered_records)}** resources across **{len(regions_observed) or len(requested_regions or []) or len(subscribed_regions)}** region(s) ({region_phrase}). "
            f"The environment includes **{len(vcn_recs)}** VCN(s), **{len(inst_recs)}** compute instance(s), and **{len(bucket_recs)}** Object Storage bucket(s)."
        )
        if media_recs:
            lines.append(
                f"Media Services resources are present (**{len(media_recs)}** total), suggesting a streaming/media workflow component within this scope."
            )
    if executive_summary_error and not executive_summary:
        # Keep the primary report clean; stash the error detail in Execution Metadata below.
        lines.append("")
        lines.append("(GenAI executive summary was not available for this run.)")
    lines.append("")

    # Tenancy & Compartment Overview
    lines.append("## Tenancy & Compartment Overview")
    if comp_counts:
        lines.append("Observed resource distribution by compartment (best-effort; based on `compartmentId` in results).")
        lines.append("")

        # Build per-compartment top types
        types_by_comp: Dict[str, Dict[str, int]] = {}
        for r in discovered_records:
            cid = _record_compartment_id(r)
            if not cid:
                continue
            rt = _record_type(r)
            if not rt:
                continue
            bucket = types_by_comp.setdefault(cid, {})
            bucket[rt] = bucket.get(rt, 0) + 1

        rows: List[List[str]] = []
        for cid, count in _top_n(comp_counts, 20):
            name = name_by_comp.get(cid, "")
            role = _infer_compartment_role_hint(name)
            label = _compartment_label(cid, alias_by_id=alias_by_comp, name_by_id=name_by_comp)
            top_types = ", ".join([f"{k}={v}" for k, v in _top_n(types_by_comp.get(cid, {}), 5)])
            rows.append([label, role or "(not inferred)", str(count), top_types or "(none)"])

        lines.extend(_md_table(["Compartment", "Role hint", "Resources", "Top resource types"], rows))
    else:
        lines.append("- No compartment IDs were present in the discovered records.")
    lines.append("")

    # Network Architecture
    lines.append("## Network Architecture")
    lines.append("Diagram artifacts (generated in the output directory):")
    lines.append("- `graph/graph_nodes.jsonl` / `graph/graph_edges.jsonl` (graph data)")
    lines.append("- `diagrams/**/diagram*.mmd` (architectural projections, if enabled)")
    lines.append("")

    diagram_summary = diagram_summary or {}
    skipped = diagram_summary.get("skipped") or []
    split = diagram_summary.get("split") or []
    violations = diagram_summary.get("violations") or []
    if skipped or split or violations:
        def _reason_label(reason: str) -> str:
            mapping = {
                "exceeds_mermaid_limit": "exceeds Mermaid size limit",
                "split_mermaid_limit": "split to stay within Mermaid limit",
                "single_node_exceeds_limit": "single node exceeds Mermaid limit",
                "split_region": "split by region",
                "split_compartment": "split by compartment",
            }
            return mapping.get(reason, reason.replace("_", " "))

        def _parts_label(parts: List[str], *, max_items: int = 5) -> str:
            if not parts:
                return "(none)"
            if len(parts) <= max_items:
                return ", ".join(parts)
            return ", ".join(parts[:max_items]) + f", (+{len(parts) - max_items} more)"

        lines.append("Diagram generation notes (best-effort):")
        lines.append("")
        if violations:
            violation_rows: List[List[str]] = []
            for item in sorted(violations, key=lambda x: str(x.get("diagram") or "")):
                diagram = str(item.get("diagram") or "")
                rule = str(item.get("rule") or "")
                detail = str(item.get("detail") or "")
                violation_rows.append([diagram, rule or "(unknown)", detail or "(none)"])
            lines.extend(_md_table(["Diagram", "Rule", "Detail"], violation_rows))
            lines.append("")
        if split:
            split_rows: List[List[str]] = []
            for item in sorted(split, key=lambda x: str(x.get("diagram") or "")):
                diagram = str(item.get("diagram") or "")
                parts = [str(p) for p in (item.get("parts") or [])]
                reason = _reason_label(str(item.get("reason") or ""))
                split_rows.append([diagram, _parts_label(parts), reason])
            lines.extend(_md_table(["Diagram", "Split outputs", "Reason"], split_rows))
            lines.append("")
        if skipped:
            skip_rows: List[List[str]] = []
            for item in sorted(skipped, key=lambda x: str(x.get("diagram") or "")):
                diagram = str(item.get("diagram") or "")
                reason = _reason_label(str(item.get("reason") or ""))
                size = str(item.get("size") or "")
                limit = str(item.get("limit") or "")
                size_label = f"{size}/{limit}" if size and limit else "(unknown)"
                skip_rows.append([diagram, reason, size_label])
            lines.extend(_md_table(["Diagram", "Reason", "Size/Limit"], skip_rows))
            lines.append("")

    # Graph-derived connectivity (only if edges include relationships beyond IN_COMPARTMENT)
    if graph_summary:
        rel_counts = graph_summary.get("relation_type_counts") or {}
        if isinstance(rel_counts, dict):
            non_membership = sorted([k for k in rel_counts.keys() if k and k != "IN_COMPARTMENT"])
        else:
            non_membership = []

        if non_membership:
            # Build a lookup for labeling without printing OCIDs.
            nodes = graph_summary.get("nodes") or []
            node_by_id: Dict[str, Dict[str, Any]] = {}
            for n in nodes:
                nid = str(n.get("nodeId") or "")
                if nid:
                    node_by_id[nid] = n

            def _label_for(nid: str) -> str:
                n = node_by_id.get(nid, {})
                name = str(n.get("name") or "")
                nt = str(n.get("nodeType") or "")
                sid = _short_id_from_ocid(nid)
                if name and nt:
                    return f"{name} ({nt}, {sid})"
                if name:
                    return f"{name} ({sid})"
                return sid or "(unknown)"

            conn_rows: List[List[str]] = []
            edges = graph_summary.get("edges") or []
            shown = 0
            for e in edges:
                rt = str(e.get("relation_type") or "")
                if not rt or rt == "IN_COMPARTMENT":
                    continue
                src = str(e.get("source_ocid") or "")
                dst = str(e.get("target_ocid") or "")
                conn_rows.append([rt, _label_for(src), _label_for(dst)])
                shown += 1
                if shown >= 25:
                    break

            if conn_rows:
                lines.append("Graph-derived connectivity (sample; OCIDs omitted):")
                lines.append("")
                lines.extend(_md_table(["Relation", "Source", "Target"], conn_rows))
                if len(edges) > shown:
                    lines.append("(Truncated.)")
                lines.append("")
        else:
            # Keep it as a single, clear statement to avoid noise.
            lines.append("Graph-derived connectivity: not available (only IN_COMPARTMENT edges were generated for this run).")
            lines.append("")

    if not vcn_recs and not subnet_recs and not (igw_recs or nat_recs or sgw_recs):
        lines.append("No core networking resources were observed in this inventory scope.")
        lines.append("")
    else:
        # Build per-VCN summary
        vcn_by_id: Dict[str, Dict[str, Any]] = {str(r.get("ocid") or ""): r for r in vcn_recs if str(r.get("ocid") or "")}

        subnets_by_vcn: Dict[str, List[Dict[str, Any]]] = {}
        for sn in subnet_recs:
            md = _record_metadata(sn)
            vcn_id = str(md.get("vcn_id") or md.get("vcnId") or "")
            subnets_by_vcn.setdefault(vcn_id, []).append(sn)

        rows: List[List[str]] = []
        for vcn in sorted(vcn_recs, key=lambda x: (_record_region(x), _record_name(x))):
            md = _record_metadata(vcn)
            vcn_id = str(vcn.get("ocid") or "")
            cidr = md.get("cidr_block") or md.get("cidrBlock")
            cidrs = md.get("cidr_blocks") or md.get("cidrBlocks")
            cidr_txt = ""
            if isinstance(cidr, str) and cidr:
                cidr_txt = cidr
            elif isinstance(cidrs, list) and cidrs:
                cidr_txt = ", ".join([str(x) for x in cidrs if x])

            subs = subnets_by_vcn.get(vcn_id, [])
            pub = 0
            priv = 0
            unk = 0
            for sn in subs:
                md_sn = _record_metadata(sn)
                exposure = _infer_subnet_exposure(md_sn)
                if exposure == "Unknown":
                    by_name = _infer_subnet_exposure_from_name(_record_name(sn))
                    exposure = by_name or "Unknown"
                if exposure.startswith("Public"):
                    pub += 1
                elif exposure.startswith("Private"):
                    priv += 1
                else:
                    unk += 1

            gws = []
            if igw_recs:
                gws.append("IGW")
            if nat_recs:
                gws.append("NAT")
            if sgw_recs:
                gws.append("ServiceGW")
            gw_txt = ", ".join(gws) if gws else "(none observed)"
            rows.append([
                _record_name(vcn) or "(unnamed)",
                _record_region(vcn) or "(unknown)",
                cidr_txt or "(unknown)",
                f"{len(subs)} (Public={pub}, Private={priv}, Unknown={unk})",
                gw_txt,
            ])

        if rows:
            lines.append("VCN summary (best-effort; subnet-to-VCN mapping requires subnet metadata):")
            lines.append("")
            lines.extend(_md_table(["VCN", "Region", "CIDR(s)", "Subnets", "Gateways"], rows))
            lines.append("")

        if subnet_recs:
            # Provide a short subnet list for quick validation.
            vcn_name_by_id = {vid: _record_name(vcn_by_id.get(vid, {})) for vid in vcn_by_id.keys()}
            sub_rows: List[List[str]] = []
            for sn in sorted(subnet_recs, key=lambda x: (_record_region(x), _record_name(x))):
                md = _record_metadata(sn)
                exposure = _infer_subnet_exposure(md)
                if exposure == "Unknown":
                    by_name = _infer_subnet_exposure_from_name(_record_name(sn))
                    if by_name:
                        exposure = by_name
                vcn_id = str(md.get("vcn_id") or md.get("vcnId") or "")
                vcn_name = vcn_name_by_id.get(vcn_id, "")
                sub_rows.append([
                    _record_name(sn) or "(unnamed)",
                    _record_region(sn) or "(unknown)",
                    exposure,
                    vcn_name or "(unknown)",
                ])
            lines.append("Subnet summary:")
            lines.append("")
            lines.extend(_md_table(["Subnet", "Region", "Exposure", "VCN"], sub_rows[:20]))
            if len(sub_rows) > 20:
                lines.append(f"(Truncated: {len(sub_rows) - 20} more subnets not shown.)")
            lines.append("")

        if nsg_recs:
            lines.append(f"Network Security Groups observed: **{len(nsg_recs)}**")
    lines.append("")

    # Workloads & Services
    lines.append("## Workloads & Services")
    if not workloads:
        lines.append("- No workload clusters could be confidently inferred from names/tags in this scope.")
        lines.append("")
    else:
        lines.append("Workload candidates (grouped by naming and/or tags; only groups with ≥3 resources are shown).")
        lines.append("")

        rows: List[List[str]] = []
        flows: List[str] = []
        shown = 0
        for wname, recs in workloads.items():
            shown += 1
            if shown > 10:
                break

            type_counts: Dict[str, int] = {}
            comp_set: set[str] = set()
            region_set: set[str] = set()
            for rr in recs:
                rt = _record_type(rr)
                if rt:
                    type_counts[rt] = type_counts.get(rt, 0) + 1
                cid = _record_compartment_id(rr)
                if cid:
                    comp_set.add(_compartment_label(cid, alias_by_id=alias_by_comp, name_by_id=name_by_comp))
                reg = _record_region(rr)
                if reg:
                    region_set.add(reg)

            top_types = ", ".join([f"{k}={v}" for k, v in _top_n(type_counts, 6)])
            desc = _describe_workload(wname, recs)
            rows.append([
                wname,
                desc,
                str(len(recs)),
                ", ".join(sorted(region_set)) or "(unknown)",
                ", ".join(sorted(comp_set)) or "(unknown)",
                top_types or "(none)",
            ])

            rt_set = set(type_counts.keys())
            if "Bucket" in rt_set and rt_set.intersection(media_types):
                flows.append(f"- {wname}: Object Storage (buckets) → Media Services (workflow/packaging) → Streaming distribution/CDN")

        lines.extend(_md_table(["Workload", "Description", "Resources", "Regions", "Compartments", "Top resource types"], rows))
        if flows:
            lines.append("")
            lines.append("Observed data flow patterns (type-based; best-effort):")
            lines.extend(flows[:6])
        lines.append("")

    # Data & Storage
    lines.append("## Data & Storage")
    ds_rows: List[List[str]] = []
    if bucket_recs:
        for r in sorted(bucket_recs, key=lambda x: (_record_region(x), _record_name(x))):
            name = _record_name(r) or "(unnamed)"
            comp = _compartment_label(_record_compartment_id(r), alias_by_id=alias_by_comp, name_by_id=name_by_comp)
            hint = _infer_bucket_purpose(name) or "(not inferred)"
            ds_rows.append(["Bucket", name, _record_region(r) or "(unknown)", comp, hint])
    if vol_recs:
        for r in sorted(vol_recs, key=lambda x: (_record_region(x), _record_name(x))):
            name = _record_name(r) or "(unnamed)"
            comp = _compartment_label(_record_compartment_id(r), alias_by_id=alias_by_comp, name_by_id=name_by_comp)
            ds_rows.append([_record_type(r) or "Volume", name, _record_region(r) or "(unknown)", comp, "(n/a)"])

    datastore_types = {
        "AutonomousDatabase",
        "DbSystem",
        "MysqlDbSystem",
        "NoSqlTable",
        "FileSystem",
        "MountTarget",
    }
    datastore_recs = [r for r in discovered_records if _record_type(r) in datastore_types]
    if datastore_recs:
        for r in sorted(datastore_recs, key=lambda x: (_record_region(x), _record_type(x), _record_name(x))):
            name = _record_name(r) or "(unnamed)"
            comp = _compartment_label(_record_compartment_id(r), alias_by_id=alias_by_comp, name_by_id=name_by_comp)
            ds_rows.append([_record_type(r) or "Datastore", name, _record_region(r) or "(unknown)", comp, "(n/a)"])

    if ds_rows:
        lines.append("")
        lines.extend(_md_table(["Type", "Name", "Region", "Compartment", "Purpose hint"], ds_rows[:40]))
        if len(ds_rows) > 40:
            lines.append(f"(Truncated: {len(ds_rows) - 40} more items not shown.)")
    else:
        lines.append("No data/storage resources were observed in this inventory scope.")
    lines.append("")

    # IAM / Policies
    lines.append("## IAM / Policies (Visible)")
    if policy_recs:
        rows: List[List[str]] = []
        for r in sorted(policy_recs, key=lambda x: (_record_compartment_id(x), _record_name(x))):
            md = _record_metadata(r)
            stmts = md.get("statements")
            stmt_count = str(len(stmts)) if isinstance(stmts, list) else "(unknown)"
            comp_label = _compartment_label(_record_compartment_id(r), alias_by_id=alias_by_comp, name_by_id=name_by_comp)
            pname = _record_name(r) or "(unnamed)"
            hint = _summarize_policy_name(pname) or "(not inferred)"
            rows.append([pname, comp_label, stmt_count, hint])
        lines.append("")
        lines.extend(_md_table(["Policy", "Compartment", "Statements", "Summary (name-derived)"], rows))
    else:
        lines.append("- No IAM Policy resources were observed in this scope.")
    lines.append("")

    # Observability / Logging
    lines.append("## Observability / Logging")
    obs_rows: List[List[str]] = []
    for r in sorted(log_group_recs, key=lambda x: (_record_region(x), _record_name(x))):
        comp = _compartment_label(_record_compartment_id(r), alias_by_id=alias_by_comp, name_by_id=name_by_comp)
        obs_rows.append(["LogGroup", _record_name(r) or "(unnamed)", _record_region(r) or "(unknown)", comp])
    for r in sorted(loga_entity_recs, key=lambda x: (_record_region(x), _record_name(x))):
        comp = _compartment_label(_record_compartment_id(r), alias_by_id=alias_by_comp, name_by_id=name_by_comp)
        obs_rows.append(["LogAnalyticsEntity", _record_name(r) or "(unnamed)", _record_region(r) or "(unknown)", comp])

    if obs_rows:
        lines.append("")
        lines.extend(_md_table(["Type", "Name", "Region", "Compartment"], obs_rows[:40]))
        if len(obs_rows) > 40:
            lines.append(f"(Truncated: {len(obs_rows) - 40} more items not shown.)")
    else:
        lines.append("No observability/logging resources were observed in this inventory scope.")
    lines.append("")

    # Risks & Gaps
    lines.append("## Risks & Gaps (Non-blocking)")
    gaps: List[str] = []
    error_summary = _summarize_enrich_errors(discovered_records)
    if excluded_regions:
        gaps.append("One or more regions were excluded due to errors during Resource Search; results may be partial. (Evidence: excluded regions list in Execution Metadata)")
    if metrics:
        cbes = metrics.get("counts_by_enrich_status") or {}
        if isinstance(cbes, dict):
            errors = int(cbes.get("ERROR", 0) or 0)
            not_impl = int(cbes.get("NOT_IMPLEMENTED", 0) or 0)
            if errors:
                gaps.append(
                    f"{errors} record(s) failed enrichment (enrichStatus=ERROR); details are preserved in the exported JSONL. (Evidence: metrics counts_by_enrich_status)"
                )
            if not_impl:
                gaps.append(
                    f"{not_impl} record(s) are present without metadata enrichment (enrichStatus=NOT_IMPLEMENTED); architectural detail may be incomplete for those resource types. (Evidence: metrics counts_by_enrich_status)"
                )

        cbrt = metrics.get("counts_by_resource_type") or {}
        if isinstance(cbrt, dict) and cbrt:
            # Identify common types that were not enriched.
            not_impl_types: Dict[str, int] = {}
            for r in discovered_records:
                if str(r.get("enrichStatus") or "") != "NOT_IMPLEMENTED":
                    continue
                rt = _record_type(r)
                if rt:
                    not_impl_types[rt] = not_impl_types.get(rt, 0) + 1
            if not_impl_types:
                tops = ", ".join([f"{k}={v}" for k, v in _top_n(not_impl_types, 6)])
                gaps.append(f"Top non-enriched resource types (count): {tops}. (Evidence: enrichStatus=NOT_IMPLEMENTED records)")
        if error_summary.get("total"):
            counts = []
            by_category = error_summary.get("by_category") or {}
            for key in _ENRICH_ERROR_CATEGORY_ORDER:
                count = int(by_category.get(key, 0) or 0)
                if count:
                    label = _ENRICH_ERROR_CATEGORY_LABELS.get(key, key)
                    counts.append(f"{label}={count}")
            if counts:
                gaps.append(
                    "Enrichment error categories (count): "
                    + ", ".join(counts)
                    + ". (Evidence: enrichStatus=ERROR records)"
                )
            top_parts: List[str] = []
            by_types = error_summary.get("by_category_types") or {}
            for key in _ENRICH_ERROR_CATEGORY_ORDER:
                type_counts = by_types.get(key) or {}
                if not type_counts:
                    continue
                tops = ", ".join([f"{k}={v}" for k, v in _top_n(type_counts, 3)])
                if tops:
                    label = _ENRICH_ERROR_CATEGORY_LABELS.get(key, key)
                    top_parts.append(f"{label}: {tops}")
            if top_parts:
                gaps.append(
                    "Top error resource types by category (count): "
                    + "; ".join(top_parts)
                    + ". (Evidence: enrichStatus=ERROR records)"
                )

    # Simple, observation-only checks (scoped to the queried inventory).
    if "LoadBalancer" not in types_in_scope:
        gaps.append("No Load Balancer resources were observed in this inventory scope. (Evidence: resource type absent in discovered records)")
    if "Waf" not in types_in_scope and "WebAppFirewall" not in types_in_scope:
        gaps.append("No WAF resources were observed in this inventory scope. (Evidence: resource type absent in discovered records)")
    if inst_recs and "Bastion" not in types_in_scope:
        gaps.append("Compute instances are present but no Bastion resources were observed in this inventory scope. (Evidence: Instance present; Bastion absent)")

    # De-dup and render
    seen_gap: set[str] = set()
    rendered = 0
    for g in gaps:
        gg = g.strip()
        if not gg or gg in seen_gap:
            continue
        seen_gap.add(gg)
        lines.append(f"- {gg}")
        rendered += 1
        if rendered >= 10:
            break
    if rendered == 0:
        lines.append("- No non-blocking gaps were detected from the available inventory signals.")
    lines.append("")

    lines.append("### Coverage Notes")
    lines.append("- This assessment is limited to the query scope and the discovered resource types; missing types may be out of scope or not returned by the search query.")
    if metrics and total_cov:
        lines.append(f"- Enrichment coverage (OK%): {_pct(ok, total_cov)}. Records with NOT_IMPLEMENTED or ERROR may lack architectural metadata details.")
    lines.append("")

    lines.append("### Recommendations (Non-binding)")
    recs: List[str] = []
    if public_subnets > 0 and ("Waf" not in types_in_scope and "WebAppFirewall" not in types_in_scope):
        recs.append("If this VCN hosts internet-facing services, consider adding WAF controls appropriate to the exposure model.")
    if inst_recs and "Bastion" not in types_in_scope:
        recs.append("If SSH/RDP access is required, consider using Bastion or other controlled access patterns instead of direct public administration.")
    if not_impl > 0:
        recs.append("Consider implementing additional enrichers for the most common NOT_IMPLEMENTED resource types to improve architectural fidelity.")
    if error_summary.get("by_category", {}).get("NOT_AUTHORIZED"):
        recs.append(
            "If enrichment errors include NotAuthorized, expand read/inspect IAM permissions for the affected services (for example: Identity, Logging, KMS, Database, OSMH)."
        )
    if error_summary.get("by_category", {}).get("NOT_FOUND"):
        recs.append(
            "If enrichment errors include NotFound, treat them as expected drift (resource deleted) and re-run to confirm."
        )
    if error_summary.get("by_category", {}).get("THROTTLING"):
        recs.append(
            "If enrichment errors include Throttling, reduce `--workers-enrich` or increase `--client-connection-pool-size`."
        )
    if error_summary.get("by_category", {}).get("SERVICE_ERROR"):
        recs.append(
            "If enrichment errors include ServiceError/5xx, retry the run; persistent failures should be recorded as best-effort gaps."
        )
    if not recs:
        recs.append("No non-binding recommendations were derived from the current inventory signals.")
    for r in recs[:6]:
        lines.append(f"- {r}")
    lines.append("")

    # Complete inventory listing (for parity with inventory/inventory.csv)
    lines.append("## Inventory Listing (Complete)")
    lines.append(
        "Complete list of resources discovered in scope (matches the exported `inventory/inventory.csv`; OCIDs omitted)."
    )

    csv_rows: Optional[int] = None
    if paths:
        csv_rows = _count_csv_rows(paths.inventory_csv)
    if csv_rows is not None:
        if csv_rows == len(discovered_records):
            lines.append(f"Rows: {len(discovered_records)} (matches inventory/inventory.csv)")
        else:
            lines.append(
                f"Rows: {len(discovered_records)} (inventory/inventory.csv has {csv_rows}; investigate export/inputs mismatch)"
            )
    else:
        lines.append(f"Rows: {len(discovered_records)}")

    if discovered_records:
        inv_rows: List[List[str]] = []
        for r in sorted(
            discovered_records,
            key=lambda x: (
                _record_type(x) or "",
                _record_name(x) or "",
                _record_region(x) or "",
                _record_compartment_id(x) or "",
            ),
        ):
            comp = _compartment_label(_record_compartment_id(r), alias_by_id=alias_by_comp, name_by_id=name_by_comp)
            inv_rows.append(
                [
                    _short_id_from_ocid(str(r.get("ocid") or "")),
                    _record_type(r) or "(unknown)",
                    _record_name(r) or "(unnamed)",
                    _record_region(r) or "(unknown)",
                    comp,
                    str(r.get("lifecycleState") or "(unknown)"),
                    str(r.get("enrichStatus") or "(unknown)"),
                ]
            )
        lines.append("")
        lines.extend(
            _md_table(
                ["ID", "Type", "Name", "Region", "Compartment", "Lifecycle", "Enrichment"],
                inv_rows,
            )
        )
    else:
        lines.append("No resources were discovered in this inventory scope.")
    lines.append("")

    # ---------- Execution metadata (preserved run-log details) ----------
    lines.append("## Execution Metadata")
    lines.append(f"- Status: **{status}**")
    lines.append(f"- Started (UTC): {started_at}")
    lines.append(f"- Finished (UTC): {finished_at}")
    if duration_note:
        lines.append(f"- {duration_note.strip()}")
    lines.append("")

    if executive_summary is None and executive_summary_error:
        lines.append("### GenAI Summary")
        lines.append(f"(GenAI summary generation failed: {_truncate(str(executive_summary_error or ''), 300)})")
        lines.append("")
    elif executive_summary:
        # Summary is already embedded above; still acknowledge it was generated.
        lines.append("### GenAI Summary")
        lines.append("(Embedded in Executive Summary.)")
        lines.append("")

    lines.append("### Steps Executed")
    lines.append("- Resolved authentication context")
    lines.append("- Discovered subscribed regions")
    lines.append("- Executed OCI Resource Search per region (Structured Search)")
    lines.append("- Normalized records and attached region metadata")
    lines.append("- Enriched records using read-only OCI SDK calls")
    lines.append("- Exported artifacts (JSONL + CSV)")
    lines.append("")

    lines.append("### Run Configuration")
    # Keep this human-readable; do not dump every internal field.
    lines.append(f"- Auth: `{cfg_dict.get('auth')}`")
    if cfg_dict.get("profile"):
        lines.append(f"- Profile: `{cfg_dict.get('profile')}`")
    if cfg_dict.get("tenancy_ocid"):
        lines.append(f"- Tenancy OCID: `{cfg_dict.get('tenancy_ocid')}`")
    lines.append(f"- Output dir: `{cfg_dict.get('outdir')}`")
    if cfg_dict.get("prev"):
        lines.append(f"- Prev inventory: `{cfg_dict.get('prev')}`")
    lines.append(f"- Workers (regions): `{cfg_dict.get('workers_region')}`")
    lines.append(f"- Workers (enrich): `{cfg_dict.get('workers_enrich')}`")
    lines.append("- Query:")
    lines.append("```")
    lines.append(str(cfg_dict.get("query") or ""))
    lines.append("```")
    lines.append("")

    lines.append("### Regions")
    lines.append(f"- Subscribed regions ({len(subscribed_regions)}):")
    lines.append("```")
    lines.append(", ".join(subscribed_regions))
    lines.append("```")

    if requested_regions:
        lines.append(f"- Requested regions ({len(requested_regions)}):")
        lines.append("```")
        lines.append(", ".join(requested_regions))
        lines.append("```")
    else:
        lines.append("- Requested regions: (all subscribed)")

    if excluded_regions:
        lines.append(f"- Excluded regions ({len(excluded_regions)}):")
        for item in sorted(excluded_regions, key=lambda d: d.get("region", "")):
            region = item.get("region", "")
            reason = item.get("reason", "")
            short = _truncate(reason, 140)
            lines.append(f"  - `{region}` — {short}")
        lines.append("")
        lines.append("#### Exclusion Details")
        for item in sorted(excluded_regions, key=lambda d: d.get("region", "")):
            region = item.get("region", "")
            reason = item.get("reason", "")
            lines.append(f"**{region}**")
            lines.append("```")
            lines.append(reason)
            lines.append("```")
    else:
        lines.append("- Excluded regions: none")
    lines.append("")

    lines.append("### Results")
    lines.append(f"- Discovered records: `{len(discovered_records)}`")

    if counts_by_region:
        lines.append("- Records by region:")
        for region, count in counts_by_region.items():
            if not region:
                continue
            lines.append(f"  - `{region}`: `{count}`")

    if metrics:
        lines.append(f"- Enrichment status:")
        cbes = metrics.get("counts_by_enrich_status") or {}
        for k in sorted(cbes.keys()):
            lines.append(f"  - `{k}`: `{cbes[k]}`")

        # Highlight enrichment failures (these records are kept in output with enrichStatus=ERROR).
        error_types: Dict[str, int] = {}
        for r in discovered_records:
            if str(r.get("enrichStatus") or "") != "ERROR":
                continue
            msg = _truncate(str(r.get("enrichError") or ""), 120)
            if not msg:
                msg = "(unknown error)"
            error_types[msg] = error_types.get(msg, 0) + 1
        if error_types:
            lines.append("- Enrichment failures (records kept in output):")
            for msg, count in sorted(error_types.items(), key=lambda kv: (-kv[1], kv[0]))[:10]:
                lines.append(f"  - `{count}`: {msg}")
        if error_summary.get("total"):
            lines.append("- Enrichment error categories (count):")
            by_category = error_summary.get("by_category") or {}
            for key in _ENRICH_ERROR_CATEGORY_ORDER:
                count = int(by_category.get(key, 0) or 0)
                if count:
                    label = _ENRICH_ERROR_CATEGORY_LABELS.get(key, key)
                    lines.append(f"  - `{label}`: `{count}`")
    lines.append("")

    lines.append("### Findings")
    if excluded_regions:
        lines.append(
            "- One or more regions were excluded due to errors during Resource Search. "
            "The run continued and produced partial results."
        )
        lines.append(
            "- Recommended follow-up: validate credentials for the excluded regions, or restrict the run via `--regions` if those regions are intentionally out of scope."
        )
    else:
        lines.append("- No regions were excluded during discovery.")

    if diff_warning:
        lines.append(f"- Diff warning: {_truncate(diff_warning, 300)}")
    if fatal_error:
        lines.append(f"- Fatal error: {_truncate(fatal_error, 500)}")

    # If we had to alias compartments, provide the mapping here (metadata/appendix only).
    if alias_by_comp:
        lines.append("")
        lines.append("### Compartment Aliases")
        lines.append("(Aliases are used in the main report to avoid printing raw OCIDs.)")
        for cid in sorted(alias_by_comp.keys()):
            alias = alias_by_comp[cid]
            name = name_by_comp.get(cid, "")
            if name:
                lines.append(f"- {alias}: {name} — `{cid}`")
            else:
                lines.append(f"- {alias}: `{cid}`")

    lines.append("")
    lines.append("### Notes")
    lines.append("- This tool is read-only by design; it does not mutate OCI resources.")
    lines.append("- For troubleshooting OCI API failures, use `oci-inv validate-auth` and consider re-running with `--json-logs`. ")

    return "\n".join(lines).rstrip() + "\n"


def write_run_report_md(
    *,
    outdir: Path,
    status: str,
    cfg: Any,
    subscribed_regions: List[str],
    requested_regions: Optional[List[str]],
    excluded_regions: List[Dict[str, str]],
    discovered_records: List[Dict[str, Any]],
    metrics: Optional[Dict[str, Any]],
    diff_warning: Optional[str] = None,
    fatal_error: Optional[str] = None,
    executive_summary: Optional[str] = None,
    executive_summary_error: Optional[str] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    diagram_summary: Optional[Dict[str, Any]] = None,
) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    paths = resolve_output_paths(outdir)
    started = started_at or _utc_now_iso()
    finished = finished_at or _utc_now_iso()

    # RunConfig is a dataclass; use asdict if possible.
    try:
        cfg_dict = asdict(cfg)
    except Exception:
        cfg_dict = {
            "auth": getattr(cfg, "auth", None),
            "profile": getattr(cfg, "profile", None),
            "tenancy_ocid": getattr(cfg, "tenancy_ocid", None),
            "query": getattr(cfg, "query", None),
            "outdir": str(getattr(cfg, "outdir", outdir)),
            "prev": str(getattr(cfg, "prev", "") or "") or None,
            "workers_region": getattr(cfg, "workers_region", None),
            "workers_enrich": getattr(cfg, "workers_enrich", None),
        }

    text = render_run_report_md(
        status=status,
        cfg_dict={**cfg_dict, "outdir": str(cfg_dict.get("outdir") or outdir)},
        started_at=started,
        finished_at=finished,
        executive_summary=executive_summary,
        executive_summary_error=executive_summary_error,
        subscribed_regions=list(subscribed_regions),
        requested_regions=list(requested_regions) if requested_regions else None,
        excluded_regions=list(excluded_regions),
        discovered_records=list(discovered_records),
        metrics=dict(metrics) if metrics else None,
        diff_warning=diff_warning,
        fatal_error=fatal_error,
        diagram_summary=dict(diagram_summary) if diagram_summary else None,
    )

    p = paths.report_md
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _money_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _money_fmt(value: Any) -> str:
    dec = _money_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{dec:.2f}"


def _usage_json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _usage_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_usage_json_safe(v) for v in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _usage_json_safe(to_dict())
        except Exception:
            return str(value)
    attr_map = getattr(value, "attribute_map", None)
    if isinstance(attr_map, dict) and attr_map:
        out: Dict[str, Any] = {}
        for key in attr_map.keys():
            try:
                out[str(key)] = _usage_json_safe(getattr(value, key))
            except Exception:
                continue
        return out
    return str(value)


_NUMERIC_USAGE_FIELDS = {
    "computed_amount",
    "computed_quantity",
    "attributed_cost",
    "attributed_usage",
    "discount",
    "list_rate",
    "overage",
    "weight",
}


def _normalize_usage_value(value: Any, *, field: Optional[str] = None) -> str:
    safe_value = _usage_json_safe(value)
    if safe_value is None:
        return "" if field in _NUMERIC_USAGE_FIELDS else "unknown"
    if isinstance(safe_value, str):
        if not safe_value.strip():
            return "" if field in _NUMERIC_USAGE_FIELDS else "unknown"
        return safe_value
    if isinstance(safe_value, (dict, list)):
        return json.dumps(safe_value, sort_keys=True, ensure_ascii=True)
    return str(safe_value)


def _usage_item_sort_key(item: Dict[str, Any]) -> Tuple[str, str, str, str, str, str, str, str]:
    return (
        str(item.get("group_by") or ""),
        str(item.get("group_value") or ""),
        str(item.get("time_usage_started") or ""),
        str(item.get("time_usage_ended") or ""),
        str(item.get("service") or ""),
        str(item.get("region") or ""),
        str(item.get("computed_amount") or ""),
        str(item.get("currency") or ""),
    )


def _normalize_cost_rows(rows: Sequence[Dict[str, Any]], name_key: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        name = str(row.get(name_key) or "").strip()
        if not name:
            continue
        amount = _money_decimal(row.get("amount", 0))
        out.append({"name": name, "amount": amount})
    out.sort(key=lambda r: (-r["amount"], r["name"].lower()))
    return out


def _cap_cost_rows(rows: List[Dict[str, Any]], cap: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if len(rows) <= cap:
        return rows, None
    head = rows[:cap]
    tail = rows[cap:]
    other = sum((r["amount"] for r in tail), Decimal("0"))
    head = list(head) + [{"name": "Other", "amount": other}]
    return head, f"Top {cap}; remaining aggregated as Other."


def _parse_lens_weights(raw: Optional[Sequence[str]]) -> Tuple[Dict[str, float], List[str]]:
    weights: Dict[str, float] = {}
    errors: List[str] = []
    if not raw:
        return weights, errors
    for entry in raw:
        text = str(entry or "").strip()
        if not text:
            continue
        if "=" not in text:
            errors.append(f"Invalid lens weight entry: {text}")
            continue
        lens, weight = [p.strip() for p in text.split("=", 1)]
        lens_title = lens.title()
        if lens_title not in {"Knowledge", "Process", "Metrics", "Adoption", "Automation"}:
            errors.append(f"Unknown lens in weight entry: {lens}")
            continue
        try:
            weights[lens_title] = float(weight)
        except Exception:
            errors.append(f"Invalid weight value for {lens_title}: {weight}")
    return weights, errors


def _parse_assessment_capabilities(raw: Optional[Sequence[str]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    parsed: List[Dict[str, Any]] = []
    errors: List[str] = []
    if not raw:
        return parsed, errors
    for entry in raw:
        text = str(entry or "").strip()
        if not text:
            continue
        parts = [p.strip() for p in text.split("|", 8)]
        if len(parts) < 9:
            errors.append(f"Invalid capability entry (expected 9 fields): {text}")
            continue
        domain, capability = parts[0], parts[1]
        lens_raw = parts[2:7]
        target_raw = parts[7]
        evidence = parts[8]
        if not domain:
            domain = "Unspecified"
        if not capability:
            errors.append(f"Capability name missing in entry: {text}")
            continue
        lens_scores: List[int] = []
        lens_ok = True
        for val in lens_raw:
            try:
                lens_scores.append(int(val))
            except Exception:
                lens_ok = False
                errors.append(f"Invalid lens score '{val}' in entry: {text}")
                break
        if not lens_ok:
            continue
        try:
            target_score = int(target_raw)
        except Exception:
            errors.append(f"Invalid target score '{target_raw}' in entry: {text}")
            continue
        parsed.append(
            {
                "domain": domain,
                "capability": capability,
                "scores": lens_scores,
                "target": target_score,
                "evidence": evidence,
            }
        )
    parsed.sort(key=lambda r: (r["domain"].lower(), r["capability"].lower()))
    return parsed, errors


def _extract_osub_total(osub_usage: Optional[Dict[str, Any]]) -> Optional[Decimal]:
    if not osub_usage:
        return None
    for key in (
        "computed_amount",
        "computedAmount",
        "total_amount",
        "totalAmount",
        "amount",
        "total_computed_amount",
        "totalComputedAmount",
    ):
        if key in osub_usage:
            try:
                return _money_decimal(osub_usage[key])
            except Exception:
                return None
    return None


def render_cost_report_md(
    *,
    status: str,
    cfg_dict: Dict[str, Any],
    cost_context: Dict[str, Any],
    narratives: Optional[Dict[str, str]] = None,
    narrative_errors: Optional[Dict[str, str]] = None,
) -> str:
    time_start = str(cost_context.get("time_start") or "")
    time_end = str(cost_context.get("time_end") or "")
    currency = str(cost_context.get("currency") or "UNKNOWN")

    services = _normalize_cost_rows(cost_context.get("services", []), "name")
    regions = _normalize_cost_rows(cost_context.get("regions", []), "name")
    raw_compartments = cost_context.get("compartments", [])
    comp_rows = _normalize_cost_rows(raw_compartments, "compartment_id")
    compartment_group_by = str(cost_context.get("compartment_group_by") or "compartmentId")
    aggregation_dims = cost_context.get("aggregation_dimensions") or ["service", compartment_group_by, "region"]
    if isinstance(aggregation_dims, (list, tuple)):
        aggregation_label = ", ".join([str(v) for v in aggregation_dims if str(v)])
    else:
        aggregation_label = str(aggregation_dims or "")

    total_cost = _money_decimal(cost_context.get("total_cost") or 0)
    if total_cost == Decimal("0") and services:
        total_cost = sum((r["amount"] for r in services), Decimal("0"))

    service_count = len({r["name"] for r in services})
    region_count = len({r["name"] for r in regions})
    compartment_ids = [r["name"] for r in comp_rows]
    compartment_count = len(set(compartment_ids))

    alias_by_comp: Dict[str, str] = {}
    name_by_comp: Dict[str, str] = {}
    if compartment_group_by == "compartmentId":
        alias_by_comp = _compartment_alias_map(compartment_ids)
        name_by_comp = cost_context.get("compartment_names") or {}

    def _sanitize_cost_narrative(text: str) -> str:
        lowered = text.lower()
        banned = (
            "recommend",
            "should ",
            "optimiz",
            "reduce ",
            "increase ",
            "forecast",
            "predict",
            "save ",
            "savings",
            "right-size",
            "rightsizing",
            "cut ",
        )
        if any(token in lowered for token in banned):
            return "(Narrative omitted: non-descriptive content detected.)"
        return text

    def _narrative_text(key: str) -> str:
        text = (narratives or {}).get(key, "").strip()
        if text:
            for prefix in ("### ", "## ", "# "):
                if text.startswith(prefix):
                    lines_local = text.splitlines()
                    text = "\n".join(lines_local[1:]).strip()
                    break
            if key != "next_steps":
                text = _sanitize_cost_narrative(text)
            return text
        err_txt = (narrative_errors or {}).get(key)
        if err_txt:
            return f"(GenAI narrative unavailable: {_truncate(str(err_txt), 200)})"
        return "(GenAI narrative unavailable for this run.)"

    def _snapshot_status() -> str:
        steps = cost_context.get("steps") or []
        step_status: Dict[str, str] = {}
        for step in steps:
            name = str(step.get("name") or "")
            status_val = str(step.get("status") or "").strip()
            status_val = status_val.split()[0] if status_val else ""
            if not name:
                continue
            prev = step_status.get(name, "")
            if prev == "ERROR" or status_val == "ERROR":
                step_status[name] = "ERROR"
            elif prev == "OK" or status_val == "OK":
                step_status[name] = "OK"
            elif prev == "SKIPPED" or status_val == "SKIPPED":
                step_status[name] = "SKIPPED"
            else:
                step_status[name] = status_val

        core_steps = {
            "usage_api_total",
            "usage_api_service",
            "usage_api_compartment",
            "usage_api_region",
        }
        core_present = bool(total_cost > 0 or service_count or region_count or compartment_count)
        if not core_present:
            return "ERROR"

        core_seen = any(name in step_status for name in core_steps)
        core_ok = all(step_status.get(name) == "OK" for name in core_steps if name in step_status)
        optional_errors = any(
            status_val == "ERROR" for name, status_val in step_status.items() if name not in core_steps
        )
        warnings = bool(cost_context.get("warnings"))
        if (core_seen and not core_ok) or optional_errors or warnings:
            return "WARNING"
        return "OK"

    lines: List[str] = []
    lines.append("# OCI Cost Snapshot Report")
    lines.append("")
    lines.append(_narrative_text("intro"))
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(_narrative_text("executive_summary"))
    lines.append("")
    lines.append("## Data Sources & Methodology")
    lines.append(_narrative_text("data_sources"))
    lines.append("")
    lines.append("## Snapshot Overview")
    lines.extend(
        _md_table(
            ["Metric", "Value"],
            [
                ["Status", _snapshot_status()],
                ["Total cost", f"{_money_fmt(total_cost)} {currency}"],
                ["Currency", currency],
                ["Time range (UTC)", f"{time_start} to {time_end}"],
                ["Grouping dimensions", aggregation_label or "(unknown)"],
                ["Services covered", str(service_count)],
                ["Compartments covered", str(compartment_count)],
                ["Regions covered", str(region_count)],
            ],
        )
    )

    lines.append("")
    lines.append("## Cost Allocation Snapshots")

    lines.append("")
    lines.append("### Cost by Service")
    service_rows, service_note = _cap_cost_rows(services, 10)
    if service_note:
        lines.append(service_note)
    if service_rows:
        lines.extend(
            _md_table(
                ["Service", f"Cost ({currency})"],
                [[r["name"], _money_fmt(r["amount"])] for r in service_rows],
            )
        )
    else:
        lines.append("(none)")

    lines.append("")
    lines.append("### Cost by Compartment")
    comp_display_rows = []
    for row in comp_rows:
        comp_id = row["name"]
        if compartment_group_by == "compartmentId":
            label = _compartment_label(comp_id, alias_by_id=alias_by_comp, name_by_id=name_by_comp)
        else:
            label = comp_id
        comp_display_rows.append({"name": label, "amount": row["amount"]})
    comp_display_rows, comp_note = _cap_cost_rows(comp_display_rows, 20)
    if comp_note:
        lines.append(comp_note)
    if comp_display_rows:
        lines.extend(
            _md_table(
                ["Compartment", f"Cost ({currency})"],
                [[r["name"], _money_fmt(r["amount"])] for r in comp_display_rows],
            )
        )
    else:
        lines.append("(none)")

    lines.append("")
    lines.append("### Cost by Region")
    region_rows, region_note = _cap_cost_rows(regions, 20)
    if region_note:
        lines.append(region_note)
    if region_rows:
        lines.extend(
            _md_table(
                ["Region", f"Cost ({currency})"],
                [[r["name"], _money_fmt(r["amount"])] for r in region_rows],
            )
        )
    else:
        lines.append("(none)")

    lines.append("")
    lines.append("## Consumption Insights (Descriptive Only)")
    lines.append(_narrative_text("consumption_insights"))

    lines.append("")
    lines.append("## Coverage & Data Gaps")
    lines.append(_narrative_text("coverage_gaps"))

    lines.append("")
    lines.append("## Intended Audience & Usage Guidelines")
    lines.append(_narrative_text("audience"))

    lines.append("")
    lines.append("## Suggested Next Steps (Optional)")
    lines.append(_narrative_text("next_steps"))

    return "\n".join(lines).rstrip() + "\n"


def write_run_report_md(
    *,
    outdir: Path,
    status: str,
    cfg: Any,
    subscribed_regions: List[str],
    requested_regions: Optional[List[str]],
    excluded_regions: List[Dict[str, str]],
    discovered_records: List[Dict[str, Any]],
    metrics: Optional[Dict[str, Any]],
    diff_warning: Optional[str] = None,
    fatal_error: Optional[str] = None,
    executive_summary: Optional[str] = None,
    executive_summary_error: Optional[str] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
    diagram_summary: Optional[Dict[str, Any]] = None,
) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    paths = resolve_output_paths(outdir)
    started = started_at or _utc_now_iso()
    finished = finished_at or _utc_now_iso()

    # RunConfig is a dataclass; use asdict if possible.
    try:
        cfg_dict = asdict(cfg)
    except Exception:
        cfg_dict = {
            "auth": getattr(cfg, "auth", None),
            "profile": getattr(cfg, "profile", None),
            "tenancy_ocid": getattr(cfg, "tenancy_ocid", None),
            "query": getattr(cfg, "query", None),
            "outdir": str(getattr(cfg, "outdir", outdir)),
            "prev": str(getattr(cfg, "prev", "") or "") or None,
            "workers_region": getattr(cfg, "workers_region", None),
            "workers_enrich": getattr(cfg, "workers_enrich", None),
        }

    text = render_run_report_md(
        status=status,
        cfg_dict={**cfg_dict, "outdir": str(cfg_dict.get("outdir") or outdir)},
        started_at=started,
        finished_at=finished,
        executive_summary=executive_summary,
        executive_summary_error=executive_summary_error,
        subscribed_regions=list(subscribed_regions),
        requested_regions=list(requested_regions) if requested_regions else None,
        excluded_regions=list(excluded_regions),
        discovered_records=list(discovered_records),
        metrics=dict(metrics) if metrics else None,
        diff_warning=diff_warning,
        fatal_error=fatal_error,
        diagram_summary=dict(diagram_summary) if diagram_summary else None,
    )

    p = paths.report_md
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _money_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _money_fmt(value: Any) -> str:
    dec = _money_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{dec:.2f}"


def _usage_json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _usage_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_usage_json_safe(v) for v in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _usage_json_safe(to_dict())
        except Exception:
            return str(value)
    attr_map = getattr(value, "attribute_map", None)
    if isinstance(attr_map, dict) and attr_map:
        out: Dict[str, Any] = {}
        for key in attr_map.keys():
            try:
                out[str(key)] = _usage_json_safe(getattr(value, key))
            except Exception:
                continue
        return out
    return str(value)


def _normalize_usage_value(value: Any, *, field: Optional[str] = None) -> str:
    safe_value = _usage_json_safe(value)
    if safe_value is None:
        return "" if field in _NUMERIC_USAGE_FIELDS else "unknown"
    if isinstance(safe_value, str):
        if not safe_value.strip():
            return "" if field in _NUMERIC_USAGE_FIELDS else "unknown"
        return safe_value
    if isinstance(safe_value, (dict, list)):
        return json.dumps(safe_value, sort_keys=True, ensure_ascii=True)
    return str(safe_value)


def _usage_item_sort_key(item: Dict[str, Any]) -> Tuple[str, str, str, str, str, str, str, str]:
    return (
        str(item.get("group_by") or ""),
        str(item.get("group_value") or ""),
        str(item.get("time_usage_started") or ""),
        str(item.get("time_usage_ended") or ""),
        str(item.get("service") or ""),
        str(item.get("region") or ""),
        str(item.get("computed_amount") or ""),
        str(item.get("currency") or ""),
    )


def _normalize_cost_rows(rows: Sequence[Dict[str, Any]], name_key: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        name = str(row.get(name_key) or "").strip()
        if not name:
            continue
        amount = _money_decimal(row.get("amount", 0))
        out.append({"name": name, "amount": amount})
    out.sort(key=lambda r: (-r["amount"], r["name"].lower()))
    return out


def _cap_cost_rows(rows: List[Dict[str, Any]], cap: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if len(rows) <= cap:
        return rows, None
    head = rows[:cap]
    tail = rows[cap:]
    other = sum((r["amount"] for r in tail), Decimal("0"))
    head = list(head) + [{"name": "Other", "amount": other}]
    return head, f"Top {cap}; remaining aggregated as Other."


def _parse_lens_weights(raw: Optional[Sequence[str]]) -> Tuple[Dict[str, float], List[str]]:
    weights: Dict[str, float] = {}
    errors: List[str] = []
    if not raw:
        return weights, errors
    for entry in raw:
        text = str(entry or "").strip()
        if not text:
            continue
        if "=" not in text:
            errors.append(f"Invalid lens weight entry: {text}")
            continue
        lens, weight = [p.strip() for p in text.split("=", 1)]
        lens_title = lens.title()
        if lens_title not in {"Knowledge", "Process", "Metrics", "Adoption", "Automation"}:
            errors.append(f"Unknown lens in weight entry: {lens}")
            continue
        try:
            weights[lens_title] = float(weight)
        except Exception:
            errors.append(f"Invalid weight value for {lens_title}: {weight}")
    return weights, errors


def _parse_assessment_capabilities(raw: Optional[Sequence[str]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    parsed: List[Dict[str, Any]] = []
    errors: List[str] = []
    if not raw:
        return parsed, errors
    for entry in raw:
        text = str(entry or "").strip()
        if not text:
            continue
        parts = [p.strip() for p in text.split("|", 8)]
        if len(parts) < 9:
            errors.append(f"Invalid capability entry (expected 9 fields): {text}")
            continue
        domain, capability = parts[0], parts[1]
        lens_raw = parts[2:7]
        target_raw = parts[7]
        evidence = parts[8]
        if not domain:
            domain = "Unspecified"
        if not capability:
            errors.append(f"Capability name missing in entry: {text}")
            continue
        lens_scores: List[int] = []
        lens_ok = True
        for val in lens_raw:
            try:
                lens_scores.append(int(val))
            except Exception:
                lens_ok = False
                errors.append(f"Invalid lens score '{val}' in entry: {text}")
                break
        if not lens_ok:
            continue
        try:
            target_score = int(target_raw)
        except Exception:
            errors.append(f"Invalid target score '{target_raw}' in entry: {text}")
            continue
        parsed.append(
            {
                "domain": domain,
                "capability": capability,
                "scores": lens_scores,
                "target": target_score,
                "evidence": evidence,
            }
        )
    parsed.sort(key=lambda r: (r["domain"].lower(), r["capability"].lower()))
    return parsed, errors


def write_cost_report_md(
    *,
    outdir: Path,
    status: str,
    cfg: Any,
    cost_context: Dict[str, Any],
    narratives: Optional[Dict[str, str]] = None,
    narrative_errors: Optional[Dict[str, str]] = None,
) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    paths = resolve_output_paths(outdir)
    try:
        cfg_dict = asdict(cfg)
    except Exception:
        cfg_dict = {
            "cost_report": getattr(cfg, "cost_report", None),
            "cost_start": getattr(cfg, "cost_start", None),
            "cost_end": getattr(cfg, "cost_end", None),
            "cost_currency": getattr(cfg, "cost_currency", None),
            "cost_compartment_group_by": getattr(cfg, "cost_compartment_group_by", None),
            "assessment_target_group": getattr(cfg, "assessment_target_group", None),
            "assessment_target_scope": getattr(cfg, "assessment_target_scope", None),
            "assessment_lens_weights": getattr(cfg, "assessment_lens_weights", None),
            "assessment_capabilities": getattr(cfg, "assessment_capabilities", None),
        }

    text = render_cost_report_md(
        status=status,
        cfg_dict=cfg_dict,
        cost_context=cost_context,
        narratives=narratives,
        narrative_errors=narrative_errors,
    )
    p = paths.cost_report_md
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _write_cost_usage_csv(
    *,
    outdir: Path,
    usage_items: Sequence[Dict[str, Any]],
    filename: str,
    group_by_filter: Optional[str] = None,
) -> Optional[Path]:
    if not usage_items:
        return None

    base_fields = [
        "group_by",
        "group_value",
        "time_usage_started",
        "time_usage_ended",
        "service",
        "region",
        "compartment_id",
        "compartment_name",
        "compartment_path",
        "resource_id",
        "resource_name",
        "sku_name",
        "sku_part_number",
        "unit",
        "computed_amount",
        "computed_quantity",
        "currency",
        "attributed_cost",
        "attributed_usage",
        "discount",
        "list_rate",
        "overage",
        "overages_flag",
        "platform",
        "ad",
        "is_forecast",
        "subscription_id",
        "tenant_id",
        "tenant_name",
        "tags",
        "weight",
    ]

    all_keys: set[str] = set()
    rows: List[Dict[str, Any]] = []
    for item in usage_items:
        if not isinstance(item, dict):
            continue
        if group_by_filter and str(item.get("group_by") or "") != group_by_filter:
            continue
        rows.append(item)
        all_keys.update(item.keys())
    if not rows:
        return None

    extra_fields = sorted(key for key in all_keys if key not in base_fields)
    fieldnames = base_fields + extra_fields
    rows.sort(key=_usage_item_sort_key)

    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / filename
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _normalize_usage_value(row.get(field), field=field) for field in fieldnames})
    return path


def write_cost_usage_csv(
    *,
    outdir: Path,
    usage_items: Sequence[Dict[str, Any]],
) -> Optional[Path]:
    return _write_cost_usage_csv(
        outdir=outdir,
        usage_items=usage_items,
        filename="cost_usage_items.csv",
    )


def write_cost_usage_grouped_csv(
    *,
    outdir: Path,
    usage_items: Sequence[Dict[str, Any]],
    group_by_label: Optional[str],
) -> Optional[Path]:
    if not group_by_label:
        return None
    return _write_cost_usage_csv(
        outdir=outdir,
        usage_items=usage_items,
        filename="cost_usage_items_grouped.csv",
        group_by_filter=group_by_label,
    )


def write_cost_usage_jsonl(
    *,
    outdir: Path,
    usage_items: Sequence[Dict[str, Any]],
) -> Optional[Path]:
    if not usage_items:
        return None

    rows: List[Dict[str, Any]] = []
    for item in usage_items:
        if isinstance(item, dict):
            rows.append(item)
    if not rows:
        return None

    rows.sort(
        key=lambda item: (
            str(item.get("group_by") or ""),
            str(item.get("group_value") or ""),
            str(item.get("time_usage_started") or ""),
            str(item.get("time_usage_ended") or ""),
            str(item.get("service") or ""),
            str(item.get("region") or ""),
            str(item.get("computed_amount") or ""),
            str(item.get("currency") or ""),
        )
    )

    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "cost_usage_items.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_usage_json_safe(row), sort_keys=True, ensure_ascii=True))
            handle.write("\n")
    return path


def write_cost_usage_views(
    *,
    outdir: Path,
    usage_items: Sequence[Dict[str, Any]],
    compartment_group_by: str,
) -> List[Path]:
    if not usage_items:
        return []

    def _write_view(filename: str, group_by: str, fieldnames: Sequence[str]) -> Optional[Path]:
        rows = [item for item in usage_items if item.get("group_by") == group_by]
        if not rows:
            return None
        rows.sort(key=_usage_item_sort_key)
        outdir.mkdir(parents=True, exist_ok=True)
        path = outdir / filename
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _normalize_usage_value(row.get(field), field=field) for field in fieldnames})
        return path

    outputs: List[Path] = []
    service_fields = [
        "time_usage_started",
        "time_usage_ended",
        "service",
        "computed_amount",
        "currency",
    ]
    region_fields = [
        "time_usage_started",
        "time_usage_ended",
        "region",
        "computed_amount",
        "currency",
    ]
    compartment_fields: List[str] = [
        "time_usage_started",
        "time_usage_ended",
    ]
    if compartment_group_by == "compartmentName":
        compartment_fields.append("compartment_name")
    elif compartment_group_by == "compartmentPath":
        compartment_fields.append("compartment_path")
    else:
        compartment_fields.extend(["compartment_id", "compartment_name", "compartment_path"])
    compartment_fields.extend(["computed_amount", "currency"])

    for filename, group_by, fields in (
        ("cost_usage_service.csv", "service", service_fields),
        ("cost_usage_region.csv", "region", region_fields),
        ("cost_usage_compartment.csv", compartment_group_by, compartment_fields),
    ):
        path = _write_view(filename, group_by, fields)
        if path:
            outputs.append(path)
    return outputs
