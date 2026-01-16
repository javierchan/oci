from __future__ import annotations

import heapq
import json
import logging
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .auth.providers import AuthContext, AuthError, get_tenancy_ocid, resolve_auth
from .config import RunConfig, load_run_config
from .diff.diff import diff_files, write_diff
from .enrich import get_enricher_for, set_enrich_context
from .logging import LogConfig, get_logger, setup_logging
from .normalize.transform import canonicalize_record, normalize_relationships, sort_relationships, stable_json_dumps
from .oci.clients import (
    get_budget_client,
    get_home_region_name,
    get_osub_usage_client,
    get_usage_api_client,
    set_client_connection_pool_size,
)
from .oci.compartments import list_compartments as oci_list_compartments
from .oci.discovery import discover_in_region
from .oci.regions import get_subscribed_regions
from .util.concurrency import parallel_map_ordered_iter
from .util.errors import (
    AuthResolutionError,
    ConfigError,
    ExportError,
    as_exit_code,
)

LOG = get_logger(__name__)

OUT_SCHEMA_VERSION = "1"
STREAM_CHUNK_SIZE = 5000
ENRICH_BATCH_SIZE = 500

REQUIRED_INVENTORY_FIELDS = {
    "ocid",
    "resourceType",
    "region",
    "collectedAt",
    "enrichStatus",
    "details",
    "relationships",
}
REQUIRED_RELATIONSHIP_FIELDS = {"source_ocid", "relation_type", "target_ocid"}
REQUIRED_GRAPH_NODE_FIELDS = {
    "nodeId",
    "nodeType",
    "nodeCategory",
    "name",
    "region",
    "compartmentId",
    "metadata",
    "tags",
    "enrichStatus",
    "enrichError",
}
REQUIRED_GRAPH_EDGE_FIELDS = {
    "source_ocid",
    "target_ocid",
    "relation_type",
    "source_type",
    "target_type",
    "region",
}
REQUIRED_RUN_SUMMARY_FIELDS = {
    "schema_version",
    "total_discovered",
    "enriched_ok",
    "not_implemented",
    "errors",
    "counts_by_resource_type",
    "counts_by_enrich_status",
    "counts_by_resource_type_and_status",
}


@dataclass(frozen=True)
class SchemaValidation:
    errors: List[str]
    warnings: List[str]


def is_mmdc_available() -> bool:
    from .export.diagram_projections import is_mmdc_available as _is_mmdc_available

    return _is_mmdc_available()


def validate_mermaid_diagrams_with_mmdc(outdir: Path, *, glob_pattern: str = "diagram*.mmd") -> List[Path]:
    from .export.diagram_projections import (
        validate_mermaid_diagrams_with_mmdc as _validate_mermaid_diagrams_with_mmdc,
    )

    return _validate_mermaid_diagrams_with_mmdc(outdir, glob_pattern=glob_pattern)


def write_diagram_projections(
    outdir: Path,
    nodes: Sequence[Dict[str, Any]],
    edges: Sequence[Dict[str, Any]],
    *,
    diagram_depth: Optional[int] = None,
) -> List[Path]:
    from .export.diagram_projections import write_diagram_projections as _write_diagram_projections

    return _write_diagram_projections(
        outdir,
        nodes,
        edges,
        diagram_depth=diagram_depth,
    )


class _StepTimers:
    def __init__(self) -> None:
        self._starts: Dict[str, float] = {}

    def start(self, key: str) -> None:
        self._starts[key] = perf_counter()

    def finish(self, key: str) -> Optional[int]:
        started = self._starts.pop(key, None)
        if started is None:
            return None
        return int((perf_counter() - started) * 1000)


def _log_event(
    logger: Any,
    level: int,
    message: str,
    *,
    step: str,
    phase: str,
    timers: Optional[_StepTimers] = None,
    timer_key: Optional[str] = None,
    **extra: Any,
) -> None:
    key = timer_key or step
    duration_ms = None
    if timers is not None:
        if phase == "start":
            timers.start(key)
        elif phase in {"complete", "error", "warning", "validated", "skipped"}:
            duration_ms = timers.finish(key)
    payload: Dict[str, Any] = {"step": step, "phase": phase, "event": f"{step}.{phase}"}
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    payload.update(extra)
    logger.log(level, message, extra=payload)


def cmd_enrich_coverage(cfg: RunConfig) -> int:
    from .enrich.coverage import compute_enrichment_coverage, top_missing_types

    inv = getattr(cfg, "inventory", None)
    top_n = int(getattr(cfg, "top", 20) or 20)
    if inv is None:
        raise ConfigError("enrich-coverage requires --inventory")
    coverage = compute_enrichment_coverage(inv)

    print(f"Total records: {coverage.total_records}")
    print(f"Total resource types: {coverage.total_resource_types}")
    print(f"Resource types with enrichers: {coverage.registered_resource_types}")
    print(f"Resource types missing enrichers: {coverage.missing_resource_types}")

    if coverage.missing_resource_types:
        print("")
        print(f"Top missing resource types (max {top_n}):")
        for rtype, count in top_missing_types(coverage, limit=top_n):
            print(f"- {rtype}: {count}")
    return 0



def _resolve_auth(cfg: RunConfig) -> AuthContext:
    try:
        return resolve_auth(cfg.auth, cfg.profile, cfg.tenancy_ocid)
    except AuthError as e:
        raise AuthResolutionError(str(e)) from e


def _resolve_auth_no_config(cfg: RunConfig) -> Optional[AuthContext]:
    try:
        return resolve_auth("resource", cfg.profile, cfg.tenancy_ocid)
    except AuthError:
        pass
    try:
        return resolve_auth("instance", cfg.profile, cfg.tenancy_ocid)
    except AuthError:
        return None


