from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


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

    lines: List[str] = []
    lines.append(f"# OCI Inventory Run Report")
    lines.append("")
    lines.append(f"Status: **{status}**")
    lines.append(f"Started (UTC): {started_at}")
    lines.append(f"Finished (UTC): {finished_at}")
    if duration_note:
        lines.append(duration_note.strip())
    lines.append("")

    if executive_summary is not None or executive_summary_error is not None:
        lines.append("## Executive Summary")
        if executive_summary:
            lines.append(executive_summary.strip())
        else:
            lines.append(
                f"(GenAI summary generation failed: {_truncate(str(executive_summary_error or ''), 300)})"
            )
        lines.append("")

    lines.append("## Steps Executed")
    lines.append("- Resolved authentication context")
    lines.append("- Discovered subscribed regions")
    lines.append("- Executed OCI Resource Search per region (Structured Search)")
    lines.append("- Normalized records and attached region metadata")
    lines.append("- Enriched records using read-only OCI SDK calls")
    lines.append("- Exported artifacts (JSONL + CSV; optional Parquet)")
    lines.append("")

    lines.append("## Run Configuration")
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

    lines.append("## Regions")
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
        lines.append("### Exclusion Details")
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

    lines.append("## Results")
    lines.append(f"- Discovered records: `{len(discovered_records)}`")

    counts_by_region = _counts_by_key(discovered_records, "region")
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

    lines.append("## Findings")
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

    lines.append("")
    lines.append("## Notes")
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
