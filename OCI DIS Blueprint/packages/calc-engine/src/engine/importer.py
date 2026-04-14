"""
Source File Importer — XLSX/CSV parser with parity-mode row selection.

Implements PRD-015 through PRD-019:
  - Headers at row 5, data starts at row 6
  - TBQ=Y inclusion, Duplicado 2 exclusion
  - Source order preservation
  - Per-row normalization events
  - Immutable SourceIntegrationRow output
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass
class NormalizationEvent:
    field: str
    old_value: object
    new_value: object
    rule: str


@dataclass
class ParsedRow:
    source_row_number: int
    raw_data: dict
    included: bool
    exclusion_reason: Optional[str]
    normalization_events: list[NormalizationEvent] = field(default_factory=list)


@dataclass
class ImportResult:
    source_row_count: int
    tbq_y_count: int
    excluded_count: int
    loaded_count: int
    header_map: dict[str, str]
    rows: list[ParsedRow]
    parser_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Column name normalization
# ---------------------------------------------------------------------------

# Canonical field → list of accepted header variants (case-insensitive)
HEADER_ALIASES: dict[str, list[str]] = {
    "seq_number": ["#", "num", "número"],
    "interface_id": ["id de interfaz", "interface id", "id interfaz"],
    "brand": ["marca", "brand"],
    "business_process": ["proceso de negocio", "proceso", "process"],
    "interface_name": ["interfaz", "interface", "nombre interfaz"],
    "description": ["descripción", "descripcion", "description"],
    "type": ["tipo", "type"],
    "interface_status": ["estado interfaz", "estado", "status"],
    "complexity": ["complejidad", "complexity"],
    "initial_scope": ["alcance inicial", "alcance", "scope"],
    "status": ["estado", "estado de interfaz"],
    "mapping_status": ["estado de mapeo", "mapping status"],
    "source_system": ["sistema de origen", "source system"],
    "source_technology": ["tecnología de origen", "source technology"],
    "source_api_reference": ["api reference", "api ref origen"],
    "source_owner": ["propietario de origen", "source owner"],
    "destination_system": ["sistema de destino", "destination system"],
    "destination_technology": ["tecnología de destino", "destination technology"],
    "destination_owner": ["propietario de destino", "destination owner"],
    "frequency": ["frecuencia", "frequency"],
    "payload_per_execution_kb": ["tamaño kb", "payload por ejecución", "payload (kb)"],
    "tbq": ["tbq"],
    "patterns": ["patrones", "patrón", "pattern"],
    "uncertainty": ["incertidumbre", "uncertainty"],
    "owner": ["owner", "dueño"],
    "identified_in": ["identificada en:", "identified in"],
    "business_process_dd": ["proceso de negocio duediligence", "dd process"],
    "slide": ["slide"],
}


def _normalize_header(raw: str) -> str:
    return raw.strip().lower().replace("\n", " ")


def build_header_map(raw_headers: list) -> dict[str, str]:
    """Map canonical field names → actual column index (str)."""
    header_map: dict[str, str] = {}
    normalized = [_normalize_header(str(h)) if h else "" for h in raw_headers]

    for field_name, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            for idx, h in enumerate(normalized):
                if alias in h:
                    header_map[field_name] = str(idx)
                    break
            if field_name in header_map:
                break

    return header_map


# ---------------------------------------------------------------------------
# Inclusion logic (PRD-017)
# ---------------------------------------------------------------------------

def _get(row: list, header_map: dict, field: str):
    idx = header_map.get(field)
    if idx is None:
        return None
    try:
        return row[int(idx)]
    except (IndexError, ValueError):
        return None


def should_include(row: list, header_map: dict) -> tuple[bool, Optional[str]]:
    """
    Parity-mode inclusion rules:
    - TBQ must be 'Y' (case-insensitive)
    - Estado must NOT be 'Duplicado 2'
    Returns (included, exclusion_reason).
    """
    tbq = _get(row, header_map, "tbq")
    if not tbq or str(tbq).strip().upper() != "Y":
        return False, f"TBQ != Y (was: {tbq!r})"

    status = _get(row, header_map, "interface_status") or _get(row, header_map, "status") or ""
    if str(status).strip() == "Duplicado 2":
        return False, "Estado = Duplicado 2"

    return True, None


# ---------------------------------------------------------------------------
# Normalization helpers (PRD-019)
# ---------------------------------------------------------------------------

FREQUENCY_ALIASES: dict[str, str] = {
    "diario": "Una vez al día",
    "1 vez al dia": "Una vez al día",
    "once a day": "Una vez al día",
    "hourly": "Cada hora",
    "cada 1 hora": "Cada hora",
    "real time": "Tiempo real",
    "tiempo real": "Tiempo real",
    "weekly": "Semanal",
    "monthly": "Mensual",
    "mensual": "Mensual",
    "semanal": "Semanal",
}


def normalize_frequency(raw: Optional[str]) -> tuple[Optional[str], Optional[NormalizationEvent]]:
    if raw is None:
        return None, None
    cleaned = raw.strip().lower()
    canonical = FREQUENCY_ALIASES.get(cleaned)
    if canonical and canonical != raw.strip():
        return canonical, NormalizationEvent(
            field="frequency", old_value=raw, new_value=canonical, rule="frequency_alias_map"
        )
    return raw.strip() or None, None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_rows(
    all_rows: list[list],
    header_row_index: int = 4,   # 0-based = row 5 (PRD-016)
    data_start_index: int = 5,   # 0-based = row 6 (PRD-016)
) -> ImportResult:
    raw_headers = all_rows[header_row_index] if len(all_rows) > header_row_index else []
    header_map = build_header_map(raw_headers)
    data_rows = all_rows[data_start_index:]

    parsed: list[ParsedRow] = []
    tbq_y_count = 0
    excluded_count = 0
    loaded_count = 0

    for row_idx, raw_row in enumerate(data_rows):
        source_row_number = data_start_index + row_idx + 1  # 1-based

        # Skip fully empty rows
        if not any(c is not None and str(c).strip() != "" for c in raw_row):
            continue

        raw_data = {str(i): raw_row[i] for i in range(len(raw_row))}
        events: list[NormalizationEvent] = []

        included, reason = should_include(raw_row, header_map)
        # Check TBQ value directly for accurate counting
        raw_tbq = _get(raw_row, header_map, "tbq")
        is_tbq_y = raw_tbq and str(raw_tbq).strip().upper() == "Y"

        if included:
            tbq_y_count += 1

            # Normalize frequency
            freq_raw = _get(raw_row, header_map, "frequency")
            freq_norm, freq_event = normalize_frequency(str(freq_raw) if freq_raw else None)
            if freq_event:
                events.append(freq_event)

            loaded_count += 1
        else:
            if is_tbq_y:
                # TBQ=Y but excluded (e.g. Duplicado 2) — matches workbook "excluded" count
                tbq_y_count += 1
                excluded_count += 1

        parsed.append(ParsedRow(
            source_row_number=source_row_number,
            raw_data=raw_data,
            included=included,
            exclusion_reason=reason,
            normalization_events=events,
        ))

    return ImportResult(
        source_row_count=len(data_rows),
        tbq_y_count=tbq_y_count,
        excluded_count=excluded_count,
        loaded_count=loaded_count,
        header_map=header_map,
        rows=parsed,
    )
