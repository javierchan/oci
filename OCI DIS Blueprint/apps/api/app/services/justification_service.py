"""Deterministic justification narrative assembly and template governance actions."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    CatalogIntegration,
    JustificationRecord,
    PatternDefinition,
    PromptTemplateVersion,
    SourceIntegrationRow,
)
from app.schemas.justification import (
    JustificationListResponse,
    JustificationNarrative,
    JustificationRecordResponse,
    MethodologyBlock,
    PromptTemplateVersionCreate,
    PromptTemplateVersionListResponse,
    PromptTemplateVersionResponse,
    PromptTemplateVersionUpdate,
)
from app.services import audit_service
from app.services.serializers import sanitize_for_json, split_csv


FALLBACK_TEMPLATE = {
    "summary": (
        "La integracion {interface_name} conecta {source_system} con {destination_system} "
        "y actualmente mantiene estado QA {qa_status}."
    ),
    "blocks": [
        {
            "title": "Contexto",
            "body": (
                "Interfaz {interface_id} para la marca {brand} dentro del proceso {business_process}. "
                "Opera con frecuencia {frequency} y {payload_text}."
            ),
        },
        {
            "title": "Patron",
            "body": "Se documenta {pattern_label}. Racional: {pattern_rationale}.",
        },
        {
            "title": "Implementacion",
            "body": (
                "Tipo {type}, trigger {trigger_type} y herramientas base {core_tools}. "
                "Politica de reintento: {retry_policy}."
            ),
        },
        {
            "title": "Gobierno QA",
            "body": "Estado QA {qa_status}. Observaciones: {qa_reasons}.",
        },
    ],
}


class _SafeFormatDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "No informado"


def _text(value: Optional[str], fallback: str = "No informado") -> str:
    if value is None:
        return fallback
    text = value.strip()
    return text or fallback


def _format_payload(payload_kb: Optional[float]) -> str:
    if payload_kb is None:
        return "payload no informado"
    return f"{payload_kb:g} KB por ejecucion"


def _pattern_label(pattern_id: Optional[str], pattern_names: dict[str, str]) -> str:
    if not pattern_id:
        return "patron pendiente de seleccion"
    name = pattern_names.get(pattern_id, pattern_id)
    return f"{pattern_id} {name}"


def serialize_prompt_template(template: PromptTemplateVersion) -> PromptTemplateVersionResponse:
    """Convert a stored prompt template version into its response schema."""

    return PromptTemplateVersionResponse(
        id=template.id,
        version=template.version,
        name=template.name,
        is_default=template.is_default,
        template_config=template.template_config,
        notes=template.notes,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _template_context(row: CatalogIntegration, pattern_names: dict[str, str]) -> dict[str, str]:
    return {
        "interface_name": _text(row.interface_name, "sin nombre"),
        "source_system": _text(row.source_system),
        "destination_system": _text(row.destination_system),
        "qa_status": _text(row.qa_status, "PENDING"),
        "interface_id": _text(row.interface_id, "sin ID formal"),
        "brand": _text(row.brand),
        "business_process": _text(row.business_process),
        "frequency": _text(row.frequency),
        "payload_text": _format_payload(row.payload_per_execution_kb),
        "pattern_label": _pattern_label(row.selected_pattern, pattern_names),
        "pattern_rationale": _text(row.pattern_rationale, "pendiente de documentar por arquitectura"),
        "type": _text(row.type),
        "trigger_type": _text(row.trigger_type),
        "core_tools": ", ".join(split_csv(row.core_tools)) if row.core_tools else "pendientes de definir",
        "retry_policy": _text(row.retry_policy, "pendiente"),
        "qa_reasons": ", ".join(row.qa_reasons or ["sin observaciones adicionales"]),
    }


def _narrative_from_row(
    row: CatalogIntegration,
    pattern_names: dict[str, str],
    template_config: dict[str, object],
    override_text: Optional[str] = None,
) -> JustificationNarrative:
    context = _SafeFormatDict(_template_context(row, pattern_names))
    summary_template = str(template_config.get("summary") or FALLBACK_TEMPLATE["summary"])
    blocks_config = template_config.get("blocks")
    blocks = blocks_config if isinstance(blocks_config, list) else FALLBACK_TEMPLATE["blocks"]

    methodology_blocks = [
        MethodologyBlock(
            title=str(block.get("title") or "Bloque"),
            body=str(block.get("body") or "").format_map(context),
        )
        for block in blocks
        if isinstance(block, dict)
    ]

    evidence = [
        f"interface_id={_text(row.interface_id, 'sin ID formal')}",
        f"source_system={_text(row.source_system)}",
        f"destination_system={_text(row.destination_system)}",
        f"frequency={_text(row.frequency)}",
        f"payload_kb={row.payload_per_execution_kb if row.payload_per_execution_kb is not None else 'N/A'}",
        f"selected_pattern={row.selected_pattern or 'UNASSIGNED'}",
    ]
    if row.source_row is not None and row.source_row.import_batch is not None:
        evidence.extend(
            [
                f"source_row_number={row.source_row.source_row_number}",
                f"import_batch_id={row.source_row.import_batch_id}",
                f"import_filename={row.source_row.import_batch.filename}",
            ]
        )

    return JustificationNarrative(
        summary=summary_template.format_map(context),
        methodology_blocks=methodology_blocks,
        evidence=evidence,
        qa_status=_text(row.qa_status, "PENDING"),
        qa_reasons=row.qa_reasons or [],
        override_text=override_text,
    )


def _response_from_record(record: JustificationRecord) -> JustificationRecordResponse:
    return JustificationRecordResponse(
        id=record.id,
        project_id=record.project_id,
        integration_id=record.integration_id,
        state=record.state,
        approved_by=record.approved_by,
        override_notes=record.override_notes,
        narrative=JustificationNarrative(**record.deterministic_text),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _transient_response(
    project_id: str,
    integration_id: str,
    narrative: JustificationNarrative,
) -> JustificationRecordResponse:
    return JustificationRecordResponse(
        id=None,
        project_id=project_id,
        integration_id=integration_id,
        state="draft",
        approved_by=None,
        override_notes=None,
        narrative=narrative,
        created_at=None,
        updated_at=None,
    )


async def _pattern_name_map(db: AsyncSession) -> dict[str, str]:
    patterns = await db.scalars(select(PatternDefinition).where(PatternDefinition.is_active.is_(True)))
    return {pattern.pattern_id: pattern.name for pattern in patterns.all()}


async def _default_template_config(db: AsyncSession) -> dict[str, object]:
    template = await db.scalar(
        select(PromptTemplateVersion).where(PromptTemplateVersion.is_default.is_(True))
    )
    if template is None:
        return FALLBACK_TEMPLATE
    return template.template_config


async def _load_integration(project_id: str, integration_id: str, db: AsyncSession) -> CatalogIntegration:
    row = await db.scalar(
        select(CatalogIntegration)
        .options(selectinload(CatalogIntegration.source_row).selectinload(SourceIntegrationRow.import_batch))
        .where(
            CatalogIntegration.project_id == project_id,
            CatalogIntegration.id == integration_id,
        )
    )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Catalog integration not found", "error_code": "CATALOG_INTEGRATION_NOT_FOUND"},
        )
    return row


async def _load_record(project_id: str, integration_id: str, db: AsyncSession) -> Optional[JustificationRecord]:
    return await db.scalar(
        select(JustificationRecord).where(
            JustificationRecord.project_id == project_id,
            JustificationRecord.integration_id == integration_id,
        )
    )


async def _load_prompt_template(version: str, db: AsyncSession) -> PromptTemplateVersion:
    template = await db.scalar(select(PromptTemplateVersion).where(PromptTemplateVersion.version == version))
    if template is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Prompt template version not found", "error_code": "PROMPT_TEMPLATE_NOT_FOUND"},
        )
    return template


async def _set_default_prompt_template(version: str, db: AsyncSession) -> None:
    templates = (await db.scalars(select(PromptTemplateVersion))).all()
    for template in templates:
        template.is_default = template.version == version
    await db.flush()


async def list_prompt_templates(db: AsyncSession) -> PromptTemplateVersionListResponse:
    """List versioned narrative templates."""

    templates = (
        await db.scalars(select(PromptTemplateVersion).order_by(PromptTemplateVersion.created_at.desc()))
    ).all()
    return PromptTemplateVersionListResponse(
        templates=[serialize_prompt_template(template) for template in templates],
        total=len(templates),
    )


async def get_prompt_template(version: str, db: AsyncSession) -> PromptTemplateVersionResponse:
    """Load one narrative template version."""

    template = await _load_prompt_template(version, db)
    return serialize_prompt_template(template)


async def create_prompt_template(
    body: PromptTemplateVersionCreate,
    actor_id: str,
    db: AsyncSession,
) -> PromptTemplateVersionResponse:
    """Create a new versioned narrative template."""

    existing = await db.scalar(select(PromptTemplateVersion.id).where(PromptTemplateVersion.version == body.version))
    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail={"detail": "Prompt template version already exists", "error_code": "PROMPT_TEMPLATE_EXISTS"},
        )
    template = PromptTemplateVersion(**body.model_dump())
    db.add(template)
    await db.flush()
    if body.is_default:
        await _set_default_prompt_template(body.version, db)
    await db.refresh(template)
    response = serialize_prompt_template(template)
    await audit_service.emit(
        event_type="prompt_template_created",
        entity_type="prompt_template_version",
        entity_id=template.id,
        actor_id=actor_id,
        old_value=None,
        new_value=response.model_dump(),
        project_id=None,
        db=db,
    )
    return response


async def update_prompt_template(
    version: str,
    body: PromptTemplateVersionUpdate,
    actor_id: str,
    db: AsyncSession,
) -> PromptTemplateVersionResponse:
    """Patch a narrative template version and audit the change."""

    template = await _load_prompt_template(version, db)
    patch = body.model_dump(exclude_none=True)
    if not patch:
        return serialize_prompt_template(template)

    old_value = serialize_prompt_template(template).model_dump()
    make_default = patch.pop("is_default", None)
    for field, value in patch.items():
        setattr(template, field, value)
    await db.flush()
    if make_default is True:
        await _set_default_prompt_template(version, db)
    elif make_default is False:
        template.is_default = False
        await db.flush()
    await db.refresh(template)
    response = serialize_prompt_template(template)
    await audit_service.emit(
        event_type="prompt_template_updated",
        entity_type="prompt_template_version",
        entity_id=template.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=response.model_dump(),
        project_id=None,
        db=db,
    )
    return response


async def set_default_prompt_template(
    version: str,
    actor_id: str,
    db: AsyncSession,
) -> PromptTemplateVersionResponse:
    """Promote one narrative template version to default."""

    template = await _load_prompt_template(version, db)
    old_value = serialize_prompt_template(template).model_dump()
    await _set_default_prompt_template(version, db)
    await db.refresh(template)
    response = serialize_prompt_template(template)
    await audit_service.emit(
        event_type="prompt_template_defaulted",
        entity_type="prompt_template_version",
        entity_id=template.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=response.model_dump(),
        project_id=None,
        db=db,
    )
    return response


async def list_justifications(project_id: str, db: AsyncSession) -> JustificationListResponse:
    """List one deterministic narrative per integration in source order."""

    pattern_names = await _pattern_name_map(db)
    template_config = await _default_template_config(db)
    rows = (
        await db.scalars(
            select(CatalogIntegration)
            .options(selectinload(CatalogIntegration.source_row).selectinload(SourceIntegrationRow.import_batch))
            .where(CatalogIntegration.project_id == project_id)
            .order_by(CatalogIntegration.seq_number, CatalogIntegration.created_at)
        )
    ).all()
    records = (
        await db.scalars(
            select(JustificationRecord).where(JustificationRecord.project_id == project_id)
        )
    ).all()
    record_map = {record.integration_id: record for record in records}

    responses: list[JustificationRecordResponse] = []
    for row in rows:
        record = record_map.get(row.id)
        if record is not None:
            responses.append(_response_from_record(record))
        else:
            responses.append(
                _transient_response(
                    project_id=project_id,
                    integration_id=row.id,
                    narrative=_narrative_from_row(row, pattern_names, template_config),
                )
            )
    return JustificationListResponse(records=responses, total=len(responses))


async def get_justification(
    project_id: str,
    integration_id: str,
    db: AsyncSession,
) -> JustificationRecordResponse:
    """Return one justification narrative, persisted when previously governed."""

    row = await _load_integration(project_id, integration_id, db)
    record = await _load_record(project_id, integration_id, db)
    if record is not None:
        return _response_from_record(record)

    pattern_names = await _pattern_name_map(db)
    template_config = await _default_template_config(db)
    return _transient_response(
        project_id=project_id,
        integration_id=integration_id,
        narrative=_narrative_from_row(row, pattern_names, template_config),
    )


async def approve_justification(
    project_id: str,
    integration_id: str,
    actor_id: str,
    db: AsyncSession,
) -> JustificationRecordResponse:
    """Persist or refresh a deterministic narrative and mark it approved."""

    row = await _load_integration(project_id, integration_id, db)
    record = await _load_record(project_id, integration_id, db)
    pattern_names = await _pattern_name_map(db)
    template_config = await _default_template_config(db)
    narrative = _narrative_from_row(row, pattern_names, template_config)

    old_value = _response_from_record(record).model_dump() if record is not None else None
    if record is None:
        record = JustificationRecord(
            project_id=project_id,
            integration_id=integration_id,
            state="approved",
            deterministic_text=sanitize_for_json(narrative.model_dump()),
            approved_by=actor_id,
            override_notes=None,
        )
        db.add(record)
    else:
        record.state = "approved"
        record.deterministic_text = sanitize_for_json(narrative.model_dump())
        record.approved_by = actor_id
        record.override_notes = None

    await db.flush()
    await db.refresh(record)
    new_value = _response_from_record(record).model_dump()
    await audit_service.emit(
        event_type="justification_approved",
        entity_type="justification_record",
        entity_id=record.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=new_value,
        project_id=project_id,
        db=db,
    )
    return _response_from_record(record)


async def override_justification(
    project_id: str,
    integration_id: str,
    actor_id: str,
    override_text: str,
    override_notes: Optional[str],
    db: AsyncSession,
) -> JustificationRecordResponse:
    """Persist an architect override while retaining the deterministic baseline."""

    row = await _load_integration(project_id, integration_id, db)
    record = await _load_record(project_id, integration_id, db)
    pattern_names = await _pattern_name_map(db)
    template_config = await _default_template_config(db)
    narrative = _narrative_from_row(
        row,
        pattern_names,
        template_config,
        override_text=override_text.strip(),
    )

    old_value = _response_from_record(record).model_dump() if record is not None else None
    if record is None:
        record = JustificationRecord(
            project_id=project_id,
            integration_id=integration_id,
            state="overridden",
            deterministic_text=sanitize_for_json(narrative.model_dump()),
            approved_by=actor_id,
            override_notes=override_notes,
        )
        db.add(record)
    else:
        record.state = "overridden"
        record.deterministic_text = sanitize_for_json(narrative.model_dump())
        record.approved_by = actor_id
        record.override_notes = override_notes

    await db.flush()
    await db.refresh(record)
    new_value = _response_from_record(record).model_dump()
    await audit_service.emit(
        event_type="justification_overridden",
        entity_type="justification_record",
        entity_id=record.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=new_value,
        project_id=project_id,
        db=db,
    )
    return _response_from_record(record)
