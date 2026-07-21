"""Presentation and grounding contracts shared by every governed agent."""

from app.agents.registry import get_agent_definition
from app.services.agent_decision_service import build_decision_workspace
from app.services.agent_output_service import govern_agent_output


def test_service_verification_rejects_meta_reasoning_and_unverified_freshness() -> None:
    output = govern_agent_output(
        get_agent_definition("service_verification"),
        "The user asked for verification. We need to respond that all 20 services are current.",
        {
            "sources_checked": 0,
            "changes_detected": 0,
            "services_checked": [],
            "findings": [],
            "recommendations": [],
        },
    )

    assert output.quality.fallback_used is True
    assert output.quality.fallback_reason == "internal_reasoning"
    assert "Official-source evidence is incomplete" in output.summary
    assert "20 services" not in output.summary
    assert output.brief.confidence == "low"


def test_bom_agent_rejects_markdown_table_and_invented_commercial_claims() -> None:
    output = govern_agent_output(
        get_agent_definition("bom_scenario"),
        "| Product | Monthly total |\n| --- | --- |\n| OIC | USD 10,000 |",
        {
            "detected_services": ["OIC3"],
            "required_questions": ["Confirm the OIC edition for Production."],
            "commercial_coverage": [],
            "warnings": [],
            "confidence": "medium",
        },
    )

    assert output.quality.fallback_reason == "markdown_table"
    assert "USD 10,000" not in output.summary
    assert output.brief.next_actions == ["Confirm the OIC edition for Production."]
    assert output.brief.validation


def test_bom_agent_prioritizes_current_published_bom() -> None:
    output = govern_agent_output(
        get_agent_definition("bom_scenario"),
        "The published baseline is current and ready for governed use.",
        {
            "current_bom": {
                "snapshot_id": "bom-1",
                "scenario_id": "scenario-1",
                "technical_snapshot_id": "technical-1",
                "ready_for_use": True,
                "coverage_pct": 100,
                "line_item_count": 17,
                "currency": "USD",
                "contract_total": 29212.92,
                "environment_names": ["Production"],
            },
            "detected_services": ["OIC3"],
            "required_questions": [],
            "commercial_coverage": [],
            "warnings": [],
            "confidence": "high",
        },
    )

    assert output.brief.headline == "Published BOM is ready for governed use"
    assert "USD 29,212.92" in output.brief.finding
    assert output.brief.next_actions == [
        "Keep this baseline unless architecture, environment timing, SKU selection, or approved price evidence changes."
    ]
    assert output.brief.confidence == "high"

    workspace, proposals = build_decision_workspace(
        get_agent_definition("bom_scenario"),
        {
            "current_bom": {
                "snapshot_id": "bom-1",
                "scenario_id": "scenario-1",
                "technical_snapshot_id": "technical-1",
                "ready_for_use": True,
                "coverage_pct": 100,
                "line_item_count": 17,
                "currency": "USD",
                "contract_total": 29212.92,
                "environment_names": ["Production"],
            },
            "detected_services": ["OIC3"],
            "required_questions": [],
        },
        project_id="project-1",
        integration_id=None,
    )
    assert workspace.recommended_alternative_id == "keep-published-baseline"
    assert workspace.outcome_metrics[2]["value"] == 0
    assert proposals == []


def test_architecture_agent_keeps_grounded_plain_language_and_adds_typed_brief() -> None:
    evidence: dict[str, object] = {
        "decision_brief": {
            "headline": "Resolve design coverage before sign-off",
            "primary_risk": "One governed integration lacks a complete route.",
            "recommended_next_action": "Open the affected integration and complete its canvas.",
        },
        "evidence": [{"id": "EV-005", "label": "Canvas coverage"}],
        "findings": [],
    }
    output = govern_agent_output(
        get_agent_definition("architecture_review"),
        "Resolve design coverage before sign-off. Open the affected integration next.",
        evidence,
    )

    assert output.quality.grounded is True
    assert output.quality.fallback_used is False
    assert output.brief.headline == "Resolve design coverage before sign-off"
    assert output.brief.evidence_ids == ["EV-005"]
    assert output.quality.evidence_completeness_pct == 100


def test_support_assistant_removes_model_deliberation_without_discarding_answer() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        (
            "The user asks how the App prices a governed service. "
            "The governed catalog lists OIC Gen3 Enterprise BYOL at USD 0.3226 per hour. "
            "Open BOM & Cost to apply the dimensioned quantity."
        ),
        {
            "fallback_answer": "Use the governed catalog and BOM & Cost.",
            "commercial_service_context": {"unit_price": "0.3226"},
            "recommended_next_action": "Open BOM & Cost.",
        },
    )

    assert output.quality.grounded is True
    assert output.quality.fallback_used is False
    assert "The user asks" not in output.summary
    assert "USD 0.3226 per hour" in output.summary


def test_support_assistant_fallback_is_the_answer_without_generic_wrapper() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        "The user asks about a pattern. We need to provide an answer.",
        {
            "fallback_answer": "Request and Reply waits for the target service response.",
            "recommended_next_action": "Open the Pattern Library.",
        },
    )

    assert output.quality.fallback_used is True
    assert output.summary == "Request and Reply waits for the target service response."
    assert "Answer from governed App context" not in output.summary
    assert "Next action:" not in output.summary


def test_support_assistant_removes_redacted_sentence_and_keeps_grounded_answer() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        (
            "Request and Reply keeps the caller waiting for the target response. "
            "Open /projects/[REDACTED] to inspect the pattern."
        ),
        {"fallback_answer": "Use the Pattern Library."},
    )

    assert output.quality.fallback_used is False
    assert output.summary == "Request and Reply keeps the caller waiting for the target response."
    assert "REDACTED" not in output.summary


