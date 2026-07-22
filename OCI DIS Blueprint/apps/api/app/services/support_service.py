"""Session-isolated contextual support conversation services."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
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
    PriceCatalogSnapshot,
    PriceItem,
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
    knowledge_grounding_failure,
)
from app.services.serializers import sanitize_for_json
from app.services.support_routing_service import (
    PROJECT_PORTFOLIO_PATTERN,
    SupportRoute,
    is_commercial_follow_up,
    route_support_question,
)


WITHHELD_INTERNAL_RESPONSE = (
    "This response was withheld because it contained internal generation notes. "
    "Please ask the question again to receive a governed answer."
)
OUTSIDE_TOPIC_PATTERN = re.compile(
    r"\b(weather|forecast outside|sports|score|recipe|poem|song|politics|president|celebrity|horoscope|"
    r"clima|deportes|receta|poema|cancion|politica|presidente|celebridad|horoscopo)\b",
    re.IGNORECASE,
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
    project = evidence.get("project")
    project_id = str(project.get("id")) if isinstance(project, dict) and project.get("id") else None
    integration = evidence.get("integration")
    if isinstance(integration, dict) and integration.get("id") and project_id:
        return [{
            "label": "Abrir detalle de integración" if spanish else "Open integration detail",
            "href": f"/projects/{project_id}/catalog/{integration['id']}",
            "reason": "Review the governed row, QA evidence, and design canvas.",
        }]
    intent = str(evidence.get("question_intent") or "")
    if project_id:
        suffix_by_intent = {
            "project_cost": "/bom",
            "commercial_guidance": "/bom",
            "business_process": "/catalog",
        }
        suffix = suffix_by_intent.get(intent, "")
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
    if intent == "commercial_guidance":
        return [{"label": "Abrir Pricing" if spanish else "Open Pricing", "href": "/admin/pricing", "reason": "Review governed products, SKUs, metrics, and releases."}]
    if "pattern_library" in evidence:
        return [{"label": "Abrir patrones" if spanish else "Open Patterns", "href": "/admin/patterns", "reason": "Review the governed pattern definition and applicability."}]
    if "service_product_library" in evidence:
        return [{"label": "Abrir productos" if spanish else "Open Service Products", "href": "/admin/services", "reason": "Review governed service evidence and interoperability."}]
    if current_route.startswith("/"):
        return [{"label": "Continuar en esta vista" if spanish else "Continue in this view", "href": current_route, "reason": "Use the current App context."}]
    return [{"label": "Abrir proyectos" if spanish else "Open Projects", "href": "/projects", "reason": "Select the project or workspace you want to investigate."}]


def _fallback_with_action(answer: str, evidence: dict[str, object]) -> str:
    """Keep provider-failure answers useful and navigable."""

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


def _unit_price(value: object, currency: object) -> str:
    """Render a catalog unit price without losing governed decimal precision."""

    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return _money(value, currency)
    return f"{str(currency or 'USD').upper()} {format(amount.normalize(), 'f')}"


def _price_type_label(value: object, *, spanish: bool) -> str:
    """Present a governed billing period in the user's language."""

    normalized = str(value or "unit").upper()
    labels = {
        "HOUR": ("hora", "hour"),
        "MONTH": ("mes", "month"),
        "YEAR": ("año", "year"),
        "PER_ITEM": ("unidad", "unit"),
        "UNIT": ("unidad", "unit"),
    }
    return labels.get(normalized, ("unidad", "unit"))[0 if spanish else 1]


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


