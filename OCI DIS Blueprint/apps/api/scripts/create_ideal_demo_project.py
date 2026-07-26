#!/usr/bin/env python3
"""Create and validate a complete fictional demo through public App APIs only."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_CEILING
import json
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


TERMINAL_JOB_STATUSES = {"completed", "failed", "cleaned_up"}
TERMINAL_AGENT_STATUSES = {
    "completed",
    "failed",
    "cancelled",
    "waiting_approval",
}
SCENARIO_VARIANTS = (
    ("LI Standard", False, "standard"),
    ("LI Enterprise", False, "enterprise"),
    ("BYOL Standard", True, "standard"),
    ("BYOL Enterprise", True, "enterprise"),
)
ENVIRONMENT_PLANS = (
    ("DEV", 1, 240.0, 0.15, Decimal("0.10"), Decimal("0.40")),
    ("QA", 7, 360.0, 0.25, Decimal("0.15"), Decimal("0.65")),
    ("PRD", 13, 744.0, 0.60, Decimal("0.25"), Decimal("1.00")),
)


class ApiFailure(RuntimeError):
    """One non-success response from the public API."""


@dataclass(frozen=True)
class DemoConfig:
    api_url: str
    project_name: str
    customer_name: str
    seed: int
    target_catalog_size: int
    import_target: int
    manual_target: int
    excluded_import_target: int
    min_distinct_systems: int
    contract_months: int
    start_date: str
    region: str
    actor_id: str
    poll_seconds: float
    timeout_seconds: float


class ApiClient:
    """Small JSON client that keeps all mutations on supported HTTP contracts."""

    def __init__(self, config: DemoConfig) -> None:
        self.base_url = config.api_url.rstrip("/")
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Actor-Id": config.actor_id,
            "X-Actor-Role": "Admin",
        }

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        query: dict[str, object] | None = None,
    ) -> dict[str, Any] | list[Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(url, data=body, headers=self.headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                contents = response.read()
                return json.loads(contents) if contents else {}
        except HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise ApiFailure(f"{method} {path} returned HTTP {exc.code}: {detail}") from exc

    def get(
        self,
        path: str,
        *,
        query: dict[str, object] | None = None,
    ) -> dict[str, Any] | list[Any]:
        return self.request("GET", path, query=query)

    def post(
        self,
        path: str,
        payload: dict[str, object],
    ) -> dict[str, Any] | list[Any]:
        return self.request("POST", path, payload)

    def patch(
        self,
        path: str,
        payload: dict[str, object],
    ) -> dict[str, Any] | list[Any]:
        return self.request("PATCH", path, payload)


def _object(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("Expected one JSON object")
    return payload


def _objects(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise TypeError("Expected a JSON object array")
    return payload


def _wait_for_resource(
    client: ApiClient,
    path: str,
    *,
    terminal_statuses: set[str],
    config: DemoConfig,
) -> dict[str, Any]:
    deadline = time.monotonic() + config.timeout_seconds
    while time.monotonic() < deadline:
        payload = _object(client.get(path))
        status = str(payload.get("status") or "")
        if status in terminal_statuses:
            return payload
        time.sleep(config.poll_seconds)
    raise TimeoutError(f"Timed out waiting for {path}")


def _create_synthetic_project(
    client: ApiClient,
    config: DemoConfig,
    job_id: str | None,
) -> tuple[str, dict[str, Any]]:
    if job_id is None:
        job = _object(
            client.post(
                "/admin/synthetic/jobs",
                {
                    "project_name": config.project_name,
                    "preset_code": "retained-smoke",
                    "target_catalog_size": config.target_catalog_size,
                    "min_distinct_systems": config.min_distinct_systems,
                    "import_target": config.import_target,
                    "manual_target": config.manual_target,
                    "excluded_import_target": config.excluded_import_target,
                    "include_justifications": True,
                    "include_exports": True,
                    "include_design_warnings": False,
                    "cleanup_policy": "manual",
                    "seed_value": config.seed,
                },
            )
        )
        job_id = str(job["id"])
        print(f"Synthetic job queued: {job_id}", flush=True)
    job = _wait_for_resource(
        client,
        f"/admin/synthetic/jobs/{job_id}",
        terminal_statuses=TERMINAL_JOB_STATUSES,
        config=config,
    )
    if job["status"] != "completed" or not job.get("project_id"):
        raise RuntimeError(f"Synthetic generation did not complete: {job}")
    return str(job["project_id"]), job


def _patch_project_identity(
    client: ApiClient,
    config: DemoConfig,
    project_id: str,
) -> dict[str, Any]:
    project = _object(client.get(f"/projects/{project_id}"))
    metadata = dict(project.get("project_metadata") or {})
    metadata.update(
        {
            "demo_profile": "ideal-enterprise-portfolio-v1",
            "fictional_customer": True,
            "contract_months": config.contract_months,
            "environment_activation_months": {"DEV": 1, "QA": 7, "PRD": 13},
            "environment_offset_months": 6,
            "verified_sku_scope": (
                "all_approved_billable_mappings_across_governed_variants"
            ),
        }
    )
    return _object(
        client.patch(
            f"/projects/{project_id}",
            {
                "name": config.project_name,
                "customer_name": config.customer_name,
                "description": (
                    "Fictional ideal-state enterprise integration portfolio with "
                    f"{config.target_catalog_size} governed integrations, a "
                    f"{config.contract_months}-month planning horizon, and DEV, QA, "
                    "and PRD activation offset by six months."
                ),
                "project_metadata": metadata,
            },
        )
    )


def _approved_mappings(client: ApiClient) -> list[dict[str, Any]]:
    payload = _object(client.get("/pricing/sku-mappings"))
    return [
        mapping
        for mapping in payload.get("mappings", [])
        if isinstance(mapping, dict) and mapping.get("status") == "approved"
    ]


def _normalize_commercially_resolvable_patterns(
    client: ApiClient,
    config: DemoConfig,
    project_id: str,
) -> dict[str, object]:
    """Replace unpriceable family-label designs through governed catalog APIs."""

    catalog = _object(
        client.get(
            f"/catalog/{project_id}",
            query={"page": 1, "page_size": 500},
        )
    )
    integrations = [
        item for item in catalog.get("integrations", []) if isinstance(item, dict)
    ]
    replacements = (
        (
            "#15",
            {
                "selected_pattern": "#06",
                "pattern_rationale": (
                    "Ideal demo normalization: governed Strangler Fig routing with "
                    "OIC and API Gateway preserves large payloads without relying "
                    "on an unresolved AI family label."
                ),
                "core_tools": "OIC Gen3",
                "additional_tools_overlays": "OCI API Gateway",
            },
        ),
        (
            "#16",
            {
                "selected_pattern": "#13",
                "pattern_rationale": (
                    "Ideal demo normalization: Zero-Trust Integration preserves "
                    "OIC, API Gateway, IAM, and Observability without an unresolved "
                    "generic OKE family label."
                ),
                "core_tools": "OIC Gen3",
                "additional_tools_overlays": (
                    "OCI API Gateway, OCI IAM and Security Services, OCI Observability"
                ),
            },
        ),
    )
    updated = 0
    replacement_counts: dict[str, int] = {}
    for source_pattern, patch in replacements:
        integration_ids = [
            str(item["id"])
            for item in integrations
            if item.get("selected_pattern") == source_pattern
        ]
        if not integration_ids:
            replacement_counts[source_pattern] = 0
            continue
        result = _object(
            client.post(
                f"/catalog/{project_id}/bulk-patch",
                {
                    "integration_ids": integration_ids,
                    "patch": patch,
                    "actor_id": config.actor_id,
                },
            )
        )
        if result.get("errors"):
            raise RuntimeError(
                f"Pattern normalization failed for {source_pattern}: {result}"
            )
        replacement_counts[source_pattern] = int(result["updated"])
        updated += int(result["updated"])

    integration_ids = [str(item["id"]) for item in integrations]
    evidence_result = _object(
        client.post(
            f"/catalog/{project_id}/bulk-patch",
            {
                "integration_ids": integration_ids,
                "patch": {
                    "business_criticality": "High",
                    "target_latency_sla": "5 seconds",
                    "data_security_classification": "Confidential",
                    "retention_processing_window": (
                        "Retain governed evidence for 30 days; complete processing "
                        "within a 4-hour window."
                    ),
                    "retry_policy": (
                        "Exponential backoff, maximum 3 retries within 10 minutes."
                    ),
                    "idempotency": (
                        "Reject duplicates by governed business key and source sequence."
                    ),
                },
                "actor_id": config.actor_id,
            },
        )
    )
    if evidence_result.get("errors"):
        raise RuntimeError(
            f"Ideal QA evidence normalization failed: {evidence_result}"
        )

    if updated or int(evidence_result["updated"]):
        job = _object(client.post(f"/recalculate/{project_id}", {}))
        job_id = str(job["job_id"])
        job = _wait_for_resource(
            client,
            f"/recalculate/{project_id}/jobs/{job_id}",
            terminal_statuses={"completed", "failed"},
            config=config,
        )
        if job["status"] != "completed":
            raise RuntimeError(f"Post-normalization recalculation failed: {job}")
    return {
        "updated": updated,
        "replacement_counts": replacement_counts,
        "qa_evidence_updated": int(evidence_result["updated"]),
    }


def _selectable_service_ids(client: ApiClient, project_id: str) -> set[str]:
    payload = _object(
        client.get(
            f"/projects/{project_id}/selectable-products",
            query={"page": 1, "page_size": 100},
        )
    )
    items = payload.get("items", [])
    return {
        str(item["service_id"])
        for item in items
        if isinstance(item, dict) and item.get("service_id")
    }


def _metric_options(
    client: ApiClient,
    project_id: str,
    service_ids: set[str],
) -> dict[str, dict[str, Any]]:
    by_mapping_id: dict[str, dict[str, Any]] = {}
    for service_id in sorted(service_ids):
        options = _objects(
            client.get(
                f"/projects/{project_id}/selectable-products/{quote(service_id)}/metric-options"
            )
        )
        for option in options:
            for variant in option.get("variants", []):
                if isinstance(variant, dict) and variant.get("sku_mapping_id"):
                    by_mapping_id[str(variant["sku_mapping_id"])] = option
    return by_mapping_id


def _decimal(value: object, default: Decimal = Decimal("0")) -> Decimal:
    if isinstance(value, bool) or value is None:
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _ceil_increment(value: Decimal, increment: Decimal) -> Decimal:
    if increment <= 0:
        return value
    units = (value / increment).to_integral_value(rounding=ROUND_CEILING)
    return units * increment


def _full_quantity(
    mapping: dict[str, Any],
    option: dict[str, Any],
) -> Decimal:
    increment = max(_decimal(mapping.get("quantity_increment")), Decimal("0.000001"))
    minimum = _decimal(mapping.get("minimum_quantity"))
    candidates = [
        _decimal(option.get("source_baseline_quantity")),
        _decimal(option.get("baseline_quantity")),
        _decimal(option.get("planning_envelope_quantity")),
        minimum,
        increment * Decimal("100"),
    ]
    for preset in option.get("quantity_presets", []):
        if isinstance(preset, dict):
            candidates.append(_decimal(preset.get("quantity")))
    full = _ceil_increment(max(candidates), increment)
    return max(full, minimum + (increment * Decimal("10")))


def _phase(
    mapping: dict[str, Any],
    option: dict[str, Any],
    *,
    environment: str,
    start_month: int,
    end_month: int,
    start_factor: Decimal,
    end_factor: Decimal,
) -> dict[str, object]:
    increment = max(_decimal(mapping.get("quantity_increment")), Decimal("0.000001"))
    minimum = _decimal(mapping.get("minimum_quantity"))
    full = _full_quantity(mapping, option)
    start = max(minimum, _ceil_increment(full * start_factor, increment))
    end = max(minimum, _ceil_increment(full * end_factor, increment))
    if end <= start:
        end = start + increment
    return {
        "service_id": mapping["service_id"],
        "metric_key": mapping["billing_metric_key"],
        "sku_mapping_id": mapping["id"],
        "start_month": start_month,
        "end_month": end_month,
        "start_multiplier": float(start_factor),
        "end_multiplier": float(end_factor),
        "interpolation": "linear",
        "start_quantity": float(start),
        "end_quantity": float(end),
        "quantity_unit": mapping["quantity_unit"],
        "monthly_quantities": [],
        "rationale": (
            f"{environment} activates in contract month {start_month} and grows "
            f"linearly through month {end_month} using governed commercial units."
        ),
    }


def _mapping_applies(
    mapping: dict[str, Any],
    *,
    byol: bool,
    edition: str,
) -> bool:
    predicates = mapping.get("predicates") or {}
    if not isinstance(predicates, dict):
        return False
    if "byol" in predicates and bool(predicates["byol"]) is not byol:
        return False
    if "edition" in predicates and str(predicates["edition"]) != edition:
        return False
    return True


def _scenario_payload(
    config: DemoConfig,
    *,
    name_suffix: str,
    byol: bool,
    edition: str,
    mappings: list[dict[str, Any]],
    options: dict[str, dict[str, Any]],
) -> tuple[dict[str, object], set[str]]:
    selected = [
        mapping
        for mapping in mappings
        if _mapping_applies(mapping, byol=byol, edition=edition)
    ]
    missing_options = sorted(
        str(mapping["id"]) for mapping in selected if str(mapping["id"]) not in options
    )
    if missing_options:
        raise RuntimeError(f"Approved mappings have no metric options: {missing_options}")

    environments: list[dict[str, object]] = []
    for (
        environment,
        activation_month,
        active_hours,
        demand_share,
        start_factor,
        end_factor,
    ) in ENVIRONMENT_PLANS:
        phases = [
            _phase(
                mapping,
                options[str(mapping["id"])],
                environment=environment,
                start_month=activation_month,
                end_month=config.contract_months,
                start_factor=start_factor,
                end_factor=end_factor,
            )
            for mapping in selected
        ]
        environments.append(
            {
                "name": environment,
                "active_hours_month": active_hours,
                "demand_share": demand_share,
                "ha_multiplier": 1.0,
                "dr_role": "none",
                "phases": phases,
            }
        )

    return (
        {
            "name": f"Ideal 36M · {name_suffix}",
            "currency": "USD",
            "region": config.region,
            "price_mode": "public_list",
            "commitment_model": "pay_as_you_go",
            "licensing_model": "byol" if byol else "license_included",
            "contract_months": config.contract_months,
            "start_date": config.start_date,
            "proration_policy": "full_month",
            "consumption_model": "explicit_units",
            "environments": environments,
            "service_config": {
                "OIC3": {"edition": edition, "byol": byol},
            },
            "assumptions": {
                "demo_profile": "ideal-enterprise-portfolio-v1",
                "environment_offset_months": 6,
                "quantity_strategy": "governed_linear_growth",
                "sku_scope": (
                    "all approved billable mappings across four governed variants"
                ),
            },
        },
        {str(mapping["id"]) for mapping in selected},
    )


def _scenario_by_name(client: ApiClient, project_id: str) -> dict[str, dict[str, Any]]:
    payload = _object(client.get(f"/projects/{project_id}/deployment-scenarios"))
    return {
        str(item["name"]): item
        for item in payload.get("scenarios", [])
        if isinstance(item, dict) and item.get("name")
    }


def _ensure_scenario(
    client: ApiClient,
    project_id: str,
    payload: dict[str, object],
) -> dict[str, Any]:
    existing = _scenario_by_name(client, project_id).get(str(payload["name"]))
    scenario = existing or _object(
        client.post(f"/projects/{project_id}/deployment-scenarios", payload)
    )
    if scenario["status"] != "approved":
        scenario = _object(
            client.post(
                f"/projects/{project_id}/deployment-scenarios/{scenario['id']}/approve",
                {},
            )
        )
    return scenario


def _existing_snapshot(
    client: ApiClient,
    project_id: str,
    scenario_id: str,
) -> dict[str, Any] | None:
    payload = _object(
        client.get(f"/projects/{project_id}/bom-snapshots", query={"limit": 20})
    )
    for item in payload.get("snapshots", []):
        if isinstance(item, dict) and item.get("scenario_id") == scenario_id:
            return _object(
                client.get(f"/projects/{project_id}/bom-snapshots/{item['id']}")
            )
    return None


def _ensure_bom(
    client: ApiClient,
    config: DemoConfig,
    project_id: str,
    scenario: dict[str, Any],
) -> dict[str, Any]:
    snapshot = _existing_snapshot(client, project_id, str(scenario["id"]))
    if snapshot is None:
        job = _object(
            client.post(
                f"/projects/{project_id}/bom-jobs",
                {"scenario_id": scenario["id"]},
            )
        )
        job = _wait_for_resource(
            client,
            f"/projects/{project_id}/bom-jobs/{job['id']}",
            terminal_statuses={"completed", "failed"},
            config=config,
        )
        if job["status"] != "completed" or not job.get("bom_snapshot_id"):
            raise RuntimeError(f"BOM generation failed: {job}")
        snapshot = _object(
            client.get(
                f"/projects/{project_id}/bom-snapshots/{job['bom_snapshot_id']}"
            )
        )
    if float(snapshot["coverage_pct"]) != 100.0:
        raise RuntimeError(
            f"BOM {snapshot['id']} coverage is {snapshot['coverage_pct']}, not 100"
        )
    if snapshot["publication_status"] != "published":
        snapshot = _object(
            client.post(
                f"/projects/{project_id}/bom-snapshots/{snapshot['id']}/review",
                {
                    "publication_status": "published",
                    "note": (
                        "Published fictional ideal-state demo after complete SKU, "
                        "commercial evidence, and ramp validation."
                    ),
                },
            )
        )
    return snapshot


def _validate_monthly_ramp(snapshot: dict[str, Any]) -> None:
    series = {
        int(item["period_index"]): item
        for item in snapshot.get("monthly_series", [])
        if isinstance(item, dict)
    }
    if sorted(series) != list(range(1, 37)):
        raise RuntimeError("BOM monthly series does not contain all 36 contract months")
    checks = (
        (1, "DEV", True),
        (6, "QA", False),
        (7, "QA", True),
        (12, "PRD", False),
        (13, "PRD", True),
    )
    for month, environment, should_be_active in checks:
        amount = float(series[month].get("by_environment", {}).get(environment, 0))
        if should_be_active and amount <= 0:
            raise RuntimeError(f"{environment} is not active in month {month}")
        if not should_be_active and amount != 0:
            raise RuntimeError(f"{environment} activates before month {month + 1}")
    totals = [float(series[month]["total"]) for month in range(1, 37)]
    if any(current + 0.01 < previous for previous, current in zip(totals, totals[1:])):
        raise RuntimeError("Contract consumption is not monotonically non-decreasing")


def _run_agent(
    client: ApiClient,
    config: DemoConfig,
    project_id: str,
    agent_type: str,
) -> dict[str, Any]:
    run = _object(
        client.post(
            "/agents/runs",
            {
                "agent_type": agent_type,
                "project_id": project_id,
                "context": {"demo_validation": True},
                "message": (
                    "Validate this fictional ideal-state demo using governed project "
                    "evidence. Report remaining gaps without inventing data."
                ),
                "include_provider": True,
            },
        )
    )
    return _wait_for_resource(
        client,
        f"/agents/runs/{run['id']}",
        terminal_statuses=TERMINAL_AGENT_STATUSES,
        config=config,
    )


def create_demo(
    config: DemoConfig,
    *,
    job_id: str | None,
    project_id: str | None,
    run_agents: bool,
) -> dict[str, object]:
    client = ApiClient(config)
    if project_id is None:
        project_id, synthetic_job = _create_synthetic_project(client, config, job_id)
    else:
        synthetic_job = {"id": job_id, "status": "reused", "project_id": project_id}
    project = _patch_project_identity(client, config, project_id)
    pattern_normalization = _normalize_commercially_resolvable_patterns(
        client,
        config,
        project_id,
    )

    catalog = _object(
        client.get(
            f"/catalog/{project_id}",
            query={"page": 1, "page_size": 500},
        )
    )
    if int(catalog["total"]) != config.target_catalog_size:
        raise RuntimeError(
            f"Expected {config.target_catalog_size} integrations, found {catalog['total']}"
        )
    catalog_rows = [
        item
        for item in catalog.get("integrations", [])
        if isinstance(item, dict)
    ]
    qa_distribution: dict[str, int] = {}
    qa_reason_distribution: dict[str, int] = {}
    for row in catalog_rows:
        qa_status = str(row.get("qa_status") or "UNKNOWN")
        qa_distribution[qa_status] = qa_distribution.get(qa_status, 0) + 1
        for reason in row.get("qa_reasons", []):
            reason_key = str(reason)
            qa_reason_distribution[reason_key] = (
                qa_reason_distribution.get(reason_key, 0) + 1
            )
    if qa_distribution != {"OK": config.target_catalog_size}:
        raise RuntimeError(
            "Ideal demo catalog is not fully QA-ready: "
            f"statuses={qa_distribution}, reasons={qa_reason_distribution}"
        )

    approved = _approved_mappings(client)
    verified_sku_mappings = [
        mapping
        for mapping in approved
        if mapping.get("is_billable") is True and mapping.get("part_number")
    ]
    non_billable_mappings = [
        mapping for mapping in approved if mapping not in verified_sku_mappings
    ]
    selectable = _selectable_service_ids(client, project_id)
    scoped_mappings = [
        mapping
        for mapping in verified_sku_mappings
        if str(mapping["service_id"]) in selectable
    ]
    if {str(item["id"]) for item in scoped_mappings} != {
        str(item["id"]) for item in verified_sku_mappings
    }:
        missing = sorted(
            {str(item["id"]) for item in verified_sku_mappings}
            - {str(item["id"]) for item in scoped_mappings}
        )
        raise RuntimeError(
            f"Approved billable SKU mappings are not selectable: {missing}"
        )
    options = _metric_options(client, project_id, selectable)

    planned_mapping_ids: set[str] = set()
    snapshots: list[dict[str, Any]] = []
    scenarios: list[dict[str, Any]] = []
    for name_suffix, byol, edition in SCENARIO_VARIANTS:
        payload, mapping_ids = _scenario_payload(
            config,
            name_suffix=name_suffix,
            byol=byol,
            edition=edition,
            mappings=scoped_mappings,
            options=options,
        )
        scenario = _ensure_scenario(client, project_id, payload)
        snapshot = _ensure_bom(client, config, project_id, scenario)
        _validate_monthly_ramp(snapshot)
        scenarios.append(scenario)
        snapshots.append(snapshot)
        planned_mapping_ids.update(mapping_ids)
        print(
            f"Published BOM {snapshot['id']} for {scenario['name']} "
            f"({snapshot['coverage_pct']}% coverage)",
            flush=True,
        )

    approved_mapping_ids = {
        str(mapping["id"]) for mapping in verified_sku_mappings
    }
    if planned_mapping_ids != approved_mapping_ids:
        raise RuntimeError(
            "Scenario suite did not cover every approved mapping: "
            f"{sorted(approved_mapping_ids - planned_mapping_ids)}"
        )
    verified_part_numbers = {
        str(mapping["part_number"])
        for mapping in verified_sku_mappings
        if mapping.get("part_number")
    }
    bom_part_numbers = {
        str(line["part_number"])
        for snapshot in snapshots
        for line in snapshot.get("line_items", [])
        if isinstance(line, dict) and line.get("part_number")
    }
    if not verified_part_numbers.issubset(bom_part_numbers):
        raise RuntimeError(
            "Published BOM suite is missing verified part numbers: "
            f"{sorted(verified_part_numbers - bom_part_numbers)}"
        )

    agent_runs: list[dict[str, Any]] = []
    if run_agents:
        for agent_type in ("architecture_review", "bom_scenario"):
            run = _run_agent(client, config, project_id, agent_type)
            if run["status"] not in {"completed", "waiting_approval"}:
                raise RuntimeError(f"{agent_type} agent failed: {run}")
            agent_runs.append(run)

    return {
        "project": project,
        "synthetic_job": synthetic_job,
        "catalog_integrations": int(catalog["total"]),
        "qa_distribution": qa_distribution,
        "pattern_normalization": pattern_normalization,
        "distinct_system_target": config.min_distinct_systems,
        "contract_months": config.contract_months,
        "environment_activation_months": {"DEV": 1, "QA": 7, "PRD": 13},
        "scenario_ids": [scenario["id"] for scenario in scenarios],
        "bom_snapshot_ids": [snapshot["id"] for snapshot in snapshots],
        "published_bom_count": len(snapshots),
        "approved_mapping_count": len(approved_mapping_ids),
        "non_billable_mapping_count": len(non_billable_mappings),
        "non_billable_mapping_ids": [
            str(mapping["id"]) for mapping in non_billable_mappings
        ],
        "verified_part_number_count": len(verified_part_numbers),
        "covered_mapping_count": len(planned_mapping_ids),
        "covered_part_number_count": len(verified_part_numbers & bom_part_numbers),
        "agent_runs": [
            {
                "id": run["id"],
                "type": run["agent_type"],
                "status": run["status"],
            }
            for run in agent_runs
        ],
        "urls": {
            "dashboard": f"http://localhost:3000/projects/{project_id}",
            "catalog": f"http://localhost:3000/projects/{project_id}/catalog",
            "map": f"http://localhost:3000/projects/{project_id}/map",
            "bom": f"http://localhost:3000/projects/{project_id}/bom",
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000/api/v1",
        help="Public API base URL.",
    )
    parser.add_argument(
        "--project-name",
        default="DEMO - Aurora Retail Integration Blueprint 2027-2029",
    )
    parser.add_argument(
        "--customer-name",
        default="Aurora Retail Nexus, S.A.P.I. de C.V. (Fictitious)",
    )
    parser.add_argument("--seed", type=int, default=20260725)
    parser.add_argument("--target-catalog-size", type=int, default=350)
    parser.add_argument("--import-target", type=int, default=300)
    parser.add_argument("--manual-target", type=int, default=50)
    parser.add_argument("--excluded-import-target", type=int, default=12)
    parser.add_argument("--min-distinct-systems", type=int, default=72)
    parser.add_argument("--contract-months", type=int, default=36)
    parser.add_argument("--start-date", default="2027-01-01")
    parser.add_argument("--region", default="us-chicago-1")
    parser.add_argument("--actor-id", default="ideal-demo-builder")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=1200.0)
    parser.add_argument("--job-id")
    parser.add_argument("--project-id")
    parser.add_argument("--skip-agents", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.import_target + args.manual_target != args.target_catalog_size:
        raise SystemExit("Import target plus manual target must equal catalog size")
    if args.contract_months != 36:
        raise SystemExit("The ideal demo contract is governed at exactly 36 months")
    date.fromisoformat(args.start_date)
    config = DemoConfig(
        api_url=args.api_url,
        project_name=args.project_name,
        customer_name=args.customer_name,
        seed=args.seed,
        target_catalog_size=args.target_catalog_size,
        import_target=args.import_target,
        manual_target=args.manual_target,
        excluded_import_target=args.excluded_import_target,
        min_distinct_systems=args.min_distinct_systems,
        contract_months=args.contract_months,
        start_date=args.start_date,
        region=args.region,
        actor_id=args.actor_id,
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.timeout_seconds,
    )
    result = create_demo(
        config,
        job_id=args.job_id,
        project_id=args.project_id,
        run_agents=not args.skip_agents,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