def test_support_assistant_fails_closed_after_model_draft_marker() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        (
            "User asks Spanish about App pricing. We have evidence of governed rate cards. "
            "Let's draft. Para estimar el total, selecciona el SKU gobernado y genera el BOM."
        ),
        {
            "fallback_answer": "Use the governed catalog and BOM & Cost.",
            "recommended_next_action": "Open BOM & Cost.",
        },
    )

    assert output.quality.grounded is False
    assert output.quality.fallback_used is True
    assert output.quality.fallback_reason == "internal_reasoning"
    assert "User asks" not in output.summary
    assert "Let's draft" not in output.summary
    assert output.summary == "Use the governed catalog and BOM & Cost."


def test_support_assistant_keeps_final_answer_after_visible_heading() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        "We must produce Spanish text. The tool result contains governed evidence.\n\nQué encontré\nEl SKU gobernado se calcula en BOM & Cost.",
        {
            "fallback_answer": "Use the governed catalog and BOM & Cost.",
            "recommended_next_action": "Open BOM & Cost.",
        },
    )

    assert output.quality.grounded is True
    assert output.summary.startswith("Qué encontré")
    assert "We must" not in output.summary


def test_support_assistant_removes_unheaded_model_planning_sentences() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        (
            "We have tool output. Need answer in Spanish, no table. "
            "The tool gave governed evidence. So: Para calcular el costo, abre BOM & Cost."
        ),
        {
            "fallback_answer": "Use the governed catalog and BOM & Cost.",
            "recommended_next_action": "Open BOM & Cost.",
        },
    )

    assert output.quality.grounded is True
    assert output.summary == "Para calcular el costo, abre BOM & Cost."


def test_support_assistant_rejects_unheaded_planning_that_uses_we_need_without_to() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        "We need produce an answer from the tool evidence. It should mention the import workflow.",
        {"fallback_answer": "La App conserva evidencia de importación gobernada."},
    )

    assert output.quality.fallback_used is True
    assert output.summary == "La App conserva evidencia de importación gobernada."


def test_support_assistant_rejects_an_answer_that_omits_an_explicit_app_question() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        "Abre el proyecto y revisa sus integraciones antes de tomar una decisión.",
        {
            "current_question": "¿Qué resuelve OCI DIS Architect?",
            "fallback_answer": "OCI DIS Architect gobierna integraciones y su evidencia.",
        },
    )

    assert output.quality.fallback_reason == "answer_not_relevant"
    assert output.summary == "OCI DIS Architect gobierna integraciones y su evidencia."


def test_support_assistant_removes_provider_deliberation_before_a_final_answer() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        (
            "It returned a content that is not final. The fallback answer contains a summary. "
            "So we must provide the answer. OCI DIS Architect gobierna integraciones y su evidencia."
        ),
        {"fallback_answer": "Usa la evidencia gobernada."},
    )

    assert output.quality.fallback_used is False
    assert output.summary == "OCI DIS Architect gobierna integraciones y su evidencia."


def test_support_assistant_keeps_how_to_answer_heading_after_model_planning() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        "User asked about a workflow. We have tool data.\n\nCómo completar el flujo\nAbre el workspace y revisa la evidencia gobernada.",
        {
            "fallback_answer": "Use the governed workspace.",
            "recommended_next_action": "Open the workspace.",
        },
    )

    assert output.quality.grounded is True
    assert output.summary.startswith("Cómo completar el flujo")
    assert "User asked" not in output.summary


def test_support_assistant_rejects_visible_drafting_rationale_from_provider() -> None:
    leaked_rationale = (
        "Must use evidence. Avoid tables. Provide navigation suggestion. So give direct answer. "
        "Also after answer, mention evidence, next actions: click on sections, or create project. "
        "Provide how user can validate: view sections. Use citations: attached citations with href. "
        "Use simple paragraphs. Let's craft. Ensure no summary. We'll follow style."
    )
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        leaked_rationale,
        {
            "current_question": "What can I do in this App?",
            "fallback_answer": (
                "OCI DIS Architect lets you govern integration catalogs, calculate volumetry, "
                "review topology, and build an evidence-backed BOM."
            ),
        },
    )

    assert output.quality.fallback_used is True
    assert output.quality.fallback_reason == "internal_reasoning"
    assert output.summary.startswith("OCI DIS Architect lets you govern")
    assert "Must use evidence" not in output.summary
    assert "Let's craft" not in output.summary


def test_support_assistant_fails_closed_when_drafting_notes_prefix_an_answer() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        "Use simple paragraphs. Let's craft. The App answer would be shown here.",
        {"fallback_answer": "Use the governed App workspace and its cited evidence."},
    )

    assert output.quality.fallback_used is True
    assert output.summary == "Use the governed App workspace and its cited evidence."
    assert "craft" not in output.summary.casefold()


def test_agent_output_rejects_claim_that_the_agent_changed_governed_data() -> None:
    output = govern_agent_output(
        get_agent_definition("import_quality"),
        "We updated the missing source rows and the import is ready.",
        {
            "batch_id": "batch-1",
            "included_count": 10,
            "excluded_count": 2,
            "recommended_next_action": "Review the two excluded rows.",
            "findings": [],
        },
    )

    assert output.quality.fallback_reason == "unverified_mutation_claim"
    assert "updated" not in output.summary.casefold()
    assert "Review the two excluded rows" in output.summary