def _pattern_answer(evidence: dict[str, object]) -> str | None:
    """Return a direct, evidence-backed explanation for a named pattern."""

    patterns = evidence.get("pattern_library")
    question = str(evidence.get("current_question") or "")
    if not isinstance(patterns, list) or not question:
        return None
    matched = next(
        (
            item
            for item in patterns
            if isinstance(item, dict)
            and any(
                _reference_appears_in_dialogue(item.get(reference), question)
                for reference in ("id", "name")
            )
        ),
        None,
    )
    if not isinstance(matched, dict):
        return None
    spanish = evidence.get("response_language") == "es"
    name = str(matched.get("name") or matched.get("id") or "the pattern")
    description = str(matched.get("description") or "").strip()
    when_to_use = str(matched.get("when_to_use") or "").strip()
    when_not_to_use = str(matched.get("when_not_to_use") or "").strip()
    if spanish:
        parts = [
            f"**{name}** es un patrón gobernado de integración. Descripción gobernada: {description}"
            if description
            else f"**{name}** es un patrón gobernado de integración."
        ]
        if when_to_use:
            parts.append(f"Úsalo cuando se cumpla la siguiente condición gobernada: {when_to_use}")
        if when_not_to_use:
            parts.append(f"No es adecuado cuando se cumpla lo siguiente: {when_not_to_use}")
        return "\n\n".join(parts)
    parts = [f"**{name}**: {description}" if description else f"**{name}** is a governed integration pattern."]
    if when_to_use:
        parts.append(f"Use it when {when_to_use[0].lower() + when_to_use[1:]}")
    if when_not_to_use:
        parts.append(f"It is not appropriate when {when_not_to_use[0].lower() + when_not_to_use[1:]}")
    return "\n\n".join(parts)


