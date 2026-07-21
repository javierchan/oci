"""Seed an isolated governed commercial release for browser quality gates only.

This script is never called by application startup or production deployment. It
requires an explicit opt-in so a synthetic release cannot be created by accident.
"""

from __future__ import annotations
# ruff: noqa: E402

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys

from sqlalchemy import select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.db import AsyncSessionLocal
from app.models import (
    CommercialDocumentSnapshot,
    CommercialEvidenceReference,
    CommercialRelease,
    CommercialRuleFamily,
    CommercialSku,
    GovernanceChangeSet,
    PriceCatalogSnapshot,
    PriceItem,
    PriceSource,
    ServiceProductSkuMapping,
    SkuCommercialConstraint,
    SkuCommercialTerm,
)
from app.schemas.pricing import PriceSyncRequest
from app.services import pricing_service


ACTOR_ID = "browser-quality-fixture"
FIXTURE_VERSION = "browser-quality-1.0.0"


def _digest(values: object) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _sync_public_catalog() -> PriceCatalogSnapshot:
    async with AsyncSessionLocal() as db:
        source = await db.scalar(
            select(PriceSource)
            .where(
                PriceSource.status == "active",
                PriceSource.source_type == "public_list",
            )
            .order_by(PriceSource.created_at)
        )
        if source is None:
            raise RuntimeError("Browser fixture requires an active public price source")
        async with db.begin_nested():
            response = await pricing_service.create_sync_job(
                PriceSyncRequest(source_id=source.id, currency="USD"),
                ACTOR_ID,
                db,
            )
        await db.commit()

    async with AsyncSessionLocal() as db:
        async with db.begin():
            job = await pricing_service.run_sync_job(
                response.id,
                db,
                trigger_type="browser_quality_fixture",
            )
        if job.snapshot_id is None:
            raise RuntimeError("Browser fixture price synchronization produced no snapshot")
        snapshot_id = job.snapshot_id

    async with AsyncSessionLocal() as db:
        async with db.begin():
            await pricing_service.approve_price_snapshot(snapshot_id, ACTOR_ID, db)
        snapshot = await db.get(PriceCatalogSnapshot, snapshot_id)
        if snapshot is None:
            raise RuntimeError("Browser fixture approved price snapshot was not found")
        return snapshot


