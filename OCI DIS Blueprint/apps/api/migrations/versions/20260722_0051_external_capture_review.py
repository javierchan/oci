"""Add governed external capture review sessions and drafts.

Revision ID: 20260722_0051
Revises: 20260721_0050
Create Date: 2026-07-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260722_0051"
down_revision = "20260721_0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_capture_sessions",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("client_name", sa.String(length=500), nullable=False),
        sa.Column("source_label", sa.String(length=500), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("normalization_policy", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_external_capture_sessions_project_id",
        "external_capture_sessions",
        ["project_id"],
    )
    op.create_index(
        "ix_external_capture_sessions_source_hash",
        "external_capture_sessions",
        ["source_hash"],
    )
    op.create_index(
        "ix_external_capture_sessions_status",
        "external_capture_sessions",
        ["status"],
    )

    op.create_table(
        "external_capture_drafts",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("source_record", sa.JSON(), nullable=False),
        sa.Column("proposed_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_values", sa.JSON(), nullable=False),
        sa.Column("pattern_assessment", sa.JSON(), nullable=False),
        sa.Column("validation_evidence", sa.JSON(), nullable=False),
        sa.Column("required_field_gaps", sa.JSON(), nullable=False),
        sa.Column("qa_preview", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewer_rationale", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promoted_integration_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["promoted_integration_id"],
            ["catalog_integrations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["external_capture_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "source_row_number",
            name="uq_external_capture_drafts_session_row",
        ),
    )
    op.create_index(
        "ix_external_capture_drafts_session_id",
        "external_capture_drafts",
        ["session_id"],
    )
    op.create_index(
        "ix_external_capture_drafts_status",
        "external_capture_drafts",
        ["status"],
    )
    op.create_index(
        "ix_external_capture_drafts_promoted_integration_id",
        "external_capture_drafts",
        ["promoted_integration_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_capture_drafts_promoted_integration_id",
        table_name="external_capture_drafts",
    )
    op.drop_index(
        "ix_external_capture_drafts_status",
        table_name="external_capture_drafts",
    )
    op.drop_index(
        "ix_external_capture_drafts_session_id",
        table_name="external_capture_drafts",
    )
    op.drop_table("external_capture_drafts")
    op.drop_index(
        "ix_external_capture_sessions_status",
        table_name="external_capture_sessions",
    )
    op.drop_index(
        "ix_external_capture_sessions_source_hash",
        table_name="external_capture_sessions",
    )
    op.drop_index(
        "ix_external_capture_sessions_project_id",
        table_name="external_capture_sessions",
    )
    op.drop_table("external_capture_sessions")
