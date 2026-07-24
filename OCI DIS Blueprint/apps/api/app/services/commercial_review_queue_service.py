"""Operational work queue for unresolved commercial-governance decisions."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import TypedDict
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CommercialException,
    CommercialMappingCandidate,
    CommercialRelease,
    CommercialReviewAssignment,
    CommercialSku,
    ProductCoverageCandidate,
    ServiceProductSkuMapping,
)
from app.services import audit_service


ENTITY_EXCEPTION = "exception"
ENTITY_MAPPING_CANDIDATE = "mapping_candidate"
ENTITY_PRODUCT_COVERAGE = "product_coverage"
ENTITY_TYPES = {
    ENTITY_EXCEPTION,
    ENTITY_MAPPING_CANDIDATE,
    ENTITY_PRODUCT_COVERAGE,
}
WORKFLOW_STATUSES = {
    "unassigned",
    "assigned",
    "in_progress",
    "waiting_evidence",
}


class PrioritySignal(TypedDict):
    code: str
    label: str
    points: int


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _signal(code: str, label: str, points: int) -> PrioritySignal:
    return {"code": code, "label": label, "points": points}


def _priority_tier(score: int) -> str:
    if score >= 120:
        return "urgent"
    if score >= 90:
        return "high"
    if score >= 50:
        return "normal"
    return "low"


def _priority(
    *,
    entity_type: str,
    severity: str | None,
    source_status: str,
    bom_impact: bool,
    blocker_count: int,
    dependency_blocked: bool,
    overdue: bool,
) -> tuple[int, list[PrioritySignal]]:
    """Return an explainable scheduling score; never a commercial decision."""

    signals: list[PrioritySignal] = []
    if entity_type == ENTITY_EXCEPTION:
        severity_points = {"high": 80, "medium": 50, "low": 20}.get(
            (severity or "").lower(), 20
        )
        signals.append(
            _signal(
                f"severity_{(severity or 'unknown').lower()}",
                f"{(severity or 'Unknown').title()}-severity exception",
                severity_points,
            )
        )
    elif entity_type == ENTITY_MAPPING_CANDIDATE:
        signals.append(
            _signal(
                "mapping_disposition_required",
                "Generated mapping still requires a human disposition",
                40,
            )
        )
    else:
        readiness_points = {
            "ready": 80,
            "blocked_release": 60,
            "blocked_evidence": 30,
        }.get(source_status, 30)
        signals.append(
            _signal(
                f"readiness_{source_status}",
                f"Product coverage is {source_status.replace('_', ' ')}",
                readiness_points,
            )
        )

    if bom_impact:
        signals.append(
            _signal(
                "bom_impact",
                "Part number participates in an approved BOM mapping",
                30,
            )
        )
    if dependency_blocked:
        signals.append(
            _signal(
                "dependency_blocked",
                "A dependency or entitlement relationship is unresolved",
                25,
            )
        )
    if blocker_count:
        blocker_points = min(20, blocker_count * 5)
        signals.append(
            _signal(
                "blocker_count",
                f"{blocker_count} governed blocker{'s' if blocker_count != 1 else ''}",
                blocker_points,
            )
        )
    if overdue:
        signals.append(_signal("overdue", "Operational due date has passed", 20))
    return sum(item["points"] for item in signals), signals


def _assignment_values(
    assignment: CommercialReviewAssignment | None,
) -> tuple[str, str | None, datetime | None, str | None, datetime | None]:
    if assignment is None:
        return "unassigned", None, None, None, None
    return (
        assignment.workflow_status,
        assignment.assignee,
        _aware(assignment.due_at),
        assignment.note,
        _aware(assignment.updated_at),
    )


def _recommended_action(entity_type: str, source_status: str) -> str:
    if entity_type == ENTITY_EXCEPTION:
        return "Inspect the cited evidence, then explicitly resolve, accept risk, or keep the exception open."
    if entity_type == ENTITY_MAPPING_CANDIDATE:
        return "Inspect official identity, term, rule, and relationship evidence before recording a mapping disposition."
    if source_status == "ready":
        return "Validate the complete product proposal, then explicitly approve or reject it."
    if source_status == "blocked_release":
        return "Resolve release coverage blockers before reviewing this product for approval."
    return "Capture the missing governed evidence before reviewing this product for approval."


def _contains_dependency(value: object) -> bool:
    text = str(value).upper()
    return any(token in text for token in ("DEPENDENCY", "RELATIONSHIP", "ENTITLEMENT"))


def _work_item(
    *,
    entity_type: str,
    entity_id: str,
    title: str,
    part_number: str | None,
    category: str | None,
    source_status: str,
    severity: str | None,
    blocker_count: int,
    dependency_blocked: bool,
    bom_impact: bool,
    created_at: datetime,
    updated_at: datetime,
    assignment: CommercialReviewAssignment | None,
    now: datetime,
) -> dict[str, object]:
    workflow_status, assignee, due_at, note, assignment_updated_at = _assignment_values(
        assignment
    )
    overdue = due_at is not None and due_at < now
    score, signals = _priority(
        entity_type=entity_type,
        severity=severity,
        source_status=source_status,
        bom_impact=bom_impact,
        blocker_count=blocker_count,
        dependency_blocked=dependency_blocked,
        overdue=overdue,
    )
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "title": title,
        "part_number": part_number,
        "category": category,
        "source_status": source_status,
        "severity": severity,
        "priority_score": score,
        "priority_tier": _priority_tier(score),
        "priority_signals": signals,
        "workflow_status": workflow_status,
        "assignee": assignee,
        "due_at": due_at,
        "overdue": overdue,
        "note": note,
        "bom_impact": bom_impact,
        "blocker_count": blocker_count,
        "recommended_next_action": _recommended_action(entity_type, source_status),
        "created_at": _aware(created_at),
        "updated_at": assignment_updated_at or _aware(updated_at),
    }


async def _active_global_release(db: AsyncSession) -> CommercialRelease | None:
    releases = (
        await db.scalars(
            select(CommercialRelease)
            .where(
                CommercialRelease.status == "approved",
                CommercialRelease.validation_status == "passed",
            )
            .order_by(
                CommercialRelease.approved_at.desc(),
                CommercialRelease.created_at.desc(),
            )
        )
    ).all()
    return next(
        (
            release
            for release in releases
            if release.release_metadata.get("scope") == "global_oci_catalog"
        ),
        None,
    )


async def _approved_bom_parts(db: AsyncSession) -> set[str]:
    parts = await db.scalars(
        select(ServiceProductSkuMapping.part_number).where(
            ServiceProductSkuMapping.status == "approved",
            ServiceProductSkuMapping.part_number.is_not(None),
        )
    )
    return {part for part in parts.all() if part}


def _mapping_part_numbers(mappings: Iterable[object]) -> set[str]:
    parts: set[str] = set()
    for mapping in mappings:
        if isinstance(mapping, dict):
            part_number = mapping.get("part_number")
            if isinstance(part_number, str) and part_number:
                parts.add(part_number)
    return parts


async def _queue_context(
    db: AsyncSession,
) -> tuple[CommercialRelease | None, list[dict[str, object]]]:
    release = await _active_global_release(db)
    if release is None:
        return None, []

    document_id = release.document_snapshot_id
    exceptions = (
        await db.scalars(
            select(CommercialException).where(
                CommercialException.document_snapshot_id == document_id,
                CommercialException.status == "open",
            )
        )
    ).all()
    candidates = (
        await db.scalars(
            select(CommercialMappingCandidate).where(
                CommercialMappingCandidate.document_snapshot_id == document_id,
                CommercialMappingCandidate.status.in_(("blocked", "pending_review")),
            )
        )
    ).all()
    coverage = (
        await db.scalars(
            select(ProductCoverageCandidate).where(
                ProductCoverageCandidate.source_document_snapshot_id == document_id,
                ProductCoverageCandidate.status == "pending_review",
            )
        )
    ).all()

    assignments = (await db.scalars(select(CommercialReviewAssignment))).all()
    assignment_by_key = {
        (assignment.entity_type, assignment.entity_id): assignment
        for assignment in assignments
    }
    bom_parts = await _approved_bom_parts(db)

    sku_ids = {candidate.commercial_sku_id for candidate in candidates}
    skus = (
        (await db.scalars(select(CommercialSku).where(CommercialSku.id.in_(sku_ids)))).all()
        if sku_ids
        else []
    )
    sku_by_id = {sku.id: sku for sku in skus}
    now = datetime.now(UTC)
    items: list[dict[str, object]] = []

    for exception in exceptions:
        code = exception.exception_code
        detail_count = len(exception.details) if isinstance(exception.details, dict) else 0
        items.append(
            _work_item(
                entity_type=ENTITY_EXCEPTION,
                entity_id=exception.id,
                title=code.replace("_", " ").title(),
                part_number=exception.part_number,
                category="Commercial exception",
                source_status=exception.status,
                severity=exception.severity,
                blocker_count=max(1, detail_count),
                dependency_blocked=_contains_dependency(code)
                or _contains_dependency(exception.details),
                bom_impact=bool(exception.part_number and exception.part_number in bom_parts),
                created_at=exception.created_at,
                updated_at=exception.updated_at,
                assignment=assignment_by_key.get((ENTITY_EXCEPTION, exception.id)),
                now=now,
            )
        )

    for candidate in candidates:
        sku = sku_by_id.get(candidate.commercial_sku_id)
        reasons = candidate.reasons if isinstance(candidate.reasons, list) else []
        items.append(
            _work_item(
                entity_type=ENTITY_MAPPING_CANDIDATE,
                entity_id=candidate.id,
                title=sku.display_name if sku else candidate.part_number,
                part_number=candidate.part_number,
                category=sku.service_category if sku else candidate.classification,
                source_status=candidate.status,
                severity=None,
                blocker_count=len(reasons),
                dependency_blocked=_contains_dependency(reasons),
                bom_impact=candidate.part_number in bom_parts,
                created_at=candidate.created_at,
                updated_at=candidate.updated_at,
                assignment=assignment_by_key.get(
                    (ENTITY_MAPPING_CANDIDATE, candidate.id)
                ),
                now=now,
            )
        )

    for product in coverage:
        blockers = (
            product.readiness_blockers
            if isinstance(product.readiness_blockers, list)
            else []
        )
        proposed_parts = _mapping_part_numbers(product.proposed_mappings)
        items.append(
            _work_item(
                entity_type=ENTITY_PRODUCT_COVERAGE,
                entity_id=product.product_key,
                title=product.product_name,
                part_number=next(iter(sorted(proposed_parts)), None),
                category=product.category,
                source_status=product.readiness_status,
                severity=None,
                blocker_count=len(blockers),
                dependency_blocked=_contains_dependency(blockers),
                bom_impact=bool(proposed_parts & bom_parts),
                created_at=product.created_at,
                updated_at=product.updated_at,
                assignment=assignment_by_key.get(
                    (ENTITY_PRODUCT_COVERAGE, product.product_key)
                ),
                now=now,
            )
        )

    return release, items


def _summary(items: list[dict[str, object]]) -> dict[str, int]:
    return {
        "total": len(items),
        "urgent": sum(item["priority_tier"] == "urgent" for item in items),
        "high": sum(item["priority_tier"] == "high" for item in items),
        "normal": sum(item["priority_tier"] == "normal" for item in items),
        "low": sum(item["priority_tier"] == "low" for item in items),
        "unassigned": sum(item["workflow_status"] == "unassigned" for item in items),
        "overdue": sum(bool(item["overdue"]) for item in items),
        "exceptions": sum(item["entity_type"] == ENTITY_EXCEPTION for item in items),
        "mapping_candidates": sum(
            item["entity_type"] == ENTITY_MAPPING_CANDIDATE for item in items
        ),
        "product_coverage": sum(
            item["entity_type"] == ENTITY_PRODUCT_COVERAGE for item in items
        ),
    }


async def list_work_queue(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
    search: str | None = None,
    entity_type: str = "all",
    priority: str = "all",
    workflow_status: str = "all",
    severity: str = "all",
    assignee: str | None = None,
) -> dict[str, object]:
    release, all_items = await _queue_context(db)
    summary = _summary(all_items)
    items = list(all_items)

    if search and search.strip():
        needle = search.strip().lower()
        items = [
            item
            for item in items
            if needle
            in " ".join(
                str(item.get(key) or "").lower()
                for key in ("title", "part_number", "category", "entity_id")
            )
        ]
    if entity_type != "all":
        items = [item for item in items if item["entity_type"] == entity_type]
    if priority != "all":
        items = [item for item in items if item["priority_tier"] == priority]
    if workflow_status != "all":
        items = [
            item for item in items if item["workflow_status"] == workflow_status
        ]
    if severity != "all":
        items = [item for item in items if item["severity"] == severity]
    if assignee and assignee.strip():
        owner = assignee.strip().lower()
        items = [
            item
            for item in items
            if str(item["assignee"] or "").lower() == owner
        ]

    max_due = datetime.max.replace(tzinfo=UTC)
    items.sort(
        key=lambda item: (
            -int(str(item["priority_score"])),
            item["due_at"] or max_due,
            item["created_at"],
            str(item["entity_type"]),
            str(item["entity_id"]),
        )
    )
    total = len(items)
    offset = (page - 1) * page_size
    return {
        "source_document_id": release.document_snapshot_id if release else None,
        "source_release_id": release.id if release else None,
        "source_release_version": release.version if release else None,
        "summary": summary,
        "items": items[offset : offset + page_size],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


async def _assert_active_target(
    entity_type: str,
    entity_id: str,
    db: AsyncSession,
) -> None:
    if entity_type == ENTITY_EXCEPTION:
        exception = await db.get(CommercialException, entity_id)
        active = exception is not None and exception.status == "open"
    elif entity_type == ENTITY_MAPPING_CANDIDATE:
        candidate = await db.get(CommercialMappingCandidate, entity_id)
        active = candidate is not None and candidate.status in {
            "blocked",
            "pending_review",
        }
    else:
        product = await db.scalar(
            select(ProductCoverageCandidate).where(
                ProductCoverageCandidate.product_key == entity_id,
                ProductCoverageCandidate.status == "pending_review",
            )
        )
        active = product is not None
    if not active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "COMMERCIAL_REVIEW_ITEM_NOT_FOUND",
                "message": "The unresolved commercial review item was not found.",
            },
        )


def _assignment_snapshot(
    assignment: CommercialReviewAssignment | None,
) -> dict[str, object] | None:
    if assignment is None:
        return None
    return {
        "entity_type": assignment.entity_type,
        "entity_id": assignment.entity_id,
        "assignee": assignment.assignee,
        "workflow_status": assignment.workflow_status,
        "due_at": _aware(assignment.due_at),
        "note": assignment.note,
        "updated_by": assignment.updated_by,
    }


async def replace_assignment(
    entity_type: str,
    entity_id: str,
    *,
    assignee: str | None,
    workflow_status: str,
    due_at: datetime | None,
    note: str | None,
    actor_id: str,
    db: AsyncSession,
) -> dict[str, object]:
    if entity_type not in ENTITY_TYPES or workflow_status not in WORKFLOW_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_COMMERCIAL_REVIEW_ASSIGNMENT",
                "message": "The entity type or workflow status is unsupported.",
            },
        )
    await _assert_active_target(entity_type, entity_id, db)
    assignment = await db.scalar(
        select(CommercialReviewAssignment).where(
            CommercialReviewAssignment.entity_type == entity_type,
            CommercialReviewAssignment.entity_id == entity_id,
        )
    )
    old_value = _assignment_snapshot(assignment)
    if assignment is None:
        assignment = CommercialReviewAssignment(
            entity_type=entity_type,
            entity_id=entity_id,
        )
        db.add(assignment)
    assignment.assignee = assignee
    assignment.workflow_status = workflow_status
    assignment.due_at = _aware(due_at)
    assignment.note = note.strip() if note and note.strip() else None
    assignment.updated_by = actor_id
    await db.flush()
    new_value = _assignment_snapshot(assignment)
    await audit_service.emit(
        "commercial_review_assignment_updated",
        "commercial_review_assignment",
        assignment.id,
        actor_id,
        old_value,
        new_value,
        None,
        db,
    )

    _, items = await _queue_context(db)
    item = next(
        (
            candidate
            for candidate in items
            if candidate["entity_type"] == entity_type
            and candidate["entity_id"] == entity_id
        ),
        None,
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "COMMERCIAL_REVIEW_ITEM_OUTSIDE_ACTIVE_RELEASE",
                "message": "The item is not part of the active global commercial release.",
            },
        )
    return item
