"""Regression tests for persisted integration-canvas interoperability."""

from __future__ import annotations

import json
from types import MappingProxyType

from app.core.calc_engine import Assumptions
from app.services.canvas_interoperability import (
    DESTINATION_NODE_ID,
    SOURCE_NODE_ID,
    CanvasEdge,
    CanvasNode,
    CanvasSemantics,
    TOOL_TO_SERVICE_ID,
    derive_canvas_semantics,
    evaluate_canvas_interoperability,
    parse_canvas_state,
    serialize_canvas_state,
)
from app.services.service_rule_service import (
    GovernedServiceLimit,
    ServiceRuleBundle,
)


def _rule_bundle() -> ServiceRuleBundle:
    definitions = {
        "billing_threshold_kb": GovernedServiceLimit(
            service_id="OIC3",
            limit_key="billing_threshold_kb",
            value=50,
            unit="KB",
            scope="billing_message",
            limit_type="payload",
            constraint_kind="billing_granularity",
            enforcement="calculate",
            applicability=MappingProxyType({"rounding": "ceiling"}),
            source_url="https://docs.oracle.com/",
            confidence=1.0,
        ),
        "rest_trigger_structured_max_payload_kb": GovernedServiceLimit(
            service_id="OIC3",
            limit_key="rest_trigger_structured_max_payload_kb",
            value=102_400,
            unit="KB",
            scope="adapter_operation",
            limit_type="payload",
            constraint_kind="hard_limit",
            enforcement="block_when_applicable",
            applicability=MappingProxyType({"adapter": "REST", "operation": "trigger"}),
            source_url="https://docs.oracle.com/",
            confidence=1.0,
        ),
        "kafka_schema_max_payload_kb": GovernedServiceLimit(
            service_id="OIC3",
            limit_key="kafka_schema_max_payload_kb",
            value=10_240,
            unit="KB",
            scope="adapter_operation",
            limit_type="payload",
            constraint_kind="hard_limit",
            enforcement="block_when_applicable",
            applicability=MappingProxyType({"adapter": "KAFKA"}),
            source_url="https://docs.oracle.com/",
            confidence=1.0,
        ),
    }
    return ServiceRuleBundle(
        version="test",
        source="normalized_service_products",
        freshness_status="current",
        limits_by_service=MappingProxyType(
            {"OIC3": MappingProxyType({key: item.value for key, item in definitions.items()})}
        ),
        definitions_by_service=MappingProxyType(
            {"OIC3": MappingProxyType(definitions)}
        ),
        relationships=(),
        stale_evidence_count=0,
        open_findings_count=0,
        last_verified_at=None,
    )


def _oic_route() -> tuple[list[CanvasNode], list[CanvasEdge]]:
    return (
        [CanvasNode("oic", "OIC Gen3", "OIC", "", 0, 0)],
        [
            CanvasEdge("1", SOURCE_NODE_ID, "oic", ""),
            CanvasEdge("2", "oic", DESTINATION_NODE_ID, ""),
        ],
    )


def test_capture_taxonomy_aliases_resolve_to_normalized_service_products() -> None:
    assert TOOL_TO_SERVICE_ID["OCI Events"] == "EVENTS"
    assert TOOL_TO_SERVICE_ID["Process Automation"] == "PROCESS_AUTOMATION"
    assert TOOL_TO_SERVICE_ID["OCI Data Catalog"] == "DATA_CATALOG"
    assert TOOL_TO_SERVICE_ID["OCI IAM and Security Services"] == "IAM"
    assert TOOL_TO_SERVICE_ID["OCI Observability"] == "OBSERVABILITY"
    assert "OCI AI Services" not in TOOL_TO_SERVICE_ID
    assert "OKE / Service Mesh" not in TOOL_TO_SERVICE_ID


