"""Persist governed OCI commercial documents and normalized SKU decisions.

Revision ID: 20260719_0041
Revises: 20260717_0040
"""

from alembic import op
import sqlalchemy as sa


revision = "20260719_0041"
down_revision = "20260717_0040"
branch_labels = None
depends_on = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "commercial_skus",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("part_number", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=1000), nullable=False),
        sa.Column("service_category", sa.String(length=500), nullable=True),
        sa.Column("source_product_id", sa.String(length=100), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("part_number", name="uq_commercial_sku_part_number"),
    )
    op.create_index("ix_commercial_sku_lifecycle_category", "commercial_skus", ["lifecycle_status", "service_category"])
    op.create_table(
        "commercial_document_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_kind", sa.String(length=50), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("storage_reference", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("approved_by", sa.String(length=100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["supersedes_snapshot_id"], ["commercial_document_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_kind", "content_hash", name="uq_commercial_document_kind_hash"),
    )
    op.create_index(
        "ix_commercial_document_kind_status",
        "commercial_document_snapshots",
        ["document_kind", "status"],
    )
    op.create_table(
        "sku_commercial_terms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("commercial_sku_id", sa.String(length=36), nullable=False),
        sa.Column("price_catalog_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("part_number", sa.String(length=50), nullable=False),
        sa.Column("service_name", sa.String(length=1000), nullable=False),
        sa.Column("service_category", sa.String(length=500), nullable=True),
        sa.Column("commercial_prices", sa.JSON(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("metric_name", sa.String(length=500), nullable=True),
        sa.Column("price_type", sa.String(length=50), nullable=True),
        sa.Column("allow_decimal_quantity", sa.Boolean(), nullable=True),
        sa.Column("availability", sa.JSON(), nullable=False),
        sa.Column("additional_information", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("disposition", sa.String(length=40), nullable=False),
        sa.Column("family_key", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_sheet", sa.String(length=255), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("source_cells", sa.JSON(), nullable=False),
        sa.Column("extraction_metadata", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["document_snapshot_id"], ["commercial_document_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["commercial_sku_id"], ["commercial_skus.id"]),
        sa.ForeignKeyConstraint(["price_catalog_snapshot_id"], ["price_catalog_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_snapshot_id", "source_sheet", "source_row", "part_number", name="uq_sku_term_document_location"),
    )
    op.create_index("ix_sku_commercial_terms_part_status", "sku_commercial_terms", ["part_number", "status"])
    op.create_table(
        "sku_commercial_constraints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("term_id", sa.String(length=36), nullable=False),
        sa.Column("constraint_type", sa.String(length=50), nullable=False),
        sa.Column("scope", sa.String(length=80), nullable=False),
        sa.Column("numeric_value", sa.Numeric(28, 8), nullable=True),
        sa.Column("text_value", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=100), nullable=True),
        sa.Column("behavior", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_cell", sa.String(length=50), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["term_id"], ["sku_commercial_terms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "term_id", "constraint_type", "scope", "source_cell",
            name="uq_sku_commercial_constraint_source",
        ),
    )
    op.create_index(
        "ix_sku_commercial_constraint_term_status",
        "sku_commercial_constraints",
        ["term_id", "status"],
    )
    op.create_table(
        "sku_commercial_relationships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("source_term_id", sa.String(length=36), nullable=True),
        sa.Column("source_commercial_sku_id", sa.String(length=36), nullable=False),
        sa.Column("target_commercial_sku_id", sa.String(length=36), nullable=True),
        sa.Column("part_number", sa.String(length=50), nullable=False),
        sa.Column("relationship_type", sa.String(length=50), nullable=False),
        sa.Column("target_part_number", sa.String(length=50), nullable=True),
        sa.Column("target_name", sa.Text(), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("resolution_status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_sheet", sa.String(length=255), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("source_cell", sa.String(length=50), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["document_snapshot_id"], ["commercial_document_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_term_id"], ["sku_commercial_terms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_commercial_sku_id"], ["commercial_skus.id"]),
        sa.ForeignKeyConstraint(["target_commercial_sku_id"], ["commercial_skus.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sku_commercial_relationship_part_type", "sku_commercial_relationships", ["part_number", "relationship_type"])
    op.create_table(
        "commercial_rule_families",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("family_key", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("formula_key", sa.String(length=100), nullable=False),
        sa.Column("metric_pattern", sa.String(length=500), nullable=False),
        sa.Column("price_types", sa.JSON(), nullable=False),
        sa.Column("quantity_behavior", sa.String(length=32), nullable=False),
        sa.Column("quantity_increment", sa.Numeric(28, 8), nullable=False),
        sa.Column("minimum_quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("aggregation_window", sa.String(length=40), nullable=False),
        sa.Column("proration_policy", sa.String(length=40), nullable=False),
        sa.Column("quote_rounding", sa.String(length=40), nullable=False),
        sa.Column("generator_version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("fixture_status", sa.String(length=32), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("approved_by", sa.String(length=100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_key", "version", name="uq_commercial_rule_family_version"),
    )
    op.create_table(
        "commercial_mapping_candidates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("commercial_sku_id", sa.String(length=36), nullable=False),
        sa.Column("term_id", sa.String(length=36), nullable=True),
        sa.Column("price_item_id", sa.String(length=36), nullable=True),
        sa.Column("existing_mapping_id", sa.String(length=36), nullable=True),
        sa.Column("part_number", sa.String(length=50), nullable=False),
        sa.Column("proposed_service_id", sa.String(length=80), nullable=True),
        sa.Column("family_key", sa.String(length=100), nullable=True),
        sa.Column("classification", sa.String(length=40), nullable=False),
        sa.Column("proposed_mapping", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("generator_version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["document_snapshot_id"], ["commercial_document_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["commercial_sku_id"], ["commercial_skus.id"]),
        sa.ForeignKeyConstraint(["term_id"], ["sku_commercial_terms.id"]),
        sa.ForeignKeyConstraint(["price_item_id"], ["price_items.id"]),
        sa.ForeignKeyConstraint(["existing_mapping_id"], ["service_product_sku_mappings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_snapshot_id", "part_number", "generator_version", name="uq_commercial_candidate_document_sku_generator"),
    )
    op.create_index("ix_commercial_candidate_status_class", "commercial_mapping_candidates", ["status", "classification"])
    op.create_table(
        "commercial_exceptions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=True),
        sa.Column("part_number", sa.String(length=50), nullable=True),
        sa.Column("exception_code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("proposed_resolution", sa.Text(), nullable=True),
        sa.Column("decision_rationale", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["document_snapshot_id"], ["commercial_document_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["commercial_mapping_candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commercial_exception_status_severity", "commercial_exceptions", ["status", "severity"])
    op.create_table(
        "commercial_evidence_references",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("source_kind", sa.String(length=50), nullable=False),
        sa.Column("document_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("governance_artifact_id", sa.String(length=36), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_sheet", sa.String(length=255), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("source_cell", sa.String(length=50), nullable=True),
        sa.Column("excerpt_hash", sa.String(length=128), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["document_snapshot_id"], ["commercial_document_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["governance_artifact_id"], ["governance_source_artifacts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commercial_evidence_entity", "commercial_evidence_references", ["entity_type", "entity_id"])
    op.create_table(
        "commercial_releases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("price_catalog_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("document_snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("governance_change_set_id", sa.String(length=36), nullable=True),
        sa.Column("mapping_set_hash", sa.String(length=128), nullable=False),
        sa.Column("rule_family_set_hash", sa.String(length=128), nullable=False),
        sa.Column("evidence_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("open_exception_count", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("approved_by", sa.String(length=100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["price_catalog_snapshot_id"], ["price_catalog_snapshots.id"]),
        sa.ForeignKeyConstraint(["document_snapshot_id"], ["commercial_document_snapshots.id"]),
        sa.ForeignKeyConstraint(["governance_change_set_id"], ["governance_change_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", name="uq_commercial_release_version"),
    )
    op.create_index("ix_commercial_release_status_validation", "commercial_releases", ["status", "validation_status"])
    op.add_column("bom_snapshots", sa.Column("commercial_release_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_bom_snapshot_commercial_release", "bom_snapshots", "commercial_releases", ["commercial_release_id"], ["id"])
    op.add_column("bom_line_items", sa.Column("commercial_term_id", sa.String(length=36), nullable=True))
    op.add_column("bom_line_items", sa.Column("commercial_rule_family_id", sa.String(length=36), nullable=True))
    op.add_column("bom_line_items", sa.Column("evidence_reference_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.create_foreign_key("fk_bom_line_commercial_term", "bom_line_items", "sku_commercial_terms", ["commercial_term_id"], ["id"])
    op.create_foreign_key("fk_bom_line_commercial_rule_family", "bom_line_items", "commercial_rule_families", ["commercial_rule_family_id"], ["id"])
    op.add_column("bom_line_periods", sa.Column("commercial_term_id", sa.String(length=36), nullable=True))
    op.add_column("bom_line_periods", sa.Column("commercial_rule_family_id", sa.String(length=36), nullable=True))
    op.add_column("bom_line_periods", sa.Column("evidence_reference_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.create_foreign_key("fk_bom_period_commercial_term", "bom_line_periods", "sku_commercial_terms", ["commercial_term_id"], ["id"])
    op.create_foreign_key("fk_bom_period_commercial_rule_family", "bom_line_periods", "commercial_rule_families", ["commercial_rule_family_id"], ["id"])
def downgrade() -> None:
    op.drop_constraint("fk_bom_period_commercial_rule_family", "bom_line_periods", type_="foreignkey")
    op.drop_constraint("fk_bom_period_commercial_term", "bom_line_periods", type_="foreignkey")
    op.drop_column("bom_line_periods", "evidence_reference_ids")
    op.drop_column("bom_line_periods", "commercial_rule_family_id")
    op.drop_column("bom_line_periods", "commercial_term_id")
    op.drop_constraint("fk_bom_line_commercial_rule_family", "bom_line_items", type_="foreignkey")
    op.drop_constraint("fk_bom_line_commercial_term", "bom_line_items", type_="foreignkey")
    op.drop_column("bom_line_items", "evidence_reference_ids")
    op.drop_column("bom_line_items", "commercial_rule_family_id")
    op.drop_column("bom_line_items", "commercial_term_id")
    op.drop_constraint("fk_bom_snapshot_commercial_release", "bom_snapshots", type_="foreignkey")
    op.drop_column("bom_snapshots", "commercial_release_id")
    op.drop_index("ix_commercial_release_status_validation", table_name="commercial_releases")
    op.drop_table("commercial_releases")
    op.drop_index("ix_commercial_evidence_entity", table_name="commercial_evidence_references")
    op.drop_table("commercial_evidence_references")
    op.drop_index("ix_commercial_exception_status_severity", table_name="commercial_exceptions")
    op.drop_table("commercial_exceptions")
    op.drop_index("ix_commercial_candidate_status_class", table_name="commercial_mapping_candidates")
    op.drop_table("commercial_mapping_candidates")
    op.drop_table("commercial_rule_families")
    op.drop_index("ix_sku_commercial_relationship_part_type", table_name="sku_commercial_relationships")
    op.drop_table("sku_commercial_relationships")
    op.drop_index("ix_sku_commercial_constraint_term_status", table_name="sku_commercial_constraints")
    op.drop_table("sku_commercial_constraints")
    op.drop_index("ix_sku_commercial_terms_part_status", table_name="sku_commercial_terms")
    op.drop_table("sku_commercial_terms")
    op.drop_index("ix_commercial_document_kind_status", table_name="commercial_document_snapshots")
    op.drop_table("commercial_document_snapshots")
    op.drop_index("ix_commercial_sku_lifecycle_category", table_name="commercial_skus")
    op.drop_table("commercial_skus")
