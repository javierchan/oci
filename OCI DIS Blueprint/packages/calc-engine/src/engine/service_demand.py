"""Pure, deterministic conversion of integration flow evidence into OCI billing demand.

The module deliberately knows nothing about databases, HTTP, SQLAlchemy, or price
catalogs. Callers provide governed metering policy and normalized flow evidence;
the result explains the technical demand that a commercial SKU will price.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING
from enum import StrEnum
from typing import Mapping, Sequence


ZERO = Decimal("0")
ONE = Decimal("1")
MILLION = Decimal("1000000")
GIB_KB = Decimal("1048576")


class DemandStatus(StrEnum):
    """Terminal state for one technical-to-commercial demand calculation."""

    RESOLVED = "resolved"
    EXPLICIT_INPUT_REQUIRED = "explicit_input_required"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class FlowEvidence:
    """Normalized demand carried by one governed integration flow."""

    integration_id: str
    payload_kb: Decimal
    logical_payload_kb: Decimal | None = None
    output_payload_kb: Decimal | None = None
    response_payload_kb: Decimal = ZERO
    executions_per_day: Decimal = ZERO
    messages_per_execution: Decimal = ONE
    batch_size: Decimal = ONE
    fragment_count: Decimal = ONE
    fan_out_targets: int = 1
    consumer_count: int = 1
    retry_count: Decimal = ZERO
    payload_strategy: str = "native"
    offloaded_payload_kb: Decimal = ZERO
    service_ids: tuple[str, ...] = ()
    node_instance_id: str | None = None
    route_index: int = 0
    upstream_blockers: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()


@dataclass(frozen=True)
class RouteServiceNode:
    """One ordered service occurrence on a governed source-to-destination route."""

    instance_id: str
    service_id: str


@dataclass(frozen=True)
class ServiceDemandContext:
    """All deterministic evidence required by a product demand adapter."""

    metric_key: str
    service_id: str
    unit: str
    flows: tuple[FlowEvidence, ...]
    metering_policy: Mapping[str, object] = field(default_factory=dict)
    service_config: Mapping[str, object] = field(default_factory=dict)
    technical_baseline: Mapping[str, object] = field(default_factory=dict)
    active_hours_month: Decimal = Decimal("744")
    demand_share: Decimal = ONE
    ha_multiplier: Decimal = ONE
    month_days: Decimal = Decimal("31")
    selected_service_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ServiceDemandResult:
    """Explainable quantity consumed by one governed commercial metric."""

    metric_key: str
    service_id: str
    quantity: Decimal | None
    unit: str
    status: DemandStatus
    adapter: str
    input_payload_kb: Decimal
    output_payload_kb: Decimal
    messages_per_month: Decimal
    operations_per_month: Mapping[str, Decimal]
    billing_units_per_month: Decimal
    rule: str
    source_url: str | None = None
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    details: Mapping[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation for BOM provenance and UI."""

        return {
            "metric_key": self.metric_key,
            "service_id": self.service_id,
            "quantity": str(self.quantity) if self.quantity is not None else None,
            "unit": self.unit,
            "status": self.status.value,
            "adapter": self.adapter,
            "input_payload_kb": str(self.input_payload_kb),
            "output_payload_kb": str(self.output_payload_kb),
            "messages_per_month": str(self.messages_per_month),
            "operations_per_month": {
                key: str(value) for key, value in self.operations_per_month.items()
            },
            "billing_units_per_month": str(self.billing_units_per_month),
            "rule": self.rule,
            "source_url": self.source_url,
            "warnings": list(self.warnings),
            "blockers": list(self.blockers),
            "details": dict(self.details),
        }


METRIC_ADAPTERS: dict[str, str] = {
    "api_gateway_call_millions": "api_gateway_calls",
    "di_data_processed_gb": "di_data_processed",
    "di_operator_execution_hours": "explicit_capacity",
    "di_workspace_hours": "workspace_runtime",
    "events": "included_usage",
    "functions_execution_10k_gb_s": "functions_execution",
    "functions_invocation_millions": "functions_invocations",
    "goldengate_ocpu_hours": "explicit_capacity",
    "iam_external_active_users": "explicit_usage",
    "iam_external_users": "explicit_usage",
    "iam_foundation": "included_usage",
    "iam_oracle_apps_premium_users": "explicit_usage",
    "iam_premium_users": "explicit_usage",
    "iam_sms": "explicit_usage",
    "iam_tokens": "explicit_usage",
    "log_analytics_active_storage_units": "explicit_usage",
    "log_analytics_archival_storage_unit_hours": "explicit_usage",
    "logging_storage_gb_months": "explicit_usage",
    "monitoring_ingestion_million_datapoints": "explicit_usage",
    "monitoring_retrieval_million_datapoints": "explicit_usage",
    "object_storage_gb_months": "object_storage",
    "object_storage_request_10k": "object_storage",
    "odi_ocpu_hours": "explicit_capacity",
    "oic_peak_packs_hour": "oic_messages",
    "process_automation": "included_usage",
    "queue_request_millions": "queue_operations",
    "stream_analytics_ocpu_hours": "explicit_capacity",
    "streaming_storage_gb_hours": "streaming_storage",
    "streaming_transfer_gb": "streaming_transfer",
}

