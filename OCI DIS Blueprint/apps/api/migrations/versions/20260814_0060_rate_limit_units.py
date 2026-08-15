"""Correct rate-limit units that were inferred as elapsed time or volume.

Revision ID: 20260814_0060
Revises: 20260814_0059
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260814_0060"
down_revision = "20260814_0059"
branch_labels = None
depends_on = None


UNIT_CORRECTIONS = {
    ("QUEUE", "ingress_throughput_mb_s_per_queue"): ("MB", "MB/s"),
    ("QUEUE", "egress_throughput_mb_s_per_queue"): ("MB", "MB/s"),
    ("QUEUE", "max_concurrent_get_rps"): (None, "requests/s"),
    ("QUEUE", "max_message_ops_per_s_per_api_per_queue"): ("seconds", "requests/s"),
    ("STREAMING", "write_throughput_mb_s_per_partition"): ("MB", "MB/s"),
    ("STREAMING", "get_requests_per_s_per_consumer_group_per_partition"): ("seconds", "requests/s"),
}


def _set_unit(service_id: str, limit_key: str, expected: str | None, target: str | None) -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE service_limits AS service_limit
               SET unit = :target,
                   updated_at = CURRENT_TIMESTAMP
              FROM service_capability_profiles AS profile
             WHERE service_limit.service_profile_id = profile.id
               AND profile.service_id = :service_id
               AND service_limit.limit_key = :limit_key
               AND service_limit.unit IS NOT DISTINCT FROM :expected
            """
        ),
        {
            "service_id": service_id,
            "limit_key": limit_key,
            "expected": expected,
            "target": target,
        },
    )


def upgrade() -> None:
    for (service_id, limit_key), (expected, target) in UNIT_CORRECTIONS.items():
        _set_unit(service_id, limit_key, expected, target)


def downgrade() -> None:
    for (service_id, limit_key), (expected, target) in UNIT_CORRECTIONS.items():
        _set_unit(service_id, limit_key, target, expected)
