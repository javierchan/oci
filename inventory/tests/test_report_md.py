from __future__ import annotations

import json
from pathlib import Path

from oci_inventory.config import RunConfig
from oci_inventory.report import (
    render_cost_report_md,
    render_run_report_md,
    write_cost_usage_csv,
    write_cost_usage_jsonl,
    write_cost_usage_views,
)


def test_render_run_report_includes_excluded_regions_and_query(tmp_path: Path) -> None:
    cfg = RunConfig(outdir=tmp_path, auth="config", profile="DEFAULT", query="query all resources")

    text = render_run_report_md(
        status="OK",
        cfg_dict={
            "auth": cfg.auth,
            "profile": cfg.profile,
            "tenancy_ocid": cfg.tenancy_ocid,
            "query": cfg.query,
            "outdir": str(cfg.outdir),
            "parquet": cfg.parquet,
            "prev": None,
            "workers_region": cfg.workers_region,
            "workers_enrich": cfg.workers_enrich,
        },
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        subscribed_regions=["mx-queretaro-1", "us-dallas-1"],
        requested_regions=None,
        excluded_regions=[{"region": "us-dallas-1", "reason": "NotAuthenticated"}],
        discovered_records=[],
        metrics={
            "counts_by_enrich_status": {"OK": 0, "ERROR": 0, "NOT_IMPLEMENTED": 0},
        },
    )

    # Narrative intro + At-a-Glance table exist
    assert "This report summarizes the OCI resources" in text
    assert "## At a Glance" in text
    assert "| Metric | Value |" in text

    # Still preserves run metadata (now under Execution Metadata)
    assert "## Execution Metadata" in text
    assert "Excluded regions" in text
    assert "us-dallas-1" in text
    assert "query all resources" in text

    # New architecture-oriented sections exist
    assert "## Network Architecture" in text
    assert "## Workloads & Services" in text


def test_render_run_report_includes_executive_summary_when_provided(tmp_path: Path) -> None:
    cfg = RunConfig(outdir=tmp_path, auth="config", profile="DEFAULT", query="query all resources")

    text = render_run_report_md(
        status="OK",
        cfg_dict={
            "auth": cfg.auth,
            "profile": cfg.profile,
            "tenancy_ocid": cfg.tenancy_ocid,
            "query": cfg.query,
            "outdir": str(cfg.outdir),
            "parquet": cfg.parquet,
            "prev": None,
            "workers_region": cfg.workers_region,
            "workers_enrich": cfg.workers_enrich,
        },
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        executive_summary="- Summary line 1\n- Summary line 2",
        subscribed_regions=["mx-queretaro-1"],
        requested_regions=None,
        excluded_regions=[],
        discovered_records=[],
        metrics=None,
    )

    assert "## Executive Summary" in text
    assert "Summary line 1" in text


def test_render_run_report_includes_complete_inventory_listing(tmp_path: Path) -> None:
    cfg = RunConfig(outdir=tmp_path, auth="config", profile="DEFAULT", query="query all resources")

    discovered = [
        {
            "resourceType": "Bucket",
            "displayName": "my-bucket",
            "compartmentId": "ocid1.compartment.oc1..exampleuniqueID",
            "region": "mx-queretaro-1",
            "lifecycleState": "ACTIVE",
            "enrichStatus": "OK",
        },
        {
            "resourceType": "MediaAsset",
            "displayName": "output/file.m3u8",
            "compartmentId": "ocid1.compartment.oc1..exampleuniqueID",
            "region": "mx-queretaro-1",
            "lifecycleState": "ACTIVE",
            "enrichStatus": "NOT_IMPLEMENTED",
        },
    ]

    text = render_run_report_md(
        status="OK",
        cfg_dict={
            "auth": cfg.auth,
            "profile": cfg.profile,
            "tenancy_ocid": cfg.tenancy_ocid,
            "query": cfg.query,
            "outdir": str(cfg.outdir),
            "parquet": cfg.parquet,
            "prev": None,
            "workers_region": cfg.workers_region,
            "workers_enrich": cfg.workers_enrich,
        },
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        subscribed_regions=["mx-queretaro-1"],
        requested_regions=None,
        excluded_regions=[],
        discovered_records=discovered,
        metrics=None,
    )

    assert "## Inventory Listing (Complete)" in text
    assert "my-bucket" in text
    assert "output/file.m3u8" in text


