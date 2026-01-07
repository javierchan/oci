from __future__ import annotations

import os
from pathlib import Path

from oci_inventory.config import DEFAULT_QUERY, RunConfig, load_run_config


def test_default_query_and_workers_from_defaults(monkeypatch) -> None:
    # No env, no config file, only "run" command
    command, cfg = load_run_config(argv=["run"])
    assert command == "run"
    assert isinstance(cfg, RunConfig)
    assert cfg.query == DEFAULT_QUERY  # must be "query all resources"
    assert cfg.workers_region > 0
    assert cfg.workers_enrich > 0
    assert cfg.auth == "auto"


def test_env_overrides_query(monkeypatch) -> None:
    monkeypatch.setenv("OCI_INV_QUERY", "query all resources where lifecycleState = 'ACTIVE'")
    command, cfg = load_run_config(argv=["run"])
    assert cfg.query == "query all resources where lifecycleState = 'ACTIVE'"


def test_cli_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("OCI_INV_QUERY", "query all resources where lifecycleState = 'ACTIVE'")
    # CLI should win over env
    command, cfg = load_run_config(argv=["run", "--query", "query all resources"])
    assert cfg.query == "query all resources"


def test_diff_command_requires_prev_and_curr(monkeypatch) -> None:
    # We don't execute cmd_diff here; just ensure we can parse args for diff subcommand
    command, cfg = load_run_config(argv=["diff", "--prev", "prev.jsonl", "--curr", "curr.jsonl"])
    assert command == "diff"
    assert str(cfg.prev) == "prev.jsonl"