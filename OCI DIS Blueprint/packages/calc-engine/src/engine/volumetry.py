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
from typing import Literal, Optional
import math


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

PayloadUnit = Literal["KB", "MB"]


@dataclass(frozen=True)
class Assumptions:
    """Matches AssumptionSet.assumptions JSON structure (TPL - Supuestos)."""
    oic_billing_threshold_kb: float = 50.0
    oic_pack_size_msgs_per_hour: int = 5000
    oic_byol_pack_size_msgs_per_hour: int = 20000
    month_days: int = 31
    streaming_partition_throughput_mb_s: float = 1.0
    streaming_read_throughput_mb_s: float = 2.0
    streaming_max_message_size_mb: float = 1.0
    streaming_retention_days: int = 7
    streaming_default_partitions: int = 200
    functions_default_duration_ms: int = 2000
    functions_default_memory_mb: int = 256
    functions_default_concurrency: int = 1
    functions_max_timeout_s: int = 300
    functions_batch_size_records: int = 500
    queue_billing_unit_kb: int = 64
    queue_max_message_kb: int = 256
    queue_retention_days: int = 7
    queue_throughput_soft_limit_msgs_per_second: int = 10
    data_integration_workspaces_per_region: int = 5
    data_integration_deleted_workspace_retention_days: int = 15
    # OIC service limits
    oic_rest_max_payload_kb: float = 51_200.0
    oic_ftp_max_payload_kb: float = 51_200.0
    oic_kafka_max_payload_kb: float = 10_240.0
    oic_rest_raw_max_payload_kb: float = 1_048_576.0
    oic_rest_attachment_max_payload_kb: float = 1_048_576.0
    oic_rest_json_schema_max_payload_kb: float = 102_400.0
    oic_soap_max_payload_kb: float = 51_200.0
    oic_soap_attachment_max_payload_kb: float = 1_048_576.0
    oic_ftp_stage_file_max_payload_kb: float = 10_485_760.0
    oic_db_stored_proc_timeout_s: int = 240
    oic_db_polling_max_payload_kb: float = 10_240.0
    oic_outbound_read_timeout_s: int = 300
    oic_outbound_connection_timeout_s: int = 300
    oic_agent_connection_timeout_s: int = 240
    oic_project_max_integrations: int = 100
    oic_project_max_deployments: int = 50
    oic_project_max_connections: int = 20
    oic_timeout_s: int = 300


def normalize_payload_to_kb(payload_value: float, unit: PayloadUnit) -> CalcResult:
    """Normalize a payload measurement into the canonical KB unit used by formulas."""

    normalized_unit = unit.upper()
    if normalized_unit == "KB":
        value = payload_value
    else:
        value = payload_value * 1024.0
    return CalcResult(
        value=value,
        unit="KB",
        formula="payload_value if unit == 'KB' else payload_value * 1024",
        inputs={"payload_value": payload_value, "unit": normalized_unit},
        reason=None,
    )


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
    selected_pattern: Optional[str] = None
    # Optional overrides (for Functions)
    override_invocations_per_month: Optional[float] = None
    override_duration_ms: Optional[int] = None
    override_memory_mb: Optional[int] = None


# ---------------------------------------------------------------------------
# Frequency / execution helpers
# ---------------------------------------------------------------------------

FREQUENCY_MAP: dict[str, float | None] = {
    "cada 5 minutos": 288.0,
    "cada 15 minutos": 96.0,
    "cada 20 minutos": 72.0,
    "cada 30 minutos": 48.0,
    "cada 1 hora": 24.0,
    "cada hora": 24.0,
    "cada 2 horas": 12.0,
    "cada 4 horas": 6.0,
    "cada 6 horas": 4.0,
    "cada 8 horas": 3.0,
    "cada 12 horas": 2.0,
    "una vez al dia": 1.0,
    "2 veces al dia": 2.0,
    "4 veces al dia": 4.0,
    "semanal": 1.0 / 7,
    "quincenal": 1.0 / 15,
    "mensual": 1.0 / 30,
    "tiempo real": 24.0,
    "bajo demanda": 1.0,
    "tbd": None,
}


def executions_per_day(frequency_label: str) -> CalcResult:
    """Derive executions/day from a governed frequency label (PRD-028)."""
    normalized_label = frequency_label.strip().lower().replace("í", "i").replace("á", "a")
    value = FREQUENCY_MAP.get(normalized_label)
    return CalcResult(
        value=value,
        unit="executions/day",
        formula=f"FREQUENCY_MAP['{normalized_label}']",
        inputs={"frequency_label": frequency_label, "normalized_frequency_label": normalized_label},
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
        formula="ceil(payload_kb / governed_threshold_kb) + ceil(response_kb / governed_threshold_kb)",
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
    *,
    byol: bool = False,
) -> CalcResult:
    """Round up to the governed OIC pack size for the chosen licensing model."""

    pack_size = (
        assumptions.oic_byol_pack_size_msgs_per_hour
        if byol
        else assumptions.oic_pack_size_msgs_per_hour
    )
    packs = math.ceil(peak_msgs_per_hour / pack_size)
    return CalcResult(
        value=float(packs),
        unit=f"packs/hour ({pack_size} msgs each)",
        formula="ceil(peak_msgs_per_hour / governed_pack_size_msgs_per_hour)",
        inputs={"peak_msgs_per_hour": peak_msgs_per_hour},
        assumption_keys=[
            "oic_byol_pack_size_msgs_per_hour" if byol else "oic_pack_size_msgs_per_hour"
        ],
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
        has_selected_pattern = bool(row.selected_pattern)

        if "oic" in tools or "oracle integration" in tools or has_selected_pattern:
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
