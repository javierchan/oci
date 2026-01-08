from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .plan import (
    WizardPlan,
    build_diff_plan,
    build_coverage_plan,
    build_run_plan,
    build_simple_plan,
)


def _as_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _as_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y"}:
        return True
    if s in {"0", "false", "no", "n"}:
        return False
    return None


def _as_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def _as_regions(v: Any) -> Optional[List[str]]:
    if v is None:
        return None
    if isinstance(v, list):
        out = [str(x).strip() for x in v if str(x).strip()]
        return out or None
    s = str(v).strip()
    if not s:
        return None
    out = [p.strip() for p in s.split(",") if p.strip()]
    return out or None


def _load_data(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".json"}:
        return dict(json.loads(raw))
    if suffix in {".yml", ".yaml"}:
        obj = yaml.safe_load(raw)
        if obj is None:
            return {}
        if not isinstance(obj, dict):
            raise ValueError("Wizard config must be a mapping/object")
        return dict(obj)
    raise ValueError("Unsupported wizard config file type; use .yaml/.yml or .json")


def load_wizard_plan_from_file(path: Path) -> WizardPlan:
    """Load a non-interactive wizard plan from a YAML/JSON file.

        Schema (minimal):
            mode: run|diff|validate-auth|list-regions|list-compartments|enrich-coverage
      auth: auto|config|instance|resource|security_token
      profile: optional
      tenancy_ocid: optional
      json_logs: optional bool
      log_level: optional (INFO/DEBUG/...)

    For mode=run:
      outdir: required (base directory)
      query: required
      regions: optional list or comma-separated string
      parquet: optional bool
            genai_summary: optional bool
      prev: optional path
      workers_region: optional int
      workers_enrich: optional int

    For mode=diff:
      prev: required path
      curr: required path
      outdir: required path
    """

    cfg = _load_data(path)

    mode = _as_str(cfg.get("mode"))
    if mode is None:
        raise ValueError("Wizard config missing required field: mode")

    auth = _as_str(cfg.get("auth"))
    if auth is None:
        raise ValueError("Wizard config missing required field: auth")

    profile = _as_str(cfg.get("profile"))
    tenancy_ocid = _as_str(cfg.get("tenancy_ocid"))
    json_logs = _as_bool(cfg.get("json_logs"))
    log_level = _as_str(cfg.get("log_level"))

    if mode in {"validate-auth", "list-regions", "list-compartments"}:
        return build_simple_plan(
            subcommand=mode,
            auth=auth,
            profile=profile,
            tenancy_ocid=tenancy_ocid,
            json_logs=json_logs,
            log_level=log_level,
        )

    if mode == "diff":
        prev = _as_str(cfg.get("prev"))
        curr = _as_str(cfg.get("curr"))
        outdir = _as_str(cfg.get("outdir"))
        if not prev or not curr or not outdir:
            raise ValueError("Wizard diff config requires: prev, curr, outdir")
        return build_diff_plan(
            auth=auth,
            profile=profile,
            tenancy_ocid=tenancy_ocid,
            prev=Path(prev),
            curr=Path(curr),
            outdir=Path(outdir),
            json_logs=json_logs,
            log_level=log_level,
        )

    if mode == "enrich-coverage":
        inventory = _as_str(cfg.get("inventory"))
        top = _as_int(cfg.get("top"))
        if not inventory:
            raise ValueError("Wizard enrich-coverage config requires: inventory")
        return build_coverage_plan(
            inventory=Path(inventory),
            top=top,
        )

    if mode == "run":
        outdir = _as_str(cfg.get("outdir"))
        query = _as_str(cfg.get("query"))
        if not outdir or not query:
            raise ValueError("Wizard run config requires: outdir, query")

        regions = _as_regions(cfg.get("regions"))
        parquet = _as_bool(cfg.get("parquet"))
        genai_summary = _as_bool(cfg.get("genai_summary"))
        prev_s = _as_str(cfg.get("prev"))
        workers_region = _as_int(cfg.get("workers_region"))
        workers_enrich = _as_int(cfg.get("workers_enrich"))
        include_terminated = _as_bool(cfg.get("include_terminated"))

        return build_run_plan(
            auth=auth,
            profile=profile,
            tenancy_ocid=tenancy_ocid,
            outdir=Path(outdir),
            query=query,
            regions=regions,
            parquet=parquet,
            genai_summary=genai_summary,
            prev=Path(prev_s) if prev_s else None,
            workers_region=workers_region,
            workers_enrich=workers_enrich,
            include_terminated=include_terminated,
            json_logs=json_logs,
            log_level=log_level,
        )

    raise ValueError(f"Unsupported wizard mode: {mode}")
