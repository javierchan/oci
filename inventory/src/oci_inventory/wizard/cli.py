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

    ans = Prompt.ask("Select", default=default_idx)
    try:
        i = int(ans)
    except Exception:
        i = 0
    if i < 1 or i > len(choices):
        raise SystemExit(f"Invalid selection: {ans}")
    return choices[i - 1]


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
    while True:
        raw = _ask_str(prompt, default=str(default))
        try:
            value = int(str(raw).strip())
        except Exception:
            continue
        if value < min_value:
            continue
        return value


def _ask_existing_file(prompt: str, default: Optional[str] = None) -> Path:
    while True:
        p = Path(_ask_str(prompt, default=default))
        if p.exists() and p.is_file():
            return p


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
        plan = build_simple_plan(
            subcommand="list-compartments",
            auth=auth,
            profile=profile,
            tenancy_ocid=tenancy_ocid,
            json_logs=json_logs,
            log_level=log_level,
        )
        raise SystemExit(_confirm_and_run(plan))

    if mode == "Enrichment coverage":
        inventory_path = _ask_existing_file("inventory.jsonl path")
        top_n = _ask_int("Top missing types to show", default=10, min_value=1)
        plan = build_coverage_plan(
            inventory=inventory_path,
            top=top_n,
        )
        raise SystemExit(_confirm_and_run(plan))

    if mode == "Diff inventories":
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
        json_logs=json_logs,
        log_level=log_level,
    )
    raise SystemExit(_confirm_and_run(plan))
