"""Presentation and grounding contracts shared by every governed agent."""

from app.agents.registry import get_agent_definition
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
