from __future__ import annotations

import io
import logging
from contextlib import redirect_stdout
from pathlib import Path
from typing import Optional, Tuple

from ..cli import (
    cmd_diff,
    cmd_enrich_coverage,
    cmd_list_compartments,
    cmd_list_genai_models,
    cmd_list_regions,
    cmd_rebuild,
    cmd_run,
    cmd_validate_auth,
)
from ..config import load_run_config
from ..logging import LogConfig, setup_logging
from ..normalize.schema import resolve_output_paths
from .plan import WizardPlan


class _BufferHandler(logging.Handler):
    def __init__(self, stream: io.StringIO) -> None:
        super().__init__()
        self._stream = stream

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore[override]
        try:
            msg = self.format(record)
            self._stream.write(msg)
            self._stream.write("\n")
        except Exception:
            # Logging must never break execution.
            return


def _configure_wizard_logging(cfg: object, log_buf: io.StringIO) -> None:
    """Configure logging so that logs are captured in-memory.

    This avoids stdout/stderr interleaving in the wizard UI.
    """

    # Force setup_logging to reconfigure for this run.
    if getattr(setup_logging, "_configured", False):
        setattr(setup_logging, "_configured", False)

    # cfg is a RunConfig; avoid importing its type here.
    level = str(getattr(cfg, "log_level", "INFO"))
    json_logs = bool(getattr(cfg, "json_logs", False))

    setup_logging(LogConfig(level=level, json_logs=json_logs))

    root = logging.getLogger()
    formatter = root.handlers[0].formatter if root.handlers else None

    handler = _BufferHandler(log_buf)
    if formatter is not None:
        handler.setFormatter(formatter)

    root.handlers = [handler]


def execute_plan(plan: WizardPlan) -> Tuple[int, Optional[Path], str, str]:
    """Execute a WizardPlan using the existing CLI command handlers.

    Returns:
      (exit_code, outdir_if_any, captured_stdout)

    Notes:
    - Output is captured to support a nicer interactive experience.
    - Logs are still emitted via the configured logger handlers.
    """

    stdout_buf = io.StringIO()
    log_buf = io.StringIO()
    try:
        command, cfg = load_run_config(argv=plan.argv)
        _configure_wizard_logging(cfg, log_buf)

        with redirect_stdout(stdout_buf):
            if command == "run":
                code = cmd_run(cfg)
                return code, cfg.outdir, stdout_buf.getvalue(), log_buf.getvalue()
            if command == "rebuild":
                code = cmd_rebuild(cfg)
                return code, cfg.outdir, stdout_buf.getvalue(), log_buf.getvalue()
            if command == "diff":
                code = cmd_diff(cfg)
                return code, cfg.outdir, stdout_buf.getvalue(), log_buf.getvalue()
            if command == "enrich-coverage":
                code = cmd_enrich_coverage(cfg)
                return code, None, stdout_buf.getvalue(), log_buf.getvalue()
            if command == "validate-auth":
                code = cmd_validate_auth(cfg)
                return code, None, stdout_buf.getvalue(), log_buf.getvalue()
            if command == "list-regions":
                code = cmd_list_regions(cfg)
                return code, None, stdout_buf.getvalue(), log_buf.getvalue()
            if command == "list-compartments":
                code = cmd_list_compartments(cfg)
                return code, None, stdout_buf.getvalue(), log_buf.getvalue()
            if command == "list-genai-models":
                code = cmd_list_genai_models(cfg)
                return code, None, stdout_buf.getvalue(), log_buf.getvalue()
        return 2, None, f"Unsupported command: {command}\n", log_buf.getvalue()
    except Exception as exc:
        if not log_buf.getvalue().strip():
            log_buf.write(f"ERROR: {exc}")
        return 1, None, stdout_buf.getvalue(), log_buf.getvalue()


def summarize_outdir(outdir: Path) -> str:
    """Best-effort summary of artifacts in the output directory."""
    if not outdir.exists() or not outdir.is_dir():
        return f"Output directory not found: {outdir}"

    paths = resolve_output_paths(outdir)
    key_paths = [
        paths.debug_log,
        paths.report_md,
        paths.report_html,
        paths.inventory_jsonl,
        paths.inventory_csv,
        paths.run_summary_json,
        paths.graph_nodes_jsonl,
        paths.graph_edges_jsonl,
        paths.relationships_jsonl,
        paths.cost_report_md,
        paths.diff_dir / "diff.json",
        paths.diff_dir / "diff_summary.json",
        paths.diagrams_consolidated_dir / "diagram.consolidated.flowchart.mmd",
        paths.diagrams_architecture_dir / "diagram.arch.tenancy.mmd",
    ]

    diagram_paths = sorted(
        p for p in paths.diagrams_dir.glob("**/diagram*.mmd") if p.is_file()
    )
    key_paths.extend(diagram_paths)

    present = [p for p in key_paths if p.exists()]
    if not present:
        return f"Wrote output directory: {outdir}"
    return "Wrote:\n" + "\n".join(f"- {p}" for p in present)
