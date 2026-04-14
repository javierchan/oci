"""Add is_system flag to pattern definitions."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260414_0003"
down_revision = "20260414_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pattern_definitions",
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute(
        sa.text(
            """
            UPDATE pattern_definitions
            SET is_system = TRUE
            WHERE pattern_id IN (
                '#01', '#02', '#03', '#04', '#05', '#06', '#07', '#08', '#09',
                '#10', '#11', '#12', '#13', '#14', '#15', '#16', '#17'
            )
            """
        )
    )
    op.alter_column("pattern_definitions", "is_system", server_default=None)


def downgrade() -> None:
    op.drop_column("pattern_definitions", "is_system")
