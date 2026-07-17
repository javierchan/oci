"""Regression tests for persisted integration-canvas interoperability."""

from __future__ import annotations

import json

from app.services.canvas_interoperability import (
    DESTINATION_NODE_ID,
    SOURCE_NODE_ID,
    CanvasSemantics,
    derive_canvas_semantics,
    parse_canvas_state,
    serialize_canvas_state,
)


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
