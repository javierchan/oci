"""Govern OCI quote quantities separately from measured service consumption."""

from alembic import op
import sqlalchemy as sa


revision = "20260715_0027"
down_revision = "20260714_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("usage_basis", sa.String(length=40), server_default="metered_usage", nullable=False),
    )
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("quote_rounding", sa.String(length=40), server_default="metered", nullable=False),
    )
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("requires_explicit_quantity", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "service_product_sku_mappings",
        sa.Column(
            "entry_guidance",
            sa.Text(),
            server_default="Enter the expected monthly usage.",
            nullable=False,
        ),
    )
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("quantity_presets", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )

    op.execute(
        """
        UPDATE service_product_sku_mappings
        SET quantity_behavior = 'packaged',
            quantity_increment = 1,
            minimum_quantity = 1,
            usage_basis = 'metered_usage',
            quote_rounding = 'whole_commercial_unit',
            requires_explicit_quantity = FALSE,
            entry_guidance = 'Enter expected monthly API calls in millions. The quote rounds demand up to whole 1M-call units; actual metered consumption may be prorated by Oracle.',
            quantity_presets = '[]'
        WHERE billing_metric_key = 'api_gateway_call_millions'
        """
    )
    op.execute(
        """
        UPDATE service_product_sku_mappings
        SET quantity_behavior = 'hourly',
            quantity_increment = 1,
            minimum_quantity = 0,
            usage_basis = 'provisioned_runtime',
            quote_rounding = 'whole_hour_plan',
            requires_explicit_quantity = TRUE,
            entry_guidance = 'Enter the hours each workspace will actually remain running. A stopped Data Integration workspace is unavailable and not billed; 744 hours means always on for the full planning month.',
            quantity_presets = json_build_array(
                json_build_object(
                    'label', 'Business hours',
                    'quantity', 160,
                    'description', 'Planning shortcut: 20 workdays at 8 hours.'
                ),
                json_build_object(
                    'label', 'Extended hours',
                    'quantity', 360,
                    'description', 'Planning shortcut for a longer controlled runtime window.'
                ),
                json_build_object(
                    'label', 'Always on',
                    'quantity', 744,
                    'description', '31 days at 24 hours; use only when the workspace stays running all month.'
                )
            )
        WHERE billing_metric_key = 'di_workspace_hours'
        """
    )
    op.execute(
        """
        UPDATE service_product_sku_mappings
        SET quantity_behavior = 'hourly',
            quantity_increment = 0.01666667,
            minimum_quantity = 0,
            usage_basis = 'utilized_runtime',
            quote_rounding = 'one_minute_minimum',
            requires_explicit_quantity = TRUE,
            entry_guidance = 'Enter accumulated Pipeline Operator execution hours. Oracle bills partial hours with a one-minute minimum; the first 30 execution hours per tenant and month are represented by the governed price tiers.',
            quantity_presets = '[]'
        WHERE billing_metric_key = 'di_operator_execution_hours'
        """
    )
    op.execute(
        """
        UPDATE service_product_sku_mappings
        SET usage_basis = 'metered_usage',
            quote_rounding = 'metered',
            requires_explicit_quantity = FALSE,
            entry_guidance = 'Enter the monthly gigabytes processed by Data Integration. This metric is independent from workspace running hours.',
            quantity_presets = '[]'
        WHERE billing_metric_key = 'di_data_processed_gb'
        """
    )


def downgrade() -> None:
    op.drop_column("service_product_sku_mappings", "quantity_presets")
    op.drop_column("service_product_sku_mappings", "entry_guidance")
    op.drop_column("service_product_sku_mappings", "requires_explicit_quantity")
    op.drop_column("service_product_sku_mappings", "quote_rounding")
    op.drop_column("service_product_sku_mappings", "usage_basis")