def test_context_overlay_is_preserved_without_becoming_a_payload_route_step() -> None:
    payload = json.dumps(
        {
            "v": 4,
            "nodes": [
                {
                    "instanceId": "oic-1",
                    "toolKey": "OIC Gen3",
                    "label": "OIC",
                    "payloadNote": "",
                    "x": 420,
                    "y": 180,
                },
                {
                    "instanceId": "iam-1",
                    "toolKey": "OCI IAM and Security Services",
                    "label": "IAM",
                    "payloadNote": "overlay",
                    "x": 420,
                    "y": 40,
                },
            ],
            "edges": [
                {
                    "edgeId": "source-oic",
                    "sourceInstanceId": SOURCE_NODE_ID,
                    "targetInstanceId": "oic-1",
                    "label": "",
                },
                {
                    "edgeId": "oic-destination",
                    "sourceInstanceId": "oic-1",
                    "targetInstanceId": DESTINATION_NODE_ID,
                    "label": "",
                },
            ],
            "coreToolKeys": ["OIC Gen3"],
            "overlayKeys": ["OCI IAM and Security Services"],
            "endpointPositions": {},
        }
    )

    parsed = parse_canvas_state(payload, ["OIC Gen3"])
    semantics = derive_canvas_semantics(parsed.nodes, parsed.edges, parsed.overlay_keys)

    assert semantics.core_tool_keys == ("OIC Gen3",)
    assert semantics.overlay_keys == ("OCI IAM and Security Services",)
    assert semantics.has_connected_route is True


def test_v4_canvas_state_preserves_endpoint_positions() -> None:
    """Accept the web canvas contract and retain its endpoint layout on normalization."""

    payload = json.dumps(
        {
            "v": 4,
            "nodes": [
                {
                    "instanceId": "oic-1",
                    "toolKey": "OIC Gen3",
                    "label": "OIC",
                    "payloadNote": "",
                    "x": 420,
                    "y": 180,
                }
            ],
            "edges": [
                {
                    "edgeId": "source-oic",
                    "sourceInstanceId": SOURCE_NODE_ID,
                    "targetInstanceId": "oic-1",
                    "label": "",
                },
                {
                    "edgeId": "oic-destination",
                    "sourceInstanceId": "oic-1",
                    "targetInstanceId": DESTINATION_NODE_ID,
                    "label": "",
                },
            ],
            "coreToolKeys": ["OIC Gen3"],
            "overlayKeys": [],
            "endpointPositions": {
                SOURCE_NODE_ID: {"x": 60, "y": 180},
                DESTINATION_NODE_ID: {"x": 780, "y": 180},
                "unknown": {"x": 0, "y": 0},
            },
        }
    )

    parsed = parse_canvas_state(payload, ["OIC Gen3"])
    serialized = serialize_canvas_state(
        parsed.nodes,
        parsed.edges,
        CanvasSemantics(
            has_directed_route=True,
            has_connected_route=True,
            core_tool_keys=parsed.core_tool_keys,
            overlay_keys=parsed.overlay_keys,
        ),
        parsed.endpoint_positions,
    )
    normalized = json.loads(serialized)

    assert normalized["v"] == 4
    assert normalized["endpointPositions"] == {
        SOURCE_NODE_ID: {"x": 60.0, "y": 180.0},
        DESTINATION_NODE_ID: {"x": 780.0, "y": 180.0},
    }


def test_v3_canvas_state_upgrades_without_endpoint_positions() -> None:
    """Keep existing stored V3 designs readable during the V4 transition."""

    payload = json.dumps(
        {
            "v": 3,
            "nodes": [],
            "edges": [],
            "coreToolKeys": [],
            "overlayKeys": [],
        }
    )

    parsed = parse_canvas_state(payload, [])

    assert parsed.mode == "canvas_json"
    assert parsed.endpoint_positions == ()


def test_oic_billing_increment_is_not_a_payload_blocker() -> None:
    nodes, edges = _oic_route()
    report = evaluate_canvas_interoperability(
        nodes,
        edges,
        (),
        Assumptions(),
        70,
        "REST Trigger",
        True,
        "REST",
        "REST",
        "REST",
        _rule_bundle(),
    )

    assert report.blockers == ()


def test_oic_adapter_specific_payload_limit_blocks_only_matching_context() -> None:
    nodes, edges = _oic_route()
    report = evaluate_canvas_interoperability(
        nodes,
        edges,
        (),
        Assumptions(),
        11 * 1024,
        "Event Trigger",
        True,
        "Kafka",
        "Kafka",
        "Kafka",
        _rule_bundle(),
    )

    assert "oic-payload-limit-kafka_schema_max_payload_kb" in {
        finding.id for finding in report.blockers
    }


def test_oic_missing_adapter_context_warns_without_inventing_a_generic_ceiling() -> None:
    nodes, edges = _oic_route()
    report = evaluate_canvas_interoperability(
        nodes,
        edges,
        (),
        Assumptions(),
        11 * 1024,
        None,
        None,
        None,
        None,
        None,
        _rule_bundle(),
    )

    assert report.blockers == ()
    assert "oic-adapter-context-required" in {finding.id for finding in report.warnings}
