"""Integration coverage for governed OCI price catalogs and BOM generation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import (
    BomLineItem,
    BomLinePeriod,
    BomSnapshot,
    CatalogIntegration,
    CommercialDocumentSnapshot,
    CommercialEvidenceReference,
    CommercialException,
    CommercialRelease,
    CommercialRuleFamily,
    CommercialSku,
    DeploymentScenario,
    DeploymentEnvironmentPlan,
    DeploymentRampPhase,
    GovernanceChangeSet,
    PriceCatalogSnapshot,
    PriceItem,
    PriceSource,
    PriceSyncJob,
    Project,
    ServiceProductSkuMapping,
    ServiceCommercialPolicy,
    VolumetrySnapshot,
    SkuCommercialConstraint,
    SkuCommercialTerm,
)
from app.models.project import ProjectStatus
from app.services import bom_service, pricing_service
from app.schemas.pricing import BomReviewRequest


async def _seed_approved_commercial_release(
    session: AsyncSession,
    catalog: PriceCatalogSnapshot,
    mappings: list[ServiceProductSkuMapping],
) -> CommercialRelease:
    """Create the minimum complete governed contract required by a new BOM."""

    document = CommercialDocumentSnapshot(
        document_kind="oracle_localizable_price_list",
        source_name="Oracle test price list",
        source_url="test://oracle-price-list",
        original_filename="oracle-price-list.xlsx",
        storage_reference="minio://pricing/oracle-price-list.xlsx",
        content_hash=f"document-{catalog.content_hash}",
        parser_version="test-1",
        currency=catalog.currency,
        status="approved_evidence",
        record_count=len(mappings),
        retrieved_at=datetime.now(UTC),
        manifest={"price_snapshot_id": catalog.id},
        approved_by="test",
        approved_at=datetime.now(UTC),
    )
    session.add(document)
    await session.flush()
    part_numbers: list[str] = []
    term_ids_by_part: dict[str, str] = {}
    rule_ids_by_part: dict[str, str] = {}
    for mapping in mappings:
        assert mapping.part_number is not None
        part_numbers.append(mapping.part_number)
        family_key = f"test::{mapping.part_number.casefold()}"
        sku = CommercialSku(
            part_number=mapping.part_number,
            display_name=mapping.tool_key,
            service_category="Integration",
            lifecycle_status="active",
            identity_metadata={},
        )
        session.add(sku)
        await session.flush()
        term = SkuCommercialTerm(
            document_snapshot_id=document.id,
            commercial_sku_id=sku.id,
            price_catalog_snapshot_id=catalog.id,
            part_number=mapping.part_number,
            service_name=mapping.tool_key,
            service_category="Integration",
            commercial_prices=[],
            currency=catalog.currency,
            metric_name=mapping.billing_metric_key,
            price_type="HOUR" if mapping.formula_key == "hourly_capacity" else "MONTH",
            allow_decimal_quantity=mapping.quantity_behavior == "continuous",
            availability=[],
            disposition="direct_metered",
            family_key=family_key,
            status="approved",
            confidence=1,
            source_sheet="Price List",
            source_row=1,
            source_cells={},
            extraction_metadata={},
        )
        rule = CommercialRuleFamily(
            family_key=family_key,
            version="1.0.0",
            formula_key=mapping.formula_key,
            metric_pattern=mapping.billing_metric_key,
            price_types=[term.price_type],
            quantity_behavior=mapping.quantity_behavior,
            quantity_increment=Decimal(str(mapping.quantity_increment)),
            minimum_quantity=Decimal(str(mapping.minimum_quantity)),
            aggregation_window=mapping.aggregation_window,
            proration_policy=mapping.proration_policy,
            quote_rounding=mapping.quote_rounding,
            generator_version="test-1",
            status="approved",
            fixture_status="passed",
            evidence={"document_snapshot_id": document.id},
            approved_by="test",
            approved_at=datetime.now(UTC),
        )
        session.add_all([term, rule])
        await session.flush()
        term_ids_by_part[mapping.part_number] = term.id
        rule_ids_by_part[mapping.part_number] = rule.id
        session.add_all(
            [
                SkuCommercialConstraint(
                    term_id=term.id,
                    constraint_type="purchase_increment",
                    scope="commercial_quantity",
                    numeric_value=Decimal(str(mapping.quantity_increment)),
                    unit=mapping.quantity_unit,
                    behavior="round_up",
                    status="approved",
                    source_cell="A1",
                    evidence_metadata={},
                ),
                CommercialEvidenceReference(
                    entity_type="sku_commercial_term",
                    entity_id=term.id,
                    source_kind="price_list",
                    document_snapshot_id=document.id,
                    source_sheet="Price List",
                    source_row=1,
                    source_cell="A1",
                    evidence_metadata={},
                ),
            ]
        )
    release = CommercialRelease(
        version=f"test-{catalog.content_hash}",
        price_catalog_snapshot_id=catalog.id,
        document_snapshot_id=document.id,
        mapping_set_hash="mapping-hash",
        rule_family_set_hash="rule-hash",
        evidence_hash="evidence-hash",
        status="approved",
        validation_status="passed",
        open_exception_count=0,
        release_metadata={
            "part_numbers": part_numbers,
            "mapping_ids_by_part": {
                mapping.part_number: [mapping.id]
                for mapping in mappings
                if mapping.part_number
            },
            "term_ids_by_part": term_ids_by_part,
            "rule_ids_by_part": rule_ids_by_part,
        },
        approved_by="test",
        approved_at=datetime.now(UTC),
    )
    session.add(release)
    await session.flush()
    return release


def _direct_commercial_contract(
    *,
    formula_key: str,
    price_type: str,
    behavior: str,
    constraints: tuple[SkuCommercialConstraint, ...],
) -> bom_service.GovernedSkuCommercialContract:
    release = CommercialRelease(
        id="release-direct",
        version="direct-1",
        price_catalog_snapshot_id="price-direct",
        document_snapshot_id="document-direct",
        mapping_set_hash="mapping-direct",
        rule_family_set_hash="rule-direct",
        evidence_hash="evidence-direct",
        status="approved",
        validation_status="passed",
        open_exception_count=0,
        release_metadata={},
    )
    term = SkuCommercialTerm(
        id="term-direct",
        document_snapshot_id="document-direct",
        commercial_sku_id="sku-direct",
        price_catalog_snapshot_id="price-direct",
        part_number="DIRECT-SKU",
        service_name="Direct fixture",
        service_category="Integration",
        commercial_prices=[],
        currency="USD",
        metric_name="Direct metric",
        price_type=price_type,
        availability=[],
        disposition="direct_metered",
        family_key="direct-family",
        status="approved",
        source_sheet="Price List",
        source_row=1,
        source_cells={},
        extraction_metadata={},
    )
    rule = CommercialRuleFamily(
        id="rule-direct",
        family_key="direct-family",
        version="1.0.0",
        formula_key=formula_key,
        metric_pattern="Direct metric",
        price_types=[price_type],
        quantity_behavior=behavior,
        quantity_increment=Decimal("1"),
        minimum_quantity=Decimal("0"),
        aggregation_window="monthly",
        proration_policy="full_month",
        quote_rounding="half_up",
        generator_version="test",
        status="approved",
        fixture_status="passed",
        evidence={},
    )
    return bom_service.GovernedSkuCommercialContract(
        release=release,
        term=term,
        rule=rule,
        constraints=constraints,
        evidence_reference_ids=("evidence-direct",),
    )


def test_release_rejects_mapping_not_pinned_at_promotion() -> None:
    mapping = ServiceProductSkuMapping(
        id="mapping-after-release",
        service_id="API_GATEWAY",
        tool_key="OCI API Gateway",
        part_number="B92072",
        billing_metric_key="api_gateway_call_millions",
        formula_key="metered_quantity",
        quantity_behavior="continuous",
        quantity_increment=Decimal("0.000001"),
        minimum_quantity=Decimal("0"),
        quantity_unit="million calls",
        predicates={},
        is_billable=True,
        status="approved",
        version="test",
        confidence=1,
    )
    release = CommercialRelease(
        id="release-before-mapping",
        version="test",
        price_catalog_snapshot_id="price",
        document_snapshot_id="document",
        mapping_set_hash="mapping-hash",
        rule_family_set_hash="rule-hash",
        evidence_hash="evidence-hash",
        status="approved",
        validation_status="passed",
        open_exception_count=0,
        release_metadata={"mapping_ids_by_part": {"B92072": ["older-mapping"]}},
    )

    with pytest.raises(ValueError, match="does not pin"):
        bom_service._validate_release_mapping_scope(release, [mapping])


def test_release_does_not_require_a_commercial_sku_for_non_billable_mappings() -> None:
    mapping = ServiceProductSkuMapping(
        id="included-service",
        service_id="EVENTS",
        tool_key="OCI Events",
        part_number=None,
        billing_metric_key="events",
        formula_key="non_billable",
        quantity_behavior="fixed_capacity",
        quantity_increment=Decimal("1"),
        minimum_quantity=Decimal("0"),
        quantity_unit="included",
        predicates={},
        is_billable=False,
        status="approved",
        version="test",
        confidence=1,
    )
    release = CommercialRelease(
        id="release-without-included-service",
        version="test",
        price_catalog_snapshot_id="price",
        document_snapshot_id="document",
        mapping_set_hash="mapping-hash",
        rule_family_set_hash="rule-hash",
        evidence_hash="evidence-hash",
        status="approved",
        validation_status="passed",
        open_exception_count=0,
        release_metadata={"mapping_ids_by_part": {}},
    )

    bom_service._validate_release_mapping_scope(release, [mapping])


def test_commercial_constraints_preserve_capacity_storage_and_time_scopes() -> None:
    hourly_contract = _direct_commercial_contract(
        formula_key="hourly_capacity",
        price_type="HOUR",
        behavior="fixed_capacity",
        constraints=(
            SkuCommercialConstraint(
                constraint_type="metric_minimum",
                scope="provisioned_capacity",
                numeric_value=Decimal("2"),
                behavior="minimum",
                status="approved",
                source_cell="F1",
                evidence_metadata={},
            ),
            SkuCommercialConstraint(
                constraint_type="usage_time_minimum",
                scope="billing_duration_seconds",
                numeric_value=Decimal("60"),
                unit="seconds",
                behavior="minimum",
                status="approved",
                source_cell="G1",
                evidence_metadata={},
            ),
        ),
    )
    hourly_mapping = ServiceProductSkuMapping(
        service_id="ATP",
        tool_key="Autonomous Database",
        part_number="B95701",
        billing_metric_key="ecpu_hour",
        formula_key="hourly_capacity",
        quantity_behavior="fixed_capacity",
        quantity_increment=1,
        minimum_quantity=0,
        quantity_unit="ECPU",
        predicates={},
        is_billable=True,
        status="approved",
        version="test",
        confidence=1,
    )
    hourly_rule = bom_service._compiled_quantity_rule(hourly_contract, hourly_mapping)
    assert hourly_rule.minimum == Decimal("2")
    assert hourly_rule.increment == Decimal("1")

    storage_contract = _direct_commercial_contract(
        formula_key="metered_quantity",
        price_type="MONTH",
        behavior="continuous",
        constraints=(
            SkuCommercialConstraint(
                constraint_type="purchase_increment",
                scope="database_storage_quantity",
                numeric_value=Decimal("1024"),
                unit="GB",
                behavior="round_up",
                status="approved",
                source_cell="G2",
                evidence_metadata={},
            ),
            SkuCommercialConstraint(
                constraint_type="purchase_increment",
                scope="backup_storage_quantity",
                numeric_value=Decimal("1"),
                unit="GB",
                behavior="round_up",
                status="approved",
                source_cell="G3",
                evidence_metadata={},
            ),
        ),
    )
    database_mapping = ServiceProductSkuMapping(
        service_id="ATP_STORAGE",
        tool_key="Autonomous Database Storage",
        part_number="B95754",
        billing_metric_key="database_storage_gb_month",
        formula_key="metered_quantity",
        quantity_behavior="continuous",
        quantity_increment=1,
        minimum_quantity=0,
        quantity_unit="GB",
        predicates={},
        is_billable=True,
        status="approved",
        version="test",
        confidence=1,
    )
    backup_mapping = ServiceProductSkuMapping(
        service_id="ATP_BACKUP",
        tool_key="Autonomous Database Backup",
        part_number="B95754",
        billing_metric_key="backup_storage_gb_month",
        formula_key="metered_quantity",
        quantity_behavior="continuous",
        quantity_increment=1,
        minimum_quantity=0,
        quantity_unit="GB",
        predicates={},
        is_billable=True,
        status="approved",
        version="test",
        confidence=1,
    )
    assert bom_service._compiled_quantity_rule(storage_contract, database_mapping).increment == Decimal("1024")
    assert bom_service._compiled_quantity_rule(storage_contract, backup_mapping).increment == Decimal("1")


@pytest.mark.asyncio
async def test_bom_scope_excludes_tbq_n_but_catalog_keeps_it(test_engine: AsyncEngine) -> None:
    """TBQ N is technical catalog evidence and never becomes economic demand."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(id="tbq-scope", name="TBQ Scope", owner_id="architect", status="active")
        session.add_all(
            [
                project,
                CatalogIntegration(
                    id="tbq-y",
                    project_id=project.id,
                    seq_number=1,
                    interface_name="Quoted route",
                    source_system="ERP",
                    destination_system="CRM",
                    tbq="Y",
                ),
                CatalogIntegration(
                    id="tbq-n",
                    project_id=project.id,
                    seq_number=2,
                    interface_name="Technical-only route",
                    source_system="ERP",
                    destination_system="Lake",
                    tbq="N",
                ),
            ]
        )
        await session.flush()

        catalog_rows = list(
            (
                await session.scalars(
                    select(CatalogIntegration).where(CatalogIntegration.project_id == project.id)
                )
            ).all()
        )
        economic_rows = await bom_service._project_integrations(project.id, session)

        assert {row.id for row in catalog_rows} == {"tbq-y", "tbq-n"}
        assert [row.id for row in economic_rows] == ["tbq-y"]


