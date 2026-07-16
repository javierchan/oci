"""Govern commercial coverage for every DIS architecture product."""

from __future__ import annotations

from datetime import UTC, datetime

from alembic import op
import sqlalchemy as sa


revision = "20260715_0029"
down_revision = "20260715_0028"
branch_labels = None
depends_on = None


POLICIES = [
    ("API_GATEWAY", "direct_metered", "quote_ready", "direct_mapping_required", ["OCI API Gateway"], [], ["monthly API calls"], "Price prorated API-call demand; do not round the billed quantity to a whole million.", ["https://www.oracle.com/cloud/price-list/"]),
    ("CONNECTOR_HUB", "dependent_cost", "input_required", "dependencies_required", ["OCI Connector Hub", "Service Connector Hub", "Connector Hub"], ["OBJECT_STORAGE", "STREAMING", "FUNCTIONS"], ["selected source, target, and task"], "Connector Hub has no direct service charge; quote the explicitly selected downstream services.", ["https://docs.oracle.com/en-us/iaas/Content/connector-hub/overview.htm"]),
    ("DATA_CATALOG", "included_non_billable", "quote_ready", "included_zero", ["OCI Data Catalog", "Data Catalog"], [], [], "Data Catalog is represented as an included product line; dependent storage or processing remains separate.", ["https://www.oracle.com/big-data/data-catalog/"]),
    ("DATA_FLOW", "dependent_cost", "input_required", "dependencies_required", ["OCI Data Flow", "Data Flow"], ["OBJECT_STORAGE"], ["Spark shape, OCPUs, runtime, storage"], "The Data Flow service is included; price its Compute, storage, and network dependencies from an approved design.", ["https://www.oracle.com/cloud/iaas-paas/"]),
    ("DATA_INTEGRATION", "direct_metered", "quote_ready", "direct_mapping_required", ["OCI Data Integration", "Data Integration"], [], ["workspace runtime, data processed, operator runtime"], "Quote each Data Integration meter independently using actual runtime rather than a universal 744-hour assumption.", ["https://www.oracle.com/cloud/price-list/"]),
    ("ENTERPRISE_DATA_QUALITY", "license_plus_infrastructure", "rate_card_required", "external_rate_required", ["Oracle Enterprise Data Quality", "Enterprise Data Quality", "EDQ"], [], ["authorized license metric, support, runtime infrastructure"], "A public OCI meter is not governed for EDQ; require an authorized rate card and deployment infrastructure before publication.", ["https://www.oracle.com/middleware/technologies/enterprise-data-quality.html"]),
    ("FUNCTIONS", "direct_metered", "quote_ready", "direct_mapping_required", ["OCI Functions", "Functions"], [], ["GB-seconds, invocations"], "Apply tenancy-month Free Tier once across environments and price both execution and invocation meters.", ["https://www.oracle.com/cloud/price-list/"]),
    ("GOLDENGATE", "direct_metered", "quote_ready", "direct_mapping_required", ["Oracle GoldenGate", "OCI GoldenGate", "GoldenGate"], [], ["OCPUs, runtime, BYOL eligibility"], "Quote actual OCPU runtime per environment and preserve the PAYG or BYOL decision.", ["https://www.oracle.com/cloud/price-list/"]),
    ("GOLDENGATE_DATA_TRANSFORMS", "dependent_cost", "input_required", "dependencies_required", ["OCI GoldenGate Data Transforms", "GoldenGate Data Transforms", "Data Transforms"], ["GOLDENGATE"], ["GoldenGate deployment and runtime"], "Treat Data Transforms as a GoldenGate-dependent capability and price the governed GoldenGate deployment.", ["https://docs.oracle.com/en/cloud/paas/goldengate-service/index.html"]),
    ("IAM", "included_with_optional_addons", "quote_ready", "included_zero", ["OCI IAM", "IAM", "Identity and Access Management"], [], ["paid identity add-ons, if used"], "Represent base IAM as included and add paid external-user, premium, token, or SMS meters only when explicitly selected.", ["https://www.oracle.com/cloud/price-list/"]),
    ("OBJECT_STORAGE", "direct_metered", "quote_ready", "direct_mapping_required", ["OCI Object Storage", "Object Storage"], [], ["stored GB-months, request units, tier and retention"], "Price storage and request meters separately; Free Tier allocation is tenancy-wide and must be confirmed.", ["https://www.oracle.com/cloud/price-list/"]),
    ("OBSERVABILITY", "direct_metered", "input_required", "explicit_metric_selection", ["OCI Observability", "OCI Monitoring", "OCI Logging", "OCI Logging Analytics", "Log Analytics", "Observability"], [], ["selected telemetry products, ingestion, retrieval, retention"], "Select only the observability meters the design actually uses; no paid metric is assumed by default.", ["https://www.oracle.com/cloud/price-list/"]),
    ("ODI", "license_plus_infrastructure", "quote_ready", "direct_mapping_required", ["Oracle Data Integrator", "ODI", "ODI Cloud Service"], [], ["OCPUs, runtime, PAYG or BYOL"], "Quote ODI OCPU-hours with an explicit PAYG or BYOL license decision and runtime plan.", ["https://www.oracle.com/a/ocom/docs/corporate/pricing/oracle-paas-and-iaas-global-price-list.pdf"]),
    ("OIC3", "direct_metered", "quote_ready", "direct_mapping_required", ["OIC Gen3", "OCI Integration", "Oracle Integration", "Oracle Integration 3"], [], ["edition, BYOL, peak message packs"], "Preserve Standard or Enterprise and BYOL per environment; price whole peak-hour message packs.", ["https://www.oracle.com/cloud/price-list/"]),
    ("ORDS", "dependent_cost", "input_required", "dependencies_required", ["ORDS", "Oracle REST Data Services"], [], ["hosting platform, database, compute and network"], "ORDS has no standalone managed OCI meter; quote the selected database and hosting platform.", ["https://www.oracle.com/database/technologies/appdev/rest.html"]),
    ("QUEUE", "direct_metered", "quote_ready", "direct_mapping_required", ["OCI Queue", "Queue"], [], ["operation mix and 64 KB request blocks"], "Calculate request units from evidenced push, get, delete, and update operations before applying the tenancy Free Tier.", ["https://www.oracle.com/cloud/price-list/"]),
    ("STREAMING", "direct_metered", "quote_ready", "direct_mapping_required", ["OCI Streaming", "Streaming"], [], ["PUT/GET transfer and retained GB-hours"], "Price transfer and storage separately using evidenced consumers and retention; do not infer a fixed multiplier.", ["https://www.oracle.com/cloud/price-list/"]),
    ("STREAM_ANALYTICS", "direct_metered", "quote_ready", "direct_mapping_required", ["OCI Stream Analytics", "Oracle Stream Analytics", "Stream Analytics"], [], ["OCPUs and active runtime"], "Quote explicit Stream Analytics OCPU-hours per environment.", ["https://www.oracle.com/a/ocom/docs/corporate/pricing/oracle-paas-and-iaas-global-price-list.pdf"]),
]