def _support_fallback_answer(evidence: dict[str, object]) -> str:
    """Build a concise App-owned answer when provider grounding is insufficient."""

    spanish = evidence.get("response_language") == "es"
    app_redirect = evidence.get("app_redirect")
    if isinstance(app_redirect, dict) and app_redirect.get("required") is True:
        if spanish:
            return (
                "No puedo responder sobre ese tema externo. Estoy aqui para ayudarte con OCI DIS Architect: "
                "integraciones, procesos, topologia, gobernanza, dimensionamiento y BOM & Cost.\n\n"
                "Dime que decision de arquitectura necesitas tomar y usare la evidencia gobernada disponible."
            )
        return (
            "I can’t answer that external-topic question. I’m here to help with OCI DIS Architect: "
            "integrations, business processes, topology, governance, sizing, and BOM & Cost.\n\n"
            "Tell me the architecture decision you need to make and I’ll use the available governed evidence."
        )
    pattern_answer = _pattern_answer(evidence)
    if pattern_answer:
        return pattern_answer
    integration = evidence.get("integration")
    process = evidence.get("business_process_flow")
    if evidence.get("question_intent") == "commercial_guidance":
        commercial_context = evidence.get("commercial_service_context")
        if isinstance(commercial_context, dict):
            sku_options = commercial_context.get("sku_options")
            priced_options = [
                option
                for option in sku_options
                if isinstance(option, dict) and isinstance(option.get("price"), dict)
            ] if isinstance(sku_options, list) else []
            if len(priced_options) > 1:
                service_name = str(commercial_context.get("service_name") or "the selected service")
                metric_keys = {
                    str(option.get("billing_metric_key") or "")
                    for option in priced_options
                    if option.get("billing_metric_key")
                }
                metric_count = len(metric_keys)
                option_summaries = []
                for option in priced_options[:4]:
                    price = cast(dict[str, object], option["price"])
                    predicates = cast(dict[str, object], option.get("predicates") or {})
                    selection_parts = []
                    if predicates.get("edition"):
                        selection_parts.append(str(predicates["edition"]).title())
                    if predicates.get("byol") is True:
                        selection_parts.append("BYOL")
                    selection = " ".join(selection_parts) or str(
                        price.get("metric_name") or option.get("part_number") or "governed option"
                    )
                    option_summaries.append(
                        f"{selection} ({option.get('part_number')}): {_unit_price(price.get('value'), price.get('currency'))} "
                        f"por {_price_type_label(price.get('price_type'), spanish=spanish)}"
                    )
                if metric_count > 1:
                    if spanish:
                        return (
                            f"**{service_name}** se cobra por más de una métrica de consumo. Los precios unitarios gobernados "
                            f"se suman en la factura del cliente: {'; '.join(option_summaries)}.\n\n"
                            "BOM & Cost aplica a cada métrica la cantidad dimensionada del escenario; no son alternativas "
                            "de licencia que haya que escoger."
                        )
                    return (
                        f"**{service_name}** is billed through more than one consumption metric. The governed unit prices "
                        f"are additive on the customer invoice: {'; '.join(option_summaries)}.\n\n"
                        "BOM & Cost applies the scenario's sized quantity to each metric; these are not license alternatives to choose between."
                    )
                if spanish:
                    return (
                        f"Identifiqué **{service_name}** y su modalidad de licencia, pero hay más de una opción "
                        f"gobernada aplicable: {'; '.join(option_summaries)}.\n\n"
                        "Indica la edición que contratará el cliente para seleccionar un SKU. Después BOM & Cost "
                        "aplica la cantidad dimensionada y el escenario para obtener el total."
                    )
                return (
                    f"I identified **{service_name}** and its license mode, but more than one governed option applies: "
                    f"{'; '.join(option_summaries)}.\n\n"
                    "Specify the edition the client will contract so the App can select one SKU. BOM & Cost then applies "
                    "sized quantity and the scenario to calculate the total."
                )
            if isinstance(sku_options, list) and len(sku_options) == 1 and isinstance(sku_options[0], dict):
                single_option = cast(dict[str, object], sku_options[0])
                single_price = single_option.get("price")
                if isinstance(single_price, dict):
                    service_name = str(commercial_context.get("service_name") or "the selected service")
                    part_number = str(single_option.get("part_number") or "the selected SKU")
                    display_name = str(single_price.get("display_name") or service_name)
                    metric = str(single_price.get("metric_name") or "the governed metric")
                    unit_price = _unit_price(
                        single_price.get("value"), single_price.get("currency")
                    )
                    price_type = str(single_price.get("price_type") or "unit")
                    if spanish:
                        localized_price_type = _price_type_label(price_type, spanish=True)
                        return (
                            f"Para {service_name}, la selección capturada corresponde al SKU **{part_number}** "
                            f"({display_name}). El catálogo aprobado registra **{unit_price} por {localized_price_type}** "
                            f"para la métrica **{metric}**.\n\n"
                            "Ese es el precio público unitario gobernado, no un total ni una tarifa contractual. "
                            "El total depende de la cantidad dimensionada y del escenario de despliegue; BOM & Cost "
                            "calcula ambos con la evidencia del proyecto."
                        )
                    return (
                        f"For {service_name}, the captured selection maps to SKU **{part_number}** "
                        f"({display_name}). The approved catalog records **{unit_price} per {price_type.lower()}** "
                        f"for **{metric}**.\n\n"
                        "That is governed public unit pricing, not a total or a contractual rate. The total depends on "
                        "sized quantity and deployment scenario; BOM & Cost calculates both from project evidence."
                    )
        if spanish:
            return (
                "Puedo buscar el precio gobernado, pero el diálogo no identifica todavía un Service Product/SKU y "
                "su modelo de licencia. Indica el servicio o conserva ese dato en el contexto; después la App puede "
                "distinguir precio unitario, cantidad dimensionada y total del BOM."
            )
        return (
            "I can look up governed pricing, but the dialogue does not yet identify a Service Product/SKU and its "
            "license model. Name the service or preserve that detail in context; the App can then distinguish unit "
            "price, sized quantity, and the BOM total."
        )
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
    app_knowledge = evidence.get("app_knowledge")
    if isinstance(app_knowledge, dict) and evidence.get("question_intent") in {
        "app_guidance",
        "workflow_guidance",
    }:
        fallback = app_knowledge.get("fallback_answer")
        if isinstance(fallback, str) and fallback:
            return fallback
    if spanish:
        return (
            "OCI DIS Architect te ayuda a importar y gobernar integraciones, revisar su calidad, calcular volumetría, "
            "analizar topología y preparar escenarios y BOM con evidencia trazable.\n\n"
            "Puedo explicarte cualquier workflow de la App o ayudarte a interpretar la evidencia de un proyecto, integración, "
            "patrón, Service Product o BOM."
        )
    return (
        "OCI DIS Architect helps you import and govern integrations, review their quality, calculate volumetry, "
        "analyze topology, and prepare traceable scenarios and BOMs.\n\n"
        "I can explain any App workflow or help interpret evidence for a project, integration, pattern, Service Product, or BOM."
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
    pattern_answer = _pattern_answer(evidence)
    if pattern_answer:
        patterns = evidence.get("pattern_library")
        if isinstance(patterns, list):
            question = str(evidence.get("current_question") or "")
            match = next(
                (
                    item for item in patterns
                    if isinstance(item, dict)
                    and any(_reference_appears_in_dialogue(item.get(key), question) for key in ("id", "name"))
                ),
                None,
            )
            if isinstance(match, dict):
                state["active_pattern"] = {"id": match.get("id"), "name": match.get("name")}
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
    # The current turn determines intent. History only resolves references
    # inside a commercial follow-up; it must not convert a new pattern or App
    # question into the previous turn's commercial question.
    project_is_explicit = needs_project_scope or project_resolution in {
        "attached_context",
        "named_in_conversation",
        "single_active_project",
        "integration_context",
    }
    support_route: SupportRoute = route_support_question(
        question,
        project_is_explicit=project_is_explicit,
        needs_project_scope=needs_project_scope,
    )
    # A follow-up such as “what metrics are added for that service?” can use
    # only a Service Product reference that was previously resolved and stored
    # in the compact ledger.  This is deliberately narrower than carrying the
    # entire old intent into unrelated questions.
    if (
        support_route.intent == "app_guidance"
        and isinstance(conversation_state.get("active_service"), dict)
        and is_commercial_follow_up(question)
    ):
        support_route = SupportRoute("commercial_guidance", True, False)
    question_intent = support_route.intent
    is_commercial_question = support_route.needs_commercial_evidence
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
    app_knowledge = build_app_knowledge_evidence(
        question,
        route,
        language=response_language,
        project_id=resolved_project_id,
        integration_id=integration_id,
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
        "response_contract": {
            "intent": question_intent,
            "requires_governed_commercial_evidence": support_route.needs_commercial_evidence,
            "model_authorship": "primary",
            "deterministic_fallback": "provider_failure_or_grounding_failure_only",
            "rule": "A new question replaces the previous topic; conversation state only resolves an explicit reference.",
        },
        "app_redirect": (
            {
                "required": True,
                "reason": "The question is outside OCI DIS Architect. Acknowledge it briefly without answering the external topic, then redirect to useful App capabilities.",
            }
            if OUTSIDE_TOPIC_PATTERN.search(question)
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
    if isinstance(knowledge_entries, list) and knowledge_entries:
        primary_entry = knowledge_entries[0]
        if isinstance(primary_entry, dict):
            entry_routes = primary_entry.get("routes")
            if isinstance(entry_routes, list) and entry_routes:
                citations.append(
                    {
                        "label": str(primary_entry.get("name") or "App knowledge"),
                        "href": str(entry_routes[0]),
                    }
                )

    wants_patterns = any(term in question_lower for term in ("pattern", "patrón", "patron")) or "/patterns" in route
    wants_services = any(
        term in question_lower
        for term in ("service product", "servicio", "interoperability", "interoperabilidad", "limit", "límite")
    ) or "/services" in route
    if is_commercial_question:
        citations.append({"label": "Pricing", "href": "/admin/pricing"})
        service_profiles = list(
            (
                await db.scalars(
                    select(ServiceCapabilityProfile)
                    .where(ServiceCapabilityProfile.is_active.is_(True))
                    .order_by(ServiceCapabilityProfile.name)
                )
            ).all()
        )
        mappings = list(
            (
                await db.scalars(
                    select(ServiceProductSkuMapping).where(
                        ServiceProductSkuMapping.status == "approved",
                        ServiceProductSkuMapping.is_billable.is_(True),
                    )
                )
            ).all()
        )
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
    evidence["fallback_answer"] = _fallback_with_action(_support_fallback_answer(evidence), evidence)
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
