"""Add request payload to service verification jobs."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260607_0013"
down_revision = "20260607_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_verification_jobs",
        sa.Column("request_payload", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("service_verification_jobs", "request_payload")
