"""Seed reference data for patterns, dictionary options, and assumptions."""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.db import get_sync_database_url
from app.models import AssumptionSet, AuditEvent, DictionaryOption, PatternDefinition, PromptTemplateVersion

PATTERNS: list[dict[str, str]] = [
    {"pattern_id": "#01", "name": "Request-Reply", "category": "SÍNCRONO"},
    {"pattern_id": "#02", "name": "Scheduled Batch Transfer", "category": "ASÍNCRONO"},
    {"pattern_id": "#03", "name": "Event-Driven Push", "category": "ASÍNCRONO"},
    {"pattern_id": "#04", "name": "Polling Sync", "category": "ASÍNCRONO"},
    {"pattern_id": "#05", "name": "Data Replication", "category": "ASÍNCRONO"},
    {"pattern_id": "#06", "name": "Saga / Compensation", "category": "SÍNCRONO + ASÍNCRONO"},
    {"pattern_id": "#07", "name": "Fanout Broadcast", "category": "ASÍNCRONO"},
    {"pattern_id": "#08", "name": "Aggregation & Enrichment", "category": "SÍNCRONO"},
    {"pattern_id": "#09", "name": "File Transfer (FTP/SFTP)", "category": "ASÍNCRONO"},
    {"pattern_id": "#10", "name": "DB Integration (ORDS/JDBC)", "category": "SÍNCRONO"},
    {"pattern_id": "#11", "name": "ERP Adapter Integration", "category": "ASÍNCRONO"},
    {"pattern_id": "#12", "name": "Message Queue Relay", "category": "ASÍNCRONO"},
    {"pattern_id": "#13", "name": "API-Led Connectivity", "category": "SÍNCRONO"},
    {"pattern_id": "#14", "name": "Streaming Ingest", "category": "ASÍNCRONO"},
    {"pattern_id": "#15", "name": "Hybrid Orchestration", "category": "SÍNCRONO + ASÍNCRONO"},
    {"pattern_id": "#16", "name": "B2B/EDI Gateway", "category": "ASÍNCRONO"},
    {"pattern_id": "#17", "name": "AI-Augmented Integration", "category": "ASÍNCRONO"},
]

ASSUMPTION_SET = {
    "version": "1.0.0",
    "label": "Workbook TPL - Supuestos v1",
    "is_default": True,
    "assumptions": {
        "oic_rest_max_payload_kb": 50000,
        "oic_ftp_max_payload_kb": 50000,
        "oic_kafka_max_payload_kb": 10000,
        "oic_timeout_s": 300,
        "oic_billing_threshold_kb": 50,
        "oic_pack_size_msgs_per_hour": 5000,
        "month_days": 30,
        "streaming_partition_throughput_mb_s": 1.0,
        "functions_default_duration_ms": 200,
        "functions_default_memory_mb": 256,
        "functions_default_concurrency": 1,
    },
    "notes": "Seeded from workbook TPL - Supuestos.",
}

