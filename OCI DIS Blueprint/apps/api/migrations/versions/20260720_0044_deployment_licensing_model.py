"""Persist the deployment scenario licensing model.

Revision ID: 20260720_0044
Revises: 20260720_0043
"""

from alembic import op
import sqlalchemy as sa


revision = "20260720_0044"
down_revision = "20260720_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deployment_scenarios",
        sa.Column(
            "licensing_model",
            sa.String(length=32),
            nullable=False,
            server_default="license_included",
        ),
    )


def downgrade() -> None:
    op.drop_column("deployment_scenarios", "licensing_model")
