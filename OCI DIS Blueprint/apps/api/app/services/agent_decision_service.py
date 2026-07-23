"""Deterministic decision workspaces, proposals, execution, and post-validation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Literal, cast

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.registry import AgentDefinition
from app.models import AgentApproval, AgentArtifact, AgentRun
from app.schemas.agent import AgentDecisionAlternative, AgentDecisionImpact, AgentDecisionWorkspace
from app.schemas.ai_review import AiReviewDraftSimulationRequest
from app.schemas.pricing import DeploymentScenarioCreateRequest
from app.schemas.service_products import ServiceVerificationFindingReviewRequest
from app.services.serializers import sanitize_for_json


@dataclass(frozen=True)
class AgentProposal:
    """One approval record derived from deterministic evidence."""

    action_type: str
    payload: dict[str, object]


def _dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _dicts(value: object) -> list[dict[str, object]]:
    return [cast(dict[str, object], item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: object, *, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:limit]


def _text(value: object, default: str = "") -> str:
    return str(value).strip() if value is not None and str(value).strip() else default


def _number(value: object) -> float:
    """Return a bounded JSON number for deterministic presentation."""

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


DecisionStatus = Literal["ready", "review", "blocked"]
DecisionConfidence = Literal["high", "medium", "low"]


def _confidence(value: object) -> DecisionConfidence:
    normalized = _text(value).casefold()
    if normalized == "high":
        return "high"
    if normalized == "low":
        return "low"
    return "medium"


def _finding_summaries(value: object, *, limit: int = 4) -> list[str]:
    """Turn structured checks into concise, user-facing evidence statements."""

    summaries: list[str] = []
    for item in _dicts(value):
        label = _text(item.get("label")) or _text(item.get("title")) or _text(item.get("check"))
        detail = _text(item.get("detail")) or _text(item.get("summary")) or _text(item.get("message"))
        summary = ": ".join(part for part in (label, detail) if part)
        if summary:
            summaries.append(summary)
        if len(summaries) >= limit:
            break
    return summaries


def _impact(
    *,
    technical: list[str] | None = None,
    commercial: list[str] | None = None,
    governance: list[str] | None = None,
    operational: list[str] | None = None,
) -> AgentDecisionImpact:
    return AgentDecisionImpact(
        technical=technical or [],
        commercial=commercial or [],
        governance=governance or [],
        operational=operational or [],
    )


def _review_workspace(
    definition: AgentDefinition,
    evidence: dict[str, object],
    *,
    project_id: str | None,
    integration_id: str | None,
) -> tuple[AgentDecisionWorkspace, list[AgentProposal]]:
    recommendation = _dict(evidence.get("recommendation_workspace"))
    action_workspace = _dict(evidence.get("action_workspace"))
    decision = _dict(evidence.get("decision_brief"))
    recommended_id = _text(recommendation.get("recommended_candidate_id")) or None
    alternatives: list[AgentDecisionAlternative] = []
    proposals: list[AgentProposal] = []

    for candidate in _dicts(recommendation.get("candidates"))[:3]:
        candidate_id = _text(candidate.get("id"), "design-candidate")
        applicable = candidate.get("applicable") is not False
        cost = _dict(candidate.get("cost_impact"))
        status: DecisionStatus = "ready" if applicable else "blocked"
        alternative = AgentDecisionAlternative(
            id=candidate_id,
            title=_text(candidate.get("title"), "Governed design alternative"),
            summary=_text(candidate.get("summary"), "Compare this governed route with the saved design."),
            status=status,
            recommended=candidate_id == recommended_id,
            changes=_strings(candidate.get("implementation_steps"), limit=5)
            or _strings(_dict(candidate.get("change_set")).get("added_tools"), limit=5),
            implementation_steps=_strings(candidate.get("implementation_steps"), limit=6),
            validation_steps=_strings(candidate.get("validation_plan"), limit=6),
            missing_inputs=_strings(candidate.get("prerequisites"), limit=6),
            impact=_impact(
                technical=_finding_summaries(candidate.get("checks"), limit=4),
                commercial=[_text(cost.get("detail"))] if _text(cost.get("detail")) else [],
                governance=["Requires explicit architect approval before the saved integration changes."],
                operational=_strings(candidate.get("tradeoffs"), limit=4),
            ),
            evidence_ids=_strings(candidate.get("evidence_ids"), limit=12),
            confidence=_confidence(candidate.get("confidence")),
            action_type="simulate_integration_design_candidate" if applicable and integration_id else None,
            action_label="Approve draft simulation" if applicable and integration_id else None,
            action_href=f"/projects/{project_id}/catalog/{integration_id}" if project_id and integration_id else None,
        )
        alternatives.append(alternative)
        if applicable and integration_id and candidate_id == recommended_id:
            proposals.append(
                AgentProposal(
                    action_type="simulate_integration_design_candidate",
                    payload={
                        "alternative_id": candidate_id,
                        "project_id": project_id,
                        "integration_id": integration_id,
                        "candidate": deepcopy(candidate),
                        "before": {
                            "pattern_id": recommendation.get("current_pattern_id"),
                            "core_tools": recommendation.get("current_core_tools", []),
                            "overlays": recommendation.get("current_overlays", []),
                            "canvas_state": recommendation.get("current_canvas_state"),
                        },
                    },
                )
            )

    for candidate in _dicts(action_workspace.get("candidates"))[:3]:
        candidate_id = _text(candidate.get("id"), "remediation-action")
        status_value = _text(candidate.get("status"), "review")
        action_status: DecisionStatus = (
            "ready" if status_value == "ready" else "blocked" if status_value == "blocked" else "review"
        )
        alternative = AgentDecisionAlternative(
            id=candidate_id,
            title=_text(candidate.get("title"), "Governed remediation action"),
            summary=_text(candidate.get("summary"), "Review the evidence-linked remediation plan."),
            status=action_status,
            recommended=not alternatives,
            changes=_strings(candidate.get("what_to_change"), limit=6),
            implementation_steps=_strings(candidate.get("implementation_steps"), limit=6),
            validation_steps=_strings(candidate.get("validation_plan"), limit=6),
            impact=_impact(
                technical=_strings(candidate.get("expected_impact"), limit=5),
                governance=["Creates an auditable remediation draft; governed records remain unchanged."],
            ),
            evidence_ids=_strings(candidate.get("evidence_ids"), limit=12),
            confidence=_confidence(candidate.get("confidence")),
            action_type="create_agent_action_draft" if action_status != "blocked" else None,
            action_label="Approve remediation draft" if action_status != "blocked" else None,
            action_href=_text(candidate.get("action_href")) or None,
        )
        alternatives.append(alternative)
        if action_status != "blocked" and len(proposals) < 3:
            proposals.append(
                AgentProposal(
                    action_type="create_agent_action_draft",
                    payload={
                        "alternative_id": candidate_id,
                        "project_id": project_id,
                        "integration_id": integration_id,
                        "candidate": deepcopy(candidate),
                    },
                )
            )

    current_state = _text(decision.get("primary_risk")) or _text(decision.get("headline"))
    goal = (
        "Choose and validate the safest governed integration design."
        if definition.type == "integration_design"
        else "Reduce topology blast radius with an evidence-linked mitigation plan."
        if definition.type == "topology_investigation"
        else "Resolve the material blockers required for architecture sign-off."
    )
    workspace = AgentDecisionWorkspace(
        workspace_type="architecture",
        goal=goal,
        current_state=current_state or "Governed architecture evidence is ready for decision.",
        recommendation_basis=_text(recommendation.get("recommendation_basis"))
        or _text(action_workspace.get("recommendation_basis"))
        or "Alternatives are derived from deterministic catalog, canvas, topology, QA, and service-rule evidence.",
        recommended_alternative_id=recommended_id or (alternatives[0].id if alternatives else None),
        alternatives=alternatives,
        outcome_metrics=[
            {"key": "readiness", "label": "Current readiness", "value": evidence.get("readiness_score")},
            {"key": "findings", "label": "Open findings", "value": len(_dicts(evidence.get("findings")))},
        ],
        post_validation=[
            "Recalculate the project after an approved governed change.",
            "Run the same review scope and compare readiness, findings, QA, and design warnings.",
            "Preserve the before/after evidence and audit correlation ID.",
        ],
    )
    return workspace, proposals


def _bom_workspace(
    evidence: dict[str, object], project_id: str | None
) -> tuple[AgentDecisionWorkspace, list[AgentProposal]]:
    current_bom = _dict(evidence.get("current_bom"))
    if current_bom.get("ready_for_use") is True:
        services = _strings(evidence.get("detected_services"), limit=24)
        environments = _strings(current_bom.get("environment_names"), limit=12)
        snapshot_id = _text(current_bom.get("snapshot_id"))
        scenario_id = _text(current_bom.get("scenario_id"))
        currency = _text(current_bom.get("currency"), "USD")
        contract_total = _number(current_bom.get("contract_total"))
        baseline = AgentDecisionAlternative(
            id="keep-published-baseline",
            title="Keep the published baseline",
            summary=(
                f"The current approved scenario has 100% coverage across {current_bom.get('line_item_count', 0)} "
                f"line(s) and {len(environments)} environment(s); contract total is {currency} {contract_total:,.2f}."
            ),
            status="ready",
            recommended=True,
            changes=["No replacement scenario is required while this BOM remains aligned with the latest technical snapshot."],
            implementation_steps=["Use the published baseline for the current planning decision and preserve its immutable provenance."],
            validation_steps=["Regenerate only after architecture, environment timing, SKU selection, or approved price evidence changes."],
            missing_inputs=[],
            impact=_impact(
                commercial=["Preserves the approved contract estimate without introducing an unsupported alternative."],
                governance=["Keeps the published BOM and its approved scenario as the authoritative commercial planning evidence."],
            ),
            evidence_ids=[item for item in (snapshot_id, scenario_id) if item],
            confidence="high",
            action_href=f"/projects/{project_id}/bom" if project_id else None,
        )
        phased = AgentDecisionAlternative(
            id="review-phased-rollout",
            title="Review a phased rollout alternative",
            summary="Create a separate comparison only when delivery dates or product activation differ from the published baseline.",
            status="review",
            recommended=False,
            changes=["Model changed activation months or real-unit quantities in a new scenario; do not overwrite the published BOM."],
            implementation_steps=["Clone the approved scenario, change only evidenced rollout inputs, then generate a separate BOM."],
            validation_steps=["Compare monthly ramp, peak, steady state, and contract total with the published baseline."],
            missing_inputs=[],
            impact=_impact(commercial=["Quantifies timing effects without presenting them as negotiated savings."]),
            evidence_ids=[item for item in (snapshot_id, scenario_id) if item],
            confidence="high",
            action_href=f"/projects/{project_id}/bom" if project_id else None,
        )
        resilient = AgentDecisionAlternative(
            id="review-availability-ready",
            title="Review an availability alternative",
            summary="Create a separate comparison when HA, DR, edition, or license posture changes by environment.",
            status="review",
            recommended=False,
            changes=["Capture the changed resilience requirement in a new governed scenario."],
            implementation_steps=["Clone the approved scenario and change only the affected environment and commercial variants."],
            validation_steps=["Require approved SKU mappings and 100% coverage before comparing or publishing."],
            missing_inputs=[],
            impact=_impact(technical=["Separates resilience capacity from logical demand."], commercial=["Shows the deterministic cost delta of the availability decision."]),
            evidence_ids=[item for item in (snapshot_id, scenario_id) if item],
            confidence="high",
            action_href=f"/projects/{project_id}/bom" if project_id else None,
        )
        return (
            AgentDecisionWorkspace(
                workspace_type="commercial",
                goal="Use the current published estimate or compare an explicitly changed deployment alternative.",
                current_state=(
                    f"Published BOM is current with {current_bom.get('coverage_pct', 0)}% coverage, "
                    f"{current_bom.get('line_item_count', 0)} line(s), and no unresolved lines."
                ),
                recommendation_basis="The recommendation uses the current technical snapshot, approved deployment scenario, immutable BOM lines, and publication state.",
                recommended_alternative_id=baseline.id,
                alternatives=[baseline, phased, resilient],
                outcome_metrics=[
                    {"key": "coverage", "label": "Commercial coverage", "value": current_bom.get("coverage_pct")},
                    {"key": "lines", "label": "BOM lines", "value": current_bom.get("line_item_count")},
                    {"key": "questions", "label": "Client inputs remaining", "value": 0},
                ],
                post_validation=[
                    "Confirm the published BOM still references the latest technical snapshot.",
                    "Regenerate after any approved architecture, scenario, SKU, or price-evidence change.",
                    "Preserve comparisons as separate immutable snapshots.",
                ],
            ),
            [],
        )
    draft = _dict(evidence.get("draft"))
    services = _strings(evidence.get("detected_services"), limit=24)
    questions = _strings(evidence.get("required_questions"), limit=12)
    warnings = _strings(evidence.get("warnings"), limit=8)
    baseline = AgentDecisionAlternative(
        id="governed-baseline",
        title="Governed baseline",
        summary=f"Create a reviewable deployment scenario for {len(services)} detected product(s) in real billing units.",
        status="ready" if draft else "blocked",
        recommended=True,
        changes=["Persist the detected products, SKU metrics, environments, quantities, and activation periods as a draft scenario."],
        implementation_steps=["Create the scenario draft.", "Review every environment and commercial variant.", "Generate a BOM only after required client inputs are confirmed."],
        validation_steps=["Require complete SKU, quantity, period, price, and source provenance before publication."],
        missing_inputs=questions,
        impact=_impact(
            commercial=warnings or ["No price or savings claim is made until the deterministic pricing engine runs."],
            governance=["The created scenario remains a draft and does not publish a quote."],
        ),
        evidence_ids=services,
        confidence=_confidence(evidence.get("confidence")),
        action_type="create_deployment_scenario_draft" if draft else None,
        action_label="Approve and create scenario" if draft else None,
        action_href=f"/projects/{project_id}/bom" if project_id else None,
    )
    phased = AgentDecisionAlternative(
        id="phased-rollout",
        title="Phased rollout",
        summary="Model DEV, QA, production, and DR activation independently by product and billing metric.",
        status="blocked" if questions else "review",
        recommended=False,
        changes=["Capture product-specific start months, monthly quantities, editions, license variants, HA, and DR posture."],
        implementation_steps=["Resolve the listed client inputs.", "Use the monthly matrix for non-linear or packaged consumption."],
        validation_steps=["Compare first-month, steady-state, peak, and cumulative contract cost against the baseline."],
        missing_inputs=questions,
        impact=_impact(commercial=["Exposes rollout timing rather than applying a universal percentage ramp."], operational=["Makes environment overlap explicit."]),
        evidence_ids=services,
        confidence="medium" if services else "low",
        action_href=f"/projects/{project_id}/bom" if project_id else None,
    )
    resilient = AgentDecisionAlternative(
        id="availability-ready",
        title="Availability-ready scenario",
        summary="Evaluate HA and DR capacity separately from the minimum commercial baseline.",
        status="blocked" if questions else "review",
        recommended=False,
        changes=["Confirm HA multipliers, DR role, failover assumptions, and environment-specific editions before sizing."],
        implementation_steps=["Capture resilience requirements per environment.", "Regenerate and compare the governed BOM."],
        validation_steps=["Verify that every added unit maps to an approved SKU and explicit resilience requirement."],
        missing_inputs=questions,
        impact=_impact(technical=["Separates resilience capacity from logical integration demand."], commercial=["Shows the deterministic cost delta of HA and DR choices."]),
        evidence_ids=services,
        confidence="medium" if services else "low",
        action_href=f"/projects/{project_id}/bom" if project_id else None,
    )
    proposals = (
        [AgentProposal(action_type="create_deployment_scenario_draft", payload={"alternative_id": baseline.id, "project_id": project_id, "scenario": draft})]
        if draft and project_id
        else []
    )
    return (
        AgentDecisionWorkspace(
            workspace_type="commercial",
            goal="Choose a deployable, explainable OCI consumption scenario before generating a quote.",
            current_state=f"{len(services)} product(s) detected; {len(questions)} client decision(s) remain.",
            recommendation_basis="Alternatives use the technical snapshot, approved commercial mappings, real billing units, and explicit environment timing.",
            recommended_alternative_id=baseline.id,
            alternatives=[baseline, phased, resilient],
            outcome_metrics=[
                {"key": "products", "label": "Detected products", "value": len(services)},
                {"key": "questions", "label": "Client inputs remaining", "value": len(questions)},
            ],
            post_validation=[
                "Generate a new BOM from the approved scenario.",
                "Require 100% quantity and price coverage before publication.",
                "Compare monthly ramp, steady state, peak, and contract total against the baseline.",
            ],
        ),
        proposals,
    )


def _quality_workspace(
    definition: AgentDefinition, evidence: dict[str, object], project_id: str | None
) -> tuple[AgentDecisionWorkspace, list[AgentProposal]]:
    if definition.type == "import_quality" and evidence.get("state") == "external_capture_review":
        summary = _dict(evidence.get("summary"))
        total = int(_number(summary.get("total")))
        schema_ready = int(_number(summary.get("schema_ready")))
        missing_required = int(_number(summary.get("missing_required")))
        pattern_changes = int(_number(summary.get("pattern_changes")))
        needs_review = int(_number(summary.get("needs_review")))
        required_gaps = _dicts(evidence.get("top_required_gaps"))
        gap_labels = [
            f"{_text(item.get('field'), 'required field')}: {int(_number(item.get('rows')))} row(s)"
            for item in required_gaps[:6]
        ]
        recommended_next_action = _text(
            evidence.get("recommended_next_action"),
            "Resolve required evidence and review each recommended pattern before approval.",
        )
        session_id = _text(evidence.get("session_id"))
        evidence_ids = [
            item
            for item in (session_id, _text(evidence.get("source_evidence_id")))
            if item
        ]
        candidate = AgentDecisionAlternative(
            id="external-capture-correction-draft",
            title="Review the governed customer-data proposals",
            summary=(
                f"{schema_ready} of {total} row(s) are schema-complete; "
                f"{missing_required} remain blocked by missing required evidence, and "
                f"{pattern_changes} pattern recommendation(s) differ from the supplied source."
            ),
            status="blocked" if missing_required else "review",
            recommended=True,
            changes=[
                recommended_next_action,
                "Keep every source row immutable while editing only its governed proposal.",
            ],
            implementation_steps=[
                "Resolve the required evidence gaps without inventing customer values.",
                "Compare the supplied and recommended pattern for every row.",
                "Record an explicit architect decision before promoting any proposal.",
            ],
            validation_steps=[
                "Revalidate each edited proposal against the governed dictionaries and active patterns.",
                "Confirm TBQ remains Y for this exercise and Tamaño KB remains the payload evidence source.",
                "Promote only explicitly approved proposals, then rerun QA, volumetry, topology, and BOM checks.",
            ],
            missing_inputs=gap_labels,
            impact=_impact(
                technical=[
                    "Preserves incomplete source evidence so downstream confidence remains truthful."
                ],
                commercial=[
                    "Keeps all staged rows TBQ=Y without creating BOM demand before catalog promotion."
                ],
                governance=[
                    "The customer workbook remains local; the App stores only row-level evidence and proposals."
                ],
                operational=[
                    "Separates normalization, human review, and canonical catalog promotion."
                ],
            ),
            evidence_ids=evidence_ids,
            confidence="high",
            action_type="create_agent_action_draft",
            action_label="Approve correction plan",
            action_href=(
                f"/projects/{project_id}/capture-review?session={session_id}"
                if project_id and session_id
                else f"/projects/{project_id}/capture-review"
                if project_id
                else None
            ),
        )
        proposal = AgentProposal(
            action_type="create_agent_action_draft",
            payload={
                "alternative_id": candidate.id,
                "project_id": project_id,
                "external_capture_session_id": session_id or None,
                "candidate": candidate.model_dump(mode="json"),
            },
        )
        return (
            AgentDecisionWorkspace(
                workspace_type="data_quality",
                goal=(
                    "Turn external customer evidence into reviewed, canonical integration "
                    "records without silently filling missing data."
                ),
                current_state=(
                    f"{needs_review} of {total} proposal(s) require an explicit decision. "
                    f"{missing_required} are blocked by missing required evidence; "
                    f"{schema_ready} are schema-complete but still require pattern review."
                ),
                recommendation_basis=(
                    "The plan uses immutable row-level source evidence, governed dictionary "
                    "normalization, deterministic QA, and line-by-line pattern assessments."
                ),
                recommended_alternative_id=candidate.id,
                alternatives=[candidate],
                outcome_metrics=[
                    {
                        "key": "proposals",
                        "label": "Proposals requiring review",
                        "value": needs_review,
                    },
                    {
                        "key": "schema_ready",
                        "label": "Schema-complete proposals",
                        "value": schema_ready,
                    },
                    {
                        "key": "missing_required",
                        "label": "Rows blocked by missing evidence",
                        "value": missing_required,
                    },
                    {
                        "key": "pattern_changes",
                        "label": "Pattern changes to review",
                        "value": pattern_changes,
                    },
                ],
                post_validation=[
                    "Confirm no source value was invented or overwritten.",
                    "Confirm no proposal moved to the canonical catalog without explicit approval.",
                    "Compare promoted counts with the approved row decisions before recalculation.",
                ],
            ),
            [proposal],
        )

    findings = _dicts(evidence.get("findings"))
    alternatives: list[AgentDecisionAlternative] = []
    proposals: list[AgentProposal] = []
    if definition.type == "service_verification":
        for finding in findings[:3]:
            finding_id = _text(finding.get("id"))
            job_id = _text(finding.get("job_id")) or _text(evidence.get("id"))
            alternative = AgentDecisionAlternative(
                id=finding_id or f"finding-{len(alternatives) + 1}",
                title=_text(finding.get("title"), "Review official-source change"),
                summary=_text(finding.get("summary"), "A governed source finding requires an Admin decision."),
                status="review",
                recommended=not alternatives,
                changes=[_text(finding.get("recommended_action"), "Review the evidence and decide whether to accept or dismiss it.")],
                implementation_steps=["Inspect the source excerpt and old/new governed values.", "Accept only when the official evidence supports the proposed update."],
                validation_steps=["Run affected quote fixtures and service-rule regression tests before publication."],
                impact=_impact(governance=["An accepted finding can update governed service evidence or limits through the existing review service."]),
                evidence_ids=[item for item in (finding_id, _text(finding.get("source_url"))) if item],
                confidence="medium",
                action_type="review_service_verification_finding" if finding_id and job_id else None,
                action_label="Approve official-source finding" if finding_id and job_id else None,
                action_href="/admin/service-products",
            )
            alternatives.append(alternative)
            if finding_id and job_id:
                proposals.append(AgentProposal(action_type="review_service_verification_finding", payload={"alternative_id": alternative.id, "job_id": job_id, "finding_id": finding_id}))
    else:
        candidate = AgentDecisionAlternative(
            id="import-correction-draft",
            title=_text(findings[0].get("title") if findings else None, "Preview governed import corrections"),
            summary=_text(findings[0].get("summary") if findings else None, "Create a bounded correction plan without changing immutable source rows."),
            status="review" if findings else "ready",
            recommended=True,
            changes=[_text(evidence.get("recommended_next_action"), "Review normalized rows and unresolved mappings.")],
            implementation_steps=["Inspect affected source rows and normalization evidence.", "Correct the offline workbook or governed catalog fields through supported workflows.", "Queue a new import batch."],
            validation_steps=["Compare included/excluded counts and rerun QA, volumetry, and BOM confidence checks."],
            impact=_impact(technical=["Improves downstream QA, sizing, topology, and BOM evidence."], governance=["Original import lineage remains immutable."]),
            evidence_ids=[_text(evidence.get("batch_id"))] if _text(evidence.get("batch_id")) else [],
            confidence="high" if not findings else "medium",
            action_type="create_agent_action_draft",
            action_label="Approve correction draft",
            action_href=f"/projects/{project_id}/import" if project_id else None,
        )
        alternatives.append(candidate)
        proposals.append(AgentProposal(action_type="create_agent_action_draft", payload={"alternative_id": candidate.id, "project_id": project_id, "candidate": candidate.model_dump(mode="json")}))
    return (
        AgentDecisionWorkspace(
            workspace_type="data_quality",
            goal="Turn evidence gaps or official-source changes into reviewed, traceable governance decisions.",
            current_state=(
                f"{evidence.get('sources_checked', 0)} source(s) checked; {evidence.get('changes_detected', 0)} change(s) detected."
                if definition.type == "service_verification"
                else f"{len(findings)} import quality finding(s) require review."
            ),
            recommendation_basis="The plan uses persisted findings, immutable lineage, allowlisted Oracle sources, and existing governed review services.",
            recommended_alternative_id=alternatives[0].id if alternatives else None,
            alternatives=alternatives,
            outcome_metrics=[{"key": "findings", "label": "Reviewable findings", "value": len(findings)}],
            post_validation=["Rerun the same verification or import quality workflow and compare open findings.", "Execute downstream regression or quote fixtures before accepting material rule changes."],
        ),
        proposals[:3],
    )


def build_decision_workspace(
    definition: AgentDefinition,
    evidence: dict[str, object],
    *,
    project_id: str | None,
    integration_id: str | None,
) -> tuple[AgentDecisionWorkspace, list[AgentProposal]]:
    """Create a domain-specific decision workspace from authoritative evidence."""

    if definition.type == "bom_scenario":
        return _bom_workspace(evidence, project_id)
    if definition.type in {"import_quality", "service_verification"}:
        return _quality_workspace(definition, evidence, project_id)
    if definition.type == "support_assistant":
        next_action = _text(evidence.get("recommended_next_action"), "Open the cited workspace and continue with a specialized review.")
        workspace = AgentDecisionWorkspace(
            workspace_type="support",
            goal="Answer the current App question and route material decisions to the correct governed workspace.",
            current_state=_text(evidence.get("direct_answer")) or _text(evidence.get("fallback_answer"), "Bounded App context is ready."),
            recommendation_basis="The assistant uses read-only App evidence and delegates governed decisions to specialized workflows.",
            recommended_alternative_id="continue-in-context",
            alternatives=[AgentDecisionAlternative(
                id="continue-in-context", title="Continue in the governed workspace", summary=next_action,
                status="ready", recommended=True, changes=[], implementation_steps=[next_action],
                validation_steps=["Open the cited record and verify the authoritative value."], impact=_impact(),
                evidence_ids=[], confidence="high" if evidence.get("in_scope") is not False else "low",
            )],
            outcome_metrics=[], post_validation=["Use a specialized agent when the request requires simulation, a draft, or approval."],
        )
        return workspace, []
    return _review_workspace(definition, evidence, project_id=project_id, integration_id=integration_id)


async def persist_proposals(run: AgentRun, proposals: list[AgentProposal], db: AsyncSession) -> list[AgentApproval]:
    """Persist at most three bounded approval proposals for one run."""

    rows: list[AgentApproval] = []
    for proposal in proposals[:3]:
        row = AgentApproval(
            run_id=run.id,
            action_type=proposal.action_type,
            status="pending",
            proposed_payload=cast(dict, sanitize_for_json(proposal.payload)),
        )
        db.add(row)
        rows.append(row)
    await db.flush()
    return rows


async def execute_approved_proposal(
    run: AgentRun,
    approval: AgentApproval,
    *,
    actor_id: str,
    db: AsyncSession,
) -> dict[str, object]:
    """Execute one approved deterministic action and return post-validation evidence."""

    if approval.status != "approved":
        raise HTTPException(status_code=409, detail={"detail": "Only approved proposals can execute", "error_code": "AGENT_PROPOSAL_NOT_APPROVED"})
    if approval.execution_status == "completed":
        return cast(dict[str, object], approval.execution_result or {})
    if approval.execution_status == "running":
        raise HTTPException(status_code=409, detail={"detail": "Proposal execution is already running", "error_code": "AGENT_PROPOSAL_EXECUTION_RUNNING"})

    approval.execution_status = "running"
    await db.flush()
    payload = cast(dict[str, object], approval.proposed_payload)
    result: dict[str, object]
    try:
        if approval.action_type == "simulate_integration_design_candidate":
            from app.services import ai_review_simulation

            project_id = _text(payload.get("project_id"))
            integration_id = _text(payload.get("integration_id"))
            candidate = _dict(payload.get("candidate"))
            if not project_id or not integration_id:
                raise HTTPException(status_code=422, detail="Proposal is missing project or integration context")
            core_tools = _strings(candidate.get("core_tools"), limit=32)
            canvas_state = _text(candidate.get("canvas_state"))
            simulation = await ai_review_simulation.simulate_canvas_draft(
                project_id=project_id,
                integration_id=integration_id,
                body=AiReviewDraftSimulationRequest(
                    core_tools=core_tools,
                    canvas_state=canvas_state,
                ),
                db=db,
            )
            draft_artifact = AgentArtifact(
                run_id=run.id,
                artifact_type="integration_design_draft",
                label=f"Approved integration draft {payload.get('alternative_id')}",
                payload=cast(dict, sanitize_for_json(candidate)),
            )
            db.add(draft_artifact)
            await db.flush()
            result = {
                "outcome": "integration_design_draft_simulated",
                "integration_id": integration_id,
                "alternative_id": payload.get("alternative_id"),
                "artifact_id": draft_artifact.id,
                "persisted": simulation.persisted,
                "technical_deltas": [item.model_dump(mode="json") for item in simulation.metrics],
                "warnings_resolved": sorted(set(simulation.current_warnings) - set(simulation.proposed_warnings)),
                "warnings_introduced": sorted(set(simulation.proposed_warnings) - set(simulation.current_warnings)),
                "commercial_impact": simulation.commercial_impact.model_dump(mode="json"),
                "validation": "completed",
                "action_href": f"/projects/{project_id}/catalog/{integration_id}",
            }
        elif approval.action_type == "create_deployment_scenario_draft":
            from app.services.bom_service import create_scenario

            project_id = _text(payload.get("project_id"))
            scenario = DeploymentScenarioCreateRequest.model_validate(payload.get("scenario"))
            created = await create_scenario(project_id, scenario, actor_id, db)
            result = {
                "outcome": "deployment_scenario_created",
                "scenario_id": created.id,
                "scenario_name": created.name,
                "status": created.status,
                "validation": "draft_created",
                "action_href": f"/projects/{project_id}/bom",
            }
        elif approval.action_type == "review_service_verification_finding":
            from app.services.service_product_service import review_verification_finding

            job_id = _text(payload.get("job_id"))
            finding_id = _text(payload.get("finding_id"))
            reviewed = await review_verification_finding(
                job_id,
                finding_id,
                ServiceVerificationFindingReviewRequest(review_status="accepted", note="Accepted through governed Agent Decision Workspace."),
                actor_id,
                db,
            )
            result = {
                "outcome": "service_verification_finding_accepted",
                "finding_id": reviewed.id,
                "review_status": reviewed.review_status,
                "validation": "accepted_update_applied_and_audited",
            }
        else:
            artifact = AgentArtifact(
                run_id=run.id,
                artifact_type="decision_draft",
                label=f"Approved {approval.action_type.replace('_', ' ')}",
                payload=cast(dict, sanitize_for_json(payload)),
            )
            db.add(artifact)
            await db.flush()
            result = {
                "outcome": "governed_draft_created",
                "artifact_id": artifact.id,
                "validation": "draft_persisted_no_authoritative_data_changed",
                "action_href": _text(_dict(payload.get("candidate")).get("action_href")) or None,
            }
        artifact = AgentArtifact(
            run_id=run.id,
            artifact_type="post_validation",
            label=f"Post-validation for {approval.action_type.replace('_', ' ')}",
            payload=cast(dict, sanitize_for_json(result)),
        )
        db.add(artifact)
        approval.execution_status = "completed"
        approval.execution_result = cast(dict, sanitize_for_json(result))
        from datetime import UTC, datetime

        approval.executed_at = datetime.now(UTC)
        await db.flush()
        return result
    except Exception:
        approval.execution_status = "failed"
        await db.flush()
        raise
