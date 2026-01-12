from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .auth.providers import AuthContext, AuthError, get_tenancy_ocid, resolve_auth
from .config import RunConfig, load_run_config
from .diff.diff import diff_files, write_diff
from .enrich import get_enricher_for, set_enrich_context
from .export.csv import write_csv
from .export.diagram_projections import is_mmdc_available, validate_mermaid_diagrams_with_mmdc, write_diagram_projections
from .export.graph import build_graph, write_graph, write_mermaid
from .export.jsonl import write_jsonl
from .export.parquet import ParquetNotAvailable, write_parquet
from .logging import LogConfig, get_logger, setup_logging
from .normalize.transform import sort_relationships, stable_json_dumps
from .oci.clients import get_budget_client, get_home_region_name, get_osub_usage_client, get_usage_api_client
from .oci.compartments import list_compartments as oci_list_compartments
from .oci.discovery import discover_in_region
from .oci.regions import get_subscribed_regions
from .report import render_cost_report_md, write_cost_report_md, write_run_report_md
from .util.concurrency import parallel_map_ordered
from .util.errors import (
    AuthResolutionError,
    ConfigError,
    ExportError,
    as_exit_code,
)

LOG = get_logger(__name__)

OUT_SCHEMA_VERSION = "1"

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
    return {}


def _extract_usage_amount(data: Dict[str, Any]) -> float:
    for key in ("computed_amount", "computedAmount", "cost", "amount"):
        val = data.get(key)
        if val is not None:
            try:
                return float(val)
            except Exception:
                return 0.0
    return 0.0


