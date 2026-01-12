from __future__ import annotations

from datetime import datetime, timezone

from oci_inventory.auth.providers import AuthContext
from oci_inventory.cli import _collect_cost_report_data, cmd_run
from oci_inventory.config import RunConfig, load_run_config
from oci_inventory.enrich.default import DefaultEnricher
from oci_inventory.normalize.transform import normalize_from_search_summary
import oci_inventory.cli as cli


def test_cli_run_writes_schema_offline(tmp_path, monkeypatch) -> None:
    base_outdir = tmp_path / "out"
    command, cfg = load_run_config(
        argv=[
            "run",
            "--outdir",
            str(base_outdir),
            "--auth",
            "config",
            "--profile",
            "DEFAULT",
            "--regions",
            "test-region",
            "--query",
            "query all resources",
        ]
    )
    assert command == "run"
    assert cfg.outdir.parent == base_outdir
    assert len(cfg.outdir.name) == 16
    assert cfg.outdir.name[8] == "T"
    assert cfg.outdir.name.endswith("Z")

    def fake_resolve_auth(_cfg):
        return AuthContext(
            method="config",
            config_dict={"tenancy": "ocid1.tenancy.oc1..test"},
            signer=None,
            profile="DEFAULT",
            tenancy_ocid="ocid1.tenancy.oc1..test",
        )

    def fake_discover(_ctx, region, _query, *, collected_at=None):
        summaries = [
            {
                "identifier": "ocid1.vcn.oc1..test",
                "resourceType": "Vcn",
                "displayName": "test-vcn",
                "compartmentId": "ocid1.compartment.oc1..test",
            },
            {
                "identifier": "ocid1.subnet.oc1..test",
                "resourceType": "Subnet",
                "displayName": "test-subnet",
                "compartmentId": "ocid1.compartment.oc1..test",
            },
        ]
        records = []
        for summary in summaries:
            rec = normalize_from_search_summary(summary, region=region, collected_at=collected_at)
            rec["searchSummary"] = summary
            records.append(rec)
        return records

    monkeypatch.setattr(cli, "_resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(cli, "get_subscribed_regions", lambda _ctx: ["test-region"])
    monkeypatch.setattr(cli, "discover_in_region", fake_discover)
    monkeypatch.setattr(cli, "get_enricher_for", lambda _rtype: DefaultEnricher())
    monkeypatch.setattr(cli, "write_diagram_projections", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli, "is_mmdc_available", lambda: False)
    monkeypatch.setattr(cli, "validate_mermaid_diagrams_with_mmdc", lambda _outdir: [])

    exit_code = cmd_run(cfg)
    assert exit_code == 0

    validation = cli._validate_outdir_schema(cfg.outdir)
    assert not validation.errors

    assert (cfg.outdir / "inventory.jsonl").is_file()
    assert (cfg.outdir / "relationships.jsonl").is_file()
    assert (cfg.outdir / "graph_nodes.jsonl").is_file()
    assert (cfg.outdir / "graph_edges.jsonl").is_file()
    assert (cfg.outdir / "run_summary.json").is_file()


def test_cli_run_can_skip_diagrams(tmp_path, monkeypatch) -> None:
    base_outdir = tmp_path / "out"
    command, cfg = load_run_config(
        argv=[
            "run",
            "--outdir",
            str(base_outdir),
            "--auth",
            "config",
            "--profile",
            "DEFAULT",
            "--regions",
            "test-region",
            "--query",
            "query all resources",
            "--no-diagrams",
        ]
    )
    assert command == "run"

    def fake_resolve_auth(_cfg):
        return AuthContext(
            method="config",
            config_dict={"tenancy": "ocid1.tenancy.oc1..test"},
            signer=None,
            profile="DEFAULT",
            tenancy_ocid="ocid1.tenancy.oc1..test",
        )

    def fake_discover(_ctx, region, _query, *, collected_at=None):
        summaries = [
            {
                "identifier": "ocid1.vcn.oc1..test",
                "resourceType": "Vcn",
                "displayName": "test-vcn",
                "compartmentId": "ocid1.compartment.oc1..test",
            }
        ]
        records = []
        for summary in summaries:
            rec = normalize_from_search_summary(summary, region=region, collected_at=collected_at)
            rec["searchSummary"] = summary
            records.append(rec)
        return records

    monkeypatch.setattr(cli, "_resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(cli, "get_subscribed_regions", lambda _ctx: ["test-region"])
    monkeypatch.setattr(cli, "discover_in_region", fake_discover)
    monkeypatch.setattr(cli, "get_enricher_for", lambda _rtype: DefaultEnricher())
    monkeypatch.setattr(cli, "is_mmdc_available", lambda: False)
    monkeypatch.setattr(cli, "validate_mermaid_diagrams_with_mmdc", lambda _outdir: [])

    exit_code = cmd_run(cfg)
    assert exit_code == 0

    validation = cli._validate_outdir_schema(cfg.outdir, expect_graph=False)
    assert not validation.errors

    assert (cfg.outdir / "graph_nodes.jsonl").exists() is False
    assert (cfg.outdir / "graph_edges.jsonl").exists() is False


def test_cost_report_skips_usage_api_without_home_region(tmp_path, monkeypatch) -> None:
    cfg = RunConfig(
        outdir=tmp_path,
        auth="config",
        profile="DEFAULT",
        query="query all resources",
        cost_report=True,
    )
    ctx = AuthContext(
        method="config",
        config_dict={"tenancy": "ocid1.tenancy.oc1..test"},
        signer=None,
        profile="DEFAULT",
        tenancy_ocid="ocid1.tenancy.oc1..test",
    )

    monkeypatch.setattr(cli, "get_home_region_name", lambda _ctx: None)

    def _fail_usage_client(*_args, **_kwargs):
        raise AssertionError("Usage API client should not be called without home region")

    monkeypatch.setattr(cli, "get_usage_api_client", _fail_usage_client)
    monkeypatch.setattr(cli, "get_budget_client", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "_list_budgets", lambda *_args, **_kwargs: ([], None))

    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cost_context = _collect_cost_report_data(
        ctx=ctx,
        cfg=cfg,
        subscribed_regions=["us-ashburn-1"],
        requested_regions=None,
        finished_at=finished_at,
    )

    step_status = {s["name"]: s["status"] for s in cost_context.get("steps", [])}
    assert step_status.get("usage_api_total") == "SKIPPED"
    assert any(
        "Unable to resolve tenancy home region" in err for err in cost_context.get("errors", [])
    )


def test_cost_currency_mismatch_does_not_override(tmp_path, monkeypatch) -> None:
    cfg = RunConfig(
        outdir=tmp_path,
        auth="config",
        profile="DEFAULT",
        query="query all resources",
        cost_report=True,
        cost_currency="EUR",
    )
    ctx = AuthContext(
        method="config",
        config_dict={"tenancy": "ocid1.tenancy.oc1..test"},
        signer=None,
        profile="DEFAULT",
        tenancy_ocid="ocid1.tenancy.oc1..test",
    )

    monkeypatch.setattr(cli, "get_home_region_name", lambda _ctx: "us-ashburn-1")
    monkeypatch.setattr(cli, "get_usage_api_client", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "get_budget_client", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "_list_budgets", lambda *_args, **_kwargs: ([], None))

    def _fake_request(_client, _tenancy, _start, _end, *, group_by):
        return ([{"name": group_by or "total", "amount": 10.0}], "USD", None)

    monkeypatch.setattr(cli, "_request_summarized_usages", _fake_request)

    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cost_context = _collect_cost_report_data(
        ctx=ctx,
        cfg=cfg,
        subscribed_regions=["us-ashburn-1"],
        requested_regions=None,
        finished_at=finished_at,
    )

    assert cost_context["currency"] == "USD"
    assert cost_context["currency_source"] == "usage_api"
    assert any("No conversion performed" in warn for warn in cost_context.get("warnings", []))


def test_osub_aggregated_usage_is_collected(tmp_path, monkeypatch) -> None:
    cfg = RunConfig(
        outdir=tmp_path,
        auth="config",
        profile="DEFAULT",
        query="query all resources",
        cost_report=True,
        osub_subscription_id="sub123",
    )
    ctx = AuthContext(
        method="config",
        config_dict={"tenancy": "ocid1.tenancy.oc1..test"},
        signer=None,
        profile="DEFAULT",
        tenancy_ocid="ocid1.tenancy.oc1..test",
    )

    monkeypatch.setattr(cli, "get_home_region_name", lambda _ctx: "us-ashburn-1")
    monkeypatch.setattr(cli, "get_usage_api_client", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "get_budget_client", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "_list_budgets", lambda *_args, **_kwargs: ([], None))
    monkeypatch.setattr(cli, "_request_summarized_usages", lambda *_args, **_kwargs: ([], "USD", None))

    class FakeResponse:
        def __init__(self, data):
            self.data = data

    class FakeOsubClient:
        def __init__(self):
            self.called = False

        def list_computed_usage_aggregateds(self, compartment_id, subscription_id, time_from, time_to, **kwargs):
            self.called = True
            return FakeResponse(
                [
                    {
                        "currencyCode": "USD",
                        "aggregatedComputedUsages": [
                            {"cost": "10.0"},
                            {"cost": "2.5"},
                        ],
                    }
                ]
            )

    osub_client = FakeOsubClient()
    monkeypatch.setattr(cli, "get_osub_usage_client", lambda *_args, **_kwargs: osub_client)

    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cost_context = _collect_cost_report_data(
        ctx=ctx,
        cfg=cfg,
        subscribed_regions=["us-ashburn-1"],
        requested_regions=None,
        finished_at=finished_at,
    )

    assert osub_client.called is True
    assert cost_context.get("osub_usage", {}).get("computed_amount") == 12.5
