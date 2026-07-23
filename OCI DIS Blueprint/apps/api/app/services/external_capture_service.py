"""Governed pre-catalog review for structured external integration evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.calc_engine import evaluate_qa
from app.models import (
    ExternalCaptureDraft,
    ExternalCaptureSession,
    PatternDefinition,
    Project,
)
from app.schemas.catalog import ManualIntegrationCreate
from app.schemas.external_capture import (
    ExternalCaptureBulkResult,
    ExternalCaptureDraftBulkCreate,
    ExternalCaptureDraftPage,
    ExternalCaptureDraftPatch,
    ExternalCaptureDraftResponse,
    ExternalCaptureDraftReview,
    ExternalCapturePromotionResponse,
    ExternalCaptureSessionCreate,
    ExternalCaptureSessionDetail,
    ExternalCaptureSessionList,
    ExternalCaptureSessionResponse,
    ExternalCaptureSummary,
)
from app.services import audit_service, catalog_service


REQUIRED_CAPTURE_FIELDS = (
    "brand",
    "business_process",
    "interface_name",
    "source_system",
    "destination_system",
)


def _not_found(entity: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "detail": f"{entity} not found",
            "error_code": f"{entity.upper().replace(' ', '_')}_NOT_FOUND",
        },
    )


def _serialize_session(row: ExternalCaptureSession) -> ExternalCaptureSessionResponse:
    return ExternalCaptureSessionResponse(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        client_name=row.client_name,
        source_label=row.source_label,
        source_hash=row.source_hash,
        status=cast(Any, row.status),
        normalization_policy=row.normalization_policy or {},
        created_by=row.created_by,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _serialize_draft(row: ExternalCaptureDraft) -> ExternalCaptureDraftResponse:
    return ExternalCaptureDraftResponse(
        id=row.id,
        session_id=row.session_id,
        source_row_number=row.source_row_number,
        source_record=row.source_record or {},
        proposed_payload=row.proposed_payload or {},
        normalized_values=row.normalized_values or {},
        pattern_assessment=row.pattern_assessment or {},
        validation_evidence=row.validation_evidence or {},
        required_field_gaps=[str(value) for value in (row.required_field_gaps or [])],
        qa_preview=row.qa_preview or {},
        confidence=row.confidence,
        status=cast(Any, row.status),
        reviewer_rationale=row.reviewer_rationale,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        promoted_integration_id=row.promoted_integration_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _get_session(
    project_id: str,
    session_id: str,
    db: AsyncSession,
) -> ExternalCaptureSession:
    row = await db.scalar(
        select(ExternalCaptureSession).where(
            ExternalCaptureSession.id == session_id,
            ExternalCaptureSession.project_id == project_id,
        )
    )
    if row is None:
        raise _not_found("External capture session")
    return row


async def _get_draft(
    project_id: str,
    session_id: str,
    draft_id: str,
    db: AsyncSession,
) -> tuple[ExternalCaptureSession, ExternalCaptureDraft]:
    session = await _get_session(project_id, session_id, db)
    row = await db.scalar(
        select(ExternalCaptureDraft).where(
            ExternalCaptureDraft.id == draft_id,
            ExternalCaptureDraft.session_id == session.id,
        )
    )
    if row is None:
        raise _not_found("External capture draft")
    return session, row


async def _validate_payload(
    session: ExternalCaptureSession,
    payload: dict[str, Any],
    db: AsyncSession,
) -> tuple[dict[str, Any], list[str], dict[str, Any], dict[str, Any]]:
    canonical = dict(payload)
    if bool((session.normalization_policy or {}).get("force_tbq_y")):
        canonical["tbq"] = "Y"

    gaps = [
        field
        for field in REQUIRED_CAPTURE_FIELDS
        if not isinstance(canonical.get(field), str) or not str(canonical.get(field)).strip()
    ]
    schema_errors: list[dict[str, str]] = []
    validated: ManualIntegrationCreate | None = None
    try:
        validated = ManualIntegrationCreate.model_validate(canonical)
    except ValidationError as exc:
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            schema_errors.append(
                {
                    "field": location,
                    "message": str(error["msg"]),
                    "type": str(error["type"]),
                }
            )
            if location in REQUIRED_CAPTURE_FIELDS and location not in gaps:
                gaps.append(location)

    pattern_id = canonical.get("selected_pattern")
    pattern_valid = False
    if isinstance(pattern_id, str) and pattern_id.strip():
        pattern_valid = bool(
            await db.scalar(
                select(func.count())
                .select_from(PatternDefinition)
                .where(
                    PatternDefinition.pattern_id == pattern_id.strip(),
                    PatternDefinition.is_active.is_(True),
                )
            )
        )
    if not pattern_valid and "selected_pattern" not in gaps:
        gaps.append("selected_pattern")

    qa_preview: dict[str, Any] = {
        "status": "PENDING",
        "reasons": ["REQUIRED_CAPTURE_EVIDENCE_MISSING"] if gaps else [],
    }
    if validated is not None:
        core_tools = ", ".join(validated.core_tools or [])
        qa = evaluate_qa(
            interface_id=validated.interface_id,
            trigger_type=validated.type,
            selected_pattern=validated.selected_pattern,
            pattern_rationale=validated.pattern_rationale,
            core_tools=core_tools,
            payload_per_execution_kb=validated.payload_per_execution_kb,
            is_fan_out=validated.is_fan_out,
            fan_out_targets=validated.fan_out_targets,
            is_active_row=True,
            retry_policy=validated.retry_policy,
            idempotency=validated.idempotency,
            target_latency_sla=validated.target_latency_sla,
            data_security_classification=validated.data_security_classification,
            retention_processing_window=validated.retention_processing_window,
            business_criticality=validated.business_criticality,
            additional_tools_overlays=None,
        )
        qa_preview = {"status": qa.status, "reasons": qa.reasons}

    validation = {
        "schema_valid": validated is not None and not gaps,
        "schema_errors": schema_errors,
        "pattern_valid": pattern_valid,
        "tbq_forced_to_y": canonical.get("tbq") == "Y",
        "promotion_ready": validated is not None and not gaps and pattern_valid,
    }
    return canonical, sorted(set(gaps)), qa_preview, validation


async def _refresh_session_status(
    session: ExternalCaptureSession,
    db: AsyncSession,
) -> None:
    statuses = list(
        (
            await db.scalars(
                select(ExternalCaptureDraft.status).where(
                    ExternalCaptureDraft.session_id == session.id
                )
            )
        ).all()
    )
    if not statuses:
        session.status = "draft"
    elif any(status == "needs_review" for status in statuses):
        session.status = "in_review"
    else:
        session.status = "completed"
        session.reviewed_at = datetime.now(timezone.utc)


async def _summary(session_id: str, db: AsyncSession) -> ExternalCaptureSummary:
    rows = list(
        (
            await db.scalars(
                select(ExternalCaptureDraft).where(
                    ExternalCaptureDraft.session_id == session_id
                )
            )
        ).all()
    )
    return ExternalCaptureSummary(
        total=len(rows),
        schema_ready=sum(
            1 for row in rows if bool((row.validation_evidence or {}).get("promotion_ready"))
        ),
        missing_required=sum(1 for row in rows if bool(row.required_field_gaps)),
        qa_review=sum(
            1 for row in rows if (row.qa_preview or {}).get("status") == "REVISAR"
        ),
        pattern_changes=sum(
            1
            for row in rows
            if (row.pattern_assessment or {}).get("source_pattern")
            != (row.pattern_assessment or {}).get("recommended_pattern")
        ),
        needs_review=sum(1 for row in rows if row.status == "needs_review"),
        approved=sum(1 for row in rows if row.status == "approved"),
        rejected=sum(1 for row in rows if row.status == "rejected"),
        promoted=sum(1 for row in rows if row.status == "promoted"),
    )


async def create_session(
    project_id: str,
    body: ExternalCaptureSessionCreate,
    actor_id: str,
    db: AsyncSession,
) -> ExternalCaptureSessionDetail:
    if await db.get(Project, project_id) is None:
        raise _not_found("Project")
    duplicate = await db.scalar(
        select(ExternalCaptureSession).where(
            ExternalCaptureSession.project_id == project_id,
            ExternalCaptureSession.source_hash == body.source_hash,
        )
    )
    if duplicate is not None:
        return ExternalCaptureSessionDetail(
            session=_serialize_session(duplicate),
            summary=await _summary(duplicate.id, db),
        )
    row = ExternalCaptureSession(
        project_id=project_id,
        name=body.name,
        client_name=body.client_name,
        source_label=body.source_label,
        source_hash=body.source_hash,
        status="draft",
        normalization_policy=body.normalization_policy,
        created_by=actor_id,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    await audit_service.emit(
        event_type="external_capture_session_created",
        entity_type="external_capture_session",
        entity_id=row.id,
        actor_id=actor_id,
        old_value=None,
        new_value={
            "source_hash": row.source_hash,
            "source_label": row.source_label,
            "client_name": row.client_name,
        },
        project_id=project_id,
        db=db,
    )
    return ExternalCaptureSessionDetail(
        session=_serialize_session(row),
        summary=await _summary(row.id, db),
    )


async def list_sessions(
    project_id: str,
    db: AsyncSession,
) -> ExternalCaptureSessionList:
    rows = (
        await db.scalars(
            select(ExternalCaptureSession)
            .where(ExternalCaptureSession.project_id == project_id)
            .order_by(ExternalCaptureSession.created_at.desc())
        )
    ).all()
    return ExternalCaptureSessionList(
        sessions=[_serialize_session(row) for row in rows]
    )


async def get_session_detail(
    project_id: str,
    session_id: str,
    db: AsyncSession,
) -> ExternalCaptureSessionDetail:
    row = await _get_session(project_id, session_id, db)
    return ExternalCaptureSessionDetail(
        session=_serialize_session(row),
        summary=await _summary(row.id, db),
    )


async def bulk_upsert_drafts(
    project_id: str,
    session_id: str,
    body: ExternalCaptureDraftBulkCreate,
    actor_id: str,
    db: AsyncSession,
) -> ExternalCaptureBulkResult:
    session = await _get_session(project_id, session_id, db)
    existing = {
        row.source_row_number: row
        for row in (
            await db.scalars(
                select(ExternalCaptureDraft).where(
                    ExternalCaptureDraft.session_id == session.id
                )
            )
        ).all()
    }
    created = 0
    updated = 0
    for item in body.drafts:
        canonical, gaps, qa_preview, validation = await _validate_payload(
            session, item.proposed_payload, db
        )
        row = existing.get(item.source_row_number)
        if row is not None and row.status == "promoted":
            continue
        if row is None:
            row = ExternalCaptureDraft(
                session_id=session.id,
                source_row_number=item.source_row_number,
                source_record=item.source_record,
                proposed_payload=canonical,
                normalized_values=item.normalized_values,
                pattern_assessment=item.pattern_assessment,
                validation_evidence={**item.validation_evidence, **validation},
                required_field_gaps=gaps,
                qa_preview=qa_preview,
                confidence=item.confidence,
                status="needs_review",
            )
            db.add(row)
            created += 1
        else:
            row.source_record = item.source_record
            row.proposed_payload = canonical
            row.normalized_values = item.normalized_values
            row.pattern_assessment = item.pattern_assessment
            row.validation_evidence = {**item.validation_evidence, **validation}
            row.required_field_gaps = gaps
            row.qa_preview = qa_preview
            row.confidence = item.confidence
            row.status = "needs_review"
            row.reviewer_rationale = None
            row.reviewed_by = None
            row.reviewed_at = None
            updated += 1
    session.status = "in_review"
    await db.flush()
    await audit_service.emit(
        event_type="external_capture_drafts_staged",
        entity_type="external_capture_session",
        entity_id=session.id,
        actor_id=actor_id,
        old_value=None,
        new_value={"created": created, "updated": updated, "source_hash": session.source_hash},
        project_id=project_id,
        db=db,
    )
    summary = await _summary(session.id, db)
    return ExternalCaptureBulkResult(
        created=created,
        updated=updated,
        total=summary.total,
        summary=summary,
    )


async def list_drafts(
    project_id: str,
    session_id: str,
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    status: str | None,
    search: str | None,
) -> ExternalCaptureDraftPage:
    session = await _get_session(project_id, session_id, db)
    query = select(ExternalCaptureDraft).where(
        ExternalCaptureDraft.session_id == session.id
    )
    if status:
        query = query.where(ExternalCaptureDraft.status == status)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(
            or_(
                ExternalCaptureDraft.proposed_payload["interface_name"].as_string().ilike(like),
                ExternalCaptureDraft.proposed_payload["source_system"].as_string().ilike(like),
                ExternalCaptureDraft.proposed_payload["destination_system"].as_string().ilike(like),
            )
        )
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        await db.scalars(
            query.order_by(ExternalCaptureDraft.source_row_number)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return ExternalCaptureDraftPage(
        drafts=[_serialize_draft(row) for row in rows],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


async def patch_draft(
    project_id: str,
    session_id: str,
    draft_id: str,
    body: ExternalCaptureDraftPatch,
    actor_id: str,
    db: AsyncSession,
) -> ExternalCaptureDraftResponse:
    session, row = await _get_draft(project_id, session_id, draft_id, db)
    if row.status == "promoted":
        raise HTTPException(status_code=409, detail="Promoted drafts are immutable")
    old_value = _serialize_draft(row).model_dump(mode="json")
    patch = body.model_dump(exclude_unset=True)
    if "proposed_payload" in patch:
        canonical, gaps, qa_preview, validation = await _validate_payload(
            session, cast(dict[str, Any], patch["proposed_payload"]), db
        )
        row.proposed_payload = canonical
        row.required_field_gaps = gaps
        row.qa_preview = qa_preview
        row.validation_evidence = {
            **(row.validation_evidence or {}),
            **validation,
        }
    for field in ("normalized_values", "pattern_assessment", "confidence"):
        if field in patch:
            setattr(row, field, patch[field])
    row.status = "needs_review"
    row.reviewer_rationale = None
    row.reviewed_by = None
    row.reviewed_at = None
    session.status = "in_review"
    await db.flush()
    await db.refresh(row)
    result = _serialize_draft(row)
    await audit_service.emit(
        event_type="external_capture_draft_updated",
        entity_type="external_capture_draft",
        entity_id=row.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=result.model_dump(mode="json"),
        project_id=project_id,
        db=db,
    )
    return result


async def review_draft(
    project_id: str,
    session_id: str,
    draft_id: str,
    body: ExternalCaptureDraftReview,
    actor_id: str,
    db: AsyncSession,
) -> ExternalCaptureDraftResponse:
    session, row = await _get_draft(project_id, session_id, draft_id, db)
    if row.status == "promoted":
        raise HTTPException(status_code=409, detail="Promoted drafts are immutable")
    if body.decision == "approve" and not bool(
        (row.validation_evidence or {}).get("promotion_ready")
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Resolve required evidence and select a governed pattern before approval",
                "error_code": "EXTERNAL_CAPTURE_DRAFT_NOT_READY",
                "missing_fields": row.required_field_gaps or [],
            },
        )
    old_status = row.status
    row.status = "approved" if body.decision == "approve" else "rejected"
    row.reviewer_rationale = body.rationale
    row.reviewed_by = actor_id
    row.reviewed_at = datetime.now(timezone.utc)
    await db.flush()
    await _refresh_session_status(session, db)
    await audit_service.emit(
        event_type=f"external_capture_draft_{row.status}",
        entity_type="external_capture_draft",
        entity_id=row.id,
        actor_id=actor_id,
        old_value={"status": old_status},
        new_value={"status": row.status, "source_row_number": row.source_row_number},
        project_id=project_id,
        db=db,
    )
    return _serialize_draft(row)


async def promote_draft(
    project_id: str,
    session_id: str,
    draft_id: str,
    actor_id: str,
    db: AsyncSession,
) -> ExternalCapturePromotionResponse:
    session, row = await _get_draft(project_id, session_id, draft_id, db)
    if row.status != "approved":
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Only approved external-capture drafts can be promoted",
                "error_code": "EXTERNAL_CAPTURE_APPROVAL_REQUIRED",
            },
        )
    canonical, gaps, qa_preview, validation = await _validate_payload(
        session, row.proposed_payload, db
    )
    if gaps or not bool(validation["promotion_ready"]):
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "The approved draft no longer satisfies the current capture contract",
                "error_code": "EXTERNAL_CAPTURE_REVALIDATION_FAILED",
                "missing_fields": gaps,
            },
        )
    payload = ManualIntegrationCreate.model_validate(canonical)
    integration = await catalog_service.manual_create_integration(
        project_id, payload, actor_id, db
    )
    row.proposed_payload = canonical
    row.required_field_gaps = gaps
    row.qa_preview = qa_preview
    row.validation_evidence = {**(row.validation_evidence or {}), **validation}
    row.status = "promoted"
    row.promoted_integration_id = integration.id
    await db.flush()
    await _refresh_session_status(session, db)
    await audit_service.emit(
        event_type="external_capture_draft_promoted",
        entity_type="external_capture_draft",
        entity_id=row.id,
        actor_id=actor_id,
        old_value={"status": "approved"},
        new_value={
            "status": "promoted",
            "integration_id": integration.id,
            "source_row_number": row.source_row_number,
        },
        project_id=project_id,
        db=db,
    )
    return ExternalCapturePromotionResponse(
        draft=_serialize_draft(row),
        integration_id=integration.id,
    )


async def build_agent_evidence(
    project_id: str,
    session_id: str,
    db: AsyncSession,
) -> dict[str, object]:
    session = await _get_session(project_id, session_id, db)
    summary = await _summary(session.id, db)
    rows = list(
        (
            await db.scalars(
                select(ExternalCaptureDraft)
                .where(ExternalCaptureDraft.session_id == session.id)
                .order_by(ExternalCaptureDraft.source_row_number)
            )
        ).all()
    )
    gap_counts: dict[str, int] = {}
    qa_counts: dict[str, int] = {}
    for row in rows:
        for gap in row.required_field_gaps or []:
            gap_counts[str(gap)] = gap_counts.get(str(gap), 0) + 1
        for reason in (row.qa_preview or {}).get("reasons", []):
            qa_counts[str(reason)] = qa_counts.get(str(reason), 0) + 1
    return {
        "state": "external_capture_review",
        "session_id": session.id,
        "source_evidence_id": f"sha256:{session.source_hash}",
        "project_name": (await db.get(Project, project_id)).name,  # type: ignore[union-attr]
        "client_name": session.client_name,
        "summary": summary.model_dump(),
        "normalization_policy": session.normalization_policy,
        "top_required_gaps": sorted(
            ({"field": key, "rows": value} for key, value in gap_counts.items()),
            key=lambda item: cast(int, item["rows"]),
            reverse=True,
        )[:8],
        "top_qa_reasons": sorted(
            ({"reason": key, "rows": value} for key, value in qa_counts.items()),
            key=lambda item: cast(int, item["rows"]),
            reverse=True,
        )[:8],
        "sample_rows": [
            {
                "source_row_number": row.source_row_number,
                "interface_name": (row.proposed_payload or {}).get("interface_name"),
                "source_system": (row.proposed_payload or {}).get("source_system"),
                "destination_system": (row.proposed_payload or {}).get("destination_system"),
                "required_field_gaps": row.required_field_gaps,
                "pattern_assessment": row.pattern_assessment,
                "qa_preview": row.qa_preview,
            }
            for row in rows[:12]
        ],
        "recommended_next_action": (
            "Resolve required-field gaps and review every pattern assessment before approving any row. "
            "Promote only explicitly approved drafts to the canonical catalog."
        ),
        "prohibited_actions": [
            "invent_missing_customer_values",
            "approve_pattern_without_human_review",
            "upload_or_store_source_workbook",
            "promote_unapproved_draft",
        ],
    }
