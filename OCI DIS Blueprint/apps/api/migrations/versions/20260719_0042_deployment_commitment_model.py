"""Persist the deployment scenario commercial commitment model.

Revision ID: 20260719_0042
Revises: 20260719_0041
"""

from alembic import op
import sqlalchemy as sa


revision = "20260719_0042"
down_revision = "20260719_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deployment_scenarios",
        sa.Column(
            "commitment_model",
            sa.String(length=32),
            nullable=False,
            server_default="pay_as_you_go",
        ),
    )


def downgrade() -> None:
    op.drop_column("deployment_scenarios", "commitment_model")
