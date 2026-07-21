"""Governed OCI product-coverage generation and promotion tests."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import (
    CommercialDocumentSnapshot,
    CommercialMappingCandidate,
    CommercialRelease,
    CommercialRuleFamily,
    CommercialSku,
    PriceCatalogSnapshot,
    PriceItem,
    PriceSource,
    ProductCoverageCandidate,
    ServiceCapabilityProfile,
    ServiceCommercialPolicy,
    ServiceProductSkuMapping,
    SkuCommercialTerm,
)
from app.services.commercial_catalog_service import GENERATOR_VERSION as COMMERCIAL_GENERATOR_VERSION


ADMIN_HEADERS = {"X-Actor-Role": "Admin", "X-Actor-Id": "coverage-reviewer"}


async def _add_commercial_product(
    db: AsyncSession,
    *,
    document: CommercialDocumentSnapshot,
    snapshot: PriceCatalogSnapshot,
    part_number: str,
    product_name: str,
) -> tuple[CommercialMappingCandidate, SkuCommercialTerm, CommercialRuleFamily]:
    sku = CommercialSku(
        part_number=part_number,
        display_name=f"{product_name} metered unit",
        service_category="Captured fallback",
        lifecycle_status="active",
        identity_metadata={
            "product_hierarchy": [
                "Section 1 - Universal Credits",
                "PaaS - Test Services",
                "Governed Test Services",
                product_name,
            ]
        },
    )
    db.add(sku)
    await db.flush()
    price_item = PriceItem(
        snapshot_id=snapshot.id,
        part_number=part_number,
        display_name=sku.display_name,
        metric_name="Requests Per Month",
        service_category="Governed Test Services",
        price_type="MONTH",
        currency="USD",
        model="PAY_AS_YOU_GO",
        value=1,
    )
    term = SkuCommercialTerm(
        document_snapshot_id=document.id,
        commercial_sku_id=sku.id,
        price_catalog_snapshot_id=snapshot.id,
        part_number=part_number,
        service_name=sku.display_name,
        service_category="Governed Test Services",
        commercial_prices=[],
        currency="USD",
        metric_name="Requests Per Month",
        price_type="MONTH",
        allow_decimal_quantity=False,
        availability=[],
        additional_information="Purchase in whole governed request units.",
        disposition="direct_metered",
        family_key=f"month::requests::{part_number.casefold()}",
        status="approved",
        confidence=1,
        source_sheet="Price List",
        source_row=1,
        source_cells={"part_number": "A1"},
        extraction_metadata={},
    )
    rule = CommercialRuleFamily(
        family_key=f"month::requests::{part_number.casefold()}",
        version="1.0.0",
        formula_key="metered_quantity",
        metric_pattern="Requests Per Month",
        price_types=["MONTH"],
        quantity_behavior="packaged",
        quantity_increment=Decimal("1"),
        minimum_quantity=Decimal("1"),
        aggregation_window="calendar_month",
        proration_policy="full_month",
        quote_rounding="ceiling",
        generator_version=COMMERCIAL_GENERATOR_VERSION,
        status="approved",
        fixture_status="passed",
        evidence={"fixture_checks": [{"name": "whole_units", "passed": True}]},
        approved_by="fixture",
        approved_at=datetime.now(UTC),
    )
    db.add_all([price_item, term, rule])
    await db.flush()
    candidate = CommercialMappingCandidate(
        document_snapshot_id=document.id,
        commercial_sku_id=sku.id,
        term_id=term.id,
        price_item_id=price_item.id,
        part_number=part_number,
        proposed_service_id=None,
        family_key=rule.family_key,
        classification="direct_metered",
        proposed_mapping={"commercial_rule_family_id": rule.id},
        confidence=1,
        generator_version=COMMERCIAL_GENERATOR_VERSION,
        status="approved",
        reasons=[],
        reviewed_by="fixture",
        reviewed_at=datetime.now(UTC),
    )
    db.add(candidate)
    await db.flush()
    return candidate, term, rule


async def _seed_coverage_evidence(test_engine: AsyncEngine, *, collision: bool = False) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        now = datetime.now(UTC)
        source = PriceSource(
            name="Oracle public pricing",
            source_type="public_list",
            currency="USD",
            status="active",
            created_by="fixture",
        )
        db.add(source)
        await db.flush()
        snapshot = PriceCatalogSnapshot(
            source_id=source.id,
            currency="USD",
            retrieved_at=now,
            content_hash="coverage-price-snapshot",
            item_count=3,
            approval_status="approved",
        )
        db.add(snapshot)
        await db.flush()
        document = CommercialDocumentSnapshot(
            document_kind="oracle_localizable_price_list",
            source_name="Oracle test price list",
            source_url="test://oracle-price-list",
            original_filename="oracle-price-list.xlsx",
            storage_reference="s3://pricing/oracle-price-list.xlsx",
            content_hash="coverage-document",
            parser_version="coverage-test-1",
            currency="USD",
            status="approved_evidence",
            record_count=3,
            retrieved_at=now,
            manifest={"price_snapshot_id": snapshot.id},
            approved_by="fixture",
            approved_at=now,
        )
        db.add(document)
        await db.flush()
        ready_candidate, ready_term, ready_rule = await _add_commercial_product(
            db,
            document=document,
            snapshot=snapshot,
            part_number="BREADY",
            product_name="Ready Product",
        )
        await _add_commercial_product(
            db,
            document=document,
            snapshot=snapshot,
            part_number="BBLOCKED",
            product_name="Blocked Product",
        )
        if collision:
            await _add_commercial_product(
                db,
                document=document,
                snapshot=snapshot,
                part_number="BCOLLISION",
                product_name="Collision Product",
            )
            db.add(
                ServiceCapabilityProfile(
                    service_id="COLLISION_PRODUCT",
                    name="Different Existing Product",
                    category="Existing",
                    is_active=True,
                    version="1.0.0",
                )
            )
        release = CommercialRelease(
            version="coverage-release-1",
            price_catalog_snapshot_id=snapshot.id,
            document_snapshot_id=document.id,
            mapping_set_hash="coverage-mappings",
            rule_family_set_hash="coverage-rules",
            evidence_hash="coverage-evidence",
            status="approved",
            validation_status="passed",
            open_exception_count=0,
            release_metadata={
                "part_numbers": ["BREADY"],
                "term_ids_by_part": {"BREADY": ready_term.id},
                "rule_ids_by_part": {"BREADY": ready_rule.id},
                "candidate_ids_by_part": {"BREADY": ready_candidate.id},
            },
            approved_by="fixture",
            approved_at=now,
        )
        db.add(release)
        await db.commit()


@pytest.mark.asyncio
async def test_generation_is_idempotent_and_does_not_activate_bom_mappings(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine)

    first = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    assert first.status_code == 200, first.text
    assert first.json()["total"] == 2
    assert first.json()["generated"] == 2
    assert first.json()["ready"] == 1

    second = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    assert second.status_code == 200, second.text
    assert second.json()["generated"] == 0
    assert second.json()["refreshed"] == 2

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        candidate_count = int(
            await db.scalar(select(func.count()).select_from(ProductCoverageCandidate)) or 0
        )
        active_mapping_count = int(
            await db.scalar(
                select(func.count())
                .select_from(ServiceProductSkuMapping)
                .where(ServiceProductSkuMapping.status == "approved")
            )
            or 0
        )
    assert candidate_count == 2
    assert active_mapping_count == 0


@pytest.mark.asyncio
async def test_readiness_gate_blocks_release_gap_and_materializes_ready_product_once(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine)
    generated = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    assert generated.status_code == 200, generated.text

    blocked = await api_client.post(
        "/api/v1/pricing/product-coverage/BLOCKED_PRODUCT/review",
        headers=ADMIN_HEADERS,
        json={"decision": "approve", "rationale": "Attempt blocked promotion."},
    )
    assert blocked.status_code == 409
    assert any(
        item["code"] == "sku_not_in_active_release"
        for item in blocked.json()["detail"]["blockers"]
    )

    for _ in range(2):
        approved = await api_client.post(
            "/api/v1/pricing/product-coverage/READY_PRODUCT/review",
            headers=ADMIN_HEADERS,
            json={"decision": "approve", "rationale": "Evidence and fixtures are complete."},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"

    refreshed = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    assert refreshed.status_code == 200, refreshed.text
    approved_detail = await api_client.get(
        "/api/v1/pricing/product-coverage/READY_PRODUCT",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert approved_detail.status_code == 200, approved_detail.text
    assert approved_detail.json()["status"] == "approved"

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        assert int(await db.scalar(select(func.count()).select_from(ServiceCapabilityProfile)) or 0) == 1
        assert int(await db.scalar(select(func.count()).select_from(ServiceCommercialPolicy)) or 0) == 1
        assert int(await db.scalar(select(func.count()).select_from(ServiceProductSkuMapping)) or 0) == 1


@pytest.mark.asyncio
async def test_service_id_collision_remains_visible_and_non_promotable(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine, collision=True)
    generated = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    assert generated.status_code == 200, generated.text

    detail = await api_client.get(
        "/api/v1/pricing/product-coverage/COLLISION_PRODUCT",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["promotable"] is False
    assert any(item["code"] == "service_id_collision" for item in payload["readiness_blockers"])


@pytest.mark.asyncio
async def test_coverage_list_is_paginated_and_rejects_viewer_generation(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine)
    forbidden = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert forbidden.status_code == 403
    await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    page = await api_client.get(
        "/api/v1/pricing/product-coverage?page=1&page_size=1",
        headers={"X-Actor-Role": "Architect"},
    )
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 2
    assert page.json()["page_size"] == 1
    assert len(page.json()["products"]) == 1
