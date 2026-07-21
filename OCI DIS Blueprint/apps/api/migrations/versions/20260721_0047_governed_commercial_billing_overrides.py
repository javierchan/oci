"""Govern per-SKU commercial billing semantic overrides.

Revision ID: 20260721_0047
Revises: 20260721_0046
Create Date: 2026-07-21
"""

from datetime import UTC, datetime
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "20260721_0047"
down_revision = "20260721_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    overrides = op.create_table(
        "commercial_billing_semantic_overrides",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("part_number", sa.String(length=50), nullable=False),
        sa.Column("allow_decimal_quantity", sa.Boolean(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approved_by", sa.String(length=100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "part_number", name="uq_commercial_billing_override_part_number"
        ),
    )
    op.create_index(
        "ix_commercial_billing_override_part_number",
        "commercial_billing_semantic_overrides",
        ["part_number"],
        unique=False,
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        overrides,
        [
            {
                "id": str(uuid4()),
                "part_number": "B92072",
                "allow_decimal_quantity": True,
                "rationale": (
                    "API Gateway bills partial million-call units; a whole-unit "
                    "estimator hint must not force a billing ceiling."
                ),
                "source_reference": None,
                "version": "1.0.0",
                "status": "approved",
                "approved_by": "migration-20260721-0047",
                "approved_at": now,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_commercial_billing_override_part_number",
        table_name="commercial_billing_semantic_overrides",
    )
    op.drop_table("commercial_billing_semantic_overrides")
