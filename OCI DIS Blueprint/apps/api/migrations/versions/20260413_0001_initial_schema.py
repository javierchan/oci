"""Initial OCI DIS Blueprint schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260413_0001"
down_revision = None
branch_labels = None
depends_on = None


project_status = sa.Enum("ACTIVE", "ARCHIVED", "DRAFT", name="projectstatus", native_enum=False)
import_status = sa.Enum("PENDING", "PROCESSING", "COMPLETED", "FAILED", name="importstatus", native_enum=False)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("status", project_status, nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "pattern_definitions",
        sa.Column("pattern_id", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("oci_components", sa.Text(), nullable=True),
        sa.Column("when_to_use", sa.Text(), nullable=True),
        sa.Column("when_not_to_use", sa.Text(), nullable=True),
        sa.Column("technical_flow", sa.Text(), nullable=True),
        sa.Column("business_value", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pattern_id"),
    )
    op.create_table(
        "dictionary_options",
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("executions_per_day", sa.Float(), nullable=True),
        sa.Column("is_volumetric", sa.Boolean(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "assumption_sets",
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_table(
        "import_batches",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("status", import_status, nullable=False),
        sa.Column("source_row_count", sa.Integer(), nullable=True),
        sa.Column("tbq_y_count", sa.Integer(), nullable=True),
        sa.Column("excluded_count", sa.Integer(), nullable=True),
        sa.Column("loaded_count", sa.Integer(), nullable=True),
        sa.Column("header_map", sa.JSON(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "source_integration_rows",
        sa.Column("import_batch_id", sa.String(length=36), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("included", sa.Boolean(), nullable=False),
        sa.Column("exclusion_reason", sa.String(length=500), nullable=True),
        sa.Column("normalization_events", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["import_batch_id"], ["import_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "catalog_integrations",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("source_row_id", sa.String(length=36), nullable=True),
        sa.Column("seq_number", sa.Integer(), nullable=False),
        sa.Column("interface_id", sa.String(length=100), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("business_process", sa.String(length=500), nullable=True),
        sa.Column("interface_name", sa.String(length=500), nullable=True),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("mapping_status", sa.String(length=100), nullable=True),
        sa.Column("initial_scope", sa.String(length=255), nullable=True),
        sa.Column("complexity", sa.String(length=100), nullable=True),
        sa.Column("frequency", sa.String(length=255), nullable=True),
        sa.Column("type", sa.String(length=100), nullable=True),
        sa.Column("base", sa.String(length=255), nullable=True),
        sa.Column("interface_status", sa.String(length=100), nullable=True),
        sa.Column("is_real_time", sa.Boolean(), nullable=True),
        sa.Column("trigger_type", sa.String(length=100), nullable=True),
        sa.Column("response_size_kb", sa.Float(), nullable=True),
        sa.Column("payload_per_execution_kb", sa.Float(), nullable=True),
        sa.Column("is_fan_out", sa.Boolean(), nullable=True),
        sa.Column("fan_out_targets", sa.Integer(), nullable=True),
        sa.Column("source_system", sa.String(length=255), nullable=True),
        sa.Column("source_technology", sa.String(length=255), nullable=True),
        sa.Column("source_api_reference", sa.String(length=1000), nullable=True),
        sa.Column("source_owner", sa.String(length=255), nullable=True),
        sa.Column("destination_system", sa.String(length=255), nullable=True),
        sa.Column("destination_technology_1", sa.String(length=255), nullable=True),
        sa.Column("destination_technology_2", sa.String(length=255), nullable=True),
        sa.Column("destination_owner", sa.String(length=255), nullable=True),
        sa.Column("executions_per_day", sa.Float(), nullable=True),
        sa.Column("payload_per_hour_kb", sa.Float(), nullable=True),
        sa.Column("selected_pattern", sa.String(length=100), nullable=True),
        sa.Column("pattern_rationale", sa.String(length=2000), nullable=True),
        sa.Column("comments", sa.String(length=4000), nullable=True),
        sa.Column("retry_policy", sa.String(length=500), nullable=True),
        sa.Column("core_tools", sa.String(length=1000), nullable=True),
        sa.Column("additional_tools_overlays", sa.String(length=1000), nullable=True),
        sa.Column("qa_status", sa.String(length=50), nullable=True),
        sa.Column("qa_reasons", sa.JSON(), nullable=True),
        sa.Column("calendarization", sa.String(length=255), nullable=True),
        sa.Column("uncertainty", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_row_id"], ["source_integration_rows.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "volumetry_snapshots",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("assumption_set_version", sa.String(length=50), nullable=False),
        sa.Column("triggered_by", sa.String(length=36), nullable=False),
        sa.Column("row_results", sa.JSON(), nullable=False),
        sa.Column("consolidated", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "dashboard_snapshots",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("volumetry_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("mode", sa.String(length=50), nullable=False),
        sa.Column("kpi_strip", sa.JSON(), nullable=False),
        sa.Column("charts", sa.JSON(), nullable=False),
        sa.Column("risks", sa.JSON(), nullable=True),
        sa.Column("maturity", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["volumetry_snapshot_id"], ["volumetry_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "justification_records",
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("integration_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("deterministic_text", sa.JSON(), nullable=False),
        sa.Column("ai_suggestion", sa.JSON(), nullable=True),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("override_notes", sa.String(length=4000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["integration_id"], ["catalog_integrations.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_events",
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=True),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("justification_records")
    op.drop_table("dashboard_snapshots")
    op.drop_table("volumetry_snapshots")
    op.drop_table("catalog_integrations")
    op.drop_table("source_integration_rows")
    op.drop_table("import_batches")
    op.drop_table("assumption_sets")
    op.drop_table("dictionary_options")
    op.drop_table("pattern_definitions")
    op.drop_table("projects")
