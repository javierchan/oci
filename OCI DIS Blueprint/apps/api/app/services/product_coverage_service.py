"""Governed proposal and approval flow for OCI product BOM coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import re
from typing import Any, TypedDict, cast

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CommercialDocumentSnapshot,
    CommercialException,
    CommercialMappingCandidate,
    CommercialRelease,
    CommercialRuleFamily,
    ProductCoverageCandidate,
    ServiceCapabilityProfile,
    ServiceCommercialPolicy,
    ServiceProductSkuMapping,
    SkuCommercialRelationship,
    SkuCommercialTerm,
)
from app.schemas.pricing import (
    OciProductCatalogRowResponse,
    ProductCoverageBlockerResponse,
    ProductCoverageDetailResponse,
    ProductCoverageGenerationResponse,
    ProductCoverageListResponse,
    ProductCoverageRowResponse,
)
from app.services import audit_service, product_catalog_service
from app.services.commercial_catalog_service import (
    GENERATOR_VERSION as COMMERCIAL_GENERATOR_VERSION,
    catalog_finalization_blockers,
)


GENERATOR_VERSION = "product-coverage-factory-1.0.0"
SUPPORTED_CLASSIFICATIONS = {"direct_metered", "included_non_billable"}
PROFILE_SERVICE_ID_MAX = 50
PROFILE_NAME_MAX = 255
PROFILE_CATEGORY_MAX = 100
MAPPING_UNIT_MAX = 100


class ProductCoverageProposal(TypedDict):
    """Typed proposal payload before it is persisted as governed JSON evidence."""

    product_name: str
    category: str | None
    proposed_service_id: str
    proposed_profile: dict[str, object]
    proposed_policy: dict[str, object]
    proposed_mappings: list[dict[str, object]]
    readiness_status: str
    readiness_blockers: list[dict[str, object]]
    source_document_snapshot_id: str | None


def _now() -> datetime:
    return datetime.now(UTC)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _string_dict(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if isinstance(item, str)}


def _json_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def _object_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _object_dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _metric_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "governed_units"


def _decimal_float(value: Decimal | float | int) -> float:
    return float(value)


def _blocker(part_number: str | None, code: str, detail: str) -> dict[str, object]:
    return {"part_number": part_number, "code": code, "detail": detail}


async def _active_release(db: AsyncSession) -> CommercialRelease | None:
    return await db.scalar(
        select(CommercialRelease)
        .where(
            CommercialRelease.status == "approved",
            CommercialRelease.validation_status == "passed",
            CommercialRelease.open_exception_count == 0,
        )
        .order_by(CommercialRelease.approved_at.desc(), CommercialRelease.created_at.desc())
        .limit(1)
    )


async def _source_document(
    db: AsyncSession, release: CommercialRelease | None
) -> CommercialDocumentSnapshot | None:
    if release is not None:
        return await db.get(CommercialDocumentSnapshot, release.document_snapshot_id)
    return await db.scalar(
        select(CommercialDocumentSnapshot)
        .where(CommercialDocumentSnapshot.status == "approved_evidence")
        .order_by(CommercialDocumentSnapshot.approved_at.desc(), CommercialDocumentSnapshot.created_at.desc())
        .limit(1)
    )


async def _all_products(db: AsyncSession) -> list[OciProductCatalogRowResponse]:
    products: list[OciProductCatalogRowResponse] = []
    page = 1
    while True:
        result = await product_catalog_service.list_products(db, page=page, page_size=200)
        products.extend(result.products)
        if len(products) >= result.total:
            return products
        page += 1


def _candidate_row(candidate: ProductCoverageCandidate) -> ProductCoverageRowResponse:
    return ProductCoverageRowResponse(
        product_key=candidate.product_key,
        product_name=candidate.product_name,
        category=candidate.category,
        sku_count=_json_int(candidate.proposed_policy.get("sku_count", 0)),
        mapping_count=len(candidate.proposed_mappings),
        readiness_status=candidate.readiness_status,
        status=candidate.status,
        promotable=candidate.readiness_status == "ready" and candidate.status == "pending_review",
        blocker_count=len(candidate.readiness_blockers),
        generator_version=candidate.generator_version,
    )


def _candidate_detail(candidate: ProductCoverageCandidate) -> ProductCoverageDetailResponse:
    row = _candidate_row(candidate)
    return ProductCoverageDetailResponse(
        **row.model_dump(),
        proposed_service_id=candidate.proposed_service_id,
        proposed_profile=candidate.proposed_profile,
        proposed_policy=candidate.proposed_policy,
        proposed_mappings=[dict(item) for item in candidate.proposed_mappings if isinstance(item, dict)],
        readiness_blockers=[
            ProductCoverageBlockerResponse.model_validate(item)
            for item in candidate.readiness_blockers
            if isinstance(item, dict)
        ],
        source_document_snapshot_id=candidate.source_document_snapshot_id,
        review_rationale=candidate.review_rationale,
        reviewed_by=candidate.reviewed_by,
        reviewed_at=candidate.reviewed_at,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


async def _proposal_for_product(
    db: AsyncSession,
    *,
    product_key: str,
    release: CommercialRelease | None,
    document: CommercialDocumentSnapshot | None,
    existing_profiles: dict[str, ServiceCapabilityProfile],
) -> ProductCoverageProposal:
    name, category, skus = await product_catalog_service.product_sku_records(
        db, requested_key=product_key
    )
    sku_ids = [sku.id for sku in skus]
    part_numbers = [sku.part_number for sku in skus]
    release_metadata = release.release_metadata if release else {}
    release_parts = set(_string_list(release_metadata.get("part_numbers")))
    release_term_ids = _string_dict(release_metadata.get("term_ids_by_part"))
    release_rule_ids = _string_dict(release_metadata.get("rule_ids_by_part"))

    candidates = list(
        (
            await db.scalars(
                select(CommercialMappingCandidate)
                .where(CommercialMappingCandidate.commercial_sku_id.in_(sku_ids))
                .order_by(CommercialMappingCandidate.created_at.desc())
            )
        ).all()
    ) if sku_ids else []
    candidate_by_sku: dict[str, CommercialMappingCandidate] = {}
    for candidate in candidates:
        if release is not None and candidate.document_snapshot_id != release.document_snapshot_id:
            continue
        candidate_by_sku.setdefault(candidate.commercial_sku_id, candidate)

    term_ids = {
        *(candidate.term_id for candidate in candidate_by_sku.values() if candidate.term_id),
        *release_term_ids.values(),
    }
    terms = list((await db.scalars(select(SkuCommercialTerm).where(SkuCommercialTerm.id.in_(term_ids)))).all()) if term_ids else []
    terms_by_id = {term.id: term for term in terms}
    rule_ids = {
        *(
            str(rule_id)
            for candidate in candidate_by_sku.values()
            if isinstance((rule_id := candidate.proposed_mapping.get("commercial_rule_family_id")), str)
        ),
        *release_rule_ids.values(),
    }
    rules = list((await db.scalars(select(CommercialRuleFamily).where(CommercialRuleFamily.id.in_(rule_ids)))).all()) if rule_ids else []
    rules_by_id = {rule.id: rule for rule in rules}

    open_exceptions = list(
        (
            await db.scalars(
                select(CommercialException).where(
                    CommercialException.part_number.in_(part_numbers),
                    CommercialException.status == "open",
                )
            )
        ).all()
    ) if part_numbers else []
    exception_codes: dict[str, set[str]] = {}
    for commercial_exception in open_exceptions:
        if commercial_exception.part_number:
            exception_codes.setdefault(commercial_exception.part_number, set()).add(
                commercial_exception.exception_code
            )
    unresolved = list(
        (
            await db.scalars(
                select(SkuCommercialRelationship).where(
                    SkuCommercialRelationship.part_number.in_(part_numbers),
                    SkuCommercialRelationship.resolution_status.in_(("unresolved", "accepted_risk")),
                )
            )
        ).all()
    ) if part_numbers else []
    relationship_statuses: dict[str, set[str]] = {}
    for relationship in unresolved:
        if relationship.part_number:
            relationship_statuses.setdefault(relationship.part_number, set()).add(
                relationship.resolution_status
            )

    proposed_service_id = product_key
    blockers: list[dict[str, object]] = []
    existing_profile = existing_profiles.get(proposed_service_id)
    if len(proposed_service_id) > PROFILE_SERVICE_ID_MAX:
        blockers.append(_blocker(None, "service_id_too_long", f"Product key exceeds the {PROFILE_SERVICE_ID_MAX}-character service ID contract."))
    if len(name) > PROFILE_NAME_MAX:
        blockers.append(_blocker(None, "product_name_too_long", f"Product name exceeds the {PROFILE_NAME_MAX}-character profile contract."))
    if not category:
        blockers.append(_blocker(None, "product_category_missing", "The captured product hierarchy has no governed category."))
    elif len(category) > PROFILE_CATEGORY_MAX:
        blockers.append(_blocker(None, "product_category_too_long", f"Product category exceeds the {PROFILE_CATEGORY_MAX}-character profile contract."))
    if existing_profile is not None and product_catalog_service.product_key(existing_profile.name) != product_key:
        blockers.append(_blocker(None, "service_id_collision", f"Service ID {proposed_service_id} already belongs to {existing_profile.name}."))

    mappings: list[dict[str, object]] = []
    classifications: list[str] = []
    family_keys: list[str] = []
    required_inputs: list[str] = []
    for sku in skus:
        commercial_candidate = candidate_by_sku.get(sku.id)
        if commercial_candidate is None:
            blockers.append(_blocker(sku.part_number, "commercial_candidate_missing", "No governed commercial mapping candidate exists in the active evidence set."))
            continue
        classifications.append(commercial_candidate.classification)
        if commercial_candidate.classification not in SUPPORTED_CLASSIFICATIONS:
            blockers.append(_blocker(sku.part_number, f"classification:{commercial_candidate.classification}", "The SKU is not classified as directly metered or included non-billable."))
            continue
        rule_id = release_rule_ids.get(sku.part_number)
        if rule_id is None:
            proposed_rule_id = commercial_candidate.proposed_mapping.get("commercial_rule_family_id")
            rule_id = str(proposed_rule_id) if isinstance(proposed_rule_id, str) else None
        term_id = release_term_ids.get(sku.part_number) or commercial_candidate.term_id
        rule = rules_by_id.get(rule_id) if rule_id else None
        term = terms_by_id.get(term_id) if term_id else None
        sku_codes = catalog_finalization_blockers(
            candidate=commercial_candidate,
            rule=rule,
            term=term,
            open_exception_codes=exception_codes.get(sku.part_number, set()),
            unresolved_relationship_statuses=relationship_statuses.get(sku.part_number, set()),
        )
        if release is None or sku.part_number not in release_parts:
            sku_codes.append("sku_not_in_active_release")
        if commercial_candidate.status != "approved":
            sku_codes.append(f"candidate_not_approved:{commercial_candidate.status}")
        if term is not None and term.status != "approved":
            sku_codes.append(f"term_not_approved:{term.status}")
        if rule is not None and rule.status != "approved":
            sku_codes.append(f"rule_not_approved:{rule.status}")
        metric_name = term.metric_name if term and term.metric_name else (rule.metric_pattern if rule else "")
        if len(metric_name) > MAPPING_UNIT_MAX:
            sku_codes.append("quantity_unit_too_long")
        for code in sorted(set(sku_codes)):
            blockers.append(_blocker(sku.part_number, code, f"{sku.part_number} is blocked by {code.replace('_', ' ')}."))
        if rule is None or term is None:
            continue
        family_keys.append(rule.family_key)
        required_inputs.append(metric_name)
        is_billable = commercial_candidate.classification == "direct_metered"
        is_byol = "BYOL" in f"{term.service_name} {term.price_type or ''}".upper()
        mappings.append(
            {
                "part_number": sku.part_number,
                "display_name": sku.display_name,
                "billing_metric_key": _metric_key(rule.family_key or metric_name),
                "formula_key": rule.formula_key,
                "quantity_behavior": rule.quantity_behavior,
                "quantity_increment": _decimal_float(rule.quantity_increment),
                "minimum_quantity": _decimal_float(rule.minimum_quantity),
                "quantity_unit": metric_name,
                "usage_basis": "metered_usage" if is_billable else "included_entitlement",
                "quote_rounding": rule.quote_rounding,
                "aggregation_window": rule.aggregation_window,
                "proration_policy": rule.proration_policy,
                "selection_policy": "required" if is_billable else "dependent",
                "requires_explicit_quantity": is_billable,
                "entry_guidance": term.additional_information or f"Enter the governed quantity for {metric_name}.",
                "predicates": {"byol": is_byol} if is_byol else {},
                "is_billable": is_billable,
                "commercial_rule_family_id": rule.id,
                "commercial_term_id": term.id,
                "source_url": document.source_url if document else None,
            }
        )

    if not mappings:
        blockers.append(_blocker(None, "quoteable_sku_missing", "No SKU in this product has complete governed billing semantics."))
    unique_blockers = list({(str(item.get("part_number")), str(item["code"])): item for item in blockers}.values())
    release_only = bool(unique_blockers) and all(item["code"] == "sku_not_in_active_release" for item in unique_blockers)
    readiness = "ready" if not unique_blockers else "blocked_release" if release_only else "blocked_evidence"
    classification = "mixed" if len(set(classifications)) > 1 else classifications[0] if classifications else "unclassified"
    source_urls = [document.source_url] if document and document.source_url else []
    profile: dict[str, object] = {
        "name": name,
        "category": category,
        "pricing_model": ", ".join(sorted(set(family_keys))) or None,
        "architectural_fit": "Captured OCI commercial product with explicitly governed SKU billing semantics.",
        "oracle_docs_urls": source_urls,
    }
    policy: dict[str, object] = {
        "classification": classification,
        "readiness": "quote_ready" if readiness == "ready" else "blocked",
        "publication_policy": "explicit_product_selection",
        "tool_aliases": [name, product_key],
        "required_inputs": sorted(set(item for item in required_inputs if item)),
        "guidance": "Select an approved commercial SKU and provide its governed billing quantity.",
        "source_urls": source_urls,
        "sku_count": len(skus),
    }
    return ProductCoverageProposal(
        product_name=name,
        category=category,
        proposed_service_id=proposed_service_id,
        proposed_profile=profile,
        proposed_policy=policy,
        proposed_mappings=mappings,
        readiness_status=readiness,
        readiness_blockers=unique_blockers,
        source_document_snapshot_id=document.id if document else None,
    )


async def generate_coverage(actor_id: str, db: AsyncSession) -> ProductCoverageGenerationResponse:
    """Create or refresh isolated product coverage proposals for the full taxonomy."""

    release = await _active_release(db)
    document = await _source_document(db, release)
    products = await _all_products(db)
    existing_candidates = {
        item.product_key: item
        for item in (await db.scalars(select(ProductCoverageCandidate))).all()
    }
    existing_profiles = {
        item.service_id: item
        for item in (await db.scalars(select(ServiceCapabilityProfile))).all()
    }
    generated = 0
    refreshed = 0
    counts = {"ready": 0, "blocked_release": 0, "blocked_evidence": 0}
    for product in products:
        proposal = await _proposal_for_product(
            db,
            product_key=product.product_key,
            release=release,
            document=document,
            existing_profiles=existing_profiles,
        )
        candidate = existing_candidates.get(product.product_key)
        if candidate is None:
            candidate = ProductCoverageCandidate(
                product_key=product.product_key,
                status="pending_review",
                generator_version=GENERATOR_VERSION,
                **proposal,
            )
            db.add(candidate)
            existing_candidates[product.product_key] = candidate
            generated += 1
        else:
            candidate.readiness_status = proposal["readiness_status"]
            candidate.readiness_blockers = cast(
                list[object], proposal["readiness_blockers"]
            )
            candidate.source_document_snapshot_id = proposal["source_document_snapshot_id"]
            if candidate.status == "pending_review":
                candidate.product_name = proposal["product_name"]
                candidate.category = proposal["category"]
                candidate.proposed_service_id = proposal["proposed_service_id"]
                candidate.proposed_profile = proposal["proposed_profile"]
                candidate.proposed_policy = proposal["proposed_policy"]
                candidate.proposed_mappings = cast(
                    list[object], proposal["proposed_mappings"]
                )
                candidate.generator_version = GENERATOR_VERSION
            refreshed += 1
        counts[proposal["readiness_status"]] += 1
    await db.flush()
    await audit_service.emit(
        "product_coverage_generated",
        "commercial_document_snapshot" if document else "product_coverage",
        document.id if document else "global-product-coverage",
        actor_id,
        None,
        {
            "generated": generated,
            "refreshed": refreshed,
            "total": len(products),
            **counts,
            "generator_version": GENERATOR_VERSION,
            "commercial_generator_version": COMMERCIAL_GENERATOR_VERSION,
        },
        None,
        db,
    )
    return ProductCoverageGenerationResponse(
        generated=generated,
        refreshed=refreshed,
        total=len(products),
        generator_version=GENERATOR_VERSION,
        **counts,
    )


async def list_coverage(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
    status: str | None = None,
    readiness_status: str | None = None,
) -> ProductCoverageListResponse:
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    query = select(ProductCoverageCandidate)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.where(or_(ProductCoverageCandidate.product_name.ilike(pattern), ProductCoverageCandidate.product_key.ilike(pattern), ProductCoverageCandidate.category.ilike(pattern)))
    if status and status != "all":
        query = query.where(ProductCoverageCandidate.status == status)
    if readiness_status and readiness_status != "all":
        query = query.where(ProductCoverageCandidate.readiness_status == readiness_status)
    total = int(await db.scalar(select(func.count()).select_from(query.subquery())) or 0)
    candidates = list((await db.scalars(query.order_by(ProductCoverageCandidate.category, ProductCoverageCandidate.product_name).offset((page - 1) * page_size).limit(page_size))).all())
    return ProductCoverageListResponse(products=[_candidate_row(item) for item in candidates], page=page, page_size=page_size, total=total)


async def get_coverage(product_key: str, db: AsyncSession) -> ProductCoverageDetailResponse:
    candidate = await db.scalar(select(ProductCoverageCandidate).where(ProductCoverageCandidate.product_key == product_catalog_service.product_key(product_key)))
    if candidate is None:
        raise HTTPException(status_code=404, detail={"detail": "Product coverage proposal not found", "error_code": "PRODUCT_COVERAGE_NOT_FOUND"})
    return _candidate_detail(candidate)


async def review_coverage(
    product_key: str,
    *,
    decision: str,
    rationale: str,
    actor_id: str,
    db: AsyncSession,
) -> ProductCoverageDetailResponse:
    candidate = await db.scalar(
        select(ProductCoverageCandidate)
        .where(
            ProductCoverageCandidate.product_key
            == product_catalog_service.product_key(product_key)
        )
        .with_for_update()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail={"detail": "Product coverage proposal not found", "error_code": "PRODUCT_COVERAGE_NOT_FOUND"})
    if decision == "approve" and candidate.readiness_status != "ready":
        raise HTTPException(status_code=409, detail={"detail": "Product coverage is blocked by governed commercial evidence", "error_code": "PRODUCT_COVERAGE_NOT_READY", "blockers": candidate.readiness_blockers})
    old_status = candidate.status
    now = _now()
    if decision == "reject":
        candidate.status = "rejected"
    else:
        profile_payload = candidate.proposed_profile
        category = profile_payload.get("category")
        if not isinstance(category, str) or not category:
            raise HTTPException(status_code=409, detail={"detail": "Product category is required before materialization", "error_code": "PRODUCT_COVERAGE_PROFILE_INVALID"})
        profile = await db.scalar(select(ServiceCapabilityProfile).where(ServiceCapabilityProfile.service_id == candidate.proposed_service_id))
        if profile is None:
            profile = ServiceCapabilityProfile(
                service_id=candidate.proposed_service_id,
                name=str(profile_payload["name"]),
                category=category,
                pricing_model=str(profile_payload.get("pricing_model") or "Governed OCI commercial rules"),
                architectural_fit=str(profile_payload.get("architectural_fit") or ""),
                oracle_docs_urls="\n".join(_string_list(profile_payload.get("oracle_docs_urls"))) or None,
                is_active=True,
                version="1.0.0",
            )
            db.add(profile)
            await db.flush()
        policy_payload = candidate.proposed_policy
        policy = await db.scalar(select(ServiceCommercialPolicy).where(ServiceCommercialPolicy.service_id == candidate.proposed_service_id))
        policy_values = {
            "classification": str(policy_payload["classification"]),
            "readiness": str(policy_payload["readiness"]),
            "publication_policy": str(policy_payload["publication_policy"]),
            "tool_aliases": _object_list(policy_payload.get("tool_aliases", [])),
            "dependent_service_ids": [],
            "required_inputs": _object_list(policy_payload.get("required_inputs", [])),
            "guidance": str(policy_payload["guidance"]),
            "source_urls": _object_list(policy_payload.get("source_urls", [])),
            "status": "approved",
            "version": "1.0.0",
            "confidence": 1.0,
        }
        if policy is None:
            policy = ServiceCommercialPolicy(service_profile_id=profile.id, service_id=profile.service_id, **policy_values)
            db.add(policy)
        else:
            if policy.service_profile_id != profile.id:
                raise HTTPException(status_code=409, detail={"detail": "Existing commercial policy belongs to another service profile", "error_code": "PRODUCT_COVERAGE_POLICY_COLLISION"})
            for field, value in policy_values.items():
                setattr(policy, field, value)
        for raw_mapping in candidate.proposed_mappings:
            if not isinstance(raw_mapping, dict):
                continue
            part_number = str(raw_mapping["part_number"])
            metric_key = str(raw_mapping["billing_metric_key"])
            mapping = await db.scalar(select(ServiceProductSkuMapping).where(ServiceProductSkuMapping.service_id == profile.service_id, ServiceProductSkuMapping.part_number == part_number, ServiceProductSkuMapping.billing_metric_key == metric_key))
            values: dict[str, Any] = {
                "service_profile_id": profile.id,
                "service_id": profile.service_id,
                "tool_key": profile.service_id,
                "part_number": part_number,
                "billing_metric_key": metric_key,
                "formula_key": str(raw_mapping["formula_key"]),
                "quantity_behavior": str(raw_mapping["quantity_behavior"]),
                "quantity_increment": float(raw_mapping["quantity_increment"]),
                "minimum_quantity": float(raw_mapping["minimum_quantity"]),
                "quantity_unit": str(raw_mapping["quantity_unit"]),
                "usage_basis": str(raw_mapping["usage_basis"]),
                "quote_rounding": str(raw_mapping["quote_rounding"]),
                "aggregation_window": str(raw_mapping["aggregation_window"]),
                "proration_policy": str(raw_mapping["proration_policy"]),
                "selection_policy": str(raw_mapping["selection_policy"]),
                "requires_explicit_quantity": bool(raw_mapping["requires_explicit_quantity"]),
                "entry_guidance": str(raw_mapping["entry_guidance"]),
                "predicates": _object_dict(raw_mapping.get("predicates", {})),
                "is_billable": bool(raw_mapping["is_billable"]),
                "status": "approved",
                "version": "1.0.0",
                "source_url": raw_mapping.get("source_url"),
                "confidence": 1.0,
            }
            if mapping is None:
                db.add(ServiceProductSkuMapping(**values))
            else:
                for field, value in values.items():
                    setattr(mapping, field, value)
        candidate.status = "approved"
    candidate.review_rationale = rationale
    candidate.reviewed_by = actor_id
    candidate.reviewed_at = now
    await db.flush()
    await audit_service.emit(
        "product_coverage_reviewed",
        "product_coverage_candidate",
        candidate.id,
        actor_id,
        {"status": old_status},
        {"status": candidate.status, "decision": decision, "rationale": rationale},
        None,
        db,
    )
    return _candidate_detail(candidate)
