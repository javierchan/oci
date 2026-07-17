"""Separate technical catalog inclusion from TBQ commercial eligibility.

Revision ID: 20260717_0036
Revises: 20260716_0035
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260717_0036"
down_revision = "20260716_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("import_batches", sa.Column("tbq_n_count", sa.Integer(), nullable=True))
    op.add_column(
        "catalog_integrations",
        sa.Column("tbq", sa.String(length=1), nullable=False, server_default="Y"),
    )
    op.create_check_constraint(
        "ck_catalog_integrations_tbq_values",
        "catalog_integrations",
        "tbq IN ('Y', 'N')",
    )
    op.drop_column("catalog_integrations", "uncertainty")


def downgrade() -> None:
    op.add_column(
        "catalog_integrations",
        sa.Column("uncertainty", sa.String(length=255), nullable=True),
    )
    op.drop_constraint(
        "ck_catalog_integrations_tbq_values",
        "catalog_integrations",
        type_="check",
    )
    op.drop_column("catalog_integrations", "tbq")
    op.drop_column("import_batches", "tbq_n_count")
