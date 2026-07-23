"""Shared integration-route evidence and deterministic service-demand projection."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from decimal import Decimal, InvalidOperation
import json

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.calc_engine import (
    DemandStatus,
    FlowEvidence,
    RouteServiceNode,
    ServiceDemandContext,
    ServiceDemandResult,
    propagate_route_flow,
    resolve_service_demand,
)
from app.models import (
    CatalogIntegration,
    DeploymentEnvironmentPlan,
    DeploymentRampPhase,
    DeploymentScenario,
    ServiceCapabilityProfile,
    ServiceProductSkuMapping,
)
from app.schemas.catalog import (
    IntegrationTechnicalDemandResponse,
    TechnicalDemandMetricResponse,
    TechnicalDemandNodeResponse,
)
from app.services.canvas_interoperability import (
    CanvasDesignValidationError,
    TOOL_TO_SERVICE_ID,
    build_canvas_routes,
    parse_canvas_state,
)


TOOL_LABEL_TO_SERVICE_ID = {
    "OIC GEN3": "OIC3",
    "ORACLE INTEGRATION 3": "OIC3",
    "OCI API GATEWAY": "API_GATEWAY",
    "OCI EVENTS": "EVENTS",
    "OCI STREAMING": "STREAMING",
    "OCI QUEUE": "QUEUE",
    "OCI FUNCTIONS": "FUNCTIONS",
    "OCI DATA INTEGRATION": "DATA_INTEGRATION",
    "DATA INTEGRATOR": "ODI",
    "ORACLE GOLDENGATE": "GOLDENGATE",
    "OCI OBJECT STORAGE": "OBJECT_STORAGE",
    "PROCESS AUTOMATION": "PROCESS_AUTOMATION",
    "OCI OBSERVABILITY": "OBSERVABILITY",
    "OCI DATA CATALOG": "DATA_CATALOG",
    "OCI IAM AND SECURITY": "IAM",
}


def _decimal_config_value(value: object, default: str) -> Decimal:
    if not isinstance(value, (str, int, float, Decimal)):
        return Decimal(default)
    try:
        parsed = Decimal(str(value))
    except InvalidOperation:
        return Decimal(default)
    return parsed if parsed.is_finite() else Decimal(default)


def split_tools(value: str | None) -> set[str]:
    """Split a legacy comma-delimited tool selection."""

    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def canvas_tools(value: str | None) -> set[str]:
    """Return governed core and overlay keys from canvas JSON or legacy CSV."""

    if not value:
        return set()
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return split_tools(value)
    if not isinstance(payload, dict):
        return set()
    result: set[str] = set()
    for key in ("coreToolKeys", "overlayKeys"):
        values = payload.get(key)
        if isinstance(values, list):
            result.update(str(item).strip() for item in values if str(item).strip())
    return result


def integration_tools(row: CatalogIntegration) -> set[str]:
    """Return every governed service capability evidenced by one integration."""

    return split_tools(row.core_tools) | canvas_tools(row.additional_tools_overlays)


def integration_tools_with_overrides(
    row: CatalogIntegration,
    tool_overrides: dict[str, tuple[str, str]] | None = None,
) -> set[str]:
    """Resolve tools after applying an in-memory architect patch, when present."""

    override = (tool_overrides or {}).get(row.id)
    if override is None:
        return integration_tools(row)
    core_tools, canvas_state = override
    return split_tools(core_tools) | canvas_tools(canvas_state)


def mapping_predicates_match(
    mapping: ServiceProductSkuMapping,
    config: dict[str, object],
) -> bool:
    """Check whether one approved SKU mapping applies to a service configuration."""

    for key, expected in (mapping.predicates or {}).items():
        actual = config.get(key)
        if isinstance(expected, str):
            if str(actual or "").lower() != expected.lower():
                return False
        elif actual != expected:
            return False
    return True


def service_ids_for_integration(
    row: CatalogIntegration,
    tool_overrides: dict[str, tuple[str, str]] | None,
) -> tuple[str, ...]:
    """Resolve only the services evidenced by this integration's governed route."""

    service_ids: set[str] = set()
    for label in integration_tools_with_overrides(row, tool_overrides):
        normalized = label.strip().upper()
        service_id = TOOL_LABEL_TO_SERVICE_ID.get(normalized) or TOOL_TO_SERVICE_ID.get(normalized)
        if service_id:
            service_ids.add(service_id)
    override = (tool_overrides or {}).get(row.id)
    core_tools = override[0] if override is not None else row.core_tools
    canvas_state = override[1] if override is not None else row.additional_tools_overlays
    try:
        state = parse_canvas_state(canvas_state, tuple(split_tools(core_tools)))
        for route in build_canvas_routes(state):
            service_ids.update(route.service_ids)
    except CanvasDesignValidationError:
        # Canvas governance reports the invalid route separately. Catalog-level
        # evidence remains available so technical coverage does not disappear.
        pass
    return tuple(sorted(service_ids))


