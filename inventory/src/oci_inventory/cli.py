from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .auth.providers import AuthContext, AuthError, resolve_auth
from .config import RunConfig, load_run_config
from .diff.diff import diff_files, write_diff
from .enrich import get_enricher_for, set_enrich_context
from .export.csv import write_csv
from .export.graph import build_graph, write_graph, write_mermaid
from .export.jsonl import write_jsonl
from .export.parquet import ParquetNotAvailable, write_parquet
from .logging import LogConfig, get_logger, setup_logging
from .normalize.transform import sort_relationships, stable_json_dumps
from .oci.compartments import list_compartments as oci_list_compartments
from .oci.discovery import discover_in_region
from .oci.regions import get_subscribed_regions
from .report import write_run_report_md
from .util.concurrency import parallel_map_ordered
from .util.errors import (
    AuthResolutionError,
    ConfigError,
    as_exit_code,
)

LOG = get_logger(__name__)


def cmd_genai_chat(cfg: RunConfig) -> int:
    from .genai.chat_probe import chat_probe
    from .genai.redact import redact_text
def cmd_genai_chat(cfg: RunConfig) -> int:
    from .genai.chat_runner import run_genai_chat

    if cfg.genai_report:
        report_text = cfg.genai_report.read_text(encoding="utf-8")
        message = (
            "Use the following OCI inventory report as context. "
            "Reply with a short Markdown response.\n\n"
            + report_text
        )
    else:
        message = cfg.genai_message or ""

    if not message.strip():
        raise ConfigError("genai-chat requires either --message or --report")

    system = (
        "You are an SRE/Cloud inventory assistant. "
        "Output Markdown text only. Do not include secrets, OCIDs, or URLs."
    )

    api = (cfg.genai_api_format or "AUTO").strip().upper()
    max_tokens = int(cfg.genai_max_tokens or 300)
    temperature = float(cfg.genai_temperature) if cfg.genai_temperature is not None else None

    try:
        if api == "AUTO":
            out, hint = run_genai_chat(
                message=message,
                api_format="GENERIC",
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if not out.strip():
                out, hint = run_genai_chat(
                    message=message,
                    api_format="COHERE",
                    system=system,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
        else:
            out, hint = run_genai_chat(
                message=message,
                api_format=api,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not out.strip():
        print(f"ERROR: GenAI chat returned empty text (hint={hint})", file=sys.stderr)
        return 1

    print(out)
    return 0

    api_format = (cfg.genai_api_format or "AUTO").upper()
    max_tokens = int(cfg.genai_max_tokens or 256)
    temperature = float(cfg.genai_temperature if cfg.genai_temperature is not None else 0.2)

    msg = cfg.genai_message
    if cfg.genai_report:
        text = cfg.genai_report.read_text(encoding="utf-8")
        # The report may contain OCIDs/URLs (for example in the query); redact before use.
        msg = (
            "Write an Executive Summary (4-8 bullets) for the following OCI inventory report.\n\n"
            + redact_text(text)
        )
    if not msg:
        raise ConfigError("genai-chat requires --message or --report")

    res = chat_probe(
        message=msg,
        api_format=api_format,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    out = (res.text or "").strip()
    if out:
        print(out)
        return 0

    print(f"(no text returned; {res.hint})")
    return 2


def _resolve_auth(cfg: RunConfig) -> AuthContext:
    try:
        return resolve_auth(cfg.auth, cfg.profile, cfg.tenancy_ocid)
    except AuthError as e:
        raise AuthResolutionError(str(e)) from e


def _enrich_record(record: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    """
    Enrich a single normalized record using the enricher registry.
    Returns the updated record and a list of relationships to emit.
    Never raises: errors are captured into the record.
    """
    rtype = str(record.get("resourceType") or "")
    enricher = get_enricher_for(rtype)
    relationships: List[Dict[str, str]] = []
    try:
        res = enricher.enrich(dict(record))  # pass a copy to be safe
        record["details"] = res.details
        relationships = sort_relationships(res.relationships or [])
        record["relationships"] = relationships
        record["enrichStatus"] = res.enrichStatus
        record["enrichError"] = res.enrichError
    except BaseException as e:
        record["details"] = {}
        record["relationships"] = []
        record["enrichStatus"] = "ERROR"
        record["enrichError"] = str(e)
    finally:
        # Ensure transient searchSummary is removed from output record
        if "searchSummary" in record:
            record.pop("searchSummary", None)
    return record, relationships


def _coverage_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts_by_resource_type: Dict[str, int] = {}
    counts_by_enrich_status: Dict[str, int] = {}
    for r in records:
        rt = str(r.get("resourceType") or "")
        counts_by_resource_type[rt] = counts_by_resource_type.get(rt, 0) + 1
        st = str(r.get("enrichStatus") or "")
        counts_by_enrich_status[st] = counts_by_enrich_status.get(st, 0) + 1

    enriched_ok = counts_by_enrich_status.get("OK", 0)
    not_implemented = counts_by_enrich_status.get("NOT_IMPLEMENTED", 0)
    errors = counts_by_enrich_status.get("ERROR", 0)

    return {
        "total_discovered": len(records),
        "enriched_ok": enriched_ok,
        "not_implemented": not_implemented,
        "errors": errors,
        "counts_by_resource_type": dict(sorted(counts_by_resource_type.items())),
        "counts_by_enrich_status": dict(sorted(counts_by_enrich_status.items())),
    }


def _write_run_summary(outdir: Path, metrics: Dict[str, Any], cfg: RunConfig) -> Path:
    summary = dict(metrics)
    # Only include required metrics; users can inspect config via logs/CLI
    path = outdir / "run_summary.json"
    path.write_text(stable_json_dumps(summary), encoding="utf-8")
    return path


def _relationships_path(outdir: Path) -> Path:
    return outdir / "relationships.jsonl"


def _write_relationships(outdir: Path, relationships: List[Dict[str, str]]) -> Optional[Path]:
    if not relationships:
        return None
    p = _relationships_path(outdir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for rel in sort_relationships(relationships):
            f.write(stable_json_dumps(rel))
            f.write("\n")
    return p


def cmd_run(cfg: RunConfig) -> int:
    # Ensure the run directory exists early so we can always emit a report.
    cfg.outdir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    status = "OK"
    fatal_error: Optional[str] = None

    subscribed_regions: List[str] = []
    requested_regions: Optional[List[str]] = None
    excluded_regions: List[Dict[str, str]] = []
    discovered: List[Dict[str, Any]] = []
    enriched: List[Dict[str, Any]] = []
    metrics: Optional[Dict[str, Any]] = None
    parquet_warning: Optional[str] = None
    diff_warning: Optional[str] = None

    executive_summary: Optional[str] = None
    executive_summary_error: Optional[str] = None

    LOG.info("Starting inventory run", extra={"outdir": str(cfg.outdir)})

    try:
        ctx = _resolve_auth(cfg)
        set_enrich_context(ctx)

        # Discover regions
        regions = get_subscribed_regions(ctx)
        subscribed_regions = list(regions)
        if not regions:
            raise ConfigError("No subscribed regions found for the tenancy/profile provided")
        if cfg.regions:
            requested_regions = [r for r in cfg.regions if r]
            regions = requested_regions
        LOG.info("Discovered subscribed regions", extra={"regions": regions})

        # Per-region discovery in parallel (ordered by region for determinism)
        regions = sorted([r for r in regions if r])

        def _disc(r: str) -> List[Dict[str, Any]]:
            return discover_in_region(ctx, r, cfg.query)

        with ThreadPoolExecutor(max_workers=max(1, cfg.workers_region)) as pool:
            futures_by_region = {r: pool.submit(_disc, r) for r in regions}

            region_results: List[List[Dict[str, Any]]] = []
            for r in regions:
                try:
                    region_results.append(futures_by_region[r].result())
                except Exception as e:
                    excluded_regions.append({"region": r, "reason": str(e)})
                    LOG.warning("Region discovery failed; skipping region", extra={"region": r, "error": str(e)})
                    region_results.append([])

        # Flatten discovered records
        discovered = [rec for sub in region_results for rec in sub]
        LOG.info("Discovery complete", extra={"count": len(discovered), "excluded_regions": len(excluded_regions)})

        # Enrichment in parallel
        all_relationships: List[Dict[str, str]] = []

        def _enrich_and_collect(rec: Dict[str, Any]) -> Dict[str, Any]:
            updated, rels = _enrich_record(rec)
            return {"record": updated, "rels": rels}

        worker_results = parallel_map_ordered(
            _enrich_and_collect, discovered, max_workers=max(1, cfg.workers_enrich)
        )
        for item in worker_results:
            enriched.append(item["record"])
            all_relationships.extend(item["rels"] or [])

        LOG.info("Enrichment complete", extra={"count": len(enriched)})

        # Exports
        inventory_jsonl = cfg.outdir / "inventory.jsonl"
        inventory_csv = cfg.outdir / "inventory.csv"
        write_jsonl(enriched, inventory_jsonl)
        write_csv(enriched, inventory_csv)

        if cfg.parquet:
            try:
                parquet_path = cfg.outdir / "inventory.parquet"
                write_parquet(enriched, parquet_path)
            except ParquetNotAvailable as e:
                parquet_warning = str(e)
                LOG.warning(str(e))

        _write_relationships(cfg.outdir, all_relationships)

        # Coverage metrics and summary
        metrics = _coverage_metrics(enriched)
        _write_run_summary(cfg.outdir, metrics, cfg)

        # Graph artifacts (nodes/edges + Mermaid)
        nodes, edges = build_graph(enriched, all_relationships)
        write_graph(cfg.outdir, nodes, edges)
        write_mermaid(cfg.outdir, nodes, edges)

        # Optional diff against previous
        if cfg.prev:
            try:
                diff_obj = diff_files(Path(cfg.prev), inventory_jsonl)
                write_diff(cfg.outdir, diff_obj)
            except Exception as e:
                diff_warning = str(e)
                LOG.warning("Diff failed", extra={"error": str(e)})

        LOG.info("Run complete", extra={"outdir": str(cfg.outdir), "excluded_regions": len(excluded_regions)})
        return 0
    except Exception as e:
        status = "FAILED"
        fatal_error = str(e)
        raise
    finally:
        # Always attempt to write a report for transparency.
        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        if cfg.genai_summary and status == "OK":
            try:
                from .genai import generate_executive_summary  # lazy import

                executive_summary = generate_executive_summary(
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    subscribed_regions=subscribed_regions,
                    requested_regions=requested_regions,
                    excluded_regions=excluded_regions,
                    metrics=metrics,
                )
            except Exception as e:
                executive_summary_error = str(e)
                LOG.warning("GenAI executive summary failed", extra={"error": str(e)})

        try:
            write_run_report_md(
                outdir=cfg.outdir,
                status=status,
                cfg=cfg,
                subscribed_regions=subscribed_regions,
                requested_regions=requested_regions,
                excluded_regions=excluded_regions,
                discovered_records=enriched or discovered,
                metrics=metrics,
                parquet_warning=parquet_warning,
                diff_warning=diff_warning,
                fatal_error=fatal_error,
                executive_summary=executive_summary,
                executive_summary_error=executive_summary_error,
                started_at=started_at,
                finished_at=finished_at,
            )
        except Exception:
            # Report generation must never affect the run outcome.
            pass


def cmd_diff(cfg: RunConfig) -> int:
    prev = cfg.prev
    curr = cfg.curr
    if not prev or not curr:
        raise ConfigError("Both --prev and --curr must be provided for diff")
    prev_p = Path(prev)
    curr_p = Path(curr)
    diff_obj = diff_files(prev_p, curr_p)
    write_diff(cfg.outdir, diff_obj)
    LOG.info("Diff complete", extra={"outdir": str(cfg.outdir)})
    return 0


def cmd_validate_auth(cfg: RunConfig) -> int:
    ctx = _resolve_auth(cfg)
    # Attempt to list regions as a validation step
    regions = get_subscribed_regions(ctx)
    LOG.info("Authentication validated", extra={"method": cfg.auth, "profile": cfg.profile, "regions": regions})
    # Print to stdout a concise success message (no secrets)
    print("OK: authentication validated; subscribed regions:", ", ".join(regions))
    return 0


def cmd_list_regions(cfg: RunConfig) -> int:
    ctx = _resolve_auth(cfg)
    regions = get_subscribed_regions(ctx)
    for r in regions:
        print(r)
    return 0


def cmd_list_compartments(cfg: RunConfig) -> int:
    ctx = _resolve_auth(cfg)
    comps = oci_list_compartments(ctx, tenancy_ocid=cfg.tenancy_ocid)
    for c in comps:
        print(f'{c["ocid"]},{c["name"]}')
    return 0


def cmd_list_genai_models(cfg: RunConfig) -> int:
    # Intentionally uses the out-of-repo GenAI config file to avoid committing secrets.
    from .genai.config import load_genai_config
    from .genai.list_models import list_genai_models, write_genai_models_csv

    genai_cfg = load_genai_config()
    rows = list_genai_models(genai_cfg=genai_cfg)
    write_genai_models_csv(rows, sys.stdout)
    return 0


def main() -> None:
    try:
        command, cfg = load_run_config()
        setup_logging(LogConfig(level=cfg.log_level, json_logs=cfg.json_logs))

        if command == "run":
            code = cmd_run(cfg)
        elif command == "diff":
            code = cmd_diff(cfg)
        elif command == "validate-auth":
            code = cmd_validate_auth(cfg)
        elif command == "list-regions":
            code = cmd_list_regions(cfg)
        elif command == "list-compartments":
            code = cmd_list_compartments(cfg)
        elif command == "list-genai-models":
            code = cmd_list_genai_models(cfg)
        elif command == "genai-chat":
            code = cmd_genai_chat(cfg)
        else:
            raise ConfigError(f"Unknown command: {command}")

        sys.exit(code)
    except SystemExit:
        raise
    except BrokenPipeError:
        # Common when users pipe to `head` or similar tools.
        # Treat as a normal early-exit and avoid logging after stdout is closed.
        try:
            sys.exit(0)
        except SystemExit:
            raise
    except Exception as e:
        # Map to consistent exit code and log
        try:
            setup_logging(LogConfig())  # ensure something is configured
        except Exception:
            pass
        LOG.error("Execution failed", extra={"error": str(e)})
        sys.exit(as_exit_code(e))


if __name__ == "__main__":
    main()
