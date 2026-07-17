"""Add atomic OCI source verification and quote-regression evidence."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260716_0034"
down_revision = "20260716_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "governance_change_sets",
        sa.Column("sync_job_id", sa.String(length=36), nullable=False),
        sa.Column("price_source_id", sa.String(length=36), nullable=False),
        sa.Column("price_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("previous_change_set_id", sa.String(length=36), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("drift_classification", sa.String(length=32), nullable=False),
        sa.Column("materiality_score", sa.Float(), nullable=False),
        sa.Column("source_manifest", sa.JSON(), nullable=False),
        sa.Column("drift_summary", sa.JSON(), nullable=False),
        sa.Column("impact_summary", sa.JSON(), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("regression_summary", sa.JSON(), nullable=False),
        sa.Column("approval_status", sa.String(length=32), nullable=False),
        sa.Column("approved_by", sa.String(length=100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["previous_change_set_id"], ["governance_change_sets.id"]),
        sa.ForeignKeyConstraint(["price_snapshot_id"], ["price_catalog_snapshots.id"]),
        sa.ForeignKeyConstraint(["price_source_id"], ["price_sources.id"]),
        sa.ForeignKeyConstraint(["sync_job_id"], ["price_sync_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sync_job_id"),
    )
    op.create_table(
        "governance_source_artifacts",
        sa.Column("change_set_id", sa.String(length=36), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("storage_reference", sa.Text(), nullable=False),
        sa.Column("source_last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieval_status", sa.String(length=32), nullable=False),
        sa.Column("validation_summary", sa.JSON(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["change_set_id"], ["governance_change_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("change_set_id", "source_kind", name="uq_governance_artifact_change_set_kind"),
    )
    op.create_table(
        "quotation_regression_runs",
        sa.Column("change_set_id", sa.String(length=36), nullable=False),
        sa.Column("family_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("fixture_count", sa.Integer(), nullable=False),
        sa.Column("passed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("mapping_count", sa.Integer(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["change_set_id"], ["governance_change_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("change_set_id", "family_key", name="uq_quote_regression_change_set_family"),
    )


def downgrade() -> None:
    op.drop_table("quotation_regression_runs")
    op.drop_table("governance_source_artifacts")
    op.drop_table("governance_change_sets")
