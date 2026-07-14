"""Deterministic integration-design candidates for the recommendation workspace."""

from __future__ import annotations

from collections import Counter
from typing import Literal, Sequence, cast

from app.core.calc_engine import Assumptions
from app.migrations.reference_seed_data import CANVAS_COMBINATIONS
from app.models import CatalogIntegration
from app.schemas.ai_review import (
    AiReviewActionCandidate,
    AiReviewActionWorkspace,
    AiReviewCanvasChangeSet,
    AiReviewFieldDiff,
    AiReviewRecommendationCandidate,
    AiReviewRecommendationCheck,
    AiReviewRecommendationCostImpact,
    AiReviewRecommendationMode,
    AiReviewRecommendationWorkspace,
    AiReviewFinding,
    AiReviewGraphContext,
    AiReviewRemediationStep,
    AiReviewTopologyInsight,
)
from app.services import service_rule_service
from app.services.canvas_interoperability import (
    DESTINATION_NODE_ID,
    SOURCE_NODE_ID,
    CanvasEdge,
    CanvasEndpointPosition,
    CanvasNode,
    derive_canvas_semantics,
    evaluate_toolset_interoperability,
    parse_canvas_state,
    serialize_canvas_state,
)
from app.services.service_rule_service import ServiceRuleBundle
from app.services.serializers import split_csv


MODE_TITLES: dict[AiReviewRecommendationMode, str] = {
    "minimum_change": "Minimum governed change",
    "resilience": "Higher resilience",
    "cost_optimized": "Cost-conscious footprint",
}


def _trigger_text(row: CatalogIntegration) -> str:
    return " ".join(
        value for value in (row.trigger_type, row.type, row.base, row.frequency) if value
    ).lower()


def _inferred_pattern(row: CatalogIntegration) -> str | None:
    text = _trigger_text(row)
    if any(token in text for token in ("event", "webhook", "stream", "pub")):
        return "#02"
    if any(token in text for token in ("rest", "soap", "request", "sync")):
        return "#01"
    if any(token in text for token in ("cdc", "replication", "change data")):
        return "#05"
    return None


def _combination_tools(combination: dict[str, object]) -> tuple[list[str], list[str]]:
    return (
        [str(item) for item in cast(list[object], combination["supported_tool_keys"])],
        [str(item) for item in cast(list[object], combination["recommended_overlays"])],
    )


def _compatible_combinations(row: CatalogIntegration) -> list[dict[str, object]]:
    pattern_id = row.selected_pattern or _inferred_pattern(row)
    valid = [item for item in CANVAS_COMBINATIONS if str(item.get("status")) == "Valid"]
    if pattern_id:
        matched = [
            item
            for item in valid
            if pattern_id in [str(value) for value in cast(list[object], item["compatible_pattern_ids"])]
        ]
        if matched:
            return matched
    return valid


def _tool_distance(
    combination: dict[str, object],
    current_tools: set[str],
    current_overlays: set[str],
) -> tuple[int, int, str]:
    tools, overlays = _combination_tools(combination)
    return (
        len(current_tools.symmetric_difference(tools)),
        len(current_overlays.symmetric_difference(overlays)),
        str(combination["code"]),
    )


def _candidate_combinations(
    row: CatalogIntegration,
    current_tools: list[str],
    current_overlays: list[str],
) -> list[tuple[AiReviewRecommendationMode, dict[str, object]]]:
    combinations = _compatible_combinations(row)
    current_tool_set = set(current_tools)
    current_overlay_set = set(current_overlays)
    minimum = min(
        combinations,
        key=lambda item: _tool_distance(item, current_tool_set, current_overlay_set),
    )
    selected: list[tuple[AiReviewRecommendationMode, dict[str, object]]] = [("minimum_change", minimum)]

    resilience_options = [
        item
        for item in combinations
        if {"OCI Queue", "OCI Streaming"}.intersection(_combination_tools(item)[0])
    ]
    if resilience_options:
        resilient = min(
            resilience_options,
            key=lambda item: (
                0 if "OCI Functions" in _combination_tools(item)[0] else 1,
                *_tool_distance(item, current_tool_set, current_overlay_set),
            ),
        )
        selected.append(("resilience", resilient))

    lower_footprint = min(
        combinations,
        key=lambda item: (
            len(_combination_tools(item)[0]) + len(_combination_tools(item)[1]),
            *_tool_distance(item, current_tool_set, current_overlay_set),
        ),
    )
    selected.append(("cost_optimized", lower_footprint))

    unique: list[tuple[AiReviewRecommendationMode, dict[str, object]]] = []
    seen: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    for mode, combination in selected:
        tools, overlays = _combination_tools(combination)
        signature = (tuple(tools), tuple(overlays))
        if signature in seen:
            continue
        seen.add(signature)
        unique.append((mode, combination))
    return unique[:3]


