"""Read-only aggregation of the captured OCI commercial product taxonomy."""

from __future__ import annotations

import re
import unicodedata
from typing import cast

from fastapi import HTTPException
from sqlalchemy import Float, and_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.pricing import (
    CommercialMappingCandidate,
    CommercialSku,
    PriceCatalogSnapshot,
    PriceItem,
    ServiceProductSkuMapping,
    SkuCommercialTerm,
)
from app.schemas.pricing import (
    OciProductCatalogDetailResponse,
    OciProductCatalogListResponse,
    OciProductCatalogRowResponse,
    OciProductPriceSummaryResponse,
    OciProductSkuResponse,
)


PAYG_MODEL = "PAY_AS_YOU_GO"
USD_CURRENCY = "USD"


def product_key(name: str) -> str:
    """Return the deterministic uppercase slug used by product detail routes."""

    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Z0-9]+", "_", ascii_name.upper()).strip("_")


def _hierarchy_value(
    db: AsyncSession,
    *,
    offset_from_end: int,
) -> ColumnElement[str | None]:
    """Build a portable JSON expression for a hierarchy value counted from the end."""

    bind = db.get_bind()
    if bind.dialect.name == "sqlite":
        path = f"$.product_hierarchy[#-{offset_from_end}]"
        return cast(ColumnElement[str | None], func.json_extract(CommercialSku.identity_metadata, path))
    return cast(
        ColumnElement[str | None],
        CommercialSku.identity_metadata["product_hierarchy"][-offset_from_end].as_string(),
    )


def _product_expressions(
    db: AsyncSession,
) -> tuple[ColumnElement[str], ColumnElement[str | None]]:
    """Return product/category expressions without assuming a fixed hierarchy depth."""

    hierarchy_name = _hierarchy_value(db, offset_from_end=1)
    hierarchy_category = _hierarchy_value(db, offset_from_end=2)
    name = cast(
        ColumnElement[str],
        func.coalesce(func.nullif(hierarchy_name, ""), CommercialSku.display_name),
    )
    category = cast(
        ColumnElement[str | None],
        func.coalesce(func.nullif(hierarchy_category, ""), CommercialSku.service_category),
    )
    return name, category


def _like_pattern(value: str) -> str:
    escaped = value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def _latest_approved_usd_snapshot(db: AsyncSession) -> PriceCatalogSnapshot | None:
    return await db.scalar(
        select(PriceCatalogSnapshot)
        .where(
            PriceCatalogSnapshot.currency == USD_CURRENCY,
            PriceCatalogSnapshot.approval_status == "approved",
        )
        .order_by(PriceCatalogSnapshot.created_at.desc(), PriceCatalogSnapshot.id.desc())
        .limit(1)
    )


def _price_summary(
    snapshot: PriceCatalogSnapshot | None,
    minimum: float | None,
    maximum: float | None,
) -> OciProductPriceSummaryResponse | None:
    if snapshot is None or minimum is None or maximum is None:
        return None
    return OciProductPriceSummaryResponse(
        currency=snapshot.currency,
        min_payg_unit_price=float(minimum),
        max_payg_unit_price=float(maximum),
    )


