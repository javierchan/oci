"""Operational commercial-review queue contract tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import (
    AuditEvent,
    CommercialException,
    CommercialMappingCandidate,
    CommercialRelease,
    CommercialReviewAssignment,
    CommercialSku,
    ProductCoverageCandidate,
    ServiceProductSkuMapping,
)


async def _seed_queue(engine: AsyncEngine) -> dict[str, str]:
    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    now = datetime.now(UTC)
    async with session_factory() as db, db.begin():
        release = CommercialRelease(
            version="commercial-global-test",
            price_catalog_snapshot_id="price-global",
            document_snapshot_id="document-global",
            mapping_set_hash="mapping",
            rule_family_set_hash="rules",
            evidence_hash="evidence",
            status="approved",
            validation_status="passed",
            release_metadata={"scope": "global_oci_catalog"},
            approved_by="reviewer",
            approved_at=now,
        )
        ignored_release = CommercialRelease(
            version="browser-quality-newer",
            price_catalog_snapshot_id="price-browser",
            document_snapshot_id="document-browser",
            mapping_set_hash="mapping-browser",
            rule_family_set_hash="rules-browser",
            evidence_hash="evidence-browser",
            status="approved",
            validation_status="passed",
            release_metadata={"scope": "browser_quality"},
            approved_by="browser",
            approved_at=now + timedelta(minutes=1),
        )
        sku = CommercialSku(
            part_number="B100",
            display_name="OCI Critical Service",
            service_category="Integration",
        )
        db.add_all([release, ignored_release, sku])
        await db.flush()

        exception = CommercialException(
            document_snapshot_id="document-global",
            part_number="B100",
            exception_code="DEPENDENCY_RELATIONSHIP_UNRESOLVED",
            severity="high",
            status="open",
            details={"relationship": "entitlement"},
        )
        ignored_exception = CommercialException(
            document_snapshot_id="document-browser",
            part_number="X999",
            exception_code="SHOULD_NOT_APPEAR",
            severity="high",
            status="open",
            details={},
        )
        candidate = CommercialMappingCandidate(
            document_snapshot_id="document-global",
            commercial_sku_id=sku.id,
            part_number="B100",
            proposed_service_id="OIC3",
            classification="direct_metered",
            proposed_mapping={"part_number": "B100"},
            confidence=0.8,
            generator_version="test",
            status="blocked",
            reasons=[{"code": "RULE_REQUIRED"}],
        )
        product = ProductCoverageCandidate(
            product_key="integration-service",
            product_name="Integration Service",
            category="Integration",
            proposed_service_id="OIC3",
            proposed_profile={},
            proposed_policy={},
            proposed_mappings=[{"part_number": "B100"}],
            readiness_status="ready",
            readiness_blockers=[],
            status="pending_review",
            generator_version="test",
            source_document_snapshot_id="document-global",
        )
        mapping = ServiceProductSkuMapping(
            service_id="OIC3",
            tool_key="OIC3",
            part_number="B100",
            billing_metric_key="messages",
            formula_key="oic_messages",
        )
        db.add_all([exception, ignored_exception, candidate, product, mapping])
        await db.flush()
        assignment = CommercialReviewAssignment(
            entity_type="exception",
            entity_id=exception.id,
            assignee="pricing.owner",
            workflow_status="in_progress",
            due_at=now - timedelta(days=1),
            note="Review the entitlement evidence.",
            updated_by="seed",
        )
        db.add(assignment)
        await db.flush()
        return {
            "exception_id": exception.id,
            "candidate_id": candidate.id,
            "product_key": product.product_key,
        }


@pytest.mark.asyncio
async def test_queue_prioritizes_active_global_release_with_explainable_signals(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    ids = await _seed_queue(test_engine)

    response = await api_client.get(
        "/api/v1/pricing/review-work-queue",
        headers={"X-Actor-Role": "Admin"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source_release_version"] == "commercial-global-test"
    assert payload["summary"]["total"] == 3
    assert payload["summary"]["urgent"] == 1
    assert payload["summary"]["overdue"] == 1
    assert payload["summary"]["unassigned"] == 2
    assert payload["total"] == 3
    assert payload["items"][0]["entity_id"] == ids["exception_id"]
    assert payload["items"][0]["priority_tier"] == "urgent"
    assert {
        signal["code"] for signal in payload["items"][0]["priority_signals"]
    } >= {"severity_high", "bom_impact", "dependency_blocked", "overdue"}
    assert all(item["part_number"] != "X999" for item in payload["items"])

    filtered = await api_client.get(
        "/api/v1/pricing/review-work-queue",
        params={"entity_type": "product_coverage", "priority": "high"},
        headers={"X-Actor-Role": "Admin"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["entity_id"] == ids["product_key"]


@pytest.mark.asyncio
async def test_assignment_update_is_audited_without_changing_commercial_state(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    ids = await _seed_queue(test_engine)

    response = await api_client.patch(
        f"/api/v1/pricing/review-work-queue/mapping_candidate/{ids['candidate_id']}",
        headers={
            "X-Actor-Role": "Admin",
            "X-Actor-Id": "commercial-admin",
        },
        json={
            "assignee": "catalog.reviewer",
            "workflow_status": "waiting_evidence",
            "due_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            "note": "Obtain the missing official rule fixture.",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["assignee"] == "catalog.reviewer"
    assert payload["workflow_status"] == "waiting_evidence"
    assert payload["source_status"] == "blocked"

    session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )
    async with session_factory() as db:
        candidate = await db.get(CommercialMappingCandidate, ids["candidate_id"])
        assignment = await db.scalar(
            select(CommercialReviewAssignment).where(
                CommercialReviewAssignment.entity_id == ids["candidate_id"]
            )
        )
        audit = await db.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "commercial_review_assignment_updated"
            )
        )
    assert candidate is not None and candidate.status == "blocked"
    assert assignment is not None and assignment.assignee == "catalog.reviewer"
    assert audit is not None
    assert audit.actor_id == "commercial-admin"
    assert audit.new_value is not None
    assert audit.new_value["workflow_status"] == "waiting_evidence"


@pytest.mark.asyncio
async def test_queue_requires_admin_and_rejects_inconsistent_assignment(
    api_client: AsyncClient,
    test_engine: AsyncEngine,
) -> None:
    ids = await _seed_queue(test_engine)

    forbidden = await api_client.get(
        "/api/v1/pricing/review-work-queue",
        headers={"X-Actor-Role": "Viewer"},
    )
    assert forbidden.status_code == 403

    invalid = await api_client.patch(
        f"/api/v1/pricing/review-work-queue/exception/{ids['exception_id']}",
        headers={"X-Actor-Role": "Admin"},
        json={
            "assignee": None,
            "workflow_status": "in_progress",
            "due_at": None,
            "note": None,
        },
    )
    assert invalid.status_code == 422
