"""Add approved AI review baselines for planned-versus-actual drift."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260501_0010"
down_revision = "20260501_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("ai_review_baselines"):
        op.create_table(
            "ai_review_baselines",
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("scope", sa.String(length=32), nullable=False),
            sa.Column("integration_id", sa.String(length=36), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=False),
            sa.Column("note", sa.String(length=2000), nullable=True),
            sa.Column("baseline_payload", sa.JSON(), nullable=False),
            sa.Column("row_count", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.ForeignKeyConstraint(["integration_id"], ["catalog_integrations.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("ai_review_baselines")}
    if "ix_ai_review_baselines_project_scope_active" not in indexes:
        op.create_index(
            "ix_ai_review_baselines_project_scope_active",
            "ai_review_baselines",
            ["project_id", "scope", "integration_id", "is_active", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("ai_review_baselines"):
        indexes = {index["name"] for index in inspector.get_indexes("ai_review_baselines")}
        if "ix_ai_review_baselines_project_scope_active" in indexes:
            op.drop_index("ix_ai_review_baselines_project_scope_active", table_name="ai_review_baselines")
        op.drop_table("ai_review_baselines")
