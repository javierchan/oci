"""Add the governed OCI Generative AI agent runtime tables."""

from alembic import op
import sqlalchemy as sa


revision = "20260712_0021"
down_revision = "20260712_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("agent_type", sa.String(length=48), nullable=False),
        sa.Column("definition_version", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("integration_id", sa.String(length=36), nullable=True),
        sa.Column("requested_by", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=18), nullable=False),
        sa.Column("context_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("legacy_job_type", sa.String(length=48), nullable=True),
        sa.Column("legacy_job_id", sa.String(length=36), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("provider_response_id", sa.String(length=255), nullable=True),
        sa.Column("opc_request_id", sa.String(length=255), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("step_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["integration_id"], ["catalog_integrations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_agent_type", "agent_runs", ["agent_type"])
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])
    op.create_index("ix_agent_runs_legacy_job_id", "agent_runs", ["legacy_job_id"])

    op.create_table(
        "agent_steps",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=32), nullable=False),
        sa.Column("tool_name", sa.String(length=96), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=True),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("opc_request_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])

    op.create_table(
        "agent_approvals",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("proposed_payload", sa.JSON(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_approvals_run_id", "agent_approvals", ["run_id"])

    op.create_table(
        "agent_artifacts",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("artifact_type", sa.String(length=48), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_artifacts_run_id", "agent_artifacts", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_artifacts_run_id", table_name="agent_artifacts")
    op.drop_table("agent_artifacts")
    op.drop_index("ix_agent_approvals_run_id", table_name="agent_approvals")
    op.drop_table("agent_approvals")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_agent_runs_legacy_job_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_project_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_type", table_name="agent_runs")
    op.drop_table("agent_runs")
