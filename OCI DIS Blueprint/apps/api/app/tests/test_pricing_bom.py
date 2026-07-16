"""Integration coverage for governed OCI price catalogs and BOM generation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import (
    BomLineItem,
    BomLinePeriod,
    BomSnapshot,
    CatalogIntegration,
    DeploymentScenario,
    DeploymentEnvironmentPlan,
    DeploymentRampPhase,
    PriceCatalogSnapshot,
    PriceItem,
    PriceSource,
    Project,
    ServiceProductSkuMapping,
    ServiceCommercialPolicy,
    VolumetrySnapshot,
)
from app.models.project import ProjectStatus
from app.services import bom_service, pricing_service


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
    assert payload["consumption_model"] == "explicit_units"
    assert payload["environments"][0]["phases"][0]["monthly_quantities"] == [
        {"period_index": 1, "quantity": 1.0},
        {"period_index": 2, "quantity": 2.0},
        {"period_index": 3, "quantity": 4.0},
    ]


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
        catalog = PriceCatalogSnapshot(
            source_id=source.id,
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
        assert len(snapshot.monthly_series) == 12
        assert len(snapshot.line_items[0].periods) == 12
        assert snapshot.line_items[0].provenance["mapping_id"] == mapping.id
        assert snapshot.line_items[0].provenance["quantity_source"] == "explicit_units"
        assert snapshot.line_items[0].periods[0].quantity == 2
        assert snapshot.line_items[0].formula.endswith("* hours")
        assert snapshot.recommendation_workspace.context == "bom"
        assert snapshot.recommendation_workspace.candidates
        assert snapshot.recommendation_workspace.candidates[0].implementation_steps


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
        catalog = PriceCatalogSnapshot(
            source_id=source.id,
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
