"""Move service-owned rules out of versioned client assumptions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260710_0014"
down_revision = "20260607_0013"
branch_labels = None
depends_on = None


SERVICE_RULE_DEFAULTS: dict[str, object] = {
    "oic_rest_max_payload_kb": 10240,
    "oic_ftp_max_payload_kb": 10240,
    "oic_kafka_max_payload_kb": 10240,
    "oic_rest_raw_max_payload_kb": 1048576,
    "oic_rest_attachment_max_payload_kb": 1048576,
    "oic_rest_json_schema_max_payload_kb": 102400,
    "oic_soap_max_payload_kb": 51200,
    "oic_soap_attachment_max_payload_kb": 1048576,
    "oic_ftp_stage_file_max_payload_kb": 10485760,
    "oic_sync_max_duration_s": 300,
    "oic_async_max_duration_s": 21600,
    "oic_max_parallel_branches": 5,
    "oic_max_invocation_depth": 16,
    "oic_sync_concurrency_new": 100,
    "oic_sync_concurrency_byol": 400,
    "oic_async_concurrency_new": 50,
    "oic_async_concurrency_byol": 200,
    "oic_pack_size_msgs_per_hour_byol": 20000,
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
    "api_gw_max_body_kb": 20480,
    "api_gw_max_function_body_kb": 6144,
    "api_gw_backend_timeout_max_s": 300,
    "api_gw_max_routes_per_deployment": 50,
    "api_gw_max_deployments_per_gateway": 20,
    "streaming_partition_throughput_mb_s": 1.0,
    "streaming_read_throughput_mb_s": 2.0,
    "streaming_max_message_kb": 1024,
    "streaming_max_message_size_mb": 1.0,
    "streaming_retention_days": 7,
    "streaming_get_rps_per_consumer_group_per_partition": 5,
    "streaming_max_consumer_groups_per_stream": 50,
    "streaming_max_partitions_muc": 200,
    "streaming_max_partitions_payg": 50,
    "functions_max_invoke_body_kb": 6144,
    "functions_sla_pct": 99.5,
    "functions_max_timeout_s": 300,
    "queue_billing_unit_kb": 64,
    "queue_max_message_kb": 256,
    "queue_max_inflight_messages": 100000,
    "queue_max_queues_per_region": 10,
    "queue_ingress_throughput_mb_s": 10,
    "queue_egress_throughput_mb_s": 10,
    "queue_max_storage_per_queue_gb": 2,
    "queue_retention_days": 7,
    "data_integration_workspaces_per_region": 5,
    "data_integration_deleted_workspace_retention_days": 15,
}

BUSINESS_METADATA_KEYS = {
    "salesforce_batch_limit_millions",
    "file_server_concurrent_connections",
    "default_record_size_bytes",
    "hours_per_month",
}


def _assumption_table() -> sa.TableClause:
    return sa.table(
        "assumption_sets",
        sa.column("id", sa.String()),
        sa.column("assumptions", sa.JSON()),
    )


def upgrade() -> None:
    table = _assumption_table()
    connection = op.get_bind()
    rows = connection.execute(sa.select(table.c.id, table.c.assumptions)).mappings().all()
    for row in rows:
        assumptions = dict(row["assumptions"] or {})
        legacy_metadata = assumptions.pop("service_metadata", {})
        assumptions.pop("source_references", None)
        for key in SERVICE_RULE_DEFAULTS:
            assumptions.pop(key, None)
        if isinstance(legacy_metadata, dict):
            business_metadata = {
                key: value
                for key, value in legacy_metadata.items()
                if key in BUSINESS_METADATA_KEYS
            }
            if business_metadata:
                assumptions["business_metadata"] = business_metadata
        connection.execute(
            table.update().where(table.c.id == row["id"]).values(assumptions=assumptions)
        )


def downgrade() -> None:
    table = _assumption_table()
    connection = op.get_bind()
    rows = connection.execute(sa.select(table.c.id, table.c.assumptions)).mappings().all()
    for row in rows:
        assumptions = dict(SERVICE_RULE_DEFAULTS)
        assumptions.update(dict(row["assumptions"] or {}))
        connection.execute(
            table.update().where(table.c.id == row["id"]).values(assumptions=assumptions)
        )
