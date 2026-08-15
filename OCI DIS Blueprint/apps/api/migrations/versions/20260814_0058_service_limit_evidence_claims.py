"""Add claim-level assurance evidence for governed service limits.

Revision ID: 20260814_0058
Revises: 20260814_0057
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260814_0058"
down_revision = "20260814_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_limit_evidence_claims",
        sa.Column("service_limit_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_source_id", sa.String(length=36), nullable=False),
        sa.Column("source_content_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("observed_value", sa.JSON(), nullable=True),
        sa.Column("observed_unit", sa.String(length=50), nullable=True),
        sa.Column("source_locator", sa.Text(), nullable=True),
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
        sa.Column("parser_version", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_source_id"],
            ["service_evidence_sources.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_limit_id"],
            ["service_limits.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service_limit_id",
            "evidence_source_id",
            "source_content_hash",
            name="uq_service_limit_claim_source_hash",
        ),
    )
    op.create_index(
        "ix_service_limit_claims_limit_current",
        "service_limit_evidence_claims",
        ["service_limit_id", "is_current"],
    )
    op.create_index(
        "ix_service_limit_claims_source_current",
        "service_limit_evidence_claims",
        ["evidence_source_id", "is_current"],
    )
    op.create_index(
        "ix_service_limit_claims_status",
        "service_limit_evidence_claims",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_service_limit_claims_status", table_name="service_limit_evidence_claims")
    op.drop_index("ix_service_limit_claims_source_current", table_name="service_limit_evidence_claims")
    op.drop_index("ix_service_limit_claims_limit_current", table_name="service_limit_evidence_claims")
    op.drop_table("service_limit_evidence_claims")
