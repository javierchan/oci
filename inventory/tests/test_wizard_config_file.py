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
outdir: out
regions: [mx-queretaro-1]
query: "query all resources"
parquet: false
genai_summary: true
workers_region: 6
workers_enrich: 24
""".lstrip(),
        encoding="utf-8",
    )

    plan = load_wizard_plan_from_file(p)
    assert plan.argv[0] == "run"
    assert "--auth" in plan.argv and "config" in plan.argv
    assert "--profile" in plan.argv and "DEFAULT" in plan.argv
    assert "--outdir" in plan.argv and "out" in plan.argv
    assert "--regions" in plan.argv and "mx-queretaro-1" in plan.argv
    assert "--query" in plan.argv and "query all resources" in plan.argv
    assert "--no-parquet" in plan.argv
    assert "--genai-summary" in plan.argv


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
