from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shlex import quote
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class WizardPlan:
    """A fully-resolved execution plan.

    `argv` is intended to be passed to `oci_inventory.config.load_run_config(argv=...)`.
    """

    argv: List[str]

    def as_command_line(self, executable: str = "oci-inv") -> str:
        return format_command([executable, *self.argv])


def format_command(args: Iterable[str]) -> str:
    return " ".join(quote(str(a)) for a in args)


def _maybe_add(argv: List[str], flag: str, value: Optional[str]) -> None:
    if value is None:
        return
    v = str(value).strip()
    if not v:
        return
    argv.extend([flag, v])


def build_common_argv(
    *,
    auth: str,
    profile: Optional[str] = None,
    tenancy_ocid: Optional[str] = None,
    log_level: Optional[str] = None,
    json_logs: Optional[bool] = None,
    config_path: Optional[Path] = None,
    client_connection_pool_size: Optional[int] = None,
) -> List[str]:
    argv: List[str] = []
    _maybe_add(argv, "--config", str(config_path) if config_path else None)
    argv.extend(["--auth", auth])
    _maybe_add(argv, "--profile", profile)
    _maybe_add(argv, "--tenancy", tenancy_ocid)
    _maybe_add(argv, "--log-level", log_level)
    _maybe_add(
        argv,
        "--client-connection-pool-size",
        str(client_connection_pool_size) if client_connection_pool_size is not None else None,
    )

    if json_logs is True:
        argv.append("--json-logs")
    elif json_logs is False:
        argv.append("--no-json-logs")

    return argv


def build_run_plan(
    *,
    auth: str,
    profile: Optional[str],
    tenancy_ocid: Optional[str],
    config_path: Optional[Path],
    outdir: Path,
    query: str,
    regions: Optional[List[str]] = None,
    genai_summary: Optional[bool] = None,
    prev: Optional[Path] = None,
    workers_region: Optional[int] = None,
    workers_enrich: Optional[int] = None,
    workers_cost: Optional[int] = None,
    workers_export: Optional[int] = None,
    client_connection_pool_size: Optional[int] = None,
    include_terminated: Optional[bool] = None,
    validate_diagrams: Optional[bool] = None,
    diagrams: Optional[bool] = None,
    schema_validation: Optional[str] = None,
    schema_sample_records: Optional[int] = None,
    diagram_depth: Optional[int] = None,
    cost_report: Optional[bool] = None,
    cost_start: Optional[str] = None,
    cost_end: Optional[str] = None,
    cost_currency: Optional[str] = None,
    cost_compartment_group_by: Optional[str] = None,
    cost_group_by: Optional[List[str]] = None,
    osub_subscription_id: Optional[str] = None,
    assessment_target_group: Optional[str] = None,
    assessment_target_scope: Optional[List[str]] = None,
    assessment_lens_weight: Optional[List[str]] = None,
    assessment_capability: Optional[List[str]] = None,
    json_logs: Optional[bool] = None,
    log_level: Optional[str] = None,
) -> WizardPlan:
    argv: List[str] = ["run"]
    argv.extend(
        build_common_argv(
            auth=auth,
            profile=profile,
            tenancy_ocid=tenancy_ocid,
            log_level=log_level,
            json_logs=json_logs,
            config_path=config_path,
            client_connection_pool_size=client_connection_pool_size,
        )
    )

    argv.extend(["--outdir", str(outdir)])
    argv.extend(["--query", query])

    if regions:
        argv.extend(["--regions", ",".join(regions)])

    if genai_summary is True:
        argv.append("--genai-summary")
    elif genai_summary is False:
        argv.append("--no-genai-summary")

    if prev:
        argv.extend(["--prev", str(prev)])

    if workers_region is not None:
        argv.extend(["--workers-region", str(int(workers_region))])

    if workers_enrich is not None:
        argv.extend(["--workers-enrich", str(int(workers_enrich))])

    if workers_cost is not None:
        argv.extend(["--workers-cost", str(int(workers_cost))])

    if workers_export is not None:
        argv.extend(["--workers-export", str(int(workers_export))])

    if include_terminated is True:
        argv.append("--include-terminated")
    elif include_terminated is False:
        argv.append("--no-include-terminated")

    if validate_diagrams is True:
        argv.append("--validate-diagrams")
    elif validate_diagrams is False:
        argv.append("--no-validate-diagrams")

    if diagrams is True:
        argv.append("--diagrams")
    elif diagrams is False:
        argv.append("--no-diagrams")

    _maybe_add(argv, "--validate-schema", schema_validation)
    if schema_sample_records is not None:
        _maybe_add(argv, "--validate-schema-sample", str(int(schema_sample_records)))
    if diagram_depth is not None:
        _maybe_add(argv, "--diagram-depth", str(int(diagram_depth)))

    if cost_report is True:
        argv.append("--cost-report")
    elif cost_report is False:
        argv.append("--no-cost-report")

    if cost_report is not False:
        _maybe_add(argv, "--cost-start", cost_start)
        _maybe_add(argv, "--cost-end", cost_end)
        _maybe_add(argv, "--cost-currency", cost_currency)
        _maybe_add(argv, "--cost-compartment-group-by", cost_compartment_group_by)
        if cost_group_by:
            _maybe_add(argv, "--cost-group-by", ",".join(cost_group_by))
        _maybe_add(argv, "--osub-subscription-id", osub_subscription_id)

    _maybe_add(argv, "--assessment-target-group", assessment_target_group)
    if assessment_target_scope:
        for entry in assessment_target_scope:
            _maybe_add(argv, "--assessment-target-scope", entry)
    if assessment_lens_weight:
        for entry in assessment_lens_weight:
            _maybe_add(argv, "--assessment-lens-weight", entry)
    if assessment_capability:
        for entry in assessment_capability:
            _maybe_add(argv, "--assessment-capability", entry)

    return WizardPlan(argv=argv)