FLOW_DRIVEN_ADAPTERS = frozenset(
    {
        "api_gateway_calls",
        "functions_execution",
        "functions_invocations",
        "included_usage",
        "object_storage",
        "oic_messages",
        "queue_operations",
        "streaming_storage",
        "streaming_transfer",
    }
)

SERVICE_PAYLOAD_LIMITS_KB: dict[str, Decimal] = {
    "API_GATEWAY": Decimal("20480"),
    "QUEUE": Decimal("256"),
    "STREAMING": Decimal("1024"),
    "FUNCTIONS": Decimal("6144"),
}


def _decimal(value: object, default: Decimal = ZERO) -> Decimal:
    if value is None or isinstance(value, bool):
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _ceil_units(value: Decimal, unit: Decimal) -> Decimal:
    if value <= ZERO or unit <= ZERO:
        return ZERO
    return (value / unit).to_integral_value(rounding=ROUND_CEILING)


def _policy_decimal(context: ServiceDemandContext, key: str, default: str) -> Decimal:
    return _decimal(context.metering_policy.get(key), Decimal(default))


def _config_decimal(context: ServiceDemandContext, key: str, default: Decimal = ZERO) -> Decimal:
    return _decimal(context.service_config.get(key), default)


def _baseline_decimal(context: ServiceDemandContext, key: str) -> Decimal:
    return _decimal(context.technical_baseline.get(key))


def _source_url(context: ServiceDemandContext) -> str | None:
    value = context.metering_policy.get("source_url")
    return str(value) if value else None


def _flow_messages(flow: FlowEvidence, context: ServiceDemandContext) -> Decimal:
    logical_messages = max(flow.messages_per_execution, ONE)
    batches = _ceil_units(logical_messages, max(flow.batch_size, ONE))
    return (
        max(flow.executions_per_day, ZERO)
        * context.month_days
        * max(batches, ONE)
        * max(flow.fragment_count, ONE)
        * max(flow.retry_count + ONE, ONE)
    )


def _matching_flows(context: ServiceDemandContext) -> tuple[FlowEvidence, ...]:
    matching = tuple(flow for flow in context.flows if context.service_id in flow.service_ids)
    if matching:
        return matching
    if any(flow.service_ids for flow in context.flows):
        return ()
    return context.flows


def _flow_blockers(flows: Sequence[FlowEvidence]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(blocker for flow in flows for blocker in flow.blockers))


def _upstream_flow_blockers(flows: Sequence[FlowEvidence]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            blocker
            for flow in flows
            for blocker in flow.upstream_blockers
        )
    )


def _service_payload_limit(
    service_id: str,
    policy: Mapping[str, object],
) -> Decimal | None:
    policy_key = (
        "max_message_kb"
        if service_id in {"QUEUE", "STREAMING"}
        else "max_request_body_kb"
    )
    default = SERVICE_PAYLOAD_LIMITS_KB.get(service_id)
    if default is None:
        return None
    return _decimal(policy.get(policy_key), default)


def propagate_route_flow(
    base_flow: FlowEvidence,
    route_nodes: Sequence[RouteServiceNode],
    *,
    service_policies: Mapping[str, Mapping[str, object]] | None = None,
    service_configs: Mapping[str, Mapping[str, object]] | None = None,
    fan_out_by_node: Mapping[str, int] | None = None,
    route_index: int = 0,
) -> tuple[FlowEvidence, ...]:
    """Propagate effective payload and message cardinality through one ordered route.

    The function records evidence for each service occurrence. Payload changes only
    when an explicit governed strategy requests fragmentation or a prior Object
    Storage node turns the body into a pointer.
    """

    policies = service_policies or {}
    configs = service_configs or {}
    fan_out = fan_out_by_node or {}
    logical_payload = base_flow.logical_payload_kb or base_flow.payload_kb
    current_payload = base_flow.payload_kb
    messages_per_execution = max(base_flow.messages_per_execution, ONE)
    inherited_blockers = list(base_flow.blockers)
    object_storage_available = False
    evidence: list[FlowEvidence] = []

    for position, node in enumerate(route_nodes):
        service_id = node.service_id
        config = configs.get(service_id, {})
        strategy = str(config.get("payload_strategy") or "native").strip().lower()
        pointer_kb = max(_decimal(config.get("pointer_payload_kb"), Decimal("4")), ONE)
        output_payload = current_payload
        fragment_count = ONE
        offloaded_payload = ZERO
        node_blockers = list(inherited_blockers)

        if service_id == "OBJECT_STORAGE":
            downstream_pointer = any(
                str(configs.get(candidate.service_id, {}).get("payload_strategy") or "")
                .strip()
                .lower()
                == "object_storage_pointer"
                for candidate in route_nodes[position + 1 :]
            )
            if strategy == "object_storage_pointer" or downstream_pointer:
                offloaded_payload = logical_payload
                output_payload = pointer_kb
                strategy = "object_storage_pointer"
            object_storage_available = True
        else:
            payload_limit = _service_payload_limit(service_id, policies.get(service_id, {}))
            if payload_limit is not None and current_payload > payload_limit:
                if strategy == "fragment":
                    fragment_count = _ceil_units(current_payload, payload_limit)
                    output_payload = current_payload / fragment_count
                elif strategy == "object_storage_pointer":
                    if object_storage_available:
                        output_payload = current_payload
                    else:
                        node_blockers.append(
                            f"{service_id} requires an upstream Object Storage node before "
                            "object_storage_pointer can replace the oversized payload."
                        )
                else:
                    node_blockers.append(
                        f"{service_id} payload {current_payload} KB exceeds the governed "
                        f"{payload_limit} KB limit; select fragment or "
                        "object_storage_pointer."
                    )

        node_flow = FlowEvidence(
            integration_id=base_flow.integration_id,
            payload_kb=current_payload,
            logical_payload_kb=logical_payload,
            output_payload_kb=output_payload,
            response_payload_kb=base_flow.response_payload_kb,
            executions_per_day=base_flow.executions_per_day,
            messages_per_execution=messages_per_execution,
            batch_size=base_flow.batch_size,
            fragment_count=fragment_count,
            fan_out_targets=max(fan_out.get(node.instance_id, 1), 1),
            consumer_count=max(fan_out.get(node.instance_id, 1), 1),
            retry_count=base_flow.retry_count,
            payload_strategy=strategy or "native",
            offloaded_payload_kb=offloaded_payload,
            service_ids=(service_id,),
            node_instance_id=node.instance_id,
            route_index=route_index,
            upstream_blockers=tuple(dict.fromkeys(inherited_blockers)),
            blockers=tuple(dict.fromkeys(node_blockers)),
        )
        evidence.append(node_flow)
        inherited_blockers = node_blockers
        current_payload = output_payload
        messages_per_execution *= fragment_count

    return tuple(evidence)


