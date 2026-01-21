from __future__ import annotations

from datetime import datetime, timezone
import types

from oci_inventory.auth.providers import AuthContext
from oci_inventory.cli import (
    _collect_cost_report_data,
    _extract_group_value,
    _extract_usage_amount,
    _extract_usage_currency,
    _request_summarized_usages,
    _usage_item_to_dict,
    cmd_run,
)
from oci_inventory.config import RunConfig, load_run_config
from oci_inventory.enrich.default import DefaultEnricher
from oci_inventory.normalize.schema import resolve_output_paths
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
        for summary in summaries:
            rec = normalize_from_search_summary(summary, region=region, collected_at=collected_at)
            rec["searchSummary"] = summary
            yield rec

    monkeypatch.setattr(cli, "_resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(cli, "get_subscribed_regions", lambda _ctx: ["test-region"])
    monkeypatch.setattr(cli, "iter_discover_in_region", fake_discover)
    monkeypatch.setattr(cli, "get_enricher_for", lambda _rtype: DefaultEnricher())
    monkeypatch.setattr(cli, "write_diagram_projections", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(cli, "is_mmdc_available", lambda: False)
    monkeypatch.setattr(cli, "validate_mermaid_diagrams_with_mmdc", lambda _outdir: [])

    exit_code = cmd_run(cfg)
    assert exit_code == 0

    validation = cli._validate_outdir_schema(cfg.outdir)
    assert not validation.errors

    paths = resolve_output_paths(cfg.outdir)
    assert paths.inventory_jsonl.is_file()
    assert paths.relationships_jsonl.is_file()
    assert paths.graph_nodes_jsonl.is_file()
    assert paths.graph_edges_jsonl.is_file()
    assert paths.run_summary_json.is_file()


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
            "--no-architecture-diagrams",
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
        for summary in summaries:
            rec = normalize_from_search_summary(summary, region=region, collected_at=collected_at)
            rec["searchSummary"] = summary
            yield rec

    monkeypatch.setattr(cli, "_resolve_auth", fake_resolve_auth)
    monkeypatch.setattr(cli, "get_subscribed_regions", lambda _ctx: ["test-region"])
    monkeypatch.setattr(cli, "iter_discover_in_region", fake_discover)
    monkeypatch.setattr(cli, "get_enricher_for", lambda _rtype: DefaultEnricher())
    monkeypatch.setattr(cli, "is_mmdc_available", lambda: False)
    monkeypatch.setattr(cli, "validate_mermaid_diagrams_with_mmdc", lambda _outdir: [])

    exit_code = cmd_run(cfg)
    assert exit_code == 0

    validation = cli._validate_outdir_schema(cfg.outdir, expect_graph=False)
    assert not validation.errors

    paths = resolve_output_paths(cfg.outdir)
    assert paths.graph_nodes_jsonl.exists() is False
    assert paths.graph_edges_jsonl.exists() is False


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

    def _fake_request(_client, _tenancy, _start, _end, *, group_by, items_out=None):
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
    assert cost_context["query_inputs"]["granularity"] == "DAILY"
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


def test_usage_item_hyphenated_keys_are_supported() -> None:
    data = {
        "computed-amount": "12.5",
        "currency": "USD",
        "service": "Compute",
        "compartment-id": "ocid1.compartment.oc1..test",
        "region": "us-ashburn-1",
    }

    assert _extract_usage_amount(data) == 12.5
    assert _extract_usage_currency(data) == "USD"
    assert _extract_group_value(data, "service") == "Compute"
    assert _extract_group_value(data, "compartmentId") == "ocid1.compartment.oc1..test"
    assert _extract_group_value(data, "region") == "us-ashburn-1"


def test_usage_item_attribute_map_object() -> None:
    class FakeUsageItem:
        attribute_map = {
            "service": "service",
            "computed_amount": "computedAmount",
            "currency": "currency",
        }

        def __init__(self) -> None:
            self.service = "Compute"
            self.computed_amount = 7.25
            self.currency = "USD"

    data = _usage_item_to_dict(FakeUsageItem())
    assert data["service"] == "Compute"
    assert data["computed_amount"] == 7.25
    assert data["currency"] == "USD"


def test_request_summarized_usages_handles_list_data(monkeypatch) -> None:
    class FakeDetails:
        def __init__(self, **_kwargs):
            pass

    fake_oci = types.SimpleNamespace(
        usage_api=types.SimpleNamespace(models=types.SimpleNamespace(RequestSummarizedUsagesDetails=FakeDetails))
    )
    monkeypatch.setitem(__import__("sys").modules, "oci", fake_oci)

    class FakeResponse:
        def __init__(self, data):
            self.data = data
            self.headers = {}

    class FakeClient:
        def request_summarized_usages(self, _details, page=None):
            return FakeResponse(
                [
                    {
                        "computed-amount": "3.5",
                        "currency": "USD",
                        "service": "Compute",
                    }
                ]
            )

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 2, tzinfo=timezone.utc)
    items_out: list[dict[str, object]] = []
    rows, currency, err = _request_summarized_usages(
        FakeClient(),
        "ocid1.tenancy.oc1..test",
        start,
        end,
        group_by="service",
        items_out=items_out,
    )

    assert err is None
    assert currency == "USD"
    assert rows == [{"name": "Compute", "amount": 3.5}]
    assert len(items_out) == 1
    item = items_out[0]
    assert item["service"] == "Compute"
    assert item["computed_amount"] == 3.5
    assert item["currency"] == "USD"
    assert item["group_by"] == "service"
    assert item["group_value"] == "Compute"


def test_cost_report_uses_compartment_group_by(monkeypatch, tmp_path) -> None:
    cfg = RunConfig(
        outdir=tmp_path,
        auth="config",
        profile="DEFAULT",
        query="query all resources",
        cost_report=True,
        cost_compartment_group_by="compartmentName",
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

    seen_group_by: list[str] = []

    def _fake_request(_client, _tenancy, _start, _end, *, group_by, items_out=None):
        if group_by:
            seen_group_by.append(group_by)
        return ([], "USD", None)

    monkeypatch.setattr(cli, "_request_summarized_usages", _fake_request)

    finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cost_context = _collect_cost_report_data(
        ctx=ctx,
        cfg=cfg,
        subscribed_regions=["us-ashburn-1"],
        requested_regions=None,
        finished_at=finished_at,
    )

    assert "compartmentName" in seen_group_by
    assert cost_context["query_inputs"]["group_by"][1] == "compartmentName"


def test_merge_sorted_inventory_chunks(tmp_path) -> None:
    chunk1 = tmp_path / "chunk1.jsonl"
    chunk2 = tmp_path / "chunk2.jsonl"
    chunk1.write_text(
        "\n".join(
            [
                '{"ocid":"ocid1.a","resourceType":"A"}',
                '{"ocid":"ocid1.c","resourceType":"A"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    chunk2.write_text(
        "\n".join(
            [
                '{"ocid":"ocid1.b","resourceType":"A"}',
                '{"ocid":"ocid1.d","resourceType":"A"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    merged = list(cli._merge_sorted_inventory_chunks([chunk1, chunk2]))
    ocids = [rec["ocid"] for rec in merged]
    assert ocids == ["ocid1.a", "ocid1.b", "ocid1.c", "ocid1.d"]


def test_merge_sorted_relationship_chunks(tmp_path) -> None:
    chunk1 = tmp_path / "rels1.jsonl"
    chunk2 = tmp_path / "rels2.jsonl"
    chunk1.write_text(
        "\n".join(
            [
                '{"source_ocid":"a","relation_type":"X","target_ocid":"1"}',
                '{"source_ocid":"b","relation_type":"X","target_ocid":"1"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    chunk2.write_text(
        "\n".join(
            [
                '{"source_ocid":"a","relation_type":"X","target_ocid":"1"}',
                '{"source_ocid":"c","relation_type":"Y","target_ocid":"2"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    merged = list(cli._merge_sorted_relationship_chunks([chunk1, chunk2]))
    keys = [(r["source_ocid"], r["relation_type"], r["target_ocid"]) for r in merged]
    assert keys == [("a", "X", "1"), ("b", "X", "1"), ("c", "Y", "2")]


def test_validate_outdir_schema_sampled_warns(tmp_path) -> None:
    paths = resolve_output_paths(tmp_path)
    inv = paths.inventory_jsonl
    rels = paths.relationships_jsonl
    summary = paths.run_summary_json

    inv.parent.mkdir(parents=True, exist_ok=True)
    rels.parent.mkdir(parents=True, exist_ok=True)

    inv.write_text(
        "\n".join(
            [
                '{"ocid":"ocid1.a","resourceType":"A","region":"r1","collectedAt":"2026-01-01T00:00:00Z","enrichStatus":"OK","details":{},"relationships":[]}',
                '{"ocid":"ocid1.b","resourceType":"B","region":"r1","collectedAt":"2026-01-01T00:00:00Z","enrichStatus":"OK","details":{},"relationships":[]}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rels.write_text("", encoding="utf-8")
    summary.write_text(
        '{"schema_version":"1","total_discovered":2,"enriched_ok":2,"not_implemented":0,"errors":0,'
        '"counts_by_resource_type":{},"counts_by_enrich_status":{},"counts_by_resource_type_and_status":{}}',
        encoding="utf-8",
    )

    result = cli._validate_outdir_schema(tmp_path, mode="sampled", sample_limit=1, expect_graph=False)
    assert result.errors == []
    assert any("sampled first 1 records" in w for w in result.warnings)


def test_parallel_map_ordered_iter_batches() -> None:
    from oci_inventory.util.concurrency import parallel_map_ordered_iter

    items = [3, 1, 2, 4]
    out = list(parallel_map_ordered_iter(lambda x: x * 2, items, max_workers=2, batch_size=2))
    assert out == [6, 2, 4, 8]
