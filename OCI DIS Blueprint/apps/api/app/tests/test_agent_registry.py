"""Agent prompt contracts remain concise and presentation-safe."""

from app.agents.registry import get_agent_definition


def test_architecture_review_agent_requests_plain_language_decision_brief() -> None:
    definition = get_agent_definition("architecture_review")

    assert definition.version == "2.0.0"
    assert "why it matters" in definition.instruction
    assert "next concrete action" in definition.instruction
    assert "Never output a Markdown table" in definition.instruction


def test_support_assistant_resolves_global_project_dossiers() -> None:
    definition = get_agent_definition("support_assistant")

    assert definition.version == "2.0.0"
    assert "project_resolution" in definition.instruction
    assert "contract total" in definition.instruction
    assert "ambiguous" in definition.instruction


def test_specialized_agents_share_explainable_output_and_safety_contracts() -> None:
    for agent_type in (
        "service_verification",
        "import_quality",
        "integration_design",
        "topology_investigation",
        "bom_scenario",
    ):
        instruction = get_agent_definition(agent_type).instruction
        assert "what was found" in instruction
        assert "Never output a Markdown table" in instruction
        assert "Never expose chain-of-thought" in instruction

    assert get_agent_definition("service_verification").version == "2.0.0"
    assert "when no source was retrieved" in get_agent_definition("service_verification").instruction
    assert get_agent_definition("import_quality").version == "2.0.0"
    assert get_agent_definition("integration_design").version == "2.0.0"
    assert get_agent_definition("topology_investigation").version == "2.0.0"
    assert get_agent_definition("bom_scenario").version == "2.0.0"