def _parse_iso_utc(value: str) -> datetime:
    raw = (value or "").strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _align_utc_day(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _default_cost_range(now_utc: datetime) -> Tuple[datetime, datetime]:
    start = datetime(now_utc.year, now_utc.month, 1, tzinfo=timezone.utc)
    return start, now_utc


def _usage_item_to_dict(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        return item
    to_dict = getattr(item, "to_dict", None)
    if callable(to_dict):
        return to_dict()  # type: ignore[no-any-return]
    attr_map = getattr(item, "attribute_map", None)
    if isinstance(attr_map, dict) and attr_map:
        out: Dict[str, Any] = {}
        for key in attr_map.keys():
            try:
                out[key] = getattr(item, key)
            except Exception:
                continue
        return out
    return {}


def _extract_usage_amount(data: Dict[str, Any]) -> float:
    for key in ("computed_amount", "computedAmount", "computed-amount", "cost", "amount"):
        val = data.get(key)
        if val is not None:
            try:
                return float(val)
            except Exception:
                return 0.0
    return 0.0


def _extract_usage_currency(data: Dict[str, Any]) -> Optional[str]:
    for key in ("currency", "currency_code", "currencyCode", "currency-code"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _extract_group_value(data: Dict[str, Any], group_by: Optional[str]) -> str:
    if not group_by:
        return ""
    keys_by_group = {
        "service": ("service", "service_name", "serviceName", "service-name"),
        "compartmentId": ("compartment_id", "compartmentId", "compartment-id"),
        "compartmentName": ("compartment_name", "compartmentName", "compartment-name"),
        "compartmentPath": ("compartment_path", "compartmentPath", "compartment-path"),
        "region": ("region", "region_name", "regionName", "region-name"),
        "sku": ("sku", "sku_name", "skuName", "sku-name"),
    }
    for key in keys_by_group.get(group_by, (group_by,)):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _request_summarized_usages(
    client: Any,
    tenancy_id: str,
    start: datetime,
    end: datetime,
    *,
    group_by: Optional[Union[str, Sequence[str]]],
    items_out: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    try:
        import oci  # type: ignore
    except Exception as e:  # pragma: no cover - import error surfaced in CLI validate
        return [], None, str(e)

    details_cls = getattr(getattr(oci, "usage_api", None), "models", None)
    if details_cls is None or not hasattr(details_cls, "RequestSummarizedUsagesDetails"):
        return [], None, "OCI Usage API models are unavailable"

    # Explicitly set query_type for cost reporting; do not rely on defaults.
    group_by_list: List[str] = []
    if group_by:
        if isinstance(group_by, str):
            group_by_list = [group_by]
        else:
            group_by_list = [str(value).strip() for value in group_by if str(value).strip()]
    group_by_label = ",".join(group_by_list) if group_by_list else "total"
    multi_group = len(group_by_list) > 1

    details_kwargs: Dict[str, Any] = {
        "tenant_id": tenancy_id,
        "time_usage_started": start,
        "time_usage_ended": end,
        "granularity": "DAILY",
        "query_type": "COST",
    }
    if group_by_list:
        details_kwargs["group_by"] = list(group_by_list)
        if any(value in {"compartmentId", "compartmentName", "compartmentPath"} for value in group_by_list):
            details_kwargs["compartment_depth"] = 6
    details = details_cls.RequestSummarizedUsagesDetails(**details_kwargs)

    totals_by_name: Dict[str, float] = {}
    meta_by_name: Dict[str, Dict[str, str]] = {}
    currency: Optional[str] = None
    page: Optional[str] = None
    while True:
        try:
            if page:
                resp = client.request_summarized_usages(details, page=page)  # type: ignore[attr-defined]
            else:
                resp = client.request_summarized_usages(details)  # type: ignore[attr-defined]
        except TypeError as e:
            if "page" in str(e):
                resp = client.request_summarized_usages(details)  # type: ignore[attr-defined]
                page = None
            else:
                return [], currency, str(e)
        except Exception as e:
            return [], currency, str(e)

        data = getattr(resp, "data", None)
        items: List[Any] = []
        data_currency = None
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("items", []) or []
            data_currency = data.get("currency")
        elif data is not None:
            items = getattr(data, "items", []) or []
            data_currency = getattr(data, "currency", None)
        if isinstance(data_currency, str) and data_currency.strip():
            currency = data_currency.strip()
        for item in items or []:
            item_dict = _usage_item_to_dict(item)
            amount = _extract_usage_amount(item_dict)
            name = ""
            if group_by_list and not multi_group:
                name = _extract_group_value(item_dict, group_by_list[0])
                if not name:
                    continue
                totals_by_name[name] = totals_by_name.get(name, 0.0) + amount
            elif multi_group:
                parts: List[str] = []
                for value in group_by_list:
                    part_val = _extract_group_value(item_dict, value)
                    if part_val:
                        parts.append(f"{value}={part_val}")
                name = "|".join(parts)
            item_currency = _extract_usage_currency(item_dict)
            if item_currency and not currency:
                currency = item_currency
            if not multi_group and group_by_list and group_by_list[0] == "compartmentId":
                meta = meta_by_name.setdefault(name, {})
                if "compartment_name" not in meta:
                    comp_name = ""
                    for key in ("compartment_name", "compartmentName", "compartment-name"):
                        val = item_dict.get(key)
                        if isinstance(val, str) and val.strip():
                            comp_name = val.strip()
                            break
                    if comp_name:
                        meta["compartment_name"] = comp_name
                if "compartment_path" not in meta:
                    comp_path = ""
                    for key in ("compartment_path", "compartmentPath", "compartment-path"):
                        val = item_dict.get(key)
                        if isinstance(val, str) and val.strip():
                            comp_path = val.strip()
                            break
                    if comp_path:
                        meta["compartment_path"] = comp_path
            if items_out is not None:
                started = ""
                ended = ""
                for key in ("time_usage_started", "timeUsageStarted", "time-usage-started"):
                    val = item_dict.get(key)
                    if isinstance(val, str) and val.strip():
                        started = val.strip()
                        break
                for key in ("time_usage_ended", "timeUsageEnded", "time-usage-ended"):
                    val = item_dict.get(key)
                    if isinstance(val, str) and val.strip():
                        ended = val.strip()
                        break
                service_name = _extract_group_value(item_dict, "service")
                if not service_name:
                    for key in ("service", "serviceName", "service-name"):
                        val = item_dict.get(key)
                        if isinstance(val, str) and val.strip():
                            service_name = val.strip()
                            break
                record = dict(item_dict)
                record.setdefault("group_by", group_by_label)
                record.setdefault("group_value", name if group_by_list else "")
                if started and not record.get("time_usage_started"):
                    record["time_usage_started"] = started
                if ended and not record.get("time_usage_ended"):
                    record["time_usage_ended"] = ended
                if service_name and not record.get("service"):
                    record["service"] = service_name
                record["computed_amount"] = amount
                record["currency"] = item_currency or currency or ""
                items_out.append(record)

        page = getattr(resp, "headers", {}).get("opc-next-page")
        if not page:
            break

    rows: List[Dict[str, Any]] = []
    for name, total in sorted(totals_by_name.items()):
        row = {"name": name, "amount": total}
        meta = meta_by_name.get(name)
        if meta:
            row.update(meta)
        rows.append(row)
    return rows, currency, None


def _list_budgets(client: Any, tenancy_id: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    budgets: List[Dict[str, Any]] = []
    page: Optional[str] = None
    while True:
        try:
            if page:
                resp = client.list_budgets(tenancy_id, page=page)  # type: ignore[attr-defined]
            else:
                resp = client.list_budgets(tenancy_id)  # type: ignore[attr-defined]
        except TypeError as e:
            if "page" in str(e):
                resp = client.list_budgets(tenancy_id)  # type: ignore[attr-defined]
                page = None
            else:
                return budgets, str(e)
        except Exception as e:
            return budgets, str(e)

        data = getattr(resp, "data", []) or []
        for item in data:
            item_dict = _usage_item_to_dict(item)
            budgets.append(item_dict)
        page = getattr(resp, "headers", {}).get("opc-next-page")
        if not page:
            break
    return budgets, None


def _list_alert_rules(client: Any, budget_id: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    rules: List[Dict[str, Any]] = []
    page: Optional[str] = None
    while True:
        try:
            if page:
                resp = client.list_alert_rules(budget_id, page=page)  # type: ignore[attr-defined]
            else:
                resp = client.list_alert_rules(budget_id)  # type: ignore[attr-defined]
        except TypeError as e:
            if "page" in str(e):
                resp = client.list_alert_rules(budget_id)  # type: ignore[attr-defined]
                page = None
            else:
                return rules, str(e)
        except Exception as e:
            return rules, str(e)
        data = getattr(resp, "data", []) or []
        for item in data:
            item_dict = _usage_item_to_dict(item)
            rules.append(item_dict)
        page = getattr(resp, "headers", {}).get("opc-next-page")
        if not page:
            break
    return rules, None


def _money_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _money_fmt(value: Any) -> str:
    dec = _money_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{dec:.2f}"


def _pct_fmt(value: Decimal, total: Decimal) -> str:
    if total <= 0:
        return "0.0%"
    pct = (value / total * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{pct:.1f}%"


def _truncate_text(text: str, max_len: int = 200) -> str:
    val = str(text or "").strip()
    if len(val) <= max_len:
        return val
    return val[: max_len - 3] + "..."


def _normalize_cost_rows(rows: Sequence[Dict[str, Any]], name_key: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        name = str(row.get(name_key) or row.get("name") or "").strip()
        if not name:
            continue
        amount = _money_decimal(row.get("amount", 0))
        out.append({"name": name, "amount": amount})
    out.sort(key=lambda r: (-r["amount"], r["name"].lower()))
    return out


def _compartment_alias_map(compartment_ids: Sequence[str]) -> Dict[str, str]:
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


def _compartment_row_label(
    row: Dict[str, Any],
    *,
    group_by: str,
    alias_by_id: Dict[str, str],
    name_by_id: Dict[str, str],
) -> str:
    if group_by == "compartmentName":
        return str(row.get("compartment_name") or row.get("compartment_id") or "").strip()
    if group_by == "compartmentPath":
        return str(row.get("compartment_path") or row.get("compartment_id") or "").strip()
    if group_by == "compartmentId":
        return _compartment_label(str(row.get("compartment_id") or ""), alias_by_id=alias_by_id, name_by_id=name_by_id)
    return str(row.get("compartment_id") or row.get("name") or "").strip()


def _rows_with_pct(rows: List[Dict[str, Any]], total: Decimal, limit: int) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for row in rows[:limit]:
        amount = _money_decimal(row.get("amount"))
        out.append(
            {
                "name": str(row.get("name") or ""),
                "cost": _money_fmt(amount),
                "share_pct": _pct_fmt(amount, total),
            }
        )
    return out


def _generate_cost_report_narratives(
    *,
    cost_context: Dict[str, Any],
    cfg: RunConfig,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    from .genai.config import try_load_genai_config
    from .genai.executive_summary import run_genai_best_effort_prompt

    keys = [
        "intro",
        "executive_summary",
        "data_sources",
        "consumption_insights",
        "coverage_gaps",
        "audience",
        "next_steps",
    ]
    genai_cfg = try_load_genai_config()
    if genai_cfg is None:
        err = "GenAI config not found or invalid; narrative generation skipped."
        return {}, {key: err for key in keys}

    time_start = str(cost_context.get("time_start") or "")
    time_end = str(cost_context.get("time_end") or "")
    currency = str(cost_context.get("currency") or "UNKNOWN")

    services = _normalize_cost_rows(cost_context.get("services", []), "name")
    regions = _normalize_cost_rows(cost_context.get("regions", []), "name")
    raw_compartments = cost_context.get("compartments", [])
    compartment_group_by = str(cost_context.get("compartment_group_by") or "compartmentId")
    alias_by_comp: Dict[str, str] = {}
    name_by_comp: Dict[str, str] = {}
    if compartment_group_by == "compartmentId":
        comp_ids = [str(r.get("compartment_id") or "") for r in raw_compartments if str(r.get("compartment_id") or "")]
        alias_by_comp = _compartment_alias_map(comp_ids)
        name_by_comp = cost_context.get("compartment_names") or {}

    compartment_rows: List[Dict[str, Any]] = []
    for row in raw_compartments:
        label = _compartment_row_label(
            row,
            group_by=compartment_group_by,
            alias_by_id=alias_by_comp,
            name_by_id=name_by_comp,
        )
        if not label:
            continue
        compartment_rows.append({"name": label, "amount": _money_decimal(row.get("amount", 0))})
    compartment_rows.sort(key=lambda r: (-r["amount"], r["name"].lower()))

    total_cost = _money_decimal(cost_context.get("total_cost") or 0)
    if total_cost == Decimal("0") and services:
        total_cost = sum((r["amount"] for r in services), Decimal("0"))

    service_count = len({r["name"] for r in services})
    region_count = len({r["name"] for r in regions})
    compartment_count = len({r["name"] for r in compartment_rows})

    top_services = _rows_with_pct(services, total_cost, 5)
    top_regions = _rows_with_pct(regions, total_cost, 5)
    top_compartments = _rows_with_pct(compartment_rows, total_cost, 5)

    query_inputs = cost_context.get("query_inputs") or {}
    base_ctx: Dict[str, Any] = {
        "time_range_utc": {"start": time_start, "end": time_end},
        "currency": currency,
        "total_cost": _money_fmt(total_cost),
        "services_covered": service_count,
        "compartments_covered": compartment_count,
        "regions_covered": region_count,
        "granularity": query_inputs.get("granularity"),
        "group_by": query_inputs.get("group_by"),
        "compartment_depth": query_inputs.get("compartment_depth"),
        "top_services": top_services,
        "top_regions": top_regions,
        "top_compartments": top_compartments,
    }

    steps = cost_context.get("steps") or []
    step_status: Dict[str, str] = {}
    for step in steps:
        name = str(step.get("name") or "").strip()
        status = str(step.get("status") or "").strip()
        if not name:
            continue
        step_status[name] = status.split()[0] if status else ""

    core_steps = ["usage_api_total", "usage_api_service", "usage_api_compartment", "usage_api_region"]
    optional_steps = sorted({name for name in step_status.keys() if name not in core_steps})
    coverage_ctx = {
        "core_steps": {name: step_status.get(name, "missing") for name in core_steps},
        "optional_steps": {name: step_status.get(name, "missing") for name in optional_steps},
        "errors": [_truncate_text(e) for e in cost_context.get("errors") or []],
        "warnings": [_truncate_text(w) for w in cost_context.get("warnings") or []],
        "budgets_count": len(cost_context.get("budgets") or []),
        "osub_usage_present": bool(cost_context.get("osub_usage")),
    }

    data_sources = []
    if any(name.startswith("usage_api") for name in step_status.keys()):
        data_sources.append(
            {
                "source": "Usage API request_summarized_usages",
                "role": "Cost totals and grouped costs by service, compartment, and region",
            }
        )
    if "budget_list" in step_status:
        data_sources.append(
            {
                "source": "Budget API list_budgets/list_alert_rules",
                "role": "Budget and alert rule metadata (read-only)",
            }
        )
    if "osub_usage" in step_status:
        data_sources.append(
            {
                "source": "OneSubscription computed usage (list_computed_usage_aggregateds)",
                "role": "Subscription usage aggregates when enabled",
            }
        )

    data_ctx = dict(base_ctx)
    data_ctx.update(
        {
            "data_sources": data_sources,
            "aggregation_dimensions": query_inputs.get("group_by"),
            "rounding": "ROUND_HALF_UP to 2 decimals",
        }
    )

    exec_ctx = dict(base_ctx)
    insights_ctx = dict(base_ctx)
    coverage_ctx_full = dict(base_ctx)
    coverage_ctx_full.update(coverage_ctx)
    audience_ctx = dict(base_ctx)
    next_steps_ctx = dict(base_ctx)
    next_steps_ctx.update(
        {
            "coverage_gaps": coverage_ctx.get("optional_steps"),
            "warnings": coverage_ctx.get("warnings"),
        }
    )

    def _build_prompt(section: str, ctx: Dict[str, Any], extras: List[str]) -> str:
        payload = json.dumps(ctx, sort_keys=True, ensure_ascii=True)
        lines = [
            f"Task: Write the {section} section for an OCI cost snapshot report.",
            "Constraints:",
            "- Use FinOps-compatible language.",
            "- Descriptive only; no optimization, forecasting, anomaly detection, or budget vs actuals.",
            "- Treat this as a point-in-time visibility and allocation snapshot, not a FinOps platform replacement.",
            "- Do not invent or infer business context (no owners, cost centers, or environments).",
            "- Do not fabricate numbers; only reference values from the context.",
            "- Output Markdown text only, no headings.",
        ]
        lines.extend(extras)
        lines.append("Context (JSON):")
        lines.append("```")
        lines.append(payload)
        lines.append("```")
        lines.append("Write the section now.")
        return "\n".join(lines)

    api_format = "AUTO"
    max_tokens = 300
    temperature = 0.2

    narratives: Dict[str, str] = {}
    errors: Dict[str, str] = {}

    prompts = {
        "intro": _build_prompt(
            "introduction",
            exec_ctx,
            ["- 1 short paragraph that states snapshot purpose and limitations."],
        ),
        "executive_summary": _build_prompt(
            "Executive Summary",
            exec_ctx,
            [
                "- 2-4 short paragraphs.",
                "- Summarize total cost and time range; mention top services and regions.",
                "- Explicitly note this is visibility-only and does not include optimization, budgets, or forecasts.",
            ],
        ),
        "data_sources": _build_prompt(
            "Data Sources & Methodology",
            data_ctx,
            [
                "- Explain data sources, time range, granularity, and grouping dimensions.",
                "- Note currency comes from Usage API and amounts are aggregated over the range.",
            ],
        ),
        "consumption_insights": _build_prompt(
            "Consumption Insights (Descriptive Only)",
            insights_ctx,
            [
                "- Describe dominant services, regions, and compartment concentration.",
                "- Use the provided percentages when referencing concentration.",
            ],
        ),
        "coverage_gaps": _build_prompt(
            "Coverage & Data Gaps",
            coverage_ctx_full,
            [
                "- Clearly list what data is included and what is missing or unavailable.",
                "- Do not speculate about missing data.",
            ],
        ),
        "audience": _build_prompt(
            "Intended Audience & Usage Guidelines",
            audience_ctx,
            [
                "- Identify typical readers and appropriate uses (visibility, allocation awareness).",
                "- State what this report should not be used for (budgeting, forecasting, rightsizing).",
            ],
        ),
        "next_steps": _build_prompt(
            "Suggested Next Steps (Optional)",
            next_steps_ctx,
            [
                "- Provide high-level, non-binding suggestions (e.g., integrate with FinOps tools, enrich tags).",
                "- No resource-level actions or optimization guidance.",
            ],
        ),
    }

    for key in keys:
        prompt = prompts.get(key, "")
        if not prompt:
            errors[key] = "Prompt missing for GenAI narrative section."
            continue
        try:
            out, _ = run_genai_best_effort_prompt(
                prompt=prompt,
                genai_cfg=genai_cfg,
                prefer_chat=False,
                api_format=api_format,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            out = (out or "").strip()
            if out:
                narratives[key] = out
            else:
                errors[key] = "GenAI returned empty response."
        except Exception as e:
            errors[key] = str(e)

    return narratives, errors


def _record_sort_key(record: Dict[str, Any]) -> Tuple[str, str]:
    return (str(record.get("ocid") or ""), str(record.get("resourceType") or ""))


def _iter_jsonl_records(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _merge_sorted_inventory_chunks(paths: Sequence[Path]) -> Iterable[Dict[str, Any]]:
    files: List[Any] = []
    heap: List[Tuple[Tuple[str, str], int, Dict[str, Any]]] = []

    def _read_next(fh: Any) -> Optional[Dict[str, Any]]:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            return json.loads(line)
        return None

    try:
        for idx, path in enumerate(paths):
            fh = path.open("r", encoding="utf-8")
            files.append(fh)
            rec = _read_next(fh)
            if rec is not None:
                heapq.heappush(heap, (_record_sort_key(rec), idx, rec))

        while heap:
            _key, idx, rec = heapq.heappop(heap)
            yield rec
            next_rec = _read_next(files[idx])
            if next_rec is not None:
                heapq.heappush(heap, (_record_sort_key(next_rec), idx, next_rec))
    finally:
        for fh in files:
            try:
                fh.close()
            except Exception:
                pass


def _relationships_by_source(relationships: Sequence[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    by_source: Dict[str, List[Dict[str, str]]] = {}
    for rel in relationships:
        src = str(rel.get("source_ocid") or "")
        if not src:
            continue
        by_source.setdefault(src, []).append(rel)
    return by_source


def _apply_derived_relationships(
    record: Dict[str, Any],
    derived_by_source: Dict[str, List[Dict[str, str]]],
) -> Dict[str, Any]:
    ocid = str(record.get("ocid") or "")
    extra = derived_by_source.get(ocid)
    if not extra:
        return record
    current = record.get("relationships")
    if isinstance(current, list):
        merged = list(current) + list(extra)
    else:
        merged = list(extra)
    updated = dict(record)
    updated["relationships"] = sort_relationships(merged)
    return updated


def _iter_export_records(
    chunk_paths: Sequence[Path],
    derived_by_source: Dict[str, List[Dict[str, str]]],
) -> Iterable[Dict[str, Any]]:
    for rec in _merge_sorted_inventory_chunks(chunk_paths):
        yield _apply_derived_relationships(rec, derived_by_source)


def _write_inventory_chunk(records: List[Dict[str, Any]], path: Path) -> int:
    records.sort(key=_record_sort_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            obj = canonicalize_record(normalize_relationships(dict(rec)))
            f.write(stable_json_dumps(obj))
            f.write("\n")
    return len(records)


def _load_inventory_chunks(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
    return records


def _cleanup_chunk_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _collect_cost_report_data(
    *,
    ctx: Optional[AuthContext],
    cfg: RunConfig,
    subscribed_regions: List[str],
    requested_regions: Optional[List[str]],
    finished_at: str,
) -> Dict[str, Any]:
    from .genai.redact import redact_text

    errors: List[str] = []
    steps: List[Dict[str, str]] = []
    warnings: List[str] = []

    now = _parse_iso_utc(finished_at)
    if cfg.cost_start:
        try:
            start_dt = _parse_iso_utc(cfg.cost_start)
        except Exception as e:
            errors.append(redact_text(f"Invalid --cost-start: {e}"))
            start_dt, _ = _default_cost_range(now)
    else:
        start_dt, _ = _default_cost_range(now)

    if cfg.cost_end:
        try:
            end_dt = _parse_iso_utc(cfg.cost_end)
        except Exception as e:
            errors.append(redact_text(f"Invalid --cost-end: {e}"))
            _, end_dt = _default_cost_range(now)
    else:
        _, end_dt = _default_cost_range(now)

    start_raw = start_dt
    end_raw = end_dt
    start_dt = _align_utc_day(start_dt)
    end_dt = _align_utc_day(end_dt)
    if start_dt != start_raw or end_dt != end_raw:
        warnings.append("Cost time range normalized to 00:00:00 UTC for Usage API DAILY granularity.")
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(days=1)
        warnings.append("Cost end time adjusted to ensure end > start.")

    if start_dt >= end_dt:
        errors.append("Cost time range is invalid (start >= end).")

    tenancy_id = get_tenancy_ocid(ctx) if ctx else None
    if not tenancy_id:
        errors.append("Tenancy OCID is required for cost reporting.")

    home_region = None
    if tenancy_id and ctx:
        try:
            home_region = get_home_region_name(ctx)
        except Exception as e:
            errors.append(redact_text(f"Home region lookup failed: {e}"))
    if tenancy_id and ctx and not home_region:
        errors.append("Unable to resolve tenancy home region; Usage API calls skipped.")

    compartment_group_by = cfg.cost_compartment_group_by or "compartmentId"
    cost_group_by = cfg.cost_group_by or []
    cost_group_by_label = ",".join(cost_group_by) if cost_group_by else ""
    services: List[Dict[str, Any]] = []
    compartments: List[Dict[str, Any]] = []
    regions: List[Dict[str, Any]] = []
    total_cost = 0.0
    currency: Optional[str] = None
    usage_items: List[Dict[str, Any]] = []

    workers_cost = int(getattr(cfg, "workers_cost", 1) or 1)
    if workers_cost < 1:
        workers_cost = 1

    query_inputs: Dict[str, Any] = {
        "tenant_id": tenancy_id,
        "time_usage_started": start_dt.isoformat(timespec="seconds"),
        "time_usage_ended": end_dt.isoformat(timespec="seconds"),
        "granularity": "DAILY",
        "query_type": "COST",
        "group_by": ["service", compartment_group_by, "region"],
        "compartment_depth": 6,
        "compartment_group_by": compartment_group_by,
        "cost_group_by": cost_group_by or None,
        "home_region": home_region or "(unresolved)",
    }
    if home_region:
        query_inputs["region"] = home_region
    if home_region and requested_regions and home_region not in requested_regions:
        warnings.append("Usage API forced to tenancy home region, overriding requested region.")
    if start_raw != start_dt:
        query_inputs["time_usage_started_raw"] = start_raw.isoformat(timespec="seconds")
    if end_raw != end_dt:
        query_inputs["time_usage_ended_raw"] = end_raw.isoformat(timespec="seconds")

    # Usage API must always target the tenancy home region (no fallback).
    if tenancy_id and start_dt < end_dt and ctx and home_region:
        try:
            usage_client = get_usage_api_client(ctx, region=home_region)
        except Exception as e:
            errors.append(redact_text(f"Usage API client failed: {e}"))
            steps.append({"name": "usage_api_total", "status": "ERROR"})
            steps.append({"name": "usage_api_service", "status": "ERROR"})
            steps.append({"name": "usage_api_compartment", "status": "ERROR"})
            steps.append({"name": "usage_api_region", "status": "ERROR"})
        else:
            usage_queries: List[Tuple[str, Optional[Union[str, Sequence[str]]]]] = [
                ("usage_api_total", None),
                ("usage_api_service", "service"),
                ("usage_api_compartment", compartment_group_by),
                ("usage_api_region", "region"),
            ]
            if cost_group_by:
                usage_queries.append(("usage_api_grouped", list(cost_group_by)))

            def _run_usage_query(
                group_by: Optional[str],
            ) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str], List[Dict[str, Any]]]:
                local_items: List[Dict[str, Any]] = []
                client = usage_client
                if workers_cost > 1:
                    try:
                        client = get_usage_api_client(ctx, region=home_region)
                    except Exception as e:
                        return [], None, f"Usage API client failed: {e}", []
                rows, cur, err = _request_summarized_usages(
                    client,
                    tenancy_id,
                    start_dt,
                    end_dt,
                    group_by=group_by,
                    items_out=local_items,
                )
                return rows, cur, err, local_items

            results: Dict[str, Tuple[List[Dict[str, Any]], Optional[str], Optional[str], List[Dict[str, Any]]]] = {}
            if workers_cost > 1:
                with ThreadPoolExecutor(max_workers=workers_cost) as executor:
                    futures = {executor.submit(_run_usage_query, group_by): name for name, group_by in usage_queries}
                    for future, name in futures.items():
                        try:
                            rows, cur, err, items = future.result()
                        except Exception as e:
                            rows, cur, err, items = [], None, str(e), []
                        results[name] = (rows, cur, err, items)
            else:
                for name, group_by in usage_queries:
                    rows, cur, err, items = _run_usage_query(group_by)
                    results[name] = (rows, cur, err, items)

            error_labels = {
                "usage_api_total": "Usage API total failed",
                "usage_api_service": "Usage API service failed",
                "usage_api_compartment": "Usage API compartment failed",
                "usage_api_region": "Usage API region failed",
                "usage_api_grouped": "Usage API grouped usage failed",
            }
            for name, _group_by in usage_queries:
                rows, cur, err, items = results.get(name, ([], None, "Usage API result missing", []))
                steps.append({"name": name, "status": "OK" if not err else "ERROR"})
                if err:
                    errors.append(redact_text(f"{error_labels.get(name, name)}: {err}"))
                else:
                    if name == "usage_api_total":
                        total_cost = sum(float(r.get("amount") or 0.0) for r in rows)
                    elif name == "usage_api_service":
                        services = rows
                    elif name == "usage_api_compartment":
                        for r in rows:
                            compartments.append(
                                {
                                    "compartment_id": r.get("name", ""),
                                    "amount": r.get("amount", 0.0),
                                    "compartment_name": r.get("compartment_name", ""),
                                    "compartment_path": r.get("compartment_path", ""),
                                }
                            )
                    elif name == "usage_api_region":
                        regions = rows
                    if cur:
                        currency = cur or currency
                if items:
                    usage_items.extend(items)
    else:
        steps.append({"name": "usage_api_total", "status": "SKIPPED"})
        steps.append({"name": "usage_api_service", "status": "SKIPPED"})
        steps.append({"name": "usage_api_compartment", "status": "SKIPPED"})
        steps.append({"name": "usage_api_region", "status": "SKIPPED"})
        if cost_group_by:
            steps.append({"name": "usage_api_grouped", "status": "SKIPPED"})

    # Usage API currency is authoritative; conversion is out of scope.
    if cfg.cost_currency:
        if currency and currency != cfg.cost_currency:
            warnings.append(
                "Requested currency "
                f"{cfg.cost_currency} but Usage API returned {currency}. "
                "No conversion performed; amounts remain in API currency."
            )
        elif not currency:
            warnings.append(
                "Requested currency "
                f"{cfg.cost_currency} but Usage API did not return currency. "
                "No conversion performed; currency is unknown."
            )

    budgets: List[Dict[str, Any]] = []
    alert_rule_counts: Dict[str, int] = {}
    if tenancy_id and ctx:
        try:
            budget_client = get_budget_client(ctx, region=home_region)
        except Exception as e:
            steps.append({"name": "budget_list", "status": "ERROR"})
            errors.append(redact_text(f"Budget client failed: {e}"))
        else:
            budget_rows, err = _list_budgets(budget_client, tenancy_id)
            steps.append({"name": "budget_list", "status": "OK" if not err else "ERROR"})
            if err:
                errors.append(redact_text(f"Budget list failed: {err}"))
            else:
                budgets = budget_rows
                for budget in budgets:
                    budget_id = str(budget.get("id") or "")
                    if not budget_id:
                        continue
                    rules, err = _list_alert_rules(budget_client, budget_id)
                    status = "OK" if not err else "ERROR"
                    steps.append({"name": "budget_alert_rules", "status": status})
                    if err:
                        errors.append(redact_text(f"Alert rules failed for budget: {err}"))
                    else:
                        alert_rule_counts[budget_id] = len(rules)
    else:
        steps.append({"name": "budget_list", "status": "SKIPPED"})

    osub_usage: Optional[Dict[str, Any]] = None
    if tenancy_id and ctx:
        subscription_id = cfg.osub_subscription_id
        if not subscription_id:
            steps.append({"name": "osub_usage", "status": "SKIPPED"})
            warnings.append("OneSubscription subscription ID not provided; skipping usage lookup.")
        else:
            try:
                osub_client = get_osub_usage_client(ctx, region=home_region)
            except Exception as e:
                steps.append({"name": "osub_usage", "status": "ERROR"})
                errors.append(redact_text(f"OneSubscription client failed: {e}"))
            else:
                try:
                    import oci  # type: ignore
                except Exception as e:  # pragma: no cover
                    steps.append({"name": "osub_usage", "status": "ERROR"})
                    errors.append(redact_text(f"OneSubscription client unavailable: {e}"))
                else:
                    if hasattr(osub_client, "list_computed_usage_aggregateds"):
                        # Use list_computed_usage_aggregateds; request_computed_usage is not supported in SDK 2.164.2.
                        try:
                            kwargs: Dict[str, Any] = {"grouping": "MONTHLY"}
                            if home_region:
                                kwargs["x_one_origin_region"] = home_region
                            resp = osub_client.list_computed_usage_aggregateds(
                                compartment_id=tenancy_id,
                                subscription_id=subscription_id,
                                time_from=start_dt,
                                time_to=end_dt,
                                **kwargs,
                            )
                            data = getattr(resp, "data", None)
                            rows = list(data) if isinstance(data, list) else []
                            total = 0.0
                            currency_code: Optional[str] = None
                            agg_rows = 0
                            for row in rows:
                                row_dict = _usage_item_to_dict(row)
                                currency_code = currency_code or _extract_usage_currency(row_dict)
                                aggregates = row_dict.get("aggregated_computed_usages") or row_dict.get(
                                    "aggregatedComputedUsages"
                                )
                                if not isinstance(aggregates, list):
                                    continue
                                for agg in aggregates:
                                    agg_dict = _usage_item_to_dict(agg)
                                    total += _extract_usage_amount(agg_dict)
                                    agg_rows += 1
                            if rows:
                                osub_usage = {
                                    "computed_amount": total,
                                    "currency_code": currency_code,
                                    "subscription_id": subscription_id,
                                    "aggregation_rows": agg_rows,
                                }
                            else:
                                warnings.append("OneSubscription returned no usage rows.")
                            steps.append({"name": "osub_usage", "status": "OK"})
                        except Exception as e:
                            msg = redact_text(f"OneSubscription usage failed: {e}")
                            if isinstance(e, oci.exceptions.ServiceError):
                                if e.status in (401, 403):
                                    msg = "OneSubscription access denied or not enabled for this tenancy."
                                elif e.status == 404:
                                    msg = "OneSubscription is not enabled for this tenancy."
                            steps.append({"name": "osub_usage", "status": "ERROR"})
                            errors.append(redact_text(msg))
                    else:
                        steps.append({"name": "osub_usage", "status": "ERROR"})
                        errors.append("OneSubscription client does not support required list APIs.")
    else:
        steps.append({"name": "osub_usage", "status": "SKIPPED"})

    compartment_names: Dict[str, str] = {}
    comp_ids = set()
    if compartment_group_by == "compartmentId":
        comp_ids = {
            str(r.get("compartment_id") or "") for r in compartments if str(r.get("compartment_id") or "")
        }
        for row in compartments:
            cid = str(row.get("compartment_id") or "")
            if not cid:
                continue
            name = str(row.get("compartment_name") or "").strip()
            path = str(row.get("compartment_path") or "").strip()
            label = path or name
            if label and cid not in compartment_names:
                compartment_names[cid] = label
    if comp_ids and ctx:
        missing = comp_ids - set(compartment_names)
        if missing:
            try:
                comp_rows = oci_list_compartments(ctx, tenancy_ocid=tenancy_id)
                for row in comp_rows:
                    ocid = row.get("ocid")
                    name = row.get("name")
                    if ocid and name and ocid not in compartment_names:
                        compartment_names[str(ocid)] = str(name)
                steps.append({"name": "compartment_names", "status": "OK"})
            except Exception as e:
                steps.append({"name": "compartment_names", "status": "ERROR"})
                errors.append(redact_text(f"Compartment name lookup failed: {e}"))
        else:
            steps.append({"name": "compartment_names", "status": "OK"})
    elif comp_ids:
        steps.append({"name": "compartment_names", "status": "ERROR"})
        errors.append("Compartment name lookup skipped: no auth context.")

    return {
        "time_start": start_dt.isoformat(timespec="seconds"),
        "time_end": end_dt.isoformat(timespec="seconds"),
        "currency": currency or "UNKNOWN",
        "currency_source": "usage_api" if currency else "unknown",
        "total_cost": total_cost,
        "services": services,
        "compartments": compartments,
        "compartment_group_by": compartment_group_by,
        "cost_group_by": cost_group_by or None,
        "cost_group_by_label": cost_group_by_label,
        "regions": regions,
        "budgets": budgets,
        "budget_alert_rule_counts": alert_rule_counts,
        "osub_usage": osub_usage,
        "usage_items": usage_items,
        "errors": errors,
        "warnings": warnings,
        "steps": steps,
        "query_inputs": query_inputs,
        "compartment_names": compartment_names,
    }


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
    counts_by_resource_type_and_status: Dict[str, Dict[str, int]] = {}
    for r in records:
        rt = str(r.get("resourceType") or "")
        counts_by_resource_type[rt] = counts_by_resource_type.get(rt, 0) + 1
        st = str(r.get("enrichStatus") or "")
        counts_by_enrich_status[st] = counts_by_enrich_status.get(st, 0) + 1
        per_type = counts_by_resource_type_and_status.setdefault(rt, {})
        per_type[st] = per_type.get(st, 0) + 1

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
        "counts_by_resource_type_and_status": {
            k: dict(sorted(v.items())) for k, v in sorted(counts_by_resource_type_and_status.items())
        },
    }


def _write_run_summary(outdir: Path, metrics: Dict[str, Any], cfg: RunConfig) -> Path:
    summary = dict(metrics)
    # Only include required metrics; users can inspect config via logs/CLI
    summary["schema_version"] = OUT_SCHEMA_VERSION
    path = outdir / "run_summary.json"
    path.write_text(stable_json_dumps(summary), encoding="utf-8")
    return path


def _relationships_path(outdir: Path) -> Path:
    return outdir / "relationships.jsonl"


def _write_relationships(outdir: Path, relationships: List[Dict[str, str]]) -> Path:
    p = _relationships_path(outdir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for rel in sort_relationships(relationships):
            f.write(stable_json_dumps(rel))
            f.write("\n")
    return p


def _merge_relationships_into_records(
    records: List[Dict[str, Any]],
    relationships: List[Dict[str, str]],
) -> None:
    if not relationships:
        return
    by_source: Dict[str, List[Dict[str, str]]] = {}
    for rel in relationships:
        src = str(rel.get("source_ocid") or "")
        if not src:
            continue
        by_source.setdefault(src, []).append(rel)
    if not by_source:
        return
    for rec in records:
        ocid = str(rec.get("ocid") or "")
        if not ocid:
            continue
        extra = by_source.get(ocid)
        if not extra:
            continue
        current = rec.get("relationships")
        if isinstance(current, list):
            merged = list(current) + list(extra)
        else:
            merged = list(extra)
        rec["relationships"] = sort_relationships(merged)


def _read_jsonl_dicts(
    path: Path,
    *,
    required_fields: set[str],
    errors: List[str],
    max_records: Optional[int] = None,
) -> List[Tuple[int, Dict[str, Any]]]:
    if not path.is_file():
        errors.append(f"{path.name}: file not found")
        return []
    records: List[Tuple[int, Dict[str, Any]]] = []
    parse_errors: List[int] = []
    non_object: List[int] = []
    missing: List[Tuple[int, List[str]]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            if max_records is not None and len(records) >= max_records:
                break
            try:
                obj = json.loads(line)
            except Exception:
                if len(parse_errors) < 5:
                    parse_errors.append(line_no)
                continue
            if not isinstance(obj, dict):
                if len(non_object) < 5:
                    non_object.append(line_no)
                continue
            missing_fields = [k for k in required_fields if k not in obj]
            if missing_fields:
                if len(missing) < 5:
                    missing.append((line_no, missing_fields))
            records.append((line_no, obj))
    if parse_errors:
        errors.append(f"{path.name}: invalid JSON lines (examples: {', '.join(str(n) for n in parse_errors)})")
    if non_object:
        errors.append(f"{path.name}: non-object JSON lines (examples: {', '.join(str(n) for n in non_object)})")
    if missing:
        details = "; ".join(f"line {ln} missing {', '.join(fields)}" for ln, fields in missing)
        errors.append(f"{path.name}: records missing required fields ({details})")
    return records


def _validate_outdir_schema(
    outdir: Path,
    *,
    expect_graph: bool = True,
    mode: str = "auto",
    sample_limit: int = 5000,
    auto_sample_bytes: int = 50 * 1024 * 1024,
) -> SchemaValidation:
    errors: List[str] = []
    warnings: List[str] = []

    inventory_path = outdir / "inventory.jsonl"
    mode = (mode or "auto").strip().lower()
    if sample_limit < 1:
        sample_limit = 1
    if mode == "off":
        warnings.append("Schema validation skipped (disabled).")
        return SchemaValidation(errors=errors, warnings=warnings)
    if mode == "auto":
        try:
            size = inventory_path.stat().st_size
        except Exception:
            size = 0
        mode = "sampled" if size >= auto_sample_bytes else "full"
    max_records = sample_limit if mode == "sampled" else None
    if mode == "sampled":
        warnings.append(f"Schema validation sampled first {sample_limit} records.")
    inventory_records = _read_jsonl_dicts(
        inventory_path,
        required_fields=REQUIRED_INVENTORY_FIELDS,
        errors=errors,
        max_records=max_records,
    )
    if inventory_records:
        collected_values = {str(obj.get("collectedAt") or "") for _, obj in inventory_records if obj.get("collectedAt")}
        if len(collected_values) > 1:
            warnings.append(
                f"{inventory_path.name}: multiple collectedAt values detected ({len(collected_values)} unique)"
            )
        bad_relationships: List[int] = []
        for line_no, obj in inventory_records:
            rels = obj.get("relationships")
            if not isinstance(rels, list):
                if len(bad_relationships) < 5:
                    bad_relationships.append(line_no)
                continue
            for rel in rels:
                if not isinstance(rel, dict):
                    if len(bad_relationships) < 5:
                        bad_relationships.append(line_no)
                    break
                if any(k not in rel for k in REQUIRED_RELATIONSHIP_FIELDS):
                    if len(bad_relationships) < 5:
                        bad_relationships.append(line_no)
                    break
        if bad_relationships:
            warnings.append(
                f"{inventory_path.name}: invalid relationships in records (examples: {', '.join(str(n) for n in bad_relationships)})"
            )

    relationships_path = outdir / "relationships.jsonl"
    _read_jsonl_dicts(
        relationships_path,
        required_fields=REQUIRED_RELATIONSHIP_FIELDS,
        errors=errors,
        max_records=max_records,
    )

    nodes_path = outdir / "graph_nodes.jsonl"
    edges_path = outdir / "graph_edges.jsonl"
    if expect_graph or nodes_path.is_file() or edges_path.is_file():
        node_records = _read_jsonl_dicts(
            nodes_path,
            required_fields=REQUIRED_GRAPH_NODE_FIELDS,
            errors=errors,
            max_records=max_records,
        )
        node_ids = {str(obj.get("nodeId") or "") for _, obj in node_records if obj.get("nodeId")}

        edge_records = _read_jsonl_dicts(
            edges_path,
            required_fields=REQUIRED_GRAPH_EDGE_FIELDS,
            errors=errors,
            max_records=max_records,
        )
        if node_ids and edge_records:
            missing_edges: List[int] = []
            for line_no, obj in edge_records:
                src = str(obj.get("source_ocid") or "")
                dst = str(obj.get("target_ocid") or "")
                if not src or not dst:
                    continue
                if src not in node_ids or dst not in node_ids:
                    if len(missing_edges) < 5:
                        missing_edges.append(line_no)
            if missing_edges:
                warnings.append(
                    f"{edges_path.name}: edges reference missing node IDs (examples: {', '.join(str(n) for n in missing_edges)})"
                )

    summary_path = outdir / "run_summary.json"
    if not summary_path.is_file():
        errors.append(f"{summary_path.name}: file not found")
    else:
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            errors.append(f"{summary_path.name}: invalid JSON")
        else:
            if not isinstance(summary, dict):
                errors.append(f"{summary_path.name}: expected JSON object")
            else:
                missing = [k for k in REQUIRED_RUN_SUMMARY_FIELDS if k not in summary]
                if missing:
                    errors.append(f"{summary_path.name}: missing required fields ({', '.join(missing)})")

    return SchemaValidation(errors=errors, warnings=warnings)


def cmd_run(cfg: RunConfig) -> int:
    from .export.csv import write_csv
    from .export.graph import build_graph, filter_edges_with_nodes, write_graph, write_mermaid
    from .export.jsonl import write_jsonl
    from .report import (
        write_cost_report_md,
        write_cost_usage_csv,
        write_cost_usage_grouped_csv,
        write_cost_usage_jsonl,
        write_cost_usage_views,
        write_run_report_md,
    )

    # Ensure the run directory exists early so we can always emit a report.
    cfg.outdir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_collected_at = started_at
    timers = _StepTimers()

    status = "OK"
    fatal_error: Optional[str] = None
    ctx: Optional[AuthContext] = None

    subscribed_regions: List[str] = []
    requested_regions: Optional[List[str]] = None
    excluded_regions: List[Dict[str, str]] = []
    discovered_count = 0
    inventory_records: List[Dict[str, Any]] = []
    metrics: Optional[Dict[str, Any]] = None
    diff_warning: Optional[str] = None

    executive_summary: Optional[str] = None
    executive_summary_error: Optional[str] = None

    _log_event(
        LOG,
        logging.INFO,
        "Starting inventory run",
        step="run",
        phase="start",
        timers=timers,
        outdir=str(cfg.outdir),
    )

    try:
        _log_event(
            LOG,
            logging.INFO,
            "Authentication resolution started",
            step="auth",
            phase="start",
            timers=timers,
            method=cfg.auth,
            profile=cfg.profile,
        )
        ctx = _resolve_auth(cfg)
        set_enrich_context(ctx)
        _log_event(
            LOG,
            logging.INFO,
            "Authentication resolved",
            step="auth",
            phase="complete",
            timers=timers,
            method=cfg.auth,
            profile=cfg.profile,
        )

        # Discover regions
        _log_event(
            LOG,
            logging.INFO,
            "Region discovery started",
            step="regions",
            phase="start",
            timers=timers,
        )
        regions = get_subscribed_regions(ctx)
        subscribed_regions = list(regions)
        if not regions:
            raise ConfigError("No subscribed regions found for the tenancy/profile provided")
        if cfg.regions:
            requested_regions = [r for r in cfg.regions if r]
            regions = requested_regions
        _log_event(
            LOG,
            logging.INFO,
            "Discovered subscribed regions",
            step="regions",
            phase="complete",
            timers=timers,
            regions=regions,
            count=len(regions),
        )

        # Per-region discovery in parallel (ordered by region for determinism)
        regions = sorted([r for r in regions if r])
        _log_event(
            LOG,
            logging.INFO,
            "Discovery started",
            step="discovery",
            phase="start",
            timers=timers,
            region_count=len(regions),
        )

        def _disc(r: str) -> List[Dict[str, Any]]:
            return discover_in_region(ctx, r, cfg.query, collected_at=run_collected_at)

        all_relationships: List[Dict[str, str]] = []
        chunk_dir = cfg.outdir / ".inventory_chunks"
        chunk_paths: List[Path] = []
        chunk_records: List[Dict[str, Any]] = []
        chunk_index = 0

        def _flush_chunk() -> None:
            nonlocal chunk_index
            if not chunk_records:
                return
            chunk_path = chunk_dir / f"inventory_chunk_{chunk_index:04d}.jsonl"
            _write_inventory_chunk(chunk_records, chunk_path)
            chunk_paths.append(chunk_path)
            chunk_records.clear()
            chunk_index += 1

        with ThreadPoolExecutor(max_workers=max(1, cfg.workers_region)) as pool:
            futures_by_region = {r: pool.submit(_disc, r) for r in regions}
            for r in regions:
                timers.start(f"discovery:{r}")

            for r in regions:
                try:
                    region_records = futures_by_region[r].result()
                except Exception as e:
                    excluded_regions.append({"region": r, "reason": str(e)})
                    _log_event(
                        LOG,
                        logging.WARNING,
                        f"Region discovery failed; skipping region {r}",
                        step="discovery",
                        phase="error",
                        timers=timers,
                        timer_key=f"discovery:{r}",
                        region=r,
                        error=str(e),
                    )
                    region_records = []

                discovered_count += len(region_records)
                _log_event(
                    LOG,
                    logging.INFO,
                    f"Region discovery complete {r}",
                    step="discovery",
                    phase="complete",
                    timers=timers,
                    timer_key=f"discovery:{r}",
                    region=r,
                    count=len(region_records),
                )
                if not region_records:
                    continue

                # Enrichment in parallel per region (streamed to disk).
                _log_event(
                    LOG,
                    logging.INFO,
                    f"Region enrichment started {r}",
                    step="enrich",
                    phase="start",
                    timers=timers,
                    timer_key=f"enrich:{r}",
                    region=r,
                    count=len(region_records),
                )
                def _enrich_and_collect(rec: Dict[str, Any]) -> Dict[str, Any]:
                    updated, rels = _enrich_record(rec)
                    return {"record": updated, "rels": rels}

                worker_results = parallel_map_ordered_iter(
                    _enrich_and_collect,
                    region_records,
                    max_workers=max(1, cfg.workers_enrich),
                    batch_size=ENRICH_BATCH_SIZE,
                )
                for item in worker_results:
                    record = item["record"]
                    all_relationships.extend(item["rels"] or [])
                    chunk_records.append(record)
                    if len(chunk_records) >= STREAM_CHUNK_SIZE:
                        _flush_chunk()
                _log_event(
                    LOG,
                    logging.INFO,
                    f"Region enrichment complete {r}",
                    step="enrich",
                    phase="complete",
                    timers=timers,
                    timer_key=f"enrich:{r}",
                    region=r,
                    count=len(region_records),
                )

        _flush_chunk()
        _log_event(
            LOG,
            logging.INFO,
            "Discovery complete",
            step="discovery",
            phase="complete",
            timers=timers,
            count=discovered_count,
            excluded_regions=len(excluded_regions),
        )

        inventory_records = _load_inventory_chunks(chunk_paths) if chunk_paths else []
        _log_event(
            LOG,
            logging.INFO,
            "Enrichment complete",
            step="enrich",
            phase="complete",
            timers=timers,
            count=len(inventory_records),
        )

        # Derive additional relationships from record metadata (offline; no new OCI calls)
        # to improve graph/report fidelity when enrichers did not emit relationships.
        from .export.graph import derive_relationships_from_metadata

        derived_relationships = derive_relationships_from_metadata(inventory_records)
        if derived_relationships:
            _merge_relationships_into_records(inventory_records, derived_relationships)
            all_relationships.extend(derived_relationships)
        derived_by_source = _relationships_by_source(derived_relationships)

        # Exports
        _log_event(
            LOG,
            logging.INFO,
            "Exporting inventory artifacts",
            step="export",
            phase="start",
            timers=timers,
        )
        inventory_jsonl = cfg.outdir / "inventory.jsonl"
        inventory_csv = cfg.outdir / "inventory.csv"
        if chunk_paths:
            def _export_iter() -> Iterable[Dict[str, Any]]:
                return _iter_export_records(chunk_paths, derived_by_source)

            write_jsonl(_export_iter(), inventory_jsonl, already_sorted=True)
            write_csv(_export_iter(), inventory_csv, already_sorted=True)
        else:
            write_jsonl(inventory_records, inventory_jsonl)
            write_csv(inventory_records, inventory_csv)

        _write_relationships(cfg.outdir, all_relationships)
        _log_event(
            LOG,
            logging.INFO,
            "Exported inventory artifacts",
            step="export",
            phase="complete",
            timers=timers,
            count=len(inventory_records),
        )

        # Coverage metrics and summary
        _log_event(
            LOG,
            logging.INFO,
            "Coverage metrics started",
            step="metrics",
            phase="start",
            timers=timers,
        )
        metrics = _coverage_metrics(inventory_records)
        _write_run_summary(cfg.outdir, metrics, cfg)
        _log_event(
            LOG,
            logging.INFO,
            "Coverage metrics complete",
            step="metrics",
            phase="complete",
            timers=timers,
        )

        # Graph artifacts (nodes/edges + Mermaid)
        if cfg.diagrams:
            _log_event(
                LOG,
                logging.INFO,
                "Graph build started",
                step="graph",
                phase="start",
                timers=timers,
            )
            nodes, edges = build_graph(inventory_records, all_relationships)
            total_edges = len(edges)
            edges, dropped_edges = filter_edges_with_nodes(nodes, edges)
            if dropped_edges:
                _log_event(
                    LOG,
                    logging.WARNING,
                    "Graph edges filtered to remove missing nodes",
                    step="graph",
                    phase="warning",
                    timers=timers,
                    dropped_edges=dropped_edges,
                    remaining_edges=len(edges),
                    total_edges=total_edges,
                )
            write_graph(cfg.outdir, nodes, edges)
            write_mermaid(cfg.outdir, nodes, edges)
            if cfg.diagram_depth < 3:
                _log_event(
                    LOG,
                    logging.INFO,
                    "Diagram depth limits consolidated diagram detail",
                    step="diagrams",
                    phase="info",
                    timers=timers,
                    diagram_depth=cfg.diagram_depth,
                )
            diagram_paths = write_diagram_projections(
                cfg.outdir,
                nodes,
                edges,
                diagram_depth=cfg.diagram_depth,
            )
            _log_event(
                LOG,
                logging.INFO,
                "Graph build complete",
                step="graph",
                phase="complete",
                timers=timers,
                nodes=len(nodes),
                edges=len(edges),
                diagrams=len(diagram_paths),
            )

        _cleanup_chunk_dir(chunk_dir)

        _log_event(
            LOG,
            logging.INFO,
            "Output schema validation started",
            step="schema",
            phase="start",
            timers=timers,
            expect_graph=cfg.diagrams,
            mode=cfg.schema_validation,
            sample_records=cfg.schema_sample_records,
        )
        validation = _validate_outdir_schema(
            cfg.outdir,
            expect_graph=cfg.diagrams,
            mode=cfg.schema_validation,
            sample_limit=cfg.schema_sample_records,
        )
        _log_event(
            LOG,
            logging.INFO,
            "Output schema validation complete",
            step="schema",
            phase="complete",
            timers=timers,
            warning_count=len(validation.warnings),
            error_count=len(validation.errors),
        )
        for warning in validation.warnings:
            _log_event(
                LOG,
                logging.WARNING,
                "Output schema validation warning",
                step="schema",
                phase="warning",
                timers=timers,
                detail=warning,
            )
        if validation.errors:
            preview = "; ".join(validation.errors[:5])
            if len(validation.errors) > 5:
                preview = f"{preview}; (and {len(validation.errors) - 5} more)"
            raise ExportError(f"Output schema validation failed: {preview}")

        # Diagram syntax policy:
        # - If --validate-diagrams is enabled, require mmdc and fail if missing.
        # - Otherwise, if mmdc is available, validate all diagram*.mmd outputs and fail
        #   on invalid Mermaid so we don't ship broken artifacts.
        if cfg.diagrams and (cfg.validate_diagrams or is_mmdc_available()):
            _log_event(
                LOG,
                logging.INFO,
                "Mermaid validation started",
                step="diagrams",
                phase="validate",
                timers=timers,
            )
            validated = validate_mermaid_diagrams_with_mmdc(cfg.outdir)
            _log_event(
                LOG,
                logging.INFO,
                "Mermaid diagrams validated",
                step="diagrams",
                phase="validated",
                timers=timers,
                count=len(validated),
            )

        # Optional diff against previous
        if cfg.prev:
            try:
                _log_event(
                    LOG,
                    logging.INFO,
                    "Diff started",
                    step="diff",
                    phase="start",
                    timers=timers,
                )
                diff_obj = diff_files(Path(cfg.prev), inventory_jsonl)
                write_diff(cfg.outdir, diff_obj)
                _log_event(
                    LOG,
                    logging.INFO,
                    "Diff complete",
                    step="diff",
                    phase="complete",
                    timers=timers,
                )
            except Exception as e:
                diff_warning = str(e)
                _log_event(
                    LOG,
                    logging.WARNING,
                    "Diff failed",
                    step="diff",
                    phase="error",
                    timers=timers,
                    error=str(e),
                )

        _log_event(
            LOG,
            logging.INFO,
            "Run complete",
            step="run",
            phase="complete",
            timers=timers,
            outdir=str(cfg.outdir),
            excluded_regions=len(excluded_regions),
        )
        return 0
    except Exception as e:
        status = "FAILED"
        fatal_error = str(e)
        raise
    finally:
        # Always attempt to write a report for transparency.
        finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        if cfg.genai_summary and status == "OK":
            _log_event(
                LOG,
                logging.INFO,
                "GenAI executive summary started",
                step="genai_summary",
                phase="start",
                timers=timers,
            )
            try:
                from .genai import generate_executive_summary  # lazy import
                from .report import build_architecture_facts  # lazy import

                arch_facts = build_architecture_facts(
                    discovered_records=inventory_records,
                    subscribed_regions=subscribed_regions,
                    requested_regions=requested_regions,
                    excluded_regions=excluded_regions,
                    metrics=metrics,
                )

                executive_summary = generate_executive_summary(
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                    subscribed_regions=subscribed_regions,
                    requested_regions=requested_regions,
                    excluded_regions=excluded_regions,
                    metrics=metrics,
                    architecture_facts=arch_facts,
                )
                _log_event(
                    LOG,
                    logging.INFO,
                    "GenAI executive summary complete",
                    step="genai_summary",
                    phase="complete",
                    timers=timers,
                    chars=len(executive_summary or ""),
                )
            except Exception as e:
                executive_summary_error = str(e)
                _log_event(
                    LOG,
                    logging.WARNING,
                    "GenAI executive summary failed",
                    step="genai_summary",
                    phase="error",
                    timers=timers,
                    error=str(e),
                )

        try:
            write_run_report_md(
                outdir=cfg.outdir,
                status=status,
                cfg=cfg,
                subscribed_regions=subscribed_regions,
                requested_regions=requested_regions,
                excluded_regions=excluded_regions,
                discovered_records=inventory_records,
                metrics=metrics,
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

        if cfg.cost_report:
            try:
                _log_event(
                    LOG,
                    logging.INFO,
                    "Cost report started",
                    step="cost_report",
                    phase="start",
                    timers=timers,
                )
                cost_context = _collect_cost_report_data(
                    ctx=ctx,
                    cfg=cfg,
                    subscribed_regions=subscribed_regions,
                    requested_regions=requested_regions,
                    finished_at=finished_at,
                )
                narratives: Optional[Dict[str, str]] = None
                narrative_errors: Optional[Dict[str, str]] = None
                if cfg.genai_summary and status == "OK":
                    _log_event(
                        LOG,
                        logging.INFO,
                        "GenAI cost report narratives started",
                        step="genai_cost_report",
                        phase="start",
                        timers=timers,
                    )
                    try:
                        narratives, narrative_errors = _generate_cost_report_narratives(
                            cost_context=cost_context,
                            cfg=cfg,
                        )
                        _log_event(
                            LOG,
                            logging.INFO,
                            "GenAI cost report narratives complete",
                            step="genai_cost_report",
                            phase="complete",
                            timers=timers,
                            error_count=len(narrative_errors or {}),
                        )
                    except Exception as e:
                        err = str(e)
                        narrative_errors = {
                            "intro": err,
                            "executive_summary": err,
                            "data_sources": err,
                            "consumption_insights": err,
                            "coverage_gaps": err,
                            "audience": err,
                            "next_steps": err,
                        }
                        _log_event(
                            LOG,
                            logging.WARNING,
                            "GenAI cost report narratives failed",
                            step="genai_cost_report",
                            phase="error",
                            timers=timers,
                            error=str(e),
                        )
                write_cost_report_md(
                    outdir=cfg.outdir,
                    status=status,
                    cfg=cfg,
                    cost_context=cost_context,
                    narratives=narratives,
                    narrative_errors=narrative_errors,
                )
                _log_event(
                    LOG,
                    logging.INFO,
                    "Cost report complete",
                    step="cost_report",
                    phase="complete",
                    timers=timers,
                    error_count=len(cost_context.get("errors") or []),
                    warning_count=len(cost_context.get("warnings") or []),
                    usage_items=len(cost_context.get("usage_items") or []),
                )
                usage_items = cost_context.get("usage_items") or []
                if usage_items:
                    workers_export = int(getattr(cfg, "workers_export", 1) or 1)
                    if workers_export < 1:
                        workers_export = 1
                    comp_group_by = cost_context.get("compartment_group_by") or "compartmentId"
                    cost_group_by_label = str(cost_context.get("cost_group_by_label") or "")
                    if workers_export > 1:
                        with ThreadPoolExecutor(max_workers=workers_export) as executor:
                            futures = [
                                executor.submit(
                                    write_cost_usage_csv,
                                    outdir=cfg.outdir,
                                    usage_items=usage_items,
                                ),
                                executor.submit(
                                    write_cost_usage_grouped_csv,
                                    outdir=cfg.outdir,
                                    usage_items=usage_items,
                                    group_by_label=cost_group_by_label or None,
                                ),
                                executor.submit(write_cost_usage_jsonl, outdir=cfg.outdir, usage_items=usage_items),
                                executor.submit(
                                    write_cost_usage_views,
                                    outdir=cfg.outdir,
                                    usage_items=usage_items,
                                    compartment_group_by=str(comp_group_by),
                                ),
                            ]
                            for future in futures:
                                future.result()
                    else:
                        write_cost_usage_csv(
                            outdir=cfg.outdir,
                            usage_items=usage_items,
                        )
                        write_cost_usage_grouped_csv(
                            outdir=cfg.outdir,
                            usage_items=usage_items,
                            group_by_label=cost_group_by_label or None,
                        )
                        write_cost_usage_jsonl(outdir=cfg.outdir, usage_items=usage_items)
                        write_cost_usage_views(
                            outdir=cfg.outdir,
                            usage_items=usage_items,
                            compartment_group_by=str(comp_group_by),
                        )
            except Exception as e:
                from .genai.redact import redact_text

                _log_event(
                    LOG,
                    logging.WARNING,
                    "Cost report failed",
                    step="cost_report",
                    phase="error",
                    timers=timers,
                    error=redact_text(str(e)),
                )


def cmd_diff(cfg: RunConfig) -> int:
    prev = cfg.prev
    curr = cfg.curr
    if not prev or not curr:
        raise ConfigError("Both --prev and --curr must be provided for diff")
    timers = _StepTimers()
    prev_p = Path(prev)
    curr_p = Path(curr)
    _log_event(
        LOG,
        logging.INFO,
        "Diff started",
        step="diff",
        phase="start",
        timers=timers,
    )
    diff_obj = diff_files(prev_p, curr_p)
    write_diff(cfg.outdir, diff_obj)
    _log_event(
        LOG,
        logging.INFO,
        "Diff complete",
        step="diff",
        phase="complete",
        timers=timers,
        outdir=str(cfg.outdir),
    )
    return 0


def cmd_validate_auth(cfg: RunConfig) -> int:
    if cfg.auth in {"config", "security_token"}:
        print("SKIP: OCI config validation disabled by policy.")
        return 0
    if cfg.auth == "auto":
        ctx = _resolve_auth_no_config(cfg)
        if ctx is None:
            print("SKIP: signer-based auth not available; OCI config validation disabled by policy.")
            return 0
    else:
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
    from .genai.config import try_load_genai_config
    from .genai.list_models import list_genai_models, write_genai_models_csv

    genai_cfg = try_load_genai_config()
    if genai_cfg is None:
        print("SKIP: GenAI config not found or invalid; list-genai-models disabled.")
        return 0
    rows = list_genai_models(genai_cfg=genai_cfg)
    write_genai_models_csv(rows, sys.stdout)
    return 0


def main() -> None:
    try:
        command, cfg = load_run_config()
        setup_logging(LogConfig(level=cfg.log_level, json_logs=cfg.json_logs))
        set_client_connection_pool_size(cfg.client_connection_pool_size)

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
        elif command == "enrich-coverage":
            code = cmd_enrich_coverage(cfg)
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
