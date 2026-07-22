"""Typed, deterministic routing for the contextual App Assistant.

The router decides *what kind* of answer the turn needs.  It never resolves a
product, price, project, or architecture fact; those remain the responsibility
of the bounded evidence builder.  Keeping this policy separate makes a new
question replace the previous topic instead of inheriting a stale intent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


SupportIntent = Literal[
    "capability_inquiry",
    "unsupported_or_out_of_scope",
    "project_portfolio",
    "project_cost",
    "commercial_guidance",
    "workflow_guidance",
    "project_context",
    "app_guidance",
]


CAPABILITY_INQUIRY_PATTERN = re.compile(
    r"\b(?:can|could|does)\s+(?:i|we|it|the app|this app|oci dis architect)\b|"
    r"\b(?:is there|does (?:the )?app (?:allow|support|provide)|supports? the app)\b|"
    r"\bis\b.{1,80}\b(?:supported|available)\b|"
    r"\b(?:puedo|podemos|se puede|la app (?:permite|soporta|ofrece)|oci dis architect (?:permite|soporta|ofrece))\b",
    re.IGNORECASE,
)

OUTSIDE_TOPIC_PATTERN = re.compile(
    r"\b(weather|forecast outside|sports|score|recipe|poem|song|politics|president|celebrity|horoscope|"
    r"clima|deportes|receta|poema|cancion|politica|presidente|celebridad|horoscopo)\b",
    re.IGNORECASE,
)


PROJECT_PORTFOLIO_PATTERN = re.compile(
    r"\b(how many|list|show|which|cu[aá]ntos|lista|muestra|cu[aá]les)\b.{0,28}\b(projects?|proyectos?)\b",
    re.IGNORECASE,
)
COMMERCIAL_GUIDANCE_PATTERN = re.compile(
    r"\b(pricing|price|cost|cuesta|cu[aá]nto|precio|costo|billing|bill\w*|factur\w*|cobr\w*|license|licencia|enterprise|"
    r"bom|bill of materials|sku|rate card|tarifa)\b",
    re.IGNORECASE,
)
WORKFLOW_PATTERN = re.compile(
    r"\b(import\w*|captur\w*|catalog\w*|cat[aá]log\w*|qa|quality|calidad|"
    r"volumetry|volumetr[ií]a|dashboard|map|topology|topolog[ií]a|scenario|escenario|"
    r"export|exportar|dictionary|diccionario|assumption|supuesto|agent|agente|governance|gobernanza)\b",
    re.IGNORECASE,
)
BILLING_SIGNAL_PATTERN = re.compile(
    r"\b(pricing|price|cost|cuesta|cu[aá]nto|precio|costo|billing|bill\w*|factur\w*|cobr\w*|rate card|tarifa)\b",
    re.IGNORECASE,
)
LICENSING_WORKFLOW_PATTERN = re.compile(
    r"\b(byol|license included|licencia incluida|modelo de licencia|licensing model)\b",
    re.IGNORECASE,
)
COMMERCIAL_FOLLOW_UP_PATTERN = re.compile(
    r"\b(metric\w*|m[eé]tric\w*|unit\w*|unidad\w*|sum\w*|add\w*|cantidad\w*|quantity\w*)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SupportRoute:
    """The explicit response contract selected before evidence retrieval."""

    intent: SupportIntent
    needs_commercial_evidence: bool
    should_answer_deterministically: bool


def route_support_question(
    question: str,
    *,
    project_is_explicit: bool,
    needs_project_scope: bool,
) -> SupportRoute:
    """Classify the current turn only; conversation history must not steer intent."""

    if OUTSIDE_TOPIC_PATTERN.search(question):
        return SupportRoute("unsupported_or_out_of_scope", False, True)
    if PROJECT_PORTFOLIO_PATTERN.search(question):
        return SupportRoute("project_portfolio", False, True)
    # Capability checks must run before commercial routing. A question such as
    # "Can I configure cost-threshold email alerts?" contains a cost token, but
    # it asks whether an App action exists rather than requesting pricing data.
    if CAPABILITY_INQUIRY_PATTERN.search(question):
        return SupportRoute("capability_inquiry", False, True)
    # A BOM/scenario/licensing question describes an App workflow unless it
    # also asks for a price or billing fact.  This prevents “what is BYOL in a
    # scenario?” from being treated as an incomplete SKU lookup.
    if (WORKFLOW_PATTERN.search(question) or LICENSING_WORKFLOW_PATTERN.search(question)) and not BILLING_SIGNAL_PATTERN.search(question):
        return SupportRoute("workflow_guidance", False, True)
    if COMMERCIAL_GUIDANCE_PATTERN.search(question):
        if project_is_explicit:
            return SupportRoute("project_cost", True, True)
        return SupportRoute("commercial_guidance", True, False)
    if needs_project_scope:
        return SupportRoute("project_context", False, False)
    return SupportRoute("app_guidance", False, False)


def is_commercial_follow_up(question: str) -> bool:
    """Recognize a narrow commercial ellipsis after a service was resolved."""

    return bool(COMMERCIAL_FOLLOW_UP_PATTERN.search(question))
