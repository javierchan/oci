"""Agent prompt contracts remain concise and presentation-safe."""

from app.agents.registry import get_agent_definition


def test_architecture_review_agent_requests_plain_language_decision_brief() -> None:
    definition = get_agent_definition("architecture_review")

    assert definition.version == "1.1.0"
    assert "why it matters" in definition.instruction
    assert "next concrete action" in definition.instruction
    assert "Never output a Markdown table" in definition.instruction


def test_support_assistant_resolves_global_project_dossiers() -> None:
    definition = get_agent_definition("support_assistant")

    assert definition.version == "1.2.0"
    assert "project_resolution" in definition.instruction
    assert "contract total" in definition.instruction
    assert "ambiguous" in definition.instruction
