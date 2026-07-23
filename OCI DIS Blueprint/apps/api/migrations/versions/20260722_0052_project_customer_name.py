"""Add governed customer identity to projects.

Revision ID: 20260722_0052
Revises: 20260722_0051
Create Date: 2026-07-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260722_0052"
down_revision = "20260722_0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("customer_name", sa.String(length=500), nullable=True),
    )
    op.execute(
        """
        UPDATE projects
        SET customer_name = COALESCE(
            NULLIF(BTRIM(project_metadata ->> 'customer_name'), ''),
            NULLIF(BTRIM(project_metadata ->> 'client_name'), ''),
            'ACME Inc.'
        )
        """
    )
    op.alter_column(
        "projects",
        "customer_name",
        existing_type=sa.String(length=500),
        nullable=False,
        server_default="ACME Inc.",
    )


def downgrade() -> None:
    op.drop_column("projects", "customer_name")
