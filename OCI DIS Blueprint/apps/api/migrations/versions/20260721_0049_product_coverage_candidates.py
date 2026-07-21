"""Add governed product coverage candidates.

Revision ID: 20260721_0049
Revises: 20260721_0048
Create Date: 2026-07-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260721_0049"
down_revision = "20260721_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_coverage_candidates",
        sa.Column("product_key", sa.String(length=255), nullable=False),
        sa.Column("product_name", sa.String(length=1000), nullable=False),
        sa.Column("category", sa.String(length=500), nullable=True),
        sa.Column("proposed_service_id", sa.String(length=255), nullable=False),
        sa.Column("proposed_profile", sa.JSON(), nullable=False),
        sa.Column("proposed_policy", sa.JSON(), nullable=False),
        sa.Column("proposed_mappings", sa.JSON(), nullable=False),
        sa.Column("readiness_status", sa.String(length=32), nullable=False),
        sa.Column("readiness_blockers", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generator_version", sa.String(length=50), nullable=False),
        sa.Column("review_rationale", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_document_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_document_snapshot_id"], ["commercial_document_snapshots.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_key", name="uq_product_coverage_candidate_key"),
    )
    op.create_index(
        "ix_product_coverage_candidate_status",
        "product_coverage_candidates",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_product_coverage_candidate_readiness",
        "product_coverage_candidates",
        ["readiness_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_coverage_candidate_readiness",
        table_name="product_coverage_candidates",
    )
    op.drop_index(
        "ix_product_coverage_candidate_status",
        table_name="product_coverage_candidates",
    )
    op.drop_table("product_coverage_candidates")
