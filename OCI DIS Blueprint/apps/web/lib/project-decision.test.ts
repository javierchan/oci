import { describe, expect, it } from "vitest";

import { deriveDecisionBrief, deriveProjectAttention } from "./project-decision";
import type { DashboardSnapshot, GraphEdge, VolumetrySnapshotSummary } from "./types";

function dashboard(overrides: Partial<DashboardSnapshot["charts"]["completeness"]> = {}): DashboardSnapshot {
  return {
    snapshot_id: "dash-1",
    project_id: "project-1",
    volumetry_snapshot_id: "volume-1",
    mode: "technical",
    created_at: "2026-08-12T00:00:00Z",
    kpi_strip: { oic_msgs_month: 0, peak_packs_hour: 0, di_workspace_active: false, di_data_processed_gb_month: 0, functions_execution_units_gb_s: 0 },
    charts: {
      coverage: {
        total_integrations: 10,
        formal_id: { complete: 10, total: 10, ratio: 1 },
        pattern: { complete: 10, total: 10, ratio: 1 },
        payload: { complete: 8, total: 10, ratio: 0.8 },
        trigger: { complete: 10, total: 10, ratio: 1 },
        source_destination: { complete: 10, total: 10, ratio: 1 },
        fan_out: { complete: 10, total: 10, ratio: 1 },
      },
      completeness: { qa_ok: 10, qa_revisar: 0, qa_pending: 0, rationale_informed: 0, core_tools_informed: 0, comments_informed: 0, retry_policy_informed: 0, ...overrides },
      pattern_mix: [],
      payload_distribution: [],
      forecast_confidence: { level: "high", title: "High confidence", message: "", payload_coverage_ratio: 0.8 },
      service_rules: { version: "1", source: "test", freshness_status: "fresh", stale_evidence_count: 0, open_findings_count: 0, last_verified_at: null },
      product_footprint: { captured_product_count: 0, represented_product_count: 0, verified_product_count: 0, included_or_dependent_count: 0, external_dependency_count: 0, selection_required_count: 0, rows_with_products: 0, total_rows: 10, products: [] },
    },
    risks: [],
    maturity: { qa_ok_pct: 100, pattern_assigned_pct: 100, payload_informed_pct: 80, governed_pct: 100 },
  };
}

const snapshot: VolumetrySnapshotSummary = {
  snapshot_id: "volume-1", project_id: "project-1", assumption_set_version: "1", triggered_by: "test",
  consolidated: { oic: { total_billing_msgs_month: 0, peak_billing_msgs_hour: 0, peak_packs_hour: 0, row_count: 0 }, data_integration: { workspace_active: false, data_processed_gb_month: 0, row_count: 0 }, functions: { total_execution_units_gb_s: 0, total_invocations_month: 0, row_count: 0 }, streaming: { total_gb_month: 0, partition_count: 0, row_count: 0 }, queue: { row_count: 0 } },
  metadata: null, row_result_count: 0, created_at: "2026-08-12T00:00:00Z",
};

const edge: GraphEdge = {
  id: "edge-1", source: "ERP", target: "CRM", integration_count: 5, integration_ids: [], integration_names: [], integration_qa_statuses: [], business_processes: [], patterns: [], qa_statuses: {}, dominant_qa_status: "REVISAR", risk_qa_status: "REVISAR", risk_score: 80, interaction_mode: "SYNCHRONOUS", total_executions_per_day: 0, total_payload_per_execution_kb: 0, total_payload_per_hour_kb: 0, executions_coverage: 0, payload_execution_coverage: 0, payload_coverage: 0, last_updated_at: "2026-08-12T00:00:00Z", integrations: [],
};

describe("project decision helpers", () => {
  it("prioritizes missing QA evidence before topology", () => {
    const result = deriveProjectAttention("project-1", dashboard({ qa_pending: 2 }), { edges: [edge] }, null);
    expect(result[0]).toMatchObject({ id: "qa-pending", priority: "critical" });
  });

  it("uses the attention center when a calculated baseline still has material risk", () => {
    const attention = deriveProjectAttention("project-1", dashboard(), { edges: [edge] }, null);
    const brief = deriveDecisionBrief("project-1", dashboard(), snapshot, attention);
    expect(brief.status).toBe("needs_review");
    expect(brief.primaryAction.href).toBe("#attention-center");
  });

  it("reports a ready decision when the calculated evidence has no material attention", () => {
    const brief = deriveDecisionBrief("project-1", dashboard(), snapshot, []);
    expect(brief.status).toBe("ready");
    expect(brief.primaryAction.href).toContain("/bom");
  });
});