def _ordered_route(core_tools: list[str], overlays: list[str]) -> list[str]:
    edge_overlays = [item for item in overlays if item in {"OCI API Gateway", "OCI Events"}]
    process_overlays = [item for item in overlays if item not in set(edge_overlays)]
    return [*edge_overlays, *core_tools, *process_overlays]


def _candidate_canvas(
    row: CatalogIntegration,
    core_tools: list[str],
    overlays: list[str],
    endpoint_positions: Sequence[CanvasEndpointPosition],
) -> str:
    payload_note = " · ".join(
        item
        for item in (
            f"{row.payload_per_execution_kb:g} KB" if row.payload_per_execution_kb is not None else None,
            row.frequency,
        )
        if item
    )
    route = _ordered_route(core_tools, overlays)
    nodes = tuple(
        CanvasNode(
            instance_id=f"recommendation-node-{index + 1}",
            tool_key=tool_key,
            label=tool_key,
            payload_note=payload_note,
            x=240.0 + index * 220.0,
            y=217.0,
        )
        for index, tool_key in enumerate(route)
    )
    edges: list[CanvasEdge] = []
    previous = SOURCE_NODE_ID
    for index, node in enumerate(nodes, start=1):
        edges.append(
            CanvasEdge(
                edge_id=f"recommendation-edge-{index}",
                source_instance_id=previous,
                target_instance_id=node.instance_id,
                label="",
            )
        )
        previous = node.instance_id
    edges.append(
        CanvasEdge(
            edge_id=f"recommendation-edge-{len(nodes) + 1}",
            source_instance_id=previous,
            target_instance_id=DESTINATION_NODE_ID,
            label="",
        )
    )
    semantics = derive_canvas_semantics(nodes, edges, overlays)
    return serialize_canvas_state(nodes, edges, semantics, endpoint_positions)


def _diff_values(current: list[str], proposed: list[str]) -> tuple[list[str], list[str], list[str]]:
    current_counts = Counter(current)
    proposed_counts = Counter(proposed)
    added = list((proposed_counts - current_counts).elements())
    removed = list((current_counts - proposed_counts).elements())
    retained = list((current_counts & proposed_counts).elements())
    return sorted(added), sorted(removed), sorted(retained)


def _field_diff(field: str, current: list[str], proposed: list[str]) -> AiReviewFieldDiff:
    return AiReviewFieldDiff(
        field=field,
        current=", ".join(current) or None,
        recommended=", ".join(proposed) or None,
    )