DICTIONARY_OPTIONS: list[dict[str, object]] = [
    {"category": "FREQUENCY", "code": "FREQ-01", "value": "Una vez al día", "executions_per_day": 1.0, "sort_order": 1},
    {"category": "FREQUENCY", "code": "FREQ-02", "value": "2 veces al día", "executions_per_day": 2.0, "sort_order": 2},
    {"category": "FREQUENCY", "code": "FREQ-03", "value": "4 veces al día", "executions_per_day": 4.0, "sort_order": 3},
    {"category": "FREQUENCY", "code": "FREQ-04", "value": "Cada hora", "executions_per_day": 24.0, "sort_order": 4},
    {"category": "FREQUENCY", "code": "FREQ-05", "value": "Cada 30 minutos", "executions_per_day": 48.0, "sort_order": 5},
    {"category": "FREQUENCY", "code": "FREQ-06", "value": "Cada 15 minutos", "executions_per_day": 96.0, "sort_order": 6},
    {"category": "FREQUENCY", "code": "FREQ-07", "value": "Cada 5 minutos", "executions_per_day": 288.0, "sort_order": 7},
    {"category": "FREQUENCY", "code": "FREQ-08", "value": "Cada minuto", "executions_per_day": 1440.0, "sort_order": 8},
    {"category": "FREQUENCY", "code": "FREQ-09", "value": "Tiempo real", "executions_per_day": 1440.0, "sort_order": 9},
    {"category": "FREQUENCY", "code": "FREQ-10", "value": "Semanal", "executions_per_day": 0.142857, "sort_order": 10},
    {"category": "FREQUENCY", "code": "FREQ-11", "value": "Mensual", "executions_per_day": 0.033333, "sort_order": 11},
    {"category": "FREQUENCY", "code": "FREQ-12", "value": "Bajo demanda", "executions_per_day": 1.0, "sort_order": 12},
    {"category": "FREQUENCY", "code": "FREQ-13", "value": "TBD", "executions_per_day": None, "sort_order": 13},
    {"category": "TRIGGER_TYPE", "code": None, "value": "Scheduled", "sort_order": 1},
    {"category": "TRIGGER_TYPE", "code": None, "value": "REST", "sort_order": 2},
    {"category": "TRIGGER_TYPE", "code": None, "value": "Event", "sort_order": 3},
    {"category": "TRIGGER_TYPE", "code": None, "value": "FTP/SFTP", "sort_order": 4},
    {"category": "TRIGGER_TYPE", "code": None, "value": "DB Polling", "sort_order": 5},
    {"category": "TRIGGER_TYPE", "code": None, "value": "JMS", "sort_order": 6},
    {"category": "TRIGGER_TYPE", "code": None, "value": "Kafka", "sort_order": 7},
    {"category": "TRIGGER_TYPE", "code": None, "value": "Webhook", "sort_order": 8},
    {"category": "TRIGGER_TYPE", "code": None, "value": "SOAP", "sort_order": 9},
    {"category": "COMPLEXITY", "code": None, "value": "Bajo", "sort_order": 1},
    {"category": "COMPLEXITY", "code": None, "value": "Medio", "sort_order": 2},
    {"category": "COMPLEXITY", "code": None, "value": "Alto", "sort_order": 3},
    {"category": "QA_STATUS", "code": None, "value": "OK", "sort_order": 1},
    {"category": "QA_STATUS", "code": None, "value": "REVISAR", "sort_order": 2},
    {"category": "QA_STATUS", "code": None, "value": "PENDING", "sort_order": 3},
    {"category": "TOOLS", "code": None, "value": "OIC Gen3", "sort_order": 1},
    {"category": "TOOLS", "code": None, "value": "OCI API Gateway", "sort_order": 2},
    {"category": "TOOLS", "code": None, "value": "OCI Streaming", "sort_order": 3},
    {"category": "TOOLS", "code": None, "value": "OCI Queue", "sort_order": 4},
    {"category": "TOOLS", "code": None, "value": "Oracle Functions", "sort_order": 5},
    {"category": "TOOLS", "code": None, "value": "OCI Data Integration", "sort_order": 6},
    {"category": "TOOLS", "code": None, "value": "Oracle ORDS", "sort_order": 7},
    {"category": "TOOLS", "code": None, "value": "ATP", "sort_order": 8},
    {"category": "TOOLS", "code": None, "value": "Oracle DB", "sort_order": 9},
    {"category": "TOOLS", "code": None, "value": "SFTP", "sort_order": 10},
    {"category": "TOOLS", "code": None, "value": "OCI Object Storage", "sort_order": 11},
    {"category": "TOOLS", "code": None, "value": "OCI APM", "sort_order": 12},
]

PROMPT_TEMPLATE = {
    "version": "1.0.0",
    "name": "Deterministic Justification Template",
    "is_default": True,
    "template_config": {
        "summary": (
            "La integracion {interface_name} conecta {source_system} con {destination_system} "
            "y actualmente mantiene estado QA {qa_status}."
        ),
        "blocks": [
            {
                "title": "Contexto",
                "body": (
                    "Interfaz {interface_id} para la marca {brand} dentro del proceso {business_process}. "
                    "Opera con frecuencia {frequency} y {payload_text}."
                ),
            },
            {
                "title": "Patron",
                "body": (
                    "Se documenta {pattern_label}. Racional: {pattern_rationale}."
                ),
            },
            {
                "title": "Implementacion",
                "body": (
                    "Tipo {type}, trigger {trigger_type} y herramientas base {core_tools}. "
                    "Politica de reintento: {retry_policy}."
                ),
            },
            {
                "title": "Gobierno QA",
                "body": "Estado QA {qa_status}. Observaciones: {qa_reasons}.",
            },
        ],
    },
    "notes": "Seeded default template for deterministic methodology narratives.",
}


