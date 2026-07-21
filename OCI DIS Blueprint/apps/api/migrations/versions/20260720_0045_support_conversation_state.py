"""Persist bounded structured state for contextual support conversations.

Revision ID: 20260720_0045
Revises: 20260720_0044
"""

from alembic import op
import sqlalchemy as sa


revision = "20260720_0045"
down_revision = "20260720_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "support_conversations",
        sa.Column("context_state", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )


def downgrade() -> None:
    op.drop_column("support_conversations", "context_state")
