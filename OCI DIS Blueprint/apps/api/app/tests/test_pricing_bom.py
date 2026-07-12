"""Integration coverage for governed OCI price catalogs and BOM generation."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import (
    BomSnapshot,
    CatalogIntegration,
    DeploymentScenario,
    PriceCatalogSnapshot,
    PriceItem,
    PriceSource,
    Project,
    ServiceProductSkuMapping,
    VolumetrySnapshot,
)
from app.models.project import ProjectStatus
from app.services import bom_service, pricing_service


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
            "environments": [
                {"name": "Production", "demand_share": 0.8},
                {"name": "Non-production", "demand_share": 0.4},
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "SCENARIO_DEMAND_SHARE_INVALID"


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
            environments=[
                {
                    "name": "Production",
                    "active_hours_month": 744,
                    "active_months_year": 12,
                    "demand_share": 1.0,
                    "ha_multiplier": 1.0,
                    "dr_role": "primary",
                }
            ],
            service_config={"OIC3": {"edition": "standard", "byol": False}},
            scenario_assumptions={"free_tier_enabled": False},
            created_by="test",
        )
        session.add_all([catalog, mapping, scenario])
        await session.flush()
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
            job_response = await bom_service.create_bom_job(project.id, scenario.id, "architect", session)
        async with session.begin():
            job = await bom_service.run_bom_job(job_response.id, session)
        assert job.status == "completed"
        assert job.bom_snapshot_id is not None
        snapshot = await bom_service.get_bom_snapshot(project.id, job.bom_snapshot_id, session)
        assert snapshot.coverage_pct == 100.0
        assert snapshot.monthly_total == 960.06
        assert snapshot.line_items[0].provenance["mapping_id"] == mapping.id
        assert snapshot.line_items[0].formula.endswith("* hours")


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
            environments=[],
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
            "warnings": [],
            "publication_status": "draft",
        }
        baseline = BomSnapshot(
            **common,
            monthly_total=100.0,
            annual_total=1200.0,
            summary={"by_service_monthly": {"OIC3": 100}, "by_environment_monthly": {"Production": 100}},
        )
        comparison = BomSnapshot(
            **{**common, "contract_total": 1500.0},
            monthly_total=125.0,
            annual_total=1500.0,
            summary={"by_service_monthly": {"OIC3": 125}, "by_environment_monthly": {"Production": 125}},
        )
        session.add_all([baseline, comparison])
        await session.commit()

        result = await bom_service.compare_bom_snapshots(project.id, baseline.id, comparison.id, session)
        assert result.monthly_delta == 25.0
        assert result.service_monthly_deltas == {"OIC3": 25.0}
        assert result.drivers[0] == "Service OIC3: +25.00 USD/month"