def _extract_usage_currency(data: Dict[str, Any]) -> Optional[str]:
    for key in ("currency", "currency_code", "currencyCode"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _extract_group_value(data: Dict[str, Any], group_by: Optional[str]) -> str:
    if not group_by:
        return ""
    keys_by_group = {
        "service": ("service", "service_name", "serviceName"),
        "compartmentId": ("compartment_id", "compartmentId", "compartment_id"),
        "region": ("region", "region_name", "regionName"),
        "sku": ("sku", "sku_name", "skuName"),
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
    group_by: Optional[str],
) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str]]:
    try:
        import oci  # type: ignore
    except Exception as e:  # pragma: no cover - import error surfaced in CLI validate
        return [], None, str(e)

    details_cls = getattr(getattr(oci, "usage_api", None), "models", None)
    if details_cls is None or not hasattr(details_cls, "RequestSummarizedUsagesDetails"):
        return [], None, "OCI Usage API models are unavailable"

    details_kwargs: Dict[str, Any] = {
        "tenant_id": tenancy_id,
        "time_usage_started": start,
        "time_usage_ended": end,
        "granularity": "MONTHLY",
        "query_type": "COST",
    }
    if group_by:
        details_kwargs["group_by"] = [group_by]
        if group_by == "compartmentId":
            details_kwargs["compartment_depth"] = 6
    details = details_cls.RequestSummarizedUsagesDetails(**details_kwargs)

    totals_by_name: Dict[str, float] = {}
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
        items = getattr(data, "items", []) if data is not None else []
        data_currency = getattr(data, "currency", None) if data is not None else None
        if isinstance(data_currency, str) and data_currency.strip():
            currency = data_currency.strip()
        for item in items or []:
            item_dict = _usage_item_to_dict(item)
            amount = _extract_usage_amount(item_dict)
            name = _extract_group_value(item_dict, group_by)
            if group_by and not name:
                continue
            totals_by_name[name] = totals_by_name.get(name, 0.0) + amount
            item_currency = _extract_usage_currency(item_dict)
            if item_currency and not currency:
                currency = item_currency

        page = getattr(resp, "headers", {}).get("opc-next-page")
        if not page:
            break

    rows = [{"name": name, "amount": total} for name, total in sorted(totals_by_name.items())]
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
        warnings.append("Cost time range normalized to 00:00:00 UTC for Usage API MONTHLY granularity.")
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(days=1)
        warnings.append("Cost end time adjusted to ensure end > start.")

    if start_dt >= end_dt:
        errors.append("Cost time range is invalid (start >= end).")

    tenancy_id = get_tenancy_ocid(ctx) if ctx else None
    if not tenancy_id:
        errors.append("Tenancy OCID is required for cost reporting.")

    cost_region = None
    if tenancy_id and ctx:
        try:
            cost_region = get_home_region_name(ctx)
        except Exception as e:
            errors.append(redact_text(f"Home region lookup failed: {e}"))
    if not cost_region:
        if requested_regions:
            cost_region = sorted([r for r in requested_regions if r])[0]
            warnings.append("Home region unavailable; using requested region for Usage API.")
        else:
            cost_region = sorted(subscribed_regions)[0] if subscribed_regions else None
            warnings.append("Home region unavailable; using subscribed region for Usage API.")

    services: List[Dict[str, Any]] = []
    compartments: List[Dict[str, Any]] = []
    regions: List[Dict[str, Any]] = []
    total_cost = 0.0
    currency: Optional[str] = None

    query_inputs: Dict[str, Any] = {
        "tenant_id": tenancy_id,
        "time_usage_started": start_dt.isoformat(timespec="seconds"),
        "time_usage_ended": end_dt.isoformat(timespec="seconds"),
        "granularity": "MONTHLY",
        "query_type": "COST",
        "group_by": ["service", "compartmentId", "region"],
        "compartment_depth": 6,
        "region": cost_region,
        "home_region": cost_region,
    }
    if cost_region and requested_regions and cost_region not in requested_regions:
        warnings.append("Usage API forced to tenancy home region, overriding requested region.")
    if start_raw != start_dt:
        query_inputs["time_usage_started_raw"] = start_raw.isoformat(timespec="seconds")
    if end_raw != end_dt:
        query_inputs["time_usage_ended_raw"] = end_raw.isoformat(timespec="seconds")

    if tenancy_id and start_dt < end_dt and ctx:
        try:
            usage_client = get_usage_api_client(ctx, region=cost_region)
        except Exception as e:
            errors.append(redact_text(f"Usage API client failed: {e}"))
            steps.append({"name": "usage_api_total", "status": "ERROR"})
            steps.append({"name": "usage_api_service", "status": "ERROR"})
            steps.append({"name": "usage_api_compartment", "status": "ERROR"})
            steps.append({"name": "usage_api_region", "status": "ERROR"})
        else:
            rows, cur, err = _request_summarized_usages(
                usage_client,
                tenancy_id,
                start_dt,
                end_dt,
                group_by=None,
            )
            steps.append({"name": "usage_api_total", "status": "OK" if not err else "ERROR"})
            if err:
                errors.append(redact_text(f"Usage API total failed: {err}"))
            else:
                total_cost = sum(float(r.get("amount") or 0.0) for r in rows)
                currency = cur or currency

            rows, cur, err = _request_summarized_usages(
                usage_client,
                tenancy_id,
                start_dt,
                end_dt,
                group_by="service",
            )
            steps.append({"name": "usage_api_service", "status": "OK" if not err else "ERROR"})
            if err:
                errors.append(redact_text(f"Usage API service failed: {err}"))
            else:
                services = rows
                currency = cur or currency

            rows, cur, err = _request_summarized_usages(
                usage_client,
                tenancy_id,
                start_dt,
                end_dt,
                group_by="compartmentId",
            )
            steps.append({"name": "usage_api_compartment", "status": "OK" if not err else "ERROR"})
            if err:
                errors.append(redact_text(f"Usage API compartment failed: {err}"))
            else:
                compartments = [
                    {"compartment_id": r.get("name", ""), "amount": r.get("amount", 0.0)} for r in rows
                ]
                currency = cur or currency

            rows, cur, err = _request_summarized_usages(
                usage_client,
                tenancy_id,
                start_dt,
                end_dt,
                group_by="region",
            )
            steps.append({"name": "usage_api_region", "status": "OK" if not err else "ERROR"})
            if err:
                errors.append(redact_text(f"Usage API region failed: {err}"))
            else:
                regions = rows
                currency = cur or currency
    else:
        steps.append({"name": "usage_api_total", "status": "SKIPPED"})
        steps.append({"name": "usage_api_service", "status": "SKIPPED"})
        steps.append({"name": "usage_api_compartment", "status": "SKIPPED"})
        steps.append({"name": "usage_api_region", "status": "SKIPPED"})

    if cfg.cost_currency:
        if currency and currency != cfg.cost_currency:
            warnings.append(
                f"Currency mismatch: Usage API returned {currency}, CLI configured {cfg.cost_currency}."
            )
        currency = cfg.cost_currency

    budgets: List[Dict[str, Any]] = []
    alert_rule_counts: Dict[str, int] = {}
    if tenancy_id and ctx:
        try:
            budget_client = get_budget_client(ctx, region=cost_region)
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
        try:
            osub_client = get_osub_usage_client(ctx, region=cost_region)
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
                if hasattr(osub_client, "request_computed_usage"):
                    try:
                        details_cls = getattr(getattr(oci, "osub_usage", None), "models", None)
                        if details_cls and hasattr(details_cls, "RequestComputedUsageDetails"):
                            details = details_cls.RequestComputedUsageDetails(
                                tenant_id=tenancy_id,
                                time_usage_started=start_dt,
                                time_usage_ended=end_dt,
                            )
                            resp = osub_client.request_computed_usage(details)  # type: ignore[attr-defined]
                            data = getattr(resp, "data", None)
                            osub_usage = _usage_item_to_dict(data) if data is not None else None
                            steps.append({"name": "osub_usage", "status": "OK"})
                        else:
                            steps.append({"name": "osub_usage", "status": "ERROR"})
                            errors.append("OneSubscription models are unavailable.")
                    except Exception as e:
                        steps.append({"name": "osub_usage", "status": "ERROR"})
                        errors.append(redact_text(f"OneSubscription usage failed: {e}"))
                else:
                    steps.append({"name": "osub_usage", "status": "ERROR"})
                    errors.append("OneSubscription client does not support computed usage requests.")
    else:
        steps.append({"name": "osub_usage", "status": "SKIPPED"})

    compartment_names: Dict[str, str] = {}
    comp_ids = {str(r.get("compartment_id") or "") for r in compartments if str(r.get("compartment_id") or "")}
    if comp_ids and ctx:
        try:
            comp_rows = oci_list_compartments(ctx, tenancy_ocid=tenancy_id)
            compartment_names = {c["ocid"]: c["name"] for c in comp_rows if c.get("ocid") and c.get("name")}
            steps.append({"name": "compartment_names", "status": "OK"})
        except Exception as e:
            steps.append({"name": "compartment_names", "status": "ERROR"})
            errors.append(redact_text(f"Compartment name lookup failed: {e}"))
    elif comp_ids:
        steps.append({"name": "compartment_names", "status": "ERROR"})
        errors.append("Compartment name lookup skipped: no auth context.")

    return {
        "time_start": start_dt.isoformat(timespec="seconds"),
        "time_end": end_dt.isoformat(timespec="seconds"),
        "currency": currency or "UNKNOWN",
        "currency_source": "usage_api" if currency and currency != cfg.cost_currency else "cli" if cfg.cost_currency else "unknown",
        "total_cost": total_cost,
        "services": services,
        "compartments": compartments,
        "regions": regions,
        "budgets": budgets,
        "budget_alert_rule_counts": alert_rule_counts,
        "osub_usage": osub_usage,
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


def _validate_outdir_schema(outdir: Path, *, expect_graph: bool = True) -> SchemaValidation:
    errors: List[str] = []
    warnings: List[str] = []

    inventory_path = outdir / "inventory.jsonl"
    inventory_records = _read_jsonl_dicts(
        inventory_path,
        required_fields=REQUIRED_INVENTORY_FIELDS,
        errors=errors,
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
    )

    nodes_path = outdir / "graph_nodes.jsonl"
    edges_path = outdir / "graph_edges.jsonl"
    if expect_graph or nodes_path.is_file() or edges_path.is_file():
        node_records = _read_jsonl_dicts(
            nodes_path,
            required_fields=REQUIRED_GRAPH_NODE_FIELDS,
            errors=errors,
        )
        node_ids = {str(obj.get("nodeId") or "") for _, obj in node_records if obj.get("nodeId")}

        edge_records = _read_jsonl_dicts(
            edges_path,
            required_fields=REQUIRED_GRAPH_EDGE_FIELDS,
            errors=errors,
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
    # Ensure the run directory exists early so we can always emit a report.
    cfg.outdir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_collected_at = started_at

    status = "OK"
    fatal_error: Optional[str] = None
    ctx: Optional[AuthContext] = None

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
            return discover_in_region(ctx, r, cfg.query, collected_at=run_collected_at)

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

        # Derive additional relationships from record metadata (offline; no new OCI calls)
        # to improve graph/report fidelity when enrichers did not emit relationships.
        from .export.graph import derive_relationships_from_metadata

        derived_relationships = derive_relationships_from_metadata(enriched)
        if derived_relationships:
            _merge_relationships_into_records(enriched, derived_relationships)
            all_relationships.extend(derived_relationships)

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
        if cfg.diagrams:
            nodes, edges = build_graph(enriched, all_relationships)
            write_graph(cfg.outdir, nodes, edges)
            write_mermaid(cfg.outdir, nodes, edges)
            write_diagram_projections(cfg.outdir, nodes, edges)

        validation = _validate_outdir_schema(cfg.outdir, expect_graph=cfg.diagrams)
        for warning in validation.warnings:
            LOG.warning("Output schema validation warning", extra={"detail": warning})
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
            validated = validate_mermaid_diagrams_with_mmdc(cfg.outdir)
            LOG.info("Mermaid diagrams validated", extra={"count": len(validated)})

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
                from .report import build_architecture_facts  # lazy import

                arch_facts = build_architecture_facts(
                    discovered_records=enriched or discovered,
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

        if cfg.cost_report:
            try:
                cost_context = _collect_cost_report_data(
                    ctx=ctx,
                    cfg=cfg,
                    subscribed_regions=subscribed_regions,
                    requested_regions=requested_regions,
                    finished_at=finished_at,
                )
                cost_executive_summary: Optional[str] = None
                cost_executive_summary_error: Optional[str] = None
                if cfg.genai_summary and status == "OK":
                    try:
                        from .genai import generate_executive_summary  # lazy import
                        from .genai.redact import redact_text

                        try:
                            cfg_dict = asdict(cfg)
                        except Exception:
                            cfg_dict = {
                                "cost_report": getattr(cfg, "cost_report", None),
                                "cost_start": getattr(cfg, "cost_start", None),
                                "cost_end": getattr(cfg, "cost_end", None),
                                "cost_currency": getattr(cfg, "cost_currency", None),
                                "assessment_target_group": getattr(cfg, "assessment_target_group", None),
                                "assessment_target_scope": getattr(cfg, "assessment_target_scope", None),
                                "assessment_lens_weights": getattr(cfg, "assessment_lens_weights", None),
                                "assessment_capabilities": getattr(cfg, "assessment_capabilities", None),
                            }

                        base_report_md = render_cost_report_md(
                            status=status,
                            cfg_dict=cfg_dict,
                            cost_context=cost_context,
                        )
                        safe_report_md = redact_text(base_report_md)
                        cost_executive_summary = generate_executive_summary(
                            status=status,
                            started_at=started_at,
                            finished_at=finished_at,
                            subscribed_regions=subscribed_regions,
                            requested_regions=requested_regions,
                            excluded_regions=excluded_regions,
                            metrics=metrics,
                            report_md=safe_report_md,
                        )
                    except Exception as e:
                        cost_executive_summary_error = str(e)
                        LOG.warning("GenAI cost report summary failed", extra={"error": str(e)})
                write_cost_report_md(
                    outdir=cfg.outdir,
                    status=status,
                    cfg=cfg,
                    cost_context=cost_context,
                    executive_summary=cost_executive_summary,
                    executive_summary_error=cost_executive_summary_error,
                )
            except Exception as e:
                from .genai.redact import redact_text

                LOG.warning("Cost report failed", extra={"error": redact_text(str(e))})


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
