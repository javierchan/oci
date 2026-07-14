"""Normalize deployment ramps and persist immutable monthly BOM periods."""

from alembic import op
import sqlalchemy as sa


revision = "20260712_0023"
down_revision = "20260712_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deployment_scenarios", sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column(
        "deployment_scenarios",
        sa.Column("proration_policy", sa.String(length=32), server_default="full_month", nullable=False),
    )
    op.execute(
        """
        UPDATE deployment_scenarios
        SET start_date = date_trunc('month', created_at)::date
        WHERE start_date IS NULL
        """
    )
    op.alter_column("deployment_scenarios", "start_date", nullable=False)

    op.create_table(
        "deployment_environment_plans",
        sa.Column("scenario_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("active_hours_month", sa.Numeric(10, 2), nullable=False),
        sa.Column("demand_share", sa.Numeric(12, 8), nullable=False),
        sa.Column("ha_multiplier", sa.Numeric(12, 8), nullable=False),
        sa.Column("dr_role", sa.String(length=20), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scenario_id"], ["deployment_scenarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scenario_id", "name", name="uq_deployment_environment_scenario_name"),
    )
    op.create_index("ix_deployment_environment_plans_scenario", "deployment_environment_plans", ["scenario_id"])

    op.create_table(
        "deployment_ramp_phases",
        sa.Column("environment_plan_id", sa.String(length=36), nullable=False),
        sa.Column("service_id", sa.String(length=80), nullable=True),
        sa.Column("start_month", sa.Integer(), nullable=False),
        sa.Column("end_month", sa.Integer(), nullable=False),
        sa.Column("start_multiplier", sa.Numeric(8, 6), nullable=False),
        sa.Column("end_multiplier", sa.Numeric(8, 6), nullable=False),
        sa.Column("interpolation", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["environment_plan_id"], ["deployment_environment_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deployment_ramp_phases_environment", "deployment_ramp_phases", ["environment_plan_id"])
    op.create_index("ix_deployment_ramp_phases_service", "deployment_ramp_phases", ["service_id"])

    op.execute(
        """
        INSERT INTO deployment_environment_plans (
            id, scenario_id, name, sequence, active_hours_month, demand_share,
            ha_multiplier, dr_role, created_at, updated_at
        )
        SELECT
            substr(md5(s.id || ':environment:' || env.ordinality::text), 1, 8) || '-' ||
            substr(md5(s.id || ':environment:' || env.ordinality::text), 9, 4) || '-' ||
            substr(md5(s.id || ':environment:' || env.ordinality::text), 13, 4) || '-' ||
            substr(md5(s.id || ':environment:' || env.ordinality::text), 17, 4) || '-' ||
            substr(md5(s.id || ':environment:' || env.ordinality::text), 21, 12),
            s.id,
            COALESCE(NULLIF(env.value->>'name', ''), 'Environment ' || env.ordinality::text),
            env.ordinality::integer,
            COALESCE((env.value->>'active_hours_month')::numeric, 744),
            COALESCE((env.value->>'demand_share')::numeric, 1),
            COALESCE((env.value->>'ha_multiplier')::numeric, 1),
            COALESCE(NULLIF(env.value->>'dr_role', ''), 'primary'),
            s.created_at,
            s.updated_at
        FROM deployment_scenarios s
        CROSS JOIN LATERAL json_array_elements(s.environments) WITH ORDINALITY AS env(value, ordinality)
        """
    )
    op.execute(
        """
        INSERT INTO deployment_ramp_phases (
            id, environment_plan_id, service_id, start_month, end_month,
            start_multiplier, end_multiplier, interpolation, rationale, created_at, updated_at
        )
        SELECT
            substr(md5(p.id || ':phase:1'), 1, 8) || '-' ||
            substr(md5(p.id || ':phase:1'), 9, 4) || '-' ||
            substr(md5(p.id || ':phase:1'), 13, 4) || '-' ||
            substr(md5(p.id || ':phase:1'), 17, 4) || '-' ||
            substr(md5(p.id || ':phase:1'), 21, 12),
            p.id, NULL, 1, s.contract_months, 1, 1, 'step',
            'Backfilled flat schedule from the pre-ramp scenario contract.',
            p.created_at, p.updated_at
        FROM deployment_environment_plans p
        JOIN deployment_scenarios s ON s.id = p.scenario_id
        """
    )
    op.drop_column("deployment_scenarios", "environments")

    op.add_column("bom_snapshots", sa.Column("steady_state_monthly_total", sa.Numeric(24, 2), nullable=True))
    op.add_column("bom_snapshots", sa.Column("peak_monthly_total", sa.Numeric(24, 2), nullable=True))
    op.add_column("bom_snapshots", sa.Column("ramp_deferred_amount", sa.Numeric(24, 2), nullable=True))
    op.add_column("bom_snapshots", sa.Column("first_active_period", sa.Integer(), nullable=True))
    op.add_column("bom_snapshots", sa.Column("steady_state_period", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE bom_snapshots
        SET steady_state_monthly_total = monthly_total,
            peak_monthly_total = monthly_total,
            ramp_deferred_amount = 0,
            first_active_period = CASE WHEN monthly_total > 0 THEN 1 ELSE NULL END,
            steady_state_period = CASE WHEN monthly_total > 0 THEN 1 ELSE NULL END
        """
    )
    op.alter_column("bom_snapshots", "steady_state_monthly_total", nullable=False)
    op.alter_column("bom_snapshots", "peak_monthly_total", nullable=False)
    op.alter_column("bom_snapshots", "ramp_deferred_amount", nullable=False)

    op.create_table(
        "bom_line_periods",
        sa.Column("bom_line_item_id", sa.String(length=36), nullable=False),
        sa.Column("period_index", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("multiplier", sa.Numeric(8, 6), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 8), nullable=False),
        sa.Column("active_hours", sa.Numeric(12, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(24, 10), nullable=False),
        sa.Column("amount", sa.Numeric(24, 2), nullable=False),
        sa.Column("selected_price_item_id", sa.String(length=36), nullable=True),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bom_line_item_id"], ["bom_line_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["selected_price_item_id"], ["price_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bom_line_item_id", "period_index", name="uq_bom_line_period"),
    )
    op.create_index("ix_bom_line_periods_line", "bom_line_periods", ["bom_line_item_id"])
    op.create_index("ix_bom_line_periods_start", "bom_line_periods", ["period_start"])
    op.execute(
        """
        INSERT INTO bom_line_periods (
            id, bom_line_item_id, period_index, period_start, multiplier, quantity,
            active_hours, unit_price, amount, selected_price_item_id, formula, inputs,
            status, warnings, provenance, created_at, updated_at
        )
        SELECT
            substr(md5(l.id || ':period:' || month_index::text), 1, 8) || '-' ||
            substr(md5(l.id || ':period:' || month_index::text), 9, 4) || '-' ||
            substr(md5(l.id || ':period:' || month_index::text), 13, 4) || '-' ||
            substr(md5(l.id || ':period:' || month_index::text), 17, 4) || '-' ||
            substr(md5(l.id || ':period:' || month_index::text), 21, 12),
            l.id, month_index,
            (s.start_date + ((month_index - 1) || ' months')::interval)::date,
            1, l.quantity,
            COALESCE(NULLIF(l.inputs->>'hours', '')::numeric, 0),
            l.unit_price, l.monthly_amount, l.price_item_id, l.formula, l.inputs,
            l.status, l.warnings, l.provenance, l.created_at, l.updated_at
        FROM bom_line_items l
        JOIN bom_snapshots b ON b.id = l.bom_snapshot_id
        JOIN deployment_scenarios s ON s.id = b.scenario_id
        CROSS JOIN LATERAL generate_series(1, s.contract_months) AS month_index
        """
    )


def downgrade() -> None:
    op.drop_index("ix_bom_line_periods_start", table_name="bom_line_periods")
    op.drop_index("ix_bom_line_periods_line", table_name="bom_line_periods")
    op.drop_table("bom_line_periods")
    op.drop_column("bom_snapshots", "steady_state_period")
    op.drop_column("bom_snapshots", "first_active_period")
    op.drop_column("bom_snapshots", "ramp_deferred_amount")
    op.drop_column("bom_snapshots", "peak_monthly_total")
    op.drop_column("bom_snapshots", "steady_state_monthly_total")

    op.add_column("deployment_scenarios", sa.Column("environments", sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE deployment_scenarios s
        SET environments = payload.environments
        FROM (
            SELECT p.scenario_id,
                json_agg(json_build_object(
                    'name', p.name,
                    'active_hours_month', p.active_hours_month,
                    'active_months_year', 12,
                    'demand_share', p.demand_share,
                    'ha_multiplier', p.ha_multiplier,
                    'dr_role', p.dr_role
                ) ORDER BY p.sequence) AS environments
            FROM deployment_environment_plans p
            GROUP BY p.scenario_id
        ) payload
        WHERE payload.scenario_id = s.id
        """
    )
    op.execute("UPDATE deployment_scenarios SET environments = '[]'::json WHERE environments IS NULL")
    op.alter_column("deployment_scenarios", "environments", nullable=False)
    op.drop_index("ix_deployment_ramp_phases_service", table_name="deployment_ramp_phases")
    op.drop_index("ix_deployment_ramp_phases_environment", table_name="deployment_ramp_phases")
    op.drop_table("deployment_ramp_phases")
    op.drop_index("ix_deployment_environment_plans_scenario", table_name="deployment_environment_plans")
    op.drop_table("deployment_environment_plans")
    op.drop_column("deployment_scenarios", "proration_policy")
    op.drop_column("deployment_scenarios", "start_date")
