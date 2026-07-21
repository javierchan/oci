"""Read-only API and service coverage for the captured OCI product taxonomy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import (
    CommercialDocumentSnapshot,
    CommercialMappingCandidate,
    CommercialSku,
    PriceCatalogSnapshot,
    PriceItem,
    PriceSource,
    ServiceProductSkuMapping,
    SkuCommercialTerm,
)
from app.services.product_catalog_service import product_key


HEADERS = {"X-Actor-Role": "Viewer"}


def _sku(
    part_number: str,
    display_name: str,
    hierarchy: list[str],
    *,
    service_category: str,
) -> CommercialSku:
    return CommercialSku(
        part_number=part_number,
        display_name=display_name,
        service_category=service_category,
        lifecycle_status="active",
        identity_metadata={"product_hierarchy": hierarchy},
    )


def _mapping(part_number: str) -> ServiceProductSkuMapping:
    return ServiceProductSkuMapping(
        service_id="TEST_PRODUCT",
        tool_key="TEST_PRODUCT",
        part_number=part_number,
        billing_metric_key="test_units",
        formula_key="metered_quantity",
        quantity_behavior="continuous",
        quantity_increment=1,
        minimum_quantity=0,
        quantity_unit="units",
        predicates={},
        is_billable=True,
        status="approved",
        version="test-1",
        confidence=1,
    )


async def _seed_product_catalog(test_engine: AsyncEngine) -> None:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        now = datetime.now(UTC)
        source = PriceSource(
            id="product-source",
            name="Oracle public pricing",
            source_type="public_list",
            currency="USD",
            status="active",
            created_by="test",
        )
        older_snapshot = PriceCatalogSnapshot(
            id="product-price-old",
            source_id=source.id,
            currency="USD",
            retrieved_at=now - timedelta(days=1),
            content_hash="old-product-prices",
            item_count=1,
            approval_status="approved",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
        snapshot = PriceCatalogSnapshot(
            id="product-price-current",
            source_id=source.id,
            currency="USD",
            retrieved_at=now,
            content_hash="current-product-prices",
            item_count=3,
            approval_status="approved",
            created_at=now,
            updated_at=now,
        )
        document = CommercialDocumentSnapshot(
            id="product-document",
            document_kind="price_list",
            source_name="Oracle Price List",
            original_filename="oracle.xlsx",
            storage_reference="s3://test/oracle.xlsx",
            content_hash="product-document-hash",
            parser_version="test-1",
            currency="USD",
            status="approved_evidence",
            record_count=4,
            retrieved_at=now,
            manifest={},
        )
        hierarchy = [
            "Section 1 - Universal Credits",
            "PaaS - Oracle Data Management Cloud Services: Oracle Exadata Exascale",
            "Oracle Data Management Cloud Services",
            "Oracle Exadata Exascale Database",
        ]
        exadata_a = _sku(
            "B100",
            "Exadata Exascale ECPU",
            hierarchy,
            service_category="Legacy category",
        )
        exadata_b = _sku(
            "B101",
            "Exadata Exascale Storage",
            hierarchy,
            service_category="Legacy category",
        )
        queue = _sku(
            "B200",
            "OCI Queue",
            ["Section 1", "Oracle Integration", "Oracle Integration Services", "OCI Queue"],
            service_category="Legacy integration",
        )
        fallback = _sku(
            "B300",
            "OCI Captured Fallback Product",
            [],
            service_category="Captured fallback category",
        )
        db.add_all([source, older_snapshot, snapshot, document, exadata_a, exadata_b, queue, fallback])
        await db.flush()

        db.add_all(
            [
                PriceItem(
                    snapshot_id=older_snapshot.id,
                    part_number="B100",
                    display_name=exadata_a.display_name,
                    metric_name="ECPU Per Hour",
                    service_category="Oracle Data Management Cloud Services",
                    price_type="HOUR",
                    currency="USD",
                    model="PAY_AS_YOU_GO",
                    value=99,
                ),
                PriceItem(
                    snapshot_id=snapshot.id,
                    part_number="B100",
                    display_name=exadata_a.display_name,
                    metric_name="ECPU Per Hour",
                    service_category="Oracle Data Management Cloud Services",
                    price_type="HOUR",
                    currency="USD",
                    model="PAY_AS_YOU_GO",
                    value=2.5,
                    range_min=0,
                    range_max=99,
                ),
                PriceItem(
                    snapshot_id=snapshot.id,
                    part_number="B100",
                    display_name=exadata_a.display_name,
                    metric_name="ECPU Per Hour",
                    service_category="Oracle Data Management Cloud Services",
                    price_type="HOUR",
                    currency="USD",
                    model="PAY_AS_YOU_GO",
                    value=1.5,
                    range_min=100,
                ),
                PriceItem(
                    snapshot_id=snapshot.id,
                    part_number="B101",
                    display_name=exadata_b.display_name,
                    metric_name="Gigabyte Per Month",
                    service_category="Oracle Data Management Cloud Services",
                    price_type="MONTH",
                    currency="USD",
                    model="PAY_AS_YOU_GO",
                    value=1.2,
                ),
            ]
        )
        terms = [
            SkuCommercialTerm(
                document_snapshot_id=document.id,
                commercial_sku_id=exadata_a.id,
                price_catalog_snapshot_id=snapshot.id,
                part_number="B100",
                service_name=exadata_a.display_name,
                service_category="Oracle Data Management Cloud Services",
                commercial_prices=[],
                currency="USD",
                metric_name="ECPU Per Hour",
                price_type="HOUR",
                availability=[],
                status="approved",
                source_sheet="Price List",
                source_row=10,
                source_cells={},
                extraction_metadata={},
            ),
            SkuCommercialTerm(
                document_snapshot_id=document.id,
                commercial_sku_id=exadata_b.id,
                price_catalog_snapshot_id=snapshot.id,
                part_number="B101",
                service_name=exadata_b.display_name,
                service_category="Oracle Data Management Cloud Services",
                commercial_prices=[],
                currency="USD",
                metric_name="Gigabyte Per Month",
                price_type="MONTH",
                availability=[],
                status="approved",
                source_sheet="Price List",
                source_row=11,
                source_cells={},
                extraction_metadata={},
            ),
        ]
        db.add_all(terms)
        await db.flush()
        db.add_all(
            [
                CommercialMappingCandidate(
                    document_snapshot_id=document.id,
                    commercial_sku_id=exadata_a.id,
                    term_id=terms[0].id,
                    part_number="B100",
                    classification="direct_metered",
                    proposed_mapping={},
                    confidence=1,
                    generator_version="test-1",
                    status="approved",
                    reasons=[],
                ),
                _mapping("B100"),
            ]
        )
        await db.commit()


def test_product_key_is_a_stable_uppercase_slug() -> None:
    assert product_key("Oracle Exadata Exascale Database") == (
        "ORACLE_EXADATA_EXASCALE_DATABASE"
    )
    assert product_key("  Análisis / AI  ") == "ANALISIS_AI"


@pytest.mark.asyncio
async def test_product_catalog_groups_taxonomy_and_keeps_unpriced_products(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_product_catalog(test_engine)

    response = await api_client.get(
        "/api/v1/pricing/product-catalog",
        headers=HEADERS,
        params={"search": "Exadata Exascale", "page": 1, "page_size": 50},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["products"] == [
        {
            "product_key": "ORACLE_EXADATA_EXASCALE_DATABASE",
            "name": "Oracle Exadata Exascale Database",
            "category": "Oracle Data Management Cloud Services",
            "sku_count": 2,
            "price_summary": {
                "currency": "USD",
                "min_payg_unit_price": 1.2,
                "max_payg_unit_price": 2.5,
            },
        }
    ]

    unpriced = await api_client.get(
        "/api/v1/pricing/product-catalog",
        headers=HEADERS,
        params={"search": "OCI Queue", "page": 1, "page_size": 1},
    )
    assert unpriced.status_code == 200, unpriced.text
    assert unpriced.json()["products"][0]["price_summary"] is None

    fallback = await api_client.get(
        "/api/v1/pricing/product-catalog",
        headers=HEADERS,
        params={"category": "fallback category"},
    )
    assert fallback.status_code == 200, fallback.text
    assert fallback.json()["products"][0]["name"] == "OCI Captured Fallback Product"


@pytest.mark.asyncio
async def test_product_catalog_paginates_products_and_sku_detail(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    await _seed_product_catalog(test_engine)

    catalog = await api_client.get(
        "/api/v1/pricing/product-catalog",
        headers=HEADERS,
        params={"page": 2, "page_size": 1},
    )
    assert catalog.status_code == 200, catalog.text
    assert catalog.json()["page"] == 2
    assert catalog.json()["page_size"] == 1
    assert catalog.json()["total"] == 3
    assert len(catalog.json()["products"]) == 1

    detail = await api_client.get(
        "/api/v1/pricing/product-catalog/ORACLE_EXADATA_EXASCALE_DATABASE",
        headers=HEADERS,
        params={"page": 1, "page_size": 1},
    )
    assert detail.status_code == 200, detail.text
    payload = detail.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert payload["total"] == 2
    assert payload["sku_count"] == 2
    assert len(payload["skus"]) == 1
    assert payload["skus"][0] == {
        "part_number": "B100",
        "display_name": "Exadata Exascale ECPU",
        "metric_name": "ECPU Per Hour",
        "price_type": "HOUR",
        "current_payg_unit_price": 2.5,
        "commercial_classification": "direct_metered",
        "is_bom_mapped": True,
    }

    second_page = await api_client.get(
        "/api/v1/pricing/product-catalog/oracle_exadata_exascale_database",
        headers=HEADERS,
        params={"page": 2, "page_size": 1},
    )
    assert second_page.status_code == 200, second_page.text
    assert second_page.json()["skus"][0]["part_number"] == "B101"
    assert second_page.json()["skus"][0]["is_bom_mapped"] is False


@pytest.mark.asyncio
async def test_product_catalog_requires_a_pricing_read_role(
    api_client: AsyncClient,
) -> None:
    response = await api_client.get(
        "/api/v1/pricing/product-catalog",
        headers={"X-Actor-Role": "Unknown"},
    )
    assert response.status_code == 403