def _payload_summary(flows: Sequence[FlowEvidence]) -> tuple[Decimal, Decimal, Decimal]:
    if not flows:
        return ZERO, ZERO, ZERO
    return (
        max((flow.payload_kb for flow in flows), default=ZERO),
        max(
            (
                flow.output_payload_kb
                if flow.output_payload_kb is not None
                else flow.response_payload_kb
            )
            for flow in flows
        ),
        sum((flow.payload_kb for flow in flows), ZERO),
    )


def _blocked(
    context: ServiceDemandContext,
    adapter: str,
    blockers: Sequence[str],
    *,
    input_payload_kb: Decimal = ZERO,
    output_payload_kb: Decimal = ZERO,
    messages_per_month: Decimal = ZERO,
    operations: Mapping[str, Decimal] | None = None,
    rule: str,
    details: Mapping[str, object] | None = None,
) -> ServiceDemandResult:
    return ServiceDemandResult(
        metric_key=context.metric_key,
        service_id=context.service_id,
        quantity=None,
        unit=context.unit,
        status=DemandStatus.BLOCKED,
        adapter=adapter,
        input_payload_kb=input_payload_kb,
        output_payload_kb=output_payload_kb,
        messages_per_month=messages_per_month,
        operations_per_month=operations or {},
        billing_units_per_month=ZERO,
        rule=rule,
        source_url=_source_url(context),
        blockers=tuple(blockers),
        details=details or {},
    )


def _explicit(
    context: ServiceDemandContext,
    adapter: str,
    *,
    config_key: str | None = None,
    rule: str,
) -> ServiceDemandResult:
    key = config_key or str(context.metering_policy.get("explicit_input_key") or context.metric_key)
    if key not in context.service_config:
        return ServiceDemandResult(
            metric_key=context.metric_key,
            service_id=context.service_id,
            quantity=None,
            unit=context.unit,
            status=DemandStatus.EXPLICIT_INPUT_REQUIRED,
            adapter=adapter,
            input_payload_kb=ZERO,
            output_payload_kb=ZERO,
            messages_per_month=ZERO,
            operations_per_month={},
            billing_units_per_month=ZERO,
            rule=rule,
            source_url=_source_url(context),
            blockers=(f"Provide governed architecture input `{key}` for {context.metric_key}.",),
            details={"required_input_key": key},
        )
    quantity = max(_config_decimal(context, key), ZERO) * context.demand_share
    return ServiceDemandResult(
        metric_key=context.metric_key,
        service_id=context.service_id,
        quantity=quantity,
        unit=context.unit,
        status=DemandStatus.RESOLVED,
        adapter=adapter,
        input_payload_kb=ZERO,
        output_payload_kb=ZERO,
        messages_per_month=ZERO,
        operations_per_month={},
        billing_units_per_month=quantity,
        rule=rule,
        source_url=_source_url(context),
        details={"input_key": key, "input_value": str(quantity)},
    )