def build_flow_evidence(
    integrations: list[CatalogIntegration],
    service_configs: dict[str, dict[str, object]],
    service_policies: dict[str, dict[str, object]],
    tool_overrides: dict[str, tuple[str, str]] | None,
) -> tuple[FlowEvidence, ...]:
    """Propagate effective payload and cardinality through every directed route."""

    evidence: list[FlowEvidence] = []
    for row in integrations:
        payload = Decimal(str(max(float(row.payload_per_execution_kb or 0), 0.0)))
        base_flow = FlowEvidence(
            integration_id=row.id,
            payload_kb=payload,
            logical_payload_kb=payload,
            response_payload_kb=Decimal(str(max(float(row.response_size_kb or 0), 0.0))),
            executions_per_day=Decimal(str(max(float(row.executions_per_day or 0), 0.0))),
            fan_out_targets=max(row.fan_out_targets or 1, 1),
            consumer_count=max(row.fan_out_targets or 1, 1),
        )
        override = (tool_overrides or {}).get(row.id)
        core_tools = override[0] if override is not None else row.core_tools
        canvas_state = override[1] if override is not None else row.additional_tools_overlays
        try:
            state = parse_canvas_state(canvas_state, tuple(split_tools(core_tools)))
            routes = build_canvas_routes(state)
        except CanvasDesignValidationError:
            routes = ()

        if routes:
            seen_prefixes: set[tuple[str, tuple[str, ...]]] = set()
            for route_index, route in enumerate(routes):
                route_nodes = tuple(
                    RouteServiceNode(instance_id=instance_id, service_id=service_id)
                    for instance_id, service_id in zip(
                        route.service_node_ids,
                        route.service_ids,
                        strict=True,
                    )
                )
                route_evidence = propagate_route_flow(
                    base_flow,
                    route_nodes,
                    service_policies=service_policies,
                    service_configs=service_configs,
                    fan_out_by_node={
                        node.instance_id: max(
                            sum(
                                1
                                for edge in state.edges
                                if edge.source_instance_id == node.instance_id
                            ),
                            1,
                        )
                        for node in state.nodes
                    },
                    route_index=route_index,
                )
                for position, flow in enumerate(route_evidence):
                    prefix_key = (
                        str(flow.node_instance_id or ""),
                        route.service_node_ids[: position + 1],
                    )
                    if prefix_key in seen_prefixes:
                        continue
                    seen_prefixes.add(prefix_key)
                    evidence.append(flow)
            continue

        # Legacy rows without a directed canvas are metered only against services
        # explicitly present in their governed catalog evidence.
        for service_id in service_ids_for_integration(row, tool_overrides):
            config = service_configs.get(service_id, {})
            strategy = str(config.get("payload_strategy") or "native")
            pointer_kb = _decimal_config_value(
                config.get("pointer_payload_kb"),
                "4",
            )
            evidence.append(
                replace(
                    base_flow,
                    output_payload_kb=(
                        pointer_kb if strategy == "object_storage_pointer" else payload
                    ),
                    payload_strategy=strategy,
                    offloaded_payload_kb=(
                        payload if strategy == "object_storage_pointer" else Decimal("0")
                    ),
                    service_ids=(service_id,),
                )
            )
    return tuple(evidence)


def resolve_mapping_demand(
    mapping: ServiceProductSkuMapping,
    *,
    flows: tuple[FlowEvidence, ...],
    service_config: dict[str, object],
    selected_service_ids: set[str],
    technical_baseline: dict[str, object] | None = None,
    active_hours_month: Decimal = Decimal("744"),
    demand_share: Decimal = Decimal("1"),
    ha_multiplier: Decimal = Decimal("1"),
) -> ServiceDemandResult:
    """Resolve one approved mapping through the shared pure demand engine."""

    policy = {**mapping.metering_policy}
    if mapping.source_url:
        policy["source_url"] = mapping.source_url
    return resolve_service_demand(
        ServiceDemandContext(
            metric_key=mapping.billing_metric_key,
            service_id=mapping.service_id,
            unit=mapping.quantity_unit,
            flows=flows,
            metering_policy=policy,
            service_config=service_config,
            technical_baseline=technical_baseline or {},
            active_hours_month=active_hours_month,
            demand_share=demand_share,
            ha_multiplier=ha_multiplier,
            selected_service_ids=frozenset(selected_service_ids),
        )
    )


