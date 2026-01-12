from __future__ import annotations

import pytest

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
    _, cfg = load_run_config(argv=["run"])
    assert cfg.query == "query all resources where lifecycleState = 'ACTIVE'"


def test_cli_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("OCI_INV_QUERY", "query all resources where lifecycleState = 'ACTIVE'")
    # CLI should win over env
    _, cfg = load_run_config(argv=["run", "--query", "query all resources"])
    assert cfg.query == "query all resources"


def test_diff_command_requires_prev_and_curr(monkeypatch) -> None:
    # We don't execute cmd_diff here; just ensure we can parse args for diff subcommand
    command, cfg = load_run_config(argv=["diff", "--prev", "prev.jsonl", "--curr", "curr.jsonl"])
    assert command == "diff"
    assert str(cfg.prev) == "prev.jsonl"
    assert str(cfg.curr) == "curr.jsonl"


def test_config_file_used_when_env_and_cli_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OCI_INV_QUERY", raising=False)
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("query: from-config\n", encoding="utf-8")

    _, cfg = load_run_config(argv=["run", "--config", str(cfg_path)])
    assert cfg.query == "from-config"


def test_env_overrides_config_file(monkeypatch, tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("query: from-config\n", encoding="utf-8")
    monkeypatch.setenv("OCI_INV_QUERY", "from-env")

    _, cfg = load_run_config(argv=["run", "--config", str(cfg_path)])
    assert cfg.query == "from-env"


def test_cli_overrides_env_and_config(monkeypatch, tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("query: from-config\nworkers_region: 7\nparquet: true\n", encoding="utf-8")
    monkeypatch.setenv("OCI_INV_QUERY", "from-env")
    monkeypatch.setenv("OCI_INV_WORKERS_REGION", "9")

    _, cfg = load_run_config(
        argv=[
            "run",
            "--config",
            str(cfg_path),
            "--query",
            "from-cli",
            "--workers-region",
            "11",
        ]
    )
    assert cfg.query == "from-cli"
    assert cfg.workers_region == 11
    assert cfg.parquet is True


def test_env_boolean_overrides_config_boolean(monkeypatch, tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("parquet: true\n", encoding="utf-8")
    monkeypatch.setenv("OCI_INV_PARQUET", "0")

    _, cfg = load_run_config(argv=["run", "--config", str(cfg_path)])
    assert cfg.parquet is False


def test_regions_from_cli() -> None:
    _, cfg = load_run_config(argv=["run", "--regions", "mx-queretaro-1,us-ashburn-1"])
    assert cfg.regions == ["mx-queretaro-1", "us-ashburn-1"]


def test_regions_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OCI_INV_REGIONS", "mx-queretaro-1")
    _, cfg = load_run_config(argv=["run"])
    assert cfg.regions == ["mx-queretaro-1"]


def test_cli_can_disable_config_boolean(tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("parquet: true\n", encoding="utf-8")

    _, cfg = load_run_config(argv=["run", "--config", str(cfg_path), "--no-parquet"])
    assert cfg.parquet is False


def test_cli_can_disable_diagrams() -> None:
    _, cfg = load_run_config(argv=["run", "--no-diagrams"])
    assert cfg.diagrams is False


def test_unknown_config_keys_warn(tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("query: from-config\nunknown_key: value\n", encoding="utf-8")

    with pytest.warns(UserWarning):
        _, cfg = load_run_config(argv=["run", "--config", str(cfg_path)])
    assert cfg.query == "from-config"


def test_invalid_config_type_raises(tmp_path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("workers_region: not-a-number\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_run_config(argv=["run", "--config", str(cfg_path)])


def test_genai_chat_parses_message_args() -> None:
    command, cfg = load_run_config(
        argv=[
            "genai-chat",
            "--api-format",
            "GENERIC",
            "--message",
            "hello",
            "--max-tokens",
            "42",
            "--temperature",
            "0.3",
        ]
    )
    assert command == "genai-chat"
    assert cfg.genai_api_format == "GENERIC"
    assert cfg.genai_message == "hello"
    assert cfg.genai_max_tokens == 42
    assert abs((cfg.genai_temperature or 0.0) - 0.3) < 1e-9


def test_cost_osub_subscription_id_parsed() -> None:
    _, cfg = load_run_config(argv=["run", "--osub-subscription-id", "sub123"])
    assert cfg.osub_subscription_id == "sub123"
