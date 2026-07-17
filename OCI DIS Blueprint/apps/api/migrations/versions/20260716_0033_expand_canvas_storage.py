"""Expand governed canvas storage for certified architectural overlays."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260716_0033"
down_revision = "20260716_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "catalog_integrations",
        "additional_tools_overlays",
        existing_type=sa.String(length=1000),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "catalog_integrations",
        "additional_tools_overlays",
        existing_type=sa.Text(),
        type_=sa.String(length=1000),
        existing_nullable=True,
    )