def build_diff_plan(
    *,
    auth: str,
    profile: Optional[str],
    tenancy_ocid: Optional[str],
    config_path: Optional[Path] = None,
    prev: Path,
    curr: Path,
    outdir: Path,
    json_logs: Optional[bool] = None,
    log_level: Optional[str] = None,
) -> WizardPlan:
    argv: List[str] = ["diff"]
    argv.extend(
        build_common_argv(
            auth=auth,
            profile=profile,
            tenancy_ocid=tenancy_ocid,
            log_level=log_level,
            json_logs=json_logs,
            config_path=config_path,
        )
    )

    argv.extend(["--prev", str(prev)])
    argv.extend(["--curr", str(curr)])
    argv.extend(["--outdir", str(outdir)])
    return WizardPlan(argv=argv)


def build_coverage_plan(*, inventory: Path, top: Optional[int] = None) -> WizardPlan:
    argv: List[str] = ["enrich-coverage", "--inventory", str(inventory)]
    if top is not None:
        argv.extend(["--top", str(int(top))])
    return WizardPlan(argv=argv)


def build_simple_plan(
    *,
    subcommand: str,
    auth: str,
    profile: Optional[str],
    tenancy_ocid: Optional[str],
    config_path: Optional[Path] = None,
    json_logs: Optional[bool] = None,
    log_level: Optional[str] = None,
) -> WizardPlan:
    if subcommand not in {"validate-auth", "list-regions", "list-compartments", "list-genai-models"}:
        raise ValueError(f"Unsupported wizard subcommand: {subcommand}")

    argv: List[str] = [subcommand]
    argv.extend(
        build_common_argv(
            auth=auth,
            profile=profile,
            tenancy_ocid=tenancy_ocid,
            log_level=log_level,
            json_logs=json_logs,
            config_path=config_path,
        )
    )
    return WizardPlan(argv=argv)