def _audit(session: Session, event_type: str, entity_type: str, entity_id: str, new_value: dict[str, object]) -> None:
    session.add(
        AuditEvent(
            project_id=None,
            actor_id="system-seed",
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=None,
            new_value=new_value,
        )
    )


def seed_patterns(session: Session) -> int:
    count = 0
    for pattern_data in PATTERNS:
        existing = session.scalar(
            select(PatternDefinition).where(PatternDefinition.pattern_id == pattern_data["pattern_id"])
        )
        if existing is None:
            existing = PatternDefinition(**pattern_data)
            session.add(existing)
            session.flush()
            _audit(session, "seed_insert", "pattern_definition", existing.id, pattern_data)
            count += 1
        else:
            existing.name = pattern_data["name"]
            existing.category = pattern_data["category"]
    return count


def seed_dictionary_options(session: Session) -> int:
    count = 0
    for option_data in DICTIONARY_OPTIONS:
        existing = session.scalar(
            select(DictionaryOption).where(
                DictionaryOption.category == option_data["category"],
                DictionaryOption.value == option_data["value"],
            )
        )
        if existing is None:
            existing = DictionaryOption(
                category=str(option_data["category"]),
                code=option_data.get("code"),
                value=str(option_data["value"]),
                executions_per_day=option_data.get("executions_per_day"),
                sort_order=int(option_data["sort_order"]),
            )
            session.add(existing)
            session.flush()
            _audit(session, "seed_insert", "dictionary_option", existing.id, option_data)
            count += 1
        else:
            existing.code = option_data.get("code")
            existing.executions_per_day = option_data.get("executions_per_day")
            existing.sort_order = int(option_data["sort_order"])
    return count


def seed_assumption_set(session: Session) -> int:
    existing = session.scalar(
        select(AssumptionSet).where(AssumptionSet.version == ASSUMPTION_SET["version"])
    )
    if existing is None:
        existing = AssumptionSet(**ASSUMPTION_SET)
        session.add(existing)
        session.flush()
        _audit(
            session,
            "seed_insert",
            "assumption_set",
            existing.id,
            {"version": ASSUMPTION_SET["version"]},
        )
        return 1
    existing.label = str(ASSUMPTION_SET["label"])
    existing.is_default = bool(ASSUMPTION_SET["is_default"])
    existing.assumptions = dict(ASSUMPTION_SET["assumptions"])
    existing.notes = ASSUMPTION_SET["notes"]
    return 0


def seed_prompt_template(session: Session) -> int:
    existing = session.scalar(
        select(PromptTemplateVersion).where(PromptTemplateVersion.version == PROMPT_TEMPLATE["version"])
    )
    if existing is None:
        existing = PromptTemplateVersion(**PROMPT_TEMPLATE)
        session.add(existing)
        session.flush()
        _audit(
            session,
            "seed_insert",
            "prompt_template_version",
            existing.id,
            {"version": PROMPT_TEMPLATE["version"]},
        )
        return 1
    existing.name = str(PROMPT_TEMPLATE["name"])
    existing.is_default = bool(PROMPT_TEMPLATE["is_default"])
    existing.template_config = dict(PROMPT_TEMPLATE["template_config"])
    existing.notes = PROMPT_TEMPLATE["notes"]
    return 0


def main() -> None:
    engine = create_engine(get_sync_database_url())
    with Session(engine) as session:
        patterns = seed_patterns(session)
        assumptions = seed_assumption_set(session)
        dictionary_options = seed_dictionary_options(session)
        prompt_templates = seed_prompt_template(session)
        session.commit()
        print(
            "Seed complete: "
            f"patterns={patterns}, assumptions={assumptions}, "
            f"dictionary_options={dictionary_options}, prompt_templates={prompt_templates}"
        )


if __name__ == "__main__":
    main()
