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
    DictionaryOption,
    ExternalCaptureDraft,
    ExternalCaptureSession,
    PatternDefinition,
    Project,
)
from app.schemas.catalog import ManualIntegrationCreate
from app.schemas.external_capture import (
    ExternalCaptureAgentAnalysis,
    ExternalCaptureBulkResult,
    ExternalCaptureCorrectionApplyRequest,
    ExternalCaptureCorrectionBulkResult,
    ExternalCaptureCorrectionResultItem,
    ExternalCaptureDraftBulkCreate,
    ExternalCaptureIgnoredSourceField,
    ExternalCaptureDraftPage,
    ExternalCaptureDraftPatch,
    ExternalCaptureDraftResponse,
    ExternalCaptureDraftReview,
    ExternalCapturePromotionResponse,
    ExternalCaptureReviewTrigger,
    ExternalCaptureSessionCreate,
    ExternalCaptureSessionDetail,
    ExternalCaptureSessionList,
    ExternalCaptureSessionResponse,
    ExternalCaptureSummary,
)
from app.services import audit_service, catalog_service
from app.services.external_capture_review_service import (
    build_required_data_contract,
    build_review_triggers,
    evidence_hash,
    partition_source_record,
    strip_formula_values,
    summarize_review_triggers,
)


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
    source_record, legacy_ignored_source_fields = partition_source_record(
        row.source_record or {}
    )
    stored_ignored_source_fields = (row.validation_evidence or {}).get(
        "excluded_source_fields", []
    )
    ignored_source_fields_by_header = {
        str(field["source_header"]): field
        for field in legacy_ignored_source_fields
        if field.get("source_header")
    }
    if isinstance(stored_ignored_source_fields, list):
        for field in stored_ignored_source_fields:
            if isinstance(field, dict) and field.get("source_header"):
                ignored_source_fields_by_header[str(field["source_header"])] = field
    ignored_source_fields = list(ignored_source_fields_by_header.values())
    review_triggers = build_review_triggers(
        required_field_gaps=row.required_field_gaps or [],
        qa_preview=row.qa_preview or {},
        pattern_assessment=row.pattern_assessment or {},
        normalized_values=row.normalized_values or {},
    )
    ignored_source_models = [
        ExternalCaptureIgnoredSourceField.model_validate(field)
        for field in ignored_source_fields
    ]
    review_trigger_models = [
        ExternalCaptureReviewTrigger.model_validate(trigger)
        for trigger in review_triggers
    ]
    current_evidence_hash = evidence_hash(
        source_record=row.source_record or {},
        proposed_payload=row.proposed_payload or {},
        normalized_values=row.normalized_values or {},
        pattern_assessment=row.pattern_assessment or {},
        validation_evidence=row.validation_evidence or {},
        required_field_gaps=row.required_field_gaps or [],
        qa_preview=row.qa_preview or {},
    )
    analysis_payload = row.agent_analysis_payload or {}
    output_quality_value = analysis_payload.get("output_quality")
    output_quality: dict[str, object] = (
        cast(dict[str, object], output_quality_value)
        if isinstance(output_quality_value, dict)
        else {}
    )
    grounded = output_quality.get("grounded") is True
    fallback_used = output_quality.get("fallback_used") is True
    provider_status = analysis_payload.get("provider_status")
    correction_contract_valid = (
        analysis_payload.get("correction_contract_valid") is True
    )
    agent_row_analysis_value = analysis_payload.get("agent_row_analysis")
    agent_row_analysis: dict[str, object] = (
        cast(dict[str, object], agent_row_analysis_value)
        if isinstance(agent_row_analysis_value, dict)
        else {}
    )
    proposed_patch_value = agent_row_analysis.get("proposed_patch")
    proposed_patch: dict[str, object] = (
        cast(dict[str, object], proposed_patch_value)
        if isinstance(proposed_patch_value, dict)
        else {}
    )
    required_decisions_value = agent_row_analysis.get("required_decisions")
    required_decisions = (
        [str(value) for value in required_decisions_value if str(value).strip()]
        if isinstance(required_decisions_value, list)
        else []
    )
    no_op_fields_value = agent_row_analysis.get("no_op_patch_fields")
    no_op_fields = (
        sorted(str(value) for value in no_op_fields_value if str(value).strip())
        if isinstance(no_op_fields_value, list)
        else []
    )
    if row.agent_analysis_run_id is None:
        analysis_status = "required"
    elif row.agent_analysis_evidence_hash != current_evidence_hash:
        analysis_status = "stale"
    elif (
        provider_status != "completed"
        or not grounded
        or fallback_used
        or not correction_contract_valid
    ):
        analysis_status = "degraded"
    else:
        analysis_status = "current"
    return ExternalCaptureDraftResponse(
        id=row.id,
        session_id=row.session_id,
        source_row_number=row.source_row_number,
        source_record=source_record,
        ignored_source_fields=ignored_source_models,
        proposed_payload=row.proposed_payload or {},
        normalized_values=row.normalized_values or {},
        pattern_assessment=row.pattern_assessment or {},
        validation_evidence=row.validation_evidence or {},
        required_field_gaps=[str(value) for value in (row.required_field_gaps or [])],
        qa_preview=row.qa_preview or {},
        review_triggers=review_trigger_models,
        review_summary=summarize_review_triggers(review_triggers),
        approval_blocked=any(
            trigger["blocks_approval"] is True for trigger in review_triggers
        ),
        agent_analysis=ExternalCaptureAgentAnalysis(
            status=cast(Any, analysis_status),
            run_id=row.agent_analysis_run_id,
            summary=(
                str(analysis_payload["summary"])
                if analysis_payload.get("summary")
                else None
            ),
            provider_status=(
                str(provider_status) if provider_status is not None else None
            ),
            grounded=grounded,
            fallback_used=fallback_used,
            correction_available=analysis_status == "current" and bool(proposed_patch),
            correction_fields=sorted(str(field) for field in proposed_patch),
            required_decisions=required_decisions,
            no_op_fields=no_op_fields,
            analyzed_at=row.agent_analyzed_at,
        ),
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
    cleaned_payload, excluded_formula_fields = strip_formula_values(payload)
    canonical = (
        cast(dict[str, Any], cleaned_payload)
        if isinstance(cleaned_payload, dict)
        else {}
    )
    force_tbq_y = bool((session.normalization_policy or {}).get("force_tbq_y"))
    if force_tbq_y:
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
        "tbq_forced_to_y": force_tbq_y,
        "tbq_value_is_y": canonical.get("tbq") == "Y",
        "promotion_ready": validated is not None and not gaps and pattern_valid,
        "excluded_operational_formula_fields": excluded_formula_fields,
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


def _has_pattern_change(row: ExternalCaptureDraft) -> bool:
    assessment = row.pattern_assessment or {}
    source_value = assessment.get("source_pattern")
    recommended_value = assessment.get("recommended_pattern")
    source = source_value.strip() if isinstance(source_value, str) else ""
    recommended = (
        recommended_value.strip()
        if isinstance(recommended_value, str)
        else ""
    )
    return bool(source and recommended and source != recommended)


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
    serialized_rows = [_serialize_draft(row) for row in rows]
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
            if _has_pattern_change(row)
        ),
        needs_review=sum(1 for row in rows if row.status == "needs_review"),
        approved=sum(1 for row in rows if row.status == "approved"),
        rejected=sum(1 for row in rows if row.status == "rejected"),
        promoted=sum(1 for row in rows if row.status == "promoted"),
        analyses_current=sum(
            1
            for row in serialized_rows
            if row.agent_analysis.status == "current"
        ),
        corrections_available=sum(
            1
            for row in serialized_rows
            if row.agent_analysis.correction_available
        ),
        human_decision_rows=sum(
            1
            for row in serialized_rows
            if row.agent_analysis.required_decisions
            or not row.agent_analysis.correction_available
        ),
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
        supported_source_record, excluded_source_fields = partition_source_record(
            item.source_record
        )
        validation_evidence = {
            **item.validation_evidence,
            **validation,
            "excluded_source_fields": excluded_source_fields,
        }
        row = existing.get(item.source_row_number)
        if row is not None and row.status == "promoted":
            continue
        if row is None:
            row = ExternalCaptureDraft(
                session_id=session.id,
                source_row_number=item.source_row_number,
                source_record=supported_source_record,
                proposed_payload=canonical,
                normalized_values=item.normalized_values,
                pattern_assessment=item.pattern_assessment,
                validation_evidence=validation_evidence,
                required_field_gaps=gaps,
                qa_preview=qa_preview,
                confidence=item.confidence,
                status="needs_review",
            )
            db.add(row)
            created += 1
        else:
            row.source_record = supported_source_record
            row.proposed_payload = canonical
            row.normalized_values = item.normalized_values
            row.pattern_assessment = item.pattern_assessment
            row.validation_evidence = validation_evidence
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
    analysis = _serialize_draft(row).agent_analysis
    if body.decision == "approve" and analysis.status != "current":
        raise HTTPException(
            status_code=409,
            detail={
                "detail": (
                    "Run a grounded Import Correction Agent analysis for the current "
                    "row evidence before approval"
                ),
                "error_code": "EXTERNAL_CAPTURE_AGENT_ANALYSIS_REQUIRED",
                "analysis_status": analysis.status,
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


async def record_agent_analysis(
    *,
    project_id: str,
    session_id: str,
    draft_id: str,
    run_id: str,
    analyzed_evidence_hash: str,
    analysis_payload: dict[str, object],
    actor_id: str,
    db: AsyncSession,
) -> None:
    """Link an immutable agent run to the row evidence it analyzed."""

    _, row = await _get_draft(project_id, session_id, draft_id, db)
    previous_run_id = row.agent_analysis_run_id
    row.agent_analysis_run_id = run_id
    row.agent_analysis_evidence_hash = analyzed_evidence_hash
    row.agent_analysis_payload = analysis_payload
    row.agent_analyzed_at = datetime.now(timezone.utc)
    await db.flush()
    await audit_service.emit(
        event_type="external_capture_agent_analysis_linked",
        entity_type="external_capture_draft",
        entity_id=row.id,
        actor_id=actor_id,
        old_value={"agent_analysis_run_id": previous_run_id},
        new_value={
            "agent_analysis_run_id": run_id,
            "evidence_hash": analyzed_evidence_hash,
            "provider_status": analysis_payload.get("provider_status"),
            "grounded": (
                cast(dict[str, object], analysis_payload.get("output_quality", {})).get(
                    "grounded"
                )
                is True
            ),
        },
        project_id=project_id,
        correlation_id=run_id,
        db=db,
    )


async def apply_agent_correction(
    *,
    project_id: str,
    session_id: str,
    draft_id: str,
    analyzed_evidence_hash: str,
    proposed_patch: dict[str, object],
    actor_id: str,
    db: AsyncSession,
) -> ExternalCaptureDraftResponse:
    """Apply a human-authorized, formula-free correction proposal and revalidate."""

    _, row = await _get_draft(project_id, session_id, draft_id, db)
    current_hash = evidence_hash(
        source_record=row.source_record or {},
        proposed_payload=row.proposed_payload or {},
        normalized_values=row.normalized_values or {},
        pattern_assessment=row.pattern_assessment or {},
        validation_evidence=row.validation_evidence or {},
        required_field_gaps=row.required_field_gaps or [],
        qa_preview=row.qa_preview or {},
    )
    if (
        analyzed_evidence_hash != current_hash
        or row.agent_analysis_evidence_hash != analyzed_evidence_hash
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "detail": (
                    "The row changed after the agent prepared this correction; "
                    "run the agent again before execution"
                ),
                "error_code": "EXTERNAL_CAPTURE_AGENT_CORRECTION_STALE",
            },
        )
    cleaned_patch, excluded_formula_fields = strip_formula_values(proposed_patch)
    if excluded_formula_fields:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "Agent correction drafts cannot contain formulas",
                "error_code": "EXTERNAL_CAPTURE_AGENT_FORMULA_REJECTED",
                "fields": excluded_formula_fields,
            },
        )
    patch = cast(dict[str, Any], cleaned_patch)
    unsupported_fields = sorted(
        set(patch) - set(ManualIntegrationCreate.model_fields)
    )
    if unsupported_fields:
        raise HTTPException(
            status_code=422,
            detail={
                "detail": "Agent correction contains unsupported App fields",
                "error_code": "EXTERNAL_CAPTURE_AGENT_FIELD_REJECTED",
                "fields": unsupported_fields,
            },
        )
    merged_payload = {**(row.proposed_payload or {}), **patch}
    return await patch_draft(
        project_id,
        session_id,
        draft_id,
        ExternalCaptureDraftPatch(proposed_payload=merged_payload),
        actor_id,
        db,
    )


