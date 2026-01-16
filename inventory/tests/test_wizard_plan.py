from __future__ import annotations

from pathlib import Path

from oci_inventory.wizard.plan import (
    build_coverage_plan,
    build_diff_plan,
    build_run_plan,
    build_simple_plan,
)


def test_build_run_plan_contains_expected_flags() -> None:
    plan = build_run_plan(
        auth="config",
        profile="DEFAULT",
        tenancy_ocid=None,
        config_path=Path("config/workers.yaml"),
        outdir=Path("out"),
        query="query all resources",
        regions=["mx-queretaro-1"],
        genai_summary=True,
        prev=Path("out/prev/inventory.jsonl"),
        workers_region=3,
        workers_enrich=9,
        workers_cost=4,
        workers_export=2,
        client_connection_pool_size=16,
        include_terminated=True,
        validate_diagrams=True,
        diagrams=False,
        schema_validation="sampled",
        schema_sample_records=2500,
        diagram_depth=2,
        diagram_max_networks=5,
        diagram_max_workloads=10,
        cost_report=True,
        cost_start="2025-01-01T00:00:00Z",
        cost_end="2025-01-31T23:59:59Z",
        cost_currency="USD",
        cost_compartment_group_by="compartmentPath",
        cost_group_by=["service", "region", "compartmentId"],
        osub_subscription_id="sub123",
        assessment_target_group="engineering",
        assessment_target_scope=["team:inventory", "org:oci"],
        assessment_lens_weight=["Knowledge=1", "Process=2"],
        assessment_capability=["domain|capability|1|1|1|1|1|target|evidence"],
        json_logs=False,
        log_level="INFO",
    )

    assert plan.argv[0] == "run"
    assert "--auth" in plan.argv
    assert "config" in plan.argv
    assert "--config" in plan.argv
    assert "config/workers.yaml" in plan.argv
    assert "--profile" in plan.argv
    assert "DEFAULT" in plan.argv
    assert "--regions" in plan.argv
    assert "mx-queretaro-1" in plan.argv
    assert "--query" in plan.argv
    assert "query all resources" in plan.argv
    assert "--genai-summary" in plan.argv
    assert "--prev" in plan.argv
    assert "out/prev/inventory.jsonl" in plan.argv
    assert "--workers-region" in plan.argv
    assert "3" in plan.argv
    assert "--workers-enrich" in plan.argv
    assert "9" in plan.argv
    assert "--workers-cost" in plan.argv
    assert "4" in plan.argv
    assert "--workers-export" in plan.argv
    assert "2" in plan.argv
    assert "--client-connection-pool-size" in plan.argv
    assert "16" in plan.argv
    assert "--include-terminated" in plan.argv
    assert "--no-json-logs" in plan.argv
    assert "--validate-diagrams" in plan.argv
    assert "--no-diagrams" in plan.argv
    assert "--validate-schema" in plan.argv
    assert "sampled" in plan.argv
    assert "--validate-schema-sample" in plan.argv
    assert "2500" in plan.argv
    assert "--diagram-depth" in plan.argv
    assert "2" in plan.argv
    assert "--diagram-max-networks" in plan.argv
    assert "5" in plan.argv
    assert "--diagram-max-workloads" in plan.argv
    assert "10" in plan.argv
    assert "--cost-report" in plan.argv
    assert "--cost-start" in plan.argv
    assert "2025-01-01T00:00:00Z" in plan.argv
    assert "--cost-end" in plan.argv
    assert "2025-01-31T23:59:59Z" in plan.argv
    assert "--cost-currency" in plan.argv
    assert "USD" in plan.argv
    assert "--cost-compartment-group-by" in plan.argv
    assert "compartmentPath" in plan.argv
    assert "--cost-group-by" in plan.argv
    assert "service,region,compartmentId" in plan.argv
    assert "--osub-subscription-id" in plan.argv
    assert "sub123" in plan.argv
    assert "--assessment-target-group" in plan.argv
    assert "engineering" in plan.argv
    assert "--assessment-target-scope" in plan.argv
    assert "team:inventory" in plan.argv
    assert "org:oci" in plan.argv
    assert "--assessment-lens-weight" in plan.argv
    assert "Knowledge=1" in plan.argv
    assert "Process=2" in plan.argv
    assert "--assessment-capability" in plan.argv
    assert "domain|capability|1|1|1|1|1|target|evidence" in plan.argv


def test_build_diff_plan_has_paths_and_outdir() -> None:
    plan = build_diff_plan(
        auth="auto",
        profile=None,
        tenancy_ocid=None,
        prev=Path("a.jsonl"),
        curr=Path("b.jsonl"),
        outdir=Path("out/diff"),
        json_logs=None,
        log_level=None,
    )
    assert plan.argv[0] == "diff"
    assert "--prev" in plan.argv
    assert "a.jsonl" in plan.argv
    assert "--curr" in plan.argv
    assert "b.jsonl" in plan.argv
    assert "--outdir" in plan.argv
    assert "out/diff" in plan.argv


def test_build_simple_plan_rejects_unknown_subcommand() -> None:
    try:
        build_simple_plan(
            subcommand="nope",
            auth="auto",
            profile=None,
            tenancy_ocid=None,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")


def test_build_coverage_plan() -> None:
    plan = build_coverage_plan(inventory=Path("out/run/inventory.jsonl"), top=5)
    assert plan.argv[0] == "enrich-coverage"
    assert "--inventory" in plan.argv
    assert "out/run/inventory.jsonl" in plan.argv
    assert "--top" in plan.argv
    assert "5" in plan.argv


def test_build_simple_plan_list_genai_models() -> None:
    plan = build_simple_plan(
        subcommand="list-genai-models",
        auth="auto",
        profile=None,
        tenancy_ocid=None,
        json_logs=None,
        log_level=None,
    )
    assert plan.argv[0] == "list-genai-models"
    assert "--auth" in plan.argv