def upgrade() -> None:
    op.add_column(
        "service_product_sku_mappings",
        sa.Column("selection_policy", sa.String(length=32), server_default="required", nullable=False),
    )
    op.create_table(
        "service_commercial_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("service_profile_id", sa.String(length=36), nullable=False),
        sa.Column("service_id", sa.String(length=80), nullable=False),
        sa.Column("classification", sa.String(length=40), nullable=False),
        sa.Column("readiness", sa.String(length=32), nullable=False),
        sa.Column("publication_policy", sa.String(length=40), nullable=False),
        sa.Column("tool_aliases", sa.JSON(), nullable=False),
        sa.Column("dependent_service_ids", sa.JSON(), nullable=False),
        sa.Column("required_inputs", sa.JSON(), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=False),
        sa.Column("source_urls", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["service_profile_id"], ["service_capability_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_profile_id", name="uq_service_commercial_policy_profile"),
        sa.UniqueConstraint("service_id", name="uq_service_commercial_policy_service"),
    )
    op.create_index("ix_service_commercial_policy_readiness", "service_commercial_policies", ["readiness", "status"])

    now = datetime.now(UTC)
    table = sa.table(
        "service_commercial_policies",
        sa.column("id", sa.String()), sa.column("service_profile_id", sa.String()),
        sa.column("service_id", sa.String()), sa.column("classification", sa.String()),
        sa.column("readiness", sa.String()), sa.column("publication_policy", sa.String()),
        sa.column("tool_aliases", sa.JSON()), sa.column("dependent_service_ids", sa.JSON()),
        sa.column("required_inputs", sa.JSON()), sa.column("guidance", sa.Text()),
        sa.column("source_urls", sa.JSON()), sa.column("status", sa.String()),
        sa.column("version", sa.String()), sa.column("confidence", sa.Float()),
        sa.column("created_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    profile_ids = {row.service_id: row.id for row in op.get_bind().execute(sa.text("SELECT id, service_id FROM service_capability_profiles"))}
    rows = []
    for index, policy in enumerate(POLICIES, start=1):
        service_id, classification, readiness, publication, aliases, dependencies, inputs, guidance, urls = policy
        rows.append({
            "id": f"02900000-0000-4000-8000-{index:012d}", "service_profile_id": profile_ids[service_id],
            "service_id": service_id, "classification": classification, "readiness": readiness,
            "publication_policy": publication, "tool_aliases": aliases,
            "dependent_service_ids": dependencies, "required_inputs": inputs, "guidance": guidance,
            "source_urls": urls, "status": "approved", "version": "1.0.0", "confidence": 1.0,
            "created_at": now, "updated_at": now,
        })
    op.bulk_insert(table, rows)

    # IAM and Observability add-ons are available to select, but must never be
    # silently added to a scenario merely because the product is present.
    _insert_mapping("02910000-0000-4000-8000-000000000001", "OBJECT_STORAGE", "OCI Object Storage", "B91628", "object_storage_gb_months", "GB-months", "continuous", 0.001, "required", "Enter average stored GB for each month and storage tier.")
    _insert_mapping("02910000-0000-4000-8000-000000000002", "OBJECT_STORAGE", "OCI Object Storage", "B91627", "object_storage_request_10k", "10K requests", "continuous", 0.0001, "required", "Enter monthly request operations in 10K-request units after confirming Free Tier allocation.")
    _insert_mapping("02910000-0000-4000-8000-000000000003", "ODI", "Oracle Data Integrator", "B88299", "odi_ocpu_hours", "OCPU-hours", "hourly", 0.01666667, "required", "Enter ODI OCPUs multiplied by active runtime.", '{"byol":false}')
    _insert_mapping("02910000-0000-4000-8000-000000000004", "ODI", "Oracle Data Integrator", "B88406", "odi_ocpu_hours", "OCPU-hours", "hourly", 0.01666667, "required", "Enter ODI OCPUs multiplied by active runtime and confirm BYOL eligibility.", '{"byol":true}')
    _insert_mapping("02910000-0000-4000-8000-000000000005", "STREAM_ANALYTICS", "OCI Stream Analytics", "B92695", "stream_analytics_ocpu_hours", "OCPU-hours", "hourly", 0.01666667, "required", "Enter provisioned OCPUs multiplied by active runtime.")
    _insert_mapping("02910000-0000-4000-8000-000000000006", "IAM", "OCI IAM", "B90936", "iam_foundation", "included units", "fixed_capacity", 1, "optional", "Base IAM is represented as included; select paid add-ons only when used.", billable=False)
    for index, part, metric, unit in [
        (7, "B112199", "iam_external_active_users", "active users/month"),
        (8, "B93493", "iam_external_users", "users/month"),
        (9, "B93494", "iam_oracle_apps_premium_users", "users/month"),
        (10, "B93495", "iam_premium_users", "users/month"),
        (11, "B93496", "iam_sms", "messages"),
        (12, "B93497", "iam_tokens", "tokens"),
    ]:
        _insert_mapping(f"02910000-0000-4000-8000-{index:012d}", "IAM", "OCI IAM", part, metric, unit, "continuous", 1, "optional", "Select and enter this paid IAM add-on only when the architecture requires it.")
    for index, part, metric, unit in [
        (13, "B90925", "monitoring_ingestion_million_datapoints", "million datapoints"),
        (14, "B90926", "monitoring_retrieval_million_datapoints", "million datapoints"),
        (15, "B92593", "logging_storage_gb_months", "GB-months"),
        (16, "B95634", "log_analytics_active_storage_units", "storage units/month"),
        (17, "B92809", "log_analytics_archival_storage_unit_hours", "storage unit-hours"),
    ]:
        _insert_mapping(f"02910000-0000-4000-8000-{index:012d}", "OBSERVABILITY", "OCI Observability", part, metric, unit, "continuous", 0.000001, "optional", "Select this meter only when telemetry scope and retention are evidenced.")


def _insert_mapping(mapping_id: str, service_id: str, tool_key: str, part_number: str, metric: str, unit: str, behavior: str, increment: float, selection: str, guidance: str, predicates: str = "{}", *, billable: bool = True) -> None:
    op.get_bind().execute(sa.text("""
        INSERT INTO service_product_sku_mappings
        (id, service_profile_id, service_id, tool_key, part_number, billing_metric_key, formula_key,
         quantity_behavior, quantity_increment, minimum_quantity, quantity_unit, usage_basis,
         quote_rounding, aggregation_window, proration_policy, free_tier_scope,
         planning_envelope_increment, metering_policy, selection_policy, requires_explicit_quantity,
         entry_guidance, quantity_presets, predicates, is_billable, status, version, source_url,
         confidence, created_at, updated_at)
        SELECT CAST(:id AS varchar), id, CAST(:service_id AS varchar), CAST(:tool_key AS varchar),
               CAST(:part_number AS varchar), CAST(:metric AS varchar), 'monthly_quantity',
               CAST(:behavior AS varchar), CAST(:increment AS numeric), 0, CAST(:unit AS varchar),
               'metered_usage', 'metered', 'calendar_month',
               'prorated', 'none', NULL, '{}'::json, :selection, TRUE, :guidance, '[]'::json,
               CAST(:predicates AS json), CAST(:billable AS boolean), 'approved', '1.3.0',
               'https://www.oracle.com/cloud/price-list/', 1.0, NOW(), NOW()
        FROM service_capability_profiles WHERE service_id = CAST(:service_id AS varchar)
    """), {"id": mapping_id, "service_id": service_id, "tool_key": tool_key, "part_number": part_number, "metric": metric, "behavior": behavior, "increment": increment, "unit": unit, "selection": selection, "guidance": guidance, "predicates": predicates, "billable": billable})


def downgrade() -> None:
    op.execute("DELETE FROM service_product_sku_mappings WHERE id LIKE '02910000-%'")
    op.drop_index("ix_service_commercial_policy_readiness", table_name="service_commercial_policies")
    op.drop_table("service_commercial_policies")
    op.drop_column("service_product_sku_mappings", "selection_policy")