async def apply_agent_corrections(
    *,
    project_id: str,
    session_id: str,
    body: ExternalCaptureCorrectionApplyRequest,
    actor_id: str,
    db: AsyncSession,
) -> ExternalCaptureCorrectionBulkResult:
    """Apply current grounded correction drafts after one explicit human action.

    This operation never approves, rejects, or promotes a row. Every candidate is
    rechecked against its current evidence hash and the existing typed correction
    boundary immediately before application.
    """

    session = await _get_session(project_id, session_id, db)
    rows = list(
        (
            await db.scalars(
                select(ExternalCaptureDraft)
                .where(ExternalCaptureDraft.session_id == session.id)
                .order_by(ExternalCaptureDraft.source_row_number)
            )
        ).all()
    )
    if body.scope == "selected":
        if not body.draft_ids:
            raise HTTPException(
                status_code=422,
                detail={
                    "detail": "Selected correction scope requires at least one draft ID",
                    "error_code": "EXTERNAL_CAPTURE_CORRECTION_SELECTION_REQUIRED",
                },
            )
        requested_ids = set(body.draft_ids)
        known_ids = {row.id for row in rows}
        unknown_ids = sorted(requested_ids - known_ids)
        if unknown_ids:
            raise HTTPException(
                status_code=404,
                detail={
                    "detail": "One or more selected correction drafts were not found",
                    "error_code": "EXTERNAL_CAPTURE_CORRECTION_DRAFT_NOT_FOUND",
                    "draft_ids": unknown_ids,
                },
            )
        rows = [row for row in rows if row.id in requested_ids]

    initial_states = [(row, _serialize_draft(row)) for row in rows]
    eligible = sum(
        1 for _, serialized in initial_states if serialized.agent_analysis.correction_available
    )
    human_decision_rows = sum(
        1
        for _, serialized in initial_states
        if serialized.agent_analysis.required_decisions
        or not serialized.agent_analysis.correction_available
    )
    results: list[ExternalCaptureCorrectionResultItem] = []
    for row, serialized in initial_states:
        analysis = serialized.agent_analysis
        if row.status == "promoted":
            results.append(
                ExternalCaptureCorrectionResultItem(
                    draft_id=row.id,
                    source_row_number=row.source_row_number,
                    status="skipped",
                    correction_fields=[],
                    reason_code="PROMOTED_DRAFT_IMMUTABLE",
                )
            )
            continue
        if analysis.status != "current":
            results.append(
                ExternalCaptureCorrectionResultItem(
                    draft_id=row.id,
                    source_row_number=row.source_row_number,
                    status="skipped",
                    correction_fields=[],
                    reason_code=f"AGENT_ANALYSIS_{analysis.status.upper()}",
                )
            )
            continue
        analysis_payload = row.agent_analysis_payload or {}
        agent_analysis_value = analysis_payload.get("agent_row_analysis")
        agent_analysis = (
            cast(dict[str, object], agent_analysis_value)
            if isinstance(agent_analysis_value, dict)
            else {}
        )
        patch_value = agent_analysis.get("proposed_patch")
        patch = (
            cast(dict[str, object], patch_value)
            if isinstance(patch_value, dict)
            else {}
        )
        if not patch:
            results.append(
                ExternalCaptureCorrectionResultItem(
                    draft_id=row.id,
                    source_row_number=row.source_row_number,
                    status="skipped",
                    correction_fields=[],
                    reason_code="HUMAN_DECISION_REQUIRED",
                )
            )
            continue
        try:
            await apply_agent_correction(
                project_id=project_id,
                session_id=session_id,
                draft_id=row.id,
                analyzed_evidence_hash=str(row.agent_analysis_evidence_hash or ""),
                proposed_patch=patch,
                actor_id=actor_id,
                db=db,
            )
        except HTTPException as exc:
            detail: dict[str, object] = (
                cast(dict[str, object], exc.detail)
                if isinstance(exc.detail, dict)
                else {}
            )
            results.append(
                ExternalCaptureCorrectionResultItem(
                    draft_id=row.id,
                    source_row_number=row.source_row_number,
                    status="failed",
                    correction_fields=sorted(str(field) for field in patch),
                    reason_code=str(
                        detail.get(
                            "error_code",
                            "EXTERNAL_CAPTURE_CORRECTION_FAILED",
                        )
                    ),
                )
            )
            continue
        results.append(
            ExternalCaptureCorrectionResultItem(
                draft_id=row.id,
                source_row_number=row.source_row_number,
                status="applied",
                correction_fields=sorted(str(field) for field in patch),
                reason_code="CORRECTION_APPLIED_REANALYSIS_REQUIRED",
            )
        )

    applied = sum(1 for result in results if result.status == "applied")
    skipped = sum(1 for result in results if result.status == "skipped")
    failed = sum(1 for result in results if result.status == "failed")
    await audit_service.emit(
        event_type="external_capture_agent_corrections_applied",
        entity_type="external_capture_session",
        entity_id=session.id,
        actor_id=actor_id,
        old_value=None,
        new_value={
            "scope": body.scope,
            "requested": len(rows),
            "eligible": eligible,
            "applied": applied,
            "skipped": skipped,
            "failed": failed,
            "human_decision_rows": human_decision_rows,
        },
        project_id=project_id,
        db=db,
    )
    return ExternalCaptureCorrectionBulkResult(
        requested=len(rows),
        eligible=eligible,
        applied=applied,
        skipped=skipped,
        failed=failed,
        human_decision_rows=human_decision_rows,
        results=results,
        summary=await _summary(session.id, db),
    )


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
    draft_id: str | None,
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
    focused_row = next((row for row in rows if row.id == draft_id), None)
    if draft_id is not None and focused_row is None:
        raise _not_found("External capture draft")
    gap_counts: dict[str, int] = {}
    qa_counts: dict[str, int] = {}
    for row in rows:
        for gap in row.required_field_gaps or []:
            gap_counts[str(gap)] = gap_counts.get(str(gap), 0) + 1
        for reason in (row.qa_preview or {}).get("reasons", []):
            qa_counts[str(reason)] = qa_counts.get(str(reason), 0) + 1
    payload: dict[str, object] = {
        "state": "external_capture_review",
        "review_scope": "single_row" if focused_row is not None else "session",
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
        # A focused row review is a strict single-row privacy boundary. Session
        # samples are useful for aggregate review, but must not accompany a
        # customer-derived focused row to the external provider.
        "sample_rows": (
            []
            if focused_row is not None
            else [
                {
                    "draft_id": serialized.id,
                    "source_row_number": serialized.source_row_number,
                    "interface_name": serialized.proposed_payload.get(
                        "interface_name"
                    ),
                    "source_system": serialized.proposed_payload.get("source_system"),
                    "destination_system": serialized.proposed_payload.get(
                        "destination_system"
                    ),
                    "review_summary": serialized.review_summary,
                    "review_triggers": [
                        trigger.model_dump(mode="json")
                        for trigger in serialized.review_triggers
                    ],
                    "pattern_assessment": serialized.pattern_assessment,
                    "qa_preview": serialized.qa_preview,
                }
                for serialized in (_serialize_draft(row) for row in rows[:12])
            ]
        ),
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
    if focused_row is not None:
        serialized = _serialize_draft(focused_row)
        dictionary_rows = list(
            (
                await db.scalars(
                    select(DictionaryOption)
                    .where(DictionaryOption.is_active.is_(True))
                    .order_by(
                        DictionaryOption.category,
                        DictionaryOption.sort_order,
                        DictionaryOption.value,
                    )
                )
            ).all()
        )
        governed_options: dict[str, list[dict[str, object]]] = {}
        for option in dictionary_rows:
            governed_options.setdefault(option.category, []).append(
                {
                    "code": option.code or "",
                    "value": option.value,
                }
            )
        pattern_rows = list(
            (
                await db.scalars(
                    select(PatternDefinition)
                    .where(PatternDefinition.is_active.is_(True))
                    .order_by(PatternDefinition.pattern_id)
                )
            ).all()
        )
        focused_evidence_hash = evidence_hash(
            source_record=focused_row.source_record or {},
            proposed_payload=focused_row.proposed_payload or {},
            normalized_values=focused_row.normalized_values or {},
            pattern_assessment=focused_row.pattern_assessment or {},
            validation_evidence=focused_row.validation_evidence or {},
            required_field_gaps=focused_row.required_field_gaps or [],
            qa_preview=focused_row.qa_preview or {},
        )
        payload["focused_row"] = {
            "draft_id": serialized.id,
            "source_row_number": serialized.source_row_number,
            "interface_name": serialized.proposed_payload.get("interface_name"),
            "source_system": serialized.proposed_payload.get("source_system"),
            "destination_system": serialized.proposed_payload.get(
                "destination_system"
            ),
            "supported_source_evidence": serialized.source_record,
            "data_received": {
                "supported_source_evidence": serialized.source_record,
                "proposed_app_record": serialized.proposed_payload,
                "normalization_decisions": serialized.normalized_values,
                "excluded_source_fields": [
                    {
                        "source_header": field.source_header,
                        "classification": field.classification,
                    }
                    for field in serialized.ignored_source_fields
                ],
            },
            "data_required": build_required_data_contract(
                serialized.proposed_payload,
                governed_options=governed_options,
                governed_patterns=[
                    {
                        "pattern_id": pattern.pattern_id,
                        "name": pattern.name,
                    }
                    for pattern in pattern_rows
                ],
            ),
            "analysis_evidence_hash": focused_evidence_hash,
            "proposed_pattern": serialized.proposed_payload.get("selected_pattern"),
            "current_pattern_rationale": serialized.proposed_payload.get(
                "pattern_rationale"
            ),
            "pattern_assessment": serialized.pattern_assessment,
            "review_summary": serialized.review_summary,
            "review_triggers": [
                trigger.model_dump(mode="json")
                for trigger in serialized.review_triggers
            ],
            "ignored_source_fields": [
                {
                    "source_header": field.source_header,
                    "classification": field.classification,
                    "reason": field.reason,
                }
                for field in serialized.ignored_source_fields
            ],
            "qa_preview": serialized.qa_preview,
            "approval_blocked": serialized.approval_blocked,
        }
        payload["recommended_next_action"] = (
            "Explain why this specific line needs review, cite only the supplied "
            "row evidence, and state the minimum human decision required."
        )
    return payload
