"""Add executable decision state to governed agent approvals.

Revision ID: 20260716_0035
Revises: 20260716_0034
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260716_0035"
down_revision = "20260716_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_approvals",
        sa.Column("execution_status", sa.String(length=24), nullable=False, server_default="not_started"),
    )
    op.add_column("agent_approvals", sa.Column("execution_result", sa.JSON(), nullable=True))
    op.add_column("agent_approvals", sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_approvals", "executed_at")
    op.drop_column("agent_approvals", "execution_result")
    op.drop_column("agent_approvals", "execution_status")
