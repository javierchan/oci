from __future__ import annotations

import io

from oci_inventory.config import load_run_config


def test_load_run_config_accepts_list_genai_models() -> None:
    command, _cfg = load_run_config(argv=["list-genai-models"])
    assert command == "list-genai-models"


def test_endpoint_region_parsing_for_genai() -> None:
    from oci_inventory.genai.list_models import _endpoint_region

    assert (
        _endpoint_region("https://inference.generativeai.us-chicago-1.oci.oraclecloud.com")
        == "us-chicago-1"
    )
    assert _endpoint_region("https://example.com") is None


def test_cmd_list_genai_models_outputs_csv(monkeypatch) -> None:
    # Import inside test so we can monkeypatch module attributes cleanly.
    from oci_inventory import cli
    from oci_inventory.genai.config import GenAIConfig
    import oci_inventory.genai.config as genai_config
    import oci_inventory.genai.list_models as genai_list_models

    # Fake GenAI config loader
    monkeypatch.setattr(
        genai_config,
        "try_load_genai_config",
        lambda _path=None: GenAIConfig(
            oci_profile="DEFAULT",
            compartment_id="ocid1.compartment.oc1..example",
            endpoint="https://inference.generativeai.us-chicago-1.oci.oraclecloud.com",
            base_model_id="ocid1.generativeaimodel.oc1..example",
            vision_model_id=None,
        ),
    )

    # Fake lister + writer
    fake_rows = [
        {
            "id": "ocid1.generativeaimodel.oc1..bbb",
            "display_name": "B Model",
            "vendor": "ExampleVendor",
            "version": "1",
            "type": "BASE",
            "lifecycle_state": "ACTIVE",
            "capabilities": ["CHAT"],
        },
        {
            "id": "ocid1.generativeaimodel.oc1..aaa",
            "display_name": "A Model",
            "vendor": "ExampleVendor",
            "version": "2",
            "type": "BASE",
            "lifecycle_state": "ACTIVE",
            "capabilities": ["TEXT_GENERATION", "CHAT"],
        },
    ]

    monkeypatch.setattr(genai_list_models, "list_genai_models", lambda *, genai_cfg: fake_rows)

    # Capture stdout by swapping sys.stdout for this call.
    buf = io.StringIO()
    monkeypatch.setattr(cli.sys, "stdout", buf)

    # Build a cfg (unused by command) and run.
    _command, cfg = load_run_config(argv=["list-genai-models"])
    rc = cli.cmd_list_genai_models(cfg)
    assert rc == 0

    out = buf.getvalue().strip().splitlines()
    assert out[0] == "id,display_name,vendor,version,type,lifecycle_state,capabilities"
    # We don't enforce ordering here because ordering is done inside list_genai_models;
    # this test focuses on CSV formatting and that the command prints something.
    assert any("A Model" in line for line in out[1:])
    assert any("B Model" in line for line in out[1:])


def test_cmd_list_genai_models_skips_when_missing_config(monkeypatch) -> None:
    from oci_inventory import cli
    import oci_inventory.genai.config as genai_config

    monkeypatch.setattr(genai_config, "try_load_genai_config", lambda _path=None: None)
    buf = io.StringIO()
    monkeypatch.setattr(cli.sys, "stdout", buf)

    _command, cfg = load_run_config(argv=["list-genai-models"])
    rc = cli.cmd_list_genai_models(cfg)
    assert rc == 0
    assert "SKIP: GenAI config not found or invalid" in buf.getvalue()
