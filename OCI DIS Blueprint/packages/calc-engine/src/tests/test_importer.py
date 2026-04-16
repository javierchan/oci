"""
Import parity tests (PRD-051).

Benchmark expectations from workbook TBQ Audit tab:
  - 157 source rows with TBQ=Y
  - 13 excluded (Duplicado 2)
  - 144 loaded in exact order
"""
from ..engine.importer import parse_rows, should_include, normalize_frequency, build_header_map


def _make_header_row():
    """Minimal header row matching source file structure (row 5, 0-based idx 4)."""
    return [
        "#", "ID de interfaz", "Owner", "Marca", "Proceso de Negocio",
        "Interfaz", "Descripción", "Estado", "Estado de Mapeo",
        "Alcance Inicial", "Complejidad", "Frecuencia", "Tipo",
        "Base", "Estado Interfaz", "Tiempo Real (Si/No)", "Tipo Trigger OIC",
        "Response Size (KB)", "Payload por Ejecución (KB)", "Fan-out (Si/No)",
        "# Destinos", "Sistema de Origen", "Tecnología de Origen",
        "API Reference", "Propietario de Origen", "Sistema de Destino",
        "Tecnología de Destino #1", "Tecnología de Destino #2",
        "Propietario de Destino", "Calendarización", "Ejec /día",
        "Payload por hora (KB)", "Patrón Seleccionado (Manual)",
        "Racional del Patrón (Manual)", "Comentarios / Observaciones",
        "Retry Policy", "Herramientas Core", "Herramientas Adicionales", "QA",
        "TBQ",
    ]


def _make_valid_row(seq=1, tbq="Y", estado="Definitiva (End-State)"):
    row = [""] * 40
    row[0] = seq       # #
    row[7] = estado    # Estado
    row[39] = tbq      # TBQ
    return row


def _make_workbook_header_row():
    """Header row matching the ADN workbook with a leading blank column."""
    return [
        None,
        "#",
        "ID de interfaz",
        "Owner",
        "Marca",
        "Proceso de Negocio",
        "Interfaz",
        "Descripción",
        "Estado",
        "Estado de Mapeo",
        "Alcance Inicial",
        "Complejidad",
        "Frecuencia",
        "Tipo",
        "Base",
        "Estado Interfaz",
        "Tiempo Real (Si/No)",
        "Tipo Trigger OIC",
        "Response Size (KB)",
        "Payload por Ejecución (KB)",
        "Fan-out (Si/No)",
        "# Destinos",
        "Sistema de Origen",
        "Tecnología de Origen",
        "API Reference",
        "Propietario de Origen",
        "Sistema de Destino",
        "Tecnología de Destino #1",
        "Tecnología de Destino #2",
        "Propietario de Destino",
        "Calendarización",
        "Ejec /día",
        "Payload por hora (KB)",
        "Patrón Seleccionado (Manual)",
        "Racional del Patrón (Manual)",
        "Comentarios / Observaciones",
        "Retry Policy",
        "Herramientas Core Cuantificables / Volumétricas",
        "Herramientas Adicionales / Overlays (Complemento manual)",
        "QA",
        "TBQ",
        "Incertidumbre",
    ]


def _make_workbook_data_row():
    row = [None] * 42
    row[1] = 1
    row[6] = "Store Master Sync"
    row[10] = "Wave 1"
    row[12] = "Una vez al día"
    row[17] = "REST Trigger"
    row[19] = 0
    row[27] = "SFTP"
    row[28] = "API Rest"
    row[40] = "Y"
    row[41] = "TBD"
    return row


# ---------------------------------------------------------------------------
# Header map
# ---------------------------------------------------------------------------

def test_header_map_finds_tbq():
    headers = _make_header_row()
    hmap = build_header_map(headers)
    assert "tbq" in hmap


def test_header_map_finds_interface_id():
    headers = _make_header_row()
    hmap = build_header_map(headers)
    assert "interface_id" in hmap


def test_header_map_prefers_named_workbook_headers():
    headers = _make_workbook_header_row()
    hmap = build_header_map(headers)
    assert hmap["interface_name"] == "6"
    assert hmap["initial_scope"] == "10"
    assert hmap["trigger_type"] == "17"


