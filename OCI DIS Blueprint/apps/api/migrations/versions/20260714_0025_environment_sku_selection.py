"""Persist the governed commercial SKU selection on every environment metric plan."""

from alembic import op
import sqlalchemy as sa


revision = "20260714_0025"
down_revision = "20260713_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "deployment_ramp_phases",
        sa.Column("sku_mapping_id", sa.String(length=36)),
    )
    op.create_foreign_key(
        "fk_deployment_ramp_phase_sku_mapping",
        "deployment_ramp_phases",
        "service_product_sku_mappings",
        ["sku_mapping_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_deployment_ramp_phases_sku_mapping",
        "deployment_ramp_phases",
        ["sku_mapping_id"],
    )
    op.execute(
        """
        UPDATE deployment_ramp_phases AS phase
        SET sku_mapping_id = (
            SELECT mapping.id
            FROM service_product_sku_mappings AS mapping
            JOIN deployment_environment_plans AS environment
              ON environment.id = phase.environment_plan_id
            JOIN deployment_scenarios AS scenario
              ON scenario.id = environment.scenario_id
            WHERE mapping.service_id = phase.service_id
              AND mapping.billing_metric_key = phase.metric_key
              AND mapping.status = 'approved'
            ORDER BY
              CASE
                WHEN mapping.predicates::jsonb <@ COALESCE(
                  scenario.service_config::jsonb -> phase.service_id,
                  '{}'::jsonb
                ) THEN 0
                WHEN mapping.predicates::jsonb = '{}'::jsonb THEN 1
                ELSE 2
              END,
              mapping.created_at,
              mapping.id
            LIMIT 1
        )
        WHERE phase.metric_key IS NOT NULL
          AND phase.sku_mapping_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_deployment_ramp_phases_sku_mapping", table_name="deployment_ramp_phases")
    op.drop_constraint(
        "fk_deployment_ramp_phase_sku_mapping",
        "deployment_ramp_phases",
        type_="foreignkey",
    )
    op.drop_column("deployment_ramp_phases", "sku_mapping_id")