async def list_products(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
    category: str | None = None,
) -> OciProductCatalogListResponse:
    """Return one bounded page grouped by captured product identity."""

    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    name_expression, category_expression = _product_expressions(db)
    snapshot = await _latest_approved_usd_snapshot(db)

    if snapshot is None:
        minimum_price = literal(None, type_=Float).label("minimum_price")
        maximum_price = literal(None, type_=Float).label("maximum_price")
        grouped = select(
            name_expression.label("name"),
            func.min(category_expression).label("category"),
            func.count(func.distinct(CommercialSku.id)).label("sku_count"),
            minimum_price,
            maximum_price,
        ).select_from(CommercialSku)
    else:
        grouped = (
            select(
                name_expression.label("name"),
                func.min(category_expression).label("category"),
                func.count(func.distinct(CommercialSku.id)).label("sku_count"),
                func.min(PriceItem.value).label("minimum_price"),
                func.max(PriceItem.value).label("maximum_price"),
            )
            .select_from(CommercialSku)
            .outerjoin(
                PriceItem,
                and_(
                    PriceItem.part_number == CommercialSku.part_number,
                    PriceItem.snapshot_id == snapshot.id,
                    PriceItem.model == PAYG_MODEL,
                ),
            )
        )

    filters: list[ColumnElement[bool]] = []
    if search and search.strip():
        pattern = _like_pattern(search)
        filters.append(
            or_(
                name_expression.ilike(pattern, escape="\\"),
                category_expression.ilike(pattern, escape="\\"),
            )
        )
    if category and category.strip():
        filters.append(category_expression.ilike(_like_pattern(category), escape="\\"))
    if filters:
        grouped = grouped.where(*filters)

    grouped = grouped.group_by(name_expression)
    total = int(await db.scalar(select(func.count()).select_from(grouped.subquery())) or 0)
    rows = (
        await db.execute(
            grouped.order_by(func.min(category_expression), name_expression)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    products = [
        OciProductCatalogRowResponse(
            product_key=product_key(str(row.name)),
            name=str(row.name),
            category=str(row.category) if row.category is not None else None,
            sku_count=int(row.sku_count),
            price_summary=_price_summary(
                snapshot,
                float(row.minimum_price) if row.minimum_price is not None else None,
                float(row.maximum_price) if row.maximum_price is not None else None,
            ),
        )
        for row in rows
    ]
    return OciProductCatalogListResponse(
        products=products,
        page=page,
        page_size=page_size,
        total=total,
    )


async def _resolve_product(
    db: AsyncSession,
    requested_key: str,
) -> tuple[str, str | None]:
    name_expression, category_expression = _product_expressions(db)
    rows = (
        await db.execute(
            select(
                name_expression.label("name"),
                func.min(category_expression).label("category"),
            )
            .select_from(CommercialSku)
            .group_by(name_expression)
            .order_by(name_expression)
        )
    ).all()
    normalized_key = product_key(requested_key)
    matches = [row for row in rows if product_key(str(row.name)) == normalized_key]
    if not matches:
        raise HTTPException(
            status_code=404,
            detail={"detail": "OCI product not found", "error_code": "OCI_PRODUCT_NOT_FOUND"},
        )
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The product key is not unique in the captured taxonomy",
                "error_code": "OCI_PRODUCT_KEY_AMBIGUOUS",
            },
        )
    match = matches[0]
    return str(match.name), str(match.category) if match.category is not None else None


async def _product_price_summary(
    db: AsyncSession,
    *,
    name: str,
    snapshot: PriceCatalogSnapshot | None,
) -> OciProductPriceSummaryResponse | None:
    if snapshot is None:
        return None
    name_expression, _ = _product_expressions(db)
    row = (
        await db.execute(
            select(
                func.min(PriceItem.value).label("minimum_price"),
                func.max(PriceItem.value).label("maximum_price"),
            )
            .select_from(CommercialSku)
            .outerjoin(
                PriceItem,
                and_(
                    PriceItem.part_number == CommercialSku.part_number,
                    PriceItem.snapshot_id == snapshot.id,
                    PriceItem.model == PAYG_MODEL,
                ),
            )
            .where(name_expression == name)
        )
    ).one()
    return _price_summary(
        snapshot,
        float(row.minimum_price) if row.minimum_price is not None else None,
        float(row.maximum_price) if row.maximum_price is not None else None,
    )


