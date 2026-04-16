"""Seed reference data for patterns, dictionary options, and assumptions."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.db import get_sync_database_url
from app.models import AssumptionSet, AuditEvent, DictionaryOption, PatternDefinition, PromptTemplateVersion
from app.migrations.reference_seed_data import DICTIONARY_OPTIONS, PATTERNS

ASSUMPTION_SET = {
    "version": "1.0.0",
    "label": "Workbook TPL - Supuestos v1",
    "is_default": True,
    "assumptions": {
        "oic_rest_max_payload_kb": 51200,
        "oic_ftp_max_payload_kb": 51200,
        "oic_kafka_max_payload_kb": 10240,
        "oic_rest_raw_max_payload_kb": 1048576,
        "oic_rest_attachment_max_payload_kb": 1048576,
        "oic_rest_json_schema_max_payload_kb": 102400,
        "oic_soap_max_payload_kb": 51200,
        "oic_soap_attachment_max_payload_kb": 1048576,
        "oic_ftp_stage_file_max_payload_kb": 10485760,
        "oic_timeout_s": 300,
        "oic_db_stored_proc_timeout_s": 240,
        "oic_db_polling_max_payload_kb": 10240,
        "oic_outbound_read_timeout_s": 300,
        "oic_outbound_connection_timeout_s": 300,
        "oic_agent_connection_timeout_s": 240,
        "oic_billing_threshold_kb": 50,
        "oic_pack_size_msgs_per_hour": 5000,
        "oic_byol_pack_size_msgs_per_hour": 20000,
        "oic_project_max_integrations": 100,
        "oic_project_max_deployments": 50,
        "oic_project_max_connections": 20,
        "month_days": 31,
        "streaming_partition_throughput_mb_s": 1.0,
        "streaming_read_throughput_mb_s": 2.0,
        "streaming_max_message_size_mb": 1.0,
        "streaming_retention_days": 7,
        "streaming_default_partitions": 200,
        "functions_default_duration_ms": 2000,
        "functions_default_memory_mb": 256,
        "functions_default_concurrency": 1,
        "functions_max_timeout_s": 300,
        "functions_batch_size_records": 500,
        "queue_billing_unit_kb": 64,
        "queue_max_message_kb": 256,
        "queue_retention_days": 7,
        "queue_throughput_soft_limit_msgs_per_second": 10,
        "data_integration_workspaces_per_region": 5,
        "data_integration_deleted_workspace_retention_days": 15,
        "source_references": {
            "oic_limits": "TPL - Supuestos: OCI Gen3 official service limits",
            "oic_billing": "TPL - Supuestos: OIC billing message and pack guidance",
            "streaming_limits": "TPL - Supuestos: OCI Streaming service limits",
            "functions_limits": "TPL - Supuestos: OCI Functions operational limits",
            "queue_limits": "TPL - Supuestos: OCI Queue limits and pricing unit",
            "data_integration_limits": "TPL - Supuestos: OCI Data Integration regional limits",
            "data_integrator_proxy_usage": "TPL - Supuestos: Data Integrator uses jobs/month proxy guidance",
        },
        "service_metadata": {
            "data_integrator_usage_model": "Jobs/month (proxy)",
            "data_integration_compute_isolated": True,
            "functions_cold_start_typical": "10-20 sec",
            "functions_ram_default_per_ad": 60,
            "salesforce_batch_limit_millions": 8,
            "file_server_concurrent_connections": 50,
            "default_record_size_bytes": 250,
            "hours_per_month": 744,
        },
    },
    "notes": "Seeded from workbook TPL - Supuestos.",
}

PROMPT_TEMPLATE: dict[str, Any] = {
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
            existing = PatternDefinition(**pattern_data, is_system=True)
            session.add(existing)
            session.flush()
            _audit(session, "seed_insert", "pattern_definition", existing.id, cast(dict[str, object], pattern_data))
            count += 1
        else:
            existing.name = pattern_data["name"]
            existing.category = pattern_data["category"]
            existing.description = cast(str | None, pattern_data.get("description"))
            existing.oci_components = cast(str | None, pattern_data.get("oci_components"))
            existing.when_to_use = cast(str | None, pattern_data.get("when_to_use"))
            existing.when_not_to_use = cast(str | None, pattern_data.get("when_not_to_use"))
            existing.technical_flow = cast(str | None, pattern_data.get("technical_flow"))
            existing.business_value = cast(str | None, pattern_data.get("business_value"))
            existing.is_system = True
            existing.version = "1.0.0"
            continue
        existing.description = cast(str | None, pattern_data.get("description"))
        existing.oci_components = cast(str | None, pattern_data.get("oci_components"))
        existing.when_to_use = cast(str | None, pattern_data.get("when_to_use"))
        existing.when_not_to_use = cast(str | None, pattern_data.get("when_not_to_use"))
        existing.technical_flow = cast(str | None, pattern_data.get("technical_flow"))
        existing.business_value = cast(str | None, pattern_data.get("business_value"))
        existing.version = "1.0.0"
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
                code=cast(str | None, option_data.get("code")),
                value=str(option_data["value"]),
                description=cast(str | None, option_data.get("description")),
                executions_per_day=cast(float | None, option_data.get("executions_per_day")),
                is_volumetric=cast(bool | None, option_data.get("is_volumetric")),
                sort_order=int(cast(int, option_data["sort_order"])),
                is_active=bool(option_data.get("is_active", True)),
                version=cast(str, option_data.get("version", "1.0.0")),
            )
            session.add(existing)
            session.flush()
            _audit(session, "seed_insert", "dictionary_option", existing.id, option_data)
            count += 1
        else:
            existing.code = cast(str | None, option_data.get("code"))
            existing.description = cast(str | None, option_data.get("description"))
            existing.executions_per_day = cast(float | None, option_data.get("executions_per_day"))
            existing.is_volumetric = cast(bool | None, option_data.get("is_volumetric"))
            existing.sort_order = int(cast(int, option_data["sort_order"]))
            existing.is_active = bool(option_data.get("is_active", True))
            existing.version = cast(str, option_data.get("version", "1.0.0"))
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
    existing.assumptions = cast(dict[str, Any], dict(cast(dict[str, Any], ASSUMPTION_SET["assumptions"])))
    existing.notes = cast(str | None, ASSUMPTION_SET["notes"])
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
    existing.template_config = cast(dict[str, Any], dict(PROMPT_TEMPLATE["template_config"]))
    existing.notes = cast(str | None, PROMPT_TEMPLATE["notes"])
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
