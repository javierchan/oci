"""Add persisted AI review jobs for governed architecture reviews."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260501_0008"
down_revision = "20260428_0007"
branch_labels = None
depends_on = None


ai_review_job_status = sa.Enum(
    "pending",
    "running",
    "completed",
    "failed",
    name="aireviewjobstatus",
    native_enum=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("ai_review_jobs"):
        op.create_table(
            "ai_review_jobs",
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("requested_by", sa.String(length=36), nullable=False),
            sa.Column("status", ai_review_job_status, nullable=False),
            sa.Column("scope", sa.String(length=32), nullable=False),
            sa.Column("integration_id", sa.String(length=36), nullable=True),
            sa.Column("input_payload", sa.JSON(), nullable=False),
            sa.Column("result_payload", sa.JSON(), nullable=True),
            sa.Column("accepted_recommendations", sa.JSON(), nullable=True),
            sa.Column("error_details", sa.JSON(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.ForeignKeyConstraint(["integration_id"], ["catalog_integrations.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("ai_review_jobs")}
    if "ix_ai_review_jobs_project_created" not in indexes:
        op.create_index(
            "ix_ai_review_jobs_project_created",
            "ai_review_jobs",
            ["project_id", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("ai_review_jobs"):
        indexes = {index["name"] for index in inspector.get_indexes("ai_review_jobs")}
        if "ix_ai_review_jobs_project_created" in indexes:
            op.drop_index("ix_ai_review_jobs_project_created", table_name="ai_review_jobs")
        op.drop_table("ai_review_jobs")
