"""Add structured pattern applicability guidance for capture and exports."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260710_0016"
down_revision = "20260710_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pattern_definitions",
        sa.Column("applicability_examples", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "pattern_definitions",
        sa.Column("selection_questions", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.add_column(
        "pattern_definitions",
        sa.Column("required_inputs", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.alter_column("pattern_definitions", "applicability_examples", server_default=None)
    op.alter_column("pattern_definitions", "selection_questions", server_default=None)
    op.alter_column("pattern_definitions", "required_inputs", server_default=None)


def downgrade() -> None:
    op.drop_column("pattern_definitions", "required_inputs")
    op.drop_column("pattern_definitions", "selection_questions")
    op.drop_column("pattern_definitions", "applicability_examples")