def test_header_map_handles_accent_variants():
    headers = [None, "Patron Seleccionado (Manual)", "Herramientas Core Cuantificables / Volumetricas"]
    hmap = build_header_map(headers)
    assert hmap["selected_pattern"] == "1"
    assert hmap["core_tools"] == "2"


# ---------------------------------------------------------------------------
# Inclusion rules (PRD-017)
# ---------------------------------------------------------------------------

def test_include_tbq_y():
    headers = _make_header_row()
    hmap = build_header_map(headers)
    row = _make_valid_row(tbq="Y")
    included, reason = should_include(row, hmap)
    assert included is True
    assert reason is None


def test_exclude_tbq_n():
    headers = _make_header_row()
    hmap = build_header_map(headers)
    row = _make_valid_row(tbq="N")
    included, reason = should_include(row, hmap)
    assert included is False


def test_exclude_duplicado_2():
    headers = _make_header_row()
    hmap = build_header_map(headers)
    row = _make_valid_row(tbq="Y", estado="Duplicado 2")
    included, reason = should_include(row, hmap)
    assert included is False
    assert "Duplicado 2" in reason


def test_include_duplicado_1():
    headers = _make_header_row()
    hmap = build_header_map(headers)
    row = _make_valid_row(tbq="Y", estado="Duplicado 1")
    included, reason = should_include(row, hmap)
    assert included is True


# ---------------------------------------------------------------------------
# Normalization (PRD-019)
# ---------------------------------------------------------------------------

def test_frequency_normalization_alias():
    norm, event = normalize_frequency("diario")
    assert norm == "Una vez al día"
    assert event is not None
    assert event.rule == "frequency_alias_map"


def test_frequency_no_normalization_needed():
    norm, event = normalize_frequency("Una vez al día")
    assert event is None


def test_frequency_none():
    norm, event = normalize_frequency(None)
    assert norm is None
    assert event is None


# ---------------------------------------------------------------------------
# Full parse (parity targets from TBQ Audit)
# ---------------------------------------------------------------------------

def _build_parity_dataset():
    """
    Simulate 170 source rows:
      - 157 with TBQ=Y (13 of which are Duplicado 2)
      - 13 with TBQ=N
    Expected: loaded = 157 - 13 = 144
    """
    header_row = _make_header_row()
    rows = [
        [""] * 5,     # Row 1: meta
        [""] * 5,     # Row 2: meta
        [""] * 5,     # Row 3: meta
        [""] * 5,     # Row 4: meta (header at index 4)
        header_row,   # Index 4 (row 5 in 1-based)
    ]
    # 13 TBQ=N
    for i in range(13):
        rows.append(_make_valid_row(seq=i+1, tbq="N"))
    # 13 TBQ=Y Duplicado 2
    for i in range(13):
        rows.append(_make_valid_row(seq=i+14, tbq="Y", estado="Duplicado 2"))
    # 144 valid TBQ=Y
    for i in range(144):
        rows.append(_make_valid_row(seq=i+27, tbq="Y"))
    return rows


def test_parity_loaded_count():
    rows = _build_parity_dataset()
    result = parse_rows(rows)
    assert result.loaded_count == 144, f"Expected 144, got {result.loaded_count}"


def test_parity_excluded_count():
    rows = _build_parity_dataset()
    result = parse_rows(rows)
    assert result.excluded_count == 13


def test_parity_order_preserved():
    rows = _build_parity_dataset()
    result = parse_rows(rows)
    included = [r for r in result.rows if r.included]
    seq_numbers = [r.raw_data.get("0") for r in included]
    assert seq_numbers == sorted(seq_numbers), "Source order must be preserved (PRD-018)"


def test_parse_rows_preserves_zero_payload_and_workbook_values() -> None:
    rows = [
        [""] * 5,
        [""] * 5,
        [""] * 5,
        [""] * 5,
        _make_workbook_header_row(),
        _make_workbook_data_row(),
    ]
    result = parse_rows(rows)
    assert result.loaded_count == 1
    assert result.rows[0].raw_data["19"] == 0
    assert result.rows[0].raw_data["17"] == "REST Trigger"
    assert result.rows[0].raw_data["41"] == "TBD"