def _candidate(
    *,
    mode: AiReviewRecommendationMode,
    combination: dict[str, object],
    row: CatalogIntegration,
    current_tools: list[str],
    current_overlays: list[str],
    endpoint_positions: Sequence[CanvasEndpointPosition],
    service_rules: ServiceRuleBundle,
    evidence_ids: list[str],
) -> AiReviewRecommendationCandidate:
    tools, overlays = _combination_tools(combination)
    report = evaluate_toolset_interoperability(
        core_tool_keys=tools,
        overlay_tool_keys=overlays,
        assumptions=service_rule_service.apply_service_rules(Assumptions(), service_rules),
        payload_kb=row.payload_per_execution_kb,
        trigger_type=row.trigger_type,
        is_real_time=row.is_real_time,
        source_technology=row.source_technology,
        destination_technology=row.destination_technology_1,
        integration_type=row.type,
        service_rules=service_rules,
    )
    added_tools, removed_tools, retained_tools = _diff_values(current_tools, tools)
    added_overlays, removed_overlays, _ = _diff_values(current_overlays, overlays)
    pattern_ids = [str(item) for item in cast(list[object], combination["compatible_pattern_ids"])]
    pattern_id = row.selected_pattern if row.selected_pattern in pattern_ids else pattern_ids[0] if pattern_ids else None
    pattern_status: Literal["pass", "review"] = "pass" if row.selected_pattern in pattern_ids else "review"
    compatibility_status: Literal["pass", "review", "blocked"] = (
        "blocked" if report.blockers else "review" if report.warnings else "pass"
    )
    volumetry_status: Literal["pass", "not_computable"] = (
        "pass"
        if row.payload_per_execution_kb is not None and row.executions_per_day is not None
        else "not_computable"
    )
    candidate_id = f"{mode}-{str(combination['code']).lower()}"
    summary = str(combination["guidance"])
    change_count = len(added_tools) + len(removed_tools) + len(added_overlays) + len(removed_overlays)
    why = (
        f"Uses governed combination {combination['code']} with {change_count} route change(s) "
        f"relative to the saved design."
    )
    checks = [
        AiReviewRecommendationCheck(
            id="route",
            label="Directed source-to-destination route",
            status="pass",
            detail="The preview materializes one connected route through every proposed component.",
        ),
        AiReviewRecommendationCheck(
            id="pattern",
            label="Pattern alignment",
            status=pattern_status,
            detail=(
                f"{row.selected_pattern} is compatible with {combination['code']}."
                if pattern_status == "pass"
                else f"Review pattern selection; {combination['code']} supports {', '.join(pattern_ids)}."
            ),
        ),
        AiReviewRecommendationCheck(
            id="interoperability",
            label="OCI interoperability and limits",
            status=compatibility_status,
            detail=(
                f"{len(report.blockers)} blocker(s), {len(report.warnings)} warning(s), "
                f"and {len(report.advisories)} advisory item(s)."
            ),
        ),
        AiReviewRecommendationCheck(
            id="volumetry",
            label="Volumetry evidence",
            status=volumetry_status,
            detail=(
                "Payload and execution frequency are available for recalculation."
                if volumetry_status == "pass"
                else "Capture payload and execution frequency before relying on a sizing comparison."
            ),
        ),
        AiReviewRecommendationCheck(
            id="cost",
            label="Monthly and contractual cost",
            status="review",
            detail=(
                "Apply the candidate to an unsaved draft, then use Simulate impact with an approved deployment "
                "scenario before deciding whether to save."
            ),
        ),
    ]
    return AiReviewRecommendationCandidate(
        id=candidate_id,
        mode=mode,
        title=MODE_TITLES[mode],
        summary=summary,
        why=why,
        combination_code=str(combination["code"]),
        pattern_id=pattern_id,
        core_tools=tools,
        overlays=overlays,
        canvas_state=_candidate_canvas(row, tools, overlays, endpoint_positions),
        change_set=AiReviewCanvasChangeSet(
            added_tools=added_tools,
            removed_tools=removed_tools,
            retained_tools=retained_tools,
            added_overlays=added_overlays,
            removed_overlays=removed_overlays,
        ),
        field_diffs=[
            _field_diff("core_tools", current_tools, tools),
            _field_diff("architectural_overlays", current_overlays, overlays),
        ],
        implementation_steps=[
            "Preview the proposed route against the saved canvas.",
            "Apply the proposal to an unsaved draft and capture any deployment-specific values.",
            "Run canvas validation and Simulate impact before saving.",
            "Compare technical, monthly, contractual, and ramp deltas against the approved scenario.",
            "Save, recalculate, and publish only after the architect accepts the simulated impact.",
        ],
        prerequisites=[
            "Confirm connectivity mode and private endpoint or connectivity-agent requirements.",
            "Confirm retry, ordering, and idempotency expectations with the owning teams.",
        ],
        validation_plan=[
            "Validate adapter and endpoint connectivity in DEV.",
            "Exercise payload limits, retries, ordering, and failure recovery.",
            "Compare the side-effect-free draft simulation against the saved technical and commercial baseline.",
            "After approval, confirm persisted recalculation and BOM reproduce the accepted preview.",
            "Promote through QA and PROD only after architecture approval.",
        ],
        tradeoffs=[
            f"{combination['code']} activates {', '.join(cast(list[str], combination['activates_metrics']))} metrics.",
            "Additional services can improve separation of concerns while increasing operational ownership.",
        ],
        checks=checks,
        cost_impact=AiReviewRecommendationCostImpact(
            status="requires_draft_simulation",
            direction="unknown",
            detail=(
                "No commercial delta is inferred by the recommendation generator. Apply this candidate to an "
                "unsaved draft and run Simulate impact; the deterministic BOM engine remains authoritative."
            ),
        ),
        evidence_ids=[*evidence_ids, f"COMBINATION-{combination['code']}", service_rules.version],
        confidence="high" if compatibility_status == "pass" and pattern_status == "pass" else "medium",
        applicable=not report.blockers,
    )


