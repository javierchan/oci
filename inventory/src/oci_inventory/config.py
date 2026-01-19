from __future__ import annotations

import argparse
import json
import os
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

# --------
# Defaults
# --------
DEFAULT_QUERY = "query all resources"
DEFAULT_WORKERS_REGION = 6
DEFAULT_WORKERS_ENRICH = 24
DEFAULT_WORKERS_COST = 1
DEFAULT_WORKERS_EXPORT = 1
DEFAULT_CLIENT_CONNECTION_POOL_SIZE = 24
DEFAULT_SCHEMA_VALIDATION = "auto"
DEFAULT_SCHEMA_SAMPLE_RECORDS = 5000
DEFAULT_DIAGRAM_DEPTH = 2
AUTH_METHODS = {"auto", "config", "instance", "resource", "security_token"}
ALLOWED_CONFIG_KEYS = {
    "outdir",
    "prev",
    "curr",
    "query",
    "include_terminated",
    "json_logs",
    "log_level",
    "workers_region",
    "workers_enrich",
    "workers_cost",
    "workers_export",
    "client_connection_pool_size",
    "genai_summary",
    "validate_diagrams",
    "diagrams",
    "schema_validation",
    "schema_sample_records",
    "diagram_depth",
    "regions",
    "auth",
    "profile",
    "tenancy_ocid",
    # cost reporting
    "cost_report",
    "cost_start",
    "cost_end",
    "cost_currency",
    "cost_compartment_group_by",
    "cost_group_by",
    "osub_subscription_id",
    "assessment_target_group",
    "assessment_target_scope",
    "assessment_lens_weights",
    "assessment_capabilities",
    # enrich-coverage
    "inventory",
    "top",
}
BOOL_CONFIG_KEYS = {
    "include_terminated",
    "json_logs",
    "genai_summary",
    "validate_diagrams",
    "diagrams",
    "cost_report",
}
INT_CONFIG_KEYS = {
    "workers_region",
    "workers_enrich",
    "workers_cost",
    "workers_export",
    "client_connection_pool_size",
    "schema_sample_records",
    "diagram_depth",
    "top",
}
PATH_CONFIG_KEYS = {"outdir", "prev", "curr", "inventory"}
STR_CONFIG_KEYS = {
    "query",
    "log_level",
    "auth",
    "profile",
    "tenancy_ocid",
    "schema_validation",
    "cost_start",
    "cost_end",
    "cost_currency",
    "cost_compartment_group_by",
    "osub_subscription_id",
    "assessment_target_group",
}
LIST_CONFIG_KEYS = {
    "assessment_target_scope",
    "assessment_lens_weights",
    "assessment_capabilities",
    "cost_group_by",
}


@dataclass(frozen=True)
class RunConfig:
    # General
    outdir: Path
    prev: Optional[Path] = None
    curr: Optional[Path] = None
    query: str = DEFAULT_QUERY
    include_terminated: bool = False  # reserved for future use of filters
    json_logs: bool = False
    log_level: str = "INFO"

    # Performance
    workers_region: int = DEFAULT_WORKERS_REGION
    workers_enrich: int = DEFAULT_WORKERS_ENRICH
    workers_cost: int = DEFAULT_WORKERS_COST
    workers_export: int = DEFAULT_WORKERS_EXPORT
    client_connection_pool_size: Optional[int] = DEFAULT_CLIENT_CONNECTION_POOL_SIZE
    regions: Optional[List[str]] = None

    # Optional features
    genai_summary: bool = False
    validate_diagrams: bool = False
    diagrams: bool = True
    schema_validation: str = DEFAULT_SCHEMA_VALIDATION
    schema_sample_records: int = DEFAULT_SCHEMA_SAMPLE_RECORDS
    diagram_depth: int = DEFAULT_DIAGRAM_DEPTH

    # Cost reporting (optional)
    cost_report: bool = False
    cost_start: Optional[str] = None
    cost_end: Optional[str] = None
    cost_currency: Optional[str] = None
    cost_compartment_group_by: Optional[str] = None
    cost_group_by: Optional[List[str]] = None
    osub_subscription_id: Optional[str] = None
    assessment_target_group: Optional[str] = None
    assessment_target_scope: Optional[List[str]] = None
    assessment_lens_weights: Optional[List[str]] = None
    assessment_capabilities: Optional[List[str]] = None

    # Enrichment coverage (used by enrich-coverage)
    inventory: Optional[Path] = None
    top: Optional[int] = None

    # Auth
    auth: str = "auto"  # auto|config|instance|resource|security_token
    profile: Optional[str] = None
    tenancy_ocid: Optional[str] = None  # used for validate-auth/list-*

    # Internal/derived
    collected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


