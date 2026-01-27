from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .plan import (
    WizardPlan,
    build_diff_plan,
    build_coverage_plan,
    build_run_plan,
    build_simple_plan,
)
from .runner import execute_plan, summarize_outdir
from .config_file import load_wizard_plan_from_file


def _require_rich() -> None:
    try:
        import rich  # noqa: F401
    except Exception as e:  # pragma: no cover
        raise SystemExit(
            "The wizard UI is an optional feature. Install it with: pip install .[wizard]\n"
            f"(Import error: {e})\n"
        )


def _ask_choice(
    prompt: str,
    choices: Sequence[Union[str, Tuple[str, str]]],
    default: Optional[str] = None,
    *,
    allow_back: bool = False,
) -> str:
    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()
    console.print(f"\n[bold]{prompt}[/bold]")
    normalized: List[Tuple[str, str]] = []
    for item in choices:
        if isinstance(item, tuple):
            label, desc = item
        else:
            label, desc = str(item), ""
        normalized.append((label, desc))

    if allow_back and "Back" not in [label for label, _ in normalized]:
        normalized.append(("Back", "Return to the previous menu."))
    labels = [label for label, _ in normalized]

    for idx, (label, desc) in enumerate(normalized, start=1):
        console.print(f"  [cyan]{idx}[/cyan]) {label}")
        console.print(f"     [dim]{desc}[/dim]")

    default_idx = None
    if default and default in labels:
        default_idx = str(labels.index(default) + 1)

    while True:
        ans = Prompt.ask("Select", default=default_idx)
        try:
            i = int(ans)
        except Exception:
            i = 0
        if 1 <= i <= len(labels):
            return labels[i - 1]
        console.print(f"[red]Invalid selection: {ans}[/red]")


def _ask_bool(prompt: str, default: bool) -> bool:
    from rich.prompt import Confirm

    return bool(Confirm.ask(prompt, default=default))


def _ask_str(prompt: str, default: Optional[str] = None, allow_blank: bool = False) -> str:
    from rich.prompt import Prompt

    while True:
        v = Prompt.ask(prompt, default=default)
        if v.strip() or allow_blank:
            return v


def _ask_int(prompt: str, default: int, *, min_value: int = 1) -> int:
    from rich.console import Console

    console = Console()
    while True:
        raw = _ask_str(prompt, default=str(default))
        try:
            value = int(str(raw).strip())
        except Exception:
            console.print("[red]Enter a valid integer.[/red]")
            continue
        if value < min_value:
            console.print(f"[red]Value must be >= {min_value}.[/red]")
            continue
        return value


def _ask_optional_int(prompt: str) -> Optional[int]:
    from rich.console import Console

    console = Console()
    while True:
        raw = _ask_str(prompt, default="", allow_blank=True).strip()
        if not raw:
            return None
        try:
            return int(raw)
        except Exception:
            console.print("[red]Enter a valid integer or leave blank.[/red]")
            continue


def _ask_optional_int_with_min(prompt: str, *, min_value: int = 0) -> Optional[int]:
    from rich.console import Console

    console = Console()
    while True:
        value = _ask_optional_int(prompt)
        if value is None:
            return None
        if value < min_value:
            console.print(f"[red]Value must be >= {min_value}.[/red]")
            continue
        return value


def _ask_optional_float(prompt: str) -> Optional[float]:
    from rich.console import Console

    console = Console()
    while True:
        raw = _ask_str(prompt, default="", allow_blank=True).strip()
        if not raw:
            return None
        try:
            return float(raw)
        except Exception:
            console.print("[red]Enter a valid number or leave blank.[/red]")
            continue


def _ask_repeatable_list(prompt: str) -> List[str]:
    out: List[str] = []
    while True:
        v = _ask_str(prompt, default="", allow_blank=True).strip()
        if not v:
            return out
        out.append(v)