async def _latest_scenario(
    project_id: str,
    db: AsyncSession,
) -> DeploymentScenario | None:
    approved = await db.scalar(
        select(DeploymentScenario)
        .where(
            DeploymentScenario.project_id == project_id,
            DeploymentScenario.status == "approved",
        )
        .order_by(DeploymentScenario.approved_at.desc(), DeploymentScenario.updated_at.desc())
    )
    if approved is not None:
        return approved
    return await db.scalar(
        select(DeploymentScenario)
        .where(DeploymentScenario.project_id == project_id)
        .order_by(DeploymentScenario.updated_at.desc())
    )


def _scenario_config(
    scenario: DeploymentScenario | None,
    service_id: str,
) -> dict[str, object]:
    if scenario is None:
        return {}
    value = scenario.service_config.get(service_id)
    return dict(value) if isinstance(value, dict) else {}


def _metric_response(
    mapping: ServiceProductSkuMapping,
    demand: ServiceDemandResult,
) -> TechnicalDemandMetricResponse:
    return TechnicalDemandMetricResponse(
        mapping_id=mapping.id,
        part_number=mapping.part_number,
        metric_key=demand.metric_key,
        quantity=float(demand.quantity) if demand.quantity is not None else None,
        unit=demand.unit,
        status=demand.status.value,
        adapter=demand.adapter,
        messages_per_month=float(demand.messages_per_month),
        operations_per_month={
            key: float(value) for key, value in demand.operations_per_month.items()
        },
        billing_units_per_month=float(demand.billing_units_per_month),
        rule=demand.rule,
        source_url=demand.source_url,
        warnings=list(demand.warnings),
        blockers=list(demand.blockers),
    )


def select_node_mappings(
    mappings: list[ServiceProductSkuMapping],
    *,
    service_id: str,
    service_config: dict[str, object],
    selected_mapping_ids: set[str],
) -> list[ServiceProductSkuMapping]:
    """Apply the BOM's explicit-variant precedence to one canvas service node."""

    applicable = [
        mapping
        for mapping in mappings
        if mapping.service_id == service_id
        and mapping_predicates_match(mapping, service_config)
    ]
    selected = [
        mapping for mapping in applicable if mapping.id in selected_mapping_ids
    ]
    selected_metric_keys = {mapping.billing_metric_key for mapping in selected}
    required = [
        mapping
        for mapping in applicable
        if mapping.selection_policy == "required"
        and mapping.billing_metric_key not in selected_metric_keys
    ]
    return sorted(
        [*required, *selected],
        key=lambda mapping: (mapping.billing_metric_key, mapping.id),
    )


async def _selected_scenario_mapping_ids(
    scenario: DeploymentScenario | None,
    db: AsyncSession,
) -> set[str]:
    """Return explicit SKU variants selected by the latest project scenario."""

    if scenario is None:
        return set()
    mapping_ids = (
        await db.scalars(
            select(DeploymentRampPhase.sku_mapping_id)
            .join(
                DeploymentEnvironmentPlan,
                DeploymentEnvironmentPlan.id
                == DeploymentRampPhase.environment_plan_id,
            )
            .where(
                DeploymentEnvironmentPlan.scenario_id == scenario.id,
                DeploymentRampPhase.sku_mapping_id.is_not(None),
            )
            .distinct()
        )
    ).all()
    return {mapping_id for mapping_id in mapping_ids if mapping_id}


