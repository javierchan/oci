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
  resolveCanvasServiceId,
  type CanvasInteroperabilityArgs,
} from "./canvas-interoperability";
import type { CanvasServiceProfile } from "./types";

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
): CanvasServiceProfile {
  const limitDefinitions = Object.fromEntries(
    Object.entries(limits).map(([limitKey, value]) => [
      limitKey,
      {
        id: `${serviceId}-${limitKey}`,
        limit_key: limitKey,
        label: limitKey,
        scope: "service_operation",
        limit_type: "payload",
        constraint_kind: limitKey === "billing_threshold_kb" ? "billing_granularity" : "hard_limit",
        enforcement: limitKey === "billing_threshold_kb" ? "calculate" : "block_when_applicable",
        applicability: {},
        value,
        unit: "KB",
        default_value: null,
        can_request_increase: false,
        source_url: "https://docs.oracle.com/",
        source_retrieved_at: null,
        confidence: 1,
        notes: null,
        is_active: true,
        updated_at: "2026-07-17T00:00:00Z",
      },
    ]),
  );
  return {
    id: serviceId,
    service_id: serviceId,
    name: serviceId,
    category: "ORCHESTRATION",
    sla_uptime_pct: null,
    pricing_model: null,
    limits,
    limit_definitions: limitDefinitions,
    summary: null,
    architecture_role: null,
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
    serviceProfilesById: new Map<string, CanvasServiceProfile>([
      ["OIC3", profile("OIC3", {
        billing_threshold_kb: 50,
        rest_trigger_structured_max_payload_kb: 102400,
        kafka_schema_max_payload_kb: 10240,
      })],
      ["FUNCTIONS", profile("FUNCTIONS", { max_invoke_body_kb: 6144 })],
      ["API_GATEWAY", profile("API_GATEWAY", { max_request_body_kb: 20480 })],
      ["QUEUE", profile("QUEUE", { max_message_size_kb: 256 })],
      ["STREAMING", profile("STREAMING", { max_message_size_kb: 1024 })],
    ]),
    ...overrides,
  };
}

describe("canvas-interoperability", () => {
  it("resolves normalized Service Product aliases without guessing generic families", () => {
    expect(resolveCanvasServiceId("OCI Events")).toBe("EVENTS");
    expect(resolveCanvasServiceId("Process Automation")).toBe("PROCESS_AUTOMATION");
    expect(resolveCanvasServiceId("OCI Data Catalog")).toBe("DATA_CATALOG");
    expect(resolveCanvasServiceId("OCI IAM and Security Services")).toBe("IAM");
    expect(resolveCanvasServiceId("OCI Observability")).toBe("OBSERVABILITY");
    expect(resolveCanvasServiceId("OCI AI Services")).toBe("AI_SERVICES");
    expect(resolveCanvasServiceId("OKE / Service Mesh")).toBe("OKE");
    expect(resolveCanvasServiceId("OCI Kubernetes Engine (OKE)")).toBe("OKE");
    expect(resolveCanvasServiceId("SFTP")).toBe("SFTP_TRANSFER");
    expect(resolveCanvasServiceId("SFTP File Transfer")).toBe("SFTP_TRANSFER");
  });

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

  it("treats the OIC 50 KB billing increment as pricing granularity, not a payload ceiling", () => {
    const report = evaluateCanvasInteroperability(
      makeArgs({
        payloadKb: 70,
        triggerType: "REST Trigger",
        nodes: [node("oic", "OIC Gen3")],
        edges: [
          edge("1", SOURCE_NODE_ID, "oic"),
          edge("2", "oic", DESTINATION_NODE_ID),
        ],
      }),
    );

    expect(report.blockers).toHaveLength(0);
  });

  it("applies the governed adapter-specific OIC payload boundary", () => {
    const report = evaluateCanvasInteroperability(
      makeArgs({
        payloadKb: 11 * 1024,
        sourceTechnology: "Kafka",
        nodes: [node("oic", "OIC Gen3")],
        edges: [
          edge("1", SOURCE_NODE_ID, "oic"),
          edge("2", "oic", DESTINATION_NODE_ID),
        ],
      }),
    );

    expect(report.blockers.map((finding) => finding.id)).toContain(
      "oic-payload-limit-kafka_schema_max_payload_kb",
    );
  });

  it("requests adapter evidence instead of inventing a generic OIC ceiling", () => {
    const report = evaluateCanvasInteroperability(
      makeArgs({
        payloadKb: 11 * 1024,
        nodes: [node("oic", "OIC Gen3")],
        edges: [
          edge("1", SOURCE_NODE_ID, "oic"),
          edge("2", "oic", DESTINATION_NODE_ID),
        ],
      }),
    );

    expect(report.blockers).toHaveLength(0);
    expect(report.warnings.map((finding) => finding.id)).toContain(
      "oic-adapter-context-required",
    );
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
