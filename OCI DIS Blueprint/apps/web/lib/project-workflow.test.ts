import { describe, expect, it } from "vitest";

import { deriveProjectWorkflowGuide } from "@/lib/project-workflow";
import type { DashboardSnapshot } from "@/lib/types";

const projectId = "project-123";

function dashboard(overrides: Partial<DashboardSnapshot["charts"]["completeness"]> = {}): DashboardSnapshot {
  return {
    snapshot_id: "dashboard-1",
    project_id: projectId,
    volumetry_snapshot_id: "snapshot-1",
    mode: "technical",
    kpi_strip: {
      oic_msgs_month: 0,
      peak_packs_hour: 0,
      di_workspace_active: false,
      di_data_processed_gb_month: 0,
      functions_execution_units_gb_s: 0,
    },
    charts: {
      coverage: { total_integrations: 0, formal_id: { complete: 0, total: 0, ratio: 0 }, pattern: { complete: 0, total: 0, ratio: 0 }, payload: { complete: 0, total: 0, ratio: 0 }, trigger: { complete: 0, total: 0, ratio: 0 }, source_destination: { complete: 0, total: 0, ratio: 0 }, fan_out: { complete: 0, total: 0, ratio: 0 } },
      completeness: { qa_ok: 0, qa_review: 0, qa_pending: 0, rationale_informed: 0, core_tools_informed: 0, comments_informed: 0, retry_policy_informed: 0, ...overrides },
      pattern_mix: [],
      payload_distribution: [],
      forecast_confidence: { level: "high", title: "High", message: "", payload_coverage_ratio: 1 },
      service_rules: { version: "v1", source: "test", freshness_status: "current", stale_evidence_count: 0, open_findings_count: 0, last_verified_at: null },
      product_footprint: { captured_product_count: 0, represented_product_count: 0, verified_product_count: 0, included_or_dependent_count: 0, external_dependency_count: 0, selection_required_count: 0, rows_with_products: 0, total_rows: 0, products: [] },
    },
    risks: [],
    maturity: { qa_ok_pct: 0, pattern_assigned_pct: 0, payload_informed_pct: 0, governed_pct: 0 },
    created_at: "2026-07-25T00:00:00Z",
  };
}

describe("deriveProjectWorkflowGuide", () => {
  it("starts an empty project with inventory creation", () => {
    const guide = deriveProjectWorkflowGuide({ projectId, catalogCount: 0, latestSnapshotId: null, dashboard: null });

    expect(guide.nextAction.label).toBe("Build the inventory");
    expect(guide.steps[0].state).toBe("current");
  });

  it("routes QA review before calculation", () => {
    const guide = deriveProjectWorkflowGuide({ projectId, catalogCount: 4, latestSnapshotId: null, dashboard: dashboard({ qa_review: 2 }) });

    expect(guide.nextAction.label).toBe("Resolve the QA queue");
    expect(guide.nextAction.href).toContain("qa_status=REVIEW");
  });

  it("routes a governed, calculated project to topology investigation", () => {
    const guide = deriveProjectWorkflowGuide({ projectId, catalogCount: 4, latestSnapshotId: "snapshot-1", dashboard: dashboard({ qa_ok: 4 }) });

    expect(guide.nextAction.label).toBe("Investigate the dependency map");
    expect(guide.steps[2].state).toBe("complete");
  });
});
