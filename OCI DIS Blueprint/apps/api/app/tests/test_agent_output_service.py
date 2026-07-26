"""Presentation and grounding contracts shared by every governed agent."""

import json

from app.agents.registry import get_agent_definition
from app.services.agent_decision_service import build_decision_workspace
from app.services.agent_output_service import govern_agent_output, normalize_agent_summary
from app.services.external_capture_review_service import (
    parse_agent_correction,
    partition_source_record,
)


def test_external_capture_partitions_only_aliases_with_current_app_targets() -> None:
    supported, excluded = partition_source_record(
        {
            "Interfaz": "Synthetic interface",
            "Tecnología de Destino #1": "Synthetic technology",
            "Tipo Trigger OIC": "Synthetic trigger",
            "Response Size (KB)": 8,
            "Tecnología de Destino #2": "Synthetic secondary technology",
            "Comentarios": "Synthetic note",
            "Identificada en:": "Synthetic workshop",
            "Slide": 3,
        }
    )

    assert supported == {
        "Interfaz": "Synthetic interface",
        "Tecnología de Destino #1": "Synthetic technology",
    }
    assert {item["source_header"] for item in excluded} == {
        "Tipo Trigger OIC",
        "Response Size (KB)",
        "Tecnología de Destino #2",
        "Comentarios",
        "Identificada en:",
        "Slide",
    }
    assert {item["classification"] for item in excluded} == {"unsupported"}


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


def test_import_correction_workspace_explains_external_capture_review_counts() -> None:
    workspace, proposals = build_decision_workspace(
        get_agent_definition("import_quality"),
        {
            "state": "external_capture_review",
            "session_id": "capture-session-1",
            "source_evidence_id": "sha256:abc123",
            "summary": {
                "total": 241,
                "schema_ready": 196,
                "missing_required": 45,
                "pattern_changes": 178,
                "needs_review": 241,
            },
            "top_required_gaps": [
                {"field": "destination_system", "rows": 26},
                {"field": "source_system", "rows": 19},
            ],
            "recommended_next_action": (
                "Resolve required-field gaps and review every pattern assessment "
                "before approving any row."
            ),
        },
        project_id="project-1",
        integration_id=None,
    )

    assert workspace.current_state == (
        "241 of 241 proposal(s) require an explicit decision. "
        "45 are blocked by missing required evidence; "
        "196 are schema-complete but still require pattern review."
    )
    assert workspace.alternatives[0].status == "blocked"
    assert workspace.alternatives[0].missing_inputs == [
        "destination_system: 26 row(s)",
        "source_system: 19 row(s)",
    ]
    assert workspace.outcome_metrics == [
        {
            "key": "proposals",
            "label": "Proposals requiring review",
            "value": 241,
        },
        {
            "key": "schema_ready",
            "label": "Schema-complete proposals",
            "value": 196,
        },
        {
            "key": "missing_required",
            "label": "Rows blocked by missing evidence",
            "value": 45,
        },
        {
            "key": "pattern_changes",
            "label": "Pattern changes to review",
            "value": 178,
        },
    ]
    assert workspace.alternatives[0].action_href == (
        "/projects/project-1/capture-review?session=capture-session-1"
    )
    assert proposals == []