def _payload_strategy(
    context: ServiceDemandContext,
    flow: FlowEvidence,
    max_payload_kb: Decimal,
    *,
    adapter: str,
) -> tuple[Decimal, Decimal, str, tuple[str, ...]]:
    """Return effective payload, fragments, strategy, blockers."""

    payload_kb = flow.payload_kb
    declared_strategy = flow.payload_strategy.strip().lower()
    if declared_strategy not in {"", "native"}:
        effective_payload = flow.output_payload_kb
        if effective_payload is None:
            effective_payload = payload_kb
        fragments = max(flow.fragment_count, ONE)
        if declared_strategy == "object_storage_pointer":
            if "OBJECT_STORAGE" not in context.selected_service_ids:
                return (
                    payload_kb,
                    ONE,
                    declared_strategy,
                    (
                        "Object Storage must be selected when payload_strategy is "
                        "object_storage_pointer.",
                    ),
                )
            return effective_payload, fragments, declared_strategy, ()
        if declared_strategy == "fragment":
            if effective_payload > max_payload_kb:
                return (
                    effective_payload,
                    fragments,
                    declared_strategy,
                    (
                        f"Fragmented payload {effective_payload} KB still exceeds the "
                        f"governed {max_payload_kb} KB limit.",
                    ),
                )
            return effective_payload, fragments, declared_strategy, ()
    if payload_kb <= max_payload_kb or payload_kb <= ZERO:
        effective_payload = (
            flow.output_payload_kb
            if flow.output_payload_kb is not None
            else payload_kb
        )
        return effective_payload, max(flow.fragment_count, ONE), "native", ()
    strategy = str(context.service_config.get("payload_strategy") or "").strip().lower()
    if strategy == "fragment":
        fragments = _ceil_units(payload_kb, max_payload_kb)
        return payload_kb / fragments, fragments, strategy, ()
    if strategy == "object_storage_pointer":
        if "OBJECT_STORAGE" not in context.selected_service_ids:
            return (
                payload_kb,
                ONE,
                strategy,
                ("Object Storage must be selected when payload_strategy is object_storage_pointer.",),
            )
        pointer_kb = max(_config_decimal(context, "pointer_payload_kb", Decimal("4")), ONE)
        return pointer_kb, ONE, strategy, ()
    return (
        payload_kb,
        ONE,
        "unresolved",
        (
            f"{context.service_id} payload {payload_kb} KB exceeds the governed "
            f"{max_payload_kb} KB limit; select fragment or object_storage_pointer.",
        ),
    )


def _oic_messages(context: ServiceDemandContext) -> ServiceDemandResult:
    flows = _matching_flows(context)
    block_kb = _policy_decimal(context, "message_block_kb", "50")
    pack_size = _policy_decimal(context, "pack_messages_per_hour", "5000")
    peak_packs = _baseline_decimal(context, "oic_peak_packs_hour")
    total_messages = ZERO
    billable_messages = ZERO
    max_payload, max_response, _ = _payload_summary(flows)
    for flow in flows:
        messages = _flow_messages(flow, context)
        total_messages += messages
        billable_messages += messages * (
            _ceil_units(flow.payload_kb, block_kb)
            + _ceil_units(flow.response_payload_kb, block_kb)
        )
    if peak_packs <= ZERO and billable_messages > ZERO:
        peak_hour_messages = sum(
            (
                max(flow.executions_per_day, ZERO)
                / Decimal("24")
                * max(flow.messages_per_execution, ONE)
                * (
                    _ceil_units(flow.payload_kb, block_kb)
                    + _ceil_units(flow.response_payload_kb, block_kb)
                )
            )
            for flow in flows
        )
        peak_packs = _ceil_units(peak_hour_messages, pack_size)
    quantity = peak_packs * context.demand_share * context.ha_multiplier
    return ServiceDemandResult(
        metric_key=context.metric_key,
        service_id=context.service_id,
        quantity=quantity,
        unit=context.unit,
        status=DemandStatus.RESOLVED,
        adapter="oic_messages",
        input_payload_kb=max_payload,
        output_payload_kb=max_response,
        messages_per_month=total_messages,
        operations_per_month={"trigger_or_invoke": total_messages},
        billing_units_per_month=billable_messages,
        rule=f"ceil(request/{block_kb} KB) + ceil(response/{block_kb} KB), then peak/{pack_size}",
        source_url=_source_url(context),
        details={
            "message_block_kb": str(block_kb),
            "pack_messages_per_hour": str(pack_size),
            "peak_packs_hour": str(quantity),
        },
    )


def _api_gateway_calls(context: ServiceDemandContext) -> ServiceDemandResult:
    flows = _matching_flows(context)
    max_body_kb = _policy_decimal(context, "max_request_body_kb", "20480")
    max_payload, max_response, _ = _payload_summary(flows)
    total_calls = sum((_flow_messages(flow, context) for flow in flows), ZERO)
    blockers: list[str] = []
    for flow in flows:
        _, _, _, strategy_blockers = _payload_strategy(
            context, flow, max_body_kb, adapter="api_gateway_calls"
        )
        blockers.extend(strategy_blockers)
    if blockers:
        return _blocked(
            context,
            "api_gateway_calls",
            blockers,
            input_payload_kb=max_payload,
            output_payload_kb=max_response,
            messages_per_month=total_calls,
            operations={"api_calls": total_calls},
            rule=f"one API call per governed flow message; body <= {max_body_kb} KB",
        )
    return ServiceDemandResult(
        metric_key=context.metric_key,
        service_id=context.service_id,
        quantity=total_calls / MILLION * context.demand_share,
        unit=context.unit,
        status=DemandStatus.RESOLVED,
        adapter="api_gateway_calls",
        input_payload_kb=max_payload,
        output_payload_kb=max_response,
        messages_per_month=total_calls,
        operations_per_month={"api_calls": total_calls},
        billing_units_per_month=total_calls,
        rule=f"API calls / {MILLION}; partial million is prorated",
        source_url=_source_url(context),
        details={"max_request_body_kb": str(max_body_kb)},
    )


