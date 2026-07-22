"""Session-isolated contextual support conversation services."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Literal, cast
from urllib.parse import quote
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AiReviewJob,
    AssumptionSet,
    BomLineItem,
    BomSnapshot,
    CatalogIntegration,
    DashboardSnapshot,
    DeploymentScenario,
    DeploymentEnvironmentPlan,
    DeploymentRampPhase,
    DictionaryOption,
    ImportBatch,
    PatternDefinition,
    PriceCatalogSnapshot,
    PriceItem,
    ProductCoverageCandidate,
    Project,
    ServiceCapabilityProfile,
    ServiceCommercialPolicy,
    ServiceProductSkuMapping,
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
from app.services.agent_output_service import support_output_contains_internal_reasoning
from app.services.app_knowledge_service import (
    build_app_knowledge_evidence,
    explicit_intent_cue,
    knowledge_grounding_failure,
)
from app.services.serializers import sanitize_for_json


WITHHELD_INTERNAL_RESPONSE = (
    "This response was withheld because it contained internal generation notes. "
    "Please ask the question again to receive a governed answer."
)
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
SPANISH_QUESTION_PATTERN = re.compile(
    r"[¿¡áéíóúñ]|\b(qué|que|cómo|como|cuál|cual|cuánto|cuanto|dónde|donde|esta|este|quiero|"
    r"integración|proceso|ayuda|siguiente|servicio|precio|costo|cuesta)\b",
    re.IGNORECASE,
)
PROJECT_SCOPE_PATTERN = re.compile(
    r"\b(this|current|selected|active|este|esta|actual|seleccionado|activo)\b.{0,24}\b("
    r"project|proyecto|pricing|price|cost|precio|costo|bom|bill of materials|dashboard|qa|risk|riesgo|"
    r"scenario|escenario|import|importaci[oó]n|business process|proceso de negocio|topology|topolog[ií]a)\b|"
    r"\b(project|proyecto)\b.{0,28}\b(pricing|price|cost|precio|costo|bom|bill of materials|dashboard|qa|"
    r"risk|riesgo|scenario|escenario)\b|"
    r"\b(pricing|price|cost|precio|costo|bom|bill of materials)\b.{0,28}\b(project|proyecto)\b",
    re.IGNORECASE,
)
PROJECT_ROUTE_PATTERN = re.compile(r"/projects/([0-9a-f-]{36})(?:/|$)", re.IGNORECASE)
COMMERCIAL_VALUE_PATTERN = re.compile(
    r"\b(price|pricing|cost|costs|priced|bill(?:ed|ing)?|charge(?:d)?|precio|costo|cuesta|cobra|factura)\b",
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
    """Accept every non-empty benign question so the assistant can redirect helpfully.

    OCI Guardrails remains the authority for unsafe or abusive input. Topic matching
    is presentation guidance, not a second safety system.
    """

    normalized = question.strip()
    del has_context
    return bool(normalized)


def _deduplicate_citations(citations: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep one unambiguous App destination per visible citation label."""

    normalized: list[dict[str, str]] = []
    label_indexes: dict[str, int] = {}
    for citation in citations:
        label = str(citation.get("label") or "App context").strip() or "App context"
        href = str(citation.get("href") or "/projects").strip() or "/projects"
        label_key = label.casefold()
        existing_index = label_indexes.get(label_key)
        if existing_index is None:
            label_indexes[label_key] = len(normalized)
            normalized.append({"label": label, "href": href})
            continue
        if normalized[existing_index]["href"] == "/" and href != "/":
            normalized[existing_index] = {"label": label, "href": href}
    return normalized


def support_summary_is_grounded(summary: str, evidence: dict[str, object]) -> bool:
    """Allow rich explanations while blocking placeholders and invented governed facts."""

    normalized_summary = summary.casefold()
    serialized_evidence = str(sanitize_for_json(evidence)).casefold().replace(",", "")
    if INTERNAL_PLACEHOLDER_PATTERN.search(summary):
        return False
    if any(term in normalized_summary and term not in serialized_evidence for term in UNGROUNDED_SENSITIVE_TERMS):
        return False
    for part_number in re.findall(r"\bB\d{5,}\b", summary, re.IGNORECASE):
        if part_number.casefold() not in serialized_evidence:
            return False
    for claim in re.findall(r"(?:USD\s*)?\$\s*\d[\d,]*(?:\.\d+)?|USD\s+\d[\d,]*(?:\.\d+)?", summary, re.IGNORECASE):
        normalized = claim.casefold().replace("usd", "").replace("$", "").replace(",", "").strip()
        if normalized not in serialized_evidence:
            return False
    if knowledge_grounding_failure(summary, evidence) is not None:
        return False
    return True


