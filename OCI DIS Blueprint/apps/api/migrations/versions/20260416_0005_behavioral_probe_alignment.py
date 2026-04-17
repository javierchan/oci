"""Align persisted schema and seed data with behavioral validation probes."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260416_0005"
down_revision = "20260415_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("projects", "metadata", new_column_name="project_metadata")
    op.alter_column("justification_records", "state", new_column_name="status")
    op.add_column("justification_records", sa.Column("narrative", sa.Text(), nullable=True))

    op.execute("UPDATE projects SET status = lower(status) WHERE status IS NOT NULL")
    op.execute("UPDATE import_batches SET status = lower(status) WHERE status IS NOT NULL")
    op.execute("UPDATE justification_records SET status = lower(status) WHERE status IS NOT NULL")
    op.execute("UPDATE justification_records SET narrative = deterministic_text::text WHERE narrative IS NULL")
    op.execute(
        """
        UPDATE assumption_sets AS target
        SET assumptions = (base.assumptions::jsonb || target.assumptions::jsonb)::json
        FROM assumption_sets AS base
        WHERE base.version = '1.0.0'
          AND target.version <> '1.0.0'
        """
    )

    op.alter_column("justification_records", "narrative", nullable=False)


def downgrade() -> None:
    op.drop_column("justification_records", "narrative")
    op.alter_column("justification_records", "status", new_column_name="state")
    op.alter_column("projects", "project_metadata", new_column_name="metadata")
