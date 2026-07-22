"""Add governed App knowledge maintenance jobs and candidates.

Revision ID: 20260721_0050
Revises: 20260721_0049
Create Date: 2026-07-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260721_0050"
down_revision = "20260721_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_maintenance_jobs",
        sa.Column("requested_by", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_maintenance_jobs_status", "knowledge_maintenance_jobs", ["status"])
    op.create_index("ix_knowledge_maintenance_jobs_source_hash", "knowledge_maintenance_jobs", ["source_hash"])
    op.create_table(
        "knowledge_maintenance_findings",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("section_id", sa.String(length=64), nullable=False),
        sa.Column("finding_type", sa.String(length=48), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("current_value", sa.JSON(), nullable=False),
        sa.Column("candidate_value", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["knowledge_maintenance_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_maintenance_findings_job_id", "knowledge_maintenance_findings", ["job_id"])
    op.create_index("ix_knowledge_maintenance_findings_section_id", "knowledge_maintenance_findings", ["section_id"])
    op.create_index("ix_knowledge_maintenance_findings_review_status", "knowledge_maintenance_findings", ["review_status"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_maintenance_findings_review_status", table_name="knowledge_maintenance_findings")
    op.drop_index("ix_knowledge_maintenance_findings_section_id", table_name="knowledge_maintenance_findings")
    op.drop_index("ix_knowledge_maintenance_findings_job_id", table_name="knowledge_maintenance_findings")
    op.drop_table("knowledge_maintenance_findings")
    op.drop_index("ix_knowledge_maintenance_jobs_source_hash", table_name="knowledge_maintenance_jobs")
    op.drop_index("ix_knowledge_maintenance_jobs_status", table_name="knowledge_maintenance_jobs")
    op.drop_table("knowledge_maintenance_jobs")
