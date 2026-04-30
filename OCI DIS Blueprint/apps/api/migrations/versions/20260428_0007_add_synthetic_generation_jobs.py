"""Add persisted synthetic-generation jobs for the admin synthetic lab."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260428_0007"
down_revision = "20260416_0006"
branch_labels = None
depends_on = None


synthetic_generation_job_status = sa.Enum(
    "pending",
    "running",
    "completed",
    "failed",
    "cleaned_up",
    name="syntheticgenerationjobstatus",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "synthetic_generation_jobs",
        sa.Column("requested_by", sa.String(length=36), nullable=False),
        sa.Column("status", synthetic_generation_job_status, nullable=False),
        sa.Column("preset_code", sa.String(length=100), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("project_name", sa.String(length=255), nullable=True),
        sa.Column("seed_value", sa.Integer(), nullable=False),
        sa.Column("catalog_target", sa.Integer(), nullable=False),
        sa.Column("manual_target", sa.Integer(), nullable=False),
        sa.Column("import_target", sa.Integer(), nullable=False),
        sa.Column("excluded_import_target", sa.Integer(), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("validation_results", sa.JSON(), nullable=True),
        sa.Column("artifact_manifest", sa.JSON(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("synthetic_generation_jobs")