def test_rebuilds_historical_monthly_series_from_immutable_line_periods() -> None:
    """Historical snapshots remain chartable even when their JSON summary lacks a series."""

    oic_line = BomLineItem(id="oic-line", environment="Production", service_id="OIC3")
    queue_line = BomLineItem(id="queue-line", environment="QA", service_id="QUEUE")
    periods = {
        "oic-line": [
            BomLinePeriod(period_index=1, period_start=date(2026, 1, 1), amount=10),
            BomLinePeriod(period_index=2, period_start=date(2026, 2, 1), amount=20),
        ],
        "queue-line": [
            BomLinePeriod(period_index=1, period_start=date(2026, 1, 1), amount=2.5),
            BomLinePeriod(period_index=2, period_start=date(2026, 2, 1), amount=5),
        ],
    }

    assert bom_service._monthly_series_from_line_periods([oic_line, queue_line], periods) == [
        {
            "period_index": 1,
            "period_start": date(2026, 1, 1),
            "total": 12.5,
            "cumulative_total": 12.5,
            "by_environment": {"Production": 10.0, "QA": 2.5},
            "by_service": {"OIC3": 10.0, "QUEUE": 2.5},
        },
        {
            "period_index": 2,
            "period_start": date(2026, 2, 1),
            "total": 25.0,
            "cumulative_total": 37.5,
            "by_environment": {"Production": 20.0, "QA": 5.0},
            "by_service": {"OIC3": 20.0, "QUEUE": 5.0},
        },
    ]


