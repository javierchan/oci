import type { AuditEvent, BomSnapshot, DashboardSnapshot, GraphEdge, VolumetrySnapshotSummary } from "@/lib/types";

export type AttentionPriority = "critical" | "high" | "medium" | "low";

export type AttentionItem = {
  id: string;
  priority: AttentionPriority;
  title: string;
  detail: string;
  href: string;
  source: "qa" | "topology" | "coverage" | "bom";
};

export type DecisionBrief = {
  status: "blocked" | "needs_review" | "ready_with_caveats" | "ready";
  headline: string;
  recommendation: string;
  confidence: string;
  primaryAction: { label: string; href: string };
  evidence: Array<{ label: string; value: string }>;
};

export type ChangeSummary = {
  title: string;
  detail: string;
  tone: "positive" | "neutral" | "attention";
};

export type AdoptionMetric = {
  label: string;
  value: string;
  detail: string;
};

function catalogHref(projectId: string, status: "PENDING" | "REVISAR"): string {
  return `/projects/${projectId}/catalog?qa_status=${status}`;
}

function priorityForRisk(count: number): AttentionPriority {
  return count >= 20 ? "critical" : count >= 5 ? "high" : "medium";
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function deriveProjectAttention(
  projectId: string,
  dashboard: DashboardSnapshot | null,
  graph: { edges: GraphEdge[] } | null,
  bom: BomSnapshot | null,
): AttentionItem[] {
  const items: AttentionItem[] = [];
  const completeness = dashboard?.charts.completeness;
  const pending = completeness?.qa_pending ?? 0;
  const review = completeness?.qa_revisar ?? 0;

  if (pending > 0) {
    items.push({
      id: "qa-pending",
      priority: "critical",
      title: `${pending} integration${pending === 1 ? " is" : "s are"} missing required evidence`,
      detail: "Sizing and approval confidence remain limited until required capture fields are completed.",
      href: catalogHref(projectId, "PENDING"),
      source: "qa",
    });
  }
  if (review > 0) {
    items.push({
      id: "qa-review",
      priority: review >= 20 ? "critical" : "high",
      title: `${review} integration${review === 1 ? " needs" : "s need"} architect review`,
      detail: "Resolve governed QA decisions before treating the technical baseline as sign-off ready.",
      href: catalogHref(projectId, "REVISAR"),
      source: "qa",
    });
  }

  for (const risk of dashboard?.risks.slice(0, 3) ?? []) {
    items.push({
      id: `risk-${risk.code}`,
      priority: priorityForRisk(risk.count),
      title: risk.label,
      detail: `${risk.count} affected integration${risk.count === 1 ? "" : "s"}; open the filtered catalog to inspect evidence.`,
      href: catalogHref(projectId, "REVISAR"),
      source: "qa",
    });
  }

  const criticalPaths = (graph?.edges ?? [])
    .filter((edge) => edge.risk_qa_status !== "OK")
    .toSorted((left, right) => right.risk_score - left.risk_score)
    .slice(0, 3);
  for (const edge of criticalPaths) {
    items.push({
      id: `path-${edge.id}`,
      priority: edge.risk_score >= 75 ? "critical" : edge.risk_score >= 45 ? "high" : "medium",
      title: `${edge.source} → ${edge.target}`,
      detail: `Priority route: ${edge.integration_count} integrations · risk score ${Math.round(edge.risk_score)}.`,
      href: `/projects/${projectId}/map?path=${encodeURIComponent(edge.id)}`,
      source: "topology",
    });
  }

  const payloadCoverage = dashboard?.charts.coverage.payload;
  if (payloadCoverage && payloadCoverage.total > 0 && payloadCoverage.ratio < 0.6) {
    items.push({
      id: "payload-coverage",
      priority: payloadCoverage.ratio < 0.25 ? "critical" : "high",
      title: `Payload evidence is only ${percent(payloadCoverage.ratio)} complete`,
      detail: "Technical estimates remain directional until payload evidence is improved.",
      href: `/projects/${projectId}/catalog`,
      source: "coverage",
    });
  }

  if (bom && bom.publication_status !== "published") {
    items.push({
      id: "bom-review",
      priority: bom.coverage_pct >= 100 ? "medium" : "high",
      title: "Commercial baseline needs governed review",
      detail: `${Math.round(bom.coverage_pct)}% BOM coverage · publication status: ${bom.publication_status.replaceAll("_", " ")}.`,
      href: `/projects/${projectId}/bom`,
      source: "bom",
    });
  }

  const rank: Record<AttentionPriority, number> = { critical: 0, high: 1, medium: 2, low: 3 };
  return items.toSorted((left, right) => rank[left.priority] - rank[right.priority]).slice(0, 8);
}

export function deriveDecisionBrief(
  projectId: string,
  dashboard: DashboardSnapshot | null,
  latestSnapshot: VolumetrySnapshotSummary | undefined,
  attention: AttentionItem[],
): DecisionBrief {
  const pending = dashboard?.charts.completeness.qa_pending ?? 0;
  const review = dashboard?.charts.completeness.qa_revisar ?? 0;
  const payloadCoverage = dashboard?.charts.coverage.payload.ratio ?? 0;
  const hasSizing = Boolean(latestSnapshot);
  const highPriority = attention.filter((item) => item.priority === "critical" || item.priority === "high");

  if (!hasSizing) {
    return {
      status: "blocked",
      headline: "Technical decision is blocked until a baseline is calculated",
      recommendation: "Complete governed capture and create the first immutable technical snapshot.",
      confidence: "No technical snapshot",
      primaryAction: { label: "Calculate baseline", href: `/projects/${projectId}` },
      evidence: [
        { label: "Catalog QA", value: `${review} review · ${pending} pending` },
        { label: "Payload evidence", value: percent(payloadCoverage) },
      ],
    };
  }
  if (pending > 0 || highPriority.length > 0) {
    return {
      status: "needs_review",
      headline: "The baseline is available, but material decisions remain",
      recommendation: "Resolve the highest-priority governed evidence before presenting this project for approval.",
      confidence: dashboard?.charts.forecast_confidence.title ?? "Evidence review required",
      primaryAction: { label: "Open attention center", href: "#attention-center" },
      evidence: [
        { label: "Catalog QA", value: `${review} review · ${pending} pending` },
        { label: "Priority items", value: String(highPriority.length) },
        { label: "Payload evidence", value: percent(payloadCoverage) },
      ],
    };
  }
  return {
    status: review > 0 ? "ready_with_caveats" : "ready",
    headline: review > 0 ? "Technical baseline is ready with documented caveats" : "Technical baseline is ready for the next governed decision",
    recommendation: review > 0
      ? "Review the remaining caveats with the architecture owner, then compare deployment scenarios before approval."
      : "Investigate the critical topology paths and compare deployment scenarios before approval.",
    confidence: dashboard?.charts.forecast_confidence.title ?? "Technical evidence available",
    primaryAction: { label: "Open decision workspace", href: `/projects/${projectId}/bom` },
    evidence: [
      { label: "Catalog QA", value: `${dashboard?.charts.completeness.qa_ok ?? 0} OK` },
      { label: "Payload evidence", value: percent(payloadCoverage) },
      { label: "Snapshot", value: new Date(latestSnapshot?.created_at ?? "").toLocaleDateString("en-US") },
    ],
  };
}

export function deriveChangeSummary(
  current: VolumetrySnapshotSummary | undefined,
  previous: VolumetrySnapshotSummary | undefined,
  currentDashboard: DashboardSnapshot | null,
  previousDashboard: DashboardSnapshot | null,
  audit: AuditEvent[],
): ChangeSummary[] {
  const changes: ChangeSummary[] = [];
  if (current && previous) {
    const currentOic = current.consolidated.oic.total_billing_msgs_month;
    const previousOic = previous.consolidated.oic.total_billing_msgs_month;
    const delta = previousOic === 0 ? 0 : ((currentOic - previousOic) / previousOic) * 100;
    changes.push({
      title: "Technical demand",
      detail: `${delta === 0 ? "No" : `${delta > 0 ? "+" : ""}${Math.round(delta)}%`} OIC billing-message change since the prior snapshot.`,
      tone: Math.abs(delta) >= 10 ? "attention" : "neutral",
    });
  }
  if (currentDashboard && previousDashboard) {
    const qaNow = currentDashboard.charts.completeness.qa_ok;
    const qaBefore = previousDashboard.charts.completeness.qa_ok;
    const delta = qaNow - qaBefore;
    changes.push({
      title: "QA readiness",
      detail: `${delta === 0 ? "No change" : `${delta > 0 ? "+" : ""}${delta} QA-ready integrations`} since the prior dashboard snapshot.`,
      tone: delta > 0 ? "positive" : delta < 0 ? "attention" : "neutral",
    });
  }
  if (audit.length > 0) {
    changes.push({
      title: "Recent governed activity",
      detail: `${audit.length} audited change${audit.length === 1 ? "" : "s"} in the most recent project activity window.`,
      tone: "neutral",
    });
  }
  return changes;
}

export function deriveAdoptionMetrics(events: AuditEvent[], total: number, catalogCount: number): AdoptionMetric[] {
  const uniqueActors = new Set(events.map((event) => event.actor_id)).size;
  const approvals = events.filter((event) => /approve|accept|publish/i.test(event.event_type)).length;
  const catalogMutations = events.filter((event) => event.entity_type === "catalog_integration").length;
  return [
    { label: "Audited activity", value: String(total), detail: "Project events retained in the governed audit trail." },
    { label: "Recent contributors", value: String(uniqueActors), detail: "Distinct actors in the latest audited activity window." },
    { label: "Decision evidence", value: String(approvals), detail: "Recent approval or recommendation-acceptance events." },
    { label: "Catalog changes", value: `${catalogMutations}/${catalogCount}`, detail: "Recent governed integration changes; this is not a productivity estimate." },
  ];
}