def _verified_facts(evidence: dict[str, object]) -> list[dict[str, object]]:
    """Project the sensitive App facts the model may quote verbatim."""

    facts: list[dict[str, object]] = []

    def add(fact_id: str, label: str, value: object, *, unit: str | None = None, source: str) -> None:
        if value is None or value == "":
            return
        fact: dict[str, object] = {"id": fact_id, "label": label, "value": value, "source": source}
        if unit:
            fact["unit"] = unit
        facts.append(fact)

    governance = evidence.get("governance_summary")
    if isinstance(governance, dict):
        for key, label in (
            ("active_patterns", "Active integration patterns"),
            ("active_service_products", "Active Service Products"),
            ("active_dictionary_options", "Active dictionary options"),
            ("assumption_versions", "Assumption versions"),
        ):
            add(f"governance.{key}", label, governance.get(key), source="governance_summary")

    project_resolution = evidence.get("project_resolution")
    if isinstance(project_resolution, dict):
        add(
            "portfolio.active_project_count",
            "Active projects",
            project_resolution.get("active_project_count"),
            source="project_resolution",
        )

    project = evidence.get("project")
    if isinstance(project, dict):
        add("project.name", "Project", project.get("name"), source="project")
        add("project.status", "Project status", project.get("status"), source="project")
        add("project.integration_count", "Governed integrations", project.get("integration_count"), source="project")
        latest_bom = project.get("latest_bom")
        if isinstance(latest_bom, dict):
            currency = str(latest_bom.get("currency") or "USD")
            for key, label in (
                ("contract_total", "Contract total"),
                ("monthly_total", "Monthly run rate"),
                ("peak_monthly_total", "Peak monthly total"),
                ("ramp_deferred_amount", "Ramp timing effect"),
            ):
                add(f"bom.{key}", label, latest_bom.get(key), unit=currency, source="project.latest_bom")
            add("bom.coverage_pct", "BOM price coverage", latest_bom.get("coverage_pct"), unit="percent", source="project.latest_bom")
            add("bom.publication_status", "BOM publication status", latest_bom.get("publication_status"), source="project.latest_bom")

    integration = evidence.get("integration")
    if isinstance(integration, dict):
        for key, label in (
            ("name", "Integration"),
            ("source_system", "Source system"),
            ("destination_system", "Destination system"),
            ("pattern", "Selected pattern"),
            ("qa_status", "Integration QA status"),
            ("frequency", "Frequency"),
            ("payload_per_execution_kb", "Payload per execution"),
        ):
            add(
                f"integration.{key}",
                label,
                integration.get(key),
                unit="KB" if key == "payload_per_execution_kb" else None,
                source="integration",
            )

    commercial = evidence.get("commercial_service_context")
    if isinstance(commercial, dict):
        add("commercial.service", "Service Product", commercial.get("service_name"), source="commercial_service_context")
        sku_options = commercial.get("sku_options")
        if isinstance(sku_options, list):
            for index, option in enumerate(sku_options[:8]):
                if not isinstance(option, dict):
                    continue
                prefix = f"commercial.sku_options.{index}"
                add(f"{prefix}.part_number", "Oracle SKU", option.get("part_number"), source="commercial_service_context")
                add(f"{prefix}.metric", "Billing metric", option.get("billing_metric_key"), source="commercial_service_context")
                price = option.get("price")
                if isinstance(price, dict):
                    add(
                        f"{prefix}.unit_price",
                        "Governed unit price",
                        price.get("value"),
                        unit=str(price.get("currency") or "USD"),
                        source="commercial_service_context",
                    )
    return facts


def _support_next_actions(evidence: dict[str, object]) -> list[dict[str, str]]:
    """Return only executable internal routes suitable for a clickable answer."""

    spanish = evidence.get("response_language") == "es"
    current_context = evidence.get("current_context")
    current_route = str(current_context.get("route") or "") if isinstance(current_context, dict) else ""
    knowledge = evidence.get("app_knowledge")
    if evidence.get("question_intent") == "capability_inquiry" and isinstance(knowledge, dict):
        assessment = knowledge.get("capability_assessment")
        closest = assessment.get("closest_entry") if isinstance(assessment, dict) else None
        if isinstance(closest, dict):
            routes = closest.get("routes")
            href = str(routes[0]) if isinstance(routes, list) and routes else "/projects"
            name = str(closest.get("name") or "Projects")
            return [{
                "label": f"Abrir {name}" if spanish else f"Open {name}",
                "href": href,
                "reason": "Use the closest documented App workflow.",
            }]
    project = evidence.get("project")
    project_id = str(project.get("id")) if isinstance(project, dict) and project.get("id") else None
    integration = evidence.get("integration")
    if isinstance(integration, dict) and integration.get("id") and project_id:
        return [{
            "label": "Abrir detalle de integración" if spanish else "Open integration detail",
            "href": f"/projects/{project_id}/catalog/{integration['id']}",
            "reason": "Review the governed row, QA evidence, and design canvas.",
        }]
    if project_id:
        evidence_kind = str(evidence.get("evidence_interpretation") or "")
        suffix = "/bom" if evidence_kind.startswith("bom") or evidence_kind == "quote_readiness" else ""
        labels = {
            "/bom": ("Abrir BOM & Cost", "Open BOM & Cost"),
            "/catalog": ("Abrir catálogo", "Open Catalog"),
            "": ("Abrir dashboard del proyecto", "Open project dashboard"),
        }
        return [{
            "label": labels[suffix][0 if spanish else 1],
            "href": f"/projects/{project_id}{suffix}",
            "reason": "Continue in the governed workspace for this project.",
        }]
    if "pattern_library" in evidence:
        return [{"label": "Abrir patrones" if spanish else "Open Patterns", "href": "/admin/patterns", "reason": "Review the governed pattern definition and applicability."}]
    if "service_product_library" in evidence:
        return [{"label": "Abrir productos" if spanish else "Open Service Products", "href": "/admin/services", "reason": "Review governed service evidence and interoperability."}]
    if current_route.startswith("/"):
        return [{"label": "Continuar en esta vista" if spanish else "Continue in this view", "href": current_route, "reason": "Use the current App context."}]
    return [{"label": "Abrir proyectos" if spanish else "Open Projects", "href": "/projects", "reason": "Select the project or workspace you want to investigate."}]


