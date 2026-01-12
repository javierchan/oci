from __future__ import annotations

from pathlib import Path

from oci_inventory.config import RunConfig
from oci_inventory.report import render_cost_report_md, render_run_report_md


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
