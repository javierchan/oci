"""
QA Engine — row-level QA status calculation (PRD-025).

Replicates OK / REVISAR logic from workbook column AN.
Returns structured reasons so the UI can drill down.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class QAResult:
    status: str          # "OK" | "REVISAR"
    reasons: list[str]   # structured reason codes for REVISAR


def _normalize_trigger_key(value: str) -> str:
    return " ".join(value.strip().lower().replace("-", " ").split())


# Governed trigger types from TPL - Diccionario / workbook capture vocabulary.
VALID_TRIGGER_TYPES = {
    "scheduled": "Scheduled",
    "rest": "REST",
    "rest trigger": "REST Trigger",
    "event": "Event",
    "event trigger": "Event Trigger",
    "ftp/sftp": "FTP/SFTP",
    "db polling": "DB Polling",
    "jms": "JMS",
    "kafka": "Kafka",
    "webhook": "Webhook",
    "soap": "SOAP",
    "soap trigger": "SOAP Trigger",
}

# Governed pattern IDs from TPL - Patrones
VALID_PATTERN_IDS = {
    "#01", "#02", "#03", "#04", "#05", "#06", "#07", "#08",
    "#09", "#10", "#11", "#12", "#13", "#14", "#15", "#16", "#17",
}


def normalize_trigger_type(trigger_type: Optional[str]) -> Optional[str]:
    if not trigger_type or trigger_type.strip() == "":
        return None
    normalized = VALID_TRIGGER_TYPES.get(_normalize_trigger_key(trigger_type))
    return normalized


def evaluate_qa(
    interface_id: Optional[str],
    trigger_type: Optional[str],
    selected_pattern: Optional[str],
    pattern_rationale: Optional[str],
    core_tools: Optional[str],
    payload_per_execution_kb: Optional[float],
    is_fan_out: Optional[bool],
    fan_out_targets: Optional[int],
    uncertainty: Optional[str],
    is_active_row: bool = True,
) -> QAResult:
    if not is_active_row:
        return QAResult(status="PENDING", reasons=[])

    reasons: list[str] = []
    resolved_trigger_type = normalize_trigger_type(trigger_type)

    # Invalid or missing trigger type
    if resolved_trigger_type is None:
        reasons.append("INVALID_TRIGGER_TYPE")

    # Missing or invalid pattern
    if not selected_pattern or selected_pattern not in VALID_PATTERN_IDS:
        reasons.append("INVALID_PATTERN")

    # Missing rationale
    if not pattern_rationale or len(pattern_rationale.strip()) < 10:
        reasons.append("MISSING_RATIONALE")

    # Missing core tools
    if not core_tools or core_tools.strip() == "":
        reasons.append("MISSING_CORE_TOOLS")

    # Missing payload (mandatory input — PRD-027)
    if payload_per_execution_kb is None:
        reasons.append("MISSING_PAYLOAD")

    # Fan-out declared but targets missing
    if is_fan_out and (fan_out_targets is None or fan_out_targets < 2):
        reasons.append("MISSING_FAN_OUT_TARGETS")

    # TBD uncertainty flag
    if uncertainty and "TBD" in uncertainty.upper():
        reasons.append("TBD_UNCERTAINTY")

    status = "OK" if not reasons else "REVISAR"
    return QAResult(status=status, reasons=reasons)
