"""
Source File Importer — XLSX/CSV parser with parity-mode row selection.

Implements PRD-015 through PRD-019:
  - Supports parity workbooks with headers at row 5 and template uploads with headers at row 1
  - Technical inclusion regardless of TBQ commercial eligibility
  - Duplicado 2 source defects rejected from the active catalog
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
    tbq_n_count: int
    excluded_count: int
    loaded_count: int
    header_map: dict[str, str]
    rows: list[ParsedRow]
    parser_version: str = "3.1.0"


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
    "business_criticality": ["criticidad de negocio", "business criticality"],
    "type": ["tipo", "type"],
    "base": ["base"],
    "interface_status": ["estado interfaz", "interface status"],
    "complexity": ["complejidad", "complexity"],
    "initial_scope": ["alcance inicial", "alcance", "scope"],
    "status": ["estado", "status"],
    "mapping_status": ["estado de mapeo", "mapping status"],
    "source_system": ["sistema de origen", "source system"],
    "source_technology": ["tecnología de origen", "source technology"],
    "source_api_reference": ["api reference", "source api reference", "api ref origen"],
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
    "data_security_classification": [
        "clasificación de datos / seguridad",
        "clasificacion de datos / seguridad",
        "data / security classification",
        "data classification",
    ],
    "frequency": ["frecuencia", "frequency"],
    "is_real_time": ["tiempo real (si/no)", "tiempo real", "real time (yes/no)", "real time"],
    "target_latency_sla": [
        "sla / latencia objetivo",
        "sla/latencia objetivo",
        "sla / target latency",
        "target latency",
    ],
    "trigger_type": ["tipo trigger oic", "trigger type", "tipo de trigger"],
    "response_size_kb": ["response size (kb)", "response size", "tamaño respuesta kb"],
    "payload_per_execution_kb": [
        "payload por ejecución (kb)",
        "payload por ejecucion (kb)",
        "payload por ejecución",
        "payload por ejecucion",
        "payload (kb)",
        "tamaño kb",
        "tamaño en kb",
        "tamano en kb",
    ],
    "is_fan_out": ["fan-out (si/no)", "fan-out", "fan out"],
    "fan_out_targets": ["# destinos", "# destinations", "fan-out targets", "fan out targets"],
    "calendarization": ["calendarización", "calendarizacion", "calendarization", "schedule window"],
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
    "idempotency": ["idempotencia", "idempotency"],
    "retention_processing_window": [
        "retención / ventana de procesamiento",
        "retencion / ventana de procesamiento",
        "retention / processing window",
        "processing window",
    ],
    "core_tools": [
        "herramientas core cuantificables / volumétricas",
        "herramientas core cuantificables / volumetricas",
        "herramientas core",
        "core tools",
        "quantifiable core tools",
        "posibles tools y componentes identificados",
    ],
    "additional_tools_overlays": [
        "herramientas adicionales / overlays (complemento manual)",
        "herramientas adicionales",
        "additional tools",
        "architectural overlays",
        "overlays",
    ],
    "tbq": ["tbq"],
    "owner": ["owner", "dueño"],
    "identified_in": ["identificada en:", "identified in"],
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
    - TBQ controls commercial eligibility, not technical catalog inclusion
    - Estado must NOT be 'Duplicado 2' because it is a known master-workbook defect
    Returns (included, exclusion_reason).
    """
    status = _get(row, header_map, "interface_status") or _get(row, header_map, "status") or ""
    normalized_status = str(status).strip().casefold()
    if normalized_status in {"duplicado 2", "duplicate 2"}:
        return False, "Interface Status = Duplicate 2"

    return True, None


# ---------------------------------------------------------------------------
# Normalization helpers (PRD-019)
# ---------------------------------------------------------------------------

FREQUENCY_ALIASES: dict[str, str] = {
    "diario": "Once per day", "1 vez al dia": "Once per day",
    "una vez al dia": "Once per day",
    "once a day": "Once per day", "once daily": "Once per day",
    "once per day": "Once per day",
    "hourly": "Every hour", "every hour": "Every hour",
    "cada hora": "Every hour", "cada 1 hora": "Every hour",
    "every 5 minutes": "Every 5 minutes", "cada 5 minutos": "Every 5 minutes",
    "every 15 minutes": "Every 15 minutes", "cada 15 minutos": "Every 15 minutes",
    "every 20 minutes": "Every 20 minutes", "cada 20 minutos": "Every 20 minutes",
    "every 30 minutes": "Every 30 minutes", "cada 30 minutos": "Every 30 minutes",
    "every 2 hours": "Every 2 hours", "cada 2 horas": "Every 2 hours",
    "every 4 hours": "Every 4 hours", "cada 4 horas": "Every 4 hours",
    "every 6 hours": "Every 6 hours", "cada 6 horas": "Every 6 hours",
    "4 veces al dia": "Every 6 hours",
    "every 8 hours": "Every 8 hours", "cada 8 horas": "Every 8 hours",
    "every 12 hours": "Every 12 hours", "cada 12 horas": "Every 12 hours",
    "2 veces al dia": "Every 12 hours", "dos veces al dia": "Every 12 hours",
    "real time": "Real Time", "tiempo real": "Real Time",
    "weekly": "Weekly", "semanal": "Weekly",
    "biweekly": "Biweekly", "quincenal": "Biweekly",
    "monthly": "Monthly", "mensual": "Monthly",
    "on demand": "On Demand", "bajo demanda": "On Demand",
}