def _parse_config_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    text = path.read_text(encoding="utf-8")
    try:
        if path.suffix.lower() in {".yaml", ".yml"}:
            data = yaml.safe_load(text) or {}
        elif path.suffix.lower() == ".json":
            data = json.loads(text)
        else:
            # Try YAML first then JSON
            try:
                data = yaml.safe_load(text) or {}
            except Exception:
                data = json.loads(text)
    except Exception as e:
        raise ValueError(f"Failed to parse config file {path}: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("Top-level config must be an object")
    return data


def _env_str(name: str) -> Optional[str]:
    raw = os.getenv(name)
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    return raw


def _env_bool(name: str) -> Optional[bool]:
    raw = os.getenv(name)
    if raw is None:
        return None
    raw = raw.strip().lower()
    if not raw:
        return None
    return raw in {"1", "true", "yes", "on"}


def _env_int(name: str) -> Optional[int]:
    raw = os.getenv(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _coerce_bool(key: str, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"Config field '{key}' must be a boolean")


def _coerce_int(key: str, value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return int(value)
        except Exception:
            pass
    raise ValueError(f"Config field '{key}' must be an integer")


def _normalize_config_file(data: Dict[str, Any]) -> Dict[str, Any]:
    unknown = sorted(set(data.keys()) - ALLOWED_CONFIG_KEYS)
    if unknown:
        warnings.warn(f"Unknown config keys ignored: {', '.join(unknown)}")
    normalized: Dict[str, Any] = {}
    for key, value in data.items():
        if key not in ALLOWED_CONFIG_KEYS:
            continue
        if value is None:
            normalized[key] = None
            continue
        if key == "regions":
            if isinstance(value, str):
                regions = [r.strip() for r in value.split(",") if r.strip()]
                normalized[key] = regions
            elif isinstance(value, list) and all(isinstance(r, str) for r in value):
                normalized[key] = [r.strip() for r in value if r.strip()]
            else:
                raise ValueError("Config field 'regions' must be a list of strings or comma-separated string")
        elif key in BOOL_CONFIG_KEYS:
            normalized[key] = _coerce_bool(key, value)
        elif key in INT_CONFIG_KEYS:
            normalized[key] = _coerce_int(key, value)
        elif key in PATH_CONFIG_KEYS:
            if isinstance(value, (str, Path)):
                normalized[key] = value
            else:
                raise ValueError(f"Config field '{key}' must be a string path")
        elif key in LIST_CONFIG_KEYS:
            if isinstance(value, str):
                items = [v.strip() for v in value.split(",") if v.strip()]
                normalized[key] = items
            elif isinstance(value, list) and all(isinstance(v, str) for v in value):
                normalized[key] = [v.strip() for v in value if v.strip()]
            else:
                raise ValueError(f"Config field '{key}' must be a list of strings or comma-separated string")
        elif key in STR_CONFIG_KEYS:
            if isinstance(value, str):
                normalized[key] = value
            else:
                raise ValueError(f"Config field '{key}' must be a string")
        else:
            normalized[key] = value
    auth = normalized.get("auth")
    if auth is not None:
        auth = str(auth).lower()
        if auth not in AUTH_METHODS:
            raise ValueError(f"Config field 'auth' must be one of: {', '.join(sorted(AUTH_METHODS))}")
        normalized["auth"] = auth
    return _compact_dict(normalized)


def _compact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Drop keys with None values so they don't override lower-precedence config.
    """
    return {k: v for k, v in data.items() if v is not None}


def _merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """
    Shallow merge: values in b override a.
    """
    merged = dict(a)
    merged.update(b)
    return merged


def _timestamp_dir(base: Optional[Union[str, Path]]) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if base:
        return Path(base) / ts
    return Path("out") / ts


def load_run_config(
    args: Optional[argparse.Namespace] = None,
    argv: Optional[list[str]] = None,
    subcommand: Optional[str] = None,
) -> Tuple[str, RunConfig]:
    """
    Build RunConfig by merging defaults, optional config file, env vars, and CLI args.
    Precedence (low -> high): defaults < config file < env < CLI.

    Returns:
            (command, RunConfig) where command is the subcommand selected:
            run|diff|validate-auth|list-regions|list-compartments|list-genai-models|enrich-coverage
    """
    parser = argparse.ArgumentParser(prog="oci-inv", description="OCI Inventory CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # common flags builder
    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--config",
            type=Path,
            help="Optional YAML/JSON config file (defaults to config/workers.yaml when present)",
        )
        p.add_argument(
            "--json-logs",
            action=argparse.BooleanOptionalAction,
            default=None,
            help="Enable JSON logs",
        )
        p.add_argument("--log-level", default=None, help="Log level (INFO, DEBUG, ...)")
        p.add_argument(
            "--client-connection-pool-size",
            type=int,
            default=None,
            help=(
                "HTTP connection pool size per OCI SDK client "
                f"(default {DEFAULT_CLIENT_CONNECTION_POOL_SIZE} when repo defaults are used)"
            ),
        )
        # Auth
        p.add_argument(
            "--auth",
            default=None,
            choices=["auto", "config", "instance", "resource", "security_token"],
            help="Auth method (default: auto)",
        )
        p.add_argument("--profile", default=None, help="OCI config profile (for config auth)")
        p.add_argument(
            "--tenancy",
            dest="tenancy_ocid",
            default=None,
            help="Tenancy OCID (required for some ops if not using config auth)",
        )

    # run
    p_run = subparsers.add_parser("run", help="Run inventory collection")
    add_common(p_run)
    p_run.add_argument(
        "--outdir",
        type=Path,
        default=None,
        help="Output base directory (out/TS with structured subfolders)",
    )
    p_run.add_argument(
        "--prev",
        type=Path,
        default=None,
        help="Previous inventory JSONL for diff (e.g., out/TS/inventory/inventory.jsonl)",
    )
    p_run.add_argument(
        "--query",
        default=None,
        help='Structured Search query (default: "query all resources")',
    )
    p_run.add_argument(
        "--workers-region", type=int, default=None, help=f"Max parallel regions (default {DEFAULT_WORKERS_REGION})"
    )
    p_run.add_argument(
        "--workers-enrich", type=int, default=None, help=f"Max enricher workers (default {DEFAULT_WORKERS_ENRICH})"
    )
    p_run.add_argument(
        "--workers-cost",
        type=int,
        default=None,
        help=f"Max parallel cost API tasks (opt-in; default {DEFAULT_WORKERS_COST})",
    )
    p_run.add_argument(
        "--workers-export",
        type=int,
        default=None,
        help=f"Max parallel export tasks (opt-in; default {DEFAULT_WORKERS_EXPORT})",
    )
    p_run.add_argument(
        "--regions",
        default=None,
        help="Comma-separated list of regions to query (overrides subscriptions)",
    )
    p_run.add_argument(
        "--include-terminated",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include terminated resources (future use)",
    )

    p_run.add_argument(
        "--genai-summary",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Generate a GenAI Executive Summary and embed it into report/report.md "
            "(uses OCI_INV_GENAI_CONFIG, else ~/.config/oci-inv/genai.yaml, else inventory/.local/genai.yaml)"
        ),
    )

    p_run.add_argument(
        "--validate-diagrams",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Require Mermaid diagram validation using the external 'mmdc' command "
            "(@mermaid-js/mermaid-cli). Fails the run if mmdc is missing or validation fails. "
            "(If mmdc is present, diagrams are validated automatically even without this flag.)"
        ),
    )
    p_run.add_argument(
        "--diagrams",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Generate graph artifacts and Mermaid diagram projections (disable with --no-diagrams).",
    )
    p_run.add_argument(
        "--validate-schema",
        choices=["auto", "full", "sampled", "off"],
        default=None,
        help=(
            "Schema validation mode for outputs: auto (default), full, sampled, or off. "
            "Auto switches to sampling for large inventory/inventory.jsonl files."
        ),
    )
    p_run.add_argument(
        "--validate-schema-sample",
        type=int,
        default=None,
        help=f"Records to scan when --validate-schema=sampled (default {DEFAULT_SCHEMA_SAMPLE_RECORDS}).",
    )
    p_run.add_argument(
        "--diagram-depth",
        type=int,
        default=None,
        help="Depth for consolidated diagrams (1=network, 2=workloads, 3=workloads+edges).",
    )

    p_run.add_argument(
        "--cost-report",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Generate cost/cost_report.md using OCI Usage API (read-only).",
    )
    p_run.add_argument(
        "--cost-start",
        default=None,
        help="UTC start time (ISO 8601) for cost reporting (default: month-to-date).",
    )
    p_run.add_argument(
        "--cost-end",
        default=None,
        help="UTC end time (ISO 8601) for cost reporting (default: now).",
    )
    p_run.add_argument(
        "--cost-currency",
        default=None,
        help="ISO 4217 currency code (optional if Usage API returns currency).",
    )
    p_run.add_argument(
        "--cost-compartment-group-by",
        choices=("compartmentId", "compartmentName", "compartmentPath"),
        default=None,
        help="Group cost by compartmentId (default), compartmentName, or compartmentPath.",
    )
    p_run.add_argument(
        "--cost-group-by",
        default=None,
        help="Comma-separated Usage API group_by list for combined cost usage items (opt-in).",
    )
    p_run.add_argument(
        "--osub-subscription-id",
        default=None,
        help="OneSubscription subscription ID for ComputedUsageClient (optional).",
    )
    p_run.add_argument(
        "--assessment-target-group",
        default=None,
        help="Assessment target group (team, business unit, or org).",
    )
    p_run.add_argument(
        "--assessment-target-scope",
        action="append",
        default=None,
        help="Assessment target scope entry (repeatable).",
    )
    p_run.add_argument(
        "--assessment-lens-weight",
        action="append",
        default=None,
        help="Assessment lens weight, e.g. Knowledge=1 (repeatable).",
    )
    p_run.add_argument(
        "--assessment-capability",
        action="append",
        default=None,
        help=(
            "Assessment capability entry (repeatable). Format: "
            "domain|capability|knowledge|process|metrics|adoption|automation|target|evidence"
        ),
    )

    # diff
    p_diff = subparsers.add_parser("diff", help="Diff two inventory JSONL files")
    add_common(p_diff)
    p_diff.add_argument(
        "--prev",
        type=Path,
        required=False,
        help="Previous inventory JSONL (e.g., out/TS/inventory/inventory.jsonl)",
    )
    p_diff.add_argument(
        "--curr",
        type=Path,
        required=False,
        help="Current inventory JSONL (e.g., out/TS/inventory/inventory.jsonl)",
    )
    p_diff.add_argument("--outdir", type=Path, default=None, help="Output dir for diff files")

    # validate-auth
    p_val = subparsers.add_parser("validate-auth", help="Validate authentication setup")
    add_common(p_val)

    # list-regions
    p_lr = subparsers.add_parser("list-regions", help="List subscribed regions")
    add_common(p_lr)

    # list-compartments
    p_lc = subparsers.add_parser("list-compartments", help="List compartments in tenancy")
    add_common(p_lc)

    # list-genai-models
    # Uses OCI_INV_GENAI_CONFIG, else ~/.config/oci-inv/genai.yaml, else inventory/.local/genai.yaml.
    p_lgm = subparsers.add_parser(
        "list-genai-models",
        help=(
            "List OCI GenAI models and capabilities "
            "(uses OCI_INV_GENAI_CONFIG, else ~/.config/oci-inv/genai.yaml, else inventory/.local/genai.yaml)"
        ),
    )
    add_common(p_lgm)

    # enrich-coverage
    p_ec = subparsers.add_parser(
        "enrich-coverage",
        help="Show which resource types are missing enrichers for a given inventory JSONL",
    )
    add_common(p_ec)
    p_ec.add_argument(
        "--inventory",
        type=Path,
        required=True,
        help="Path to an inventory JSONL file (e.g., out/TS/inventory/inventory.jsonl)",
    )
    p_ec.add_argument(
        "--top",
        type=int,
        default=20,
        help="Show top N missing resource types (default: 20)",
    )

    ns = args if args is not None else parser.parse_args(argv)
    command = ns.command if subcommand is None else subcommand

    # defaults
    base: Dict[str, Any] = {
        "outdir": None,
        "prev": None,
        "curr": None,
        "query": DEFAULT_QUERY,
        "include_terminated": False,
        "json_logs": False,
        "log_level": "INFO",
        "workers_region": DEFAULT_WORKERS_REGION,
        "workers_enrich": DEFAULT_WORKERS_ENRICH,
        "workers_cost": DEFAULT_WORKERS_COST,
        "workers_export": DEFAULT_WORKERS_EXPORT,
        "client_connection_pool_size": DEFAULT_CLIENT_CONNECTION_POOL_SIZE,
        "genai_summary": False,
        "validate_diagrams": False,
        "diagrams": True,
        "schema_validation": DEFAULT_SCHEMA_VALIDATION,
        "schema_sample_records": DEFAULT_SCHEMA_SAMPLE_RECORDS,
        "diagram_depth": DEFAULT_DIAGRAM_DEPTH,
        "inventory": None,
        "top": None,
        "auth": "auto",
        "profile": None,
        "tenancy_ocid": None,
        "cost_report": False,
        "cost_start": None,
        "cost_end": None,
        "cost_currency": None,
        "cost_compartment_group_by": None,
        "cost_group_by": None,
        "osub_subscription_id": None,
        "assessment_target_group": None,
        "assessment_target_scope": None,
        "assessment_lens_weights": None,
        "assessment_capabilities": None,
    }

    # config file (auto-load repo defaults when present)
    file_cfg: Dict[str, Any] = {}
    if getattr(ns, "config", None):
        file_cfg = _normalize_config_file(_parse_config_file(Path(ns.config)))
    else:
        default_cfg_path = Path("config") / "workers.yaml"
        if default_cfg_path.exists():
            file_cfg = _normalize_config_file(_parse_config_file(default_cfg_path))

    # env
    env_cfg: Dict[str, Any] = _compact_dict(
        {
            "outdir": _env_str("OCI_INV_OUTDIR"),
            "prev": _env_str("OCI_INV_PREV"),
            "curr": _env_str("OCI_INV_CURR"),
            "query": _env_str("OCI_INV_QUERY"),
            "include_terminated": _env_bool("OCI_INV_INCLUDE_TERMINATED"),
            "json_logs": _env_bool("OCI_INV_JSON_LOGS"),
            "log_level": _env_str("OCI_INV_LOG_LEVEL"),
            "workers_region": _env_int("OCI_INV_WORKERS_REGION"),
            "workers_enrich": _env_int("OCI_INV_WORKERS_ENRICH"),
            "workers_cost": _env_int("OCI_INV_WORKERS_COST"),
            "workers_export": _env_int("OCI_INV_WORKERS_EXPORT"),
            "client_connection_pool_size": _env_int("OCI_INV_CLIENT_CONNECTION_POOL_SIZE"),
            "genai_summary": _env_bool("OCI_INV_GENAI_SUMMARY"),
            "validate_diagrams": _env_bool("OCI_INV_VALIDATE_DIAGRAMS"),
            "diagrams": _env_bool("OCI_INV_DIAGRAMS"),
            "schema_validation": _env_str("OCI_INV_SCHEMA_VALIDATION"),
            "schema_sample_records": _env_int("OCI_INV_SCHEMA_SAMPLE_RECORDS"),
            "diagram_depth": _env_int("OCI_INV_DIAGRAM_DEPTH"),
            "cost_report": _env_bool("OCI_INV_COST_REPORT"),
            "cost_start": _env_str("OCI_INV_COST_START"),
            "cost_end": _env_str("OCI_INV_COST_END"),
            "cost_currency": _env_str("OCI_INV_COST_CURRENCY"),
            "cost_compartment_group_by": _env_str("OCI_INV_COST_COMPARTMENT_GROUP_BY"),
            "cost_group_by": _env_str("OCI_INV_COST_GROUP_BY"),
            "osub_subscription_id": _env_str("OCI_INV_OSUB_SUBSCRIPTION_ID"),
            "assessment_target_group": _env_str("OCI_INV_ASSESSMENT_TARGET_GROUP"),
            "assessment_target_scope": _env_str("OCI_INV_ASSESSMENT_TARGET_SCOPE"),
            "assessment_lens_weights": _env_str("OCI_INV_ASSESSMENT_LENS_WEIGHTS"),
            "assessment_capabilities": _env_str("OCI_INV_ASSESSMENT_CAPABILITIES"),
            "regions": _env_str("OCI_INV_REGIONS"),
            "auth": _env_str("OCI_INV_AUTH"),
            "profile": _env_str("OCI_INV_PROFILE"),
            "tenancy_ocid": _env_str("OCI_TENANCY_OCID"),
        }
    )

    # CLI
    cli_cfg: Dict[str, Any] = _compact_dict(
        {
            "outdir": getattr(ns, "outdir", None),
            "prev": getattr(ns, "prev", None),
            "curr": getattr(ns, "curr", None),
            "query": getattr(ns, "query", None),
            "include_terminated": getattr(ns, "include_terminated", None),
            "json_logs": getattr(ns, "json_logs", None),
            "log_level": getattr(ns, "log_level", None),
            "workers_region": getattr(ns, "workers_region", None),
            "workers_enrich": getattr(ns, "workers_enrich", None),
            "workers_cost": getattr(ns, "workers_cost", None),
            "workers_export": getattr(ns, "workers_export", None),
            "client_connection_pool_size": getattr(ns, "client_connection_pool_size", None),
            "genai_summary": getattr(ns, "genai_summary", None),
            "validate_diagrams": getattr(ns, "validate_diagrams", None),
            "diagrams": getattr(ns, "diagrams", None),
            "schema_validation": getattr(ns, "validate_schema", None),
            "schema_sample_records": getattr(ns, "validate_schema_sample", None),
            "diagram_depth": getattr(ns, "diagram_depth", None),
            "cost_report": getattr(ns, "cost_report", None),
            "cost_start": getattr(ns, "cost_start", None),
            "cost_end": getattr(ns, "cost_end", None),
            "cost_currency": getattr(ns, "cost_currency", None),
            "cost_compartment_group_by": getattr(ns, "cost_compartment_group_by", None),
            "cost_group_by": getattr(ns, "cost_group_by", None),
            "osub_subscription_id": getattr(ns, "osub_subscription_id", None),
            "assessment_target_group": getattr(ns, "assessment_target_group", None),
            "assessment_target_scope": getattr(ns, "assessment_target_scope", None),
            "assessment_lens_weights": getattr(ns, "assessment_lens_weight", None),
            "assessment_capabilities": getattr(ns, "assessment_capability", None),
            "inventory": getattr(ns, "inventory", None),
            "top": getattr(ns, "top", None),
            "regions": getattr(ns, "regions", None),
            "auth": getattr(ns, "auth", None),
            "profile": getattr(ns, "profile", None),
            "tenancy_ocid": getattr(ns, "tenancy_ocid", None),
        }
    )

    merged = _merge_dicts(base, _merge_dicts(file_cfg, _merge_dicts(env_cfg, cli_cfg)))

    # Normalize/construct types
    outdir_raw = merged.get("outdir")
    outdir = _timestamp_dir(outdir_raw) if command == "run" else Path(outdir_raw) if outdir_raw else Path.cwd()
    prev = Path(merged["prev"]) if merged.get("prev") else None
    curr = Path(merged["curr"]) if merged.get("curr") else None
    profile = merged.get("profile")
    tenancy = merged.get("tenancy_ocid")
    log_level = (merged.get("log_level") or "INFO").upper()
    regions_raw = merged.get("regions")
    regions: Optional[List[str]] = None
    if isinstance(regions_raw, list):
        regions = [str(r).strip() for r in regions_raw if str(r).strip()]
    elif isinstance(regions_raw, str):
        regions = [r.strip() for r in regions_raw.split(",") if r.strip()]

    def _parse_list_field(raw: Any) -> Optional[List[str]]:
        if raw is None:
            return None
        if isinstance(raw, list):
            return [str(v).strip() for v in raw if str(v).strip()]
        if isinstance(raw, str):
            return [v.strip() for v in raw.split(",") if v.strip()]
        return None

    assessment_target_scope = _parse_list_field(merged.get("assessment_target_scope"))
    assessment_lens_weights = _parse_list_field(merged.get("assessment_lens_weights"))
    assessment_capabilities = _parse_list_field(merged.get("assessment_capabilities"))

    comp_group_by_raw = merged.get("cost_compartment_group_by")
    cost_compartment_group_by = None
    if comp_group_by_raw is not None:
        cost_compartment_group_by = str(comp_group_by_raw).strip()
        if cost_compartment_group_by not in {"compartmentId", "compartmentName", "compartmentPath"}:
            raise ValueError(
                "cost_compartment_group_by must be one of compartmentId, compartmentName, compartmentPath"
            )

    cost_group_by_raw = merged.get("cost_group_by")
    cost_group_by = _parse_list_field(cost_group_by_raw)
    if cost_group_by:
        allowed_cost_group_by = {"service", "region", "compartmentId", "compartmentName", "compartmentPath", "sku"}
        deduped: List[str] = []
        for value in cost_group_by:
            if value in deduped:
                continue
            deduped.append(value)
        invalid = [value for value in deduped if value not in allowed_cost_group_by]
        if invalid:
            raise ValueError(
                "cost_group_by must be a comma-separated list of: "
                "service, region, compartmentId, compartmentName, compartmentPath, sku"
            )
        cost_group_by = deduped

    # default workers if None
    workers_region = int(merged["workers_region"] or DEFAULT_WORKERS_REGION)
    workers_enrich = int(merged["workers_enrich"] or DEFAULT_WORKERS_ENRICH)
    workers_cost = int(merged["workers_cost"] or DEFAULT_WORKERS_COST)
    workers_export = int(merged["workers_export"] or DEFAULT_WORKERS_EXPORT)
    client_connection_pool_size = merged.get("client_connection_pool_size")
    if client_connection_pool_size is not None:
        client_connection_pool_size = int(client_connection_pool_size)
        if client_connection_pool_size < 1:
            raise ValueError("client_connection_pool_size must be >= 1")
    schema_validation = str(merged.get("schema_validation") or DEFAULT_SCHEMA_VALIDATION).strip().lower()
    if schema_validation not in {"auto", "full", "sampled", "off"}:
        raise ValueError("schema_validation must be one of auto, full, sampled, off")
    schema_sample_records = int(merged.get("schema_sample_records") or DEFAULT_SCHEMA_SAMPLE_RECORDS)
    if schema_sample_records < 1:
        schema_sample_records = DEFAULT_SCHEMA_SAMPLE_RECORDS
    diagram_depth = int(merged.get("diagram_depth") or DEFAULT_DIAGRAM_DEPTH)
    if diagram_depth not in {1, 2, 3}:
        raise ValueError("diagram_depth must be 1, 2, or 3")

    cfg = RunConfig(
        outdir=outdir,
        prev=prev,
        curr=curr,
        query=str(merged.get("query") or DEFAULT_QUERY),
        include_terminated=bool(merged["include_terminated"]),
        json_logs=bool(merged["json_logs"]),
        log_level=log_level,
        workers_region=workers_region,
        workers_enrich=workers_enrich,
        workers_cost=workers_cost,
        workers_export=workers_export,
        client_connection_pool_size=client_connection_pool_size,
        genai_summary=bool(merged.get("genai_summary")),
        validate_diagrams=bool(merged.get("validate_diagrams")),
        diagrams=bool(merged.get("diagrams")),
        schema_validation=schema_validation,
        schema_sample_records=schema_sample_records,
        diagram_depth=diagram_depth,
        cost_report=bool(merged.get("cost_report")),
        cost_start=str(merged.get("cost_start")) if merged.get("cost_start") else None,
        cost_end=str(merged.get("cost_end")) if merged.get("cost_end") else None,
        cost_currency=str(merged.get("cost_currency")) if merged.get("cost_currency") else None,
        cost_compartment_group_by=cost_compartment_group_by,
        cost_group_by=cost_group_by,
        osub_subscription_id=str(merged.get("osub_subscription_id"))
        if merged.get("osub_subscription_id")
        else None,
        assessment_target_group=str(merged.get("assessment_target_group"))
        if merged.get("assessment_target_group")
        else None,
        assessment_target_scope=assessment_target_scope,
        assessment_lens_weights=assessment_lens_weights,
        assessment_capabilities=assessment_capabilities,
        inventory=Path(merged.get("inventory")) if merged.get("inventory") else None,
        top=int(merged.get("top")) if merged.get("top") is not None else None,
        regions=regions or None,
        auth=str(merged["auth"] or "auto"),
        profile=str(profile) if profile else None,
        tenancy_ocid=str(tenancy) if tenancy else None,
    )
    return command, cfg


def dump_config(cfg: RunConfig) -> Dict[str, Any]:
    return {
        "outdir": str(cfg.outdir),
        "prev": str(cfg.prev) if cfg.prev else None,
        "curr": str(cfg.curr) if cfg.curr else None,
        "query": cfg.query,
        "include_terminated": cfg.include_terminated,
        "json_logs": cfg.json_logs,
        "log_level": cfg.log_level,
        "workers_region": cfg.workers_region,
        "workers_enrich": cfg.workers_enrich,
        "workers_cost": cfg.workers_cost,
        "workers_export": cfg.workers_export,
        "client_connection_pool_size": cfg.client_connection_pool_size,
        "genai_summary": cfg.genai_summary,
        "validate_diagrams": cfg.validate_diagrams,
        "diagrams": cfg.diagrams,
        "schema_validation": cfg.schema_validation,
        "schema_sample_records": cfg.schema_sample_records,
        "diagram_depth": cfg.diagram_depth,
        "cost_report": cfg.cost_report,
        "cost_start": cfg.cost_start,
        "cost_end": cfg.cost_end,
        "cost_currency": cfg.cost_currency,
        "cost_compartment_group_by": cfg.cost_compartment_group_by,
        "cost_group_by": cfg.cost_group_by,
        "osub_subscription_id": cfg.osub_subscription_id,
        "assessment_target_group": cfg.assessment_target_group,
        "assessment_target_scope": cfg.assessment_target_scope,
        "assessment_lens_weights": cfg.assessment_lens_weights,
        "assessment_capabilities": cfg.assessment_capabilities,
        "regions": cfg.regions,
        "auth": cfg.auth,
        "profile": cfg.profile,
        "tenancy_ocid": cfg.tenancy_ocid,
        "inventory": str(cfg.inventory) if cfg.inventory else None,
        "top": cfg.top,
        "collected_at": cfg.collected_at,
    }