async def _seed_release(snapshot_id: str) -> CommercialRelease:
    async with AsyncSessionLocal() as db:
        snapshot = await db.get(PriceCatalogSnapshot, snapshot_id)
        if snapshot is None:
            raise RuntimeError("Browser fixture price snapshot was not found")
        existing = await db.scalar(
            select(CommercialRelease).where(
                CommercialRelease.price_catalog_snapshot_id == snapshot.id,
                CommercialRelease.version == f"{FIXTURE_VERSION}-{snapshot.content_hash[:12]}",
            )
        )
        if existing is not None:
            return existing

        mappings = list(
            (
                await db.scalars(
                    select(ServiceProductSkuMapping)
                    .where(
                        ServiceProductSkuMapping.status == "approved",
                        ServiceProductSkuMapping.is_billable.is_(True),
                        ServiceProductSkuMapping.part_number.is_not(None),
                    )
                    .order_by(
                        ServiceProductSkuMapping.part_number,
                        ServiceProductSkuMapping.service_id,
                        ServiceProductSkuMapping.billing_metric_key,
                    )
                )
            ).all()
        )
        if not mappings:
            raise RuntimeError("Browser fixture requires approved billable SKU mappings")
        prices = list(
            (
                await db.scalars(
                    select(PriceItem)
                    .where(PriceItem.snapshot_id == snapshot.id)
                    .order_by(PriceItem.part_number, PriceItem.range_min.nullsfirst())
                )
            ).all()
        )
        prices_by_part: dict[str, list[PriceItem]] = defaultdict(list)
        for price in prices:
            prices_by_part[price.part_number].append(price)
        mappings_by_part: dict[str, list[ServiceProductSkuMapping]] = defaultdict(list)
        for mapping in mappings:
            if mapping.part_number:
                mappings_by_part[mapping.part_number].append(mapping)
        missing_prices = sorted(set(mappings_by_part) - set(prices_by_part))
        if missing_prices:
            raise RuntimeError(
                "Browser fixture mapped SKUs are absent from the official price snapshot: "
                + ", ".join(missing_prices)
            )

        now = datetime.now(UTC)
        document = CommercialDocumentSnapshot(
            document_kind="browser_quality_fixture",
            source_name="Browser quality commercial evidence",
            source_url="test://browser-quality-commercial-evidence",
            original_filename="browser-quality-commercial-evidence.json",
            storage_reference="test://browser-quality-commercial-evidence",
            content_hash=_digest(
                {
                    "snapshot": snapshot.content_hash,
                    "parts": sorted(mappings_by_part),
                    "version": FIXTURE_VERSION,
                }
            ),
            parser_version=FIXTURE_VERSION,
            currency=snapshot.currency,
            status="approved_evidence",
            record_count=len(mappings_by_part),
            retrieved_at=now,
            manifest={
                "fixture_scope": "browser_quality_only",
                "price_snapshot_id": snapshot.id,
            },
            approved_by=ACTOR_ID,
            approved_at=now,
        )
        db.add(document)
        await db.flush()

        term_ids_by_part: dict[str, str] = {}
        rule_ids_by_part: dict[str, str] = {}
        mapping_ids_by_part: dict[str, list[str]] = {}
        for row_number, part_number in enumerate(sorted(mappings_by_part), start=1):
            part_mappings = mappings_by_part[part_number]
            mapping = part_mappings[0]
            part_prices = prices_by_part[part_number]
            price = part_prices[0]
            sku = await db.scalar(
                select(CommercialSku).where(CommercialSku.part_number == part_number)
            )
            if sku is None:
                sku = CommercialSku(
                    part_number=part_number,
                    display_name=price.display_name,
                    service_category=price.service_category,
                    lifecycle_status="active",
                    identity_metadata={"fixture_scope": "browser_quality_only"},
                )
                db.add(sku)
                await db.flush()
            family_key = f"browser::{part_number.casefold()}"
            term = SkuCommercialTerm(
                document_snapshot_id=document.id,
                commercial_sku_id=sku.id,
                price_catalog_snapshot_id=snapshot.id,
                part_number=part_number,
                service_name=price.display_name,
                service_category=price.service_category,
                commercial_prices=[
                    {
                        "model": item.model,
                        "value": item.value,
                        "range_min": item.range_min,
                        "range_max": item.range_max,
                    }
                    for item in part_prices
                ],
                currency=snapshot.currency,
                metric_name=price.metric_name,
                price_type=price.price_type,
                allow_decimal_quantity=any(
                    item.quantity_behavior == "continuous" for item in part_mappings
                ),
                availability=[],
                disposition="direct_metered",
                family_key=family_key,
                status="approved",
                confidence=1,
                source_sheet="Browser Quality Fixture",
                source_row=row_number,
                source_cells={},
                extraction_metadata={"fixture_scope": "browser_quality_only"},
            )
            rule = CommercialRuleFamily(
                family_key=family_key,
                version=FIXTURE_VERSION,
                formula_key=mapping.formula_key,
                metric_pattern=mapping.billing_metric_key,
                price_types=sorted({item.price_type for item in part_prices}),
                quantity_behavior=mapping.quantity_behavior,
                quantity_increment=Decimal(str(mapping.quantity_increment)),
                minimum_quantity=Decimal(str(mapping.minimum_quantity)),
                aggregation_window=mapping.aggregation_window,
                proration_policy=mapping.proration_policy,
                quote_rounding=mapping.quote_rounding,
                generator_version=FIXTURE_VERSION,
                status="approved",
                fixture_status="passed",
                evidence={"document_snapshot_id": document.id},
                approved_by=ACTOR_ID,
                approved_at=now,
            )
            db.add_all([term, rule])
            await db.flush()
            term_ids_by_part[part_number] = term.id
            rule_ids_by_part[part_number] = rule.id
            mapping_ids_by_part[part_number] = [item.id for item in part_mappings]
            db.add_all(
                [
                    SkuCommercialConstraint(
                        term_id=term.id,
                        constraint_type="purchase_increment",
                        scope="commercial_quantity",
                        numeric_value=Decimal(str(mapping.quantity_increment)),
                        unit=mapping.quantity_unit,
                        behavior="round_up",
                        status="approved",
                        source_cell=f"A{row_number}",
                        evidence_metadata={"fixture_scope": "browser_quality_only"},
                    ),
                    CommercialEvidenceReference(
                        entity_type="sku_commercial_term",
                        entity_id=term.id,
                        source_kind="browser_quality_fixture",
                        document_snapshot_id=document.id,
                        source_sheet="Browser Quality Fixture",
                        source_row=row_number,
                        source_cell=f"A{row_number}",
                        evidence_metadata={"fixture_scope": "browser_quality_only"},
                    ),
                ]
            )

        change_set = await db.scalar(
            select(GovernanceChangeSet)
            .where(GovernanceChangeSet.price_snapshot_id == snapshot.id)
            .order_by(GovernanceChangeSet.created_at.desc())
        )
        release = CommercialRelease(
            version=f"{FIXTURE_VERSION}-{snapshot.content_hash[:12]}",
            price_catalog_snapshot_id=snapshot.id,
            document_snapshot_id=document.id,
            governance_change_set_id=change_set.id if change_set else None,
            mapping_set_hash=_digest(mapping_ids_by_part),
            rule_family_set_hash=_digest(rule_ids_by_part),
            evidence_hash=document.content_hash,
            status="approved",
            validation_status="passed",
            open_exception_count=0,
            release_metadata={
                "fixture_scope": "browser_quality_only",
                "part_numbers": sorted(mappings_by_part),
                "mapping_ids_by_part": mapping_ids_by_part,
                "term_ids_by_part": term_ids_by_part,
                "rule_ids_by_part": rule_ids_by_part,
            },
            approved_by=ACTOR_ID,
            approved_at=now,
        )
        db.add(release)
        await db.commit()
        await db.refresh(release)
        return release


async def _run() -> None:
    if os.getenv("ALLOW_BROWSER_COMMERCIAL_FIXTURE") != "1":
        raise RuntimeError(
            "Refusing to seed browser commercial data without "
            "ALLOW_BROWSER_COMMERCIAL_FIXTURE=1"
        )
    snapshot = await _sync_public_catalog()
    release = await _seed_release(snapshot.id)
    print(
        json.dumps(
            {
                "fixture_scope": "browser_quality_only",
                "price_snapshot_id": snapshot.id,
                "commercial_release_id": release.id,
                "commercial_release_version": release.version,
            },
            indent=2,
        )
    )


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