def build_integration_recommendation_workspace(
    *,
    row: CatalogIntegration,
    service_rules: ServiceRuleBundle,
    evidence_ids: list[str],
) -> AiReviewRecommendationWorkspace:
    """Build up to three governed alternatives for one integration canvas."""

    parsed = parse_canvas_state(row.additional_tools_overlays, split_csv(row.core_tools))
    current_tools = list(parsed.core_tool_keys)
    current_overlays = list(parsed.overlay_keys)
    candidates = [
        _candidate(
            mode=mode,
            combination=combination,
            row=row,
            current_tools=current_tools,
            current_overlays=current_overlays,
            endpoint_positions=parsed.endpoint_positions,
            service_rules=service_rules,
            evidence_ids=evidence_ids,
        )
        for mode, combination in _candidate_combinations(row, current_tools, current_overlays)
    ]
    applicable = [candidate for candidate in candidates if candidate.applicable]
    recommended = min(
        applicable or candidates,
        key=lambda item: (
            0 if item.mode == "minimum_change" else 1,
            len(item.change_set.added_tools)
            + len(item.change_set.removed_tools)
            + len(item.change_set.added_overlays)
            + len(item.change_set.removed_overlays),
            item.id,
        ),
        default=None,
    )
    current_canvas_state = serialize_canvas_state(
        parsed.nodes,
        parsed.edges,
        derive_canvas_semantics(parsed.nodes, parsed.edges, parsed.overlay_keys),
        parsed.endpoint_positions,
    )
    return AiReviewRecommendationWorkspace(
        integration_id=row.id,
        current_pattern_id=row.selected_pattern,
        current_core_tools=current_tools,
        current_overlays=current_overlays,
        current_canvas_state=current_canvas_state,
        recommended_candidate_id=recommended.id if recommended else None,
        recommendation_basis=(
            "Candidates are generated from governed G01-G18 combinations, normalized Service Product limits, "
            "the saved canvas, pattern, trigger, payload, and frequency. OCI GenAI explains and prioritizes; "
            "deterministic validation remains authoritative."
        ),
        candidates=candidates,
    )


def _action_status(finding: AiReviewFinding | None) -> Literal["ready", "review", "blocked"]:
    if finding is None:
        return "review"
    if finding.severity == "critical":
        return "blocked"
    if finding.severity in {"high", "medium"}:
        return "review"
    return "ready"


def _action_priority(index: int, finding: AiReviewFinding | None) -> Literal["now", "next", "monitor"]:
    if finding is not None and finding.severity in {"critical", "high"}:
        return "now"
    if index < 2:
        return "next"
    return "monitor"