def test_public_and_contract_price_normalization() -> None:
    public = pricing_service.normalize_public_price_payload(
        {
            "items": [
                {
                    "partNumber": "B89639",
                    "displayName": "Oracle Integration",
                    "metricName": "5K messages per hour",
                    "serviceCategory": "Integration",
                    "currencyCodeLocalizations": [
                        {"currencyCode": "USD", "prices": [{"model": "PAY_AS_YOU_GO", "value": 0.6452}]}
                    ],
                }
            ]
        },
        "USD",
    )
    assert public[0]["part_number"] == "B89639"
    assert public[0]["value"] == 0.6452

    contract = pricing_service.normalize_rate_card_csv(
        b"Part Number,Product Name,Metric,Net Unit Price,Currency\nB89639,Oracle Integration,5K messages per hour,0.50,USD\n",
        "USD",
    )
    assert contract[0]["model"] == "CONTRACT_RATE"
    assert contract[0]["value"] == 0.5


def test_metric_options_separate_measured_demand_from_quote_policy() -> None:
    """Quote-ready options must not leak the workbook's 744-hour convention."""

    integration = CatalogIntegration(
        project_id="project",
        seq_number=1,
        interface_name="Gateway flow",
        source_system="ERP",
        destination_system="CRM",
        core_tools="OCI API Gateway",
        executions_per_day=9392,
    )
    mappings = [
        ServiceProductSkuMapping(
            id="api-mapping",
            service_id="API_GATEWAY",
            tool_key="OCI API Gateway",
            part_number="B92072",
            billing_metric_key="api_gateway_call_millions",
            formula_key="monthly_quantity",
            quantity_behavior="continuous",
            quantity_increment=0.000001,
            minimum_quantity=0,
            quantity_unit="million API calls",
            usage_basis="metered_usage",
            quote_rounding="metered_prorated",
            aggregation_window="calendar_month",
            proration_policy="prorated",
            free_tier_scope="none",
            planning_envelope_increment=1,
            metering_policy={"billing_unit": "1000000_api_calls"},
            requires_explicit_quantity=False,
            entry_guidance="Enter monthly API calls.",
            quantity_presets=[],
            predicates={},
            is_billable=True,
            status="approved",
            version="test",
            confidence=1,
        ),
        ServiceProductSkuMapping(
            id="workspace-mapping",
            service_id="DATA_INTEGRATION",
            tool_key="OCI Data Integration",
            part_number="B92598",
            billing_metric_key="di_workspace_hours",
            formula_key="monthly_quantity",
            quantity_behavior="hourly",
            quantity_increment=1,
            minimum_quantity=0,
            quantity_unit="workspace-hours",
            usage_basis="provisioned_runtime",
            quote_rounding="whole_hour_plan",
            aggregation_window="provisioned_runtime",
            proration_policy="whole_hour_plan",
            free_tier_scope="none",
            planning_envelope_increment=None,
            metering_policy={"runtime_state": "running"},
            requires_explicit_quantity=True,
            entry_guidance="Enter actual running hours.",
            quantity_presets=[{"label": "Always on", "quantity": 744, "description": "Full month."}],
            predicates={},
            is_billable=True,
            status="approved",
            version="test",
            confidence=1,
        ),
    ]

    options = bom_service._metric_options(
        ["API_GATEWAY", "DATA_INTEGRATION"],
        mappings,
        {},
        [integration],
        {"API_GATEWAY": {}, "DATA_INTEGRATION": {"workspace_count": 1}},
    )
    api_gateway = next(option for option in options if option.service_id == "API_GATEWAY")
    workspace = next(option for option in options if option.metric_key == "di_workspace_hours")

    assert api_gateway.source_baseline_quantity == pytest.approx(0.291152)
    assert api_gateway.baseline_quantity == pytest.approx(0.291152)
    assert api_gateway.planning_envelope_quantity == 1
    assert api_gateway.quote_rounding == "metered_prorated"
    assert workspace.source_baseline_quantity == 0
    assert workspace.baseline_quantity == 0
    assert workspace.requires_explicit_quantity is True


def test_product_detection_does_not_depend_on_sku_mapping() -> None:
    """Architecture products without a direct SKU must remain visible to BOM governance."""

    integration = CatalogIntegration(
        project_id="project",
        seq_number=1,
        interface_name="Catalog harvest",
        source_system="Lake",
        destination_system="Governance",
        core_tools="OCI Data Catalog",
    )
    policy = ServiceCommercialPolicy(
        id="policy",
        service_profile_id="profile",
        service_id="DATA_CATALOG",
        classification="included_non_billable",
        readiness="quote_ready",
        publication_policy="included_zero",
        tool_aliases=["OCI Data Catalog"],
        dependent_service_ids=[],
        required_inputs=[],
        guidance="Included service.",
        source_urls=[],
        status="approved",
        version="test",
        confidence=1,
    )

    services, tools = bom_service._detected_services([integration], [], [policy])

    assert services == ["DATA_CATALOG"]
    assert tools == {"OCI Data Catalog"}


def test_non_billable_mapping_cannot_replace_governed_commercial_policy() -> None:
    """Every detected product must be normalized and commercially classified."""

    mapping = ServiceProductSkuMapping(
        id="events-mapping",
        service_id="EVENTS",
        tool_key="OCI Events",
        part_number=None,
        billing_metric_key="events",
        formula_key="non_billable",
        predicates={},
        is_billable=False,
        status="approved",
        version="test",
        confidence=1,
    )

    coverage = bom_service._commercial_coverage(["EVENTS"], [], [mapping])

    assert coverage[0].readiness == "blocked"
    assert coverage[0].publication_policy == "policy_required"


def test_optional_commercial_metrics_are_available_but_not_default_selected() -> None:
    mapping = ServiceProductSkuMapping(
        id="optional",
        service_id="OBSERVABILITY",
        tool_key="OCI Observability",
        part_number="B90925",
        billing_metric_key="monitoring_ingestion_million_datapoints",
        formula_key="monthly_quantity",
        quantity_behavior="continuous",
        quantity_increment=0.000001,
        minimum_quantity=0,
        quantity_unit="million datapoints",
        usage_basis="metered_usage",
        quote_rounding="metered",
        aggregation_window="calendar_month",
        proration_policy="prorated",
        free_tier_scope="tenant_month",
        metering_policy={},
        selection_policy="optional",
        requires_explicit_quantity=True,
        entry_guidance="Select only when used.",
        quantity_presets=[],
        predicates={},
        is_billable=True,
        status="approved",
        version="test",
        confidence=1,
    )

    options = bom_service._metric_options(
        ["OBSERVABILITY"], [mapping], {}, [], {"OBSERVABILITY": {}}
    )

    assert len(options) == 1
    assert options[0].default_selected is False
    assert options[0].variants[0].selection_policy == "optional"


def test_tenant_month_free_tier_is_shared_across_environment_lines() -> None:
    """A tenancy allowance cannot restart for every environment or BOM line."""

    mapping = ServiceProductSkuMapping(
        id="functions-mapping",
        service_id="FUNCTIONS",
        tool_key="OCI Functions",
        part_number="B90617",
        billing_metric_key="functions_execution_10k_gb_s",
        formula_key="tiered_monthly",
        quantity_behavior="continuous",
        quantity_increment=0.000001,
        minimum_quantity=0,
        quantity_unit="10K GB-s",
        usage_basis="metered_usage",
        quote_rounding="metered",
        aggregation_window="tenant_month",
        proration_policy="prorated",
        free_tier_scope="tenant_month",
        planning_envelope_increment=None,
        metering_policy={"free_gb_seconds_per_tenant_month": 400000},
        requires_explicit_quantity=False,
        entry_guidance="Measured execution.",
        quantity_presets=[],
        predicates={},
        is_billable=True,
        status="approved",
        version="test",
        confidence=1,
    )
    remaining: dict[tuple[str, int], Decimal] = {}
    first = bom_service._allocate_tenant_month_free_tier(
        mapping=mapping,
        quantities=(Decimal("8"), Decimal("12")),
        free_tier=10,
        enabled=True,
        remaining_by_sku_period=remaining,
    )
    second = bom_service._allocate_tenant_month_free_tier(
        mapping=mapping,
        quantities=(Decimal("7"), Decimal("3")),
        free_tier=10,
        enabled=True,
        remaining_by_sku_period=remaining,
    )

    assert first == (Decimal("8"), Decimal("10"))
    assert second == (Decimal("2"), Decimal("0"))
    assert remaining[("B90617", 1)] == 0
    assert remaining[("B90617", 2)] == 0


