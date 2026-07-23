import { describe, expect, it } from "vitest";

import { buildTopologyPulseInsights } from "./topology-insights";
import type { GraphEdge, GraphIntegrationSummary, GraphResponse } from "./types";

function integration(
  id: string,
  qaStatus: string,
  payloadPerExecutionKb: number | null,
  payloadPerHourKb: number | null,
): GraphIntegrationSummary {
  return {
    id,
    name: `Integration ${id}`,
    qa_status: qaStatus,
    owner: null,
    pattern: "#01 · Request-Reply",
    trigger_type: "REST",
    interaction_mode: "SYNCHRONOUS",
    executions_per_day: payloadPerExecutionKb === null ? null : 24,
    payload_per_execution_kb: payloadPerExecutionKb,
    payload_per_hour_kb: payloadPerHourKb,
    updated_at: "2026-07-22T12:00:00Z",
  };
}

function edge(
  id: string,
  source: string,
  target: string,
  integrations: GraphIntegrationSummary[],
): GraphEdge {
  const coveredExecution = integrations.filter((item) => item.payload_per_execution_kb !== null);
  const coveredHour = integrations.filter((item) => item.payload_per_hour_kb !== null);
  return {
    id,
    source,
    target,
    integration_count: integrations.length,
    integration_ids: integrations.map((item) => item.id),
    integration_names: integrations.map((item) => item.name),
    integration_qa_statuses: integrations.map((item) => item.qa_status),
    business_processes: ["Order to Cash"],
    patterns: ["#01 · Request-Reply"],
    qa_statuses: {
      OK: integrations.filter((item) => item.qa_status === "OK").length,
      REVISAR: integrations.filter((item) => item.qa_status === "REVISAR").length,
      PENDING: integrations.filter((item) => item.qa_status === "PENDING").length,
    },
    dominant_qa_status: integrations.some((item) => item.qa_status === "REVISAR") ? "REVISAR" : "OK",
    risk_qa_status: integrations.some((item) => item.qa_status === "REVISAR") ? "REVISAR" : "OK",
    risk_score: 1,
    interaction_mode: "SYNCHRONOUS",
    total_executions_per_day: sum(integrations.map((item) => item.executions_per_day)),
    total_payload_per_execution_kb: sum(coveredExecution.map((item) => item.payload_per_execution_kb)),
    total_payload_per_hour_kb: sum(coveredHour.map((item) => item.payload_per_hour_kb)),
    executions_coverage: integrations.filter((item) => item.executions_per_day !== null).length,
    payload_execution_coverage: coveredExecution.length,
    payload_coverage: coveredHour.length,
    last_updated_at: "2026-07-22T12:00:00Z",
    integrations,
  };
}

function sum(values: Array<number | null>): number {
  return values.reduce<number>((total, value) => total + (value ?? 0), 0);
}

const EDGE_ONE = edge(
  "a-b",
  "A",
  "B",
  [integration("1", "OK", 64, 1536), integration("2", "REVISAR", 128, 3072)],
);
const EDGE_TWO = edge("b-c", "B", "C", [integration("3", "PENDING", null, null)]);
const GRAPH: GraphResponse = {
  nodes: [
    { id: "A", label: "A", integration_count: 2, as_source_count: 2, as_destination_count: 0, brands: [], business_processes: [], owners: [], technologies: [] },
    { id: "B", label: "B", integration_count: 3, as_source_count: 1, as_destination_count: 2, brands: [], business_processes: [], owners: [], technologies: [] },
    { id: "C", label: "C", integration_count: 1, as_source_count: 0, as_destination_count: 1, brands: [], business_processes: [], owners: [], technologies: [] },
  ],
  edges: [EDGE_ONE, EDGE_TWO],
  meta: {
    node_count: 3,
    edge_count: 2,
    integration_count: 3,
    business_processes: [],
    business_process_families: [],
    brands: [],
    latest_updated_at: "2026-07-22T12:00:00Z",
    executions_coverage: 2,
    payload_execution_coverage: 2,
    payload_coverage: 2,
  },
};

describe("topology pulse insights", () => {
  it("aggregates the filtered graph once and preserves payload evidence coverage", () => {
    const insights = buildTopologyPulseInsights(GRAPH, { metricMode: "relationships" });

    expect(insights.scopeLabel).toBe("Filtered topology");
    expect(insights.integrationCount).toBe(3);
    expect(insights.totalPayloadPerExecutionKb).toBe(192);
    expect(insights.payloadExecutionCoverage).toBe(2);
    expect(insights.qa).toEqual({ ok: 1, review: 1, pending: 1, total: 3 });
    expect(insights.flow).toEqual({
      leftLabel: "Sources",
      leftValue: 2,
      rightLabel: "Destinations",
      rightValue: 2,
    });
    expect(insights.concentration.topSystemLabel).toBe("B");
    expect(insights.concentration.topSystemShare).toBeCloseTo(0.5);
  });

  it("scopes system flow to inbound and outbound integrations", () => {
    const insights = buildTopologyPulseInsights(GRAPH, {
      metricMode: "payload",
      selectedNodeId: "B",
    });

    expect(insights.scope).toBe("system");
    expect(insights.scopeLabel).toBe("B");
    expect(insights.flow).toEqual({
      leftLabel: "Inbound",
      leftValue: 2,
      rightLabel: "Outbound",
      rightValue: 1,
    });
    expect(insights.pathStats.max).toBe(4608);
  });

  it("can isolate one integration inside a selected path", () => {
    const insights = buildTopologyPulseInsights(GRAPH, {
      metricMode: "executions",
      selectedEdgeId: EDGE_ONE.id,
      selectedIntegrationId: "2",
    });

    expect(insights.scope).toBe("integration");
    expect(insights.scopeLabel).toBe("Integration 2");
    expect(insights.integrationCount).toBe(1);
    expect(insights.totalPayloadPerExecutionKb).toBe(128);
    expect(insights.payloadExecutionCoverage).toBe(1);
    expect(insights.totalExecutionsPerDay).toBe(24);
    expect(insights.qa).toEqual({ ok: 0, review: 1, pending: 0, total: 1 });
    expect(insights.paths).toHaveLength(1);
    expect(insights.paths[0]?.edgeId).toBe(EDGE_ONE.id);
    expect(insights.concentration.topPathShare).toBe(1);
    expect(insights.concentration.topSystemShare).toBe(0.5);
  });
});
