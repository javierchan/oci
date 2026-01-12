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
AUTH_METHODS = {"auto", "config", "instance", "resource", "security_token"}
ALLOWED_CONFIG_KEYS = {
    "outdir",
    "parquet",
    "prev",
    "curr",
    "query",
    "include_terminated",
    "json_logs",
    "log_level",
    "workers_region",
    "workers_enrich",
    "genai_summary",
    "validate_diagrams",
    "regions",
    "auth",
    "profile",
    "tenancy_ocid",
    # cost reporting
    "cost_report",
    "cost_start",
    "cost_end",
    "cost_currency",
    "assessment_target_group",
    "assessment_target_scope",
    "assessment_lens_weights",
    "assessment_capabilities",
    # enrich-coverage
    "inventory",
    "top",
}
BOOL_CONFIG_KEYS = {"parquet", "include_terminated", "json_logs", "genai_summary", "validate_diagrams", "cost_report"}
INT_CONFIG_KEYS = {"workers_region", "workers_enrich", "top"}
PATH_CONFIG_KEYS = {"outdir", "prev", "curr", "inventory"}
STR_CONFIG_KEYS = {
    "query",
    "log_level",
    "auth",
    "profile",
    "tenancy_ocid",
    "cost_start",
    "cost_end",
    "cost_currency",
    "assessment_target_group",
}
LIST_CONFIG_KEYS = {"assessment_target_scope", "assessment_lens_weights", "assessment_capabilities"}


