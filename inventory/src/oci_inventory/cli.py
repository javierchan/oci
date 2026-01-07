from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .auth.providers import AuthContext, AuthError, resolve_auth
from .config import RunConfig, load_run_config
from .diff.diff import diff_files, write_diff
from .enrich import get_enricher_for
from .export.csv import write_csv
from .export.jsonl import write_jsonl
from .export.parquet import ParquetNotAvailable, write_parquet
from .logging import LogConfig, get_logger, setup_logging
from .normalize.transform import sort_relationships, stable_json_dumps
from .oci.compartments import list_compartments as oci_list_compartments
from .oci.discovery import discover_in_region
from .oci.regions import get_subscribed_regions
from .util.concurrency import parallel_map_ordered
from .util.errors import (
    AuthResolutionError,
    ConfigError,
    as_exit_code,
)

LOG = get_logger(__name__)


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
    LOG.info("Starting inventory run", extra={"outdir": str(cfg.outdir)})
    ctx = _resolve_auth(cfg)

    # Discover regions
    regions = get_subscribed_regions(ctx)
    if not regions:
        raise ConfigError("No subscribed regions found for the tenancy/profile provided")
    if cfg.regions:
        regions = [r for r in cfg.regions if r]
    LOG.info("Discovered subscribed regions", extra={"regions": regions})

    # Per-region discovery in parallel (ordered by region for determinism)
    regions = sorted(regions)
    def _disc(r: str) -> List[Dict[str, Any]]:
        return discover_in_region(ctx, r, cfg.query)

    with ThreadPoolExecutor(max_workers=max(1, cfg.workers_region)) as pool:
        futures = [pool.submit(_disc, r) for r in regions]
        region_results: List[List[Dict[str, Any]]] = [f.result() for f in futures]

    # Flatten discovered records
    discovered: List[Dict[str, Any]] = [rec for sub in region_results for rec in sub]
    LOG.info("Discovery complete", extra={"count": len(discovered)})

    # Enrichment in parallel
    enriched: List[Dict[str, Any]] = []
    all_relationships: List[Dict[str, str]] = []

    def _enrich_and_collect(rec: Dict[str, Any]) -> Dict[str, Any]:
        updated, rels = _enrich_record(rec)
        if rels:
            # side-effect append is safe post-future completion aggregation only; collect via return
            pass
        return {"record": updated, "rels": rels}

    worker_results = parallel_map_ordered(_enrich_and_collect, discovered, max_workers=max(1, cfg.workers_enrich))
    for item in worker_results:
        enriched.append(item["record"])
        all_relationships.extend(item["rels"] or [])

    LOG.info("Enrichment complete", extra={"count": len(enriched)})

    # Exports
    cfg.outdir.mkdir(parents=True, exist_ok=True)
    inventory_jsonl = cfg.outdir / "inventory.jsonl"
    inventory_csv = cfg.outdir / "inventory.csv"
    write_jsonl(enriched, inventory_jsonl)
    write_csv(enriched, inventory_csv)

    parquet_path: Optional[Path] = None
    if cfg.parquet:
        try:
            parquet_path = cfg.outdir / "inventory.parquet"
            write_parquet(enriched, parquet_path)
        except ParquetNotAvailable as e:
            LOG.warning(str(e))

    _write_relationships(cfg.outdir, all_relationships)

    # Coverage metrics and summary
    metrics = _coverage_metrics(enriched)
    _write_run_summary(cfg.outdir, metrics, cfg)

    # Optional diff against previous
    if cfg.prev:
        try:
            diff_obj = diff_files(Path(cfg.prev), inventory_jsonl)
            write_diff(cfg.outdir, diff_obj)
        except Exception as e:
            LOG.warning("Diff failed", extra={"error": str(e)})
            # Not fatal for run; continue

    LOG.info("Run complete", extra={"outdir": str(cfg.outdir)})
    return 0


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
        else:
            raise ConfigError(f"Unknown command: {command}")

        sys.exit(code)
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