def test_import_correction_workspace_focuses_one_row_without_proposing_approval() -> None:
    workspace, proposals = build_decision_workspace(
        get_agent_definition("import_quality"),
        {
            "state": "external_capture_review",
            "review_scope": "single_row",
            "session_id": "capture-session-1",
            "source_evidence_id": "sha256:abc123",
            "focused_row": {
                "draft_id": "draft-25",
                "source_row_number": 25,
                "interface_name": "Nueva Integración para formato CSV",
                "review_summary": (
                    "Approval is blocked: Destination system is missing. "
                    "2 additional review decision(s) remain."
                ),
                "review_triggers": [
                    {
                        "code": "REQUIRED_FIELD:destination_system",
                        "kind": "required_gap",
                        "title": "Destination system is missing",
                        "evidence": (
                            "The proposed App record has no supported value for "
                            "Destination system."
                        ),
                        "required_decision": (
                            "Provide verified destination system evidence or reject "
                            "this proposal."
                        ),
                        "blocks_approval": True,
                    },
                    {
                        "code": "NORMALIZATION_UNRESOLVED:frequency",
                        "kind": "normalization_gap",
                        "title": "Frequency could not be normalized",
                        "evidence": (
                            "The source value 'TBD' has no governed normalized value."
                        ),
                        "required_decision": (
                            "Confirm the intended frequency using the active App dictionary."
                        ),
                        "blocks_approval": False,
                    },
                ],
            },
        },
        project_id="project-1",
        integration_id=None,
    )

    assert workspace.goal == (
        "Explain why this integration line needs review and identify the minimum "
        "human decision."
    )
    assert workspace.alternatives[0].status == "blocked"
    assert workspace.alternatives[0].missing_inputs == [
        "Provide verified destination system evidence or reject this proposal."
    ]
    assert workspace.alternatives[0].action_href == (
        "/projects/project-1/capture-review"
        "?session=capture-session-1&draft=draft-25"
    )
    assert proposals == []


def test_import_correction_agent_maps_only_grounded_supported_values() -> None:
    evidence: dict[str, object] = {
        "focused_row": {
            "supported_source_evidence": {
                "Sistema de destino": "DemandTec",
                "Patrón": "Patrón 2 - Asíncrono / Event-Driven",
            },
            "data_received": {
                "proposed_app_record": {
                    "destination_system": "",
                    "selected_pattern": "#02",
                }
            },
            "data_required": {
                "governed_patterns": [
                    {
                        "pattern_id": "#02",
                        "name": "Event-Driven / Pub-Sub",
                    }
                ]
            },
            "ignored_source_fields": [
                {
                    "source_header": "Costo Total $ USD Diario",
                    "classification": "commercial_formula",
                }
            ],
        }
    }
    analysis = parse_agent_correction(
        json.dumps(
            {
                "explanation": (
                    "Destination is present in supported evidence and can be mapped; "
                    "the workbook formula is not an App input."
                ),
                "deviations": [
                    {
                        "source_field": "Sistema de destino",
                        "target_field": "destination_system",
                        "issue": "The supported destination was not mapped.",
                        "evidence": "Sistema de destino = DemandTec.",
                        "proposed_action": "Map DemandTec to destination_system.",
                        "confidence": "high",
                    },
                    {
                        "source_field": "Costo Total $ USD Diario",
                        "target_field": None,
                        "issue": "Formula has no supported operational target.",
                        "evidence": "The source field was classified as commercial_formula.",
                        "proposed_action": "Keep it excluded.",
                        "confidence": "high",
                    },
                ],
                "proposed_patch": {
                    "destination_system": "DemandTec",
                    "selected_pattern": "#02",
                    "description": "=Table357[[#This Row],[Costo]]*1",
                    "unsupported_cost": 42,
                },
                "excluded_fields": ["Costo Total $ USD Diario"],
                "required_decisions": [
                    "Confirm the pattern using the observed transport evidence."
                ],
            }
        ),
        evidence,
    )

    assert analysis is not None
    assert analysis["proposed_patch"] == {
        "destination_system": "DemandTec",
    }
    assert analysis["no_op_patch_fields"] == ["selected_pattern"]
    assert analysis["excluded_fields"] == ["Costo Total $ USD Diario"]
    assert analysis["rejected_patch_fields"] == [
        "description",
        "unsupported_cost",
    ]
    required_decisions = analysis["required_decisions"]
    assert isinstance(required_decisions, list)
    assert any(
        "contained a formula" in decision
        for decision in required_decisions
    )
    assert any(
        "no supported App target" in decision
        for decision in required_decisions
    )