def _fallback_with_action(answer: str, evidence: dict[str, object]) -> str:
    """Keep provider-failure answers useful and navigable."""

    if re.search(r"\*\*(?:Next action|Siguiente paso):\*\*", answer, re.IGNORECASE):
        return answer
    actions = evidence.get("next_actions")
    if not isinstance(actions, list) or not actions or not isinstance(actions[0], dict):
        return answer
    action = actions[0]
    label = str(action.get("label") or "Open workspace")
    href = str(action.get("href") or "/projects")
    prefix = "**Siguiente paso:**" if evidence.get("response_language") == "es" else "**Next action:**"
    return f"{answer}\n\n{prefix} [{label}]({href})"


def _question_needs_project_scope(question: str) -> bool:
    """Distinguish project dossiers from portfolio-level discovery questions."""

    return bool(PROJECT_SCOPE_PATTERN.search(question))


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


def _compact_reference(value: object) -> str:
    """Normalize a governed name for bounded dialogue-reference matching."""

    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _reference_appears_in_dialogue(reference: object, dialogue: str) -> bool:
    """Resolve a service name from natural dialogue without maintaining keyword aliases."""

    normalized_reference = _compact_reference(reference)
    normalized_dialogue = _compact_reference(dialogue)
    if len(normalized_reference) < 5:
        return False
    if normalized_reference in normalized_dialogue:
        return True
    words = re.findall(r"[a-z0-9]+", dialogue.casefold())
    phrases = (
        "".join(words[index : index + width])
        for width in range(1, min(4, len(words)) + 1)
        for index in range(0, len(words) - width + 1)
    )
    return any(
        len(candidate) >= 5 and SequenceMatcher(a=normalized_reference, b=candidate).ratio() >= 0.82
        for candidate in phrases
    )