def _queue_operations(context: ServiceDemandContext) -> ServiceDemandResult:
    flows = _matching_flows(context)
    request_block_kb = _policy_decimal(context, "request_block_kb", "64")
    max_message_kb = _policy_decimal(context, "max_message_kb", "256")
    configured = context.service_config.get("queue_operations")
    operation_counts = dict(configured) if isinstance(configured, Mapping) else {
        "push": 1,
        "get": 1,
        "delete": 1,
        "update": 0,
    }
    total_operations: dict[str, Decimal] = {
        "push": ZERO,
        "get": ZERO,
        "delete": ZERO,
        "update": ZERO,
    }
    total_messages = ZERO
    total_request_units = ZERO
    max_input, _, _ = _payload_summary(flows)
    max_output = ZERO
    blockers: list[str] = []
    strategy_details: list[dict[str, object]] = []
    for flow in flows:
        messages = _flow_messages(flow, context)
        consumers = max(
            int(
                _config_decimal(
                    context,
                    "consumer_count",
                    Decimal(str(max(flow.consumer_count, flow.fan_out_targets, 1))),
                )
            ),
            1,
        )
        effective_payload, fragments, strategy, strategy_blockers = _payload_strategy(
            context, flow, max_message_kb, adapter="queue_operations"
        )
        blockers.extend(strategy_blockers)
        fragmented_messages = (
            messages * fragments if flow.fragment_count <= ONE and fragments > ONE else messages
        )
        total_messages += fragmented_messages
        max_output = max(max_output, effective_payload)
        push_count = fragmented_messages * _decimal(operation_counts.get("push"), ONE)
        get_count = fragmented_messages * _decimal(operation_counts.get("get"), ONE) * consumers
        delete_count = fragmented_messages * _decimal(operation_counts.get("delete"), ONE) * consumers
        update_count = fragmented_messages * _decimal(operation_counts.get("update"), ZERO)
        payload_units = max(_ceil_units(effective_payload, request_block_kb), ONE)
        total_operations["push"] += push_count
        total_operations["get"] += get_count
        total_operations["delete"] += delete_count
        total_operations["update"] += update_count
        total_request_units += (
            (push_count + get_count) * payload_units
            + delete_count
            + update_count
        )
        strategy_details.append(
            {
                "integration_id": flow.integration_id,
                "strategy": strategy,
                "fragments_per_message": str(fragments),
                "effective_payload_kb": str(effective_payload),
                "consumer_count": consumers,
                "request_units_per_payload_operation": str(payload_units),
            }
        )
    if blockers:
        return _blocked(
            context,
            "queue_operations",
            blockers,
            input_payload_kb=max_input,
            output_payload_kb=max_output,
            messages_per_month=total_messages,
            operations=total_operations,
            rule=(
                f"push/get payload operations round to {request_block_kb} KB blocks; "
                "delete/update count as requests"
            ),
            details={"flow_strategies": strategy_details},
        )
    warnings = (
        (
            "Queue operations use the inferred standard lifecycle push/get/delete. "
            "Override queue_operations only when the approved design differs.",
        )
        if not isinstance(configured, Mapping)
        else ()
    )
    return ServiceDemandResult(
        metric_key=context.metric_key,
        service_id=context.service_id,
        quantity=total_request_units / MILLION * context.demand_share,
        unit=context.unit,
        status=DemandStatus.RESOLVED,
        adapter="queue_operations",
        input_payload_kb=max_input,
        output_payload_kb=max_output,
        messages_per_month=total_messages,
        operations_per_month=total_operations,
        billing_units_per_month=total_request_units,
        rule=(
            f"ceil(payload/{request_block_kb} KB) for each push/get; "
            "delete/update counted independently"
        ),
        source_url=_source_url(context),
        warnings=warnings,
        details={
            "request_block_kb": str(request_block_kb),
            "max_message_kb": str(max_message_kb),
            "flow_strategies": strategy_details,
        },
    )


