"""Add normalized service product library tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260607_0012"
down_revision = "20260501_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_product_versions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("service_profile_id", sa.String(36), nullable=False),
        sa.Column("version_label", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("use_cases", sa.JSON(), nullable=False),
        sa.Column("anti_patterns", sa.JSON(), nullable=False),
        sa.Column("regional_availability", sa.Text(), nullable=True),
        sa.Column("commercial_notes", sa.Text(), nullable=True),
        sa.Column("security_notes", sa.Text(), nullable=True),
        sa.Column("deprecation_notes", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["service_profile_id"], ["service_capability_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_profile_id", "version_label", name="uq_service_product_version_profile_label"),
    )
    op.create_index(
        "ix_service_product_versions_service_profile_id",
        "service_product_versions",
        ["service_profile_id"],
    )

    op.create_table(
        "service_limits",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("service_profile_id", sa.String(36), nullable=False),
        sa.Column("limit_key", sa.String(150), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("limit_type", sa.String(50), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("default_value", sa.JSON(), nullable=True),
        sa.Column("can_request_increase", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["service_profile_id"], ["service_capability_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_profile_id", "limit_key", name="uq_service_limit_profile_key"),
    )
    op.create_index("ix_service_limits_service_profile_id", "service_limits", ["service_profile_id"])
    op.create_index("ix_service_limits_limit_type", "service_limits", ["limit_type"])

    op.create_table(
        "service_interoperability_rules",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("source_service_profile_id", sa.String(36), nullable=False),
        sa.Column("target_service_profile_id", sa.String(36), nullable=False),
        sa.Column("relationship_type", sa.String(100), nullable=False),
        sa.Column("supported", sa.Boolean(), nullable=False),
        sa.Column("directionality", sa.String(50), nullable=False),
        sa.Column("patterns", sa.JSON(), nullable=False),
        sa.Column("required_components", sa.JSON(), nullable=False),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("risk_notes", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_service_profile_id"], ["service_capability_profiles.id"]),
        sa.ForeignKeyConstraint(["target_service_profile_id"], ["service_capability_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_service_profile_id",
            "target_service_profile_id",
            "relationship_type",
            name="uq_service_interop_source_target_type",
        ),
    )
    op.create_index(
        "ix_service_interop_source_service_profile_id",
        "service_interoperability_rules",
        ["source_service_profile_id"],
    )
    op.create_index(
        "ix_service_interop_target_service_profile_id",
        "service_interoperability_rules",
        ["target_service_profile_id"],
    )

    op.create_table(
        "service_evidence_sources",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("service_profile_id", sa.String(36), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("publisher", sa.String(120), nullable=False),
        sa.Column("trust_tier", sa.String(80), nullable=False),
        sa.Column("retrieval_strategy", sa.String(80), nullable=False),
        sa.Column("expected_update_frequency_days", sa.Integer(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.String(128), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["service_profile_id"], ["service_capability_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_profile_id", "url", name="uq_service_evidence_profile_url"),
    )
    op.create_index(
        "ix_service_evidence_sources_service_profile_id",
        "service_evidence_sources",
        ["service_profile_id"],
    )
    op.create_index("ix_service_evidence_sources_status", "service_evidence_sources", ["status"])

    op.create_table(
        "service_verification_jobs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("requested_by", sa.String(100), nullable=False),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("services_checked", sa.JSON(), nullable=False),
        sa.Column("sources_checked", sa.Integer(), nullable=False),
        sa.Column("changes_detected", sa.Integer(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("recommendations", sa.JSON(), nullable=False),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_service_verification_jobs_status", "service_verification_jobs", ["status"])

    op.create_table(
        "service_verification_findings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.Column("service_profile_id", sa.String(36), nullable=True),
        sa.Column("finding_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("evidence_excerpt", sa.Text(), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("review_status", sa.String(50), nullable=False),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["service_verification_jobs.id"]),
        sa.ForeignKeyConstraint(["service_profile_id"], ["service_capability_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_service_verification_findings_job_id",
        "service_verification_findings",
        ["job_id"],
    )
    op.create_index(
        "ix_service_verification_findings_review_status",
        "service_verification_findings",
        ["review_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_service_verification_findings_review_status", table_name="service_verification_findings")
    op.drop_index("ix_service_verification_findings_job_id", table_name="service_verification_findings")
    op.drop_table("service_verification_findings")
    op.drop_index("ix_service_verification_jobs_status", table_name="service_verification_jobs")
    op.drop_table("service_verification_jobs")
    op.drop_index("ix_service_evidence_sources_status", table_name="service_evidence_sources")
    op.drop_index("ix_service_evidence_sources_service_profile_id", table_name="service_evidence_sources")
    op.drop_table("service_evidence_sources")
    op.drop_index("ix_service_interop_target_service_profile_id", table_name="service_interoperability_rules")
    op.drop_index("ix_service_interop_source_service_profile_id", table_name="service_interoperability_rules")
    op.drop_table("service_interoperability_rules")
    op.drop_index("ix_service_limits_limit_type", table_name="service_limits")
    op.drop_index("ix_service_limits_service_profile_id", table_name="service_limits")
    op.drop_table("service_limits")
    op.drop_index("ix_service_product_versions_service_profile_id", table_name="service_product_versions")
    op.drop_table("service_product_versions")
