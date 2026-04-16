"""
OCI DIS Volumetry Calculation Engine
=====================================
Deterministic calculation service — workbook parity required (PRD-011, PRD-027 to PRD-035).

All formulas are pure functions with no side effects.
Inputs are typed via dataclasses; outputs include formula metadata for explainability.
This engine is called by the Celery worker and must never contain UI or database code.

Design rules:
  1. No floating-point mutation — round only at the output boundary.
  2. Every function returns a CalcResult with inputs, formula, value, and unit.
  3. Unknown or missing inputs return None with an explicit reason string.
  4. Assumption versions are always passed explicitly — no global state.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import math


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Assumptions:
    """Matches AssumptionSet.assumptions JSON structure (TPL - Supuestos)."""
    oic_billing_threshold_kb: float = 50.0
    oic_pack_size_msgs_per_hour: int = 5000
    month_days: int = 30
    streaming_partition_throughput_mb_s: float = 1.0
    functions_default_duration_ms: int = 200
    functions_default_memory_mb: int = 256
    functions_default_concurrency: int = 1
    # OIC service limits
    oic_rest_max_payload_kb: float = 50_000.0   # 50 MB
    oic_ftp_max_payload_kb: float = 50_000.0
    oic_kafka_max_payload_kb: float = 10_000.0


@dataclass(frozen=True)
class CalcResult:
    value: Optional[float]
    unit: str
    formula: str
    inputs: dict
    reason: Optional[str] = None
    assumption_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IntegrationInput:
    """Minimal input slice needed for volumetry — sourced from CatalogIntegration."""
    integration_id: str
    payload_per_execution_kb: Optional[float]
    executions_per_day: Optional[float]  # derived field (AF)
    trigger_type: Optional[str]          # Scheduled | REST | Event
    is_real_time: Optional[bool]
    core_tools: Optional[str]            # comma-separated, e.g. "OIC Gen3, ATP, Functions"
    response_size_kb: Optional[float]
    is_fan_out: Optional[bool]
    fan_out_targets: Optional[int]
    # Optional overrides (for Functions)
    override_invocations_per_month: Optional[float] = None
    override_duration_ms: Optional[int] = None
    override_memory_mb: Optional[int] = None


# ---------------------------------------------------------------------------
# Frequency / execution helpers
# ---------------------------------------------------------------------------

FREQUENCY_MAP: dict[str, float] = {
    # Code: executions/day — from TPL - Diccionario
    "Once Daily": 1.0,
    "Twice Daily": 2.0,
    "4 Times Daily": 4.0,
    "Hourly": 24.0,
    "Every 30 Minutes": 48.0,
    "Every 15 Minutes": 96.0,
    "Every 5 Minutes": 288.0,
    "Every Minute": 1440.0,
    "Real Time": 1440.0,   # treated as per-minute for sizing
    "Weekly": 1.0 / 7,
    "Monthly": 1.0 / 30,
    "On Demand": 1.0,      # conservative default
    "Una vez al día": 1.0,
    "2 veces al día": 2.0,
    "4 veces al día": 4.0,
    "Cada hora": 24.0,
    "Cada 30 minutos": 48.0,
    "Cada 15 minutos": 96.0,
    "Cada 5 minutos": 288.0,
    "Cada minuto": 1440.0,
    "Tiempo real": 1440.0,   # treated as per-minute for sizing
    "Semanal": 1.0 / 7,
    "Mensual": 1.0 / 30,
    "Bajo demanda": 1.0,     # conservative default
    "TBD": None,
}


def executions_per_day(frequency_label: str) -> CalcResult:
    """Derive executions/day from a governed frequency label (PRD-028)."""
    value = FREQUENCY_MAP.get(frequency_label)
    return CalcResult(
        value=value,
        unit="executions/day",
        formula=f"FREQUENCY_MAP['{frequency_label}']",
        inputs={"frequency_label": frequency_label},
        reason=None if value is not None else f"Frequency '{frequency_label}' not in governed map",
    )


# ---------------------------------------------------------------------------
# Payload / timing drivers
# ---------------------------------------------------------------------------

def payload_per_hour_kb(payload_kb: float, execs_per_day: float) -> CalcResult:
    """Payload/hour = payload_per_execution_kb * executions_per_day / 24 (PRD-029)."""
    value = payload_kb * execs_per_day / 24.0
    return CalcResult(
        value=value,
        unit="KB/hour",
        formula="payload_per_execution_kb * executions_per_day / 24",
        inputs={"payload_kb": payload_kb, "execs_per_day": execs_per_day},
    )


def payload_per_month_kb(payload_kb: float, execs_per_day: float, assumptions: Assumptions) -> CalcResult:
    """Payload/month = payload/day * month_days (PRD-029)."""
    payload_per_day = payload_kb * execs_per_day
    value = payload_per_day * assumptions.month_days
    return CalcResult(
        value=value,
        unit="KB/month",
        formula="payload_per_execution_kb * executions_per_day * month_days",
        inputs={"payload_kb": payload_kb, "execs_per_day": execs_per_day},
        assumption_keys=["month_days"],
    )


# ---------------------------------------------------------------------------
# OIC billing messages (PRD-030, PRD-031)
# ---------------------------------------------------------------------------

def oic_billing_messages_per_execution(
    payload_kb: float,
    response_kb: float,
    assumptions: Assumptions,
) -> CalcResult:
    """
    OIC billing msg count per execution.
    Each 50 KB (or fraction) = 1 billing message, applied to both request and response.
    """
    threshold = assumptions.oic_billing_threshold_kb
    request_msgs = math.ceil(payload_kb / threshold) if payload_kb else 0
    response_msgs = math.ceil(response_kb / threshold) if response_kb else 0
    total = request_msgs + response_msgs
    return CalcResult(
        value=float(total),
        unit="billing messages/execution",
        formula="ceil(payload_kb / 50) + ceil(response_kb / 50)",
        inputs={"payload_kb": payload_kb, "response_kb": response_kb},
        assumption_keys=["oic_billing_threshold_kb"],
    )


def oic_billing_messages_per_month(
    payload_kb: float,
    response_kb: float,
    execs_per_day: float,
    assumptions: Assumptions,
) -> CalcResult:
    msgs_per_exec = oic_billing_messages_per_execution(payload_kb, response_kb, assumptions)
    if msgs_per_exec.value is None:
        return CalcResult(value=None, unit="billing messages/month",
                          formula="", inputs={}, reason=msgs_per_exec.reason)
    monthly_execs = execs_per_day * assumptions.month_days
    value = msgs_per_exec.value * monthly_execs
    return CalcResult(
        value=value,
        unit="billing messages/month",
        formula="msgs_per_exec * executions_per_day * month_days",
        inputs={"msgs_per_exec": msgs_per_exec.value, "execs_per_day": execs_per_day},
        assumption_keys=["month_days"],
    )


def oic_peak_packs_per_hour(
    peak_msgs_per_hour: float,
    assumptions: Assumptions,
) -> CalcResult:
    """Round up to 5K-message packs/hour for OIC standard licensing (PRD-031)."""
    packs = math.ceil(peak_msgs_per_hour / assumptions.oic_pack_size_msgs_per_hour)
    return CalcResult(
        value=float(packs),
        unit="packs/hour (5K msgs each)",
        formula="ceil(peak_msgs_per_hour / 5000)",
        inputs={"peak_msgs_per_hour": peak_msgs_per_hour},
        assumption_keys=["oic_pack_size_msgs_per_hour"],
    )


# ---------------------------------------------------------------------------
# Oracle Functions (PRD-034)
# ---------------------------------------------------------------------------

def functions_invocations_per_month(
    row: IntegrationInput,
    assumptions: Assumptions,
) -> CalcResult:
    """
    If override_invocations_per_month set → use it.
    Otherwise derive from payload → bytes → executions/day → month.
    """
    if row.override_invocations_per_month is not None:
        return CalcResult(
            value=row.override_invocations_per_month,
            unit="invocations/month",
            formula="override_invocations_per_month (manual override)",
            inputs={"override": row.override_invocations_per_month},
        )
    if row.executions_per_day is None:
        return CalcResult(value=None, unit="invocations/month", formula="",
                          inputs={}, reason="executions_per_day not available")
    value = row.executions_per_day * assumptions.month_days
    return CalcResult(
        value=value,
        unit="invocations/month",
        formula="executions_per_day * month_days",
        inputs={"execs_per_day": row.executions_per_day},
        assumption_keys=["month_days"],
    )


def functions_execution_units(
    invocations: float,
    duration_ms: int,
    memory_mb: int,
    concurrency: int,
) -> CalcResult:
    """GB-seconds = invocations * (duration_ms/1000) * (memory_mb/1024) * concurrency."""
    gb_seconds = invocations * (duration_ms / 1000) * (memory_mb / 1024) * concurrency
    return CalcResult(
        value=gb_seconds,
        unit="GB-seconds/month",
        formula="invocations * (duration_ms/1000) * (memory_mb/1024) * concurrency",
        inputs={
            "invocations": invocations,
            "duration_ms": duration_ms,
            "memory_mb": memory_mb,
            "concurrency": concurrency,
        },
    )


# ---------------------------------------------------------------------------
# OCI Streaming (PRD-032)
# ---------------------------------------------------------------------------

def streaming_gb_per_month(
    payload_kb_per_month: float,
) -> CalcResult:
    value = payload_kb_per_month / (1024 * 1024)
    return CalcResult(
        value=value,
        unit="GB/month",
        formula="payload_kb_per_month / (1024 * 1024)",
        inputs={"payload_kb_per_month": payload_kb_per_month},
    )


def streaming_partition_count(
    peak_kb_per_second: float,
    assumptions: Assumptions,
) -> CalcResult:
    """Partitions = ceil(peak_KB/s / (partition_throughput_MB/s * 1024))."""
    throughput_kb_s = assumptions.streaming_partition_throughput_mb_s * 1024
    partitions = math.ceil(peak_kb_per_second / throughput_kb_s) if peak_kb_per_second > 0 else 1
    return CalcResult(
        value=float(partitions),
        unit="partitions",
        formula="ceil(peak_kb_per_second / (throughput_mb_s * 1024))",
        inputs={"peak_kb_per_second": peak_kb_per_second},
        assumption_keys=["streaming_partition_throughput_mb_s"],
    )


# ---------------------------------------------------------------------------
# OCI Data Integration (PRD-033)
# ---------------------------------------------------------------------------

def di_data_processed_gb(
    payload_kb_per_month: float,
) -> CalcResult:
    value = payload_kb_per_month / (1024 * 1024)
    return CalcResult(
        value=value,
        unit="GB/month",
        formula="payload_kb_per_month / (1024^2)",
        inputs={"payload_kb_per_month": payload_kb_per_month},
    )


# ---------------------------------------------------------------------------
# Project-level consolidation
# ---------------------------------------------------------------------------

def consolidate_project(
    rows: list[IntegrationInput],
    assumptions: Assumptions,
) -> dict:
    """
    Compute row-level and consolidated drivers for all integrations.
    Returns structured dict consumed by VolumetrySnapshot.consolidated.
    """
    oic_rows, di_rows, functions_rows, streaming_rows, queue_rows = [], [], [], [], []

    for row in rows:
        tools = (row.core_tools or "").lower()

        if "oic" in tools or "oracle integration" in tools:
            oic_rows.append(row)
        if "data integration" in tools or "odi" in tools:
            di_rows.append(row)
        if "functions" in tools:
            functions_rows.append(row)
        if "streaming" in tools:
            streaming_rows.append(row)
        if "queue" in tools:
            queue_rows.append(row)

    # OIC totals
    total_oic_msgs_month = 0.0
    for r in oic_rows:
        if r.payload_per_execution_kb and r.executions_per_day:
            msgs = oic_billing_messages_per_month(
                r.payload_per_execution_kb,
                r.response_size_kb or 0,
                r.executions_per_day,
                assumptions,
            )
            if msgs.value:
                total_oic_msgs_month += msgs.value

    peak_oic_msgs_hour = total_oic_msgs_month / (assumptions.month_days * 24)
    packs = oic_peak_packs_per_hour(peak_oic_msgs_hour, assumptions)

    # Functions totals
    total_invocations = 0.0
    for r in functions_rows:
        inv = functions_invocations_per_month(r, assumptions)
        if inv.value:
            total_invocations += inv.value
    total_exec_units = functions_execution_units(
        total_invocations,
        assumptions.functions_default_duration_ms,
        assumptions.functions_default_memory_mb,
        assumptions.functions_default_concurrency,
    ).value

    return {
        "oic": {
            "total_billing_msgs_month": total_oic_msgs_month,
            "peak_billing_msgs_hour": peak_oic_msgs_hour,
            "peak_packs_hour": packs.value,
            "row_count": len(oic_rows),
        },
        "data_integration": {
            "workspace_active": len(di_rows) > 0,
            "row_count": len(di_rows),
        },
        "functions": {
            "total_invocations_month": total_invocations,
            "total_execution_units_gb_s": total_exec_units,
            "row_count": len(functions_rows),
        },
        "streaming": {"row_count": len(streaming_rows)},
        "queue": {"row_count": len(queue_rows)},
    }
