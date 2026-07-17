"""Continuous verification of official OCI pricing and estimator evidence."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import hashlib
import json
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.pricing_engine import QuantityBehavior, QuantityRule, normalize_quantity
from app.models import (
    GovernanceChangeSet,
    GovernanceSourceArtifact,
    PriceCatalogSnapshot,
    PriceItem,
    PriceSource,
    PriceSyncJob,
    QuotationRegressionRun,
    ServiceCommercialPolicy,
    ServiceProductSkuMapping,
)
from app.services import storage_service


OFFICIAL_ESTIMATOR_SOURCES = {
    "products": "https://www.oracle.com/a/ocom/docs/cloudestimator2/data/products.json",
    "metrics": "https://www.oracle.com/a/ocom/docs/cloudestimator2/data/metrics.json",
    "presets": "https://www.oracle.com/a/ocom/docs/cloudestimator2/data/productpresets.json",
}
ALLOWED_HOSTS = {"apexapps.oracle.com", "www.oracle.com", "oracle.com"}
FETCH_ATTEMPTS = 3
FETCH_TIMEOUT_SECONDS = 45.0
USER_AGENT = "OCI-DIS-Architect-Governance/1.0"


def _now() -> datetime:
    return datetime.now(UTC)


def _canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _record_count(payload: dict[str, Any]) -> int:
    for key in ("items", "products", "metrics", "presets", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)
        if isinstance(value, dict):
            return len(value)
    return len(payload)


def _source_last_updated(payload: dict[str, Any]) -> datetime | None:
    for key in ("lastUpdated", "last_updated", "updatedAt", "updated_at"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "") not in ALLOWED_HOSTS:
        raise ValueError("Official OCI governance source is not allowlisted")


async def _fetch_json(client: httpx.AsyncClient, url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    _validate_url(url)
    last_error: Exception | None = None
    for attempt in range(FETCH_ATTEMPTS):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or _record_count(payload) < 1:
                raise ValueError("Official OCI source returned an empty or invalid JSON object")
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
            if attempt + 1 < FETCH_ATTEMPTS:
                await asyncio.sleep(0.5 * (2**attempt))
    raise ValueError(f"Official OCI source could not be verified: {last_error}") from last_error


async def fetch_official_source_bundle(
    source: PriceSource,
    currency: str,
) -> dict[str, tuple[str, dict[str, Any]]]:
    """Fetch the price feed and all estimator reference catalogs as one validation unit."""

    if not source.base_url:
        raise ValueError("Public price source has no URL")
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        price_payload, products, metrics, presets = await asyncio.gather(
            _fetch_json(client, source.base_url, {"currencyCode": currency.upper()}),
            _fetch_json(client, OFFICIAL_ESTIMATOR_SOURCES["products"]),
            _fetch_json(client, OFFICIAL_ESTIMATOR_SOURCES["metrics"]),
            _fetch_json(client, OFFICIAL_ESTIMATOR_SOURCES["presets"]),
        )
    return {
        "price_catalog": (source.base_url, price_payload),
        "products": (OFFICIAL_ESTIMATOR_SOURCES["products"], products),
        "metrics": (OFFICIAL_ESTIMATOR_SOURCES["metrics"], metrics),
        "presets": (OFFICIAL_ESTIMATOR_SOURCES["presets"], presets),
    }


def _price_signature(item: PriceItem | dict[str, object]) -> tuple[object, ...]:
    if isinstance(item, PriceItem):
        return (
            item.part_number,
            item.model,
            float(item.value),
            item.range_min,
            item.range_max,
            item.range_unit,
            item.metric_name,
        )
    return (
        item["part_number"],
        item["model"],
        float(str(item["value"])),
        item["range_min"],
        item["range_max"],
        item["range_unit"],
        item["metric_name"],
    )


async def _run_family_regressions(
    *,
    change_set: GovernanceChangeSet,
    normalized_prices: list[dict[str, object]],
    db: AsyncSession,
) -> list[QuotationRegressionRun]:
    policies = (
        await db.scalars(
            select(ServiceCommercialPolicy)
            .where(ServiceCommercialPolicy.status == "approved")
            .order_by(ServiceCommercialPolicy.service_id)
        )
    ).all()
    mappings = (
        await db.scalars(
            select(ServiceProductSkuMapping)
            .where(ServiceProductSkuMapping.status == "approved")
            .order_by(ServiceProductSkuMapping.service_id, ServiceProductSkuMapping.billing_metric_key)
        )
    ).all()
    available_skus = {str(item["part_number"]) for item in normalized_prices}
    runs: list[QuotationRegressionRun] = []
    for policy in policies:
        started_at = _now()
        family_mappings = [mapping for mapping in mappings if mapping.service_id == policy.service_id]
        findings: list[object] = []
        checks = 0
        if policy.readiness not in {"quote_ready", "input_required", "rate_card_required", "ready"}:
            findings.append({"code": "POLICY_NOT_READY", "detail": policy.readiness})
        requires_public_mapping = policy.classification == "direct_metered" or (
            policy.classification == "license_plus_infrastructure" and policy.readiness == "quote_ready"
        )
        if requires_public_mapping and not family_mappings:
            findings.append({"code": "MAPPING_MISSING", "detail": "Priced service has no approved SKU mapping"})
        for mapping in family_mappings:
            checks += 1
            if (
                mapping.is_billable
                and policy.readiness != "rate_card_required"
                and mapping.part_number not in available_skus
            ):
                findings.append(
                    {"code": "SKU_NOT_IN_CANDIDATE", "mapping_id": mapping.id, "part_number": mapping.part_number}
                )
            try:
                rule = QuantityRule(
                    behavior=QuantityBehavior(mapping.quantity_behavior),
                    increment=Decimal(str(mapping.quantity_increment)),
                    minimum=Decimal(str(mapping.minimum_quantity)),
                )
                sample = max(rule.minimum, rule.increment * Decimal("1.5"))
                normalized = normalize_quantity(sample, rule)
                if normalized < rule.minimum:
                    raise ValueError("normalized quantity is below minimum")
            except (ValueError, ArithmeticError) as exc:
                findings.append({"code": "QUANTITY_RULE_INVALID", "mapping_id": mapping.id, "detail": str(exc)})
        if not family_mappings:
            checks = 1
        failed_count = len(findings)
        status = "passed" if failed_count == 0 else "failed"
        runs.append(
            QuotationRegressionRun(
                change_set_id=change_set.id,
                family_key=policy.service_id,
                status=status,
                fixture_count=checks,
                passed_count=max(checks - failed_count, 0),
                failed_count=failed_count,
                mapping_count=len(family_mappings),
                findings=findings,
                started_at=started_at,
                completed_at=_now(),
            )
        )
    return runs


async def persist_change_set(
    *,
    job: PriceSyncJob,
    source: PriceSource,
    snapshot: PriceCatalogSnapshot,
    previous_snapshot: PriceCatalogSnapshot | None,
    bundle: dict[str, tuple[str, dict[str, Any]]],
    normalized_prices: list[dict[str, object]],
    trigger_type: str,
    db: AsyncSession,
) -> GovernanceChangeSet:
    """Persist source evidence, drift, impact, and deterministic quote regressions."""

    previous_change_set = await db.scalar(
        select(GovernanceChangeSet)
        .where(
            GovernanceChangeSet.price_source_id == source.id,
            GovernanceChangeSet.currency == job.currency,
            GovernanceChangeSet.approval_status.in_(("approved", "not_required")),
        )
        .order_by(GovernanceChangeSet.created_at.desc())
    )
    change_set = GovernanceChangeSet(
        sync_job_id=job.id,
        price_source_id=source.id,
        price_snapshot_id=snapshot.id,
        previous_change_set_id=previous_change_set.id if previous_change_set else None,
        trigger_type=trigger_type,
        currency=job.currency,
        status="validating",
        drift_classification="none",
        materiality_score=0,
        source_manifest={},
        drift_summary={},
        impact_summary={},
        validation_status="pending",
        regression_summary={},
        approval_status="pending_review",
    )
    db.add(change_set)
    await db.flush()

    previous_hashes: dict[str, str] = {}
    if previous_change_set is not None:
        prior_artifacts = (
            await db.scalars(
                select(GovernanceSourceArtifact).where(
                    GovernanceSourceArtifact.change_set_id == previous_change_set.id
                )
            )
        ).all()
        previous_hashes = {artifact.source_kind: artifact.content_hash for artifact in prior_artifacts}

    manifest: dict[str, object] = {}
    changed_sources: list[str] = []
    retrieved_at = _now()
    for source_kind, (source_url, payload) in bundle.items():
        content_hash = _payload_hash(payload)
        record_count = _record_count(payload)
        if previous_hashes.get(source_kind) != content_hash:
            changed_sources.append(source_kind)
        storage_reference = storage_service.put_bytes(
            f"governance/oci-sources/jobs/{job.id}/{source_kind}.json",
            _canonical_bytes(payload),
            content_type="application/json",
            metadata={"change-set-id": change_set.id, "source-kind": source_kind},
        )
        db.add(
            GovernanceSourceArtifact(
                change_set_id=change_set.id,
                source_kind=source_kind,
                source_url=source_url,
                content_hash=content_hash,
                record_count=record_count,
                storage_reference=storage_reference,
                source_last_updated=_source_last_updated(payload),
                retrieval_status="verified",
                validation_summary={"json_object": True, "non_empty": True, "record_count": record_count},
                retrieved_at=retrieved_at,
            )
        )
        manifest[source_kind] = {
            "url": source_url,
            "sha256": content_hash,
            "record_count": record_count,
            "storage_reference": storage_reference,
        }

    previous_items: list[PriceItem] = []
    if previous_snapshot is not None:
        previous_items = list(
            (
                await db.scalars(
                    select(PriceItem).where(PriceItem.snapshot_id == previous_snapshot.id)
                )
            ).all()
        )
    old_signatures = {_price_signature(item) for item in previous_items}
    new_signatures = {_price_signature(item) for item in normalized_prices}
    added = new_signatures - old_signatures
    removed = old_signatures - new_signatures
    price_changes = len(added) + len(removed)
    denominator = max(len(old_signatures), len(new_signatures), 1)
    materiality = min(price_changes / denominator, 1.0)
    changed_skus = sorted({str(item[0]) for item in added | removed})
    active_mappings = (
        await db.scalars(
            select(ServiceProductSkuMapping).where(ServiceProductSkuMapping.status == "approved")
        )
    ).all()
    affected_services = sorted(
        {mapping.service_id for mapping in active_mappings if mapping.part_number in changed_skus}
    )
    if previous_change_set is None:
        drift_classification = "baseline"
    elif price_changes:
        drift_classification = "commercial"
    elif changed_sources:
        drift_classification = "reference_metadata"
    else:
        drift_classification = "none"

    regression_runs = await _run_family_regressions(
        change_set=change_set,
        normalized_prices=normalized_prices,
        db=db,
    )
    db.add_all(regression_runs)
    passed = sum(run.status == "passed" for run in regression_runs)
    failed = len(regression_runs) - passed
    validation_status = "passed" if regression_runs and failed == 0 else "failed"
    has_drift = drift_classification != "none"
    change_set.source_manifest = manifest
    change_set.drift_classification = drift_classification
    change_set.materiality_score = materiality
    change_set.drift_summary = {
        "changed_sources": changed_sources,
        "price_signature_changes": price_changes,
        "added_or_changed": len(added),
        "removed_or_changed": len(removed),
    }
    change_set.impact_summary = {
        "affected_skus": changed_skus[:200],
        "affected_services": affected_services,
        "active_mapping_count": len(active_mappings),
    }
    change_set.validation_status = validation_status
    change_set.regression_summary = {
        "families": len(regression_runs),
        "passed": passed,
        "failed": failed,
        "coverage_pct": round((passed / len(regression_runs)) * 100, 2) if regression_runs else 0,
    }
    if validation_status != "passed":
        change_set.status = "blocked"
        change_set.approval_status = "blocked"
    elif not has_drift:
        change_set.status = "no_change"
        change_set.approval_status = "not_required"
        change_set.promoted_at = retrieved_at
    else:
        change_set.status = "ready_for_review"
        change_set.approval_status = "pending_review"
    await db.flush()
    return change_set


async def ensure_public_snapshot_is_current(snapshot: PriceCatalogSnapshot, db: AsyncSession) -> None:
    """Block new public-list quotes when official verification evidence is stale or absent."""

    settings = get_settings()
    change_set = await db.scalar(
        select(GovernanceChangeSet)
        .where(
            GovernanceChangeSet.price_snapshot_id == snapshot.id,
            GovernanceChangeSet.validation_status == "passed",
            GovernanceChangeSet.approval_status.in_(("approved", "not_required")),
        )
        .order_by(GovernanceChangeSet.created_at.desc())
    )
    if change_set is None:
        raise ValueError("Approved public price catalog has no verified OCI source change set; run verification first")
    verified_at = change_set.promoted_at or change_set.approved_at or change_set.created_at
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=UTC)
    if verified_at < _now() - timedelta(hours=settings.OCI_GOVERNANCE_MAX_SOURCE_AGE_HOURS):
        raise ValueError(
            "Official OCI pricing evidence is stale; complete source verification before generating a new BOM"
        )
