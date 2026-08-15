"""Bind core service limits to their canonical Oracle limit pages.

Revision ID: 20260814_0059
Revises: 20260814_0058
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260814_0059"
down_revision = "20260814_0058"
branch_labels = None
depends_on = None


SOURCE_ASSIGNMENTS = {
    "API_GATEWAY": (
        "https://docs.oracle.com/en-us/iaas/Content/APIGateway/home.htm",
        "https://docs.oracle.com/en-us/iaas/Content/APIGateway/Reference/apigatewaylimits.htm",
    ),
    "STREAMING": (
        "https://docs.oracle.com/en-us/iaas/Content/Streaming/home.htm",
        "https://docs.oracle.com/en-us/iaas/Content/Streaming/Concepts/streamingoverview_topic-Limits_on_Streaming_Resources.htm",
    ),
    "QUEUE": (
        "https://docs.oracle.com/en-us/iaas/Content/queue/home.htm",
        "https://docs.oracle.com/en-us/iaas/Content/queue/overview.htm",
    ),
}


def _rebind(service_id: str, source_url: str, target_url: str) -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE service_limits AS service_limit
               SET source_url = :target_url,
                   updated_at = CURRENT_TIMESTAMP
              FROM service_capability_profiles AS profile
             WHERE service_limit.service_profile_id = profile.id
               AND profile.service_id = :service_id
               AND service_limit.source_url = :source_url
            """
        ),
        {
            "service_id": service_id,
            "source_url": source_url,
            "target_url": target_url,
        },
    )


def upgrade() -> None:
    for service_id, (source_url, target_url) in SOURCE_ASSIGNMENTS.items():
        _rebind(service_id, source_url, target_url)


def downgrade() -> None:
    for service_id, (source_url, target_url) in SOURCE_ASSIGNMENTS.items():
        _rebind(service_id, target_url, source_url)
