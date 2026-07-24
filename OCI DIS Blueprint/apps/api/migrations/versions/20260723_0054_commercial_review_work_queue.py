"""Add operational ownership for the commercial review work queue."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260723_0054"
down_revision = "20260723_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "commercial_review_assignments",
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=255), nullable=False),
        sa.Column("assignee", sa.String(length=100), nullable=True),
        sa.Column(
            "workflow_status",
            sa.String(length=32),
            nullable=False,
            server_default="unassigned",
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_type",
            "entity_id",
            name="uq_commercial_review_assignment_entity",
        ),
    )
    op.create_index(
        "ix_commercial_review_assignment_workflow_due",
        "commercial_review_assignments",
        ["workflow_status", "due_at"],
        unique=False,
    )
    op.create_index(
        "ix_commercial_review_assignment_assignee",
        "commercial_review_assignments",
        ["assignee"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_commercial_review_assignment_assignee",
        table_name="commercial_review_assignments",
    )
    op.drop_index(
        "ix_commercial_review_assignment_workflow_due",
        table_name="commercial_review_assignments",
    )
    op.drop_table("commercial_review_assignments")