def _ask_multi_select(
    prompt: str,
    choices: Sequence[Union[str, Tuple[str, str]]],
    *,
    default: Optional[Sequence[str]] = None,
) -> List[str]:
    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()
    console.print(f"\n[bold]{prompt}[/bold]")
    normalized: List[Tuple[str, str]] = []
    for item in choices:
        if isinstance(item, tuple):
            label, desc = item
        else:
            label, desc = str(item), ""
        normalized.append((label, desc))

    labels = [label for label, _ in normalized]
    for idx, (label, desc) in enumerate(normalized, start=1):
        console.print(f"  [cyan]{idx}[/cyan]) {label}")
        console.print(f"     [dim]{desc}[/dim]")

    default_idx = None
    if default:
        idx_list = [str(labels.index(item) + 1) for item in default if item in labels]
        if idx_list:
            default_idx = ",".join(idx_list)

    while True:
        raw = Prompt.ask("Select (comma-separated, blank = none)", default=default_idx or "").strip()
        if not raw:
            return []
        tokens = [t.strip() for t in raw.split(",") if t.strip()]
        selected: List[str] = []
        invalid: List[str] = []
        for token in tokens:
            if token.isdigit():
                idx = int(token)
                if 1 <= idx <= len(labels):
                    selected.append(labels[idx - 1])
                else:
                    invalid.append(token)
            else:
                match = next((l for l in labels if l.lower() == token.lower()), None)
                if match:
                    selected.append(match)
                else:
                    invalid.append(token)
        if invalid:
            console.print(f"[red]Invalid selection(s): {', '.join(invalid)}[/red]")
            continue
        deduped: List[str] = []
        for item in selected:
            if item not in deduped:
                deduped.append(item)
        return deduped


def _ask_existing_file(prompt: str, default: Optional[str] = None) -> Path:
    from rich.console import Console

    console = Console()
    while True:
        p = Path(_ask_str(prompt, default=default))
        if p.exists() and p.is_file():
            return p
        console.print(f"[red]File not found: {p}[/red]")


def _ask_optional_existing_file(prompt: str, default: Optional[str] = None) -> Optional[Path]:
    from rich.console import Console

    console = Console()
    while True:
        raw = _ask_str(prompt, default=default, allow_blank=True).strip()
        if not raw or raw.lower() in {"none", "no", "skip"}:
            return None
        p = Path(raw)
        if p.exists() and p.is_file():
            return p
        console.print(f"[red]File not found: {p}[/red]")


def _ask_outdir_base(prompt: str, default: str) -> Path:
    while True:
        p = Path(_ask_str(prompt, default=default))
        # Allow non-existent; reject existing non-directory.
        if p.exists() and not p.is_dir():
            continue
        return p


