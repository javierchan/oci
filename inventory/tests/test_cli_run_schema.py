from __future__ import annotations

from oci_inventory.auth.providers import AuthContext
from oci_inventory.cli import cmd_run
from oci_inventory.config import load_run_config
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
