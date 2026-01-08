from __future__ import annotations

from pathlib import Path

from oci_inventory.wizard.plan import (
    build_diff_plan,
    build_run_plan,
    build_simple_plan,
)


def test_build_run_plan_contains_expected_flags() -> None:
    plan = build_run_plan(
        auth="config",
        profile="DEFAULT",
        tenancy_ocid=None,
        outdir=Path("out"),
        query="query all resources",
        regions=["mx-queretaro-1"],
        parquet=True,
        genai_summary=True,
        prev=Path("out/prev/inventory.jsonl"),
        workers_region=3,
        workers_enrich=9,
        include_terminated=None,
        json_logs=False,
        log_level="INFO",
    )

    assert plan.argv[0] == "run"
    assert "--auth" in plan.argv
    assert "config" in plan.argv
    assert "--profile" in plan.argv
    assert "DEFAULT" in plan.argv
    assert "--regions" in plan.argv
    assert "mx-queretaro-1" in plan.argv
    assert "--query" in plan.argv
    assert "query all resources" in plan.argv
    assert "--parquet" in plan.argv
    assert "--genai-summary" in plan.argv
    assert "--prev" in plan.argv
    assert "out/prev/inventory.jsonl" in plan.argv
    assert "--workers-region" in plan.argv
    assert "3" in plan.argv
    assert "--workers-enrich" in plan.argv
    assert "9" in plan.argv
    assert "--no-json-logs" in plan.argv


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