CONTROLLED_VALUE_ALIASES: dict[str, dict[str, str]] = {
    "complexity": {
        "bajo": "Low", "baja": "Low", "low": "Low",
        "medio": "Medium", "media": "Medium", "medium": "Medium",
        "alto": "High", "alta": "High", "high": "High",
    },
    "business_criticality": {
        "bajo": "Low", "baja": "Low", "low": "Low",
        "medio": "Medium", "media": "Medium", "medium": "Medium",
        "alto": "High", "alta": "High", "high": "High",
        "critica": "Critical", "critical": "Critical",
    },
    "data_security_classification": {
        "publica": "Public", "public": "Public", "interna": "Internal",
        "internal": "Internal", "confidencial": "Confidential",
        "confidential": "Confidential", "restringida": "Restricted",
        "restricted": "Restricted",
    },
    "initial_scope": {"si": "Yes", "yes": "Yes", "y": "Yes", "no": "No", "n": "No"},
    "status": {
        "ya existe": "Already Exists", "already exists": "Already Exists",
        "definitiva (end-state)": "Target State", "target state": "Target State",
        "en revision": "In Review", "in review": "In Review",
        "en progreso": "In Progress", "in progress": "In Progress",
        "tbd": "TBD", "duplicado 1": "Duplicate 1", "duplicate 1": "Duplicate 1",
    },
    "mapping_status": {
        "en analisis": "Under Analysis", "under analysis": "Under Analysis",
        "mapeado": "Mapped", "mapped": "Mapped",
        "pendiente": "Pending", "pending": "Pending",
    },
}
CONTROLLED_VALUE_ALIASES["interface_status"] = CONTROLLED_VALUE_ALIASES["status"]


def _normalize_alias_key(value: str) -> str:
    collapsed = " ".join(value.strip().casefold().split())
    return normalize("NFKD", collapsed).encode("ascii", "ignore").decode("ascii")


def normalize_frequency(raw: Optional[str]) -> tuple[Optional[str], Optional[NormalizationEvent]]:
    if raw is None:
        return None, None
    cleaned = _normalize_alias_key(raw)
    canonical = FREQUENCY_ALIASES.get(cleaned)
    if canonical and canonical != raw.strip():
        return canonical, NormalizationEvent(
            field="frequency", old_value=raw, new_value=canonical, rule="frequency_alias_map"
        )
    return raw.strip() or None, None


def normalize_controlled_value(
    field_name: str,
    raw: Optional[str],
) -> tuple[Optional[str], Optional[NormalizationEvent]]:
    """Map supported legacy labels to the App's English governed contract."""

    if raw is None:
        return None, None
    stripped = raw.strip()
    if not stripped:
        return None, None
    canonical = CONTROLLED_VALUE_ALIASES.get(field_name, {}).get(
        _normalize_alias_key(stripped), stripped
    )
    if canonical != stripped:
        return canonical, NormalizationEvent(
            field=field_name,
            old_value=raw,
            new_value=canonical,
            rule="english_governed_value",
        )
    return canonical, None


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
    tbq_n_count = 0
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
        normalized_tbq = str(raw_tbq or "N").strip().upper()
        is_tbq_y = normalized_tbq == "Y"
        if included:
            if is_tbq_y:
                tbq_y_count += 1
            else:
                tbq_n_count += 1
            # Normalize frequency
            freq_raw = _get(raw_row, header_map, "frequency")
            freq_norm, freq_event = normalize_frequency(str(freq_raw) if freq_raw else None)
            if freq_event:
                events.append(freq_event)
            for field_name in CONTROLLED_VALUE_ALIASES:
                raw_value = _get(raw_row, header_map, field_name)
                _, event = normalize_controlled_value(
                    field_name,
                    str(raw_value) if raw_value is not None else None,
                )
                if event:
                    events.append(event)

            loaded_count += 1
        else:
            excluded_count += 1

        parsed.append(ParsedRow(
            source_row_number=source_row_number,
            raw_data=raw_data,
            included=included,
            exclusion_reason=reason,
            normalization_events=events,
        ))

    return ImportResult(
        source_row_count=len(parsed),
        tbq_y_count=tbq_y_count,
        tbq_n_count=tbq_n_count,
        excluded_count=excluded_count,
        loaded_count=loaded_count,
        header_map=header_map,
        rows=parsed,
    )