def _streaming_transfer(context: ServiceDemandContext) -> ServiceDemandResult:
    flows = _matching_flows(context)
    max_message_kb = _policy_decimal(context, "max_message_kb", "1024")
    puts = ZERO
    gets = ZERO
    transferred_kb = ZERO
    max_input, _, _ = _payload_summary(flows)
    max_output = ZERO
    blockers: list[str] = []
    details: list[dict[str, object]] = []
    for flow in flows:
        messages = _flow_messages(flow, context)
        consumers = max(
            int(
                _config_decimal(
                    context,
                    "consumer_count",
                    Decimal(str(max(flow.consumer_count, flow.fan_out_targets, 1))),
                )
            ),
            1,
        )
        effective_payload, fragments, strategy, strategy_blockers = _payload_strategy(
            context, flow, max_message_kb, adapter="streaming_transfer"
        )
        blockers.extend(strategy_blockers)
        message_count = (
            messages * fragments if flow.fragment_count <= ONE and fragments > ONE else messages
        )
        puts += message_count
        gets += message_count * consumers
        transferred_kb += effective_payload * (message_count + message_count * consumers)
        max_output = max(max_output, effective_payload)
        details.append(
            {
                "integration_id": flow.integration_id,
                "strategy": strategy,
                "fragments_per_message": str(fragments),
                "consumer_count": consumers,
                "effective_payload_kb": str(effective_payload),
            }
        )
    operations = {"put": puts, "get": gets}
    if blockers:
        return _blocked(
            context,
            "streaming_transfer",
            blockers,
            input_payload_kb=max_input,
            output_payload_kb=max_output,
            messages_per_month=puts,
            operations=operations,
            rule=f"PUT + GET bytes by consumer; message <= {max_message_kb} KB",
            details={"flow_strategies": details},
        )
    return ServiceDemandResult(
        metric_key=context.metric_key,
        service_id=context.service_id,
        quantity=transferred_kb / GIB_KB * context.demand_share,
        unit=context.unit,
        status=DemandStatus.RESOLVED,
        adapter="streaming_transfer",
        input_payload_kb=max_input,
        output_payload_kb=max_output,
        messages_per_month=puts,
        operations_per_month=operations,
        billing_units_per_month=transferred_kb,
        rule="sum(PUT bytes + GET bytes for each governed consumer) / GiB",
        source_url=_source_url(context),
        details={"max_message_kb": str(max_message_kb), "flow_strategies": details},
    )


def _streaming_storage(context: ServiceDemandContext) -> ServiceDemandResult:
    transfer_context = ServiceDemandContext(
        **{**context.__dict__, "metric_key": "streaming_transfer_gb", "unit": "GB transferred"}
    )
    transfer = _streaming_transfer(transfer_context)
    if transfer.status is DemandStatus.BLOCKED:
        return ServiceDemandResult(
            **{
                **transfer.__dict__,
                "metric_key": context.metric_key,
                "unit": context.unit,
                "adapter": "streaming_storage",
            }
        )
    retention_days = _config_decimal(
        context,
        "retention_days",
        _policy_decimal(context, "default_retention_days", "1"),
    )
    max_retention = _policy_decimal(context, "max_retention_days", "7")
    if retention_days <= ZERO or retention_days > max_retention:
        return _blocked(
            context,
            "streaming_storage",
            (f"Streaming retention_days must be between 1 and {max_retention}.",),
            input_payload_kb=transfer.input_payload_kb,
            output_payload_kb=transfer.output_payload_kb,
            messages_per_month=transfer.messages_per_month,
            operations=transfer.operations_per_month,
            rule="daily written GB × retention days × 24 hours",
        )
    written_kb = ZERO
    for flow in _matching_flows(context):
        effective_payload, _, _, _ = _payload_strategy(
            context,
            flow,
            _policy_decimal(context, "max_message_kb", "1024"),
            adapter="streaming_storage",
        )
        written_kb += effective_payload * _flow_messages(flow, context)
    daily_gb = written_kb / GIB_KB / context.month_days
    quantity = daily_gb * retention_days * Decimal("24") * context.demand_share
    return ServiceDemandResult(
        metric_key=context.metric_key,
        service_id=context.service_id,
        quantity=quantity,
        unit=context.unit,
        status=DemandStatus.RESOLVED,
        adapter="streaming_storage",
        input_payload_kb=transfer.input_payload_kb,
        output_payload_kb=transfer.output_payload_kb,
        messages_per_month=transfer.messages_per_month,
        operations_per_month=transfer.operations_per_month,
        billing_units_per_month=quantity,
        rule="written GB/day × retention days × 24",
        source_url=_source_url(context),
        details={"retention_days": str(retention_days), "max_retention_days": str(max_retention)},
    )


