"""Align governed quantities with Oracle metering and tenancy-wide allowances."""

from alembic import op
import sqlalchemy as sa


revision = "20260715_0028"
down_revision = "20260715_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("aggregation_window", sa.String(length=40), server_default="calendar_month", nullable=False),
    )
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("proration_policy", sa.String(length=40), server_default="prorated", nullable=False),
    )
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("free_tier_scope", sa.String(length=40), server_default="none", nullable=False),
    )
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("planning_envelope_increment", sa.Numeric(28, 8), nullable=True),
    )
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("metering_policy", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )

    # API Gateway is metered in million-call units, but Oracle explicitly prorates
    # partial millions. A whole-million envelope is advisory and never replaces the
    # canonical billable quantity.
    bind.exec_driver_sql(
        """
        UPDATE service_product_sku_mappings
        SET quantity_behavior = 'continuous',
            quantity_increment = 0.000001,
            minimum_quantity = 0,
            usage_basis = 'metered_usage',
            quote_rounding = 'metered_prorated',
            aggregation_window = 'calendar_month',
            proration_policy = 'prorated',
            free_tier_scope = 'none',
            planning_envelope_increment = 1,
            requires_explicit_quantity = FALSE,
            entry_guidance = 'Enter expected monthly API calls in millions. Oracle prorates partial 1M-call units; the optional whole-million envelope is a planning reserve, not the billed quantity.',
            metering_policy = '{"billing_unit":"1000000_api_calls","partial_unit":"prorated","planning_envelope_only":true}',
            version = '1.2.0'
        WHERE billing_metric_key = 'api_gateway_call_millions'
        """
    )
    bind.exec_driver_sql(
        """
        UPDATE service_product_sku_mappings
        SET aggregation_window = 'peak_hour',
            proration_policy = 'whole_capacity_pack',
            free_tier_scope = 'none',
            metering_policy = json_build_object(
                'message_block_kb', 50,
                'pack_messages_per_hour', CASE WHEN COALESCE((predicates->>'byol')::boolean, FALSE) THEN 20000 ELSE 5000 END,
                'requires_activity_role', TRUE,
                'same_instance_internal_calls', 'excluded'
            ),
            version = '1.2.0'
        WHERE billing_metric_key = 'oic_peak_packs_hour'
        """
    )
    bind.exec_driver_sql(
        """
        UPDATE service_product_sku_mappings
        SET aggregation_window = 'provisioned_runtime',
            proration_policy = 'whole_hour_plan',
            free_tier_scope = 'none',
            metering_policy = '{"runtime_state":"running","stopped_state":"not_billed","default_runtime":null}',
            version = '1.2.0'
        WHERE billing_metric_key = 'di_workspace_hours'
        """
    )
    bind.exec_driver_sql(
        """
        UPDATE service_product_sku_mappings
        SET aggregation_window = 'calendar_month',
            proration_policy = 'prorated',
            free_tier_scope = 'none',
            metering_policy = '{"billing_unit":"gb_processed"}',
            version = '1.2.0'
        WHERE billing_metric_key = 'di_data_processed_gb'
        """
    )
    bind.exec_driver_sql(
        """
        UPDATE service_product_sku_mappings
        SET aggregation_window = 'tenant_month',
            proration_policy = 'one_minute_minimum',
            free_tier_scope = 'tenant_month',
            metering_policy = '{"minimum_runtime_minutes":1,"free_hours_per_tenant_month":30}',
            version = '1.2.0'
        WHERE billing_metric_key = 'di_operator_execution_hours'
        """
    )
    bind.exec_driver_sql(
        """
        UPDATE service_product_sku_mappings
        SET aggregation_window = 'tenant_month',
            proration_policy = 'prorated',
            free_tier_scope = 'tenant_month',
            metering_policy = CASE billing_metric_key
                WHEN 'functions_execution_10k_gb_s' THEN '{"free_gb_seconds_per_tenant_month":400000,"billing_unit_gb_seconds":10000}'::json
                ELSE '{"free_invocations_per_tenant_month":2000000,"billing_unit_invocations":1000000}'::json
            END,
            version = '1.2.0'
        WHERE billing_metric_key IN ('functions_execution_10k_gb_s', 'functions_invocation_millions')
        """
    )
    bind.exec_driver_sql(
        """
        UPDATE service_product_sku_mappings
        SET aggregation_window = 'calendar_month',
            proration_policy = 'prorated',
            free_tier_scope = 'none',
            requires_explicit_quantity = TRUE,
            entry_guidance = CASE billing_metric_key
                WHEN 'streaming_transfer_gb' THEN 'Enter PUT and GET transfer in billed GB. Do not apply a fixed read/write multiplier unless consumer evidence supports it.'
                ELSE 'Enter retained GB-hours from stream size and retention policy; transfer volume alone is not sufficient.'
            END,
            metering_policy = CASE billing_metric_key
                WHEN 'streaming_transfer_gb' THEN '{"operations":["put","get"],"default_operation_multiplier":null}'::json
                ELSE '{"unit":"gb_hour","requires_retention_evidence":true}'::json
            END,
            version = '1.2.0'
        WHERE billing_metric_key IN ('streaming_transfer_gb', 'streaming_storage_gb_hours')
        """
    )
    bind.exec_driver_sql(
        """
        UPDATE service_product_sku_mappings
        SET quantity_behavior = 'continuous',
            quantity_increment = 0.000001,
            minimum_quantity = 0,
            aggregation_window = 'tenant_month',
            proration_policy = 'event_block_ceiling_then_prorated',
            free_tier_scope = 'tenant_month',
            requires_explicit_quantity = TRUE,
            entry_guidance = 'Enter monthly Queue request units after rounding each push, get, delete, or update operation to 64 KB blocks. Do not infer a fixed operation count without flow evidence.',
            metering_policy = '{"request_block_kb":64,"operations":["push","get","delete","update"],"free_requests_per_tenant_month":1000000,"default_operations_per_message":null}',
            version = '1.2.0'
        WHERE billing_metric_key = 'queue_request_millions'
        """
    )
    bind.exec_driver_sql(
        """
        UPDATE service_product_sku_mappings
        SET quantity_behavior = 'hourly',
            quantity_increment = 0.01666667,
            minimum_quantity = 0,
            aggregation_window = 'provisioned_runtime',
            proration_policy = 'one_minute_minimum',
            free_tier_scope = 'none',
            requires_explicit_quantity = TRUE,
            entry_guidance = 'Enter GoldenGate OCPU-hours per environment. Partial OCPU-hours use a one-minute minimum; confirm OCPU count, runtime, and BYOL eligibility.',
            metering_policy = '{"minimum_runtime_minutes":1,"requires_ocpu_count":true,"requires_byol_decision":true}',
            version = '1.2.0'
        WHERE billing_metric_key = 'goldengate_ocpu_hours'
        """
    )
    bind.exec_driver_sql(
        """
        UPDATE service_product_sku_mappings
        SET aggregation_window = 'non_billable',
            proration_policy = 'included',
            free_tier_scope = 'none',
            metering_policy = CASE billing_metric_key
                WHEN 'process_automation' THEN '{"direct_sku":"included","contributes_to_oic_messages":true}'::json
                ELSE '{"direct_sku":"none","downstream_usage_may_bill":true}'::json
            END,
            version = '1.2.0'
        WHERE billing_metric_key IN ('events', 'process_automation')
        """
    )


def downgrade() -> None:
    op.drop_column("service_product_sku_mappings", "metering_policy")
    op.drop_column("service_product_sku_mappings", "planning_envelope_increment")
    op.drop_column("service_product_sku_mappings", "free_tier_scope")
    op.drop_column("service_product_sku_mappings", "proration_policy")
    op.drop_column("service_product_sku_mappings", "aggregation_window")