def test_import_correction_agent_accepts_json_wrapped_in_provider_prose() -> None:
    evidence: dict[str, object] = {
        "focused_row": {
            "supported_source_evidence": {"Target system": "Synthetic Target"},
            "data_received": {
                "proposed_app_record": {"destination_system": ""}
            },
            "ignored_source_fields": [],
        }
    }
    analysis = parse_agent_correction(
        (
            "Governed result follows.\n"
            "```json\n"
            + json.dumps(
                {
                    "explanation": "The supported target can be mapped.",
                    "deviations": [],
                    "proposed_patch": {
                        "destination_system": "Synthetic Target"
                    },
                    "excluded_fields": [],
                    "required_decisions": [],
                }
            )
            + "\n```\nNo operational action was executed."
        ),
        evidence,
    )

    assert analysis is not None
    assert analysis["proposed_patch"] == {
        "destination_system": "Synthetic Target"
    }


def test_import_correction_workspace_proposes_correction_not_row_approval() -> None:
    workspace, proposals = build_decision_workspace(
        get_agent_definition("import_quality"),
        {
            "state": "external_capture_review",
            "review_scope": "single_row",
            "session_id": "capture-session-1",
            "source_evidence_id": "sha256:abc123",
            "focused_row": {
                "draft_id": "draft-25",
                "source_row_number": 25,
                "interface_name": "Nueva Integración para formato CSV",
                "analysis_evidence_hash": "evidence-hash-25",
                "review_summary": "Approval is blocked: Destination system is missing.",
                "review_triggers": [
                    {
                        "code": "REQUIRED_FIELD:destination_system",
                        "kind": "required_gap",
                        "title": "Destination system is missing",
                        "evidence": "The App proposal has no destination.",
                        "required_decision": "Confirm the observed destination.",
                        "blocks_approval": True,
                    }
                ],
            },
            "agent_row_analysis": {
                "deviations": [
                    {
                        "issue": "Destination was not mapped.",
                        "proposed_action": "Map DemandTec.",
                    }
                ],
                "proposed_patch": {"destination_system": "DemandTec"},
                "excluded_fields": ["Costo Total $ USD Diario"],
                "required_decisions": ["Confirm DemandTec before execution."],
            },
        },
        project_id="project-1",
        integration_id=None,
    )

    assert workspace.alternatives[0].action_type == (
        "apply_external_capture_correction_draft"
    )
    assert workspace.alternatives[0].action_label == "Authorize correction draft"
    assert len(proposals) == 1
    assert proposals[0].action_type == "apply_external_capture_correction_draft"
    assert proposals[0].payload["proposed_patch"] == {
        "destination_system": "DemandTec"
    }
    assert proposals[0].payload["analysis_evidence_hash"] == "evidence-hash-25"


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


def test_support_assistant_can_reject_output_without_creating_visible_fallback() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        "The user asks about a pattern. We need to provide an answer.",
        {
            "fallback_answer": "Request and Reply waits for the target service response.",
            "recommended_next_action": "Open the Pattern Library.",
        },
        allow_fallback=False,
    )

    assert output.quality.grounded is False
    assert output.quality.fallback_used is False
    assert output.quality.fallback_reason == "empty_provider_summary"
    assert output.summary == ""


def test_support_assistant_compares_numeric_values_not_number_formatting() -> None:
    evidence: dict[str, object] = {
        "commercial_service_context": {
            "service_name": "OCI Functions",
            "pricing_model": "First 400K GB-memory-seconds/month free.",
            "sku_options": [
                {
                    "part_number": "B90617",
                    "quantity_unit": "10K GB-s",
                    "price": {
                        "metric_name": "10,000 GB Memory-Seconds",
                        "currency": "USD",
                        "value": 0.1417,
                    },
                }
            ],
        },
        "fallback_answer": "Open the governed Service Product.",
    }
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        (
            "OCI Functions is priced at USD 0.1417 per 10 000 GB memory-seconds; "
            "the governed policy records 400 K free GB-memory-seconds."
        ),
        evidence,
        allow_fallback=False,
    )
    assert output.quality.grounded is True

    spanish_grouping = govern_agent_output(
        get_agent_definition("support_assistant"),
        (
            "OCI Functions cuesta USD 0.1417 por 10.000 GB-seconds; "
            "incluye 400.000 GB-memory-seconds."
        ),
        evidence,
        allow_fallback=False,
    )
    assert spanish_grouping.quality.grounded is True

    invented = govern_agent_output(
        get_agent_definition("support_assistant"),
        "OCI Functions is priced at USD 99.",
        evidence,
        allow_fallback=False,
    )
    assert invented.quality.grounded is False
    assert invented.quality.fallback_reason == "unsupported_numeric_claim"

    invented_duration = govern_agent_output(
        get_agent_definition("support_assistant"),
        "Request and Reply should complete within 30 seconds.",
        {"fallback_answer": "Use the governed pattern guidance."},
        allow_fallback=False,
    )
    assert invented_duration.quality.grounded is False
    assert invented_duration.quality.fallback_reason == "unsupported_numeric_claim"