def _functions(context: ServiceDemandContext, *, execution: bool) -> ServiceDemandResult:
    flows = _matching_flows(context)
    max_body_kb = _policy_decimal(context, "max_request_body_kb", "6144")
    max_input, max_response, _ = _payload_summary(flows)
    total_invocations = sum((_flow_messages(flow, context) for flow in flows), ZERO)
    blockers: list[str] = []
    for flow in flows:
        _, _, _, strategy_blockers = _payload_strategy(
            context, flow, max_body_kb, adapter="functions"
        )
        blockers.extend(strategy_blockers)
    if blockers:
        return _blocked(
            context,
            "functions_execution" if execution else "functions_invocations",
            blockers,
            input_payload_kb=max_input,
            output_payload_kb=max_response,
            messages_per_month=total_invocations,
            operations={"invocations": total_invocations},
            rule=f"function request body <= {max_body_kb} KB",
        )
    baseline_key = "functions_execution_10k_gb_s" if execution else "functions_invocation_millions"
    baseline = _baseline_decimal(context, baseline_key)
    if baseline <= ZERO and execution:
        memory_gb = _config_decimal(context, "memory_gb")
        duration_seconds = _config_decimal(context, "duration_seconds")
        if memory_gb <= ZERO or duration_seconds <= ZERO:
            return _explicit(
                context,
                "functions_execution",
                config_key="execution_10k_gb_s",
                rule="invocations × memory GB × duration seconds / 10,000",
            )
        baseline = total_invocations * memory_gb * duration_seconds / Decimal("10000")
    if baseline <= ZERO:
        baseline = total_invocations / MILLION
    return ServiceDemandResult(
        metric_key=context.metric_key,
        service_id=context.service_id,
        quantity=baseline * context.demand_share,
        unit=context.unit,
        status=DemandStatus.RESOLVED,
        adapter="functions_execution" if execution else "functions_invocations",
        input_payload_kb=max_input,
        output_payload_kb=max_response,
        messages_per_month=total_invocations,
        operations_per_month={"invocations": total_invocations},
        billing_units_per_month=baseline,
        rule=(
            "invocations × memory GB × duration seconds / 10,000"
            if execution
            else "invocations / 1,000,000"
        ),
        source_url=_source_url(context),
        details={"max_request_body_kb": str(max_body_kb)},
    )


def _object_storage(context: ServiceDemandContext) -> ServiceDemandResult:
    flows = _matching_flows(context)
    input_payload, output_payload, _ = _payload_summary(flows)
    retention_days = _config_decimal(
        context,
        "retention_days",
        _policy_decimal(context, "default_retention_days", "30"),
    )
    read_count = max(_config_decimal(context, "reads_per_object", ONE), ZERO)
    object_writes = ZERO
    object_reads = ZERO
    stored_kb = ZERO
    for flow in flows:
        offloaded_kb = max(flow.offloaded_payload_kb, ZERO)
        if offloaded_kb <= ZERO and flow.payload_strategy == "object_storage_pointer":
            offloaded_kb = max(flow.payload_kb - (flow.output_payload_kb or ZERO), ZERO)
        if offloaded_kb <= ZERO:
            continue
        messages = _flow_messages(flow, context)
        object_writes += messages
        consumers = max(flow.consumer_count, flow.fan_out_targets, 1)
        object_reads += messages * read_count * consumers
        stored_kb += offloaded_kb * messages

    explicit_key = str(
        context.metering_policy.get("explicit_input_key") or context.metric_key
    )
    if stored_kb <= ZERO and explicit_key in context.service_config:
        return _explicit(
            context,
            "object_storage",
            config_key=explicit_key,
            rule="explicit governed storage capacity or request evidence",
        )
    if stored_kb <= ZERO:
        return ServiceDemandResult(
            metric_key=context.metric_key,
            service_id=context.service_id,
            quantity=ZERO,
            unit=context.unit,
            status=DemandStatus.RESOLVED,
            adapter="object_storage",
            input_payload_kb=input_payload,
            output_payload_kb=output_payload,
            messages_per_month=ZERO,
            operations_per_month={"put": ZERO, "get": ZERO},
            billing_units_per_month=ZERO,
            rule="No payload is offloaded on the governed route.",
            source_url=_source_url(context),
            details={"retention_days": str(retention_days)},
        )

    if context.metric_key == "object_storage_request_10k":
        requests = object_writes + object_reads
        quantity = requests / Decimal("10000") * context.demand_share
        return ServiceDemandResult(
            metric_key=context.metric_key,
            service_id=context.service_id,
            quantity=quantity,
            unit=context.unit,
            status=DemandStatus.RESOLVED,
            adapter="object_storage",
            input_payload_kb=input_payload,
            output_payload_kb=output_payload,
            messages_per_month=object_writes,
            operations_per_month={"put": object_writes, "get": object_reads},
            billing_units_per_month=requests,
            rule="(object writes + governed reads) / 10,000",
            source_url=_source_url(context),
            details={"retention_days": str(retention_days)},
        )

    average_gb_month = (
        stored_kb / GIB_KB * max(retention_days, ONE) / context.month_days
    )
    return ServiceDemandResult(
        metric_key=context.metric_key,
        service_id=context.service_id,
        quantity=average_gb_month * context.demand_share,
        unit=context.unit,
        status=DemandStatus.RESOLVED,
        adapter="object_storage",
        input_payload_kb=input_payload,
        output_payload_kb=output_payload,
        messages_per_month=object_writes,
        operations_per_month={"put": object_writes, "get": object_reads},
        billing_units_per_month=stored_kb,
        rule="offloaded payload GB × retained fraction of month",
        source_url=_source_url(context),
        details={
            "retention_days": str(retention_days),
            "offloaded_kb_month": str(stored_kb),
        },
    )


