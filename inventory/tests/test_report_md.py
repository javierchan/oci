from __future__ import annotations

from pathlib import Path

from oci_inventory.config import RunConfig
from oci_inventory.report import render_run_report_md


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
