import { describe, expect, it } from "vitest";

import { arrangeCanvasNodes } from "../lib/canvas-layout";
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

    expect(catalog).toMatchObject({ x: 292, y: 28 });
    expect(gateway).toMatchObject({ x: 596, y: 28 });
    expect(stream).toMatchObject({ x: 292, y: 222 });
    expect(catalog?.x).toBeGreaterThanOrEqual(40 + 208 + 40);
  });
});
