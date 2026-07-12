"""Session-isolated contextual support conversation services."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BomSnapshot,
    CatalogIntegration,
    DashboardSnapshot,
    DeploymentScenario,
    Project,
    SupportAttachment,
    SupportConversation,
    SupportMessage,
)
from app.schemas.agent import (
    SupportAttachmentResponse,
    SupportConversationResponse,
    SupportMessageCreateRequest,
    SupportMessageResponse,
)
from app.services.serializers import sanitize_for_json


OUT_OF_SCOPE_RESPONSE = (
    "I can only help with OCI DIS Architect, its workflows, and the integration architecture, "
    "topology, Service Product, volumetry, pricing, or BOM evidence available in this App."
)
APP_DOMAIN_PATTERN = re.compile(
    r"\b(oci|dis|architect|app|application|project|integration|interface|catalog|capture|import|dashboard|"
    r"map|topology|canvas|pattern|service|product|volumetry|payload|frequency|qa|governance|assumption|"
    r"pricing|price|cost|bom|bill of materials|sku|scenario|agent|review|export|workbook|oracle|streaming|"
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
    """Build bounded governed evidence for one contextual support answer."""

    question = str(context.get("question") or context.get("message") or "").strip()
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
    evidence: dict[str, object] = {
        "in_scope": True,
        "application": "OCI DIS Architect",
        "current_view": {
            "route": context.get("route"),
            "page_title": context.get("page_title"),
        },
        "attached_components": attachments[:8],
        "conversation": transcript[:12],
        "capabilities": [
            "governed workbook import and capture",
            "integration catalog and lineage",
            "volumetry and QA",
            "integration design canvas and topology",
            "Service Product Library and interoperability",
            "governed OCI pricing and Bill of Materials",
            "evidence-backed architecture and specialist agent reviews",
        ],
        "citations": [{"label": "Current App view", "href": str(context.get("route") or "/projects")}],
    }
    if project_id:
        project = await db.get(Project, project_id)
        if project is not None:
            integration_count = int(
                await db.scalar(
                    select(func.count()).select_from(CatalogIntegration).where(CatalogIntegration.project_id == project.id)
                )
                or 0
            )
            scenario_count = int(
                await db.scalar(
                    select(func.count()).select_from(DeploymentScenario).where(DeploymentScenario.project_id == project.id)
                )
                or 0
            )
            latest_bom = await db.scalar(
                select(BomSnapshot).where(BomSnapshot.project_id == project.id).order_by(BomSnapshot.created_at.desc()).limit(1)
            )
            latest_dashboard = await db.scalar(
                select(DashboardSnapshot)
                .where(DashboardSnapshot.project_id == project.id)
                .order_by(DashboardSnapshot.created_at.desc())
                .limit(1)
            )
            evidence["project"] = {
                "id": project.id,
                "name": project.name,
                "status": project.status.value if hasattr(project.status, "value") else str(project.status),
                "integration_count": integration_count,
                "deployment_scenario_count": scenario_count,
                "latest_bom": (
                    {
                        "id": latest_bom.id,
                        "publication_status": latest_bom.publication_status,
                        "currency": latest_bom.currency,
                        "coverage_pct": latest_bom.coverage_pct,
                        "monthly_total": latest_bom.monthly_total,
                    }
                    if latest_bom
                    else None
                ),
                "latest_dashboard": (
                    {
                        "snapshot_id": latest_dashboard.id,
                        "created_at": latest_dashboard.created_at,
                        "risks": cast(list[object], latest_dashboard.risks or [])[:8],
                        "maturity": cast(dict[str, object], latest_dashboard.maturity or {}),
                    }
                    if latest_dashboard
                    else None
                ),
            }
            cast(list[dict[str, str]], evidence["citations"]).append(
                {"label": project.name, "href": f"/projects/{project.id}"}
            )
    if integration_id:
        integration = await db.get(CatalogIntegration, integration_id)
        if integration is not None and (project_id is None or integration.project_id == project_id):
            evidence["integration"] = {
                "id": integration.id,
                "interface_id": integration.interface_id,
                "name": integration.interface_name,
                "source_system": integration.source_system,
                "destination_system": integration.destination_system,
                "pattern": integration.selected_pattern,
                "qa_status": integration.qa_status,
                "qa_reasons": integration.qa_reasons or [],
                "payload_per_execution_kb": integration.payload_per_execution_kb,
                "frequency": integration.frequency,
                "core_tools": integration.core_tools,
                "overlays": integration.additional_tools_overlays,
            }
            cast(list[dict[str, str]], evidence["citations"]).append(
                {
                    "label": integration.interface_name or integration.interface_id or "Integration",
                    "href": f"/projects/{integration.project_id}/catalog/{integration.id}",
                }
            )
    evidence["fallback_answer"] = (
        "I collected the governed context for this App view. OCI GenAI synthesis is unavailable right now; "
        "use the cited project or integration record for the authoritative details."
    )
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
