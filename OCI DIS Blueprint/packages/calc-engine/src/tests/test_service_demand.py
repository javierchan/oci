"""Boundary and propagation tests for governed service-demand adapters."""

from decimal import Decimal

import pytest

from engine.service_demand import (
    DemandStatus,
    FlowEvidence,
    RouteServiceNode,
    ServiceDemandContext,
    propagate_route_flow,
    registered_metric_keys,
    resolve_service_demand,
)


def _context(
    metric_key: str,
    service_id: str,
    payload_kb: str,
    *,
    policy: dict[str, object] | None = None,
    config: dict[str, object] | None = None,
    flow_overrides: dict[str, object] | None = None,
    selected_service_ids: frozenset[str] = frozenset(),
) -> ServiceDemandContext:
    flow_values: dict[str, object] = {
        "integration_id": "INT-001",
        "payload_kb": Decimal(payload_kb),
        "executions_per_day": Decimal("1"),
        "service_ids": (service_id,),
    }
    flow_values.update(flow_overrides or {})
    return ServiceDemandContext(
        metric_key=metric_key,
        service_id=service_id,
        unit="billing units",
        flows=(FlowEvidence(**flow_values),),
        metering_policy=policy or {},
        service_config=config or {},
        month_days=Decimal("1"),
        selected_service_ids=selected_service_ids,
    )


@pytest.mark.parametrize(
    ("payload_kb", "expected_units"),
    (("50", Decimal("1")), ("51", Decimal("2"))),
)
def test_oic_uses_50kb_billing_blocks_without_treating_them_as_transport_limits(
    payload_kb: str,
    expected_units: Decimal,
) -> None:
    result = resolve_service_demand(
        _context(
            "oic_peak_packs_hour",
            "OIC3",
            payload_kb,
            policy={"message_block_kb": 50, "pack_messages_per_hour": 5000},
        )
    )

    assert result.status is DemandStatus.RESOLVED
    assert result.billing_units_per_month == expected_units
    assert result.quantity == Decimal("1")


@pytest.mark.parametrize(
    ("payload_kb", "expected_request_units"),
    (
        ("64", Decimal("3")),
        ("65", Decimal("5")),
        ("256", Decimal("9")),
    ),
)
def test_queue_rounds_payload_operations_and_counts_the_full_message_lifecycle(
    payload_kb: str,
    expected_request_units: Decimal,
) -> None:
    result = resolve_service_demand(
        _context(
            "queue_request_millions",
            "QUEUE",
            payload_kb,
            policy={"request_block_kb": 64, "max_message_kb": 256},
        )
    )

    assert result.status is DemandStatus.RESOLVED
    assert result.operations_per_month == {
        "push": Decimal("1"),
        "get": Decimal("1"),
        "delete": Decimal("1"),
        "update": Decimal("0"),
    }
    assert result.billing_units_per_month == expected_request_units
    assert result.quantity == expected_request_units / Decimal("1000000")


def test_queue_blocks_oversized_messages_until_transport_strategy_is_explicit() -> None:
    result = resolve_service_demand(
        _context(
            "queue_request_millions",
            "QUEUE",
            "257",
            policy={"request_block_kb": 64, "max_message_kb": 256},
        )
    )

    assert result.status is DemandStatus.BLOCKED
    assert "select fragment or object_storage_pointer" in result.blockers[0]


def test_queue_fragmentation_changes_message_and_operation_counts() -> None:
    result = resolve_service_demand(
        _context(
            "queue_request_millions",
            "QUEUE",
            "257",
            policy={"request_block_kb": 64, "max_message_kb": 256},
            config={"payload_strategy": "fragment"},
        )
    )

    assert result.status is DemandStatus.RESOLVED
    assert result.output_payload_kb == Decimal("128.5")
    assert result.messages_per_month == Decimal("2")
    assert result.operations_per_month["push"] == Decimal("2")
    assert result.operations_per_month["get"] == Decimal("2")
    assert result.operations_per_month["delete"] == Decimal("2")
    assert result.billing_units_per_month == Decimal("14")


def test_streaming_counts_put_and_get_bytes_for_each_consumer() -> None:
    result = resolve_service_demand(
        _context(
            "streaming_transfer_gb",
            "STREAMING",
            "1024",
            policy={"max_message_kb": 1024},
            flow_overrides={"consumer_count": 3},
        )
    )

    assert result.status is DemandStatus.RESOLVED
    assert result.operations_per_month == {
        "put": Decimal("1"),
        "get": Decimal("3"),
    }
    assert result.billing_units_per_month == Decimal("4096")


def test_streaming_blocks_above_1mb_without_a_strategy() -> None:
    result = resolve_service_demand(
        _context(
            "streaming_transfer_gb",
            "STREAMING",
            "1025",
            policy={"max_message_kb": 1024},
        )
    )

    assert result.status is DemandStatus.BLOCKED