async def product_detail(
    db: AsyncSession,
    *,
    requested_key: str,
    page: int = 1,
    page_size: int = 50,
) -> OciProductCatalogDetailResponse:
    """Return one product with only the requested page of SKU evidence."""

    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    name, category = await _resolve_product(db, requested_key)
    name_expression, _ = _product_expressions(db)
    product_filter = name_expression == name
    total = int(
        await db.scalar(
            select(func.count()).select_from(CommercialSku).where(product_filter)
        )
        or 0
    )
    sku_rows = (
        await db.execute(
            select(
                CommercialSku.id.label("sku_id"),
                CommercialSku.part_number,
                CommercialSku.display_name,
            )
            .where(product_filter)
            .order_by(CommercialSku.part_number, CommercialSku.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    sku_ids = [str(row.sku_id) for row in sku_rows]
    part_numbers = [str(row.part_number) for row in sku_rows]

    latest_terms: dict[str, tuple[str | None, str | None]] = {}
    latest_classifications: dict[str, str] = {}
    mapped_parts: set[str] = set()
    current_prices: dict[str, float] = {}
    snapshot = await _latest_approved_usd_snapshot(db)

    if sku_ids:
        term_ranked = (
            select(
                SkuCommercialTerm.commercial_sku_id.label("sku_id"),
                SkuCommercialTerm.metric_name,
                SkuCommercialTerm.price_type,
                func.row_number()
                .over(
                    partition_by=SkuCommercialTerm.commercial_sku_id,
                    order_by=(SkuCommercialTerm.created_at.desc(), SkuCommercialTerm.id.desc()),
                )
                .label("row_number"),
            )
            .where(SkuCommercialTerm.commercial_sku_id.in_(sku_ids))
            .subquery()
        )
        term_rows = (
            await db.execute(
                select(
                    term_ranked.c.sku_id,
                    term_ranked.c.metric_name,
                    term_ranked.c.price_type,
                ).where(term_ranked.c.row_number == 1)
            )
        ).all()
        latest_terms = {
            str(row.sku_id): (
                str(row.metric_name) if row.metric_name is not None else None,
                str(row.price_type) if row.price_type is not None else None,
            )
            for row in term_rows
        }

        candidate_ranked = (
            select(
                CommercialMappingCandidate.commercial_sku_id.label("sku_id"),
                CommercialMappingCandidate.classification,
                func.row_number()
                .over(
                    partition_by=CommercialMappingCandidate.commercial_sku_id,
                    order_by=(
                        CommercialMappingCandidate.created_at.desc(),
                        CommercialMappingCandidate.id.desc(),
                    ),
                )
                .label("row_number"),
            )
            .where(CommercialMappingCandidate.commercial_sku_id.in_(sku_ids))
            .subquery()
        )
        classification_rows = (
            await db.execute(
                select(
                    candidate_ranked.c.sku_id,
                    candidate_ranked.c.classification,
                ).where(candidate_ranked.c.row_number == 1)
            )
        ).all()
        latest_classifications = {
            str(row.sku_id): str(row.classification) for row in classification_rows
        }

    if part_numbers:
        mapped_parts = set(
            str(value)
            for value in (
                await db.scalars(
                    select(ServiceProductSkuMapping.part_number)
                    .where(ServiceProductSkuMapping.part_number.in_(part_numbers))
                    .distinct()
                )
            ).all()
            if value is not None
        )
        if snapshot is not None:
            price_ranked = (
                select(
                    PriceItem.part_number,
                    PriceItem.value,
                    func.row_number()
                    .over(
                        partition_by=PriceItem.part_number,
                        order_by=(
                            func.coalesce(PriceItem.range_min, 0),
                            PriceItem.range_max,
                            PriceItem.id,
                        ),
                    )
                    .label("row_number"),
                )
                .where(
                    PriceItem.snapshot_id == snapshot.id,
                    PriceItem.model == PAYG_MODEL,
                    PriceItem.part_number.in_(part_numbers),
                )
                .subquery()
            )
            price_rows = (
                await db.execute(
                    select(price_ranked.c.part_number, price_ranked.c.value).where(
                        price_ranked.c.row_number == 1
                    )
                )
            ).all()
            current_prices = {
                str(row.part_number): float(row.value) for row in price_rows
            }

    detail_skus = []
    for row in sku_rows:
        sku_id = str(row.sku_id)
        part_number = str(row.part_number)
        metric_name, price_type = latest_terms.get(sku_id, (None, None))
        detail_skus.append(
            OciProductSkuResponse(
                part_number=part_number,
                display_name=str(row.display_name),
                metric_name=metric_name,
                price_type=price_type,
                current_payg_unit_price=current_prices.get(part_number),
                commercial_classification=latest_classifications.get(sku_id),
                is_bom_mapped=part_number in mapped_parts,
            )
        )

    return OciProductCatalogDetailResponse(
        product_key=product_key(name),
        name=name,
        category=category,
        sku_count=total,
        price_summary=await _product_price_summary(db, name=name, snapshot=snapshot),
        skus=detail_skus,
        page=page,
        page_size=page_size,
        total=total,
    )