def build_review_action_workspace(
    *,
    project_id: str,
    graph_context: AiReviewGraphContext | None,
    findings: list[AiReviewFinding],
    topology_insights: list[AiReviewTopologyInsight],
    remediation_plan: list[AiReviewRemediationStep],
) -> AiReviewActionWorkspace | None:
    """Build a bounded, prescriptive project or topology action plan."""

    findings_by_id = {item.id: item for item in findings}
    candidates: list[AiReviewActionCandidate] = []
    if graph_context is not None and topology_insights:
        for index, insight in enumerate(topology_insights[:3]):
            related = next(
                (
                    item
                    for item in findings
                    if set(item.integration_ids).intersection(insight.integration_ids)
                ),
                None,
            )
            target = insight.system_name or (
                f"{insight.source_system} to {insight.destination_system}"
                if insight.source_system and insight.destination_system
                else insight.title
            )
            candidates.append(
                AiReviewActionCandidate(
                    id=f"topology-action-{insight.id}",
                    priority=_action_priority(index, related),
                    status=_action_status(related),
                    title=insight.title,
                    summary=insight.summary,
                    what_to_change=[
                        f"Reduce the concentrated risk around {target}.",
                        "Align route, QA, and service-limit decisions for the linked integrations.",
                    ],
                    implementation_steps=[
                        "Inspect the selected dependency cluster and identify the affected inbound and outbound routes.",
                        "Resolve the highest-severity canvas, payload, or QA decision on each linked integration.",
                        "Recalculate the project and rerun the topology investigation before approval.",
                    ],
                    validation_plan=[
                        "Confirm the selected system or edge no longer concentrates open critical/high findings.",
                        "Exercise failure isolation and recovery for the affected dependency path.",
                        "Compare refreshed readiness and blast-radius evidence with this review.",
                    ],
                    expected_impact=[
                        "Lower dependency-path risk and clearer ownership at the selected topology boundary.",
                        "A measurable change in linked QA and canvas evidence rather than narrative-only advice.",
                    ],
                    evidence_ids=[insight.id, *(related.evidence_ids if related else [])],
                    action_label="Open topology context",
                    action_href=insight.action_href,
                    confidence="high" if insight.severity in {"high", "medium"} else "medium",
                )
            )
        return AiReviewActionWorkspace(
            context="topology",
            title="Topology remediation workspace",
            recommendation_basis=(
                "Actions are derived from governed graph concentration, linked integrations, QA state, "
                "canvas warnings, and Service Product rules."
            ),
            candidates=candidates,
        )

    for index, step in enumerate(remediation_plan[:3]):
        related = next(
            (findings_by_id[item] for item in step.finding_ids if item in findings_by_id),
            None,
        )
        candidates.append(
            AiReviewActionCandidate(
                id=f"project-action-{step.id}",
                priority=_action_priority(index, related),
                status=_action_status(related),
                title=step.title,
                summary=step.action,
                what_to_change=[
                    related.recommended_state if related else step.action,
                    f"Owner: {step.owner}; affected integrations: {len(step.integration_ids)}.",
                ],
                implementation_steps=[
                    step.action,
                    "Open the affected records and capture the architect-owned decision or governed design change.",
                    "Recalculate and rerun Architecture Review to verify the finding changed state.",
                ],
                validation_plan=[
                    related.recommendation if related else "Verify remediation against linked governed evidence.",
                    "Confirm QA, canvas compatibility, and service-limit evidence agree after recalculation.",
                    "Do not update the approved baseline until the refreshed review is acceptable.",
                ],
                expected_impact=[step.expected_impact],
                evidence_ids=related.evidence_ids if related else step.finding_ids,
                action_label=related.action_label if related else "Open affected records",
                action_href=step.action_href or (related.action_href if related else f"/projects/{project_id}"),
                confidence="high" if related and related.severity in {"critical", "high"} else "medium",
            )
        )
    if not candidates:
        return None
    return AiReviewActionWorkspace(
        context="project",
        title="Project remediation workspace",
        recommendation_basis=(
            "Actions are generated from prioritized deterministic findings, evidence IDs, ownership, "
            "Service Product rules, stress results, and planned-baseline drift."
        ),
        candidates=candidates,
    )
