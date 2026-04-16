"""
Source File Importer — XLSX/CSV parser with parity-mode row selection.

Implements PRD-015 through PRD-019:
  - Supports parity workbooks with headers at row 5 and template uploads with headers at row 1
  - TBQ=Y inclusion, Duplicado 2 exclusion
  - Source order preservation
  - Per-row normalization events
  - Immutable SourceIntegrationRow output
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from unicodedata import normalize


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
    "interface_name": ["interfaz", "interface", "interface name", "nombre interfaz"],
    "description": ["descripción", "descripcion", "description"],
    "type": ["tipo", "type"],
    "base": ["base"],
    "interface_status": ["estado interfaz", "interface status"],
    "complexity": ["complejidad", "complexity"],
    "initial_scope": ["alcance inicial", "alcance", "scope"],
    "status": ["estado", "status"],
    "mapping_status": ["estado de mapeo", "mapping status"],
    "source_system": ["sistema de origen", "source system"],
    "source_technology": ["tecnología de origen", "source technology"],
    "source_api_reference": ["api reference", "api ref origen"],
    "source_owner": ["propietario de origen", "source owner"],
    "destination_system": ["sistema de destino", "destination system"],
    "destination_technology_1": [
        "tecnología de destino #1",
        "tecnologia de destino #1",
        "tecnología de destino",
        "tecnologia de destino",
        "destination technology #1",
        "destination technology",
    ],
    "destination_technology_2": [
        "tecnología de destino #2",
        "tecnologia de destino #2",
        "destination technology #2",
    ],
    "destination_owner": ["propietario de destino", "destination owner"],
    "frequency": ["frecuencia", "frequency"],
    "is_real_time": ["tiempo real (si/no)", "tiempo real", "real time (yes/no)", "real time"],
    "trigger_type": ["tipo trigger oic", "trigger type", "tipo de trigger"],
    "response_size_kb": ["response size (kb)", "response size", "tamaño respuesta kb"],
    "payload_per_execution_kb": [
        "payload por ejecución (kb)",
        "payload por ejecucion (kb)",
        "payload por ejecución",
        "payload por ejecucion",
        "payload (kb)",
        "tamaño kb",
    ],
    "is_fan_out": ["fan-out (si/no)", "fan-out", "fan out"],
    "fan_out_targets": ["# destinos", "fan-out targets", "fan out targets"],
    "calendarization": ["calendarización", "calendarizacion", "calendarization"],
    "selected_pattern": [
        "patrón seleccionado (manual)",
        "patron seleccionado (manual)",
        "patrón seleccionado",
        "patron seleccionado",
        "patrones",
        "pattern selected",
        "selected pattern",
    ],
    "pattern_rationale": [
        "racional del patrón (manual)",
        "racional del patron (manual)",
        "racional del patrón",
        "racional del patron",
        "pattern rationale",
    ],
    "comments": [
        "comentarios / observaciones",
        "comentarios/observaciones",
        "comentarios",
        "observaciones",
        "comments",
    ],
    "retry_policy": ["retry policy"],
    "core_tools": [
        "herramientas core cuantificables / volumétricas",
        "herramientas core cuantificables / volumetricas",
        "herramientas core",
        "core tools",
        "posibles tools y componentes identificados",
    ],
    "additional_tools_overlays": [
        "herramientas adicionales / overlays (complemento manual)",
        "herramientas adicionales",
        "additional tools",
        "overlays",
    ],
    "tbq": ["tbq"],
    "uncertainty": ["incertidumbre", "uncertainty"],
    "owner": ["owner", "dueño"],
    "identified_in": ["identificada en:", "identified in"],
    "business_process_dd": [
        "proceso de negocio duedilligence",
        "proceso de negocio duediligence",
        "dd process",
    ],
    "slide": ["slide"],
}


def _normalize_header(raw: str) -> str:
    collapsed = " ".join(raw.strip().lower().replace("\n", " ").split())
    return normalize("NFKD", collapsed).encode("ascii", "ignore").decode("ascii")


def _header_matches(alias: str, header: str) -> bool:
    if header == alias:
        return True
    return (
        header.startswith(f"{alias} ")
        or header.startswith(f"{alias}(")
        or header.startswith(f"{alias}:")
        or header.startswith(f"{alias}-")
    )


def build_header_map(raw_headers: list) -> dict[str, str]:
    """Map canonical field names → actual column index (str)."""
    header_map: dict[str, str] = {}
    normalized = [_normalize_header(str(h)) if h else "" for h in raw_headers]

    for field_name, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            for idx, h in enumerate(normalized):
                if _header_matches(alias, h):
                    header_map[field_name] = str(idx)
                    break
            if field_name in header_map:
                break

    return header_map


def detect_header_row(all_rows: list[list], candidate_limit: int = 5) -> int:
    """Choose the strongest header row candidate from the first few rows."""

    if not all_rows:
        return 0

    best_index = 0
    best_score = -1
    for index, row in enumerate(all_rows[:candidate_limit]):
        score = len(build_header_map(row))
        if score > best_score:
            best_index = index
            best_score = score

    return best_index


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
    "hourly": "Cada 1 hora",
    "cada hora": "Cada 1 hora",
    "cada 1 hora": "Cada 1 hora",
    "every 2 hours": "Cada 2 horas",
    "cada 2 horas": "Cada 2 horas",
    "every 4 hours": "Cada 4 horas",
    "cada 4 horas": "Cada 4 horas",
    "every 6 hours": "Cada 6 horas",
    "cada 6 horas": "Cada 6 horas",
    "every 8 hours": "Cada 8 horas",
    "cada 8 horas": "Cada 8 horas",
    "every 12 hours": "Cada 12 horas",
    "cada 12 horas": "Cada 12 horas",
    "2 veces al dia": "Cada 12 horas",
    "dos veces al dia": "Cada 12 horas",
    "4 veces al dia": "Cada 6 horas",
    "real time": "Tiempo Real",
    "tiempo real": "Tiempo Real",
    "weekly": "Semanal",
    "monthly": "Mensual",
    "mensual": "Mensual",
    "semanal": "Semanal",
    "biweekly": "Quincenal",
    "quincenal": "Quincenal",
    "on demand": "Bajo demanda",
    "bajo demanda": "Bajo demanda",
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
    if all_rows:
        detected_header_row_index = detect_header_row(all_rows)
        if detected_header_row_index != header_row_index:
            header_row_index = detected_header_row_index
            data_start_index = header_row_index + 1

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