def test_pointer_strategy_prices_object_storage_and_downstream_pointer_payload() -> None:
    flow = {
        "output_payload_kb": Decimal("4"),
        "payload_strategy": "object_storage_pointer",
        "offloaded_payload_kb": Decimal("1481"),
        "consumer_count": 2,
    }
    object_storage = resolve_service_demand(
        _context(
            "object_storage_request_10k",
            "OBJECT_STORAGE",
            "1485",
            config={"retention_days": 30},
            flow_overrides=flow,
            selected_service_ids=frozenset({"OBJECT_STORAGE", "QUEUE"}),
        )
    )
    queue = resolve_service_demand(
        _context(
            "queue_request_millions",
            "QUEUE",
            "1485",
            policy={"request_block_kb": 64, "max_message_kb": 256},
            flow_overrides=flow,
            selected_service_ids=frozenset({"OBJECT_STORAGE", "QUEUE"}),
        )
    )

    assert object_storage.status is DemandStatus.RESOLVED
    assert object_storage.operations_per_month == {
        "put": Decimal("1"),
        "get": Decimal("2"),
    }
    assert queue.status is DemandStatus.RESOLVED
    assert queue.output_payload_kb == Decimal("4")
    assert queue.messages_per_month == Decimal("1")


def test_route_fragmentation_propagates_effective_payload_and_message_cardinality() -> None:
    route = propagate_route_flow(
        FlowEvidence(
            integration_id="INT-ROUTE-001",
            payload_kb=Decimal("1485"),
            executions_per_day=Decimal("1"),
        ),
        (
            RouteServiceNode("oic-node", "OIC3"),
            RouteServiceNode("queue-node", "QUEUE"),
            RouteServiceNode("function-node", "FUNCTIONS"),
        ),
        service_policies={
            "QUEUE": {"max_message_kb": 256, "request_block_kb": 64},
        },
        service_configs={
            "QUEUE": {"payload_strategy": "fragment"},
        },
    )

    assert [flow.service_ids for flow in route] == [("OIC3",), ("QUEUE",), ("FUNCTIONS",)]
    assert route[1].payload_kb == Decimal("1485")
    assert route[1].output_payload_kb == Decimal("247.5")
    assert route[1].fragment_count == Decimal("6")
    assert route[2].payload_kb == Decimal("247.5")
    assert route[2].messages_per_execution == Decimal("6")

    queue = resolve_service_demand(
        ServiceDemandContext(
            metric_key="queue_request_millions",
            service_id="QUEUE",
            unit="million requests",
            flows=route,
            metering_policy={"max_message_kb": 256, "request_block_kb": 64},
            month_days=Decimal("1"),
            selected_service_ids=frozenset({"OIC3", "QUEUE", "FUNCTIONS"}),
        )
    )
    assert queue.status is DemandStatus.RESOLVED
    assert queue.messages_per_month == Decimal("6")
    assert queue.operations_per_month == {
        "push": Decimal("6"),
        "get": Decimal("6"),
        "delete": Decimal("6"),
        "update": Decimal("0"),
    }


def test_route_pointer_strategy_offloads_body_before_downstream_queue() -> None:
    route = propagate_route_flow(
        FlowEvidence(
            integration_id="INT-ROUTE-002",
            payload_kb=Decimal("1485"),
            executions_per_day=Decimal("1"),
        ),
        (
            RouteServiceNode("object-node", "OBJECT_STORAGE"),
            RouteServiceNode("queue-node", "QUEUE"),
            RouteServiceNode("function-node", "FUNCTIONS"),
        ),
        service_policies={
            "QUEUE": {"max_message_kb": 256, "request_block_kb": 64},
        },
        service_configs={
            "QUEUE": {"payload_strategy": "object_storage_pointer"},
            "OBJECT_STORAGE": {"pointer_payload_kb": 4},
        },
    )

    assert route[0].offloaded_payload_kb == Decimal("1485")
    assert route[0].output_payload_kb == Decimal("4")
    assert route[1].payload_kb == Decimal("4")
    assert route[2].payload_kb == Decimal("4")
    assert not route[1].blockers


def test_route_oversize_blocker_is_inherited_by_downstream_services() -> None:
    route = propagate_route_flow(
        FlowEvidence(
            integration_id="INT-ROUTE-003",
            payload_kb=Decimal("257"),
            executions_per_day=Decimal("1"),
        ),
        (
            RouteServiceNode("queue-node", "QUEUE"),
            RouteServiceNode("function-node", "FUNCTIONS"),
        ),
        service_policies={"QUEUE": {"max_message_kb": 256}},
    )

    assert len(route[0].blockers) == 1
    assert route[0].upstream_blockers == ()
    assert route[1].blockers == route[0].blockers
    assert route[1].upstream_blockers == route[0].blockers
    queue = resolve_service_demand(
        ServiceDemandContext(
            metric_key="queue_request_millions",
            service_id="QUEUE",
            unit="million requests",
            flows=route,
            month_days=Decimal("1"),
        )
    )
    assert queue.status is DemandStatus.BLOCKED
    assert "exceeds the governed 256 KB limit" in queue.blockers[0]
    assert queue.rule == (
        "push/get payload operations round to 64 KB blocks; "
        "delete/update count as requests"
    )
    functions = resolve_service_demand(
        ServiceDemandContext(
            metric_key="functions_invocation_millions",
            service_id="FUNCTIONS",
            unit="million invocations",
            flows=route,
            month_days=Decimal("1"),
        )
    )
    assert functions.status is DemandStatus.BLOCKED
    assert functions.blockers == route[0].blockers
    assert functions.rule == (
        "Upstream route blockers must be resolved before demand can be priced."
    )


