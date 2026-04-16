/* Coverage for governed canvas parsing and route semantics. */

import { describe, expect, it } from "vitest";

import {
  DESTINATION_NODE_ID,
  SOURCE_NODE_ID,
  deriveCanvasSemantics,
  parseCanvasState,
  serializeCanvasState,
  type CanvasEdge,
  type CanvasNode,
} from "./canvas-governance";
import type { CanvasCombination } from "./types";

const combinations: CanvasCombination[] = [
  {
    code: "G04",
    name: "Fan-out / desacople con cola",
    capture_standard: "OIC Gen3, OCI Queue, OCI Functions",
    supported_tool_keys: ["OIC Gen3", "OCI Queue", "OCI Functions"],
    compatible_pattern_ids: ["#02", "#08", "#17"],
    activates_metrics: ["OIC", "Queue", "Functions"],
    activates_volumetric_metrics: true,
    recommended_overlays: [],
    guidance: "Fan-out y resiliencia sin broker streaming.",
    status: "Válido",
  },
  {
    code: "G13",
    name: "Webhook distribuido",
    capture_standard: "OIC Gen3, OCI Queue, OCI Functions",
    supported_tool_keys: ["OIC Gen3", "OCI Queue", "OCI Functions"],
    compatible_pattern_ids: ["#17", "#02"],
    activates_metrics: ["OIC", "Queue", "Functions"],
    activates_volumetric_metrics: true,
    recommended_overlays: ["OCI API Gateway"],
    guidance: "Webhooks con desacople y fan-out.",
    status: "Válido",
  },
];

function node(instanceId: string, toolKey: string, label: string): CanvasNode {
  return {
    instanceId,
    toolKey,
    label,
    payloadNote: "",
    x: 0,
    y: 0,
  };
}

function edge(edgeId: string, sourceInstanceId: string, targetInstanceId: string): CanvasEdge {
  return {
    edgeId,
    sourceInstanceId,
    targetInstanceId,
    label: "",
  };
}

describe("canvas-governance", () => {
  it("separates core tools from overlays on the active route", () => {
    const nodes = [
      node("api", "OCI API Gateway", "API"),
      node("oic", "OIC Gen3", "OIC"),
      node("queue", "OCI Queue", "Queue"),
      node("fn", "OCI Functions", "Fn"),
    ];
    const edges = [
      edge("1", SOURCE_NODE_ID, "api"),
      edge("2", "api", "oic"),
      edge("3", "oic", "queue"),
      edge("4", "queue", "fn"),
      edge("5", "fn", DESTINATION_NODE_ID),
    ];

    const semantics = deriveCanvasSemantics({
      nodes,
      edges,
      overlayToolKeys: ["OCI API Gateway"],
      combinations,
      selectedPattern: null,
    });

    expect(semantics.hasConnectedRoute).toBe(true);
    expect(semantics.coreToolKeys).toEqual(["OCI Functions", "OCI Queue", "OIC Gen3"]);
    expect(semantics.overlayKeys).toEqual(["OCI API Gateway"]);
    expect(semantics.processingRouteLabels).toEqual(["OIC -> Queue -> Fn"]);
  });

  it("rejects overlays-only routes and ignores disconnected islands", () => {
    const nodes = [
      node("api", "OCI API Gateway", "API"),
      node("island", "OCI Queue", "Isolated Queue"),
    ];
    const edges = [
      edge("1", SOURCE_NODE_ID, "api"),
      edge("2", "api", DESTINATION_NODE_ID),
    ];

    const semantics = deriveCanvasSemantics({
      nodes,
      edges,
      overlayToolKeys: ["OCI API Gateway"],
      combinations,
      selectedPattern: null,
    });

    expect(semantics.hasDirectedRoute).toBe(true);
    expect(semantics.hasConnectedRoute).toBe(false);
    expect(semantics.coreToolKeys).toEqual([]);
    expect(semantics.disconnectedNodeIds).toEqual(["island"]);
  });

  it("round-trips v3 canvas state with persisted overlay metadata", () => {
    const nodes = [node("oic", "OIC Gen3", "OIC"), node("queue", "OCI Queue", "Queue")];
    const edges = [
      edge("1", SOURCE_NODE_ID, "oic"),
      edge("2", "oic", "queue"),
      edge("3", "queue", DESTINATION_NODE_ID),
    ];
    const serialized = serializeCanvasState(nodes, edges, {
      coreToolKeys: ["OIC Gen3", "OCI Queue"],
      overlayKeys: ["OCI API Gateway"],
    });

    const parsed = parseCanvasState(serialized, []);

    expect(parsed.coreToolKeys).toEqual(["OCI Queue", "OIC Gen3"]);
    expect(parsed.overlayKeys).toEqual(["OCI API Gateway"]);
    expect(parsed.edges).toHaveLength(3);
  });

  it("surfaces governed combination suggestions from the active stack", () => {
    const nodes = [
      node("api", "OCI API Gateway", "API"),
      node("oic", "OIC Gen3", "OIC"),
      node("queue", "OCI Queue", "Queue"),
      node("fn", "OCI Functions", "Fn"),
    ];
    const edges = [
      edge("1", SOURCE_NODE_ID, "api"),
      edge("2", "api", "oic"),
      edge("3", "oic", "queue"),
      edge("4", "queue", "fn"),
      edge("5", "fn", DESTINATION_NODE_ID),
    ];

    const semantics = deriveCanvasSemantics({
      nodes,
      edges,
      overlayToolKeys: ["OCI API Gateway"],
      combinations,
      selectedPattern: "#17",
    });

    expect(semantics.matchedCombinations[0]?.combination.code).toBe("G13");
    expect(semantics.suggestedPatternIds).toContain("#17");
    expect(semantics.suggestedPatternIds).toContain("#02");
  });
});
