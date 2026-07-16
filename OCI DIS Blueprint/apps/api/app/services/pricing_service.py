"""Governed OCI price synchronization, catalog approval, and SKU mapping services."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
from io import StringIO
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException
import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PriceCatalogSnapshot,
    PriceItem,
    PriceSource,
    PriceSyncJob,
    ServiceProductSkuMapping,
)
from app.schemas.pricing import (
    PriceCatalogSnapshotListResponse,
    PriceCatalogSnapshotResponse,
    PriceItemListResponse,
    PriceItemResponse,
    PriceSourceListResponse,
    PriceSourceResponse,
    PriceSyncJobListResponse,
    PriceSyncJobResponse,
    PriceSyncRequest,
    SkuMappingListResponse,
    SkuMappingPatchRequest,
    SkuMappingResponse,
    QuantityPresetResponse,
)
from app.services import storage_service
from app.services import audit_service


PRICE_FETCH_TIMEOUT_SECONDS = 45.0
PRICE_USER_AGENT = "OCI-DIS-Blueprint-Pricing/1.0"
ALLOWED_PUBLIC_PRICE_HOSTS = {"apexapps.oracle.com", "www.oracle.com", "oracle.com"}


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _optional_float(value: object) -> float | None:
    if value is None or (isinstance(value, str) and value.strip() in {"", "-"}):
        return None
    if not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _derive_price_type(metric_name: str) -> str:
    normalized = metric_name.lower()
    if "per hour" in normalized or normalized.endswith(" hour"):
        return "HOUR"
    if "per month" in normalized or normalized.endswith(" month"):
        return "MONTH"
    return "PER_ITEM"


def _price_localizations(item: dict[str, Any]) -> list[dict[str, Any]]:
    localizations = item.get("currencyCodeLocalizations")
    if isinstance(localizations, list):
        return [entry for entry in localizations if isinstance(entry, dict)]
    prices = item.get("prices")
    if isinstance(prices, list):
        return [entry for entry in prices if isinstance(entry, dict)]
    return []


def normalize_public_price_payload(payload: dict[str, Any], currency: str) -> list[dict[str, object]]:
    """Normalize Oracle's documented public product-price response into price tiers."""

    requested_currency = currency.upper()
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise ValueError("Oracle price response does not contain an items array")

    normalized: list[dict[str, object]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        part_number = str(raw_item.get("partNumber") or "").strip()
        display_name = str(raw_item.get("displayName") or "").strip()
        metric_name = str(raw_item.get("metricName") or "").strip()
        service_category = str(raw_item.get("serviceCategory") or "").strip()
        if not part_number or not display_name or not metric_name:
            continue
        for localization in _price_localizations(raw_item):
            localization_currency = str(localization.get("currencyCode") or "").upper()
            if localization_currency != requested_currency:
                continue
            tiers = localization.get("prices")
            if not isinstance(tiers, list):
                continue
            for tier in tiers:
                if not isinstance(tier, dict):
                    continue
                value = _optional_float(tier.get("value"))
                if value is None:
                    continue
                normalized.append(
                    {
                        "part_number": part_number,
                        "display_name": display_name,
                        "metric_name": metric_name,
                        "service_category": service_category,
                        "price_type": _derive_price_type(metric_name),
                        "currency": requested_currency,
                        "model": str(tier.get("model") or "PAY_AS_YOU_GO"),
                        "value": value,
                        "range_min": _optional_float(tier.get("rangeMin")),
                        "range_max": _optional_float(tier.get("rangeMax")),
                        "range_unit": str(tier.get("rangeUnit") or "").strip() or None,
                    }
                )
    normalized.sort(
        key=lambda row: (
            str(row["part_number"]),
            _optional_float(row["range_min"]) if row["range_min"] is not None else -1.0,
            _optional_float(row["range_max"]) if row["range_max"] is not None else float("inf"),
            _optional_float(row["value"]) or 0.0,
        )
    )
    if not normalized:
        raise ValueError(f"Oracle price response contains no {requested_currency} prices")
    return normalized


def _catalog_hash(items: list[dict[str, object]]) -> str:
    canonical = json.dumps(items, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


MAX_RATE_CARD_BYTES = 20 * 1024 * 1024


def _normalized_header(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _first_csv_value(row: dict[str, str], aliases: set[str]) -> str:
    for key, value in row.items():
        if _normalized_header(key) in aliases and value is not None:
            return value.strip()
    return ""


def normalize_rate_card_csv(contents: bytes, default_currency: str) -> list[dict[str, object]]:
    """Normalize an authorized Oracle rate-card CSV without retaining unneeded columns."""

    if not contents or len(contents) > MAX_RATE_CARD_BYTES:
        raise ValueError("Rate card must be a non-empty CSV no larger than 20 MB")
    try:
        decoded = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = contents.decode("latin-1")
    reader = csv.DictReader(StringIO(decoded))
    if not reader.fieldnames:
        raise ValueError("Rate card CSV has no header row")

    aliases = {
        "part_number": {"partnumber", "partno", "sku", "skunumber"},
        "display_name": {"displayname", "productname", "product", "description", "servicename"},
        "metric_name": {"metricname", "metric", "unit", "billingmetric", "unitofmeasure"},
        "service_category": {"servicecategory", "category", "service", "productcategory"},
        "currency": {"currency", "currencycode"},
        "model": {"model", "pricemodel", "pricingmodel"},
        "value": {"value", "price", "unitprice", "netunitprice", "paygprice", "rate"},
        "range_min": {"rangemin", "minimum", "min", "tiermin", "minimumquantity"},
        "range_max": {"rangemax", "maximum", "max", "tiermax", "maximumquantity"},
        "range_unit": {"rangeunit", "tierunit", "quantityunit"},
    }
    normalized: list[dict[str, object]] = []
    for row_number, row in enumerate(reader, start=2):
        part_number = _first_csv_value(row, aliases["part_number"])
        display_name = _first_csv_value(row, aliases["display_name"])
        metric_name = _first_csv_value(row, aliases["metric_name"])
        raw_value = _first_csv_value(row, aliases["value"])
        value = _optional_float(raw_value.replace(",", "").replace("$", ""))
        if not part_number and not display_name and not raw_value:
            continue
        if not part_number or not display_name or not metric_name or value is None:
            raise ValueError(f"Rate card row {row_number} is missing SKU, product, metric, or numeric price")
        currency = (_first_csv_value(row, aliases["currency"]) or default_currency).upper()
        normalized.append(
            {
                "part_number": part_number,
                "display_name": display_name,
                "metric_name": metric_name,
                "service_category": _first_csv_value(row, aliases["service_category"]) or "Contract rate card",
                "price_type": _derive_price_type(metric_name),
                "currency": currency,
                "model": _first_csv_value(row, aliases["model"]) or "CONTRACT_RATE",
                "value": value,
                "range_min": _optional_float(_first_csv_value(row, aliases["range_min"])),
                "range_max": _optional_float(_first_csv_value(row, aliases["range_max"])),
                "range_unit": _first_csv_value(row, aliases["range_unit"]) or None,
            }
        )
    if not normalized:
        raise ValueError("Rate card CSV contains no usable price rows")
    currencies = {str(item["currency"]) for item in normalized}
    if len(currencies) != 1:
        raise ValueError("A rate card snapshot must contain exactly one currency")
    normalized.sort(key=lambda item: (str(item["part_number"]), _as_sort_float(item["range_min"])))
    return normalized


def _as_sort_float(value: object) -> float:
    parsed = _optional_float(value)
    return parsed if parsed is not None else -1.0


def _price_signature(item: PriceItem | dict[str, object]) -> tuple[object, ...]:
    if isinstance(item, PriceItem):
        return (
            item.part_number,
            item.model,
            item.value,
            item.range_min,
            item.range_max,
            item.range_unit,
            item.metric_name,
        )
    return (
        item["part_number"],
        item["model"],
        item["value"],
        item["range_min"],
        item["range_max"],
        item["range_unit"],
        item["metric_name"],
    )


async def _fetch_public_prices(source: PriceSource, currency: str) -> dict[str, Any]:
    if not source.base_url:
        raise ValueError("Public price source has no URL")
    parsed = urlparse(source.base_url)
    if parsed.scheme != "https" or (parsed.hostname or "") not in ALLOWED_PUBLIC_PRICE_HOSTS:
        raise ValueError("Public price source is not allowlisted")
    async with httpx.AsyncClient(
        timeout=PRICE_FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": PRICE_USER_AGENT, "Accept": "application/json"},
    ) as client:
        response = await client.get(source.base_url, params={"currencyCode": currency.upper()})
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Oracle price source did not return a JSON object")
    return payload


def serialize_price_source(source: PriceSource) -> PriceSourceResponse:
    """Serialize a governed price source."""

    return PriceSourceResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        base_url=source.base_url,
        currency=source.currency,
        status=source.status,
        last_synced_at=source.last_synced_at,
        created_by=source.created_by,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def serialize_sync_job(job: PriceSyncJob) -> PriceSyncJobResponse:
    """Serialize a price synchronization job."""

    return PriceSyncJobResponse(
        id=job.id,
        source_id=job.source_id,
        requested_by=job.requested_by,
        currency=job.currency,
        status=job.status,
        started_at=job.started_at,
        completed_at=job.completed_at,
        item_count=job.item_count,
        changes_detected=job.changes_detected,
        snapshot_id=job.snapshot_id,
        error_details=job.error_details,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def serialize_price_snapshot(snapshot: PriceCatalogSnapshot) -> PriceCatalogSnapshotResponse:
    """Serialize immutable price catalog metadata."""

    return PriceCatalogSnapshotResponse(
        id=snapshot.id,
        source_id=snapshot.source_id,
        sync_job_id=snapshot.sync_job_id,
        currency=snapshot.currency,
        source_last_updated=snapshot.source_last_updated,
        retrieved_at=snapshot.retrieved_at,
        content_hash=snapshot.content_hash,
        item_count=snapshot.item_count,
        approval_status=snapshot.approval_status,
        approved_by=snapshot.approved_by,
        approved_at=snapshot.approved_at,
        metadata=snapshot.snapshot_metadata,
        created_at=snapshot.created_at,
    )


def serialize_price_item(item: PriceItem) -> PriceItemResponse:
    """Serialize one price item."""

    return PriceItemResponse(
        id=item.id,
        snapshot_id=item.snapshot_id,
        part_number=item.part_number,
        display_name=item.display_name,
        metric_name=item.metric_name,
        service_category=item.service_category,
        price_type=item.price_type,
        currency=item.currency,
        model=item.model,
        value=item.value,
        range_min=item.range_min,
        range_max=item.range_max,
        range_unit=item.range_unit,
    )


def serialize_sku_mapping(mapping: ServiceProductSkuMapping) -> SkuMappingResponse:
    """Serialize one SKU mapping rule."""

    return SkuMappingResponse(
        id=mapping.id,
        service_id=mapping.service_id,
        tool_key=mapping.tool_key,
        part_number=mapping.part_number,
        billing_metric_key=mapping.billing_metric_key,
        formula_key=mapping.formula_key,
        quantity_behavior=mapping.quantity_behavior,
        quantity_increment=mapping.quantity_increment,
        minimum_quantity=mapping.minimum_quantity,
        quantity_unit=mapping.quantity_unit,
        usage_basis=mapping.usage_basis,
        quote_rounding=mapping.quote_rounding,
        aggregation_window=mapping.aggregation_window,
        proration_policy=mapping.proration_policy,
        free_tier_scope=mapping.free_tier_scope,
        planning_envelope_increment=mapping.planning_envelope_increment,
        metering_policy=mapping.metering_policy,
        selection_policy=str(getattr(mapping, "selection_policy", None) or "required"),
        requires_explicit_quantity=mapping.requires_explicit_quantity,
        entry_guidance=mapping.entry_guidance,
        quantity_presets=[
            QuantityPresetResponse.model_validate(item)
            for item in mapping.quantity_presets
            if isinstance(item, dict)
        ],
        predicates=mapping.predicates,
        is_billable=mapping.is_billable,
        status=mapping.status,
        version=mapping.version,
        source_url=mapping.source_url,
        confidence=mapping.confidence,
        updated_at=mapping.updated_at,
    )


async def list_price_sources(db: AsyncSession) -> PriceSourceListResponse:
    """Return configured price sources."""

    rows = (await db.scalars(select(PriceSource).order_by(PriceSource.name))).all()
    return PriceSourceListResponse(sources=[serialize_price_source(row) for row in rows], total=len(rows))


async def import_rate_card(
    *,
    name: str,
    currency: str,
    filename: str,
    contents: bytes,
    actor_id: str,
    db: AsyncSession,
) -> PriceCatalogSnapshotResponse:
    """Persist an immutable, approved snapshot from an authorized contract CSV."""

    normalized = normalize_rate_card_csv(contents, currency.upper())
    normalized_currency = str(normalized[0]["currency"])
    if normalized_currency != currency.upper():
        raise HTTPException(
            status_code=422,
            detail={"detail": "Uploaded currency does not match the requested currency", "error_code": "RATE_CARD_CURRENCY_MISMATCH"},
        )
    source = await db.scalar(
        select(PriceSource).where(
            PriceSource.name == name.strip(),
            PriceSource.source_type == "manual_rate_card",
        )
    )
    if source is None:
        source = PriceSource(
            name=name.strip(),
            source_type="manual_rate_card",
            base_url=None,
            currency=normalized_currency,
            status="active",
            source_config={"import_format": "oracle_rate_card_csv_v1"},
            created_by=actor_id,
        )
        db.add(source)
        await db.flush()

    content_hash = _catalog_hash(normalized)
    existing = await db.scalar(
        select(PriceCatalogSnapshot).where(
            PriceCatalogSnapshot.source_id == source.id,
            PriceCatalogSnapshot.currency == normalized_currency,
            PriceCatalogSnapshot.content_hash == content_hash,
        )
    )
    if existing is not None:
        return serialize_price_snapshot(existing)

    now = _now()
    previous = await db.scalar(
        select(PriceCatalogSnapshot)
        .where(
            PriceCatalogSnapshot.source_id == source.id,
            PriceCatalogSnapshot.currency == normalized_currency,
            PriceCatalogSnapshot.approval_status == "approved",
        )
        .order_by(PriceCatalogSnapshot.created_at.desc())
    )
    snapshot = PriceCatalogSnapshot(
        source_id=source.id,
        sync_job_id=None,
        currency=normalized_currency,
        source_last_updated=None,
        retrieved_at=now,
        content_hash=content_hash,
        item_count=len(normalized),
        approval_status="approved",
        approved_by=actor_id,
        approved_at=now,
        snapshot_metadata={
            "source_type": source.source_type,
            "original_filename": Path(filename).name,
            "previous_snapshot_id": previous.id if previous else None,
            "adapter_version": "oracle_rate_card_csv_v1",
            "estimate_notice": "Contract rates are customer-provided inputs and are not an Oracle quote.",
        },
    )
    db.add(snapshot)
    await db.flush()
    stored_reference = storage_service.put_bytes(
        f"pricing/rate-cards/{snapshot.id}.csv",
        contents,
        content_type="text/csv",
        metadata={"snapshot-id": snapshot.id, "currency": normalized_currency},
    )
    snapshot.snapshot_metadata = {
        **snapshot.snapshot_metadata,
        "storage_reference": stored_reference,
    }
    db.add_all([PriceItem(snapshot_id=snapshot.id, **item) for item in normalized])
    source.currency = normalized_currency
    source.last_synced_at = now
    await audit_service.emit(
        event_type="contract_rate_card_imported",
        entity_type="price_catalog_snapshot",
        entity_id=snapshot.id,
        actor_id=actor_id,
        old_value={"snapshot_id": previous.id} if previous else None,
        new_value={
            "source_id": source.id,
            "currency": normalized_currency,
            "item_count": len(normalized),
            "content_hash": content_hash,
            "approval_status": snapshot.approval_status,
        },
        project_id=None,
        db=db,
    )
    await db.flush()
    await db.refresh(snapshot)
    return serialize_price_snapshot(snapshot)


async def create_sync_job(request: PriceSyncRequest, actor_id: str, db: AsyncSession) -> PriceSyncJobResponse:
    """Persist a pending price synchronization job."""

    source = await db.get(PriceSource, request.source_id) if request.source_id else await db.scalar(
        select(PriceSource)
        .where(PriceSource.status == "active", PriceSource.source_type == "public_list")
        .order_by(PriceSource.created_at)
    )
    if source is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Active price source not found", "error_code": "PRICE_SOURCE_NOT_FOUND"},
        )
    currency = request.currency.upper()
    job = PriceSyncJob(
        source_id=source.id,
        requested_by=actor_id,
        currency=currency,
        status="pending",
        item_count=0,
        changes_detected=0,
    )
    db.add(job)
    await db.flush()
    await audit_service.emit(
        event_type="price_sync_requested",
        entity_type="price_sync_job",
        entity_id=job.id,
        actor_id=actor_id,
        old_value=None,
        new_value={"source_id": source.id, "currency": currency, "status": job.status},
        project_id=None,
        correlation_id=job.id,
        db=db,
    )
    await db.refresh(job)
    return serialize_sync_job(job)


async def run_sync_job(job_id: str, db: AsyncSession) -> PriceSyncJob:
    """Fetch, normalize, snapshot, and diff one price source."""

    job = await db.get(PriceSyncJob, job_id)
    if job is None:
        raise ValueError("Price synchronization job not found")
    source = await db.get(PriceSource, job.source_id)
    if source is None:
        raise ValueError("Price source not found")
    if source.source_type != "public_list":
        raise ValueError(f"Unsupported automatic price source type: {source.source_type}")

    job.status = "running"
    job.started_at = _now()
    await db.flush()
    payload = await _fetch_public_prices(source, job.currency)
    normalized = normalize_public_price_payload(payload, job.currency)
    content_hash = _catalog_hash(normalized)
    existing = await db.scalar(
        select(PriceCatalogSnapshot).where(
            PriceCatalogSnapshot.source_id == source.id,
            PriceCatalogSnapshot.currency == job.currency,
            PriceCatalogSnapshot.content_hash == content_hash,
        )
    )
    now = _now()
    if existing is not None:
        job.status = "completed"
        job.completed_at = now
        job.item_count = existing.item_count
        job.changes_detected = 0
        job.snapshot_id = existing.id
        source.last_synced_at = now
        await db.flush()
        return job

    previous = await db.scalar(
        select(PriceCatalogSnapshot)
        .where(
            PriceCatalogSnapshot.source_id == source.id,
            PriceCatalogSnapshot.currency == job.currency,
            PriceCatalogSnapshot.approval_status == "approved",
        )
        .order_by(PriceCatalogSnapshot.created_at.desc())
    )
    previous_signatures: set[tuple[object, ...]] = set()
    if previous is not None:
        previous_items = (
            await db.scalars(select(PriceItem).where(PriceItem.snapshot_id == previous.id))
        ).all()
        previous_signatures = {_price_signature(item) for item in previous_items}
    new_signatures = {_price_signature(item) for item in normalized}
    changes_detected = len(previous_signatures.symmetric_difference(new_signatures)) if previous else 0
    approval_status = "approved" if previous is None else "pending_review"
    snapshot = PriceCatalogSnapshot(
        source_id=source.id,
        sync_job_id=job.id,
        currency=job.currency,
        source_last_updated=_parse_datetime(payload.get("lastUpdated")),
        retrieved_at=now,
        content_hash=content_hash,
        item_count=len(normalized),
        approval_status=approval_status,
        approved_by="system:first_catalog" if previous is None else None,
        approved_at=now if previous is None else None,
        snapshot_metadata={
            "source_type": source.source_type,
            "source_url": source.base_url,
            "changes_detected": changes_detected,
            "previous_snapshot_id": previous.id if previous else None,
            "adapter_version": "oracle_public_products_v1",
        },
    )
    db.add(snapshot)
    await db.flush()
    db.add_all([PriceItem(snapshot_id=snapshot.id, **item) for item in normalized])
    job.status = "completed"
    job.completed_at = now
    job.item_count = len(normalized)
    job.changes_detected = changes_detected
    job.snapshot_id = snapshot.id
    source.last_synced_at = now
    await audit_service.emit(
        event_type="price_sync_completed",
        entity_type="price_catalog_snapshot",
        entity_id=snapshot.id,
        actor_id=job.requested_by,
        old_value={"snapshot_id": previous.id} if previous else None,
        new_value={
            "currency": snapshot.currency,
            "item_count": snapshot.item_count,
            "changes_detected": changes_detected,
            "approval_status": approval_status,
            "content_hash": content_hash,
        },
        project_id=None,
        correlation_id=job.id,
        db=db,
    )
    await db.flush()
    return job


async def mark_sync_job_failed(job_id: str, error: dict[str, object], db: AsyncSession) -> None:
    """Persist terminal failure details for a price sync job."""

    job = await db.get(PriceSyncJob, job_id)
    if job is None:
        return
    job.status = "failed"
    job.completed_at = _now()
    job.error_details = error
    await db.flush()


async def list_sync_jobs(db: AsyncSession, limit: int = 20) -> PriceSyncJobListResponse:
    """Return recent price synchronization jobs."""

    rows = (
        await db.scalars(select(PriceSyncJob).order_by(PriceSyncJob.created_at.desc()).limit(min(max(limit, 1), 100)))
    ).all()
    return PriceSyncJobListResponse(jobs=[serialize_sync_job(row) for row in rows], total=len(rows))


async def get_sync_job(job_id: str, db: AsyncSession) -> PriceSyncJobResponse:
    """Return one price synchronization job."""

    job = await db.get(PriceSyncJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"detail": "Price sync job not found", "error_code": "PRICE_SYNC_JOB_NOT_FOUND"})
    return serialize_sync_job(job)


async def list_price_snapshots(db: AsyncSession, limit: int = 20) -> PriceCatalogSnapshotListResponse:
    """Return recent price catalog snapshots."""

    rows = (
        await db.scalars(
            select(PriceCatalogSnapshot)
            .order_by(PriceCatalogSnapshot.created_at.desc())
            .limit(min(max(limit, 1), 100))
        )
    ).all()
    return PriceCatalogSnapshotListResponse(
        snapshots=[serialize_price_snapshot(row) for row in rows],
        total=len(rows),
    )


async def approve_price_snapshot(snapshot_id: str, actor_id: str, db: AsyncSession) -> PriceCatalogSnapshotResponse:
    """Approve a reviewed price catalog snapshot for BOM generation."""

    snapshot = await db.get(PriceCatalogSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail={"detail": "Price snapshot not found", "error_code": "PRICE_SNAPSHOT_NOT_FOUND"})
    old_status = snapshot.approval_status
    snapshot.approval_status = "approved"
    snapshot.approved_by = actor_id
    snapshot.approved_at = _now()
    await audit_service.emit(
        event_type="price_snapshot_approved",
        entity_type="price_catalog_snapshot",
        entity_id=snapshot.id,
        actor_id=actor_id,
        old_value={"approval_status": old_status},
        new_value={"approval_status": snapshot.approval_status, "content_hash": snapshot.content_hash},
        project_id=None,
        db=db,
    )
    await db.flush()
    await db.refresh(snapshot)
    return serialize_price_snapshot(snapshot)


async def list_price_items(
    snapshot_id: str,
    db: AsyncSession,
    *,
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> PriceItemListResponse:
    """Return paginated normalized price items."""

    query = select(PriceItem).where(PriceItem.snapshot_id == snapshot_id)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                PriceItem.part_number.ilike(term),
                PriceItem.display_name.ilike(term),
                PriceItem.service_category.ilike(term),
            )
        )
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        await db.scalars(
            query.order_by(PriceItem.part_number, PriceItem.range_min)
            .offset((max(page, 1) - 1) * page_size)
            .limit(min(max(page_size, 1), 200))
        )
    ).all()
    return PriceItemListResponse(
        items=[serialize_price_item(row) for row in rows],
        total=total,
        page=max(page, 1),
        page_size=min(max(page_size, 1), 200),
    )