def _baseline(
    context: ServiceDemandContext,
    adapter: str,
    baseline_key: str,
    *,
    rule: str,
    ha: bool = False,
) -> ServiceDemandResult:
    quantity = _baseline_decimal(context, baseline_key)
    if quantity <= ZERO:
        return _explicit(context, adapter, config_key=baseline_key, rule=rule)
    multiplier = context.demand_share * (context.ha_multiplier if ha else ONE)
    return ServiceDemandResult(
        metric_key=context.metric_key,
        service_id=context.service_id,
        quantity=quantity * multiplier,
        unit=context.unit,
        status=DemandStatus.RESOLVED,
        adapter=adapter,
        input_payload_kb=max((flow.payload_kb for flow in _matching_flows(context)), default=ZERO),
        output_payload_kb=ZERO,
        messages_per_month=sum((_flow_messages(flow, context) for flow in _matching_flows(context)), ZERO),
        operations_per_month={},
        billing_units_per_month=quantity,
        rule=rule,
        source_url=_source_url(context),
    )


def resolve_service_demand(context: ServiceDemandContext) -> ServiceDemandResult:
    """Resolve one governed metric without using price or persistence state."""

    adapter = str(
        context.metering_policy.get("demand_adapter")
        or METRIC_ADAPTERS.get(context.metric_key)
        or ""
    )
    if not adapter:
        return _blocked(
            context,
            "missing",
            (f"No deterministic demand adapter is registered for {context.metric_key}.",),
            rule="Every active BOM metric requires a governed demand adapter.",
        )
    matching_flows = _matching_flows(context)
    inherited_blockers = _upstream_flow_blockers(matching_flows)
    if adapter in FLOW_DRIVEN_ADAPTERS and inherited_blockers:
        input_payload, output_payload, _ = _payload_summary(matching_flows)
        return _blocked(
            context,
            adapter,
            inherited_blockers,
            input_payload_kb=input_payload,
            output_payload_kb=output_payload,
            messages_per_month=sum(
                (_flow_messages(flow, context) for flow in matching_flows),
                ZERO,
            ),
            rule="Upstream route blockers must be resolved before demand can be priced.",
        )
    if (
        adapter in FLOW_DRIVEN_ADAPTERS
        and context.flows
        and any(flow.service_ids for flow in context.flows)
        and not matching_flows
    ):
        return _blocked(
            context,
            adapter,
            (
                f"No governed flow evidence is tagged for service {context.service_id}; "
                "zero demand cannot be inferred from an unrelated route.",
            ),
            rule="Flow-driven demand requires at least one route segment for the selected service.",
        )
    if adapter == "oic_messages":
        return _oic_messages(context)
    if adapter == "api_gateway_calls":
        return _api_gateway_calls(context)
    if adapter == "queue_operations":
        return _queue_operations(context)
    if adapter == "streaming_transfer":
        return _streaming_transfer(context)
    if adapter == "streaming_storage":
        return _streaming_storage(context)
    if adapter == "functions_execution":
        return _functions(context, execution=True)
    if adapter == "functions_invocations":
        return _functions(context, execution=False)
    if adapter == "di_data_processed":
        return _baseline(
            context,
            adapter,
            "di_data_processed_gb",
            rule="governed monthly DI data processed",
        )
    if adapter == "workspace_runtime":
        workspace_count = _config_decimal(context, "workspace_count", ONE)
        quantity = workspace_count * context.active_hours_month * context.ha_multiplier
        return ServiceDemandResult(
            metric_key=context.metric_key,
            service_id=context.service_id,
            quantity=quantity,
            unit=context.unit,
            status=DemandStatus.RESOLVED,
            adapter=adapter,
            input_payload_kb=ZERO,
            output_payload_kb=ZERO,
            messages_per_month=ZERO,
            operations_per_month={},
            billing_units_per_month=quantity,
            rule="workspace count × active runtime hours × HA multiplier",
            source_url=_source_url(context),
            details={"workspace_count": str(workspace_count)},
        )
    if adapter == "object_storage":
        return _object_storage(context)
    if adapter in {"explicit_capacity", "explicit_usage"}:
        return _explicit(
            context,
            adapter,
            rule="explicit governed architecture quantity",
        )
    if adapter == "included_usage":
        flows = _matching_flows(context)
        input_payload, output_payload, _ = _payload_summary(flows)
        messages = sum((_flow_messages(flow, context) for flow in flows), ZERO)
        return ServiceDemandResult(
            metric_key=context.metric_key,
            service_id=context.service_id,
            quantity=ZERO,
            unit=context.unit,
            status=DemandStatus.RESOLVED,
            adapter=adapter,
            input_payload_kb=input_payload,
            output_payload_kb=output_payload,
            messages_per_month=messages,
            operations_per_month={"events": messages} if messages > ZERO else {},
            billing_units_per_month=ZERO,
            rule="No direct SKU charge; downstream usage remains independently metered.",
            source_url=_source_url(context),
        )
    return _blocked(
        context,
        adapter,
        (f"Demand adapter `{adapter}` is not implemented.",),
        rule="Every configured adapter must have executable deterministic behavior.",
    )


def registered_metric_keys() -> frozenset[str]:
    """Expose deterministic coverage for quality gates and governance tests."""

    return frozenset(METRIC_ADAPTERS)
