"""Session-isolated contextual support conversation services."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal, cast
from urllib.parse import quote
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssumptionSet,
    BomSnapshot,
    CatalogIntegration,
    DashboardSnapshot,
    DeploymentScenario,
    DictionaryOption,
    ImportBatch,
    PatternDefinition,
    Project,
    ServiceCapabilityProfile,
    SupportAttachment,
    SupportConversation,
    SupportMessage,
)
from app.models.project import ProjectStatus
from app.schemas.agent import (
    SupportAttachmentResponse,
    SupportConversationResponse,
    SupportMessageCreateRequest,
    SupportMessageResponse,
)
from app.services import audit_service
from app.services.serializers import sanitize_for_json


OUT_OF_SCOPE_RESPONSE = (
    "I’m here to help with OCI DIS Architect and the architecture work inside it. "
    "Ask me about a project, integration, business process, topology, Service Product, volumetry, "
    "pricing, BOM, or how to use this workspace."
)
APP_DOMAIN_PATTERN = re.compile(
    r"\b(oci|dis|architect|app|application|project|integration|interface|catalog|capture|import|dashboard|"
    r"map|topology|canvas|pattern|service|product|volumetry|payload|frequency|qa|governance|assumption|"
    r"pricing|price|cost|precio|costo|bom|bill of materials|sku|scenario|escenario|agent|review|export|"
    r"workbook|oracle|proyecto|proyectos|streaming|"
    r"queue|functions|goldengate|data integrator|api gateway)\b",
    re.IGNORECASE,
)
REFERENTIAL_PATTERN = re.compile(
    r"\b(this|that|these|those|current|here|screen|page|view|selected|it|esto|esta|este|aqui|pantalla|vista)\b",
    re.IGNORECASE,
)
OUTSIDE_TOPIC_PATTERN = re.compile(
    r"\b(weather|forecast outside|sports|score|recipe|poem|song|politics|president|celebrity|horoscope|"
    r"clima|deportes|receta|poema|cancion|politica|presidente|celebridad|horoscopo)\b",
    re.IGNORECASE,
)
MARKDOWN_TABLE_PATTERN = re.compile(r"(?m)^\s*\|.+\|\s*$")
INTERNAL_PLACEHOLDER_PATTERN = re.compile(
    r"\[(?:redacted|removed)\]|\{(?:project|integration)_id\}",
    re.IGNORECASE,
)
UNGROUNDED_SENSITIVE_TERMS: tuple[str, ...] = (
    "gdpr",
    "hipaa",
    "pci dss",
    "soc 2",
    "sanction",
    "sanción",
    "sancion",
)
UNGROUNDED_ACTION_TERMS: tuple[str, ...] = (
    "approve",
    "approval",
    "aprobar",
    "aprobación",
    "aprobacion",
    "deploy",
    "deployment",
    "despliegue",
    "production test",
    "prueba en producción",
    "prueba en produccion",
)
SPANISH_QUESTION_PATTERN = re.compile(
    r"[¿¡áéíóúñ]|\b(qué|que|cómo|como|cuál|cual|dónde|donde|esta|este|integración|proceso|ayuda|siguiente)\b",
    re.IGNORECASE,
)
PROJECT_PORTFOLIO_PATTERN = re.compile(
    r"\b(how many|list|show|which|cu[aá]ntos|lista|muestra|cu[aá]les)\b.{0,28}\b(projects?|proyectos?)\b",
    re.IGNORECASE,
)
PROJECT_SCOPE_PATTERN = re.compile(
    r"\b(this|current|selected|active|este|esta|actual|seleccionado|activo)\b.{0,24}\b(project|proyecto)\b|"
    r"\b(project|proyecto|pricing|price|cost|precio|costo|bom|bill of materials|dashboard|qa|risk|riesgo|"
    r"scenario|escenario|import|importaci[oó]n|business process|proceso de negocio)\b",
    re.IGNORECASE,
)
PROJECT_ROUTE_PATTERN = re.compile(r"/projects/([0-9a-f-]{36})(?:/|$)", re.IGNORECASE)

APP_SECTIONS: tuple[dict[str, str], ...] = (
    {"name": "Projects", "route": "/projects", "purpose": "Open and manage independent architecture assessments."},
    {"name": "Dashboard", "route": "/projects/{project_id}", "purpose": "Review coverage, products, maturity, and prioritized risks."},
    {"name": "Import", "route": "/projects/{project_id}/import", "purpose": "Download, upload, trace, and review governed workbook capture."},
    {"name": "Capture", "route": "/projects/{project_id}/capture", "purpose": "Define an integration through the governed capture workflow."},
    {"name": "Catalog", "route": "/projects/{project_id}/catalog", "purpose": "Review integration definitions, lineage, QA, patterns, and design decisions."},
    {"name": "Map", "route": "/projects/{project_id}/graph", "purpose": "Investigate system dependencies, paths, concentration, and blast radius."},
    {"name": "BOM & Cost", "route": "/projects/{project_id}/bom", "purpose": "Build governed deployment scenarios and immutable OCI estimates."},
    {"name": "Library", "route": "/admin", "purpose": "Govern patterns, dictionaries, assumptions, Service Products, pricing, and agents."},
)


def validate_support_session_id(value: str) -> str:
    """Require a canonical UUID so callers cannot probe another session namespace."""

    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"detail": "Invalid support session", "error_code": "SUPPORT_SESSION_INVALID"},
        ) from exc
    return str(parsed)


def question_is_in_scope(question: str, *, has_context: bool) -> bool:
    """Apply a conservative deterministic App-domain boundary before inference."""

    normalized = question.strip()
    if not normalized:
        return False
    if OUTSIDE_TOPIC_PATTERN.search(normalized):
        return False
    if APP_DOMAIN_PATTERN.search(normalized):
        return True
    if normalized.lower() in {"hello", "hi", "help", "hola", "ayuda", "what can you do?", "que puedes hacer?"}:
        return True
    return has_context and bool(REFERENTIAL_PATTERN.search(normalized))


def support_summary_is_grounded(summary: str, evidence: dict[str, object]) -> bool:
    """Reject verbose or sensitive support synthesis not supported by tool evidence."""

    normalized_summary = summary.casefold()
    serialized_evidence = str(sanitize_for_json(evidence)).casefold()
    if (
        len(summary.split()) > 280
        or MARKDOWN_TABLE_PATTERN.search(summary)
        or INTERNAL_PLACEHOLDER_PATTERN.search(summary)
    ):
        return False
    if any(term in normalized_summary and term not in serialized_evidence for term in UNGROUNDED_SENSITIVE_TERMS):
        return False
    recommended_action = ""
    integration = evidence.get("integration")
    if isinstance(integration, dict):
        recommended_action = str(integration.get("recommended_next_action") or "").casefold()
    return not any(
        term in normalized_summary and term not in recommended_action
        for term in UNGROUNDED_ACTION_TERMS
    )


def _question_needs_project_scope(question: str) -> bool:
    """Distinguish project dossiers from portfolio-level discovery questions."""

    return not bool(PROJECT_PORTFOLIO_PATTERN.search(question)) and bool(
        PROJECT_SCOPE_PATTERN.search(question)
    )


def _project_id_from_attachments(attachments: list[object]) -> str | None:
    """Read only explicit App-owned project references from attached route context."""

    for attachment in reversed(attachments[:8]):
        if not isinstance(attachment, dict):
            continue
        attachment_type = str(attachment.get("attachment_type") or "")
        entity_id = attachment.get("entity_id")
        if attachment_type == "project" and isinstance(entity_id, str):
            return entity_id
        context = attachment.get("context")
        if isinstance(context, dict) and isinstance(context.get("project_id"), str):
            return str(context["project_id"])
        href = str(attachment.get("href") or "")
        match = PROJECT_ROUTE_PATTERN.search(href)
        if match:
            return match.group(1)
    return None


def _project_name_match(
    projects: list[Project],
    question: str,
    transcript: list[object],
) -> Project | None:
    """Resolve an explicitly named project from the current or recent user questions."""

    user_text = " ".join(
        str(item.get("content") or "")
        for item in transcript[:12]
        if isinstance(item, dict) and item.get("role") == "user"
    )
    searchable = f"{question} {user_text}".casefold()
    matches = [project for project in projects if project.name.casefold() in searchable]
    return max(matches, key=lambda item: len(item.name)) if matches else None


def _money(value: object, currency: object) -> str:
    """Format governed commercial values without assuming a currency symbol."""

    try:
        amount = float(value) if isinstance(value, (int, float, str)) else 0.0
    except (TypeError, ValueError):
        amount = 0.0
    return f"{str(currency or 'USD').upper()} {amount:,.2f}"


def _support_fallback_answer(evidence: dict[str, object]) -> str:
    """Build a concise App-owned answer when provider grounding is insufficient."""

    spanish = evidence.get("response_language") == "es"
    integration = evidence.get("integration")
    process = evidence.get("business_process_flow")
    if isinstance(integration, dict):
        name = str(integration.get("name") or integration.get("interface_id") or "This integration")
        source = str(integration.get("source_system") or "an uncaptured source")
        destination = str(integration.get("destination_system") or "an uncaptured destination")
        process_name = str(integration.get("business_process") or "an uncaptured business process")
        lines = [
            f"{name} mueve datos gobernados de {source} a {destination} dentro de {process_name}."
            if spanish
            else f"{name} moves governed data from {source} to {destination} within {process_name}.",
        ]
        if isinstance(process, dict):
            predecessor = process.get("captured_predecessor")
            successor = process.get("captured_successor")
            if spanish:
                lines.append(
                    f"Antes: {predecessor}."
                    if predecessor
                    else "Antes: no hay una integración precedente capturada en este proceso."
                )
                lines.append(
                    f"Después: {successor}."
                    if successor
                    else "Después: no hay una integración posterior capturada en este proceso."
                )
            else:
                lines.append(
                    f"Before: {predecessor}."
                    if predecessor
                    else "Before: no preceding integration is captured in this process."
                )
                lines.append(
                    f"After: {successor}."
                    if successor
                    else "After: no following integration is captured in this process."
                )
        qa_status = str(integration.get("qa_status") or "Not captured")
        qa_reasons = integration.get("qa_reasons")
        if integration.get("needs_attention"):
            reason_text = "; ".join(str(item) for item in qa_reasons) if isinstance(qa_reasons, list) else ""
            attention = (
                f"Atención: QA está en {qa_status}. {reason_text}"
                if spanish
                else f"Attention: QA is {qa_status}. {reason_text}"
            )
            lines.append(attention.strip())
        else:
            lines.append(
                f"Atención: QA está en {qa_status}; no se identificó remediación a nivel de integración."
                if spanish
                else f"Attention: QA is {qa_status}; no row-level remediation is identified."
            )
        if spanish:
            lines.append(
                "Siguiente paso: revisa el límite capturado del proceso y el diseño guardado antes del cierre de arquitectura."
                if not integration.get("needs_attention")
                else "Siguiente paso: revisa las razones de QA y completa los campos gobernados faltantes en el detalle de la integración."
            )
        else:
            lines.append(f"Next: {integration.get('recommended_next_action')}")
        return "\n\n".join(lines)
    project = evidence.get("project")
    if isinstance(project, dict):
        latest_bom = project.get("latest_bom")
        if evidence.get("question_intent") == "project_cost":
            if isinstance(latest_bom, dict):
                currency = latest_bom.get("currency")
                contract_total = _money(latest_bom.get("contract_total"), currency)
                monthly_total = _money(latest_bom.get("monthly_total"), currency)
                peak_total = _money(latest_bom.get("peak_monthly_total"), currency)
                coverage = float(latest_bom.get("coverage_pct") or 0)
                status = str(latest_bom.get("publication_status") or "draft")
                if spanish:
                    return (
                        f"El último BOM de {project.get('name')} estima **{contract_total}** para el contrato.\n\n"
                        f"- Consumo mensual inicial: {monthly_total}\n"
                        f"- Pico mensual: {peak_total}\n"
                        f"- Cobertura de precios: {coverage:.0f}%\n"
                        f"- Estado: {status}\n\n"
                        "Siguiente paso: abre BOM & Cost para revisar el escenario, la rampa mensual y los SKU antes de usar esta estimación en una propuesta."
                    )
                return (
                    f"The latest BOM for {project.get('name')} estimates **{contract_total}** for the contract.\n\n"
                    f"- Initial monthly run rate: {monthly_total}\n"
                    f"- Peak monthly run rate: {peak_total}\n"
                    f"- Price coverage: {coverage:.0f}%\n"
                    f"- Status: {status}\n\n"
                    "Next: open BOM & Cost to review the scenario, monthly ramp, and SKUs before using this estimate in a proposal."
                )
            return (
                f"{project.get('name')} todavía no tiene un BOM calculado. Abre BOM & Cost, selecciona un escenario aprobado y ejecuta el cálculo."
                if spanish
                else f"{project.get('name')} does not have a calculated BOM yet. Open BOM & Cost, select an approved scenario, and run the calculation."
            )
        if spanish:
            return (
                f"{project.get('name')} contiene {project.get('integration_count')} integraciones gobernadas. "
                "Puedo ayudarte a revisar su distribución de QA, procesos de negocio, topología o último BOM.\n\n"
                "Dime qué decisión necesitas tomar."
            )
        return (
            f"{project.get('name')} contains {project.get('integration_count')} governed integrations. "
            "I can help you inspect its QA distribution, business processes, topology, or latest BOM.\n\n"
            "Tell me which decision you are working through, or add the relevant App context."
        )
    project_workspaces = evidence.get("project_workspaces")
    if isinstance(project_workspaces, list):
        active = [
            item
            for item in project_workspaces
            if isinstance(item, dict) and str(item.get("status") or "").casefold() == "active"
        ]
        if evidence.get("question_intent") == "project_portfolio":
            count = len(active)
            names = ", ".join(str(item.get("name")) for item in active[:5])
            if spanish:
                return (
                    f"La App tiene **{count} proyecto{'s' if count != 1 else ''} activo{'s' if count != 1 else ''}**."
                    + (f"\n\n{names}." if names else "")
                )
            return (
                f"The App has **{count} active project{'s' if count != 1 else ''}**."
                + (f"\n\n{names}." if names else "")
            )
        resolution = evidence.get("project_resolution")
        if isinstance(resolution, dict) and resolution.get("ambiguous"):
            names = ", ".join(str(item.get("name")) for item in active[:5])
            return (
                f"Encontré varios proyectos activos: {names}. Indica el proyecto o abre su workspace para consultar su evidencia."
                if spanish
                else f"I found multiple active projects: {names}. Name the project or open its workspace so I can use the right evidence."
            )
    return (
        "I can help you move through OCI DIS Architect and explain the governed evidence behind an integration, "
        "business process, topology path, Service Product, or BOM.\n\n"
        "Open the relevant workspace or add its context, then ask the decision you need to make."
    )


async def _conversation_for_session(
    session_id: str,
    db: AsyncSession,
    *,
    create: bool,
    actor_id: str,
) -> SupportConversation:
    conversation = await db.scalar(
        select(SupportConversation).where(
            SupportConversation.session_id == session_id,
            SupportConversation.status == "active",
        )
    )
    if conversation is not None:
        return conversation
    if not create:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Support conversation not found", "error_code": "SUPPORT_CONVERSATION_NOT_FOUND"},
        )
    conversation = SupportConversation(
        session_id=session_id,
        actor_id=actor_id or "web-user",
        title="OCI DIS Architect support",
        status="active",
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def _serialize_message(message: SupportMessage, db: AsyncSession) -> SupportMessageResponse:
    attachments = list(
        (
            await db.scalars(
                select(SupportAttachment)
                .where(SupportAttachment.message_id == message.id)
                .order_by(SupportAttachment.created_at)
            )
        ).all()
    )
    return SupportMessageResponse(
        id=message.id,
        role=cast(Literal["user", "assistant"], message.role),
        content=message.content,
        status=cast(Literal["pending", "completed", "failed", "refused"], message.status),
        agent_run_id=message.agent_run_id,
        context=cast(dict[str, object], message.context_snapshot),
        citations=cast(list[dict[str, str]], message.citations),
        attachments=[
            SupportAttachmentResponse(
                id=item.id,
                attachment_type=cast(
                    Literal["page", "project", "integration", "catalog", "topology", "canvas", "import", "bom", "admin"],
                    item.attachment_type,
                ),
                label=item.label,
                entity_id=item.entity_id,
                href=item.href,
                context=cast(dict[str, object], item.context_payload),
            )
            for item in attachments
        ],
        created_at=message.created_at,
    )


async def serialize_conversation(
    conversation: SupportConversation,
    db: AsyncSession,
) -> SupportConversationResponse:
    """Serialize the latest bounded history for one isolated conversation."""

    messages = list(
        (
            await db.scalars(
                select(SupportMessage)
                .where(SupportMessage.conversation_id == conversation.id)
                .order_by(SupportMessage.created_at.desc())
                .limit(60)
            )
        ).all()
    )
    messages.reverse()
    return SupportConversationResponse(
        id=conversation.id,
        title=conversation.title,
        status=cast(Literal["active", "archived"], conversation.status),
        messages=[await _serialize_message(message, db) for message in messages],
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


async def get_or_create_conversation(
    session_id: str,
    actor_id: str,
    db: AsyncSession,
) -> SupportConversationResponse:
    """Return the active conversation owned by exactly one browser session."""

    conversation = await _conversation_for_session(
        validate_support_session_id(session_id), db, create=True, actor_id=actor_id
    )
    return await serialize_conversation(conversation, db)


async def get_conversation(
    conversation_id: str,
    session_id: str,
    db: AsyncSession,
) -> SupportConversationResponse:
    """Read a conversation only when both ID and opaque session match."""

    normalized_session = validate_support_session_id(session_id)
    conversation = await db.get(SupportConversation, conversation_id)
    if conversation is None or conversation.session_id != normalized_session:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Support conversation not found", "error_code": "SUPPORT_CONVERSATION_NOT_FOUND"},
        )
    return await serialize_conversation(conversation, db)


async def clear_conversation_history(
    conversation_id: str,
    session_id: str,
    actor_id: str,
    db: AsyncSession,
) -> SupportConversationResponse:
    """Clear one session-owned visible transcript while retaining agent-run audit records."""

    normalized_session = validate_support_session_id(session_id)
    conversation = await db.get(SupportConversation, conversation_id)
    if conversation is None or conversation.session_id != normalized_session or conversation.status != "active":
        raise HTTPException(
            status_code=404,
            detail={"detail": "Support conversation not found", "error_code": "SUPPORT_CONVERSATION_NOT_FOUND"},
        )
    pending_count = int(
        await db.scalar(
            select(func.count())
            .select_from(SupportMessage)
            .where(
                SupportMessage.conversation_id == conversation.id,
                SupportMessage.status == "pending",
            )
        )
        or 0
    )
    if pending_count:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "Wait for the current support response before clearing history",
                "error_code": "SUPPORT_TURN_PENDING",
            },
        )
    message_count = int(
        await db.scalar(
            select(func.count())
            .select_from(SupportMessage)
            .where(SupportMessage.conversation_id == conversation.id)
        )
        or 0
    )
    attachment_count = int(
        await db.scalar(
            select(func.count())
            .select_from(SupportAttachment)
            .where(SupportAttachment.conversation_id == conversation.id)
        )
        or 0
    )
    await db.execute(
        delete(SupportAttachment).where(SupportAttachment.conversation_id == conversation.id)
    )
    await db.execute(
        delete(SupportMessage).where(SupportMessage.conversation_id == conversation.id)
    )
    conversation.updated_at = datetime.now(UTC)
    await audit_service.emit(
        event_type="support_conversation_history_cleared",
        entity_type="support_conversation",
        entity_id=conversation.id,
        actor_id=actor_id or conversation.actor_id,
        old_value={"message_count": message_count, "attachment_count": attachment_count},
        new_value={"message_count": 0, "attachment_count": 0},
        project_id=None,
        correlation_id=conversation.id,
        db=db,
    )
    return await serialize_conversation(conversation, db)


async def prepare_support_turn(
    conversation_id: str,
    session_id: str,
    body: SupportMessageCreateRequest,
    db: AsyncSession,
) -> tuple[SupportMessage, SupportMessage, dict[str, object]]:
    """Persist a user turn and pending assistant response before worker dispatch."""

    normalized_session = validate_support_session_id(session_id)
    conversation = await db.get(SupportConversation, conversation_id)
    if conversation is None or conversation.session_id != normalized_session or conversation.status != "active":
        raise HTTPException(
            status_code=404,
            detail={"detail": "Support conversation not found", "error_code": "SUPPORT_CONVERSATION_NOT_FOUND"},
        )
    pending_count = int(
        await db.scalar(
            select(func.count())
            .select_from(SupportMessage)
            .where(
                SupportMessage.conversation_id == conversation.id,
                SupportMessage.role == "assistant",
                SupportMessage.status == "pending",
            )
        )
        or 0
    )
    if pending_count:
        raise HTTPException(
            status_code=409,
            detail={"detail": "A support response is already running", "error_code": "SUPPORT_TURN_PENDING"},
        )
    context_snapshot = cast(
        dict[str, object],
        sanitize_for_json(
            {
                "route": body.route,
                "page_title": body.page_title,
                "project_id": body.project_id,
                "integration_id": body.integration_id,
            }
        ),
    )
    user_message = SupportMessage(
        conversation_id=conversation.id,
        role="user",
        content=body.content.strip(),
        status="completed",
        context_snapshot=context_snapshot,
        citations=[],
    )
    db.add(user_message)
    await db.flush()
    for item in body.attachments:
        db.add(
            SupportAttachment(
                conversation_id=conversation.id,
                message_id=user_message.id,
                attachment_type=item.attachment_type,
                label=item.label,
                entity_id=item.entity_id,
                href=item.href,
                context_payload=cast(dict, sanitize_for_json(item.context)),
            )
        )
    assistant_message = SupportMessage(
        conversation_id=conversation.id,
        role="assistant",
        content="",
        status="pending",
        context_snapshot=context_snapshot,
        citations=[],
    )
    db.add(assistant_message)
    conversation.updated_at = datetime.now(UTC)
    await db.flush()
    previous = list(
        (
            await db.scalars(
                select(SupportMessage)
                .where(
                    SupportMessage.conversation_id == conversation.id,
                    SupportMessage.status.in_(["completed", "refused"]),
                )
                .order_by(SupportMessage.created_at.desc())
                .limit(12)
            )
        ).all()
    )
    previous.reverse()
    agent_context: dict[str, object] = {
        **context_snapshot,
        "question": body.content.strip(),
        "conversation_id": conversation.id,
        "support_assistant_message_id": assistant_message.id,
        "attachments": [item.model_dump(mode="json") for item in body.attachments],
        "transcript": [{"role": item.role, "content": item.content[:1200]} for item in previous],
    }
    return user_message, assistant_message, agent_context


async def link_support_run(message_id: str, run_id: str, db: AsyncSession) -> None:
    """Link the pending assistant message to its auditable AgentRun."""

    message = await db.get(SupportMessage, message_id)
    if message is not None:
        message.agent_run_id = run_id
        await db.flush()


async def build_support_evidence(
    project_id: str | None,
    integration_id: str | None,
    context: dict[str, object],
    db: AsyncSession,
) -> dict[str, object]:
    """Build bounded, App-wide governed evidence for one contextual answer."""

    question = str(context.get("question") or context.get("message") or "").strip()
    question_lower = question.casefold()
    attachments = cast(
        list[object], context.get("attachments") if isinstance(context.get("attachments"), list) else []
    )
    transcript = cast(
        list[object], context.get("transcript") if isinstance(context.get("transcript"), list) else []
    )
    has_context = bool(context.get("route") or attachments or project_id or integration_id)
    if not question_is_in_scope(question, has_context=has_context):
        return {
            "in_scope": False,
            "refusal": OUT_OF_SCOPE_RESPONSE,
            "authority": "app_domain_policy",
            "citations": [],
        }

    route = str(context.get("route") or "/projects")
    citations: list[dict[str, str]] = [{"label": "Current context", "href": route}]
    projects = list(
        (
            await db.scalars(
                select(Project).order_by(Project.updated_at.desc()).limit(50)
            )
        ).all()
    )
    projects_by_id = {item.id: item for item in projects}
    active_projects = [item for item in projects if item.status == ProjectStatus.ACTIVE]
    resolved_project_id = project_id
    project_resolution = "route" if project_id else None
    if resolved_project_id is None:
        attached_project_id = _project_id_from_attachments(attachments)
        if attached_project_id in projects_by_id:
            resolved_project_id = attached_project_id
            project_resolution = "attached_context"
    if resolved_project_id is None:
        named_project = _project_name_match(projects, question, transcript)
        if named_project is not None:
            resolved_project_id = named_project.id
            project_resolution = "named_in_conversation"
    needs_project_scope = _question_needs_project_scope(question)
    if resolved_project_id is None and needs_project_scope and len(active_projects) == 1:
        resolved_project_id = active_projects[0].id
        project_resolution = "single_active_project"
    question_intent = (
        "project_cost"
        if any(
            term in question_lower
            for term in ("pricing", "price", "cost", "precio", "costo", "bom", "bill of materials")
        )
        else "project_portfolio"
        if PROJECT_PORTFOLIO_PATTERN.search(question)
        else "project_context"
        if needs_project_scope
        else "app_guidance"
    )
    pattern_count = int(
        await db.scalar(
            select(func.count()).select_from(PatternDefinition).where(PatternDefinition.is_active.is_(True))
        )
        or 0
    )
    service_count = int(
        await db.scalar(
            select(func.count())
            .select_from(ServiceCapabilityProfile)
            .where(ServiceCapabilityProfile.is_active.is_(True))
        )
        or 0
    )
    dictionary_count = int(
        await db.scalar(
            select(func.count()).select_from(DictionaryOption).where(DictionaryOption.is_active.is_(True))
        )
        or 0
    )
    assumption_count = int(await db.scalar(select(func.count()).select_from(AssumptionSet)) or 0)
    evidence: dict[str, object] = {
        "in_scope": True,
        "application": "OCI DIS Architect",
        "answer_policy": {
            "authority": "Only facts in this tool result are authoritative.",
            "unknowns": "Say what evidence is missing instead of supplying generic external facts.",
            "style": "Answer naturally and directly. Use short paragraphs or bullets, never a Markdown table.",
        },
        "response_language": "es" if SPANISH_QUESTION_PATTERN.search(question) else "en",
        "current_context": {
            "route": route,
            "page_title": context.get("page_title"),
        },
        "question_intent": question_intent,
        "project_resolution": {
            "resolved_project_id": resolved_project_id,
            "method": project_resolution,
            "ambiguous": bool(needs_project_scope and resolved_project_id is None and len(active_projects) > 1),
            "active_project_count": len(active_projects),
        },
        "attached_components": attachments[:8],
        "conversation_questions": [
            item
            for item in transcript[:12]
            if isinstance(item, dict) and item.get("role") == "user"
        ],
        "scope_rules": {
            "conversation": "Previous questions provide dialogue continuity but are not architecture evidence.",
            "integration": "Do not apply project-level risks to an integration unless its row evidence identifies the same issue.",
            "process": "Do not invent predecessors, successors, events, approvals, or runtime behavior outside the captured ordered integrations.",
            "actions": "Recommend only navigation, review, or missing capture supported by this result; never invent an approval workflow.",
        },
        "app_sections": list(APP_SECTIONS),
        "governance_summary": {
            "active_patterns": pattern_count,
            "active_service_products": service_count,
            "active_dictionary_options": dictionary_count,
            "assumption_versions": assumption_count,
        },
        "citations": citations,
    }

    wants_patterns = any(term in question_lower for term in ("pattern", "patrón", "patron")) or "/patterns" in route
    wants_services = any(
        term in question_lower
        for term in ("service product", "servicio", "interoperability", "interoperabilidad", "limit", "límite")
    ) or "/services" in route
    if wants_patterns:
        patterns = list(
            (
                await db.scalars(
                    select(PatternDefinition)
                    .where(PatternDefinition.is_active.is_(True))
                    .order_by(PatternDefinition.pattern_id)
                    .limit(24)
                )
            ).all()
        )
        evidence["pattern_library"] = [
            {
                "id": item.pattern_id,
                "name": item.name,
                "category": item.category,
                "description": item.description,
                "when_to_use": item.when_to_use,
                "when_not_to_use": item.when_not_to_use,
            }
            for item in patterns
        ]
        citations.append({"label": "Pattern Library", "href": "/admin/patterns"})
    if wants_services:
        services = list(
            (
                await db.scalars(
                    select(ServiceCapabilityProfile)
                    .where(ServiceCapabilityProfile.is_active.is_(True))
                    .order_by(ServiceCapabilityProfile.name)
                    .limit(30)
                )
            ).all()
        )
        evidence["service_product_library"] = [
            {
                "id": item.service_id,
                "name": item.name,
                "category": item.category,
                "architectural_fit": item.architectural_fit,
                "interoperability_notes": item.interoperability_notes,
            }
            for item in services
        ]
        citations.append({"label": "Service Product Library", "href": "/admin/services"})

    integration: CatalogIntegration | None = None
    if integration_id:
        candidate = await db.get(CatalogIntegration, integration_id)
        if candidate is not None and (resolved_project_id is None or candidate.project_id == resolved_project_id):
            integration = candidate
            if resolved_project_id is None:
                resolved_project_id = candidate.project_id
                project_resolution = "integration_context"
                cast(dict[str, object], evidence["project_resolution"])["resolved_project_id"] = resolved_project_id
                cast(dict[str, object], evidence["project_resolution"])["method"] = project_resolution
                cast(dict[str, object], evidence["project_resolution"])["ambiguous"] = False
            integration_needs_attention = str(integration.qa_status or "").upper() not in {"OK", "QA OK"}
            evidence["integration"] = {
                "id": integration.id,
                "interface_id": integration.interface_id,
                "name": integration.interface_name,
                "description": integration.description,
                "business_process": integration.business_process,
                "owner": integration.owner,
                "brand": integration.brand,
                "status": integration.status,
                "source_system": integration.source_system,
                "source_technology": integration.source_technology,
                "source_owner": integration.source_owner,
                "destination_system": integration.destination_system,
                "destination_technologies": [
                    value
                    for value in (
                        integration.destination_technology_1,
                        integration.destination_technology_2,
                    )
                    if value
                ],
                "destination_owner": integration.destination_owner,
                "type": integration.type,
                "trigger_type": integration.trigger_type,
                "frequency": integration.frequency,
                "executions_per_day": integration.executions_per_day,
                "payload_per_execution_kb": integration.payload_per_execution_kb,
                "payload_per_hour_kb": integration.payload_per_hour_kb,
                "pattern": integration.selected_pattern,
                "pattern_rationale": integration.pattern_rationale,
                "qa_status": integration.qa_status,
                "qa_reasons": integration.qa_reasons or [],
                "core_tools": integration.core_tools,
                "overlays": integration.additional_tools_overlays,
                "retry_policy": integration.retry_policy,
                "uncertainty": integration.uncertainty,
                "needs_attention": integration_needs_attention,
                "recommended_next_action": (
                    "Review the listed QA reasons and complete the missing governed fields in Integration Detail."
                    if integration_needs_attention
                    else "No row-level QA remediation is identified. Review the captured process boundary and saved design before sign-off."
                ),
            }
            citations.append(
                {
                    "label": integration.interface_name or integration.interface_id or "Integration",
                    "href": f"/projects/{integration.project_id}/catalog/{integration.id}",
                }
            )

    if resolved_project_id:
        project = projects_by_id.get(resolved_project_id) or await db.get(Project, resolved_project_id)
        if project is not None:
            integration_count = int(
                await db.scalar(
                    select(func.count())
                    .select_from(CatalogIntegration)
                    .where(CatalogIntegration.project_id == project.id)
                )
                or 0
            )
            qa_rows = (
                await db.execute(
                    select(CatalogIntegration.qa_status, func.count())
                    .where(CatalogIntegration.project_id == project.id)
                    .group_by(CatalogIntegration.qa_status)
                )
            ).all()
            process_rows = (
                await db.execute(
                    select(CatalogIntegration.business_process, func.count())
                    .where(
                        CatalogIntegration.project_id == project.id,
                        CatalogIntegration.business_process.is_not(None),
                        CatalogIntegration.business_process != "",
                    )
                    .group_by(CatalogIntegration.business_process)
                    .order_by(func.count().desc(), CatalogIntegration.business_process)
                    .limit(24)
                )
            ).all()
            pattern_rows = (
                await db.execute(
                    select(CatalogIntegration.selected_pattern, func.count())
                    .where(
                        CatalogIntegration.project_id == project.id,
                        CatalogIntegration.selected_pattern.is_not(None),
                    )
                    .group_by(CatalogIntegration.selected_pattern)
                    .order_by(func.count().desc())
                    .limit(20)
                )
            ).all()
            latest_import = await db.scalar(
                select(ImportBatch)
                .where(ImportBatch.project_id == project.id)
                .order_by(ImportBatch.created_at.desc())
                .limit(1)
            )
            scenarios = list(
                (
                    await db.scalars(
                        select(DeploymentScenario)
                        .where(DeploymentScenario.project_id == project.id)
                        .order_by(DeploymentScenario.updated_at.desc())
                        .limit(8)
                    )
                ).all()
            )
            latest_bom = await db.scalar(
                select(BomSnapshot)
                .where(BomSnapshot.project_id == project.id)
                .order_by(BomSnapshot.created_at.desc())
                .limit(1)
            )
            latest_dashboard = await db.scalar(
                select(DashboardSnapshot)
                .where(DashboardSnapshot.project_id == project.id)
                .order_by(DashboardSnapshot.created_at.desc())
                .limit(1)
            )
            process_portfolio = [
                {"name": str(name), "integration_count": int(count)}
                for name, count in process_rows
                if name
            ]
            evidence["project"] = {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "status": project.status.value if hasattr(project.status, "value") else str(project.status),
                "integration_count": integration_count,
                "qa_distribution": {
                    str(status or "UNSET"): int(count) for status, count in qa_rows
                },
                "business_processes": process_portfolio,
                "pattern_distribution": {
                    str(pattern or "UNSET"): int(count) for pattern, count in pattern_rows
                },
                "latest_import": (
                    {
                        "filename": latest_import.filename,
                        "status": (
                            latest_import.status.value
                            if hasattr(latest_import.status, "value")
                            else str(latest_import.status)
                        ),
                        "loaded_count": latest_import.loaded_count,
                        "excluded_count": latest_import.excluded_count,
                    }
                    if latest_import
                    else None
                ),
                "deployment_scenarios": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "status": item.status,
                        "region": item.region,
                        "currency": item.currency,
                    }
                    for item in scenarios
                ],
                "latest_bom": (
                    {
                        "id": latest_bom.id,
                        "publication_status": latest_bom.publication_status,
                        "currency": latest_bom.currency,
                        "coverage_pct": latest_bom.coverage_pct,
                        "monthly_total": latest_bom.monthly_total,
                        "peak_monthly_total": latest_bom.peak_monthly_total,
                        "contract_total": latest_bom.contract_total,
                        "first_active_period": latest_bom.first_active_period,
                        "steady_state_period": latest_bom.steady_state_period,
                        "ramp_deferred_amount": latest_bom.ramp_deferred_amount,
                        "monthly_series": latest_bom.summary.get("monthly_series", []),
                    }
                    if latest_bom
                    else None
                ),
                "latest_dashboard": (
                    {
                        "snapshot_id": latest_dashboard.id,
                        "created_at": latest_dashboard.created_at,
                        "kpis": cast(dict[str, object], latest_dashboard.kpi_strip or {}),
                        "risks": cast(list[object], latest_dashboard.risks or [])[:10],
                        "maturity": cast(dict[str, object], latest_dashboard.maturity or {}),
                    }
                    if latest_dashboard
                    and (
                        integration is None
                        or any(term in question_lower for term in ("dashboard", "project risk", "riesgo del proyecto"))
                    )
                    else None
                ),
            }
            citations.append({"label": project.name, "href": f"/projects/{project.id}"})
            if question_intent == "project_cost":
                citations.append({"label": "BOM & Cost", "href": f"/projects/{project.id}/bom"})

            focus_process = integration.business_process if integration else None
            if focus_process is None:
                matches = [
                    str(name)
                    for name, _ in process_rows
                    if name and str(name).casefold() in question_lower
                ]
                focus_process = max(matches, key=len) if matches else None
            if focus_process:
                process_integrations = list(
                    (
                        await db.scalars(
                            select(CatalogIntegration)
                            .where(
                                CatalogIntegration.project_id == project.id,
                                CatalogIntegration.business_process == focus_process,
                            )
                            .order_by(CatalogIntegration.seq_number)
                            .limit(30)
                        )
                    ).all()
                )
                focus_index = next(
                    (index for index, item in enumerate(process_integrations) if integration and item.id == integration.id),
                    None,
                )
                evidence["business_process_flow"] = {
                    "name": focus_process,
                    "integration_count": len(process_integrations),
                    "captured_predecessor": (
                        process_integrations[focus_index - 1].interface_name
                        if focus_index is not None and focus_index > 0
                        else None
                    ),
                    "captured_successor": (
                        process_integrations[focus_index + 1].interface_name
                        if focus_index is not None and focus_index + 1 < len(process_integrations)
                        else None
                    ),
                    "boundary_note": (
                        "This is the only integration captured for this business process; no before or after step is evidenced."
                        if len(process_integrations) == 1
                        else "Before and after refer only to adjacent captured integrations in this ordered list."
                    ),
                    "ordered_integrations": [
                        {
                            "sequence": item.seq_number,
                            "name": item.interface_name,
                            "description": item.description,
                            "source": item.source_system,
                            "destination": item.destination_system,
                            "pattern": item.selected_pattern,
                            "qa_status": item.qa_status,
                        }
                        for item in process_integrations
                    ],
                }
                citations.append(
                    {
                        "label": focus_process,
                        "href": f"/projects/{project.id}/catalog?business_process={quote(focus_process)}",
                    }
                )
    else:
        evidence["project_workspaces"] = [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "status": item.status.value if hasattr(item.status, "value") else str(item.status),
            }
            for item in projects[:20]
        ]
        citations.append({"label": "Projects", "href": "/projects"})

    evidence["fallback_answer"] = _support_fallback_answer(evidence)
    if question_intent in {"project_portfolio", "project_cost"}:
        evidence["direct_answer"] = evidence["fallback_answer"]
    return cast(dict[str, object], sanitize_for_json(evidence))


async def complete_support_message(
    message_id: str,
    *,
    content: str,
    status: str,
    citations: list[dict[str, str]],
    db: AsyncSession,
) -> None:
    """Persist the final bounded answer returned by the agent worker."""

    message = await db.get(SupportMessage, message_id)
    if message is None:
        return
    message.content = content[:12000]
    message.status = status
    message.citations = cast(list, sanitize_for_json(citations[:12]))
    await db.flush()


async def fail_support_message(message_id: str, db: AsyncSession) -> None:
    """Expose an honest recoverable failure when the worker cannot complete."""

    await complete_support_message(
        message_id,
        content="I could not complete this App support response. Please retry.",
        status="failed",
        citations=[],
        db=db,
    )
