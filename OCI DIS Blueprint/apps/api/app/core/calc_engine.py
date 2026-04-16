"""Helpers that make the pure calc-engine package importable from the API."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_calc_engine_path() -> None:
    """Add the calc-engine src directory to ``sys.path`` in local and Docker runs."""

    resolved_file = Path(__file__).resolve()
    candidates = [Path("/calc-engine/src")]
    candidates.extend(parent / "packages" / "calc-engine" / "src" for parent in resolved_file.parents)
    for candidate in candidates:
        if candidate.exists():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            return
    raise RuntimeError("Unable to locate packages/calc-engine/src for API imports.")


_ensure_calc_engine_path()

from engine.importer import HEADER_ALIASES, ImportResult, NormalizationEvent, ParsedRow, detect_header_row, parse_rows  # noqa: E402
from engine.qa import QAResult, evaluate_qa, normalize_trigger_type  # noqa: E402
from engine.volumetry import (  # noqa: E402
    Assumptions,
    CalcResult,
    IntegrationInput,
    consolidate_project,
    normalize_payload_to_kb,
    oic_billing_messages_per_execution,
    oic_peak_packs_per_hour,
    executions_per_day,
    functions_execution_units,
    functions_invocations_per_month,
    oic_billing_messages_per_month,
    payload_per_hour_kb,
    payload_per_month_kb,
    streaming_gb_per_month,
    streaming_partition_count,
    di_data_processed_gb,
)

__all__ = [
    "Assumptions",
    "CalcResult",
    "HEADER_ALIASES",
    "ImportResult",
    "IntegrationInput",
    "NormalizationEvent",
    "ParsedRow",
    "QAResult",
    "consolidate_project",
    "detect_header_row",
    "di_data_processed_gb",
    "evaluate_qa",
    "executions_per_day",
    "functions_execution_units",
    "functions_invocations_per_month",
    "normalize_trigger_type",
    "normalize_payload_to_kb",
    "oic_billing_messages_per_execution",
    "oic_billing_messages_per_month",
    "oic_peak_packs_per_hour",
    "parse_rows",
    "payload_per_hour_kb",
    "payload_per_month_kb",
    "streaming_gb_per_month",
    "streaming_partition_count",
]