def _evidence_fallback(evidence: dict[str, object]) -> str:
    """Explain persisted project evidence when inference is unavailable."""

    spanish = evidence.get("response_language") == "es"
    project = evidence.get("project")
    evidence_kind = str(evidence.get("evidence_interpretation") or "")
    if isinstance(project, dict) and evidence_kind.startswith("bom"):
        bom = project.get("latest_bom")
        if not isinstance(bom, dict):
            return (
                f"{project.get('name')} todavía no tiene un BOM calculado."
                if spanish
                else f"{project.get('name')} does not have a calculated BOM yet."
            )
        total = _money(bom.get("contract_total"), bom.get("currency"))
        line_items_value = bom.get("line_items")
        lines: list[object] = line_items_value if isinstance(line_items_value, list) else []
        if evidence_kind == "bom_sku" and lines:
            question = str(evidence.get("current_question") or "").casefold()
            line = next(
                (
                    cast(dict[str, object], candidate)
                    for candidate in lines
                    if isinstance(candidate, dict)
                    and any(
                        str(candidate.get(field) or "").casefold() in question
                        for field in ("part_number", "description")
                        if candidate.get(field)
                    )
                ),
                cast(dict[str, object], lines[0]),
            )
            return (
                f"El SKU **{line.get('part_number')}** se seleccionó para **{line.get('description')}** por la métrica "
                f"**{line.get('metric_name')}**, con cantidad {line.get('quantity')} {line.get('unit')}. "
                f"La fórmula gobernada es `{line.get('formula')}`."
                if spanish
                else f"SKU **{line.get('part_number')}** was selected for **{line.get('description')}** using "
                f"**{line.get('metric_name')}**, quantity {line.get('quantity')} {line.get('unit')}. "
                f"Its governed formula is `{line.get('formula')}`."
            )
        return (
            f"El último BOM de **{project.get('name')}** totaliza **{total}**, con {len(lines)} líneas y "
            f"{float(bom.get('coverage_pct') or 0):.0f}% de cobertura gobernada."
            if spanish
            else f"The latest BOM for **{project.get('name')}** totals **{total}**, with {len(lines)} line items and "
            f"{float(bom.get('coverage_pct') or 0):.0f}% governed coverage."
        )
    if isinstance(project, dict) and evidence_kind == "review":
        review = project.get("latest_ai_review")
        if isinstance(review, dict):
            return str(review.get("decision_brief") or review.get("summary") or "No decision brief was persisted.")
    if isinstance(project, dict) and evidence_kind == "quote_readiness":
        coverage = project.get("commercial_coverage")
        if isinstance(coverage, dict):
            return (
                f"Quote readiness: {coverage.get('ready', 0)} productos listos y "
                f"{coverage.get('blocked', 0)} bloqueados. Revisa los blockers persistidos antes de publicar."
                if spanish
                else f"Quote readiness: {coverage.get('ready', 0)} products ready and "
                f"{coverage.get('blocked', 0)} blocked. Review the persisted blockers before publication."
            )
    commercial = evidence.get("commercial_service_context")
    if isinstance(commercial, dict):
        options = [
            item
            for item in cast(list[object], commercial.get("sku_options") or [])
            if isinstance(item, dict)
        ]
        rows: list[str] = []
        for option in options[:8]:
            price = option.get("price")
            price_text = "price evidence unavailable"
            if isinstance(price, dict) and price.get("value") is not None:
                period = str(price.get("price_type") or "unit").casefold()
                if spanish:
                    period = {"hour": "hora", "month": "mes", "unit": "unidad"}.get(period, period)
                connector = "por" if spanish else "per"
                price_text = f"{price.get('currency') or 'USD'} {price['value']} {connector} {period}"
            predicates_value = option.get("predicates")
            predicates: dict[str, object] = (
                cast(dict[str, object], predicates_value)
                if isinstance(predicates_value, dict)
                else {}
            )
            variant_parts = [
                (str(key).upper() if isinstance(value, bool) else str(value).title())
                for key, value in predicates.items()
                if value not in (None, False, "")
            ]
            variant = " ".join(variant_parts)
            rows.append(f"- {variant or 'Default'} ({option.get('part_number')}): {price_text}")
        heading = (
            f"Identifiqué **{commercial.get('service_name')}** en la evidencia comercial gobernada."
            if spanish
            else f"I found **{commercial.get('service_name')}** in governed commercial evidence."
        )
        return f"{heading}\n\n" + "\n".join(rows)
    integration = evidence.get("integration")
    if isinstance(integration, dict):
        name = str(integration.get("name") or integration.get("interface_id") or "This integration")
        source = str(integration.get("source_system") or "an uncaptured source")
        destination = str(integration.get("destination_system") or "an uncaptured destination")
        process_name = str(integration.get("business_process") or "an uncaptured business process")
        if spanish:
            summary = (
                f"{name} mueve datos gobernados de **{source}** a **{destination}** "
                f"dentro de **{process_name}**."
            )
        else:
            summary = (
                f"{name} moves governed data from **{source}** to **{destination}** "
                f"within **{process_name}**."
            )
        process = evidence.get("business_process_flow")
        if not isinstance(process, dict):
            return summary
        predecessor = process.get("captured_predecessor")
        successor = process.get("captured_successor")
        if spanish:
            position = (
                f"Anterior capturada: **{predecessor or 'ninguna'}**. "
                f"Siguiente capturada: **{successor or 'ninguna'}**."
            )
        else:
            position = (
                f"Captured predecessor: **{predecessor or 'none'}**. "
                f"Captured successor: **{successor or 'none'}**."
            )
        return f"{summary}\n\n{position}"
    knowledge = evidence.get("app_knowledge")
    if isinstance(knowledge, dict) and isinstance(knowledge.get("fallback_answer"), str):
        return str(knowledge["fallback_answer"])
    return "Open the relevant governed workspace and attach its context so I can interpret its evidence."


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
    content = message.content
    if message.role == "assistant" and support_output_contains_internal_reasoning(content):
        content = WITHHELD_INTERNAL_RESPONSE
    return SupportMessageResponse(
        id=message.id,
        role=cast(Literal["user", "assistant"], message.role),
        content=content,
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
        context_state=cast(dict[str, object], sanitize_for_json(conversation.context_state or {})),
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
    conversation.context_state = {}
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


async def remove_conversation_context(
    conversation_id: str,
    session_id: str,
    context_key: str,
    actor_id: str,
    db: AsyncSession,
) -> SupportConversationResponse:
    """Remove one user-selected semantic reference from an isolated conversation."""

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
                "detail": "Wait for the current support response before changing conversation context",
                "error_code": "SUPPORT_TURN_PENDING",
            },
        )
    state = dict(conversation.context_state or {})
    before_count = len(state)
    state.pop(context_key, None)
    conversation.context_state = cast(dict, sanitize_for_json(state))
    conversation.updated_at = datetime.now(UTC)
    await audit_service.emit(
        event_type="support_conversation_context_removed",
        entity_type="support_conversation",
        entity_id=conversation.id,
        actor_id=actor_id or conversation.actor_id,
        old_value={"context_key_count": before_count},
        new_value={"context_key_count": len(state), "removed_key": context_key},
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
    conversation_state = dict(conversation.context_state or {})
    conversation_state["language"] = "es" if SPANISH_QUESTION_PATTERN.search(body.content) else "en"
    conversation_state["last_question"] = body.content.strip()[:300]
    conversation_state["last_route"] = body.route
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
    conversation.context_state = conversation_state
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
        "conversation_state": conversation_state,
    }
    return user_message, assistant_message, agent_context