@dataclass(frozen=True)
class RunConfig:
    # General
    outdir: Path
    parquet: bool = False
    prev: Optional[Path] = None
    curr: Optional[Path] = None
    query: str = DEFAULT_QUERY
    include_terminated: bool = False  # reserved for future use of filters
    json_logs: bool = False
    log_level: str = "INFO"

    # Performance
    workers_region: int = DEFAULT_WORKERS_REGION
    workers_enrich: int = DEFAULT_WORKERS_ENRICH
    regions: Optional[List[str]] = None

    # Optional features
    genai_summary: bool = False
    validate_diagrams: bool = False

    # Cost reporting (optional)
    cost_report: bool = False
    cost_start: Optional[str] = None
    cost_end: Optional[str] = None
    cost_currency: Optional[str] = None
    assessment_target_group: Optional[str] = None
    assessment_target_scope: Optional[List[str]] = None
    assessment_lens_weights: Optional[List[str]] = None
    assessment_capabilities: Optional[List[str]] = None

    # GenAI (used by genai-chat)
    genai_api_format: Optional[str] = None  # AUTO|GENERIC|COHERE
    genai_message: Optional[str] = None
    genai_report: Optional[Path] = None
    genai_max_tokens: Optional[int] = None
    genai_temperature: Optional[float] = None

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
            run|diff|validate-auth|list-regions|list-compartments|list-genai-models|genai-chat|enrich-coverage
    """
    parser = argparse.ArgumentParser(prog="oci-inv", description="OCI Inventory CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # common flags builder
    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", type=Path, help="Optional YAML/JSON config file")
        p.add_argument(
            "--json-logs",
            action=argparse.BooleanOptionalAction,
            default=None,
            help="Enable JSON logs",
        )
        p.add_argument("--log-level", default=None, help="Log level (INFO, DEBUG, ...)")
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
    p_run.add_argument("--outdir", type=Path, default=None, help="Output base directory (out/TS)")
    p_run.add_argument(
        "--parquet",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Also write Parquet (pyarrow)",
    )
    p_run.add_argument("--prev", type=Path, default=None, help="Previous inventory.jsonl for diff")
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
            "Generate a GenAI Executive Summary and embed it into report.md "
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
        "--cost-report",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Generate cost_report.md using OCI Usage API (read-only).",
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
    p_diff.add_argument("--prev", type=Path, required=False, help="Previous inventory.jsonl")
    p_diff.add_argument("--curr", type=Path, required=False, help="Current inventory.jsonl")
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

    # genai-chat
    # One-off chat probe for debugging the configured GenAI model/endpoint.
    p_gc = subparsers.add_parser(
        "genai-chat",
        help=(
            "Send a one-off GenAI chat request "
            "(uses OCI_INV_GENAI_CONFIG, else ~/.config/oci-inv/genai.yaml, else inventory/.local/genai.yaml)"
        ),
    )
    add_common(p_gc)
    p_gc.add_argument(
        "--api-format",
        default=None,
        choices=["AUTO", "GENERIC", "COHERE"],
        help="Chat request format (default: AUTO)",
    )
    p_gc.add_argument("--message", default=None, help="Message to send (will be redacted)")
    p_gc.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Path to a report.md to use as context (will be redacted)",
    )
    p_gc.add_argument("--max-tokens", type=int, default=None, help="Max output tokens")
    p_gc.add_argument("--temperature", type=float, default=None, help="Sampling temperature")

    # enrich-coverage
    p_ec = subparsers.add_parser(
        "enrich-coverage",
        help="Show which resource types are missing enrichers for a given inventory.jsonl",
    )
    add_common(p_ec)
    p_ec.add_argument(
        "--inventory",
        type=Path,
        required=True,
        help="Path to an inventory.jsonl file",
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
        "parquet": False,
        "prev": None,
        "curr": None,
        "query": DEFAULT_QUERY,
        "include_terminated": False,
        "json_logs": False,
        "log_level": "INFO",
        "workers_region": DEFAULT_WORKERS_REGION,
        "workers_enrich": DEFAULT_WORKERS_ENRICH,
        "genai_summary": False,
        "validate_diagrams": False,
        "genai_api_format": None,
        "genai_message": None,
        "genai_report": None,
        "genai_max_tokens": None,
        "genai_temperature": None,
        "inventory": None,
        "top": None,
        "auth": "auto",
        "profile": None,
        "tenancy_ocid": None,
        "cost_report": False,
        "cost_start": None,
        "cost_end": None,
        "cost_currency": None,
        "assessment_target_group": None,
        "assessment_target_scope": None,
        "assessment_lens_weights": None,
        "assessment_capabilities": None,
    }

    # config file
    file_cfg: Dict[str, Any] = {}
    if getattr(ns, "config", None):
        file_cfg = _normalize_config_file(_parse_config_file(Path(ns.config)))

    # env
    env_cfg: Dict[str, Any] = _compact_dict(
        {
            "outdir": _env_str("OCI_INV_OUTDIR"),
            "parquet": _env_bool("OCI_INV_PARQUET"),
            "prev": _env_str("OCI_INV_PREV"),
            "curr": _env_str("OCI_INV_CURR"),
            "query": _env_str("OCI_INV_QUERY"),
            "include_terminated": _env_bool("OCI_INV_INCLUDE_TERMINATED"),
            "json_logs": _env_bool("OCI_INV_JSON_LOGS"),
            "log_level": _env_str("OCI_INV_LOG_LEVEL"),
            "workers_region": _env_int("OCI_INV_WORKERS_REGION"),
            "workers_enrich": _env_int("OCI_INV_WORKERS_ENRICH"),
            "genai_summary": _env_bool("OCI_INV_GENAI_SUMMARY"),
            "validate_diagrams": _env_bool("OCI_INV_VALIDATE_DIAGRAMS"),
            "cost_report": _env_bool("OCI_INV_COST_REPORT"),
            "cost_start": _env_str("OCI_INV_COST_START"),
            "cost_end": _env_str("OCI_INV_COST_END"),
            "cost_currency": _env_str("OCI_INV_COST_CURRENCY"),
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
            "parquet": getattr(ns, "parquet", None),
            "prev": getattr(ns, "prev", None),
            "curr": getattr(ns, "curr", None),
            "query": getattr(ns, "query", None),
            "include_terminated": getattr(ns, "include_terminated", None),
            "json_logs": getattr(ns, "json_logs", None),
            "log_level": getattr(ns, "log_level", None),
            "workers_region": getattr(ns, "workers_region", None),
            "workers_enrich": getattr(ns, "workers_enrich", None),
            "genai_summary": getattr(ns, "genai_summary", None),
            "validate_diagrams": getattr(ns, "validate_diagrams", None),
            "cost_report": getattr(ns, "cost_report", None),
            "cost_start": getattr(ns, "cost_start", None),
            "cost_end": getattr(ns, "cost_end", None),
            "cost_currency": getattr(ns, "cost_currency", None),
            "assessment_target_group": getattr(ns, "assessment_target_group", None),
            "assessment_target_scope": getattr(ns, "assessment_target_scope", None),
            "assessment_lens_weights": getattr(ns, "assessment_lens_weight", None),
            "assessment_capabilities": getattr(ns, "assessment_capability", None),
            "genai_api_format": getattr(ns, "api_format", None),
            "genai_message": getattr(ns, "message", None),
            "genai_report": getattr(ns, "report", None),
            "genai_max_tokens": getattr(ns, "max_tokens", None),
            "genai_temperature": getattr(ns, "temperature", None),
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

    # default workers if None
    workers_region = int(merged["workers_region"] or DEFAULT_WORKERS_REGION)
    workers_enrich = int(merged["workers_enrich"] or DEFAULT_WORKERS_ENRICH)

    cfg = RunConfig(
        outdir=outdir,
        parquet=bool(merged["parquet"]),
        prev=prev,
        curr=curr,
        query=str(merged.get("query") or DEFAULT_QUERY),
        include_terminated=bool(merged["include_terminated"]),
        json_logs=bool(merged["json_logs"]),
        log_level=log_level,
        workers_region=workers_region,
        workers_enrich=workers_enrich,
        genai_summary=bool(merged.get("genai_summary")),
        validate_diagrams=bool(merged.get("validate_diagrams")),
        cost_report=bool(merged.get("cost_report")),
        cost_start=str(merged.get("cost_start")) if merged.get("cost_start") else None,
        cost_end=str(merged.get("cost_end")) if merged.get("cost_end") else None,
        cost_currency=str(merged.get("cost_currency")) if merged.get("cost_currency") else None,
        assessment_target_group=str(merged.get("assessment_target_group"))
        if merged.get("assessment_target_group")
        else None,
        assessment_target_scope=assessment_target_scope,
        assessment_lens_weights=assessment_lens_weights,
        assessment_capabilities=assessment_capabilities,
        genai_api_format=str(merged.get("genai_api_format")) if merged.get("genai_api_format") else None,
        genai_message=str(merged.get("genai_message")) if merged.get("genai_message") else None,
        genai_report=Path(merged.get("genai_report")) if merged.get("genai_report") else None,
        genai_max_tokens=int(merged.get("genai_max_tokens")) if merged.get("genai_max_tokens") else None,
        genai_temperature=float(merged.get("genai_temperature")) if merged.get("genai_temperature") else None,
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
        "parquet": cfg.parquet,
        "prev": str(cfg.prev) if cfg.prev else None,
        "curr": str(cfg.curr) if cfg.curr else None,
        "query": cfg.query,
        "include_terminated": cfg.include_terminated,
        "json_logs": cfg.json_logs,
        "log_level": cfg.log_level,
        "workers_region": cfg.workers_region,
        "workers_enrich": cfg.workers_enrich,
        "genai_summary": cfg.genai_summary,
        "validate_diagrams": cfg.validate_diagrams,
        "cost_report": cfg.cost_report,
        "cost_start": cfg.cost_start,
        "cost_end": cfg.cost_end,
        "cost_currency": cfg.cost_currency,
        "assessment_target_group": cfg.assessment_target_group,
        "assessment_target_scope": cfg.assessment_target_scope,
        "assessment_lens_weights": cfg.assessment_lens_weights,
        "assessment_capabilities": cfg.assessment_capabilities,
        "regions": cfg.regions,
        "auth": cfg.auth,
        "profile": cfg.profile,
        "tenancy_ocid": cfg.tenancy_ocid,
        "genai_api_format": cfg.genai_api_format,
        "genai_message": cfg.genai_message,
        "genai_report": str(cfg.genai_report) if cfg.genai_report else None,
        "genai_max_tokens": cfg.genai_max_tokens,
        "genai_temperature": cfg.genai_temperature,
        "inventory": str(cfg.inventory) if cfg.inventory else None,
        "top": cfg.top,
        "collected_at": cfg.collected_at,
    }
