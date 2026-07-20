"""Govern service-limit semantics and adapter-specific OIC payload rules.

Revision ID: 20260717_0040
Revises: 20260717_0039
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "20260717_0040"
down_revision = "20260717_0039"
branch_labels = None
depends_on = None


OIC_SOURCE_URL = (
    "https://docs.oracle.com/en/cloud/paas/application-integration/"
    "oracle-integration-oci/service-limits.html"
)
OIC_ADAPTER_SOURCE_URL = (
    "https://docs.oracle.com/en/cloud/paas/application-integration/"
    "oracle-integration-oci/component-adapters.html"
)
OIC_BILLING_SOURCE_URL = (
    "https://docs.oracle.com/en-us/iaas/application-integration/doc/"
    "how-billing-message-usage-is-calculated-based-feature.html"
)


def _source_url(definition: dict[str, object]) -> str:
    applicability = definition.get("applicability")
    if isinstance(applicability, dict) and "adapter" in applicability:
        return OIC_ADAPTER_SOURCE_URL
    return OIC_SOURCE_URL


OIC_LIMITS: dict[str, dict[str, object]] = {
    "messaging_max_payload_kb": {
        "label": "OIC Messaging payload maximum",
        "value": 10_240,
        "unit": "KB",
        "scope": "component_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"component": "oic_messaging", "payload_mode": "message"},
    },
    "rest_trigger_structured_max_payload_kb": {
        "label": "REST trigger structured payload maximum",
        "value": 102_400,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "REST", "operation": "trigger", "payload_mode": "structured"},
    },
    "rest_invoke_structured_cloud_max_payload_kb": {
        "label": "REST invoke structured cloud payload maximum",
        "value": 102_400,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {
            "adapter": "REST",
            "operation": "invoke",
            "payload_mode": "structured",
            "endpoint_mode": ["public", "private_endpoint"],
        },
    },
    "rest_invoke_structured_agent_max_payload_kb": {
        "label": "REST invoke structured connectivity-agent payload maximum",
        "value": 51_200,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {
            "adapter": "REST",
            "operation": "invoke",
            "payload_mode": "structured",
            "endpoint_mode": "connectivity_agent",
        },
    },
    "rest_raw_max_payload_kb": {
        "label": "REST raw or binary payload maximum",
        "value": 1_048_576,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "REST", "payload_mode": ["raw", "binary"]},
    },
    "rest_attachment_max_payload_kb": {
        "label": "REST attachment payload maximum",
        "value": 1_048_576,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "REST", "payload_mode": "attachment"},
    },
    "rest_json_schema_sample_max_kb": {
        "label": "REST JSON schema sample maximum",
        "value": 100,
        "unit": "KB",
        "scope": "design_time",
        "limit_type": "payload",
        "constraint_kind": "design_time_limit",
        "enforcement": "warn",
        "applicability": {"adapter": "REST", "operation": "schema_sample"},
    },
    "soap_structured_max_payload_kb": {
        "label": "SOAP structured cloud payload maximum",
        "value": 102_400,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {
            "adapter": "SOAP",
            "payload_mode": "structured",
            "endpoint_mode": ["public", "private_endpoint"],
        },
    },
    "soap_structured_agent_max_payload_kb": {
        "label": "SOAP structured connectivity-agent payload maximum",
        "value": 51_200,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {
            "adapter": "SOAP",
            "payload_mode": "structured",
            "endpoint_mode": "connectivity_agent",
        },
    },
    "soap_attachment_max_payload_kb": {
        "label": "SOAP attachment payload maximum",
        "value": 1_048_576,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "SOAP", "payload_mode": "attachment"},
    },
    "kafka_schema_max_payload_kb": {
        "label": "Kafka schema payload maximum",
        "value": 10_240,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "KAFKA", "payload_mode": "structured"},
    },
    "jms_schema_max_payload_kb": {
        "label": "JMS schema payload maximum",
        "value": 10_240,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "JMS", "payload_mode": "structured"},
    },
    "database_outbound_schema_max_payload_kb": {
        "label": "Database outbound schema payload maximum",
        "value": 10_240,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "DATABASE", "operation": "outbound", "payload_mode": "structured"},
    },
    "database_polling_agent_max_payload_kb": {
        "label": "Database polling connectivity-agent payload maximum",
        "value": 51_200,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "DATABASE", "operation": "polling", "endpoint_mode": "connectivity_agent"},
    },
    "database_polling_private_max_payload_kb": {
        "label": "Database polling private-endpoint payload maximum",
        "value": 102_400,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "DATABASE", "operation": "polling", "endpoint_mode": "private_endpoint"},
    },
    "ftp_structured_cloud_max_payload_kb": {
        "label": "FTP structured cloud payload maximum",
        "value": 102_400,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "FTP", "payload_mode": "structured", "endpoint_mode": ["public", "private_endpoint"]},
    },
    "ftp_structured_agent_max_payload_kb": {
        "label": "FTP structured connectivity-agent payload maximum",
        "value": 51_200,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "FTP", "payload_mode": "structured", "endpoint_mode": "connectivity_agent"},
    },
    "ftp_unstructured_max_payload_kb": {
        "label": "FTP unstructured file maximum",
        "value": 1_048_576,
        "unit": "KB",
        "scope": "adapter_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"adapter": "FTP", "payload_mode": "unstructured"},
    },
    "stage_read_entire_file_max_payload_kb": {
        "label": "Stage File read-entire-file maximum",
        "value": 102_400,
        "unit": "KB",
        "scope": "component_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"component": "stage_file", "operation": "read_entire_file"},
    },
    "stage_encrypt_decrypt_max_payload_kb": {
        "label": "Stage File encrypt or decrypt maximum",
        "value": 1_048_576,
        "unit": "KB",
        "scope": "component_operation",
        "limit_type": "payload",
        "constraint_kind": "hard_limit",
        "enforcement": "block_when_applicable",
        "applicability": {"component": "stage_file", "operation": ["encrypt", "decrypt"]},
    },
}


def _json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"))


def upgrade() -> None:
    op.add_column(
        "service_limits",
        sa.Column(
            "constraint_kind",
            sa.String(length=50),
            nullable=False,
            server_default="informational",
        ),
    )
    op.add_column(
        "service_limits",
        sa.Column(
            "enforcement",
            sa.String(length=50),
            nullable=False,
            server_default="inform",
        ),
    )
    op.add_column(
        "service_limits",
        sa.Column(
            "applicability",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )

    bind = op.get_bind()
    now = datetime.now(UTC)

    bind.execute(
        sa.text(
            """
            UPDATE service_limits
               SET constraint_kind = CASE
                       WHEN limit_key = 'billing_threshold_kb' THEN 'billing_granularity'
                       WHEN limit_type = 'payload' THEN 'hard_limit'
                       WHEN can_request_increase THEN 'adjustable_quota'
                       WHEN limit_type = 'quota' THEN 'fixed_quota'
                       ELSE 'informational'
                   END,
                   enforcement = CASE
                       WHEN limit_key = 'billing_threshold_kb' THEN 'calculate'
                       WHEN limit_type = 'payload' THEN 'block_when_applicable'
                       WHEN can_request_increase OR limit_type = 'quota' THEN 'warn'
                       ELSE 'inform'
                   END
            """
        )
    )

    profile_id = bind.scalar(
        sa.text("SELECT id FROM service_capability_profiles WHERE service_id = 'OIC3'")
    )
    if profile_id is not None:
        old_limits = bind.scalar(
            sa.text("SELECT limits FROM service_capability_profiles WHERE id = :id"),
            {"id": profile_id},
        )
        profile_limits = dict(old_limits or {})
        profile_limits.pop("max_message_size_kb", None)
        for key, definition in OIC_LIMITS.items():
            profile_limits[key] = definition["value"]
        profile_limits.update(
            {
                "event_integrations_per_instance": 50,
                "project_max_integrations": 200,
                "project_max_connections": 100,
                "project_max_deployments": 100,
            }
        )
        bind.execute(
            sa.text(
                "UPDATE service_capability_profiles SET limits = CAST(:limits AS JSON), "
                "anti_patterns = :anti_patterns, updated_at = :now WHERE id = :id"
            ),
            {
                "id": profile_id,
                "limits": _json(profile_limits),
                "anti_patterns": (
                    "Payload limits are adapter- and operation-specific; 50 KB is billing granularity, "
                    "not a technical payload ceiling. Use Object Storage references only when the selected "
                    "adapter boundary is exceeded. Synchronous flows are limited to 5 minutes, parallel "
                    "branches to 5, and project resources to their governed quotas."
                ),
                "now": now,
            },
        )
        bind.execute(
            sa.text(
                "UPDATE service_limits SET is_active = false, updated_at = :now "
                "WHERE service_profile_id = :id AND limit_key = 'max_message_size_kb'"
            ),
            {"id": profile_id, "now": now},
        )

        for key, definition in OIC_LIMITS.items():
            existing_id = bind.scalar(
                sa.text(
                    "SELECT id FROM service_limits "
                    "WHERE service_profile_id = :profile_id AND limit_key = :limit_key"
                ),
                {"profile_id": profile_id, "limit_key": key},
            )
            values = {
                "label": definition["label"],
                "scope": definition["scope"],
                "limit_type": definition["limit_type"],
                "constraint_kind": definition["constraint_kind"],
                "enforcement": definition["enforcement"],
                "applicability": _json(definition["applicability"]),
                "value": _json(definition["value"]),
                "unit": definition["unit"],
                "source_url": _source_url(definition),
                "now": now,
            }
            if existing_id is None:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO service_limits (
                            id, service_profile_id, limit_key, label, scope, limit_type,
                            constraint_kind, enforcement, applicability, value, unit,
                            default_value, can_request_increase, source_url,
                            source_retrieved_at, confidence, notes, is_active,
                            created_at, updated_at
                        ) VALUES (
                            :id, :profile_id, :limit_key, :label, :scope, :limit_type,
                            :constraint_kind, :enforcement, CAST(:applicability AS JSON),
                            CAST(:value AS JSON), :unit, NULL, false, :source_url,
                            NULL, 0.95, NULL, true, :now, :now
                        )
                        """
                    ),
                    {
                        **values,
                        "id": str(uuid4()),
                        "profile_id": profile_id,
                        "limit_key": key,
                    },
                )
            else:
                bind.execute(
                    sa.text(
                        """
                        UPDATE service_limits
                           SET label = :label, scope = :scope, limit_type = :limit_type,
                               constraint_kind = :constraint_kind, enforcement = :enforcement,
                               applicability = CAST(:applicability AS JSON), value = CAST(:value AS JSON),
                               unit = :unit, can_request_increase = false, source_url = :source_url,
                               confidence = GREATEST(confidence, 0.95), is_active = true, updated_at = :now
                         WHERE id = :id
                        """
                    ),
                    {**values, "id": existing_id},
                )

        special_semantics = {
            "billing_threshold_kb": ("billing_granularity", "calculate", "billing_message", {"rounding": "ceiling", "applies_to": ["trigger_request", "invoke_response"]}),
            "sync_flow_max_duration_s": ("hard_limit", "block_when_applicable", "integration_runtime", {"execution_model": "synchronous"}),
            "async_scheduled_flow_max_duration_s": ("hard_limit", "block_when_applicable", "integration_runtime", {"execution_model": ["asynchronous", "scheduled"]}),
            "max_parallel_branches": ("hard_limit", "block_when_applicable", "integration_design", {"component": "parallel_action"}),
            "max_invocation_depth": ("hard_limit", "block_when_applicable", "integration_runtime", {"component": "nested_integration"}),
            "project_max_integrations": ("fixed_quota", "warn", "oic_project", {}),
            "project_max_connections": ("fixed_quota", "warn", "oic_project", {}),
            "project_max_deployments": ("fixed_quota", "warn", "oic_project", {}),
        }
        for key, (kind, enforcement, scope, applicability) in special_semantics.items():
            source_url = OIC_BILLING_SOURCE_URL if key == "billing_threshold_kb" else OIC_SOURCE_URL
            bind.execute(
                sa.text(
                    """
                    UPDATE service_limits
                       SET constraint_kind = :kind, enforcement = :enforcement,
                           scope = :scope, applicability = CAST(:applicability AS JSON),
                           source_url = :source_url, updated_at = :now
                     WHERE service_profile_id = :profile_id AND limit_key = :limit_key
                    """
                ),
                {
                    "profile_id": profile_id,
                    "limit_key": key,
                    "kind": kind,
                    "enforcement": enforcement,
                    "scope": scope,
                    "applicability": _json(applicability),
                    "source_url": source_url,
                    "now": now,
                },
            )

    api_gateway_id = bind.scalar(
        sa.text("SELECT id FROM service_capability_profiles WHERE service_id = 'API_GATEWAY'")
    )
    if api_gateway_id is not None:
        bind.execute(
            sa.text(
                """
                UPDATE service_limits
                   SET value = CAST('4' AS JSON), unit = 'KB', constraint_kind = 'hard_limit',
                       enforcement = 'block_when_applicable', scope = 'gateway_response',
                       applicability = CAST('{"response_mode":"stock_response"}' AS JSON),
                       updated_at = :now
                 WHERE service_profile_id = :profile_id
                   AND limit_key = 'max_stock_response_body_kb'
                """
            ),
            {"profile_id": api_gateway_id, "now": now},
        )


def downgrade() -> None:
    bind = op.get_bind()
    profile_id = bind.scalar(
        sa.text("SELECT id FROM service_capability_profiles WHERE service_id = 'OIC3'")
    )
    if profile_id is not None:
        for limit_key in OIC_LIMITS:
            bind.execute(
                sa.text(
                    "DELETE FROM service_limits "
                    "WHERE service_profile_id = :id AND limit_key = :limit_key"
                ),
                {"id": profile_id, "limit_key": limit_key},
            )
        bind.execute(
            sa.text(
                "UPDATE service_limits SET is_active = true "
                "WHERE service_profile_id = :id AND limit_key = 'max_message_size_kb'"
            ),
            {"id": profile_id},
        )
    op.drop_column("service_limits", "applicability")
    op.drop_column("service_limits", "enforcement")
    op.drop_column("service_limits", "constraint_kind")