async def update_conversation_state(
    conversation_id: str,
    evidence: dict[str, object],
    db: AsyncSession,
) -> None:
    """Persist only resolved, deterministic conversational references.

    Model output is deliberately excluded: future turns resolve their subjects
    from App evidence, never from previous generated prose.
    """

    conversation = await db.get(SupportConversation, conversation_id)
    if conversation is None:
        return
    state = dict(conversation.context_state or {})
    state["topic"] = evidence.get("question_intent")
    state["language"] = evidence.get("response_language", state.get("language", "en"))
    commercial = evidence.get("commercial_service_context")
    if isinstance(commercial, dict) and commercial.get("service_id"):
        state["active_service"] = {
            "id": commercial["service_id"],
            "name": commercial.get("service_name"),
        }
    knowledge = evidence.get("app_knowledge")
    if isinstance(knowledge, dict):
        top_match = knowledge.get("top_match")
        if isinstance(top_match, dict) and top_match.get("section_id"):
            state["active_knowledge_section"] = top_match["section_id"]
    resolution = evidence.get("project_resolution")
    if isinstance(resolution, dict) and resolution.get("resolved_project_id"):
        state["active_project_id"] = resolution["resolved_project_id"]
    conversation.context_state = cast(dict, sanitize_for_json(state))
    conversation.updated_at = datetime.now(UTC)
    await db.flush()


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
    conversation_state = cast(
        dict[str, object], context.get("conversation_state") if isinstance(context.get("conversation_state"), dict) else {}
    )
    dialogue_text = " ".join(
        [question]
        + [
            str(item.get("content") or "")
            for item in transcript[:12]
            if isinstance(item, dict) and item.get("role") == "user"
        ]
    )
    if not question_is_in_scope(
        question,
        has_context=bool(context.get("route") or attachments or project_id or integration_id),
    ):
        return {
            "in_scope": False,
            "refusal": "Enter a question so I can help with OCI DIS Architect.",
            "authority": "empty_input_policy",
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
    response_language = "es" if SPANISH_QUESTION_PATTERN.search(dialogue_text) else "en"
    app_knowledge = await build_app_knowledge_evidence(
        question,
        route,
        language=response_language,
        project_id=resolved_project_id,
        integration_id=integration_id,
    )
    question_intent = str(app_knowledge.get("intent") or "concept_explanation")
    response_mode = str(app_knowledge.get("mode") or "knowledge")
    top_match = app_knowledge.get("top_match")
    knowledge_section = (
        str(top_match.get("section_id") or "") if isinstance(top_match, dict) else ""
    )
    evidence_interpretation = ""
    if (resolved_project_id or integration_id) and explicit_intent_cue(question) is None:
        if re.search(r"\b(why|por qu[eé]).{0,30}\bsku\b|\bsku\b.{0,30}\b(selected|seleccionad)", question, re.IGNORECASE):
            evidence_interpretation = "bom_sku"
        elif re.search(r"\b(bom|bill of materials|contract total|total del contrato|cost of this project|costo de este proyecto|precio total de este proyecto)\b", question, re.IGNORECASE):
            evidence_interpretation = "bom_summary"
        elif re.search(r"\b(finding|hallazgo|decision brief|architecture review|revisi[oó]n de arquitectura)\b", question, re.IGNORECASE):
            evidence_interpretation = "review"
        elif re.search(r"\b(quote[- ]ready|cotizable|blocker|bloquead[oa]).{0,30}\b(quote|cotiz|pricing|precio)?", question, re.IGNORECASE):
            evidence_interpretation = "quote_readiness"
    if evidence_interpretation:
        question_intent = "evidence_interpretation"

    active_service_profiles = list(
        (
            await db.scalars(
                select(ServiceCapabilityProfile)
                .where(ServiceCapabilityProfile.is_active.is_(True))
                .order_by(ServiceCapabilityProfile.name)
            )
        ).all()
    )
    active_service_mappings = list(
        (
            await db.scalars(
                select(ServiceProductSkuMapping).where(
                    ServiceProductSkuMapping.status == "approved",
                    ServiceProductSkuMapping.is_billable.is_(True),
                )
            )
        ).all()
    )
    named_mapping_service_ids = {
        item.service_id
        for item in active_service_mappings
        if _reference_appears_in_dialogue(item.tool_key, dialogue_text)
    }
    matched_named_services = [
        item
        for item in active_service_profiles
        if _reference_appears_in_dialogue(item.name, dialogue_text)
        or _reference_appears_in_dialogue(item.service_id, dialogue_text)
        or item.service_id in named_mapping_service_ids
    ]
    is_commercial_question = bool(matched_named_services) and (
        knowledge_section in {"pricing", "bom"}
        or bool(COMMERCIAL_VALUE_PATTERN.search(question))
    )
    evidence: dict[str, object] = {
        "in_scope": True,
        "application": "OCI DIS Architect",
        "answer_policy": {
            "authority": "Only facts in this tool result are authoritative.",
            "unknowns": "Say what evidence is missing instead of supplying generic external facts.",
            "style": "Answer naturally and directly. Use short paragraphs, lists, bold text, or a compact Markdown table when it improves comprehension.",
        },
        "response_language": response_language,
        "current_question": question,
        "current_context": {
            "route": route,
            "page_title": context.get("page_title"),
        },
        "question_intent": question_intent,
        "evidence_interpretation": evidence_interpretation,
        "response_contract": {
            "intent": question_intent,
            "requires_governed_commercial_evidence": is_commercial_question,
            "model_authorship": "primary",
            "deterministic_fallback": "provider_failure_or_grounding_failure_only",
            "rule": (
                "Start with the bottom line, explain briefly, and end with exactly one executable next action. "
                "Semantic App knowledge determines intent; project evidence takes precedence for evidence interpretation. "
                "For capability_inquiry, capability_assessment is authoritative and absence requires explicit abstention."
            ),
        },
        "app_redirect": (
            {
                "required": True,
                "reason": "The question is outside OCI DIS Architect. Acknowledge it briefly without answering the external topic, then redirect to useful App capabilities.",
            }
            if response_mode == "boundary"
            else {"required": False}
        ),
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
        "conversation_state": conversation_state,
        "scope_rules": {
            "conversation": "Previous questions provide dialogue continuity but are not architecture evidence.",
            "integration": "Do not apply project-level risks to an integration unless its row evidence identifies the same issue.",
            "process": "Do not invent predecessors, successors, events, approvals, or runtime behavior outside the captured ordered integrations.",
            "actions": "Recommend only navigation, review, or missing capture supported by this result; never invent an approval workflow.",
        },
        "app_knowledge": app_knowledge,
        "governance_summary": {
            "active_patterns": pattern_count,
            "active_service_products": service_count,
            "active_dictionary_options": dictionary_count,
            "assumption_versions": assumption_count,
        },
        "citations": citations,
    }
    knowledge_entries = app_knowledge.get("entries")
    capability_assessment = app_knowledge.get("capability_assessment")
    if isinstance(capability_assessment, dict) and capability_assessment.get("status") == "documented":
        assessed_entries = capability_assessment.get("matched_entries")
        if isinstance(assessed_entries, list):
            knowledge_entries = assessed_entries
    if isinstance(knowledge_entries, list):
        for entry in knowledge_entries[:3]:
            if not isinstance(entry, dict):
                continue
            entry_routes = entry.get("routes")
            if not isinstance(entry_routes, list) or not entry_routes:
                continue
            citation = {
                "label": str(entry.get("name") or "App knowledge"),
                "href": str(entry_routes[0]),
            }
            if citation not in citations:
                citations.append(citation)

    # Integration evidence needs both architecture patterns and Service Products so
    # the assistant can explain the governed design relationship without forcing a
    # single semantic retrieval result to choose one side of that relationship.
    wants_patterns = (
        integration_id is not None
        or knowledge_section == "patterns"
        or "/patterns" in route
    )
    wants_services = (
        integration_id is not None
        or knowledge_section in {"library", "pricing"}
        or "/services" in route
    )
    if is_commercial_question:
        citations.append({"label": "Pricing", "href": "/admin/pricing"})
        service_profiles = active_service_profiles
        mappings = active_service_mappings
        profile_by_service = {item.service_id: item for item in service_profiles}
        matched_mappings = [
            item
            for item in mappings
            if any(
                _reference_appears_in_dialogue(reference, dialogue_text)
                for reference in (
                    item.tool_key,
                    profile_by_service[item.service_id].name
                    if item.service_id in profile_by_service
                    else "",
                )
            )
        ]
        active_service = conversation_state.get("active_service")
        if not matched_mappings and isinstance(active_service, dict) and active_service.get("id"):
            matched_mappings = [
                item for item in mappings if item.service_id == str(active_service["id"])
            ]
        requested_byol = "byol" in dialogue_text.casefold()
        requested_edition = (
            "enterprise"
            if "enterprise" in dialogue_text.casefold()
            else "standard"
            if "standard" in dialogue_text.casefold()
            else None
        )
        if requested_byol or requested_edition:
            matched_mappings = [
                item
                for item in matched_mappings
                if (not requested_byol or item.predicates.get("byol") is True)
                and (not requested_edition or item.predicates.get("edition") == requested_edition)
            ]
        if matched_mappings:
            evidence["question_intent"] = "evidence_interpretation"
            evidence["evidence_interpretation"] = "commercial_sku"
            response_contract = evidence.get("response_contract")
            if isinstance(response_contract, dict):
                response_contract["intent"] = "evidence_interpretation"
            latest_catalog = await db.scalar(
                select(PriceCatalogSnapshot)
                .where(PriceCatalogSnapshot.approval_status == "approved")
                .order_by(PriceCatalogSnapshot.retrieved_at.desc())
                .limit(1)
            )
            part_numbers = [item.part_number for item in matched_mappings if item.part_number]
            price_by_part: dict[str, PriceItem] = {}
            if latest_catalog and part_numbers:
                price_items = list(
                    (
                        await db.scalars(
                            select(PriceItem).where(
                                PriceItem.snapshot_id == latest_catalog.id,
                                PriceItem.part_number.in_(part_numbers),
                            )
                        )
                    ).all()
                )
                price_by_part = {item.part_number: item for item in price_items}
            selected_service = profile_by_service.get(matched_mappings[0].service_id)
            evidence["commercial_service_context"] = {
                "service_id": matched_mappings[0].service_id,
                "service_name": selected_service.name if selected_service else matched_mappings[0].tool_key,
                "pricing_model": selected_service.pricing_model if selected_service else None,
                "selection": {"byol": requested_byol, "edition": requested_edition},
                "sku_options": [
                    {
                        "part_number": item.part_number,
                        "predicates": item.predicates,
                        "billing_metric_key": item.billing_metric_key,
                        "quantity_unit": item.quantity_unit,
                        "price": (
                            {
                                "display_name": price_by_part[item.part_number].display_name,
                                "metric_name": price_by_part[item.part_number].metric_name,
                                "price_type": price_by_part[item.part_number].price_type,
                                "currency": price_by_part[item.part_number].currency,
                                "value": price_by_part[item.part_number].value,
                            }
                            if item.part_number in price_by_part
                            else None
                        ),
                    }
                    for item in matched_mappings[:8]
                ],
            }
            citations.append({"label": "Service Products", "href": "/admin/services"})
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
        service_ids = [item.service_id for item in services]
        commercial_policies = list(
            (
                await db.scalars(
                    select(ServiceCommercialPolicy).where(
                        ServiceCommercialPolicy.service_id.in_(service_ids),
                        ServiceCommercialPolicy.status == "approved",
                    )
                )
            ).all()
        )
        commercial_policy_by_service = {
            item.service_id: item for item in commercial_policies
        }
        approved_mapping_rows = (
            await db.execute(
                select(
                    ServiceProductSkuMapping.service_id,
                    func.count(ServiceProductSkuMapping.id),
                )
                .where(
                    ServiceProductSkuMapping.service_id.in_(service_ids),
                    ServiceProductSkuMapping.status == "approved",
                )
                .group_by(ServiceProductSkuMapping.service_id)
            )
        ).all()
        mapping_count_by_service = {
            str(service_id): int(count)
            for service_id, count in approved_mapping_rows
        }
        evidence["service_product_library"] = [
            {
                "id": item.service_id,
                "name": item.name,
                "category": item.category,
                "architectural_fit": item.architectural_fit,
                "interoperability_notes": item.interoperability_notes,
                "commercial_classification": (
                    commercial_policy_by_service[item.service_id].classification
                    if item.service_id in commercial_policy_by_service
                    else "unclassified"
                ),
                "commercial_readiness": (
                    commercial_policy_by_service[item.service_id].readiness
                    if item.service_id in commercial_policy_by_service
                    else "blocked"
                ),
                "publication_policy": (
                    commercial_policy_by_service[item.service_id].publication_policy
                    if item.service_id in commercial_policy_by_service
                    else "policy_required"
                ),
                "governed_meter_count": mapping_count_by_service.get(item.service_id, 0),
                "required_commercial_inputs": (
                    commercial_policy_by_service[item.service_id].required_inputs
                    if item.service_id in commercial_policy_by_service
                    else ["approved commercial policy"]
                ),
                "commercial_guidance": (
                    commercial_policy_by_service[item.service_id].guidance
                    if item.service_id in commercial_policy_by_service
                    else "Commercial policy is missing; BOM publication is blocked."
                ),
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
            bom_line_items = (
                list(
                    (
                        await db.scalars(
                            select(BomLineItem)
                            .where(BomLineItem.bom_snapshot_id == latest_bom.id)
                            .order_by(BomLineItem.contract_amount.desc(), BomLineItem.description)
                            .limit(40)
                        )
                    ).all()
                )
                if latest_bom
                else []
            )
            review_query = (
                select(AiReviewJob)
                .where(
                    AiReviewJob.project_id == project.id,
                    AiReviewJob.status == "completed",
                )
                .order_by(AiReviewJob.finished_at.desc(), AiReviewJob.created_at.desc())
                .limit(1)
            )
            if integration is not None:
                review_query = review_query.where(AiReviewJob.integration_id == integration.id)
            latest_ai_review = await db.scalar(review_query)
            coverage_rows = (
                await db.execute(
                    select(
                        ProductCoverageCandidate.readiness_status,
                        func.count(ProductCoverageCandidate.id),
                    ).group_by(ProductCoverageCandidate.readiness_status)
                )
            ).all()
            latest_scenario = scenarios[0] if scenarios else None
            environment_plans = (
                list(
                    (
                        await db.scalars(
                            select(DeploymentEnvironmentPlan)
                            .where(DeploymentEnvironmentPlan.scenario_id == latest_scenario.id)
                            .order_by(DeploymentEnvironmentPlan.sequence)
                        )
                    ).all()
                )
                if latest_scenario
                else []
            )
            ramp_phases = []
            if environment_plans:
                ramp_phases = list(
                    (
                        await db.scalars(
                            select(DeploymentRampPhase)
                            .where(
                                DeploymentRampPhase.environment_plan_id.in_(
                                    [item.id for item in environment_plans]
                                )
                            )
                            .order_by(DeploymentRampPhase.start_month)
                            .limit(80)
                        )
                    ).all()
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
                "latest_scenario_configuration": (
                    {
                        "id": latest_scenario.id,
                        "name": latest_scenario.name,
                        "status": latest_scenario.status,
                        "region": latest_scenario.region,
                        "currency": latest_scenario.currency,
                        "price_mode": latest_scenario.price_mode,
                        "commitment_model": latest_scenario.commitment_model,
                        "licensing_model": latest_scenario.licensing_model,
                        "contract_months": latest_scenario.contract_months,
                        "start_date": latest_scenario.start_date,
                        "environments": [
                            {
                                "id": item.id,
                                "name": item.name,
                                "active_hours_month": item.active_hours_month,
                                "demand_share": item.demand_share,
                                "ha_multiplier": item.ha_multiplier,
                                "dr_role": item.dr_role,
                            }
                            for item in environment_plans
                        ],
                        "phases": [
                            {
                                "environment_plan_id": item.environment_plan_id,
                                "service_id": item.service_id,
                                "metric_key": item.metric_key,
                                "start_month": item.start_month,
                                "end_month": item.end_month,
                                "start_quantity": item.start_quantity,
                                "end_quantity": item.end_quantity,
                                "quantity_unit": item.quantity_unit,
                                "interpolation": item.interpolation,
                            }
                            for item in ramp_phases
                        ],
                    }
                    if latest_scenario
                    else None
                ),
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
                        "line_items": [
                            {
                                "environment": item.environment,
                                "service_id": item.service_id,
                                "part_number": item.part_number,
                                "description": item.description,
                                "metric_name": item.metric_name,
                                "quantity": item.quantity,
                                "unit": item.unit,
                                "unit_price": item.unit_price,
                                "monthly_amount": item.monthly_amount,
                                "contract_amount": item.contract_amount,
                                "formula": item.formula,
                                "status": item.status,
                                "warnings": item.warnings,
                                "provenance": item.provenance,
                            }
                            for item in bom_line_items
                        ],
                    }
                    if latest_bom
                    else None
                ),
                "latest_ai_review": (
                    {
                        "id": latest_ai_review.id,
                        "scope": latest_ai_review.scope,
                        "integration_id": latest_ai_review.integration_id,
                        "decision_brief": cast(dict[str, object], latest_ai_review.result_payload or {}).get("decision_brief"),
                        "summary": cast(dict[str, object], latest_ai_review.result_payload or {}).get("summary"),
                        "findings": cast(dict[str, object], latest_ai_review.result_payload or {}).get("findings", []),
                        "recommendation": cast(dict[str, object], latest_ai_review.result_payload or {}).get("recommendation"),
                    }
                    if latest_ai_review
                    else None
                ),
                "commercial_coverage": {
                    "ready": sum(
                        int(count)
                        for status, count in coverage_rows
                        if str(status) == "ready"
                    ),
                    "blocked": sum(
                        int(count)
                        for status, count in coverage_rows
                        if str(status) != "ready"
                    ),
                    "by_status": {str(status): int(count) for status, count in coverage_rows},
                },
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
            if evidence_interpretation.startswith("bom"):
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

    evidence["verified_facts"] = _verified_facts(evidence)
    evidence["next_actions"] = _support_next_actions(evidence)
    actions = evidence["next_actions"]
    raw_allowed_routes = app_knowledge.get("allowed_routes")
    allowed_route_items = raw_allowed_routes if isinstance(raw_allowed_routes, list) else []
    allowed_routes = {
        str(item).split("?", 1)[0].rstrip("/") or "/"
        for item in allowed_route_items
    }
    if route.startswith("/"):
        allowed_routes.add(route.split("?", 1)[0].rstrip("/") or "/")
    if isinstance(actions, list):
        allowed_routes.update(
            str(action.get("href")).split("?", 1)[0].rstrip("/") or "/"
            for action in actions
            if isinstance(action, dict) and str(action.get("href") or "").startswith("/")
        )
    app_knowledge["allowed_routes"] = sorted(allowed_routes)
    if isinstance(actions, list) and actions and isinstance(actions[0], dict):
        evidence["recommended_next_action"] = str(actions[0].get("label") or "Open the relevant App workspace")
        evidence["recommended_next_action_route"] = str(actions[0].get("href") or "/projects")
    citations[:] = _deduplicate_citations(citations)
    evidence["fallback_answer"] = _fallback_with_action(_evidence_fallback(evidence), evidence)
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
    if support_output_contains_internal_reasoning(content):
        message.content = WITHHELD_INTERNAL_RESPONSE
        message.status = "failed"
        message.citations = []
    else:
        message.content = content[:12000]
        message.status = status
        message.citations = cast(list, sanitize_for_json(_deduplicate_citations(citations)[:12]))
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
