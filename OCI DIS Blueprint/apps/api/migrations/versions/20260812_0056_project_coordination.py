"""Add project-shared views and auditable attention coordination.

Revision ID: 20260812_0056
Revises: 20260724_0055
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20260812_0056"
down_revision = "20260724_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_saved_views",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("surface", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("is_shared", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_saved_views_project_id", "project_saved_views", ["project_id"])
    op.create_table(
        "project_attention_tasks",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("attention_key", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("evidence_href", sa.String(length=2048), nullable=False),
        sa.Column("assignee", sa.String(length=255), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "attention_key", name="uq_project_attention_task_key"),
    )
    op.create_index("ix_project_attention_tasks_project_id", "project_attention_tasks", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_attention_tasks_project_id", table_name="project_attention_tasks")
    op.drop_table("project_attention_tasks")
    op.drop_index("ix_project_saved_views_project_id", table_name="project_saved_views")
    op.drop_table("project_saved_views")