async def get_integration_technical_demand(
    project_id: str,
    integration_id: str,
    db: AsyncSession,
) -> IntegrationTechnicalDemandResponse:
    """Return explainable per-node technical demand for the integration canvas."""

    integration = await db.scalar(
        select(CatalogIntegration).where(
            CatalogIntegration.id == integration_id,
            CatalogIntegration.project_id == project_id,
        )
    )
    if integration is None:
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "Catalog integration not found",
                "error_code": "CATALOG_INTEGRATION_NOT_FOUND",
            },
        )

    mappings = list(
        (
            await db.scalars(
                select(ServiceProductSkuMapping)
                .where(ServiceProductSkuMapping.status == "approved")
                .order_by(
                    ServiceProductSkuMapping.service_id,
                    ServiceProductSkuMapping.billing_metric_key,
                )
            )
        ).all()
    )
    scenario = await _latest_scenario(project_id, db)
    selected_mapping_ids = await _selected_scenario_mapping_ids(scenario, db)
    evidenced_service_ids = set(service_ids_for_integration(integration, None))
    service_configs = {
        service_id: _scenario_config(scenario, service_id)
        for service_id in evidenced_service_ids
    }
    service_policies: dict[str, dict[str, object]] = {}
    for mapping in mappings:
        if mapping.service_id not in evidenced_service_ids:
            continue
        policy = service_policies.setdefault(mapping.service_id, {})
        for key, value in mapping.metering_policy.items():
            policy.setdefault(key, value)

    flows = build_flow_evidence(
        [integration],
        service_configs,
        service_policies,
        None,
    )
    flows_by_node: dict[str, list[FlowEvidence]] = defaultdict(list)
    for index, flow in enumerate(flows):
        key = flow.node_instance_id or f"legacy:{flow.service_ids[0]}:{index}"
        flows_by_node[key].append(flow)

    profiles = list(
        (
            await db.scalars(
                select(ServiceCapabilityProfile).where(
                    ServiceCapabilityProfile.service_id.in_(evidenced_service_ids),
                    ServiceCapabilityProfile.is_active.is_(True),
                )
            )
        ).all()
    )
    profile_by_service = {profile.service_id: profile for profile in profiles}
    canvas_node_metadata: dict[str, tuple[str, str]] = {}
    try:
        state = parse_canvas_state(
            integration.additional_tools_overlays,
            tuple(split_tools(integration.core_tools)),
        )
        canvas_node_metadata = {
            node.instance_id: (node.tool_key, node.label)
            for node in state.nodes
        }
    except CanvasDesignValidationError:
        pass

    node_responses: list[TechnicalDemandNodeResponse] = []
    global_blockers: list[str] = []
    status_rank = {
        DemandStatus.RESOLVED.value: 0,
        DemandStatus.EXPLICIT_INPUT_REQUIRED.value: 1,
        DemandStatus.BLOCKED.value: 2,
    }
    for node_key, node_flows in flows_by_node.items():
        service_id = node_flows[0].service_ids[0]
        service_config = service_configs.get(service_id, {})
        node_mappings = select_node_mappings(
            mappings,
            service_id=service_id,
            service_config=service_config,
            selected_mapping_ids=selected_mapping_ids,
        )
        metric_responses = [
            _metric_response(
                mapping,
                resolve_mapping_demand(
                    mapping,
                    flows=tuple(node_flows),
                    service_config=service_config,
                    selected_service_ids=evidenced_service_ids,
                ),
            )
            for mapping in node_mappings
        ]
        if not metric_responses:
            node_status = DemandStatus.BLOCKED.value
            node_blockers = [
                f"No approved required SKU mapping covers service {service_id}."
            ]
        else:
            node_status = max(
                (metric.status for metric in metric_responses),
                key=lambda value: status_rank[value],
            )
            node_blockers = list(
                dict.fromkeys(
                    blocker
                    for flow in node_flows
                    for blocker in flow.blockers
                )
            )
            node_blockers.extend(
                blocker
                for metric in metric_responses
                for blocker in metric.blockers
                if blocker not in node_blockers
            )
        global_blockers.extend(
            blocker for blocker in node_blockers if blocker not in global_blockers
        )

        output_payloads = [
            flow.output_payload_kb
            if flow.output_payload_kb is not None
            else flow.payload_kb
            for flow in node_flows
        ]
        input_messages_per_execution = sum(
            max(flow.messages_per_execution, Decimal("1"))
            for flow in node_flows
        )
        output_messages_per_execution = sum(
            max(flow.messages_per_execution, Decimal("1"))
            * max(flow.fragment_count, Decimal("1"))
            for flow in node_flows
        )
        tool_key, label = canvas_node_metadata.get(
            node_key,
            (
                service_id,
                (
                    profile_by_service[service_id].name
                    if service_id in profile_by_service
                    else service_id
                ),
            ),
        )
        profile = profile_by_service.get(service_id)
        node_responses.append(
            TechnicalDemandNodeResponse(
                instance_id=node_key,
                service_id=service_id,
                tool_key=tool_key,
                label=label,
                route_indexes=sorted({flow.route_index for flow in node_flows}),
                input_payload_kb=float(max(flow.payload_kb for flow in node_flows)),
                output_payload_kb=float(max(output_payloads)),
                logical_payload_kb=float(
                    max(
                        flow.logical_payload_kb or flow.payload_kb
                        for flow in node_flows
                    )
                ),
                input_messages_per_execution=float(input_messages_per_execution),
                output_messages_per_execution=float(output_messages_per_execution),
                fragment_count=float(
                    max(flow.fragment_count for flow in node_flows)
                ),
                fan_out_targets=max(flow.fan_out_targets for flow in node_flows),
                payload_strategy=node_flows[0].payload_strategy,
                offloaded_payload_kb=float(
                    max(flow.offloaded_payload_kb for flow in node_flows)
                ),
                status=node_status,
                source_urls=(
                    [
                        item.strip()
                        for item in (profile.oracle_docs_urls or "").splitlines()
                        if item.strip()
                    ]
                    if profile is not None
                    else []
                ),
                blockers=node_blockers,
                metrics=metric_responses,
            )
        )

    return IntegrationTechnicalDemandResponse(
        project_id=project_id,
        integration_id=integration_id,
        scenario_id=scenario.id if scenario is not None else None,
        scenario_status=scenario.status if scenario is not None else None,
        nodes=node_responses,
        blockers=global_blockers,
    )
