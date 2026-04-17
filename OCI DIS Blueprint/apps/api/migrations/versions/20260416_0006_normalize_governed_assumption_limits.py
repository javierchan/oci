"""Normalize immutable governed assumption limits across stored versions."""

from __future__ import annotations

from alembic import op

revision = "20260416_0006"
down_revision = "20260416_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE assumption_sets AS target
        SET assumptions = jsonb_set(
            jsonb_set(
                jsonb_set(
                    jsonb_set(
                        jsonb_set(
                            jsonb_set(
                                jsonb_set(
                                    target.assumptions::jsonb,
                                    '{oic_rest_max_payload_kb}',
                                    base.assumptions::jsonb -> 'oic_rest_max_payload_kb',
                                    true
                                ),
                                '{oic_ftp_max_payload_kb}',
                                base.assumptions::jsonb -> 'oic_ftp_max_payload_kb',
                                true
                            ),
                            '{oic_kafka_max_payload_kb}',
                            base.assumptions::jsonb -> 'oic_kafka_max_payload_kb',
                            true
                        ),
                        '{oic_sync_max_duration_s}',
                        base.assumptions::jsonb -> 'oic_sync_max_duration_s',
                        true
                    ),
                    '{api_gw_max_body_kb}',
                    base.assumptions::jsonb -> 'api_gw_max_body_kb',
                    true
                ),
                '{queue_max_message_kb}',
                base.assumptions::jsonb -> 'queue_max_message_kb',
                true
            ),
            '{functions_max_invoke_body_kb}',
            base.assumptions::jsonb -> 'functions_max_invoke_body_kb',
            true
        )::json
        FROM assumption_sets AS base
        WHERE base.version = '1.0.0'
          AND target.version <> '1.0.0'
        """
    )


def downgrade() -> None:
    # Irreversible data normalization.
    pass