def test_service_tagged_flows_do_not_fall_back_to_unrelated_integrations() -> None:
    context = ServiceDemandContext(
        metric_key="queue_request_millions",
        service_id="QUEUE",
        unit="million requests",
        flows=(
            FlowEvidence(
                integration_id="stream-only",
                payload_kb=Decimal("64"),
                executions_per_day=Decimal("100"),
                service_ids=("STREAMING",),
            ),
        ),
        month_days=Decimal("1"),
    )

    result = resolve_service_demand(context)

    assert result.status is DemandStatus.BLOCKED
    assert result.quantity is None
    assert result.messages_per_month == Decimal("0")
    assert "No governed flow evidence is tagged for service QUEUE" in result.blockers[0]


def test_current_bom_metric_registry_has_a_deterministic_adapter_for_every_metric() -> None:
    expected = {
        "api_gateway_call_millions",
        "di_data_processed_gb",
        "di_operator_execution_hours",
        "di_workspace_hours",
        "events",
        "functions_execution_10k_gb_s",
        "functions_invocation_millions",
        "goldengate_ocpu_hours",
        "iam_external_active_users",
        "iam_external_users",
        "iam_foundation",
        "iam_oracle_apps_premium_users",
        "iam_premium_users",
        "iam_sms",
        "iam_tokens",
        "log_analytics_active_storage_units",
        "log_analytics_archival_storage_unit_hours",
        "logging_storage_gb_months",
        "monitoring_ingestion_million_datapoints",
        "monitoring_retrieval_million_datapoints",
        "object_storage_gb_months",
        "object_storage_request_10k",
        "odi_ocpu_hours",
        "oic_peak_packs_hour",
        "process_automation",
        "queue_request_millions",
        "stream_analytics_ocpu_hours",
        "streaming_storage_gb_hours",
        "streaming_transfer_gb",
    }

    assert registered_metric_keys() == expected


@pytest.mark.parametrize("metric_key", sorted(registered_metric_keys()))
def test_every_registered_metric_reaches_an_explainable_terminal_state(
    metric_key: str,
) -> None:
    """A governed metric must resolve or request evidence, never lack an adapter."""

    service_by_metric = {
        "api_gateway_call_millions": "API_GATEWAY",
        "di_data_processed_gb": "DATA_INTEGRATION",
        "di_operator_execution_hours": "DATA_INTEGRATION",
        "di_workspace_hours": "DATA_INTEGRATION",
        "events": "EVENTS",
        "functions_execution_10k_gb_s": "FUNCTIONS",
        "functions_invocation_millions": "FUNCTIONS",
        "goldengate_ocpu_hours": "GOLDENGATE",
        "iam_external_active_users": "IAM",
        "iam_external_users": "IAM",
        "iam_foundation": "IAM",
        "iam_oracle_apps_premium_users": "IAM",
        "iam_premium_users": "IAM",
        "iam_sms": "IAM",
        "iam_tokens": "IAM",
        "log_analytics_active_storage_units": "OBSERVABILITY",
        "log_analytics_archival_storage_unit_hours": "OBSERVABILITY",
        "logging_storage_gb_months": "OBSERVABILITY",
        "monitoring_ingestion_million_datapoints": "OBSERVABILITY",
        "monitoring_retrieval_million_datapoints": "OBSERVABILITY",
        "object_storage_gb_months": "OBJECT_STORAGE",
        "object_storage_request_10k": "OBJECT_STORAGE",
        "odi_ocpu_hours": "DATA_INTEGRATOR",
        "oic_peak_packs_hour": "OIC3",
        "process_automation": "PROCESS_AUTOMATION",
        "queue_request_millions": "QUEUE",
        "stream_analytics_ocpu_hours": "STREAM_ANALYTICS",
        "streaming_storage_gb_hours": "STREAMING",
        "streaming_transfer_gb": "STREAMING",
    }
    service_id = service_by_metric[metric_key]
    result = resolve_service_demand(
        _context(
            metric_key,
            service_id,
            "32",
            config={
                metric_key: 1,
                "memory_gb": 1,
                "duration_seconds": 1,
                "retention_days": 1,
            },
            selected_service_ids=frozenset({service_id}),
        )
    )

    assert result.adapter != "missing"
    assert result.status in {
        DemandStatus.RESOLVED,
        DemandStatus.EXPLICIT_INPUT_REQUIRED,
    }
    assert not any(
        "not implemented" in blocker or "No deterministic demand adapter" in blocker
        for blocker in result.blockers
    )
