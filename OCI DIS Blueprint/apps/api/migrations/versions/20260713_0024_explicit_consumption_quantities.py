"""Add governed explicit product quantities and normalized monthly ramp values."""

from alembic import op
import sqlalchemy as sa


revision = "20260713_0024"
down_revision = "20260712_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deployment_scenarios",
        sa.Column("consumption_model", sa.String(length=32), server_default="legacy_share", nullable=False),
    )
    op.execute("UPDATE deployment_scenarios SET consumption_model = 'legacy_share'")
    op.alter_column(
        "deployment_scenarios",
        "consumption_model",
        server_default="explicit_units",
    )

    op.add_column(
        "service_product_sku_mappings",
        sa.Column("quantity_behavior", sa.String(length=32), server_default="continuous", nullable=False),
    )
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("quantity_increment", sa.Numeric(28, 8), server_default="0.000001", nullable=False),
    )
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("minimum_quantity", sa.Numeric(28, 8), server_default="0", nullable=False),
    )
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("quantity_unit", sa.String(length=100), server_default="units", nullable=False),
    )
    op.execute(
        """
        UPDATE service_product_sku_mappings
        SET quantity_behavior = CASE billing_metric_key
                WHEN 'oic_peak_packs_hour' THEN 'packaged'
                WHEN 'di_workspace_hours' THEN 'hourly'
                WHEN 'di_operator_execution_hours' THEN 'hourly'
                WHEN 'goldengate_ocpu_hours' THEN 'hourly'
                WHEN 'events' THEN 'fixed_capacity'
                WHEN 'process_automation' THEN 'fixed_capacity'
                ELSE 'continuous'
            END,
            quantity_increment = CASE billing_metric_key
                WHEN 'oic_peak_packs_hour' THEN 1
                WHEN 'di_workspace_hours' THEN 1
                WHEN 'di_operator_execution_hours' THEN 0.01
                WHEN 'goldengate_ocpu_hours' THEN 1
                WHEN 'di_data_processed_gb' THEN 0.001
                WHEN 'streaming_transfer_gb' THEN 0.001
                WHEN 'streaming_storage_gb_hours' THEN 0.001
                ELSE 0.000001
            END,
            minimum_quantity = CASE billing_metric_key
                WHEN 'oic_peak_packs_hour' THEN 1
                ELSE 0
            END,
            quantity_unit = CASE billing_metric_key
                WHEN 'oic_peak_packs_hour' THEN 'message packs'
                WHEN 'di_workspace_hours' THEN 'workspace-hours'
                WHEN 'di_data_processed_gb' THEN 'GB'
                WHEN 'di_operator_execution_hours' THEN 'execution-hours'
                WHEN 'functions_execution_10k_gb_s' THEN '10K GB-s'
                WHEN 'functions_invocation_millions' THEN 'million invocations'
                WHEN 'streaming_transfer_gb' THEN 'GB transferred'
                WHEN 'streaming_storage_gb_hours' THEN 'GB-hours'
                WHEN 'queue_request_millions' THEN 'million requests'
                WHEN 'goldengate_ocpu_hours' THEN 'OCPU-hours'
                WHEN 'api_gateway_call_millions' THEN 'million API calls'
                WHEN 'events' THEN 'included'
                WHEN 'process_automation' THEN 'included'
                ELSE 'units'
            END
        """
    )

    op.add_column("deployment_ramp_phases", sa.Column("metric_key", sa.String(length=150)))
    op.add_column("deployment_ramp_phases", sa.Column("start_quantity", sa.Numeric(28, 8)))
    op.add_column("deployment_ramp_phases", sa.Column("end_quantity", sa.Numeric(28, 8)))
    op.add_column("deployment_ramp_phases", sa.Column("quantity_unit", sa.String(length=100)))
    op.create_index("ix_deployment_ramp_phases_metric", "deployment_ramp_phases", ["metric_key"])

    op.create_table(
        "deployment_ramp_period_quantities",
        sa.Column("ramp_phase_id", sa.String(length=36), nullable=False),
        sa.Column("period_index", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ramp_phase_id"], ["deployment_ramp_phases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ramp_phase_id", "period_index", name="uq_deployment_ramp_period"),
    )
    op.create_index(
        "ix_deployment_ramp_period_quantities_phase",
        "deployment_ramp_period_quantities",
        ["ramp_phase_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_deployment_ramp_period_quantities_phase",
        table_name="deployment_ramp_period_quantities",
    )
    op.drop_table("deployment_ramp_period_quantities")
    op.drop_index("ix_deployment_ramp_phases_metric", table_name="deployment_ramp_phases")
    op.drop_column("deployment_ramp_phases", "quantity_unit")
    op.drop_column("deployment_ramp_phases", "end_quantity")
    op.drop_column("deployment_ramp_phases", "start_quantity")
    op.drop_column("deployment_ramp_phases", "metric_key")
    op.drop_column("service_product_sku_mappings", "quantity_unit")
    op.drop_column("service_product_sku_mappings", "minimum_quantity")
    op.drop_column("service_product_sku_mappings", "quantity_increment")
    op.drop_column("service_product_sku_mappings", "quantity_behavior")
    op.drop_column("deployment_scenarios", "consumption_model")