def test_priced_lines_share_tenant_month_free_tier_and_full_capacity_comparison() -> None:
    """Persisted line totals and rollout comparison must consume the same allowance pool."""

    mapping = ServiceProductSkuMapping(
        id="functions-mapping",
        service_id="FUNCTIONS",
        tool_key="OCI Functions",
        part_number="B90617",
        billing_metric_key="functions_execution_10k_gb_s",
        formula_key="tiered_monthly",
        quantity_behavior="continuous",
        quantity_increment=0.000001,
        minimum_quantity=0,
        quantity_unit="10K GB-s",
        usage_basis="metered_usage",
        quote_rounding="metered",
        aggregation_window="tenant_month",
        proration_policy="prorated",
        free_tier_scope="tenant_month",
        planning_envelope_increment=None,
        metering_policy={"free_10k_gb_seconds_per_tenant_month": 10},
        requires_explicit_quantity=False,
        entry_guidance="Measured execution.",
        quantity_presets=[],
        predicates={},
        is_billable=True,
        status="approved",
        version="test",
        confidence=1,
    )
    price_items = [
        PriceItem(
            id="free-tier",
            snapshot_id="snapshot",
            part_number="B90617",
            display_name="Functions execution free tier",
            metric_name="10K GB-s",
            service_category="Functions",
            price_type="tier",
            currency="USD",
            model="PAY_AS_YOU_GO",
            value=0,
            range_min=0,
            range_max=10,
            range_unit="10K GB-s",
        ),
        PriceItem(
            id="paid-tier",
            snapshot_id="snapshot",
            part_number="B90617",
            display_name="Functions execution",
            metric_name="10K GB-s",
            service_category="Functions",
            price_type="tier",
            currency="USD",
            model="PAY_AS_YOU_GO",
            value=2,
            range_min=10,
            range_max=None,
            range_unit="10K GB-s",
        ),
    ]
    scenario = DeploymentScenario(
        id="scenario",
        project_id="project",
        name="Shared allowance",
        currency="USD",
        region="global",
        price_mode="public_list",
        technical_snapshot_id="technical-snapshot",
        contract_months=2,
        start_date=date(2026, 1, 1),
        scenario_assumptions={"free_tier_enabled": True},
        service_config={},
        created_by="architect",
    )
    remaining: dict[tuple[str, int], Decimal] = {}
    first_line, first_periods = bom_service._price_mapping_line(
        mapping,
        price_items,
        12,
        "10K GB-s",
        {"name": "Production", "active_hours_month": 744},
        scenario,
        [],
        (Decimal("1"), Decimal("1")),
        explicit_quantities=(Decimal("8"), Decimal("12")),
        free_tier_remaining=remaining,
    )
    second_line, second_periods = bom_service._price_mapping_line(
        mapping,
        price_items,
        7,
        "10K GB-s",
        {"name": "QA", "active_hours_month": 160},
        scenario,
        [],
        (Decimal("1"), Decimal("1")),
        explicit_quantities=(Decimal("7"), Decimal("3")),
        free_tier_remaining=remaining,
    )

    assert [period["amount"] for period in first_periods] == [0.0, 4.0]
    assert [period["amount"] for period in second_periods] == [10.0, 6.0]
    assert first_line["_full_capacity_monthly"] == 4.0
    assert second_line["_full_capacity_monthly"] == 14.0
    assert cast(dict[str, object], second_line["inputs"])["free_quantity"] == "0"


