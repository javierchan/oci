"""Continuous OCI source verification and quote-promotion gates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import (
    GovernanceChangeSet,
    PriceCatalogSnapshot,
    PriceSource,
    PriceSyncJob,
    ServiceCapabilityProfile,
    ServiceCommercialPolicy,
    ServiceProductSkuMapping,
)
from app.services import pricing_governance_service, pricing_service


def _bundle() -> dict[str, tuple[str, dict[str, object]]]:
    return {
        "price_catalog": (
            "https://apexapps.oracle.com/prices",
            {"items": [{"partNumber": "B1"}], "lastUpdated": "2026-07-16T00:00:00Z"},
        ),
        "products": ("https://www.oracle.com/products.json", {"products": [{"id": "B1"}]}),
        "metrics": ("https://www.oracle.com/metrics.json", {"metrics": [{"id": "M1"}]}),
        "presets": ("https://www.oracle.com/presets.json", {"presets": [{"id": "P1"}]}),
    }


def _normalized_prices() -> list[dict[str, object]]:
    return [
        {
            "part_number": "B1",
            "display_name": "Governed integration service",
            "metric_name": "Unit per month",
            "service_category": "Integration",
            "price_type": "MONTH",
            "currency": "USD",
            "model": "PAY_AS_YOU_GO",
            "value": 2.0,
            "range_min": None,
            "range_max": None,
            "range_unit": None,
        }
    ]


@pytest.mark.asyncio
async def test_change_set_archives_all_sources_and_runs_family_fixture(
    test_engine: AsyncEngine,
    isolated_object_storage: dict[str, bytes],
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        async with db.begin():
            source = PriceSource(
                name="Oracle public prices",
                source_type="public_list",
                base_url="https://apexapps.oracle.com/prices",
                currency="USD",
                status="active",
                created_by="test",
            )
            db.add(source)
            await db.flush()
            job = PriceSyncJob(source_id=source.id, requested_by="test", currency="USD", status="running")
            profile = ServiceCapabilityProfile(
                service_id="TEST",
                name="Test service",
                category="Integration",
                limits={},
            )
            db.add_all([job, profile])
            await db.flush()
            policy = ServiceCommercialPolicy(
                service_profile_id=profile.id,
                service_id="TEST",
                classification="direct_metered",
                readiness="quote_ready",
                publication_policy="priced",
                tool_aliases=["Test"],
                dependent_service_ids=[],
                required_inputs=[],
                guidance="Use measured units.",
                source_urls=[],
                status="approved",
            )
            mapping = ServiceProductSkuMapping(
                service_profile_id=profile.id,
                service_id="TEST",
                tool_key="Test",
                part_number="B1",
                billing_metric_key="test_units",
                formula_key="monthly_quantity",
                quantity_behavior="fixed_capacity",
                quantity_increment=1,
                minimum_quantity=1,
                quantity_unit="units",
                is_billable=True,
                status="approved",
            )
            snapshot = PriceCatalogSnapshot(
                source_id=source.id,
                sync_job_id=job.id,
                currency="USD",
                retrieved_at=datetime.now(UTC),
                content_hash="candidate",
                item_count=1,
                approval_status="pending_review",
                snapshot_metadata={},
            )
            db.add_all([policy, mapping, snapshot])
            await db.flush()
            change_set = await pricing_governance_service.persist_change_set(
                job=job,
                source=source,
                snapshot=snapshot,
                previous_snapshot=None,
                bundle=_bundle(),
                normalized_prices=_normalized_prices(),
                trigger_type="manual",
                db=db,
            )

        response = await pricing_service.get_governance_change_set(change_set.id, db)
        assert response.validation_status == "passed"
        assert response.status == "ready_for_review"
        assert len(response.artifacts) == 4
        assert response.regression_summary == {
            "families": 1,
            "passed": 1,
            "failed": 0,
            "coverage_pct": 100.0,
        }
        assert response.regressions[0].family_key == "TEST"
        assert response.regressions[0].status == "passed"
        assert len(isolated_object_storage) == 4


@pytest.mark.asyncio
async def test_public_snapshot_approval_requires_passing_change_set(test_engine: AsyncEngine) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        async with db.begin():
            source = PriceSource(
                name="Oracle public prices",
                source_type="public_list",
                base_url="https://apexapps.oracle.com/prices",
                currency="USD",
                status="active",
                created_by="test",
            )
            db.add(source)
            await db.flush()
            job = PriceSyncJob(source_id=source.id, requested_by="test", currency="USD", status="completed")
            db.add(job)
            await db.flush()
            snapshot = PriceCatalogSnapshot(
                source_id=source.id,
                sync_job_id=job.id,
                currency="USD",
                retrieved_at=datetime.now(UTC),
                content_hash="candidate",
                item_count=1,
                approval_status="pending_review",
                snapshot_metadata={},
            )
            db.add(snapshot)
            await db.flush()
            blocked = GovernanceChangeSet(
                sync_job_id=job.id,
                price_source_id=source.id,
                price_snapshot_id=snapshot.id,
                trigger_type="manual",
                currency="USD",
                status="blocked",
                drift_classification="commercial",
                materiality_score=1,
                source_manifest={},
                drift_summary={},
                impact_summary={},
                validation_status="failed",
                regression_summary={"families": 1, "passed": 0, "failed": 1},
                approval_status="blocked",
            )
            db.add(blocked)

        with pytest.raises(Exception) as exc_info:
            async with db.begin():
                await pricing_service.approve_price_snapshot(snapshot.id, "admin", db)
        assert "Quotation regression" in str(exc_info.value)


@pytest.mark.asyncio
async def test_public_snapshot_freshness_is_enforced(
    test_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        async with db.begin():
            source = PriceSource(
                name="Oracle public prices",
                source_type="public_list",
                base_url="https://apexapps.oracle.com/prices",
                currency="USD",
                status="active",
                created_by="test",
            )
            db.add(source)
            await db.flush()
            job = PriceSyncJob(source_id=source.id, requested_by="test", currency="USD", status="completed")
            db.add(job)
            await db.flush()
            snapshot = PriceCatalogSnapshot(
                source_id=source.id,
                sync_job_id=job.id,
                currency="USD",
                retrieved_at=datetime.now(UTC),
                content_hash="approved",
                item_count=1,
                approval_status="approved",
                snapshot_metadata={},
            )
            db.add(snapshot)
            await db.flush()
            change_set = GovernanceChangeSet(
                sync_job_id=job.id,
                price_source_id=source.id,
                price_snapshot_id=snapshot.id,
                trigger_type="scheduled",
                currency="USD",
                status="promoted",
                drift_classification="baseline",
                materiality_score=0,
                source_manifest={},
                drift_summary={},
                impact_summary={},
                validation_status="passed",
                regression_summary={"families": 20, "passed": 20, "failed": 0},
                approval_status="approved",
                promoted_at=datetime.now(UTC) - timedelta(hours=73),
            )
            db.add(change_set)

        monkeypatch.setattr(
            pricing_governance_service,
            "get_settings",
            lambda: type("Settings", (), {"OCI_GOVERNANCE_MAX_SOURCE_AGE_HOURS": 72})(),
        )
        with pytest.raises(ValueError, match="stale"):
            await pricing_governance_service.ensure_public_snapshot_is_current(snapshot, db)
