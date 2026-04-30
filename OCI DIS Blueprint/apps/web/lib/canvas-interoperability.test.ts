/* Coverage for Oracle-backed interoperability checks in the integration design canvas. */

import { describe, expect, it } from "vitest";

import {
  DESTINATION_NODE_ID,
  SOURCE_NODE_ID,
  type CanvasEdge,
  type CanvasNode,
} from "./canvas-governance";
import {
  evaluateCanvasInteroperability,
  type CanvasInteroperabilityArgs,
} from "./canvas-interoperability";
import type { ServiceCapabilityProfile } from "./types";

function node(instanceId: string, toolKey: string, label = toolKey): CanvasNode {
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

function profile(
  serviceId: string,
  limits: Record<string, unknown>,
): ServiceCapabilityProfile {
  return {
    id: serviceId,
    service_id: serviceId,
    name: serviceId,
    category: "ORCHESTRATION",
    sla_uptime_pct: null,
    pricing_model: null,
    limits,
    architectural_fit: null,
    anti_patterns: null,
    interoperability_notes: null,
    oracle_docs_urls: null,
    is_active: true,
    version: "1.0.0",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function makeArgs(
  overrides: Partial<CanvasInteroperabilityArgs>,
): CanvasInteroperabilityArgs {
  return {
    nodes: [],
    edges: [],
    overlayToolKeys: ["OCI API Gateway"],
    payloadKb: null,
    triggerType: null,
    isRealTime: null,
    sourceTechnology: null,
    destinationTechnology: null,
    integrationType: null,
    serviceProfilesById: new Map<string, ServiceCapabilityProfile>([
      ["OIC3", profile("OIC3", { max_message_size_kb: 10240 })],
      ["FUNCTIONS", profile("FUNCTIONS", { max_invoke_body_kb: 6144 })],
      ["API_GATEWAY", profile("API_GATEWAY", { max_request_body_kb: 20480 })],
      ["QUEUE", profile("QUEUE", { max_message_size_kb: 256 })],
      ["STREAMING", profile("STREAMING", { max_message_size_kb: 1024 })],
    ]),
    ...overrides,
  };
}

describe("canvas-interoperability", () => {
  it("blocks payloads that exceed documented service limits", () => {
    const report = evaluateCanvasInteroperability(
      makeArgs({
        payloadKb: 7000,
        nodes: [node("fn", "OCI Functions")],
        edges: [
          edge("1", SOURCE_NODE_ID, "fn"),
          edge("2", "fn", DESTINATION_NODE_ID),
        ],
      }),
    );

    expect(report.blockers.map((finding) => finding.id)).toContain("functions-payload-limit");
  });

  it("blocks connector hub when it is fed directly from the external source", () => {
    const report = evaluateCanvasInteroperability(
      makeArgs({
        nodes: [
          node("hub", "OCI Connector Hub"),
          node("fn", "OCI Functions"),
        ],
        edges: [
          edge("1", SOURCE_NODE_ID, "hub"),
          edge("2", "hub", "fn"),
          edge("3", "fn", DESTINATION_NODE_ID),
        ],
      }),
    );

    expect(report.blockers.map((finding) => finding.id)).toContain("connector-hub-source-0");
  });

  it("allows a documented Queue -> Connector Hub -> Functions handoff", () => {
    const report = evaluateCanvasInteroperability(
      makeArgs({
        nodes: [
          node("queue", "OCI Queue"),
          node("hub", "OCI Connector Hub"),
          node("fn", "OCI Functions"),
        ],
        edges: [
          edge("1", SOURCE_NODE_ID, "queue"),
          edge("2", "queue", "hub"),
          edge("3", "hub", "fn"),
          edge("4", "fn", DESTINATION_NODE_ID),
        ],
      }),
    );

    expect(report.blockers.some((finding) => finding.id.startsWith("connector-hub-"))).toBe(false);
  });

  it("blocks API Gateway on SOAP-triggered routes", () => {
    const report = evaluateCanvasInteroperability(
      makeArgs({
        triggerType: "SOAP Trigger",
        nodes: [
          node("api", "OCI API Gateway"),
          node("oic", "OIC Gen3"),
        ],
        edges: [
          edge("1", SOURCE_NODE_ID, "api"),
          edge("2", "api", "oic"),
          edge("3", "oic", DESTINATION_NODE_ID),
        ],
      }),
    );

    expect(report.blockers.map((finding) => finding.id)).toContain("gateway-soap-0");
  });

  it("warns when Data Integration is used on a real-time route", () => {
    const report = evaluateCanvasInteroperability(
      makeArgs({
        isRealTime: true,
        nodes: [node("di", "OCI Data Integration")],
        edges: [
          edge("1", SOURCE_NODE_ID, "di"),
          edge("2", "di", DESTINATION_NODE_ID),
        ],
      }),
    );

    expect(report.warnings.map((finding) => finding.id)).toContain(
      "data-integration-low-latency-warning",
    );
  });

  it("advises fronting ORDS with API Gateway on REST routes", () => {
    const report = evaluateCanvasInteroperability(
      makeArgs({
        triggerType: "REST Trigger",
        nodes: [node("ords", "Oracle ORDS")],
        edges: [
          edge("1", SOURCE_NODE_ID, "ords"),
          edge("2", "ords", DESTINATION_NODE_ID),
        ],
      }),
    );

    expect(report.advisories.map((finding) => finding.id)).toContain("ords-gateway-advisory");
  });
});