@pytest.mark.asyncio
async def test_contract_rate_card_import_is_admin_only_and_idempotent(api_client: AsyncClient) -> None:
    files = {
        "file": (
            "customer-rate-card.csv",
            b"Part Number,Product Name,Metric,Net Unit Price,Currency\nB89639,Oracle Integration,5K messages per hour,0.50,USD\n",
            "text/csv",
        )
    }
    denied = await api_client.post(
        "/api/v1/pricing/rate-card-imports",
        data={"name": "Customer agreement", "currency": "USD"},
        files=files,
        headers={"X-Actor-Role": "Viewer"},
    )
    assert denied.status_code == 403

    first = await api_client.post(
        "/api/v1/pricing/rate-card-imports",
        data={"name": "Customer agreement", "currency": "USD"},
        files=files,
        headers={"X-Actor-Role": "Admin", "X-Actor-Id": "pricing-admin"},
    )
    assert first.status_code == 200
    assert first.json()["approval_status"] == "approved"
    second = await api_client.post(
        "/api/v1/pricing/rate-card-imports",
        data={"name": "Customer agreement", "currency": "USD"},
        files=files,
        headers={"X-Actor-Role": "Admin", "X-Actor-Id": "pricing-admin"},
    )
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_scenario_rejects_unbalanced_environment_shares(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(name="Pricing test", status=ProjectStatus.ACTIVE, owner_id="owner")
        session.add(project)
        await session.flush()
        snapshot = VolumetrySnapshot(
            project_id=project.id,
            assumption_set_version="1.0.0",
            triggered_by="test",
            row_results={},
            consolidated={},
            snapshot_metadata={},
        )
        session.add(snapshot)
        await session.commit()
        project_id = project.id
        snapshot_id = snapshot.id

    response = await api_client.post(
        f"/api/v1/projects/{project_id}/deployment-scenarios",
        headers={"X-Actor-Role": "Architect", "X-Actor-Id": "architect"},
        json={
            "name": "Invalid split",
            "technical_snapshot_id": snapshot_id,
            "consumption_model": "legacy_share",
            "environments": [
                {"name": "Production", "demand_share": 0.8},
                {"name": "Non-production", "demand_share": 0.4},
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "SCENARIO_DEMAND_SHARE_INVALID"

    explicit_empty = await api_client.post(
        f"/api/v1/projects/{project_id}/deployment-scenarios",
        headers={"X-Actor-Role": "Architect", "X-Actor-Id": "architect"},
        json={
            "name": "Missing quantities",
            "technical_snapshot_id": snapshot_id,
            "consumption_model": "explicit_units",
            "environments": [{"name": "Production", "phases": []}],
        },
    )
    assert explicit_empty.status_code == 422
    assert explicit_empty.json()["detail"]["error_code"] == "SCENARIO_EXPLICIT_QUANTITY_REQUIRED"


@pytest.mark.asyncio
async def test_scenario_persists_exact_monthly_product_quantities(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(name="Monthly quantity test", status=ProjectStatus.ACTIVE, owner_id="owner")
        session.add(project)
        await session.flush()
        snapshot = VolumetrySnapshot(
            project_id=project.id,
            assumption_set_version="1.0.0",
            triggered_by="test",
            row_results={},
            consolidated={},
            snapshot_metadata={},
        )
        session.add(snapshot)
        await session.commit()

    response = await api_client.post(
        f"/api/v1/projects/{project.id}/deployment-scenarios",
        headers={"X-Actor-Role": "Architect", "X-Actor-Id": "architect"},
        json={
            "name": "DEV message ramp",
            "technical_snapshot_id": snapshot.id,
            "commitment_model": "annual_commitment",
            "contract_months": 3,
            "consumption_model": "explicit_units",
            "environments": [{
                "name": "DEV",
                "phases": [{
                    "service_id": "OIC3",
                    "metric_key": "oic_peak_packs_hour",
                    "start_month": 1,
                    "end_month": 3,
                    "interpolation": "monthly",
                    "quantity_unit": "message packs",
                    "monthly_quantities": [
                        {"period_index": 1, "quantity": 1},
                        {"period_index": 2, "quantity": 2},
                        {"period_index": 3, "quantity": 4},
                    ],
                }],
            }],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["commitment_model"] == "annual_commitment"
    assert payload["consumption_model"] == "explicit_units"
    assert payload["environments"][0]["phases"][0]["monthly_quantities"] == [
        {"period_index": 1, "quantity": 1.0},
        {"period_index": 2, "quantity": 2.0},
        {"period_index": 3, "quantity": 4.0},
    ]


def test_price_tier_selection_isolated_by_commitment_model() -> None:
    """One SKU never combines PAYG and Annual prices in the same quote."""

    items = [
        PriceItem(
            id="payg",
            snapshot_id="snapshot",
            part_number="SAME-SKU",
            display_name="Same product",
            metric_name="Unit per month",
            service_category="Test",
            price_type="MONTH",
            currency="USD",
            model="PAY_AS_YOU_GO",
            value=3,
        ),
        PriceItem(
            id="annual",
            snapshot_id="snapshot",
            part_number="SAME-SKU",
            display_name="Same product",
            metric_name="Unit per month",
            service_category="Test",
            price_type="MONTH",
            currency="USD",
            model="ANNUAL_COMMITMENT",
            value=2,
        ),
    ]

    payg_tiers, _, payg_paid, payg_selected = bom_service._selected_price_tiers(
        items, "pay_as_you_go"
    )
    annual_tiers, _, annual_paid, annual_selected = bom_service._selected_price_tiers(
        items, "annual_commitment"
    )

    assert [tier.unit_price for tier in payg_tiers] == [Decimal("3")]
    assert [item.id for item in payg_paid] == ["payg"]
    assert [item.id for item in payg_selected] == ["payg"]
    assert [tier.unit_price for tier in annual_tiers] == [Decimal("2")]
    assert [item.id for item in annual_paid] == ["annual"]
    assert [item.id for item in annual_selected] == ["annual"]


@pytest.mark.asyncio
async def test_bom_uses_requested_price_source_and_produces_traceable_line(test_engine: AsyncEngine) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(name="BOM test", status=ProjectStatus.ACTIVE, owner_id="owner")
        session.add(project)
        await session.flush()
        technical = VolumetrySnapshot(
            project_id=project.id,
            assumption_set_version="1.0.0",
            triggered_by="test",
            row_results={},
            consolidated={"oic": {"peak_packs_hour": 2}},
            snapshot_metadata={},
        )
        integration = CatalogIntegration(
            project_id=project.id,
            seq_number=1,
            interface_name="Order flow",
            source_system="ERP",
            destination_system="CRM",
            core_tools="OIC Gen3",
        )
        source = PriceSource(
            name="Public OCI",
            source_type="public_list",
            base_url="https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/",
            currency="USD",
            status="active",
            source_config={},
            created_by="test",
        )
        session.add_all([technical, integration, source])
        await session.flush()
        sync_job = PriceSyncJob(
            source_id=source.id,
            requested_by="test",
            currency="USD",
            status="completed",
        )
        session.add(sync_job)
        await session.flush()
        catalog = PriceCatalogSnapshot(
            source_id=source.id,
            sync_job_id=sync_job.id,
            currency="USD",
            retrieved_at=technical.created_at,
            content_hash="test-public-catalog",
            item_count=1,
            approval_status="approved",
            approved_by="test",
            approved_at=technical.created_at,
            snapshot_metadata={},
        )
        mapping = ServiceProductSkuMapping(
            service_id="OIC3",
            tool_key="OIC Gen3",
            part_number="B89639",
            billing_metric_key="oic_peak_packs_hour",
            formula_key="hourly_capacity",
            quantity_behavior="fixed_capacity",
            quantity_increment=1,
            minimum_quantity=1,
            quantity_unit="packs/hour",
            predicates={"edition": "standard", "byol": False},
            is_billable=True,
            status="approved",
            version="test-1",
            confidence=1.0,
        )
        scenario = DeploymentScenario(
            project_id=project.id,
            name="Public baseline",
            status="approved",
            currency="USD",
            region="global",
            price_mode="public_list",
            technical_snapshot_id=technical.id,
            contract_months=12,
            start_date=date(2026, 1, 1),
            proration_policy="full_month",
            consumption_model="explicit_units",
            service_config={"OIC3": {"edition": "standard", "byol": False}},
            scenario_assumptions={"free_tier_enabled": False},
            created_by="test",
        )
        session.add_all([catalog, mapping, scenario])
        await session.flush()
        session.add(
            GovernanceChangeSet(
                sync_job_id=sync_job.id,
                price_source_id=source.id,
                price_snapshot_id=catalog.id,
                trigger_type="test",
                currency="USD",
                status="promoted",
                drift_classification="baseline",
                materiality_score=0,
                source_manifest={},
                drift_summary={},
                impact_summary={},
                validation_status="passed",
                regression_summary={"families": 1, "passed": 1, "failed": 0},
                approval_status="approved",
                promoted_at=datetime.now(UTC),
            )
        )
        environment = DeploymentEnvironmentPlan(
            scenario_id=scenario.id,
            name="Production",
            sequence=1,
            active_hours_month=744,
            demand_share=1.0,
            ha_multiplier=1.0,
            dr_role="primary",
        )
        session.add(environment)
        await session.flush()
        session.add(
            DeploymentRampPhase(
                environment_plan_id=environment.id,
                service_id="OIC3",
                metric_key="oic_peak_packs_hour",
                start_month=1,
                end_month=12,
                start_multiplier=1,
                end_multiplier=1,
                interpolation="step",
                start_quantity=2,
                end_quantity=2,
                quantity_unit="packs/hour",
                rationale="Two governed hourly capacity packs.",
            )
        )
        session.add(
            PriceItem(
                snapshot_id=catalog.id,
                part_number="B89639",
                display_name="Oracle Integration",
                metric_name="5K messages per hour",
                service_category="Integration",
                price_type="HOUR",
                currency="USD",
                model="PAY_AS_YOU_GO",
                value=0.6452,
            )
        )
        commercial_release = await _seed_approved_commercial_release(
            session, catalog, [mapping]
        )
        await session.commit()
        async with session.begin():
            dry_run = await bom_service.calculate_bom(
                project_id=project.id,
                scenario=scenario,
                technical=technical.consolidated,
                db=session,
            )
        assert dry_run.monthly_total == 960.06
        assert dry_run.contract_total == 11520.72
        assert dry_run.coverage_pct == 100.0
        assert dry_run.commercial_release.id == commercial_release.id
        assert dry_run.line_payloads[0]["commercial_term_id"] is not None
        assert dry_run.line_payloads[0]["commercial_rule_family_id"] is not None
        assert dry_run.line_payloads[0]["evidence_reference_ids"]
        async with session.begin():
            job_response = await bom_service.create_bom_job(project.id, scenario.id, "architect", session)
        async with session.begin():
            job = await bom_service.run_bom_job(job_response.id, session)
        assert job.status == "completed"
        assert job.bom_snapshot_id is not None
        snapshot = await bom_service.get_bom_snapshot(project.id, job.bom_snapshot_id, session)
        assert snapshot.coverage_pct == 100.0
        assert snapshot.monthly_total == 960.06
        assert snapshot.contract_total == 11520.72
        assert snapshot.commercial_release_id == commercial_release.id
        assert len(snapshot.monthly_series) == 12
        assert len(snapshot.line_items[0].periods) == 12
        assert snapshot.line_items[0].provenance["mapping_id"] == mapping.id
        assert snapshot.line_items[0].provenance["quantity_source"] == "explicit_units"
        assert snapshot.line_items[0].periods[0].quantity == 2
        assert snapshot.line_items[0].formula.endswith("* hours")
        assert snapshot.recommendation_workspace.context == "bom"
        assert snapshot.recommendation_workspace.candidates
        assert snapshot.recommendation_workspace.candidates[0].implementation_steps
        persisted_snapshot = await session.get(BomSnapshot, job.bom_snapshot_id)
        assert persisted_snapshot is not None
        assert persisted_snapshot.commercial_release_id == commercial_release.id
        persisted_line = await session.scalar(
            select(BomLineItem).where(BomLineItem.bom_snapshot_id == persisted_snapshot.id)
        )
        assert persisted_line is not None
        assert persisted_line.commercial_term_id is not None
        assert persisted_line.commercial_rule_family_id is not None
        assert persisted_line.evidence_reference_ids
        persisted_period = await session.scalar(
            select(BomLinePeriod).where(BomLinePeriod.bom_line_item_id == persisted_line.id)
        )
        assert persisted_period is not None
        assert persisted_period.commercial_term_id == persisted_line.commercial_term_id
        assert persisted_period.commercial_rule_family_id == persisted_line.commercial_rule_family_id
        assert persisted_period.evidence_reference_ids == persisted_line.evidence_reference_ids

        reviewed = await bom_service.review_bom_snapshot(
            project.id,
            persisted_snapshot.id,
            BomReviewRequest(publication_status="approved"),
            "architect",
            session,
        )
        assert reviewed.publication_status == "approved"

        session.add(
            CommercialException(
                document_snapshot_id=commercial_release.document_snapshot_id,
                part_number="B89639",
                exception_code="LATE_SOURCE_CONFLICT",
                severity="high",
                status="open",
                details={},
            )
        )
        await session.flush()
        with pytest.raises(HTTPException) as exc_info:
            await bom_service.review_bom_snapshot(
                project.id,
                persisted_snapshot.id,
                BomReviewRequest(publication_status="published"),
                "architect",
                session,
            )
        assert exc_info.value.status_code == 409
        detail = cast(dict[str, object], exc_info.value.detail)
        assert detail["error_code"] == "BOM_COMMERCIAL_EVIDENCE_INCOMPLETE"


@pytest.mark.asyncio
async def test_bom_resolves_commercial_variant_per_environment(test_engine: AsyncEngine) -> None:
    """The same product metric can use a different approved SKU in each environment."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(name="Environment SKU variants", status=ProjectStatus.ACTIVE, owner_id="owner")
        session.add(project)
        await session.flush()
        technical = VolumetrySnapshot(
            project_id=project.id,
            assumption_set_version="1.0.0",
            triggered_by="test",
            row_results={},
            consolidated={"oic": {"peak_packs_hour": 1}},
            snapshot_metadata={},
        )
        integration = CatalogIntegration(
            project_id=project.id,
            seq_number=1,
            interface_id="ENV-SKU-001",
            interface_name="Environment SKU test",
            source_system="Source",
            destination_system="Destination",
            frequency="Daily",
            core_tools="OIC Gen3",
            qa_status="OK",
        )
        source = PriceSource(
            name="Environment SKU catalog",
            source_type="public_list",
            base_url="test://environment-skus",
            currency="USD",
            status="active",
            source_config={},
            created_by="test",
        )
        session.add_all([technical, integration, source])
        await session.flush()
        sync_job = PriceSyncJob(
            source_id=source.id,
            requested_by="test",
            currency="USD",
            status="completed",
        )
        session.add(sync_job)
        await session.flush()
        catalog = PriceCatalogSnapshot(
            source_id=source.id,
            sync_job_id=sync_job.id,
            currency="USD",
            retrieved_at=technical.created_at,
            content_hash="environment-sku-catalog",
            item_count=2,
            approval_status="approved",
            approved_by="test",
            approved_at=technical.created_at,
            snapshot_metadata={},
        )
        mappings = [
            ServiceProductSkuMapping(
                service_id="OIC3",
                tool_key="OIC Gen3",
                part_number=part_number,
                billing_metric_key="oic_peak_packs_hour",
                formula_key="hourly_capacity",
                quantity_behavior="fixed_capacity",
                quantity_increment=1,
                minimum_quantity=1,
                quantity_unit="packs/hour",
                predicates={"edition": edition, "byol": False},
                is_billable=True,
                status="approved",
                version="test-1",
                confidence=1,
            )
            for edition, part_number in [("standard", "OIC-STD"), ("enterprise", "OIC-ENT")]
        ]
        scenario = DeploymentScenario(
            project_id=project.id,
            name="Mixed OIC editions",
            status="approved",
            currency="USD",
            region="global",
            price_mode="public_list",
            technical_snapshot_id=technical.id,
            contract_months=1,
            start_date=date(2026, 1, 1),
            proration_policy="full_month",
            consumption_model="explicit_units",
            service_config={"OIC3": {"edition": "standard", "byol": False}},
            scenario_assumptions={"free_tier_enabled": False},
            created_by="test",
        )
        session.add_all([catalog, *mappings, scenario])
        await session.flush()
        session.add(
            GovernanceChangeSet(
                sync_job_id=sync_job.id,
                price_source_id=source.id,
                price_snapshot_id=catalog.id,
                trigger_type="test",
                currency="USD",
                status="promoted",
                drift_classification="baseline",
                materiality_score=0,
                source_manifest={},
                drift_summary={},
                impact_summary={},
                validation_status="passed",
                regression_summary={"families": 1, "passed": 1, "failed": 0},
                approval_status="approved",
                promoted_at=datetime.now(UTC),
            )
        )
        for sequence, (name, mapping) in enumerate(
            [("Production", mappings[1]), ("QA", mappings[0])], start=1
        ):
            environment = DeploymentEnvironmentPlan(
                scenario_id=scenario.id,
                name=name,
                sequence=sequence,
                active_hours_month=744,
                demand_share=1,
                ha_multiplier=1,
                dr_role="primary" if name == "Production" else "none",
            )
            session.add(environment)
            await session.flush()
            session.add(DeploymentRampPhase(
                environment_plan_id=environment.id,
                service_id="OIC3",
                metric_key="oic_peak_packs_hour",
                sku_mapping_id=mapping.id,
                start_month=1,
                end_month=1,
                start_multiplier=1,
                end_multiplier=1,
                interpolation="step",
                start_quantity=1,
                end_quantity=1,
                quantity_unit="packs/hour",
            ))
        session.add_all([
            PriceItem(
                snapshot_id=catalog.id,
                part_number=part_number,
                display_name=f"Oracle Integration {edition.title()}",
                metric_name=f"{edition.title()} message pack",
                service_category="Integration",
                price_type="HOUR",
                currency="USD",
                model="PAY_AS_YOU_GO",
                value=price,
            )
            for edition, part_number, price in [
                ("standard", "OIC-STD", 1),
                ("enterprise", "OIC-ENT", 2),
            ]
        ])
        await _seed_approved_commercial_release(session, catalog, mappings)
        await session.commit()

        async with session.begin():
            calculation = await bom_service.calculate_bom(
                project_id=project.id,
                scenario=scenario,
                technical=technical.consolidated,
                db=session,
            )

        assert calculation.monthly_total == 2232
        assert {(line["environment"], line["part_number"]) for line in calculation.line_payloads} == {
            ("Production", "OIC-ENT"),
            ("QA", "OIC-STD"),
        }
        variant_labels: set[str] = set()
        for line in calculation.line_payloads:
            provenance = line["provenance"]
            assert isinstance(provenance, dict)
            variant_labels.add(str(provenance["commercial_variant"]))
        assert variant_labels == {"Enterprise · PAYG · OIC-ENT", "Standard · PAYG · OIC-STD"}


@pytest.mark.asyncio
async def test_contract_rate_overrides_price_but_inherits_public_terms(
    test_engine: AsyncEngine,
) -> None:
    """A private rate never replaces the approved public quantity semantics."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        public_source = PriceSource(
            name="Public commercial contract",
            source_type="public_list",
            currency="USD",
            status="active",
            source_config={},
            created_by="test",
        )
        contract_source = PriceSource(
            name="Customer rate card",
            source_type="manual_rate_card",
            currency="USD",
            status="active",
            source_config={},
            created_by="test",
        )
        session.add_all([public_source, contract_source])
        await session.flush()
        public_catalog = PriceCatalogSnapshot(
            source_id=public_source.id,
            currency="USD",
            retrieved_at=datetime.now(UTC),
            content_hash="public-commercial-terms",
            item_count=1,
            approval_status="approved",
            snapshot_metadata={},
        )
        contract_catalog = PriceCatalogSnapshot(
            source_id=contract_source.id,
            currency="USD",
            retrieved_at=datetime.now(UTC),
            content_hash="customer-price-override",
            item_count=1,
            approval_status="approved",
            snapshot_metadata={},
        )
        mapping = ServiceProductSkuMapping(
            service_id="OIC3",
            tool_key="OIC Gen3",
            part_number="RATE-OVERRIDE",
            billing_metric_key="oic_peak_packs_hour",
            formula_key="hourly_capacity",
            quantity_behavior="fixed_capacity",
            quantity_increment=1,
            minimum_quantity=1,
            quantity_unit="packs/hour",
            predicates={},
            is_billable=True,
            status="approved",
            version="test-1",
            confidence=1,
        )
        session.add_all([public_catalog, contract_catalog, mapping])
        await session.flush()
        release = await _seed_approved_commercial_release(
            session, public_catalog, [mapping]
        )
        contract_price = PriceItem(
            snapshot_id=contract_catalog.id,
            part_number="RATE-OVERRIDE",
            display_name="Oracle Integration negotiated rate",
            metric_name="Message pack per hour",
            service_category="Integration",
            price_type="HOUR",
            currency="USD",
            model="CONTRACT_RATE",
            value=0.5,
        )
        session.add(contract_price)
        await session.flush()

        resolved_release = await bom_service._resolve_commercial_release(
            price_snapshot=contract_catalog,
            price_source=contract_source,
            currency="USD",
            db=session,
        )
        contracts = await bom_service._governed_sku_contracts(
            release=resolved_release,
            part_numbers={"RATE-OVERRIDE"},
            currency="USD",
            db=session,
        )
        scenario = DeploymentScenario(
            project_id="project",
            name="Contract override",
            status="approved",
            currency="USD",
            region="global",
            price_mode="manual_rate_card",
            commitment_model="annual_commitment",
            technical_snapshot_id="technical",
            contract_months=1,
            start_date=date(2026, 1, 1),
            proration_policy="full_month",
            consumption_model="explicit_units",
            service_config={},
            scenario_assumptions={},
            created_by="test",
        )
        line, periods = bom_service._price_mapping_line(
            mapping,
            [contract_price],
            1.2,
            "packs/hour",
            {"name": "Production", "active_hours_month": 744},
            scenario,
            [],
            (Decimal("1"),),
            (Decimal("1.2"),),
            {},
            contracts["RATE-OVERRIDE"],
        )

        assert resolved_release.id == release.id
        assert line["unit_price"] == 0.5
        assert line["quantity"] == 2
        assert line["monthly_amount"] == 744
        assert line["commercial_term_id"] == contracts["RATE-OVERRIDE"].term.id
        provenance = cast(dict[str, object], line["provenance"])
        assert provenance["contract_price_override"] is True
        assert provenance["public_commercial_price_snapshot_id"] == public_catalog.id
        assert provenance["applied_price_snapshot_id"] == contract_catalog.id
        assert periods[0]["commercial_rule_family_id"] == contracts["RATE-OVERRIDE"].rule.id


@pytest.mark.asyncio
async def test_governed_contract_blocks_open_exception_and_unapproved_rule(
    test_engine: AsyncEngine,
) -> None:
    """Calculation cannot bypass unresolved evidence or unapproved rule logic."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        source = PriceSource(
            name="Blocking catalog",
            source_type="public_list",
            currency="USD",
            status="active",
            source_config={},
            created_by="test",
        )
        session.add(source)
        await session.flush()
        catalog = PriceCatalogSnapshot(
            source_id=source.id,
            currency="USD",
            retrieved_at=datetime.now(UTC),
            content_hash="blocking-commercial-terms",
            item_count=1,
            approval_status="approved",
            snapshot_metadata={},
        )
        mapping = ServiceProductSkuMapping(
            service_id="API_GATEWAY",
            tool_key="OCI API Gateway",
            part_number="BLOCKED-SKU",
            billing_metric_key="api_gateway_call_millions",
            formula_key="metered_quantity",
            quantity_behavior="packaged",
            quantity_increment=1,
            minimum_quantity=1,
            quantity_unit="million calls",
            predicates={},
            is_billable=True,
            status="approved",
            version="test-1",
            confidence=1,
        )
        session.add_all([catalog, mapping])
        await session.flush()
        release = await _seed_approved_commercial_release(session, catalog, [mapping])
        exception = CommercialException(
            document_snapshot_id=release.document_snapshot_id,
            part_number="BLOCKED-SKU",
            exception_code="SOURCE_CONFLICT",
            severity="high",
            status="open",
            details={},
        )
        session.add(exception)
        await session.flush()

        with pytest.raises(ValueError, match="unresolved_exception_parts"):
            await bom_service._governed_sku_contracts(
                release=release,
                part_numbers={"BLOCKED-SKU"},
                currency="USD",
                db=session,
            )

        exception.status = "resolved"
        rule = await session.scalar(
            select(CommercialRuleFamily).where(
                CommercialRuleFamily.family_key == "test::blocked-sku"
            )
        )
        assert rule is not None
        rule.status = "draft"
        await session.flush()
        with pytest.raises(ValueError, match="missing_approved_rules"):
            await bom_service._governed_sku_contracts(
                release=release,
                part_numbers={"BLOCKED-SKU"},
                currency="USD",
                db=session,
            )


@pytest.mark.asyncio
async def test_historical_bom_reads_but_cannot_be_newly_published_without_release(
    test_engine: AsyncEngine,
) -> None:
    """Legacy snapshots remain readable while publication requires governed evidence."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(name="Historical BOM", status=ProjectStatus.ACTIVE, owner_id="owner")
        source = PriceSource(
            name="Historical source",
            source_type="public_list",
            currency="USD",
            status="active",
            source_config={},
            created_by="test",
        )
        session.add_all([project, source])
        await session.flush()
        technical = VolumetrySnapshot(
            project_id=project.id,
            assumption_set_version="1.0.0",
            triggered_by="test",
            row_results={},
            consolidated={},
            snapshot_metadata={},
        )
        catalog = PriceCatalogSnapshot(
            source_id=source.id,
            currency="USD",
            retrieved_at=datetime.now(UTC),
            content_hash="historical-catalog",
            item_count=0,
            approval_status="approved",
            snapshot_metadata={},
        )
        session.add_all([technical, catalog])
        await session.flush()
        scenario = DeploymentScenario(
            project_id=project.id,
            name="Historical scenario",
            status="approved",
            currency="USD",
            region="global",
            price_mode="public_list",
            technical_snapshot_id=technical.id,
            contract_months=12,
            start_date=date(2026, 1, 1),
            proration_policy="full_month",
            consumption_model="explicit_units",
            service_config={},
            scenario_assumptions={},
            created_by="test",
        )
        session.add(scenario)
        await session.flush()
        snapshot = BomSnapshot(
            project_id=project.id,
            scenario_id=scenario.id,
            technical_snapshot_id=technical.id,
            price_catalog_snapshot_id=catalog.id,
            commercial_release_id=None,
            mapping_version="legacy",
            engine_version="legacy",
            currency="USD",
            coverage_pct=100,
            monthly_total=0,
            annual_total=0,
            contract_total=0,
            steady_state_monthly_total=0,
            peak_monthly_total=0,
            ramp_deferred_amount=0,
            summary={},
            warnings=[],
            publication_status="draft",
        )
        session.add(snapshot)
        await session.flush()

        readable = await bom_service.get_bom_snapshot(project.id, snapshot.id, session)
        assert readable.id == snapshot.id
        with pytest.raises(HTTPException) as exc_info:
            await bom_service.review_bom_snapshot(
                project.id,
                snapshot.id,
                BomReviewRequest(publication_status="published"),
                "architect",
                session,
            )
        assert exc_info.value.status_code == 409
        detail = cast(dict[str, object], exc_info.value.detail)
        assert detail["error_code"] == "BOM_COMMERCIAL_RELEASE_REQUIRED"


@pytest.mark.asyncio
async def test_scenario_assistant_uses_current_published_bom(test_engine: AsyncEngine) -> None:
    """A published current BOM replaces generic missing-input assumptions."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(name="Current BOM", status=ProjectStatus.ACTIVE, owner_id="owner")
        source = PriceSource(
            name="Public",
            source_type="public_list",
            currency="USD",
            status="active",
            source_config={},
            created_by="test",
        )
        session.add_all([project, source])
        await session.flush()
        technical = VolumetrySnapshot(
            project_id=project.id,
            assumption_set_version="1.0.0",
            triggered_by="test",
            row_results={},
            consolidated={},
            snapshot_metadata={},
        )
        catalog = PriceCatalogSnapshot(
            source_id=source.id,
            currency="USD",
            retrieved_at=datetime.now(UTC),
            content_hash="current-bom-price",
            item_count=1,
            approval_status="approved",
            snapshot_metadata={},
        )
        session.add_all([technical, catalog])
        await session.flush()
        scenario = DeploymentScenario(
            project_id=project.id,
            name="Published production baseline",
            status="approved",
            currency="USD",
            region="global",
            price_mode="public_list",
            technical_snapshot_id=technical.id,
            contract_months=12,
            start_date=date(2026, 1, 1),
            proration_policy="full_month",
            consumption_model="explicit_units",
            service_config={},
            scenario_assumptions={},
            created_by="test",
            approved_by="architect",
            approved_at=datetime.now(UTC),
        )
        session.add(scenario)
        await session.flush()
        session.add(
            DeploymentEnvironmentPlan(
                scenario_id=scenario.id,
                name="Production",
                sequence=1,
                active_hours_month=744,
                demand_share=1,
                ha_multiplier=1,
                dr_role="primary",
            )
        )
        bom = BomSnapshot(
            project_id=project.id,
            scenario_id=scenario.id,
            technical_snapshot_id=technical.id,
            price_catalog_snapshot_id=catalog.id,
            mapping_version="test",
            engine_version="test",
            currency="USD",
            coverage_pct=100,
            monthly_total=100,
            annual_total=1200,
            contract_total=1200,
            steady_state_monthly_total=100,
            peak_monthly_total=100,
            ramp_deferred_amount=0,
            first_active_period=1,
            steady_state_period=1,
            summary={"line_count": 2, "blocked_line_count": 0},
            warnings=[],
            publication_status="published",
            approved_by="architect",
            approved_at=datetime.now(UTC),
        )
        session.add(bom)
        await session.flush()
        session.add(
            BomLineItem(
                bom_snapshot_id=bom.id,
                environment="Production",
                service_id="OIC3",
                part_number="B89639",
                description="Oracle Integration",
                metric_name="5K messages per hour",
                quantity=1,
                unit="message packs",
                unit_price=100,
                monthly_amount=100,
                annual_amount=1200,
                contract_amount=1200,
                formula="1 x 100",
                inputs={},
                status="priced",
                warnings=[],
                provenance={},
            )
        )
        session.add(
            BomLineItem(
                bom_snapshot_id=bom.id,
                environment="Production",
                service_id="DATA_CATALOG",
                part_number=None,
                description="OCI Data Catalog",
                metric_name="Included technical capability",
                quantity=0,
                unit="included",
                unit_price=0,
                monthly_amount=0,
                annual_amount=0,
                contract_amount=0,
                formula="non-billable governed evidence",
                inputs={},
                status="non_billable",
                warnings=[],
                provenance={},
            )
        )
        await session.commit()

        assistant = await bom_service.build_scenario_assistant(project.id, session)

        assert assistant.current_bom is not None
        assert assistant.current_bom.ready_for_use is True
        assert assistant.current_bom.publication_status == "published"
        assert assistant.current_bom.environment_names == ["Production"]
        assert assistant.current_bom.line_item_count == 2
        assert assistant.current_bom.unresolved_line_count == 0
        assert assistant.required_questions == []
        assert assistant.confidence == "high"
        assert assistant.draft.name == "Published production baseline alternative"


@pytest.mark.asyncio
async def test_bom_comparison_explains_governed_delta(test_engine: AsyncEngine) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(name="Compare BOM", status=ProjectStatus.ACTIVE, owner_id="owner")
        session.add(project)
        await session.flush()
        technical = VolumetrySnapshot(
            project_id=project.id,
            assumption_set_version="1.0.0",
            triggered_by="test",
            row_results={},
            consolidated={},
            snapshot_metadata={},
        )
        source = PriceSource(
            name="Public",
            source_type="public_list",
            currency="USD",
            status="active",
            source_config={},
            created_by="test",
        )
        session.add_all([technical, source])
        await session.flush()
        catalog = PriceCatalogSnapshot(
            source_id=source.id,
            currency="USD",
            retrieved_at=technical.created_at,
            content_hash="compare-price",
            item_count=0,
            approval_status="approved",
            snapshot_metadata={},
        )
        scenario = DeploymentScenario(
            project_id=project.id,
            name="Compare",
            status="approved",
            currency="USD",
            region="global",
            price_mode="public_list",
            technical_snapshot_id=technical.id,
            contract_months=12,
            start_date=date(2026, 1, 1),
            proration_policy="full_month",
            service_config={},
            scenario_assumptions={},
            created_by="test",
        )
        session.add_all([catalog, scenario])
        await session.flush()
        common = {
            "project_id": project.id,
            "scenario_id": scenario.id,
            "technical_snapshot_id": technical.id,
            "price_catalog_snapshot_id": catalog.id,
            "mapping_version": "test",
            "engine_version": "test",
            "currency": "USD",
            "coverage_pct": 100.0,
            "contract_total": 1200.0,
            "steady_state_monthly_total": 100.0,
            "peak_monthly_total": 100.0,
            "ramp_deferred_amount": 0.0,
            "first_active_period": 1,
            "steady_state_period": 1,
            "warnings": [],
            "publication_status": "draft",
        }
        baseline = BomSnapshot(
            **common,
            monthly_total=100.0,
            annual_total=1200.0,
            summary={"by_service_monthly": {"OIC3": 100}, "by_environment_monthly": {"Production": 100}, "monthly_series": []},
        )
        comparison = BomSnapshot(
            **{
                **common,
                "contract_total": 1500.0,
                "steady_state_monthly_total": 125.0,
                "peak_monthly_total": 125.0,
            },
            monthly_total=125.0,
            annual_total=1500.0,
            summary={"by_service_monthly": {"OIC3": 125}, "by_environment_monthly": {"Production": 125}, "monthly_series": []},
        )
        session.add_all([baseline, comparison])
        await session.commit()

        result = await bom_service.compare_bom_snapshots(project.id, baseline.id, comparison.id, session)
        assert result.monthly_delta == 25.0
        assert result.service_monthly_deltas == {"OIC3": 25.0}
        assert result.drivers[0] == "Service OIC3: +25.00 USD/month"


@pytest.mark.asyncio
async def test_scenario_persists_multiple_environments_and_service_ramps(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    """The public contract round-trips normalized environment and phase ownership."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        project = Project(name="Ramp scenario", status=ProjectStatus.ACTIVE, owner_id="owner")
        session.add(project)
        await session.flush()
        technical = VolumetrySnapshot(
            project_id=project.id,
            assumption_set_version="1.0.0",
            triggered_by="test",
            row_results={},
            consolidated={},
            snapshot_metadata={},
        )
        session.add(technical)
        await session.commit()

    response = await api_client.post(
        f"/api/v1/projects/{project.id}/deployment-scenarios",
        headers={"X-Actor-Role": "Architect", "X-Actor-Id": "architect"},
        json={
            "name": "Phased rollout",
            "technical_snapshot_id": technical.id,
            "consumption_model": "legacy_share",
            "start_date": "2026-02-01",
            "contract_months": 24,
            "environments": [
                {
                    "name": "Production",
                    "demand_share": 0.8,
                    "phases": [
                        {"service_id": None, "start_month": 3, "end_month": 6, "start_multiplier": 0.25, "end_multiplier": 1.0, "interpolation": "linear"}
                    ],
                },
                {
                    "name": "QA",
                    "demand_share": 0.2,
                    "dr_role": "none",
                    "phases": [
                        {"service_id": None, "start_month": 1, "end_month": 24, "start_multiplier": 1.0, "end_multiplier": 1.0, "interpolation": "step"},
                        {"service_id": "OIC3", "start_month": 2, "end_month": 24, "start_multiplier": 0.5, "end_multiplier": 0.5, "interpolation": "step"},
                    ],
                },
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["start_date"] == "2026-02-01"
    assert [item["name"] for item in payload["environments"]] == ["Production", "QA"]
    assert payload["environments"][1]["phases"][1]["service_id"] == "OIC3"
