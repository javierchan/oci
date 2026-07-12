/* Unit coverage for topology metric, process, and risk presentation helpers. */

import { describe, expect, it } from "vitest";

import {
  advanceRiskReview,
  businessProcessFamily,
  edgeMetricCoverage,
  edgeMetricLabel,
  edgeMetricValue,
  edgeRiskLabel,
} from "./topology";
import type { GraphEdge } from "./types";

const EDGE: GraphEdge = {
  id: "source__target",
  source: "Source",
  target: "Target",
  integration_count: 3,
  integration_ids: ["1", "2", "3"],
  integration_names: ["One", "Two", "Three"],
  integration_qa_statuses: ["OK", "REVISAR", "REVISAR"],
  business_processes: ["Order to Cash — Retail to Finance"],
  patterns: ["#01 · Request-Reply"],
  qa_statuses: { OK: 1, REVISAR: 2 },
  dominant_qa_status: "REVISAR",
  risk_qa_status: "REVISAR",
  risk_score: 23,
  interaction_mode: "SYNCHRONOUS",
  total_executions_per_day: 360,
  total_payload_per_hour_kb: 1920,
  executions_coverage: 3,
  payload_coverage: 2,
  last_updated_at: "2026-07-11T12:00:00Z",
  integrations: [],
};

describe("topology helpers", () => {
  it("extracts a stable business process family", () => {
    expect(businessProcessFamily("Order to Cash — Retail to Finance")).toBe("Order to Cash");
    expect(businessProcessFamily("Inventory Synchronization")).toBe("Inventory Synchronization");
  });

  it("selects the requested governed edge metric and coverage", () => {
    expect(edgeMetricValue(EDGE, "relationships")).toBe(3);
    expect(edgeMetricValue(EDGE, "executions")).toBe(360);
    expect(edgeMetricValue(EDGE, "payload")).toBe(1920);
    expect(edgeMetricCoverage(EDGE, "payload")).toBe(2);
    expect(edgeMetricLabel("relationships")).toBe("Integration count");
  });

  it("describes the actionable risk carried by an edge", () => {
    expect(edgeRiskLabel(EDGE)).toBe("2 need review");
    expect(edgeRiskLabel({ ...EDGE, qa_statuses: { PENDING: 1, REVISAR: 2 } })).toBe("1 pending");
  });

  it("advances through risk review without mutating governed QA", () => {
    const secondEdge = { ...EDGE, id: "second", source: "Second source" };
    const initial = advanceRiskReview([EDGE, secondEdge], [], null);
    expect(initial.nextEdge?.id).toBe(EDGE.id);
    expect(initial.reviewedIds).toEqual([]);

    const advanced = advanceRiskReview([EDGE, secondEdge], [], EDGE.id);
    expect(advanced.reviewedIds).toEqual([EDGE.id]);
    expect(advanced.nextEdge?.id).toBe("second");
    expect(advanced.complete).toBe(false);

    const complete = advanceRiskReview([EDGE, secondEdge], [EDGE.id], "second");
    expect(complete.nextEdge).toBeNull();
    expect(complete.complete).toBe(true);
    expect(EDGE.risk_qa_status).toBe("REVISAR");
  });
});
