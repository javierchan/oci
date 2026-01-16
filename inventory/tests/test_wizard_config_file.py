from __future__ import annotations

import json
from pathlib import Path

from oci_inventory.wizard.config_file import load_wizard_plan_from_file


def test_load_wizard_plan_from_yaml(tmp_path: Path) -> None:
    p = tmp_path / "plan.yaml"
    p.write_text(
        """
mode: run
auth: config
profile: DEFAULT
config: config/workers.yaml
outdir: out
regions: [mx-queretaro-1]
query: "query all resources"
genai_summary: true
validate_diagrams: true
diagrams: false
schema_validation: sampled
schema_sample_records: 2000
diagram_depth: 2
cost_report: true
cost_start: "2025-01-01T00:00:00Z"
cost_end: "2025-01-31T23:59:59Z"
cost_currency: "USD"
cost_compartment_group_by: compartmentPath
cost_group_by: [service, region, compartmentId]
osub_subscription_id: "sub123"
assessment_target_group: "engineering"
assessment_target_scope: [team:inventory, org:oci]
assessment_lens_weight: [Knowledge=1, Process=2]
assessment_capability:
  - "domain|capability|1|1|1|1|1|target|evidence"
workers_region: 6
workers_enrich: 24
workers_cost: 3
workers_export: 2
client_connection_pool_size: 12
""".lstrip(),
        encoding="utf-8",
    )

    plan = load_wizard_plan_from_file(p)
    assert plan.argv[0] == "run"
    assert "--auth" in plan.argv and "config" in plan.argv
    assert "--profile" in plan.argv and "DEFAULT" in plan.argv
    assert "--config" in plan.argv and "config/workers.yaml" in plan.argv
    assert "--outdir" in plan.argv and "out" in plan.argv
    assert "--regions" in plan.argv and "mx-queretaro-1" in plan.argv
    assert "--query" in plan.argv and "query all resources" in plan.argv
    assert "--genai-summary" in plan.argv
    assert "--validate-diagrams" in plan.argv
    assert "--no-diagrams" in plan.argv
    assert "--validate-schema" in plan.argv
    assert "sampled" in plan.argv
    assert "--validate-schema-sample" in plan.argv
    assert "2000" in plan.argv
    assert "--diagram-depth" in plan.argv
    assert "2" in plan.argv
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
    assert "--workers-cost" in plan.argv
    assert "3" in plan.argv
    assert "--workers-export" in plan.argv
    assert "2" in plan.argv
    assert "--client-connection-pool-size" in plan.argv
    assert "12" in plan.argv


def test_load_wizard_plan_from_json(tmp_path: Path) -> None:
    p = tmp_path / "plan.json"
    p.write_text(
        json.dumps(
            {
                "mode": "validate-auth",
                "auth": "auto",
                "log_level": "INFO",
                "json_logs": False,
            }
        ),
        encoding="utf-8",
    )

    plan = load_wizard_plan_from_file(p)
    assert plan.argv[0] == "validate-auth"
    assert "--auth" in plan.argv and "auto" in plan.argv


def test_load_wizard_plan_coverage(tmp_path: Path) -> None:
    p = tmp_path / "plan.yaml"
    p.write_text(
        """
mode: enrich-coverage
auth: auto
inventory: out/latest/inventory.jsonl
top: 7
""".lstrip(),
        encoding="utf-8",
    )

    plan = load_wizard_plan_from_file(p)
    assert plan.argv[0] == "enrich-coverage"
    assert "--inventory" in plan.argv and "out/latest/inventory.jsonl" in plan.argv
    assert "--top" in plan.argv and "7" in plan.argv


def test_load_wizard_plan_list_genai_models(tmp_path: Path) -> None:
    p = tmp_path / "plan.json"
    p.write_text(
        json.dumps(
            {
                "mode": "list-genai-models",
                "auth": "config",
                "profile": "DEFAULT",
            }
        ),
        encoding="utf-8",
    )
    plan = load_wizard_plan_from_file(p)
    assert plan.argv[0] == "list-genai-models"
    assert "--auth" in plan.argv