def _is_within_repo(path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(Path.cwd().resolve())
    except Exception:
        return str(path.resolve()).startswith(str(Path.cwd().resolve()))


def _ask_plan_path(prompt: str, default: str) -> Path:
    from rich.console import Console

    console = Console()
    while True:
        p = Path(_ask_str(prompt, default=default))
        if p.suffix.lower() not in {".yaml", ".yml", ".json"}:
            console.print("[red]Plan file must end with .yaml, .yml, or .json.[/red]")
            continue
        if not _is_within_repo(p):
            console.print("[red]Plan file must be inside the inventory repository.[/red]")
            continue
        return p


def _parse_regions(s: str) -> Optional[List[str]]:
    import re

    raw = (s or "").strip()
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return None
    pattern = re.compile(r"^[a-z0-9-]+-[0-9]+$")
    invalid = [p for p in parts if not pattern.match(p)]
    if invalid:
        raise ValueError(f"Invalid region value(s): {', '.join(invalid)}")
    return parts


def _header() -> None:
    from rich.console import Console
    from rich.panel import Panel

    Console().print(
        Panel.fit(
            "OCI Inventory Wizard\n"
            "Guided workflows for running oci-inv safely and consistently.",
            title="oci-inv-wizard",
        )
    )


def _print_hints() -> None:
    from rich.console import Console

    Console().print("[dim]Tips: Enter accepts defaults. Ctrl+C exits.[/dim]")


def _print_startup_status() -> None:
    from rich.console import Console
    from rich.table import Table
    import os

    from ..genai.config import default_genai_config_path, local_genai_config_path

    console = Console()
    table = Table(title="Startup Context", show_header=True, header_style="bold")
    table.add_column("Source")
    table.add_column("Path")
    table.add_column("Status")

    oci_path = Path("~/.oci/config").expanduser()
    oci_status = "OK" if oci_path.exists() else "error retrieving"
    table.add_row("OCI config", str(oci_path), oci_status)

    env_path = os.environ.get("OCI_INV_GENAI_CONFIG")
    if env_path:
        genai_path = Path(env_path).expanduser()
        genai_source = "GenAI config (OCI_INV_GENAI_CONFIG)"
    else:
        default_path = default_genai_config_path()
        if default_path.exists():
            genai_path = default_path
            genai_source = "GenAI config (~/.config/oci-inv/genai.yaml)"
        else:
            genai_path = local_genai_config_path()
            genai_source = "GenAI config (inventory/.local/genai.yaml)"

    genai_status = "OK" if genai_path.exists() else "error retrieving"
    table.add_row(genai_source, str(genai_path), genai_status)

    console.print(table)


def _default_logging_from_repo_config() -> Tuple[str, bool]:
    default_level = "INFO"
    default_json = False
    cfg_path = Path("config") / "workers.yaml"
    if not cfg_path.exists():
        return default_level, default_json
    try:
        import yaml

        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return default_level, default_json
    if not isinstance(data, dict):
        return default_level, default_json

    raw_level = data.get("log_level")
    if isinstance(raw_level, str) and raw_level.strip():
        default_level = raw_level.strip().upper()

    raw_json = data.get("json_logs")
    if isinstance(raw_json, bool):
        default_json = raw_json
    elif isinstance(raw_json, str):
        raw = raw_json.strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            default_json = True
        elif raw in {"0", "false", "no", "off"}:
            default_json = False

    return default_level, default_json


def _section(title: str) -> None:
    from rich.console import Console

    Console().rule(f"[bold]{title}[/bold]")


def _write_plan_file(plan_data: Dict[str, Any], path: Path) -> None:
    from rich.console import Console
    import yaml

    console = Console()
    data = {k: v for k, v in plan_data.items() if v is not None}
    if path.suffix.lower() in {".yaml", ".yml"}:
        path.write_text(
            yaml.safe_dump(data, sort_keys=False).strip() + "\n",
            encoding="utf-8",
        )
    else:
        path.write_text(
            json.dumps(data, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
    console.print(f"[dim]Saved plan: {path}[/dim]")


def _run_quick_plan(plan: WizardPlan, title: str) -> None:
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(Panel.fit(plan.as_command_line(), title=title))
    code, _, stdout_text, log_text = execute_plan(plan)
    if log_text.strip():
        console.print(Panel.fit(log_text.rstrip(), title="Logs"))
    if stdout_text.strip():
        console.print(Panel.fit(stdout_text.rstrip(), title="Command output"))
    console.print(f"Exit code: {code}")


def _confirm_and_run(
    plan: WizardPlan,
    *,
    dry_run: bool = False,
    assume_yes: bool = False,
    plan_data: Optional[Dict[str, Any]] = None,
) -> int:
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(Panel.fit(plan.as_command_line(), title="Command preview"))

    if plan_data and _ask_bool("Save this plan file for later?", default=False):
        plan_path = _ask_plan_path("Plan file path", default="wizard-plan.yaml")
        _write_plan_file(plan_data, plan_path)

    if dry_run:
        console.print("Dry run: no execution performed.")
        return 0

    if not assume_yes and _ask_bool("Dry run only (print command and exit)?", default=False):
        console.print("Dry run: no execution performed.")
        return 0

    if not assume_yes:
        if not _ask_bool("Proceed?", default=True):
            console.print("Aborted.")
            return 1

    with console.status("Running...", spinner="dots"):
        code, outdir, stdout_text, log_text = execute_plan(plan)

    if log_text.strip():
        console.print(Panel.fit(log_text.rstrip(), title="Logs"))

    if stdout_text.strip():
        console.print(Panel.fit(stdout_text.rstrip(), title="Command output"))

    if outdir:
        console.print(Panel.fit(summarize_outdir(outdir), title="Artifacts"))

    if int(code) == 0:
        console.print(f"Exit code: {code}")
    else:
        console.print(f"Exit code: {code}")
        auth_markers = (
            "Failed to resolve auth",
            "config profile",
            "Profile",
            "OCI SDK error while loading config profile",
        )
        if any(marker in log_text for marker in auth_markers):
            console.print(
                "[yellow]Auth hint:[/yellow] If you use config auth, confirm the profile exists "
                "(default is DEFAULT) or select auth=config and set --profile explicitly."
            )
    return int(code)


def main() -> None:
    _require_rich()

    parser = argparse.ArgumentParser(prog="oci-inv-wizard", add_help=True)
    parser.add_argument(
        "--from",
        dest="from_file",
        type=Path,
        help="Run non-interactively from a YAML/JSON wizard plan file",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the resolved command and exit")
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompts (use with --from)",
    )
    ns = parser.parse_args()

    _header()
    _print_hints()
    _print_startup_status()

    if ns.from_file:
        plan = load_wizard_plan_from_file(ns.from_file)
        code = _confirm_and_run(plan, dry_run=bool(ns.dry_run), assume_yes=bool(ns.yes))
        raise SystemExit(code)

    start_in_troubleshooting = False
    while True:
        if start_in_troubleshooting:
            mode = "Troubleshooting"
        else:
            mode = _ask_choice(
                "What do you want to do?",
                [
                    ("Run inventory", "Discover resources and write a new inventory run."),
                    ("Diff inventories", "Compare two inventory/inventory.jsonl files and write a diff."),
                    ("Troubleshooting", "Diagnostics and helper utilities."),
                    ("Exit", "Quit the wizard."),
                ],
                default="Run inventory",
            )

        if mode == "Exit":
            from rich.console import Console

            Console().print("Bye o/")
            raise SystemExit(0)

        menu_origin = "main"
        if mode == "Troubleshooting":
            trouble = _ask_choice(
                "Troubleshooting",
                [
                    ("Validate auth", "Validate OCI credentials and auth configuration."),
                    ("List regions", "Show subscribed regions for the tenancy."),
                    ("List compartments", "List compartments in the tenancy."),
                    ("Enrichment coverage", "Report missing enrichers in an inventory/inventory.jsonl."),
                    ("List GenAI models", "List available OCI GenAI models and capabilities."),
                ],
                default="Validate auth",
                allow_back=True,
            )
            if trouble == "Back":
                start_in_troubleshooting = False
                continue
            mode = trouble
            menu_origin = "troubleshooting"

        start_in_troubleshooting = False

        while True:
            auth = _ask_choice(
                "Auth method",
                [
                    ("auto", "Try resource principals, then instance principals, then config DEFAULT."),
                    ("config", "Use ~/.oci/config with an explicit profile."),
                    ("instance", "Use instance principals (OCI compute)."),
                    ("resource", "Use resource principals (OCI services)."),
                    ("security_token", "Use a security_token profile in ~/.oci/config."),
                ],
                default="auto",
                allow_back=True,
            )
            if auth == "Back":
                if menu_origin == "troubleshooting":
                    start_in_troubleshooting = True
                break

            profile: Optional[str] = None
            if auth in {"config", "security_token"}:
                profile = _ask_str("Profile", default="DEFAULT")
            elif auth == "auto":
                from rich.console import Console

                Console().print(
                    "[dim]Note: auto auth falls back to config profile 'DEFAULT' if principals are unavailable. "
                    "Use auth=config to specify a different profile.[/dim]"
                )

            tenancy_ocid = _ask_str("Tenancy OCID (optional)", default="", allow_blank=True).strip() or None

            # Logging toggles (keep simple)
            default_log_level, default_json_logs = _default_logging_from_repo_config()
            json_logs = _ask_bool("Enable JSON logs?", default=default_json_logs)
            log_level = _ask_choice(
                "Log level",
                [
                    ("INFO", "Standard logs for normal operation."),
                    ("DEBUG", "Verbose logs for troubleshooting."),
                ],
                default=default_log_level if default_log_level in {"INFO", "DEBUG"} else "INFO",
                allow_back=True,
            )
            if log_level == "Back":
                continue
            break

        if auth == "Back":
            continue

        if mode == "Validate auth":
            _section("Validate Auth")
            plan = build_simple_plan(
                subcommand="validate-auth",
                auth=auth,
                profile=profile,
                tenancy_ocid=tenancy_ocid,
                json_logs=json_logs,
                log_level=log_level,
            )
            plan_data = {
                "mode": "validate-auth",
                "auth": auth,
                "profile": profile,
                "tenancy_ocid": tenancy_ocid,
                "json_logs": json_logs,
                "log_level": log_level,
            }
            raise SystemExit(_confirm_and_run(plan, plan_data=plan_data))

        if mode == "List regions":
            _section("List Regions")
            plan = build_simple_plan(
                subcommand="list-regions",
                auth=auth,
                profile=profile,
                tenancy_ocid=tenancy_ocid,
                json_logs=json_logs,
                log_level=log_level,
            )
            plan_data = {
                "mode": "list-regions",
                "auth": auth,
                "profile": profile,
                "tenancy_ocid": tenancy_ocid,
                "json_logs": json_logs,
                "log_level": log_level,
            }
            raise SystemExit(_confirm_and_run(plan, plan_data=plan_data))

        if mode == "List compartments":
            _section("List Compartments")
            plan = build_simple_plan(
                subcommand="list-compartments",
                auth=auth,
                profile=profile,
                tenancy_ocid=tenancy_ocid,
                json_logs=json_logs,
                log_level=log_level,
            )
            plan_data = {
                "mode": "list-compartments",
                "auth": auth,
                "profile": profile,
                "tenancy_ocid": tenancy_ocid,
                "json_logs": json_logs,
                "log_level": log_level,
            }
            raise SystemExit(_confirm_and_run(plan, plan_data=plan_data))

        if mode == "List GenAI models":
            _section("List GenAI Models")
            plan = build_simple_plan(
                subcommand="list-genai-models",
                auth=auth,
                profile=profile,
                tenancy_ocid=tenancy_ocid,
                json_logs=json_logs,
                log_level=log_level,
            )
            plan_data = {
                "mode": "list-genai-models",
                "auth": auth,
                "profile": profile,
                "tenancy_ocid": tenancy_ocid,
                "json_logs": json_logs,
                "log_level": log_level,
            }
            raise SystemExit(_confirm_and_run(plan, plan_data=plan_data))

        if mode == "Enrichment coverage":
            _section("Enrichment Coverage")
            inventory_path = _ask_existing_file("inventory/inventory.jsonl path")
            top_n = _ask_int("Top missing types to show", default=10, min_value=1)
            plan = build_coverage_plan(
                inventory=inventory_path,
                top=top_n,
            )
            plan_data = {
                "mode": "enrich-coverage",
                "auth": auth,
                "inventory": str(inventory_path),
                "top": top_n,
                "json_logs": json_logs,
                "log_level": log_level,
            }
            raise SystemExit(_confirm_and_run(plan, plan_data=plan_data))

        if mode == "Diff inventories":
            _section("Diff Inventories")
            prev = _ask_existing_file("Prev inventory/inventory.jsonl path")
            curr = _ask_existing_file("Curr inventory/inventory.jsonl path")
            outdir = _ask_outdir_base("Diff output dir", default=str(Path("out") / "diff"))
            plan = build_diff_plan(
                auth=auth,
                profile=profile,
                tenancy_ocid=tenancy_ocid,
                prev=prev,
                curr=curr,
                outdir=outdir,
                json_logs=json_logs,
                log_level=log_level,
            )
            plan_data = {
                "mode": "diff",
                "auth": auth,
                "profile": profile,
                "tenancy_ocid": tenancy_ocid,
                "json_logs": json_logs,
                "log_level": log_level,
                "prev": str(prev),
                "curr": str(curr),
                "outdir": str(outdir),
            }
            raise SystemExit(_confirm_and_run(plan, plan_data=plan_data))

        # Run inventory
        _section("Run Inventory")
        if _ask_bool("List subscribed regions now?", default=False):
            _section("List Regions")
            _run_quick_plan(
                build_simple_plan(
                    subcommand="list-regions",
                    auth=auth,
                    profile=profile,
                    tenancy_ocid=tenancy_ocid,
                    json_logs=json_logs,
                    log_level=log_level,
                ),
                "List Regions",
            )
        if _ask_bool("List compartments now?", default=False):
            _section("List Compartments")
            _run_quick_plan(
                build_simple_plan(
                    subcommand="list-compartments",
                    auth=auth,
                    profile=profile,
                    tenancy_ocid=tenancy_ocid,
                    json_logs=json_logs,
                    log_level=log_level,
                ),
                "List Compartments",
            )
        outdir = _ask_outdir_base("Output base dir", default="out")
        config_path = _ask_optional_existing_file(
            "Config file path (blank = use repo default config/workers.yaml)",
            default="config/workers.yaml",
        )
        use_config_workers = False
        if config_path:
            use_config_workers = _ask_bool(
                "Use worker defaults from config file?",
                default=True,
            )
        while True:
            try:
                regions = _parse_regions(
                    _ask_str(
                        "Regions (comma-separated, blank = subscribed). Example: mx-queretaro-1,us-phoenix-1",
                        default="",
                        allow_blank=True,
                    )
                )
                break
            except ValueError as exc:
                from rich.console import Console

                console = Console()
                console.print(f"[red]{exc}[/red]")
                console.print("[dim]Example: mx-queretaro-1,us-phoenix-1[/dim]")

        genai_summary = _ask_bool(
            "Generate GenAI Executive Summary in report/report.md? (uses OCI_INV_GENAI_CONFIG, else ~/.config/oci-inv/genai.yaml, else inventory/.local/genai.yaml)",
            default=False,
        )

        while True:
            query = _ask_str("Structured Search query", default="query all resources")
            if query.strip():
                break

        include_terminated = _ask_bool("Include terminated resources?", default=False)

        prev_raw = _ask_str("Prev inventory/inventory.jsonl (optional)", default="", allow_blank=True).strip()
        prev = Path(prev_raw) if prev_raw else None
        if prev and (not prev.exists() or not prev.is_file()):
            prev = None

        workers_region = None
        workers_enrich = None
        if not use_config_workers:
            workers_region = _ask_int("Max parallel regions", default=6, min_value=1)
            workers_enrich = _ask_int("Max enricher workers", default=24, min_value=1)
        workers_cost = None
        workers_export = None
        client_connection_pool_size = None

        validate_diagrams: Optional[bool] = None
        diagrams: Optional[bool] = None
        architecture_diagrams: Optional[bool] = None
        schema_validation: Optional[str] = None
        schema_sample_records: Optional[int] = None
        diagram_depth: Optional[int] = None
        cost_report: Optional[bool] = None
        cost_start: Optional[str] = None
        cost_end: Optional[str] = None
        cost_currency: Optional[str] = None
        cost_compartment_group_by: Optional[str] = None
        cost_group_by: Optional[List[str]] = None
        osub_subscription_id: Optional[str] = None
        assessment_target_group: Optional[str] = None
        assessment_target_scope: Optional[List[str]] = None
        assessment_lens_weight: Optional[List[str]] = None
        assessment_capability: Optional[List[str]] = None

        if _ask_bool("Show advanced run options?", default=False):
            _section("Advanced Run Options")
            workers_cost = _ask_optional_int_with_min("Max cost workers (blank = default)", min_value=1)
            workers_export = _ask_optional_int_with_min("Max export workers (blank = default)", min_value=1)
            client_connection_pool_size = _ask_optional_int_with_min(
                "Client connection pool size (blank = SDK default)",
                min_value=1,
            )
            diagrams_choice = _ask_choice(
                "Generate diagrams?",
                [
                    ("Default", "Use CLI/config defaults."),
                    ("Enable", "Always generate diagrams."),
                    ("Disable", "Disable diagrams for this run."),
                ],
                default="Default",
            )
            if diagrams_choice == "Enable":
                diagrams = True
            elif diagrams_choice == "Disable":
                diagrams = False
            architecture_choice = _ask_choice(
                "Generate architecture diagrams (Mermaid C4 + flowchart)?",
                [
                    ("Default", "Use CLI/config defaults."),
                    ("Enable", "Always generate architecture diagrams."),
                    ("Disable", "Disable architecture diagrams for this run."),
                ],
                default="Default",
            )
            if architecture_choice == "Enable":
                architecture_diagrams = True
            elif architecture_choice == "Disable":
                architecture_diagrams = False
            validate_choice = _ask_choice(
                "Validate Mermaid diagrams with mmdc?",
                [
                    ("Default", "Use CLI/config defaults."),
                    ("Enable", "Require validation (fails run if invalid)."),
                    ("Disable", "Skip explicit validation flag."),
                ],
                default="Default",
            )
            if validate_choice == "Enable":
                validate_diagrams = True
            elif validate_choice == "Disable":
                validate_diagrams = False

            schema_validation = _ask_choice(
                "Schema validation mode",
                [
                    ("auto", "Auto (default; sample large outputs)."),
                    ("full", "Validate all records."),
                    ("sampled", "Validate a fixed sample size."),
                    ("off", "Disable schema validation."),
                ],
                default="auto",
            )
            if schema_validation == "sampled":
                schema_sample_records = _ask_optional_int_with_min(
                    "Schema sample records (blank = default)",
                    min_value=1,
                )
            diagram_depth_choice = _ask_choice(
                "Consolidated diagram depth",
                [
                    ("1", "Global map only (tenancy + regions)."),
                    ("2", "Summary hierarchy with category counts (no per-resource nodes/edges)."),
                    ("3", "Same summary hierarchy as depth 2 (reserved for future detail)."),
                ],
                default="3",
            )
            diagram_depth = int(diagram_depth_choice)

            cost_report_choice = _ask_choice(
                "Generate cost/cost_report.md (Usage API, read-only)?",
                [
                    ("Default", "Use CLI/config defaults."),
                    ("Enable", "Generate cost report."),
                    ("Disable", "Disable cost report."),
                ],
                default="Default",
            )
            if cost_report_choice == "Enable":
                cost_report = True
            elif cost_report_choice == "Disable":
                cost_report = False
            if cost_report:
                cost_start = _ask_str("Cost start (ISO 8601, blank = month-to-date)", default="", allow_blank=True).strip()
                cost_end = _ask_str("Cost end (ISO 8601, blank = now)", default="", allow_blank=True).strip()
                cost_currency = _ask_str("Cost currency (ISO 4217, optional)", default="", allow_blank=True).strip()
                cost_compartment_group_by = _ask_choice(
                    "Cost compartment grouping",
                    [
                        ("Default", "Use compartmentId (default)."),
                        ("compartmentName", "Group by compartment display name."),
                        ("compartmentPath", "Group by compartment path."),
                    ],
                    default="Default",
                )
                if cost_compartment_group_by == "Default":
                    cost_compartment_group_by = None
                cost_group_by = _ask_multi_select(
                    "Cost group_by fields (optional)",
                    [
                        ("service", "Service name"),
                        ("region", "Region name"),
                        ("compartmentId", "Compartment OCID"),
                        ("compartmentName", "Compartment display name"),
                        ("compartmentPath", "Compartment path"),
                        ("sku", "SKU"),
                    ],
                )
                if not cost_group_by:
                    cost_group_by = None
                osub_subscription_id = _ask_str(
                    "OneSubscription subscription ID (optional)",
                    default="",
                    allow_blank=True,
                ).strip() or None
                if not cost_start:
                    cost_start = None
                if not cost_end:
                    cost_end = None
                if not cost_currency:
                    cost_currency = None

            if _ask_bool("Add assessment metadata?", default=False):
                assessment_target_group = _ask_str(
                    "Assessment target group (optional)",
                    default="",
                    allow_blank=True,
                ).strip() or None
                assessment_target_scope = _ask_repeatable_list(
                    "Assessment target scope (repeatable, blank = done)",
                )
                assessment_lens_weight = _ask_repeatable_list(
                    "Assessment lens weight (e.g., Knowledge=1) (blank = done)",
                )
                assessment_capability = _ask_repeatable_list(
                    "Assessment capability (domain|capability|knowledge|process|metrics|adoption|automation|target|evidence) (blank = done)",
                )

                if not assessment_target_scope:
                    assessment_target_scope = None
                if not assessment_lens_weight:
                    assessment_lens_weight = None
                if not assessment_capability:
                    assessment_capability = None

        plan = build_run_plan(
            auth=auth,
            profile=profile,
            tenancy_ocid=tenancy_ocid,
            config_path=config_path,
            outdir=outdir,
            query=query,
            regions=regions,
            genai_summary=genai_summary,
            prev=prev,
            workers_region=workers_region,
            workers_enrich=workers_enrich,
            workers_cost=workers_cost,
            workers_export=workers_export,
            client_connection_pool_size=client_connection_pool_size,
            include_terminated=include_terminated,
            validate_diagrams=validate_diagrams,
            diagrams=diagrams,
            architecture_diagrams=architecture_diagrams,
            schema_validation=schema_validation,
            schema_sample_records=schema_sample_records,
            diagram_depth=diagram_depth,
            cost_report=cost_report,
            cost_start=cost_start,
            cost_end=cost_end,
            cost_currency=cost_currency,
            cost_compartment_group_by=cost_compartment_group_by,
            cost_group_by=cost_group_by,
            osub_subscription_id=osub_subscription_id,
            assessment_target_group=assessment_target_group,
            assessment_target_scope=assessment_target_scope,
            assessment_lens_weight=assessment_lens_weight,
            assessment_capability=assessment_capability,
            json_logs=json_logs,
            log_level=log_level,
        )
        plan_data = {
            "mode": "run",
            "auth": auth,
            "profile": profile,
            "tenancy_ocid": tenancy_ocid,
            "json_logs": json_logs,
            "log_level": log_level,
            "config": str(config_path) if config_path else None,
            "outdir": str(outdir),
            "query": query,
            "regions": regions,
            "genai_summary": genai_summary,
            "prev": str(prev) if prev else None,
            "workers_region": workers_region,
            "workers_enrich": workers_enrich,
            "workers_cost": workers_cost,
            "workers_export": workers_export,
            "client_connection_pool_size": client_connection_pool_size,
            "include_terminated": include_terminated,
            "validate_diagrams": validate_diagrams,
            "diagrams": diagrams,
            "architecture_diagrams": architecture_diagrams,
            "schema_validation": schema_validation,
            "schema_sample_records": schema_sample_records,
            "diagram_depth": diagram_depth,
            "cost_report": cost_report,
            "cost_start": cost_start,
            "cost_end": cost_end,
            "cost_currency": cost_currency,
            "cost_compartment_group_by": cost_compartment_group_by,
            "cost_group_by": cost_group_by,
            "osub_subscription_id": osub_subscription_id,
            "assessment_target_group": assessment_target_group,
            "assessment_target_scope": assessment_target_scope,
            "assessment_lens_weight": assessment_lens_weight,
            "assessment_capability": assessment_capability,
        }
        raise SystemExit(_confirm_and_run(plan, plan_data=plan_data))
