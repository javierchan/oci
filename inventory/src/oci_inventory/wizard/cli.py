from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .plan import (
    WizardPlan,
    build_diff_plan,
    build_coverage_plan,
    build_run_plan,
    build_simple_plan,
    build_genai_chat_plan,
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


def _ask_choice(prompt: str, choices: List[str], default: Optional[str] = None) -> str:
    from rich.console import Console
    from rich.prompt import Prompt

    console = Console()
    console.print(f"\n[bold]{prompt}[/bold]")
    for idx, c in enumerate(choices, start=1):
        console.print(f"  [cyan]{idx}[/cyan]) {c}")

    default_idx = None
    if default and default in choices:
        default_idx = str(choices.index(default) + 1)

    while True:
        ans = Prompt.ask("Select", default=default_idx)
        try:
            i = int(ans)
        except Exception:
            i = 0
        if 1 <= i <= len(choices):
            return choices[i - 1]
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


def _ask_existing_file(prompt: str, default: Optional[str] = None) -> Path:
    from rich.console import Console

    console = Console()
    while True:
        p = Path(_ask_str(prompt, default=default))
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


def _parse_regions(s: str) -> Optional[List[str]]:
    raw = (s or "").strip()
    if not raw:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return parts or None


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


def _section(title: str) -> None:
    from rich.console import Console

    Console().rule(f"[bold]{title}[/bold]")


def _confirm_and_run(plan: WizardPlan, *, dry_run: bool = False, assume_yes: bool = False) -> int:
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(Panel.fit(plan.as_command_line(), title="Command preview"))

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

    if ns.from_file:
        plan = load_wizard_plan_from_file(ns.from_file)
        code = _confirm_and_run(plan, dry_run=bool(ns.dry_run), assume_yes=bool(ns.yes))
        raise SystemExit(code)

    mode = _ask_choice(
        "What do you want to do?",
        [
            "Run inventory",
            "Diff inventories",
            "Validate auth",
            "List regions",
            "List compartments",
            "List GenAI models",
            "GenAI chat",
            "Enrichment coverage",
            "Exit",
        ],
        default="Run inventory",
    )

    if mode == "Exit":
        raise SystemExit(0)

    auth = _ask_choice("Auth method", ["auto", "config", "instance", "resource", "security_token"], default="auto")
    profile: Optional[str] = None
    if auth in {"config", "security_token"}:
        profile = _ask_str("Profile", default="DEFAULT")

    tenancy_ocid = _ask_str("Tenancy OCID (optional)", default="", allow_blank=True).strip() or None

    # Logging toggles (keep simple)
    json_logs = _ask_bool("Enable JSON logs?", default=False)
    log_level = _ask_choice("Log level", ["INFO", "DEBUG"], default="INFO")

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
        raise SystemExit(_confirm_and_run(plan))

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
        raise SystemExit(_confirm_and_run(plan))

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
        raise SystemExit(_confirm_and_run(plan))

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
        raise SystemExit(_confirm_and_run(plan))

    if mode == "GenAI chat":
        _section("GenAI Chat")
        api_format = _ask_choice("GenAI API format", ["AUTO", "GENERIC", "COHERE"], default="AUTO")
        message_mode = _ask_choice(
            "Message input",
            ["Enter message", "Load message from file", "Use report.md as context"],
            default="Enter message",
        )

        message: Optional[str] = None
        report_path: Optional[Path] = None
        if message_mode == "Enter message":
            while True:
                message = _ask_str("Message", default="", allow_blank=True).strip()
                if message:
                    break
        elif message_mode == "Load message from file":
            msg_path = _ask_existing_file("Message file path")
            message = msg_path.read_text(encoding="utf-8")
        else:
            report_path = _ask_existing_file("report.md path")

        advanced = _ask_bool("Advanced GenAI options?", default=False)
        max_tokens: Optional[int] = None
        temperature: Optional[float] = None
        if advanced:
            max_tokens = _ask_optional_int("Max tokens (blank = default)")
            temperature = _ask_optional_float("Temperature (blank = default)")

        plan = build_genai_chat_plan(
            auth=auth,
            profile=profile,
            tenancy_ocid=tenancy_ocid,
            api_format=api_format,
            message=message,
            report=report_path,
            max_tokens=max_tokens,
            temperature=temperature,
            json_logs=json_logs,
            log_level=log_level,
        )
        raise SystemExit(_confirm_and_run(plan))

    if mode == "Enrichment coverage":
        _section("Enrichment Coverage")
        inventory_path = _ask_existing_file("inventory.jsonl path")
        top_n = _ask_int("Top missing types to show", default=10, min_value=1)
        plan = build_coverage_plan(
            inventory=inventory_path,
            top=top_n,
        )
        raise SystemExit(_confirm_and_run(plan))

    if mode == "Diff inventories":
        _section("Diff Inventories")
        prev = _ask_existing_file("Prev inventory.jsonl path")
        curr = _ask_existing_file("Curr inventory.jsonl path")
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
        raise SystemExit(_confirm_and_run(plan))

    # Run inventory
    _section("Run Inventory")
    outdir = _ask_outdir_base("Output base dir", default="out")
    regions = _parse_regions(_ask_str("Regions (comma-separated, blank = subscribed)", default="", allow_blank=True))

    genai_summary = _ask_bool(
        "Generate GenAI Executive Summary in report.md? (uses OCI_INV_GENAI_CONFIG, else ~/.config/oci-inv/genai.yaml, else inventory/.local/genai.yaml)",
        default=False,
    )

    while True:
        query = _ask_str("Structured Search query", default="query all resources")
        if query.strip():
            break

    parquet = _ask_bool("Write Parquet (requires pyarrow)?", default=False)

    include_terminated = _ask_bool("Include terminated resources?", default=False)

    prev_raw = _ask_str("Prev inventory.jsonl (optional)", default="", allow_blank=True).strip()
    prev = Path(prev_raw) if prev_raw else None
    if prev and (not prev.exists() or not prev.is_file()):
        prev = None

    workers_region = _ask_int("Max parallel regions", default=6, min_value=1)
    workers_enrich = _ask_int("Max enricher workers", default=24, min_value=1)

    validate_diagrams = False
    cost_report = False
    cost_start: Optional[str] = None
    cost_end: Optional[str] = None
    cost_currency: Optional[str] = None
    assessment_target_group: Optional[str] = None
    assessment_target_scope: Optional[List[str]] = None
    assessment_lens_weight: Optional[List[str]] = None
    assessment_capability: Optional[List[str]] = None

    if _ask_bool("Show advanced run options?", default=False):
        _section("Advanced Run Options")
        validate_diagrams = _ask_bool(
            "Validate Mermaid diagrams with mmdc (fails run if invalid)?",
            default=False,
        )
        cost_report = _ask_bool("Generate cost_report.md (Usage API, read-only)?", default=False)
        if cost_report:
            cost_start = _ask_str("Cost start (ISO 8601, blank = month-to-date)", default="", allow_blank=True).strip()
            cost_end = _ask_str("Cost end (ISO 8601, blank = now)", default="", allow_blank=True).strip()
            cost_currency = _ask_str("Cost currency (ISO 4217, optional)", default="", allow_blank=True).strip()
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
        outdir=outdir,
        query=query,
        regions=regions,
        parquet=parquet,
        genai_summary=genai_summary,
        prev=prev,
        workers_region=workers_region,
        workers_enrich=workers_enrich,
        include_terminated=include_terminated,
        validate_diagrams=validate_diagrams,
        cost_report=cost_report,
        cost_start=cost_start,
        cost_end=cost_end,
        cost_currency=cost_currency,
        assessment_target_group=assessment_target_group,
        assessment_target_scope=assessment_target_scope,
        assessment_lens_weight=assessment_lens_weight,
        assessment_capability=assessment_capability,
        json_logs=json_logs,
        log_level=log_level,
    )
    raise SystemExit(_confirm_and_run(plan))