def test_render_run_report_includes_workload_group_from_tags(tmp_path: Path) -> None:
    cfg = RunConfig(outdir=tmp_path, auth="config", profile="DEFAULT", query="query all resources")

    discovered = [
        {
            "resourceType": "Instance",
            "displayName": "edge-api-01",
            "compartmentId": "ocid1.compartment.oc1..exampleuniqueID",
            "region": "mx-queretaro-1",
            "lifecycleState": "RUNNING",
            "freeformTags": {"app": "EdgeApp"},
            "enrichStatus": "OK",
        },
        {
            "resourceType": "Bucket",
            "displayName": "edge-content",
            "compartmentId": "ocid1.compartment.oc1..exampleuniqueID",
            "region": "mx-queretaro-1",
            "lifecycleState": "ACTIVE",
            "freeformTags": {"app": "EdgeApp"},
            "enrichStatus": "OK",
        },
        {
            "resourceType": "Subnet",
            "displayName": "edge-subnet",
            "compartmentId": "ocid1.compartment.oc1..exampleuniqueID",
            "region": "mx-queretaro-1",
            "lifecycleState": "AVAILABLE",
            "freeformTags": {"app": "EdgeApp"},
            "enrichStatus": "OK",
        },
    ]

    text = render_run_report_md(
        status="OK",
        cfg_dict={
            "auth": cfg.auth,
            "profile": cfg.profile,
            "tenancy_ocid": cfg.tenancy_ocid,
            "query": cfg.query,
            "outdir": str(cfg.outdir),
            "parquet": cfg.parquet,
            "prev": None,
            "workers_region": cfg.workers_region,
            "workers_enrich": cfg.workers_enrich,
        },
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:01:00+00:00",
        subscribed_regions=["mx-queretaro-1"],
        requested_regions=None,
        excluded_regions=[],
        discovered_records=discovered,
        metrics=None,
    )

    assert "## Workloads & Services" in text
    assert "EdgeApp" in text


def test_render_cost_report_includes_required_sections_and_aliases(tmp_path: Path) -> None:
    cfg = RunConfig(outdir=tmp_path, auth="config", profile="DEFAULT", query="query all resources")

    cost_context = {
        "time_start": "2026-02-01T00:00:00+00:00",
        "time_end": "2026-02-15T00:00:00+00:00",
        "currency": "USD",
        "currency_source": "cli",
        "total_cost": 123.456,
        "services": [{"name": f"Service{i}", "amount": i + 1} for i in range(12)],
        "compartments": [{"compartment_id": "ocid1.compartment.oc1..exampleuniqueID", "amount": 42}],
        "regions": [{"name": "us-ashburn-1", "amount": 84}],
        "budgets": [
            {
                "id": "ocid1.budget.oc1..exampleBudget",
                "display_name": "Ops Budget",
                "amount": 100,
                "reset_period": "MONTHLY",
                "lifecycle_state": "ACTIVE",
            }
        ],
        "budget_alert_rule_counts": {"ocid1.budget.oc1..exampleBudget": 2},
        "errors": [],
        "warnings": [],
        "steps": [{"name": "usage_api_total", "status": "OK"}],
        "query_inputs": {"tenant_id": "ocid1.tenancy.oc1..exampleTenancy", "group_by": ["service"]},
        "compartment_names": {"ocid1.compartment.oc1..exampleuniqueID": "Prod"},
    }

    text = render_cost_report_md(
        status="OK",
        cfg_dict={
            "cost_report": True,
            "cost_start": None,
            "cost_end": None,
            "cost_currency": "USD",
            "assessment_target_group": "FinOps Team",
            "assessment_target_scope": ["Cost Management / Allocation"],
            "assessment_lens_weights": ["Knowledge=1", "Process=1", "Metrics=1", "Adoption=1", "Automation=1"],
            "assessment_capabilities": [
                "Cost Management|Allocation|2|2|1|1|1|10|Usage API totals + budgets",
            ],
        },
        cost_context=cost_context,
    )

    assert "# OCI Cost & Usage Assessment" in text
    assert "## Cost by Service" in text
    assert "Top 10; remaining aggregated as Other." in text
    assert "Prod (Compartment-01)" in text
    assert "## Execution Metadata" in text