def test_support_assistant_rejects_claims_the_model_says_are_outside_evidence() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        (
            "El precio gobernado es USD 0.1417 por 10,000 GB-s. "
            "Free Tier no está en la evidencia, pero incluye 2M de invocaciones."
        ),
        {
            "commercial_service_context": {
                "service_name": "OCI Functions",
                "price": {"currency": "USD", "value": 0.1417},
                "quantity_unit": "10,000 GB-s",
                "reference_numbers": [2_000_000],
            },
            "fallback_answer": "Open the governed Service Product.",
        },
        allow_fallback=False,
    )

    assert output.quality.grounded is False
    assert output.quality.fallback_reason == "self_disclaimed_unsupported_claim"


def test_support_assistant_replaces_spanish_model_next_action_synonyms() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        (
            "Los agentes analizan evidencia gobernada.\n\n"
            "Próximo paso: [Abrir la vista de Agents](/admin/agents)"
        ),
        {
            "response_language": "es",
            "app_knowledge": {
                "documented": True,
                "allowed_routes": ["/admin/agents"],
                "allowed_export_media_types": [],
                "entries": [],
            },
            "next_actions": [
                {"label": "Continuar en esta vista", "href": "/admin/agents"}
            ],
        },
        allow_fallback=False,
    )
    assert output.quality.grounded is True
    assert output.summary.count("paso:") == 1
    assert "Próximo paso" not in output.summary


def test_support_assistant_removes_external_workaround_for_absent_capability() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        (
            "OCI DIS Architect does not document cost threshold email alerts.\n\n"
            "Export the BOM, then set up your own monitoring outside the tool.\n\n"
            "[/projects]"
        ),
        {
            "response_language": "en",
            "app_knowledge": {
                "documented": True,
                "capability_assessment": {"status": "not_documented"},
                "allowed_routes": ["/projects"],
                "allowed_export_media_types": [],
                "entries": [],
            },
            "next_actions": [
                {"label": "Open BOM & Cost", "href": "/projects"}
            ],
        },
        allow_fallback=False,
    )
    assert output.quality.grounded is True
    assert "own monitoring" not in output.summary
    assert "outside the tool" not in output.summary
    assert "[/projects]" not in output.summary
    assert "does not document" in output.summary


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


def test_support_assistant_rejects_formatting_instructions_before_useful_content() -> None:
    output = govern_agent_output(
        get_agent_definition("support_assistant"),
        (
            "The answer should lead them to projects and capture workflow. "
            "Use citations: route /projects, capture etc. No tables. "
            "Use plain language, bullet lists up to 5. Mention next actions: navigate to Projects. "
            "Provide guidance. To start an integration assessment, create or select a project."
        ),
        {
            "fallback_answer": (
                "Start in Projects, create or select an assessment, then open Capture "
                "to define the first governed integration."
            ),
        },
    )

    assert output.quality.fallback_reason == "internal_reasoning"
    assert output.summary.startswith("Start in Projects")
    assert "The answer should" not in output.summary
    assert "No tables" not in output.summary


def test_agent_summary_joins_orphan_list_markers_to_their_text() -> None:
    normalized = normalize_agent_summary(
        "Start here:\n\n1.\nCreate or select a project\n\n2)\nOpen Capture\n\n-\nReview QA"
    )

    assert normalized == (
        "Start here:\n\n1. Create or select a project\n\n2) Open Capture\n- Review QA"
    )


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
