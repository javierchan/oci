from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


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


def _flatten_tags(record: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    ff = record.get("freeformTags")
    if isinstance(ff, dict):
        for k, v in ff.items():
            ks = str(k or "").strip()
            vs = str(v or "").strip()
            if ks and vs:
                out[ks] = vs

    dt = record.get("definedTags")
    if isinstance(dt, dict):
        for ns, inner in dt.items():
            if not isinstance(inner, dict):
                continue
            for k, v in inner.items():
                ks = str(k or "").strip()
                if not ks:
                    continue
                vs = str(v or "").strip()
                if vs:
                    out[f"{ns}.{ks}"] = vs
    return out


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


def _pct(n: int, d: int) -> str:
    if d <= 0:
        return "0%"
    return f"{int(round((n / d) * 100.0))}%"


def _prefix_token(name: str) -> str:
    s = (name or "").strip()
    if not s:
        return ""
    for sep in ("-", "_", "."):
        if sep in s:
            token = s.split(sep, 1)[0].strip()
            if len(token) >= 3:
                return token
    return ""


def _workload_key_candidates(record: Dict[str, Any]) -> List[str]:
    name = _record_name(record)
    tags = _flatten_tags(record)

    candidates: List[str] = []

    # Prefer explicit app/service/workload-like tags.
    preferred_keys = (
        "app",
        "application",
        "service",
        "workload",
        "project",
        "stack",
        "App",
        "Application",
        "Service",
        "Workload",
        "Project",
        "Stack",
    )
    for k in preferred_keys:
        v = tags.get(k)
        if v:
            candidates.append(v)

    # Heuristic keywords in name for common demo/workload patterns.
    nlow = (name or "").lower()
    for kw in ("media", "stream", "cdn", "edge", "demo", "sandbox"):
        if kw in nlow:
            candidates.append(kw)

    # Fallback: stable prefix token (filtered later by frequency threshold).
    pt = _prefix_token(name)
    if pt:
        candidates.append(pt)

    # Normalize and dedupe while preserving order.
    out: List[str] = []
    seen: set[str] = set()
    for c in candidates:
        c2 = (c or "").strip()
        if not c2:
            continue
        key = c2.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c2)
    return out


def group_workloads(records: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    # Two-pass: decide which prefix tokens are frequent enough to be meaningful.
    prefix_counts: Dict[str, int] = {}
    for r in records:
        t = _prefix_token(_record_name(r))
        if t:
            prefix_counts[t.lower()] = prefix_counts.get(t.lower(), 0) + 1

    def _is_eligible_prefix(token: str) -> bool:
        return prefix_counts.get(token.lower(), 0) >= 3

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in records:
        cands = _workload_key_candidates(r)
        chosen = ""
        for c in cands:
            # Keep tag/keyword candidates; allow prefix token only if frequent.
            if c.lower() in {"media", "stream", "cdn", "edge", "demo", "sandbox"}:
                chosen = c
                break
            if _is_eligible_prefix(c):
                chosen = c
                break
            # If this candidate looks like an explicit tag value, keep it.
            if " " in c or len(c) >= 4:
                # Still conservative: avoid grouping everything into "prod"/"dev".
                if c.lower() not in {"prod", "production", "dev", "test", "stage", "staging"}:
                    chosen = c
                    break
        if not chosen:
            continue
        groups.setdefault(chosen, []).append(r)

    # Keep only meaningful groups: at least 3 resources.
    out = {k: v for k, v in groups.items() if len(v) >= 3}
    return dict(sorted(out.items(), key=lambda kv: (-len(kv[1]), kv[0].lower())))


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

    workloads = group_workloads(discovered_records)

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
    parquet_warning: Optional[str] = None,
    diff_warning: Optional[str] = None,
    fatal_error: Optional[str] = None,
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
    workloads = group_workloads(discovered_records)

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

    # Executive Summary (architecture)
    lines.append("## Executive Summary")
    if executive_summary:
        # When enabled, GenAI summary is expected to be architecture-focused and redacted.
        lines.append(executive_summary.strip())
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
    lines.append("- `diagram_raw.mmd` (full graph export; intentionally noisy)")
    lines.append("- `graph_nodes.jsonl` / `graph_edges.jsonl` (graph data)")
    lines.append("- `diagram*.mmd` (architectural projections, if enabled)")
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
    if not recs:
        recs.append("No non-binding recommendations were derived from the current inventory signals.")
    for r in recs[:6]:
        lines.append(f"- {r}")
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
    lines.append("- Exported artifacts (JSONL + CSV; optional Parquet)")
    lines.append("")

    lines.append("### Run Configuration")
    # Keep this human-readable; do not dump every internal field.
    lines.append(f"- Auth: `{cfg_dict.get('auth')}`")
    if cfg_dict.get("profile"):
        lines.append(f"- Profile: `{cfg_dict.get('profile')}`")
    if cfg_dict.get("tenancy_ocid"):
        lines.append(f"- Tenancy OCID: `{cfg_dict.get('tenancy_ocid')}`")
    lines.append(f"- Output dir: `{cfg_dict.get('outdir')}`")
    lines.append(f"- Parquet: `{bool(cfg_dict.get('parquet'))}`")
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

    if parquet_warning:
        lines.append(f"- Parquet export warning: {_truncate(parquet_warning, 300)}")
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
    parquet_warning: Optional[str] = None,
    diff_warning: Optional[str] = None,
    fatal_error: Optional[str] = None,
    executive_summary: Optional[str] = None,
    executive_summary_error: Optional[str] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
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
            "parquet": getattr(cfg, "parquet", None),
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
        parquet_warning=parquet_warning,
        diff_warning=diff_warning,
        fatal_error=fatal_error,
    )

    p = outdir / "report.md"
    p.write_text(text, encoding="utf-8")
    return p