async def list_sku_mappings(db: AsyncSession) -> SkuMappingListResponse:
    """Return governed service-to-SKU mappings."""

    rows = (
        await db.scalars(
            select(ServiceProductSkuMapping).order_by(
                ServiceProductSkuMapping.tool_key,
                ServiceProductSkuMapping.billing_metric_key,
            )
        )
    ).all()
    return SkuMappingListResponse(
        mappings=[serialize_sku_mapping(row) for row in rows],
        total=len(rows),
        billable_count=sum(1 for row in rows if row.is_billable),
        non_billable_count=sum(1 for row in rows if not row.is_billable),
    )


async def patch_sku_mapping(
    mapping_id: str,
    request: SkuMappingPatchRequest,
    actor_id: str,
    db: AsyncSession,
) -> SkuMappingResponse:
    """Apply an audited Admin change to a SKU mapping."""

    mapping = await db.get(ServiceProductSkuMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail={"detail": "SKU mapping not found", "error_code": "SKU_MAPPING_NOT_FOUND"})
    old_value = serialize_sku_mapping(mapping).model_dump(mode="json")
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(mapping, field, value)
    await audit_service.emit(
        event_type="sku_mapping_updated",
        entity_type="service_product_sku_mapping",
        entity_id=mapping.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=request.model_dump(exclude_unset=True),
        project_id=None,
        db=db,
    )
    await db.flush()
    await db.refresh(mapping)
    return serialize_sku_mapping(mapping)
