from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

try:
    from rich.console import Console
    from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
except Exception:  # pragma: no cover - fallback when rich isn't available
    Console = None  # type: ignore[assignment]
    Progress = None  # type: ignore[assignment]
    BarColumn = None  # type: ignore[assignment]
    TaskProgressColumn = None  # type: ignore[assignment]
    TextColumn = None  # type: ignore[assignment]
    TimeElapsedColumn = None  # type: ignore[assignment]
    Table = None  # type: ignore[assignment]


def _format_region_counts(counts: Dict[str, int], *, max_regions: int = 4) -> str:
    if not counts:
        return ""
    items = sorted(counts.items(), key=lambda item: item[0])
    shown = items[:max_regions]
    tail = len(items) - len(shown)
    rendered = ", ".join([f"{name}={count}" for name, count in shown])
    if tail > 0:
        rendered = f"{rendered} (+{tail} more)"
    return rendered


class RunProgress:
    def __init__(self, *, enabled: bool, console: Optional[Console] = None) -> None:
        self._enabled = bool(enabled and Console and Progress)
        self._console = console or (Console() if Console else None)
        self._progress = None
        self._discovery_task: Optional[int] = None
        self._enrich_task: Optional[int] = None
        self._region_counts: Dict[str, int] = {}
        self._started = False
        if self._enabled:
            self._progress = Progress(
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("{task.fields[regions]}", justify="left"),
                TimeElapsedColumn(),
                console=self._console,
                transient=True,
            )

    def __enter__(self) -> RunProgress:
        if self._enabled and self._progress and not self._started:
            self._progress.start()
            self._started = True
        return self

    def __exit__(self, exc_type: Any, exc: Any, exc_tb: Any) -> None:
        if self._enabled and self._progress and self._started:
            self._progress.stop()
            self._started = False

    def start(self) -> None:
        self.__enter__()

    def stop(self) -> None:
        self.__exit__(None, None, None)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start_discovery(self, regions: Sequence[str]) -> None:
        if not self._enabled or not self._progress:
            return
        self._region_counts = {region: 0 for region in regions}
        self._discovery_task = self._progress.add_task(
            "Discovery",
            total=None,
            regions=_format_region_counts(self._region_counts),
        )

    def advance_discovery(self, region: str, *, count: int = 1) -> None:
        if not self._enabled or not self._progress or self._discovery_task is None:
            return
        if region:
            self._region_counts[region] = self._region_counts.get(region, 0) + count
        self._progress.update(
            self._discovery_task,
            advance=count,
            regions=_format_region_counts(self._region_counts),
        )

    def start_enrich(self) -> None:
        if not self._enabled or not self._progress:
            return
        self._enrich_task = self._progress.add_task(
            "Enrichment",
            total=None,
            regions="",
        )

    def advance_enrich(self, *, count: int = 1) -> None:
        if not self._enabled or not self._progress or self._enrich_task is None:
            return
        self._progress.update(self._enrich_task, advance=count, regions="")

    def start_export(self) -> None:
        if not self._enabled or not self._progress:
            return
        if self._enrich_task is None:
            self._enrich_task = self._progress.add_task("Export", total=None, regions="")
        else:
            self._progress.reset(self._enrich_task, total=None, completed=0)
            self._progress.update(self._enrich_task, description="Export", regions="")

    def advance_export(self, *, count: int = 1) -> None:
        if not self._enabled or not self._progress or self._enrich_task is None:
            return
        self._progress.update(self._enrich_task, advance=count, regions="")


def render_run_summary_table(
    *,
    enabled: bool,
    status: str,
    metrics: Dict[str, Any],
    regions: Sequence[str],
    outdir: str,
    console: Optional[Console] = None,
) -> None:
    if not enabled or not Table or not Console:
        return
    table = Table(title="Run Summary", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Status", status)
    table.add_row("Regions in scope", ", ".join(regions))
    table.add_row("Resources discovered", str(metrics.get("total_discovered", 0)))
    table.add_row("Enriched OK", str(metrics.get("enriched_ok", 0)))
    table.add_row("Not implemented", str(metrics.get("not_implemented", 0)))
    table.add_row("Errors", str(metrics.get("errors", 0)))
    table.add_row("Output dir", outdir)
    (console or Console()).print(table)
