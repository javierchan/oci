"""Focused import-service tests for workbook header fidelity."""

from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import ImportBatch, Project, SourceIntegrationRow
from app.models.project import ImportStatus
from app.services import import_service


def test_build_raw_column_values_preserves_header_labels() -> None:
    raw_headers = import_service._build_raw_header_labels([None, "Interfaz", None])
    raw_values = import_service._build_raw_column_values(
        {"0": "ignored", "1": "Store Master Sync", "2": "Wave 1"},
        raw_headers,
    )

    assert raw_values["Column 1"] == "ignored"
    assert raw_values["Interfaz"] == "Store Master Sync"
    assert raw_values["Column 3"] == "Wave 1"


def test_build_catalog_integration_prefers_header_aliases_over_indexes() -> None:
    header_map = {
        import_service.RAW_HEADERS_METADATA_KEY: json.dumps(
            {
                "1": "#",
                "6": "Interfaz",
                "10": "Alcance Inicial",
                "12": "Frecuencia",
                "17": "Tipo Trigger OIC",
                "19": "Payload por Ejecución (KB)",
                "22": "Sistema de Origen",
                "26": "Sistema de Destino",
                "27": "Tecnología de Destino",
                "40": "TBQ",
                "41": "Incertidumbre",
            },
            ensure_ascii=True,
        )
    }
    integration = import_service._build_catalog_integration(
        project_id="project-1",
        source_row_id="row-1",
        raw_data={
            "#": 1,
            "Interfaz": "Store Master Sync",
            "Alcance Inicial": "Wave 1",
            "Frecuencia": "Una vez al día",
            "Tipo Trigger OIC": "REST Trigger",
            "Payload por Ejecución (KB)": 0,
            "Sistema de Origen": "MFCS",
            "Sistema de Destino": "Oracle ATP",
            "Tecnología de Destino": "SFTP/API Rest",
            "TBQ": "Y",
            "Incertidumbre": "TBD",
        },
        normalization_events=[],
        header_map=header_map,
    )

    assert integration.seq_number == 1
    assert integration.interface_name == "Store Master Sync"
    assert integration.initial_scope == "Wave 1"
    assert integration.trigger_type == "REST Trigger"
    assert integration.payload_per_execution_kb == 0.0
    assert integration.destination_technology_1 == "SFTP"
    assert integration.destination_technology_2 == "API Rest"
    assert integration.uncertainty == "TBD"


def test_normalized_payload_value_converts_mb_header_into_kb() -> None:
    header_map = {
        "payload_per_execution_kb": "19",
        import_service.RAW_HEADERS_METADATA_KEY: json.dumps(
            {"19": "Payload por Ejecución (MB)"},
            ensure_ascii=True,
        ),
    }

    payload_value, payload_event = import_service._normalized_payload_value(
        {"Payload por Ejecución (MB)": 1.5},
        header_map,
    )

    assert payload_value == 1536.0
    assert payload_event == {
        "field": "payload_per_execution_kb",
        "old_value": 1.5,
        "new_value": 1536.0,
        "rule": "payload_unit_mb_to_kb",
    }


def test_normalized_payload_value_keeps_kb_string_values() -> None:
    header_map = {
        "payload_per_execution_kb": "19",
        import_service.RAW_HEADERS_METADATA_KEY: json.dumps(
            {"19": "Payload por Ejecución (KB)"},
            ensure_ascii=True,
        ),
    }

    payload_value, payload_event = import_service._normalized_payload_value(
        {"Payload por Ejecución (KB)": "768 KB"},
        header_map,
    )

    assert payload_value == 768.0
    assert payload_event is None


def test_build_catalog_integration_marks_reference_only_patterns_for_review() -> None:
    header_map = {
        import_service.RAW_HEADERS_METADATA_KEY: json.dumps(
            {
                "1": "#",
                "6": "Interfaz",
                "12": "Frecuencia",
                "17": "Tipo Trigger OIC",
                "19": "Payload por Ejecución (KB)",
                "22": "Sistema de Origen",
                "26": "Sistema de Destino",
                "33": "Patrón",
                "34": "Racional del Patrón",
                "37": "Core Tools",
                "40": "TBQ",
            },
            ensure_ascii=True,
        )
    }

    integration = import_service._build_catalog_integration(
        project_id="project-1",
        source_row_id="row-1",
        raw_data={
            "#": 1,
            "Interfaz": "Webhook Relay",
            "Frecuencia": "Tiempo Real",
            "Tipo Trigger OIC": "Webhook",
            "Payload por Ejecución (KB)": 64,
            "Sistema de Origen": "Shopify",
            "Sistema de Destino": "ATP",
            "Patrón": "#17",
            "Racional del Patrón": "Webhook is distributed to downstream consumers.",
            "Core Tools": "OIC Gen3, OCI Queue, OCI Functions",
            "TBQ": "Y",
        },
        normalization_events=[],
        header_map=header_map,
    )

    assert integration.qa_status == "REVISAR"
    assert integration.qa_reasons is not None
    assert "PATTERN_REFERENCE_ONLY" in integration.qa_reasons


@pytest.mark.asyncio
async def test_import_quality_assistant_summarizes_batch_evidence(test_engine: AsyncEngine) -> None:
    """Verify the import-quality assistant derives read-only batch guidance."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(
            id="project-import-quality-1",
            name="Import Quality Fixture",
            owner_id="analyst",
            status="active",
            description=None,
            project_metadata=None,
        )
        batch = ImportBatch(
            id="batch-import-quality-1",
            project_id=project.id,
            filename="quality.xlsx",
            parser_version="1.0.0",
            status=ImportStatus.COMPLETED,
            header_map={
                "payload_per_execution_kb": "19",
                "selected_pattern": "33",
                "trigger_type": "17",
                "source_system": "22",
                "destination_system": "26",
                import_service.RAW_HEADERS_METADATA_KEY: json.dumps(
                    {
                        "17": "Tipo Trigger OIC",
                        "19": "Payload por Ejecución (KB)",
                        "22": "Sistema de Origen",
                        "26": "Sistema de Destino",
                        "33": "Patrón",
                    }
                ),
            },
        )
        included = SourceIntegrationRow(
            import_batch_id=batch.id,
            source_row_number=6,
            raw_data={
                "Tipo Trigger OIC": "REST Trigger",
                "Payload por Ejecución (KB)": "",
                "Sistema de Origen": "CRM",
                "Sistema de Destino": "ERP",
                "Patrón": "",
            },
            included=True,
            exclusion_reason=None,
            normalization_events=[
                {
                    "field": "payload_per_execution_kb",
                    "old_value": "1 MB",
                    "new_value": 1024,
                    "rule": "payload_unit_mb_to_kb",
                }
            ],
        )
        excluded = SourceIntegrationRow(
            import_batch_id=batch.id,
            source_row_number=7,
            raw_data={"Sistema de Origen": "Legacy"},
            included=False,
            exclusion_reason="TBQ != Y",
            normalization_events=[],
        )
        session.add_all([project, batch, included, excluded])
        await session.commit()

        response = await import_service.get_import_quality_assistant(project.id, batch.id, session)

    assert response.project_id == "project-import-quality-1"
    assert response.batch_id == "batch-import-quality-1"
    assert response.row_count == 2
    assert response.included_count == 1
    assert response.excluded_count == 1
    assert response.normalization_event_count == 1
    assert any(metric.label == "Payload" and metric.value == "0%" for metric in response.metrics)
    assert any(finding.title == "Payload coverage is incomplete" for finding in response.findings)
    assert any(finding.title == "Source rows were excluded" for finding in response.findings)