def test_render_cost_report_embeds_genai_summary(tmp_path: Path) -> None:
    cfg = RunConfig(outdir=tmp_path, auth="config", profile="DEFAULT", query="query all resources")

    cost_context = {
        "time_start": "2026-02-01T00:00:00+00:00",
        "time_end": "2026-02-15T00:00:00+00:00",
        "currency": "USD",
        "currency_source": "cli",
        "total_cost": 12.34,
        "services": [{"name": "ServiceA", "amount": 12.34}],
        "compartments": [{"compartment_id": "ocid1.compartment.oc1..exampleuniqueID", "amount": 12.34}],
        "regions": [{"name": "us-ashburn-1", "amount": 12.34}],
        "budgets": [],
        "budget_alert_rule_counts": {},
        "errors": [],
        "warnings": [],
        "steps": [{"name": "usage_api_total", "status": "OK"}],
        "query_inputs": {"tenant_id": "ocid1.tenancy.oc1..exampleTenancy", "group_by": ["service"]},
        "compartment_names": {"ocid1.compartment.oc1..exampleuniqueID": "Prod"},
    }

    text = render_cost_report_md(
        status="OK",
        cfg_dict={
            "cost_report": True,
            "cost_start": None,
            "cost_end": None,
            "cost_currency": "USD",
            "assessment_target_group": "FinOps Team",
            "assessment_target_scope": ["Cost Management / Allocation"],
            "assessment_lens_weights": ["Knowledge=1", "Process=1", "Metrics=1", "Adoption=1", "Automation=1"],
            "assessment_capabilities": [
                "Cost Management|Allocation|2|2|1|1|1|10|Usage API totals + budgets",
            ],
        },
        cost_context=cost_context,
        executive_summary="Summary line.\n- Bullet one",
    )

    assert "**Executive Summary**" in text
    assert "Summary line." in text
    assert "- Bullet one" in text
    assert "GenAI executive summary embedded after the introduction." in text


def test_write_cost_usage_exports(tmp_path: Path) -> None:
    class FakeTag:
        attribute_map = {"key": "key", "value": "value"}

        def __init__(self, key: str, value: str) -> None:
            self.key = key
            self.value = value

    usage_items = [
        {
            "group_by": "service",
            "group_value": "Compute",
            "time_usage_started": "2026-01-01T00:00:00+00:00",
            "time_usage_ended": "2026-01-02T00:00:00+00:00",
            "service": "Compute",
            "computed_amount": 1.5,
            "currency": "USD",
            "tags": [FakeTag("env", "dev")],
        },
        {
            "group_by": "region",
            "group_value": "us-ashburn-1",
            "time_usage_started": "2026-01-01T00:00:00+00:00",
            "time_usage_ended": "2026-01-02T00:00:00+00:00",
            "region": "us-ashburn-1",
            "computed_amount": 2.0,
            "currency": "USD",
        },
        {
            "group_by": "compartmentId",
            "group_value": "ocid1.compartment.oc1..exampleuniqueID",
            "time_usage_started": "2026-01-01T00:00:00+00:00",
            "time_usage_ended": "2026-01-02T00:00:00+00:00",
            "compartment_id": "ocid1.compartment.oc1..exampleuniqueID",
            "compartment_name": "Prod",
            "compartment_path": "Prod",
            "computed_amount": 3.0,
            "currency": "USD",
        },
    ]

    csv_path = write_cost_usage_csv(outdir=tmp_path, usage_items=usage_items)
    jsonl_path = write_cost_usage_jsonl(outdir=tmp_path, usage_items=usage_items)
    view_paths = write_cost_usage_views(
        outdir=tmp_path,
        usage_items=usage_items,
        compartment_group_by="compartmentId",
    )

    assert csv_path is not None
    assert jsonl_path is not None
    assert csv_path.is_file()
    assert jsonl_path.is_file()
    assert (tmp_path / "cost_usage_service.csv") in view_paths
    assert (tmp_path / "cost_usage_region.csv") in view_paths
    assert (tmp_path / "cost_usage_compartment.csv") in view_paths

    csv_text = csv_path.read_text(encoding="utf-8")
    assert "group_by" in csv_text
    assert "computed_amount" in csv_text

    json_lines = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    service_line = next(item for item in json_lines if item.get("group_by") == "service")
    assert service_line["computed_amount"] == 1.5
    assert service_line["tags"] == [{"key": "env", "value": "dev"}]
