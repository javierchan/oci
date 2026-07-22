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

    assert definition.version == "5.1.0"
    assert "primary author" in definition.instruction
    assert "verified_facts" in definition.instruction
    assert "next_actions" in definition.instruction
    assert "Markdown tables" in definition.instruction
    assert "commercial_service_context" in definition.instruction
    assert "project_resolution" in definition.instruction
    assert "contract total" in definition.instruction
    assert "ambiguous" in definition.instruction
    assert "capability_assessment" in definition.instruction


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

    source_governance = get_agent_definition("service_verification")
    assert source_governance.version == "4.2.0"
    assert source_governance.tools == ("inspect_official_source_governance",)
    assert source_governance.mutates_data is False
    assert "atomic_source_set" in source_governance.instruction
    assert "freshness" in source_governance.instruction
    assert "documentary_drift" in source_governance.instruction
    assert "commercial_fixtures" in source_governance.instruction
    assert "commercial_exceptions" in source_governance.instruction
    assert "commercial_release_scope" in source_governance.instruction
    assert "candidate_revalidation" in source_governance.instruction
    assert "catalog_count" in source_governance.instruction
    assert "quote_ready_count" in source_governance.instruction
    assert "blocked_count" in source_governance.instruction
    assert "pending_count" in source_governance.instruction
    assert "explicit Admin finalization workflow" in source_governance.instruction
    assert "never finalize a catalog review" in source_governance.instruction
    assert "approve a candidate or exception" in source_governance.instruction
    assert "promote a commercial release" in source_governance.instruction
    assert "mutate a BOM" in source_governance.instruction
    assert get_agent_definition("import_quality").version == "3.0.0"
    assert get_agent_definition("integration_design").version == "2.0.0"
    assert get_agent_definition("topology_investigation").version == "2.0.0"
    assert get_agent_definition("bom_scenario").version == "2.2.0"
