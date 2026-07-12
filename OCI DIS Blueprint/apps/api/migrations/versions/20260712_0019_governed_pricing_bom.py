"""Add governed OCI pricing, deployment scenario, and BOM tables."""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20260712_0019"
down_revision = "20260711_0018"
branch_labels = None
depends_on = None


PUBLIC_SOURCE_ID = "fa500000-0000-4000-8000-000000000001"
PUBLIC_PRICING_URL = "https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/"


def upgrade() -> None:
    op.create_table(
        "price_sources",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_price_sources_name"),
    )
    op.create_index("ix_price_sources_status", "price_sources", ["status"])

    op.create_table(
        "price_sync_jobs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("requested_by", sa.String(100), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("changes_detected", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["price_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_sync_jobs_status", "price_sync_jobs", ["status"])

    op.create_table(
        "price_catalog_snapshots",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("sync_job_id", sa.String(36), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("source_last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("approval_status", sa.String(50), nullable=False),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["price_sources.id"]),
        sa.ForeignKeyConstraint(["sync_job_id"], ["price_sync_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "currency", "content_hash", name="uq_price_snapshot_source_hash"),
    )
    op.create_index(
        "ix_price_catalog_snapshots_approval",
        "price_catalog_snapshots",
        ["approval_status", "currency"],
    )

    op.create_table(
        "price_items",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("snapshot_id", sa.String(36), nullable=False),
        sa.Column("part_number", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(1000), nullable=False),
        sa.Column("metric_name", sa.String(500), nullable=False),
        sa.Column("service_category", sa.String(500), nullable=False),
        sa.Column("price_type", sa.String(50), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("range_min", sa.Float(), nullable=True),
        sa.Column("range_max", sa.Float(), nullable=True),
        sa.Column("range_unit", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["price_catalog_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_items_snapshot_part", "price_items", ["snapshot_id", "part_number"])

    op.create_table(
        "service_product_sku_mappings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("service_profile_id", sa.String(36), nullable=True),
        sa.Column("service_id", sa.String(80), nullable=False),
        sa.Column("tool_key", sa.String(120), nullable=False),
        sa.Column("part_number", sa.String(50), nullable=True),
        sa.Column("billing_metric_key", sa.String(150), nullable=False),
        sa.Column("formula_key", sa.String(100), nullable=False),
        sa.Column("predicates", sa.JSON(), nullable=False),
        sa.Column("is_billable", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["service_profile_id"], ["service_capability_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service_id",
            "part_number",
            "billing_metric_key",
            "version",
            name="uq_service_sku_mapping_version",
        ),
    )
    op.create_index(
        "ix_service_product_sku_mappings_service",
        "service_product_sku_mappings",
        ["service_id", "status"],
    )

    op.create_table(
        "deployment_scenarios",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("region", sa.String(100), nullable=False),
        sa.Column("price_mode", sa.String(50), nullable=False),
        sa.Column("technical_snapshot_id", sa.String(36), nullable=False),
        sa.Column("contract_months", sa.Integer(), nullable=False),
        sa.Column("environments", sa.JSON(), nullable=False),
        sa.Column("service_config", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["technical_snapshot_id"], ["volumetry_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deployment_scenarios_project", "deployment_scenarios", ["project_id", "status"])

    op.create_table(
        "bom_jobs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("scenario_id", sa.String(36), nullable=False),
        sa.Column("requested_by", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bom_snapshot_id", sa.String(36), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["scenario_id"], ["deployment_scenarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bom_jobs_project_status", "bom_jobs", ["project_id", "status"])

    op.create_table(
        "bom_snapshots",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("scenario_id", sa.String(36), nullable=False),
        sa.Column("technical_snapshot_id", sa.String(36), nullable=False),
        sa.Column("price_catalog_snapshot_id", sa.String(36), nullable=False),
        sa.Column("mapping_version", sa.String(100), nullable=False),
        sa.Column("engine_version", sa.String(50), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("coverage_pct", sa.Float(), nullable=False),
        sa.Column("monthly_total", sa.Float(), nullable=False),
        sa.Column("annual_total", sa.Float(), nullable=False),
        sa.Column("contract_total", sa.Float(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("publication_status", sa.String(50), nullable=False),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["scenario_id"], ["deployment_scenarios.id"]),
        sa.ForeignKeyConstraint(["technical_snapshot_id"], ["volumetry_snapshots.id"]),
        sa.ForeignKeyConstraint(["price_catalog_snapshot_id"], ["price_catalog_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bom_snapshots_project", "bom_snapshots", ["project_id", "created_at"])

    op.create_table(
        "bom_line_items",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("bom_snapshot_id", sa.String(36), nullable=False),
        sa.Column("environment", sa.String(100), nullable=False),
        sa.Column("service_id", sa.String(80), nullable=False),
        sa.Column("part_number", sa.String(50), nullable=True),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("metric_name", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(100), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("monthly_amount", sa.Float(), nullable=False),
        sa.Column("annual_amount", sa.Float(), nullable=False),
        sa.Column("contract_amount", sa.Float(), nullable=False),
        sa.Column("price_item_id", sa.String(36), nullable=True),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bom_snapshot_id"], ["bom_snapshots.id"]),
        sa.ForeignKeyConstraint(["price_item_id"], ["price_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bom_line_items_snapshot", "bom_line_items", ["bom_snapshot_id", "service_id"])

    _seed_pricing_governance()


def _seed_pricing_governance() -> None:
    now = datetime.now(UTC)
    sources = sa.table(
        "price_sources",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("source_type", sa.String()),
        sa.column("base_url", sa.Text()),
        sa.column("currency", sa.String()),
        sa.column("status", sa.String()),
        sa.column("config", sa.JSON()),
        sa.column("last_synced_at", sa.DateTime(timezone=True)),
        sa.column("created_by", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        sources,
        [
            {
                "id": PUBLIC_SOURCE_ID,
                "name": "Oracle OCI Public List Pricing",
                "source_type": "public_list",
                "base_url": PUBLIC_PRICING_URL,
                "currency": "USD",
                "status": "active",
                "config": {"documented": True, "query_parameters": ["partNumber", "currencyCode"]},
                "last_synced_at": None,
                "created_by": "migration",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    profiles = {
        row.service_id: row.id
        for row in op.get_bind().execute(
            sa.text("SELECT id, service_id FROM service_capability_profiles")
        )
    }
    mappings = sa.table(
        "service_product_sku_mappings",
        sa.column("id", sa.String()),
        sa.column("service_profile_id", sa.String()),
        sa.column("service_id", sa.String()),
        sa.column("tool_key", sa.String()),
        sa.column("part_number", sa.String()),
        sa.column("billing_metric_key", sa.String()),
        sa.column("formula_key", sa.String()),
        sa.column("predicates", sa.JSON()),
        sa.column("is_billable", sa.Boolean()),
        sa.column("status", sa.String()),
        sa.column("version", sa.String()),
        sa.column("source_url", sa.Text()),
        sa.column("confidence", sa.Float()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    definitions = [
        ("OIC3", "OIC Gen3", "B89639", "oic_peak_packs_hour", "hourly_capacity", {"edition": "standard", "byol": False}),
        ("OIC3", "OIC Gen3", "B89640", "oic_peak_packs_hour", "hourly_capacity", {"edition": "enterprise", "byol": False}),
        ("OIC3", "OIC Gen3", "B89643", "oic_peak_packs_hour", "hourly_capacity", {"edition": "standard", "byol": True}),
        ("OIC3", "OIC Gen3", "B89644", "oic_peak_packs_hour", "hourly_capacity", {"edition": "enterprise", "byol": True}),
        ("DATA_INTEGRATION", "OCI Data Integration", "B92598", "di_workspace_hours", "monthly_quantity", {}),
        ("DATA_INTEGRATION", "OCI Data Integration", "B92599", "di_data_processed_gb", "monthly_quantity", {}),
        ("DATA_INTEGRATION", "OCI Data Integration", "B93306", "di_operator_execution_hours", "monthly_quantity", {}),
        ("FUNCTIONS", "OCI Functions", "B90617", "functions_execution_10k_gb_s", "tiered_monthly", {}),
        ("FUNCTIONS", "OCI Functions", "B90618", "functions_invocation_millions", "tiered_monthly", {}),
        ("STREAMING", "OCI Streaming", "B90938", "streaming_transfer_gb", "monthly_quantity", {}),
        ("STREAMING", "OCI Streaming", "B90939", "streaming_storage_gb_hours", "monthly_quantity", {}),
        ("QUEUE", "OCI Queue", "B95697", "queue_request_millions", "tiered_monthly", {}),
        ("GOLDENGATE", "Oracle GoldenGate", "B92992", "goldengate_ocpu_hours", "monthly_quantity", {"byol": False}),
        ("GOLDENGATE", "Oracle GoldenGate", "B92993", "goldengate_ocpu_hours", "monthly_quantity", {"byol": True}),
        ("API_GATEWAY", "OCI API Gateway", "B92072", "api_gateway_call_millions", "monthly_quantity", {}),
        ("EVENTS", "OCI Events", None, "events", "non_billable", {}),
        ("PROCESS_AUTOMATION", "Process Automation", None, "process_automation", "included_with_oic_review", {}),
    ]
    rows = []
    for index, (service_id, tool_key, part_number, metric, formula, predicates) in enumerate(definitions, start=1):
        rows.append(
            {
                "id": f"fa510000-0000-4000-8000-{index:012d}",
                "service_profile_id": profiles.get(service_id),
                "service_id": service_id,
                "tool_key": tool_key,
                "part_number": part_number,
                "billing_metric_key": metric,
                "formula_key": formula,
                "predicates": predicates,
                "is_billable": part_number is not None,
                "status": "approved",
                "version": "1.0.0",
                "source_url": PUBLIC_PRICING_URL,
                "confidence": 1.0 if part_number else 0.9,
                "created_at": now,
                "updated_at": now,
            }
        )
    op.bulk_insert(mappings, rows)


def downgrade() -> None:
    op.drop_index("ix_bom_line_items_snapshot", table_name="bom_line_items")
    op.drop_table("bom_line_items")
    op.drop_index("ix_bom_snapshots_project", table_name="bom_snapshots")
    op.drop_table("bom_snapshots")
    op.drop_index("ix_bom_jobs_project_status", table_name="bom_jobs")
    op.drop_table("bom_jobs")
    op.drop_index("ix_deployment_scenarios_project", table_name="deployment_scenarios")
    op.drop_table("deployment_scenarios")
    op.drop_index("ix_service_product_sku_mappings_service", table_name="service_product_sku_mappings")
    op.drop_table("service_product_sku_mappings")
    op.drop_index("ix_price_items_snapshot_part", table_name="price_items")
    op.drop_table("price_items")
    op.drop_index("ix_price_catalog_snapshots_approval", table_name="price_catalog_snapshots")
    op.drop_table("price_catalog_snapshots")
    op.drop_index("ix_price_sync_jobs_status", table_name="price_sync_jobs")
    op.drop_table("price_sync_jobs")
    op.drop_index("ix_price_sources_status", table_name="price_sources")
    op.drop_table("price_sources")
