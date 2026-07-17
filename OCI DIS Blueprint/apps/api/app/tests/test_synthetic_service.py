"""Focused coverage for deterministic synthetic dataset generation."""

from __future__ import annotations

import json

from app.core.calc_engine import composition_issues
from app.services import synthetic_service


def test_generated_synthetic_dataset_meets_scale_and_coverage_targets() -> None:
    dataset = synthetic_service.generate_synthetic_dataset(synthetic_service.DEFAULT_SYNTHETIC_SPEC)
    validation = synthetic_service.validate_synthetic_dataset(dataset)

    assert len(dataset.import_rows) == 420
    assert len(dataset.manual_rows) == 60
    assert len(dataset.excluded_rows) == 36
    assert validation.catalog_count == 480
    assert validation.distinct_systems >= 70
    assert len(validation.covered_pattern_ids) == 17
    assert validation.max_canvas_state_length < synthetic_service.SYNTHETIC_CANVAS_MAX_BYTES

    assert all(
        not composition_issues(row.selected_pattern, row.core_tools_csv, row.canvas_state)
        for row in dataset.included_rows
    )


def test_generated_smoke_dataset_meets_smoke_targets_and_full_pattern_coverage() -> None:
    dataset = synthetic_service.generate_synthetic_dataset(synthetic_service.SMOKE_SYNTHETIC_SPEC)
    validation = synthetic_service.validate_synthetic_dataset(dataset)

    assert len(dataset.import_rows) == 12
    assert len(dataset.manual_rows) == 6
    assert len(dataset.excluded_rows) == 2
    assert validation.catalog_count == 18
    assert validation.distinct_systems >= 12
    assert len(validation.covered_pattern_ids) == synthetic_service.SUPPORTED_PATTERN_COUNT
    assert validation.max_canvas_state_length < synthetic_service.SYNTHETIC_CANVAS_MAX_BYTES


def test_synthetic_queue_routes_stay_within_governed_message_limit() -> None:
    for spec in (synthetic_service.DEFAULT_SYNTHETIC_SPEC, synthetic_service.SMOKE_SYNTHETIC_SPEC):
        dataset = synthetic_service.generate_synthetic_dataset(spec)
        queue_rows = [
            row
            for row in [*dataset.import_rows, *dataset.manual_rows]
            if "OCI Queue" in row.core_tools
        ]

        assert queue_rows
        assert max(row.payload_per_execution_kb for row in queue_rows) <= synthetic_service.SYNTHETIC_QUEUE_MAX_MESSAGE_KB


def test_synthetic_streaming_routes_stay_within_governed_message_limit() -> None:
    for spec in (synthetic_service.DEFAULT_SYNTHETIC_SPEC, synthetic_service.SMOKE_SYNTHETIC_SPEC):
        dataset = synthetic_service.generate_synthetic_dataset(spec)
        streaming_rows = [
            row
            for row in [*dataset.import_rows, *dataset.manual_rows]
            if "OCI Streaming" in row.core_tools
        ]

        assert streaming_rows
        assert max(row.payload_per_execution_kb for row in streaming_rows) <= synthetic_service.SYNTHETIC_STREAMING_MAX_MESSAGE_KB


def test_canvas_state_is_compact_and_parseable_shape() -> None:
    payload = synthetic_service.build_canvas_state(
        ("OIC Gen3", "OCI Queue", "OCI Functions"),
        ("OCI API Gateway",),
        2048.0,
    )

    assert "\"v\":3" in payload
    assert "\"coreToolKeys\"" in payload
    assert "\"overlayKeys\"" in payload
    assert len(payload) < 1000


def test_canvas_state_uses_non_overlapping_route_positions() -> None:
    payload = synthetic_service.build_canvas_state(
        ("OCI Streaming", "OIC Gen3"),
        ("OCI Events",),
        54.0,
    )
    parsed = json.loads(payload)
    nodes = parsed["nodes"]

    assert [node["x"] for node in nodes] == sorted(node["x"] for node in nodes)
    assert {node["y"] for node in nodes} == {220}
    for left, right in zip(nodes, nodes[1:]):
        assert right["x"] - left["x"] >= 260


def test_canvas_state_keeps_incompatible_gateway_overlay_off_active_route() -> None:
    payload = synthetic_service.build_canvas_state(
        ("OCI Streaming", "OIC Gen3"),
        ("OCI API Gateway",),
        54.0,
    )
    parsed = json.loads(payload)
    gateway_node = next(node for node in parsed["nodes"] if node["toolKey"] == "OCI API Gateway")
    connected_node_ids = {
        node_id
        for edge in parsed["edges"]
        for node_id in (edge["sourceInstanceId"], edge["targetInstanceId"])
    }

    assert gateway_node["instanceId"] not in connected_node_ids
    assert gateway_node["payloadNote"] == "overlay"


def test_canvas_overlay_repair_preserves_route_and_adds_visible_context_nodes() -> None:
    original = synthetic_service.build_canvas_state(("OIC Gen3",), ("OCI API Gateway",), 54.0)
    repaired = synthetic_service.add_canvas_overlays(
        original,
        ("OCI API Gateway", "OCI IAM and Security Services"),
    )
    before = json.loads(original)
    after = json.loads(repaired)

    assert after["edges"] == before["edges"]
    assert after["overlayKeys"] == ["OCI API Gateway", "OCI IAM and Security Services"]
    assert any(
        node["toolKey"] == "OCI IAM and Security Services" and node["payloadNote"] == "overlay"
        for node in after["nodes"]
    )


def test_canvas_overlay_detach_preserves_the_core_payload_route() -> None:
    original = json.dumps(
        {
            "v": 3,
            "nodes": [
                {
                    "instanceId": "gateway",
                    "toolKey": "OCI API Gateway",
                    "payloadNote": "",
                    "x": 200,
                    "y": 120,
                },
                {"instanceId": "stream", "toolKey": "OCI Streaming", "payloadNote": ""},
                {"instanceId": "oic", "toolKey": "OIC Gen3", "payloadNote": ""},
            ],
            "edges": [
                {"edgeId": "e1", "sourceInstanceId": "source-system", "targetInstanceId": "gateway"},
                {"edgeId": "e2", "sourceInstanceId": "gateway", "targetInstanceId": "stream"},
                {"edgeId": "e3", "sourceInstanceId": "stream", "targetInstanceId": "oic"},
                {"edgeId": "e4", "sourceInstanceId": "oic", "targetInstanceId": "destination-system"},
            ],
            "coreToolKeys": ["OCI Streaming", "OIC Gen3"],
            "overlayKeys": ["OCI API Gateway"],
        },
        separators=(",", ":"),
    )

    repaired_value = synthetic_service.detach_canvas_overlay_from_route(
        original,
        "OCI API Gateway",
    )
    repaired = json.loads(repaired_value)
    edge_pairs = {
        (edge["sourceInstanceId"], edge["targetInstanceId"])
        for edge in repaired["edges"]
    }

    assert ("source-system", "stream") in edge_pairs
    assert not any("gateway" in pair for pair in edge_pairs)
    gateway = next(node for node in repaired["nodes"] if node["instanceId"] == "gateway")
    assert gateway["payloadNote"] == "overlay"
    assert gateway["x"] == 340
    assert gateway["y"] == 20
    assert json.loads(
        synthetic_service.detach_canvas_overlay_from_route(
            json.dumps(repaired, separators=(",", ":")),
            "OCI API Gateway",
        )
    ) == repaired
    assert (
        synthetic_service.detach_canvas_overlay_from_route(
            repaired_value,
            "OCI API Gateway",
        )
        == repaired_value
    )
