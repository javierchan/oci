"""Governed OCI product-coverage generation and promotion tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
    SkuCommercialRelationship,
    SkuCommercialTerm,
)
from app.services import product_catalog_service
from app.services.commercial_catalog_service import GENERATOR_VERSION as COMMERCIAL_GENERATOR_VERSION


ADMIN_HEADERS = {"X-Actor-Role": "Admin", "X-Actor-Id": "coverage-reviewer"}


async def _add_commercial_product(
    db: AsyncSession,
    *,
    document: CommercialDocumentSnapshot,
    snapshot: PriceCatalogSnapshot,
    part_number: str,
    product_name: str,
    classification: str = "direct_metered",
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
    price_item = (
        PriceItem(
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
        if classification == "direct_metered"
        else None
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
        disposition=classification,
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
    db.add_all([item for item in [price_item, term, rule] if item is not None])
    await db.flush()
    candidate = CommercialMappingCandidate(
        document_snapshot_id=document.id,
        commercial_sku_id=sku.id,
        term_id=term.id,
        price_item_id=price_item.id if price_item else None,
        part_number=part_number,
        proposed_service_id=None,
        family_key=rule.family_key,
        classification=classification,
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


async def _seed_coverage_evidence(
    test_engine: AsyncEngine,
    *,
    collision: bool = False,
    include_external: bool = False,
    include_non_priced: bool = False,
) -> None:
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
        external_contract: tuple[
            CommercialMappingCandidate,
            SkuCommercialTerm,
            CommercialRuleFamily,
        ] | None = None
        if include_external:
            external_contract = await _add_commercial_product(
                db,
                document=document,
                snapshot=snapshot,
                part_number="BEXTERNAL",
                product_name="External Product",
                classification="external_rate_card",
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
        if include_non_priced:
            await _add_commercial_product(
                db,
                document=document,
                snapshot=snapshot,
                part_number="BINPUT",
                product_name="Client Input Product",
                classification="blocked_input_required",
            )
            await _add_commercial_product(
                db,
                document=document,
                snapshot=snapshot,
                part_number="BDEPENDENT",
                product_name="Dependent Product",
                classification="dependent_entitlement",
            )
            input_sku = await db.scalar(
                select(CommercialSku).where(CommercialSku.part_number == "BDEPENDENT")
            )
            parent_sku = await db.scalar(
                select(CommercialSku).where(CommercialSku.part_number == "BREADY")
            )
            assert input_sku is not None and parent_sku is not None
            db.add(
                SkuCommercialRelationship(
                    document_snapshot_id=document.id,
                    source_commercial_sku_id=input_sku.id,
                    target_commercial_sku_id=parent_sku.id,
                    part_number=input_sku.part_number,
                    relationship_type="requires",
                    target_part_number=parent_sku.part_number,
                    target_name=parent_sku.display_name,
                    guidance="Requires the governed parent product.",
                    resolution_status="resolved",
                    confidence=1,
                    status="approved",
                    source_sheet="Price List",
                    source_row=2,
                    source_cell="A2",
                )
            )
        release_part_numbers = ["BREADY"]
        term_ids_by_part = {"BREADY": ready_term.id}
        rule_ids_by_part = {"BREADY": ready_rule.id}
        candidate_ids_by_part = {"BREADY": ready_candidate.id}
        if external_contract:
            external_candidate, external_term, external_rule = external_contract
            release_part_numbers.append("BEXTERNAL")
            term_ids_by_part["BEXTERNAL"] = external_term.id
            rule_ids_by_part["BEXTERNAL"] = external_rule.id
            candidate_ids_by_part["BEXTERNAL"] = external_candidate.id
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
                "part_numbers": release_part_numbers,
                "term_ids_by_part": term_ids_by_part,
                "rule_ids_by_part": rule_ids_by_part,
                "candidate_ids_by_part": candidate_ids_by_part,
            },
            approved_by="fixture",
            approved_at=now,
        )
        db.add(release)
        await db.commit()


async def _add_newer_release_without_candidates(test_engine: AsyncEngine) -> None:
    """Reproduce a narrow approved release that has no coverage candidates of its own."""

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        existing_release = await db.scalar(
            select(CommercialRelease).order_by(CommercialRelease.approved_at.desc())
        )
        assert existing_release is not None
        now = datetime.now(UTC) + timedelta(seconds=1)
        document = CommercialDocumentSnapshot(
            document_kind="browser_validation_evidence",
            source_name="Narrow browser validation evidence",
            source_url="test://browser-validation",
            original_filename="browser-validation.xlsx",
            storage_reference="s3://pricing/browser-validation.xlsx",
            content_hash="narrow-browser-validation-document",
            parser_version="coverage-test-1",
            currency="USD",
            status="approved_evidence",
            record_count=1,
            retrieved_at=now,
            manifest={},
            approved_by="fixture",
            approved_at=now,
        )
        db.add(document)
        await db.flush()
        db.add(
            CommercialRelease(
                version="narrow-browser-release-1",
                price_catalog_snapshot_id=existing_release.price_catalog_snapshot_id,
                document_snapshot_id=document.id,
                mapping_set_hash="narrow-browser-mappings",
                rule_family_set_hash="narrow-browser-rules",
                evidence_hash="narrow-browser-evidence",
                status="approved",
                validation_status="passed",
                open_exception_count=0,
                release_metadata=dict(existing_release.release_metadata),
                approved_by="fixture",
                approved_at=now,
            )
        )
        await db.commit()


async def _latest_release_document_id(test_engine: AsyncEngine) -> str:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        release = await db.scalar(
            select(CommercialRelease).order_by(CommercialRelease.approved_at.desc())
        )
        assert release is not None
        return release.document_snapshot_id


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
async def test_generation_uses_latest_approved_candidate_evidence_when_release_is_narrow(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine, include_non_priced=True)
    await _add_newer_release_without_candidates(test_engine)

    response = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 4
    input_product = await api_client.get(
        "/api/v1/pricing/product-coverage/CLIENT_INPUT_PRODUCT",
        headers=ADMIN_HEADERS,
    )
    assert input_product.status_code == 200, input_product.text
    payload = input_product.json()
    assert payload["proposed_policy"]["classification"] == "blocked_input_required"
    assert payload["proposed_policy"]["readiness"] == "input_required"
    assert payload["source_document_snapshot_id"] != (
        await _latest_release_document_id(test_engine)
    )


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
async def test_external_rate_product_is_promotable_but_requires_rate_card_at_quote_time(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine, include_external=True)
    generated = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    assert generated.status_code == 200, generated.text

    detail = await api_client.get(
        "/api/v1/pricing/product-coverage/EXTERNAL_PRODUCT",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["readiness_status"] == "ready"
    assert payload["commercial_readiness"] == "rate_card_required"
    assert payload["promotable"] is True
    assert payload["proposed_policy"]["publication_policy"] == "external_rate_required"
    assert payload["proposed_mappings"][0]["usage_basis"] == "external_rate_card"

    approved = await api_client.post(
        "/api/v1/pricing/product-coverage/EXTERNAL_PRODUCT/review",
        headers=ADMIN_HEADERS,
        json={
            "decision": "approve",
            "rationale": "Product and quantity rules are governed; customer pricing remains quote-specific.",
        },
    )
    assert approved.status_code == 200, approved.text

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        mapping = await db.scalar(
            select(ServiceProductSkuMapping).where(
                ServiceProductSkuMapping.part_number == "BEXTERNAL"
            )
        )
        assert mapping is not None
        assert mapping.usage_basis == "external_rate_card"


@pytest.mark.asyncio
async def test_non_priced_products_materialize_policy_without_billable_mapping(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine, include_non_priced=True)
    generated = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    assert generated.status_code == 200, generated.text

    expected = {
        "CLIENT_INPUT_PRODUCT": ("manual_pricing_required", []),
        "DEPENDENT_PRODUCT": ("dependencies_required", ["READY_PRODUCT"]),
    }
    for product_key, (publication_policy, dependencies) in expected.items():
        detail = await api_client.get(
            f"/api/v1/pricing/product-coverage/{product_key}",
            headers={"X-Actor-Role": "Viewer"},
        )
        assert detail.status_code == 200, detail.text
        payload = detail.json()
        assert payload["readiness_status"] == "ready"
        assert payload["commercial_readiness"] == "input_required"
        assert payload["proposed_mappings"] == []
        assert payload["proposed_policy"]["publication_policy"] == publication_policy
        assert payload["proposed_policy"]["dependent_service_ids"] == dependencies

        approved = await api_client.post(
            f"/api/v1/pricing/product-coverage/{product_key}/review",
            headers=ADMIN_HEADERS,
            json={
                "decision": "approve",
                "rationale": "Governed non-priced disposition remains visible without inventing a rate.",
            },
        )
        assert approved.status_code == 200, approved.text

    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        policies = list(
            (
                await db.scalars(
                    select(ServiceCommercialPolicy).where(
                        ServiceCommercialPolicy.service_id.in_(expected)
                    )
                )
            ).all()
        )
        mapping_count = int(
            await db.scalar(
                select(func.count())
                .select_from(ServiceProductSkuMapping)
                .where(ServiceProductSkuMapping.service_id.in_(expected))
            )
            or 0
        )
    assert {policy.service_id for policy in policies} == set(expected)
    assert mapping_count == 0


@pytest.mark.asyncio
async def test_long_product_key_uses_a_stable_service_id_without_blocking_coverage(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine, include_non_priced=True)
    product_name = "Client Input Product With An Exceptionally Long Governed Commercial Name"
    product_key = product_catalog_service.product_key(product_name)
    assert len(product_key) > 50
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        document = await db.scalar(select(CommercialDocumentSnapshot))
        snapshot = await db.scalar(select(PriceCatalogSnapshot))
        assert document is not None and snapshot is not None
        await _add_commercial_product(
            db,
            document=document,
            snapshot=snapshot,
            part_number="BINPUTLONG",
            product_name=product_name,
            classification="blocked_input_required",
        )
        await db.commit()

    for _ in range(2):
        generated = await api_client.post(
            "/api/v1/pricing/product-coverage/generate",
            headers=ADMIN_HEADERS,
        )
        assert generated.status_code == 200, generated.text
    detail = await api_client.get(
        f"/api/v1/pricing/product-coverage/{product_key}",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["readiness_status"] == "ready"
    assert payload["commercial_readiness"] == "input_required"
    assert len(payload["proposed_service_id"]) == 50
    assert payload["proposed_service_id"].startswith(product_key[:20])
    assert not any(
        blocker["code"] == "service_id_too_long"
        for blocker in payload["readiness_blockers"]
    )


@pytest.mark.asyncio
async def test_dependent_product_without_exact_parent_relation_is_blocked(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine, include_non_priced=True)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        relationship = await db.scalar(
            select(SkuCommercialRelationship).where(
                SkuCommercialRelationship.part_number == "BDEPENDENT"
            )
        )
        assert relationship is not None
        await db.delete(relationship)
        await db.commit()

    generated = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    assert generated.status_code == 200, generated.text
    detail = await api_client.get(
        "/api/v1/pricing/product-coverage/DEPENDENT_PRODUCT",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["promotable"] is False
    assert any(
        blocker["code"] == "dependent_service_missing"
        for blocker in detail.json()["readiness_blockers"]
    )


@pytest.mark.asyncio
async def test_dependent_product_accepts_an_exact_parent_pending_coverage_review(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine, include_non_priced=True)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        relationship = await db.scalar(
            select(SkuCommercialRelationship).where(
                SkuCommercialRelationship.part_number == "BDEPENDENT"
            )
        )
        assert relationship is not None
        db.add(
            CommercialSku(
                part_number="B12345",
                display_name="Ready Product prerequisite",
                service_category="Governed Test Services",
                lifecycle_status="active",
                identity_metadata={
                    "product_hierarchy": [
                        "Section 1 - Universal Credits",
                        "PaaS - Test Services",
                        "Governed Test Services",
                        "Ready Product",
                    ]
                },
            )
        )
        relationship.resolution_status = "unresolved"
        relationship.status = "draft"
        relationship.target_commercial_sku_id = None
        relationship.target_part_number = None
        relationship.target_name = "Requires as a prerequisite: B12345 - Ready Product."
        await db.commit()

    generated = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    assert generated.status_code == 200, generated.text
    detail = await api_client.get(
        "/api/v1/pricing/product-coverage/DEPENDENT_PRODUCT",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["promotable"] is True
    assert payload["readiness_status"] == "ready"
    assert payload["commercial_readiness"] == "input_required"
    assert payload["proposed_policy"]["publication_policy"] == "dependencies_required"
    assert payload["proposed_policy"]["dependent_service_ids"] == ["READY_PRODUCT"]


@pytest.mark.asyncio
async def test_dependent_product_blocks_an_unselected_parent_alternative(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine, include_non_priced=True)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        relationship = await db.scalar(
            select(SkuCommercialRelationship).where(
                SkuCommercialRelationship.part_number == "BDEPENDENT"
            )
        )
        assert relationship is not None
        relationship.target_commercial_sku_id = None
        relationship.target_part_number = None
        relationship.target_name = (
            "Requires one of the following: B12345 - Ready Product; "
            "OR B12346 - Blocked Product."
        )
        await db.commit()

    generated = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    assert generated.status_code == 200, generated.text
    detail = await api_client.get(
        "/api/v1/pricing/product-coverage/DEPENDENT_PRODUCT",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["promotable"] is False
    assert any(
        blocker["code"] == "dependent_service_ambiguous"
        for blocker in payload["readiness_blockers"]
    )


@pytest.mark.asyncio
async def test_dependent_product_rejects_an_explicitly_rejected_parent_relation(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_coverage_evidence(test_engine, include_non_priced=True)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        relationship = await db.scalar(
            select(SkuCommercialRelationship).where(
                SkuCommercialRelationship.part_number == "BDEPENDENT"
            )
        )
        assert relationship is not None
        relationship.resolution_status = "unresolved"
        relationship.status = "rejected"
        await db.commit()

    generated = await api_client.post(
        "/api/v1/pricing/product-coverage/generate",
        headers=ADMIN_HEADERS,
    )
    assert generated.status_code == 200, generated.text
    detail = await api_client.get(
        "/api/v1/pricing/product-coverage/DEPENDENT_PRODUCT",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["promotable"] is False
    assert any(
        blocker["code"] == "dependent_relationship_rejected"
        for blocker in payload["readiness_blockers"]
    )


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
