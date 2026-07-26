import { describe, expect, it } from "vitest";

import {
  CANVAS_HEIGHT,
  SYSTEM_NODE_HEIGHT,
  SYSTEM_NODE_WIDTH,
  TOOL_NODE_HEIGHT,
  TOOL_NODE_WIDTH,
  arrangeCanvasNodes,
} from "../lib/canvas-layout";
import {
  DESTINATION_NODE_ID,
  SOURCE_NODE_ID,
  type CanvasEdge,
  type CanvasNode,
} from "../lib/canvas-governance";

function node(instanceId: string, toolKey: string, x: number): CanvasNode {
  return {
    instanceId,
    toolKey,
    label: toolKey,
    payloadNote: "",
    x,
    y: 120,
  };
}

function edge(edgeId: string, sourceInstanceId: string, targetInstanceId: string): CanvasEdge {
  return { edgeId, sourceInstanceId, targetInstanceId, label: "" };
}

describe("integration canvas layout", () => {
  it("uses one collapsed geometry for systems and DIS components", () => {
    expect(SYSTEM_NODE_WIDTH).toBe(TOOL_NODE_WIDTH);
    expect(SYSTEM_NODE_HEIGHT).toBe(TOOL_NODE_HEIGHT);
  });

  it("keeps contextual overlays clear of the source-system column", () => {
    const arranged = arrangeCanvasNodes(
      [
        node("catalog", "OCI Data Catalog", 600),
        node("gateway", "OCI API Gateway", 860),
        node("stream", "OCI Streaming", 380),
        node("oic", "OIC Gen3", 560),
      ],
      [
        edge("e1", SOURCE_NODE_ID, "stream"),
        edge("e2", "stream", "oic"),
        edge("e3", "oic", DESTINATION_NODE_ID),
      ],
      1200,
    );

    const catalog = arranged.find((item) => item.instanceId === "catalog");
    const gateway = arranged.find((item) => item.instanceId === "gateway");
    const stream = arranged.find((item) => item.instanceId === "stream");

    expect(catalog).toMatchObject({ x: 344, y: 28 });
    expect(gateway).toMatchObject({ x: 648, y: 28 });
    expect(stream).toMatchObject({
      x: 344,
      y: CANVAS_HEIGHT / 2 - TOOL_NODE_HEIGHT / 2,
    });
    expect(catalog?.x).toBeGreaterThanOrEqual(40 + SYSTEM_NODE_WIDTH + 40);
  });
});
