/* Shared presentation helpers for the integration topology workspace. */

import type { GraphEdge, GraphNode } from "@/lib/types";

export type TopologyDomainId =
  | "finance"
  | "data-platform"
  | "human-capital"
  | "identity"
  | "logistics"
  | "marketplace"
  | "retail"
  | "supply-chain"
  | "shared";

export type TopologyLayoutMode = "cluster" | "flow";

export type TopologyMetricMode = "relationships" | "executions" | "payload";

export type TopologyVisibilityMode = "priority" | "all";

export type TopologyDomain = {
  id: TopologyDomainId;
  label: string;
  shortLabel: string;
  color: string;
  softColor: string;
};

export type QaTotals = {
  ok: number;
  review: number;
  pending: number;
  total: number;
};

export type RiskReviewStep = {
  reviewedIds: string[];
  nextEdge: GraphEdge | null;
  complete: boolean;
};

export const BUSINESS_PROCESS_COLORS = [
  "#0f766e",
  "#2563eb",
  "#c2410c",
  "#7c3aed",
  "#be185d",
  "#ca8a04",
  "#0891b2",
  "#64748b",
];

export function businessProcessFamily(value: string): string {
  return value.split(" — ", 1)[0]?.trim() || "Unassigned";
}

export function businessProcessColor(value: string): string {
  const family = businessProcessFamily(value);
  const index = Math.abs(family.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0));
  return BUSINESS_PROCESS_COLORS[index % BUSINESS_PROCESS_COLORS.length];
}

export function edgeMetricValue(edge: GraphEdge, metric: TopologyMetricMode): number {
  if (metric === "executions") {
    return edge.total_executions_per_day;
  }
  if (metric === "payload") {
    return edge.total_payload_per_hour_kb;
  }
  return edge.integration_count;
}

export function edgeMetricCoverage(edge: GraphEdge, metric: TopologyMetricMode): number {
  if (metric === "executions") {
    return edge.executions_coverage;
  }
  if (metric === "payload") {
    return edge.payload_coverage;
  }
  return edge.integration_count;
}

export function edgeMetricLabel(metric: TopologyMetricMode): string {
  if (metric === "executions") {
    return "Executions / day";
  }
  if (metric === "payload") {
    return "Payload / hour";
  }
  return "Integration count";
}

export function edgeMetricUnit(metric: TopologyMetricMode): string {
  if (metric === "executions") {
    return "exec/day";
  }
  if (metric === "payload") {
    return "KB/hour";
  }
  return "integrations";
}

export function edgeRiskLabel(edge: GraphEdge): string {
  const review = edge.qa_statuses.REVISAR ?? 0;
  const pending = edge.qa_statuses.PENDING ?? 0;
  if (pending > 0) {
    return `${pending} pending`;
  }
  if (review > 0) {
    return `${review} need review`;
  }
  return "QA OK";
}

export function advanceRiskReview(
  rankedRiskEdges: GraphEdge[],
  reviewedEdgeIds: string[],
  currentEdgeId: string | null,
): RiskReviewStep {
  const reviewed = new Set(reviewedEdgeIds);
  if (currentEdgeId && rankedRiskEdges.some((edge) => edge.id === currentEdgeId)) {
    reviewed.add(currentEdgeId);
  }
  const nextEdge = rankedRiskEdges.find((edge) => !reviewed.has(edge.id)) ?? null;
  return {
    reviewedIds: Array.from(reviewed),
    nextEdge,
    complete: rankedRiskEdges.length > 0 && !nextEdge,
  };
}

export const TOPOLOGY_DOMAINS: Record<TopologyDomainId, TopologyDomain> = {
  finance: {
    id: "finance",
    label: "Finance",
    shortLabel: "FINANCE",
    color: "#2563eb",
    softColor: "#dbeafe",
  },
  "data-platform": {
    id: "data-platform",
    label: "Data Platform",
    shortLabel: "DATA PLATFORM",
    color: "#059669",
    softColor: "#d1fae5",
  },
  "human-capital": {
    id: "human-capital",
    label: "Human Capital",
    shortLabel: "HUMAN CAPITAL",
    color: "#7c3aed",
    softColor: "#ede9fe",
  },
  identity: {
    id: "identity",
    label: "Identity",
    shortLabel: "IDENTITY",
    color: "#0891b2",
    softColor: "#cffafe",
  },
  logistics: {
    id: "logistics",
    label: "Logistics",
    shortLabel: "LOGISTICS",
    color: "#0f766e",
    softColor: "#ccfbf1",
  },
  marketplace: {
    id: "marketplace",
    label: "Marketplace",
    shortLabel: "MARKETPLACE",
    color: "#c2410c",
    softColor: "#ffedd5",
  },
  retail: {
    id: "retail",
    label: "Retail",
    shortLabel: "RETAIL",
    color: "#be185d",
    softColor: "#fce7f3",
  },
  "supply-chain": {
    id: "supply-chain",
    label: "Supply Chain",
    shortLabel: "SUPPLY CHAIN",
    color: "#ca8a04",
    softColor: "#fef3c7",
  },
  shared: {
    id: "shared",
    label: "Shared Services",
    shortLabel: "SHARED",
    color: "#64748b",
    softColor: "#e2e8f0",
  },
};

export const TOPOLOGY_DOMAIN_ORDER: TopologyDomainId[] = [
  "finance",
  "human-capital",
  "marketplace",
  "identity",
  "data-platform",
  "retail",
  "logistics",
  "supply-chain",
  "shared",
];

function includesAny(value: string, terms: string[]): boolean {
  return terms.some((term) => value.includes(term));
}

export function topologyDomainForNode(node: Pick<GraphNode, "label" | "business_processes">): TopologyDomain {
  const label = node.label.toLowerCase();
  const processText = node.business_processes.join(" ").toLowerCase();
  const combined = `${label} ${processText}`;

  if (label.startsWith("finance ")) {
    return TOPOLOGY_DOMAINS.finance;
  }
  if (label.startsWith("data platform ")) {
    return TOPOLOGY_DOMAINS["data-platform"];
  }
  if (label.startsWith("human capital ")) {
    return TOPOLOGY_DOMAINS["human-capital"];
  }
  if (label.startsWith("identity ")) {
    return TOPOLOGY_DOMAINS.identity;
  }
  if (label.startsWith("logistics ")) {
    return TOPOLOGY_DOMAINS.logistics;
  }
  if (label.startsWith("marketplace ")) {
    return TOPOLOGY_DOMAINS.marketplace;
  }
  if (label.startsWith("retail ")) {
    return TOPOLOGY_DOMAINS.retail;
  }
  if (label.startsWith("supply chain ")) {
    return TOPOLOGY_DOMAINS["supply-chain"];
  }

  if (includesAny(label, ["data platform", "analytics lake", "warehouse", "data lake"])) {
    return TOPOLOGY_DOMAINS["data-platform"];
  }
  if (includesAny(label, ["supply chain", "inventory service", "warehouse system"])) {
    return TOPOLOGY_DOMAINS["supply-chain"];
  }
  if (includesAny(label, ["human capital", "payroll", "workforce", "hcm"])) {
    return TOPOLOGY_DOMAINS["human-capital"];
  }
  if (includesAny(label, ["identity", "access", "iam"])) {
    return TOPOLOGY_DOMAINS.identity;
  }
  if (includesAny(label, ["marketplace", "partner gateway"])) {
    return TOPOLOGY_DOMAINS.marketplace;
  }
  if (includesAny(label, ["retail", "store", "pos"])) {
    return TOPOLOGY_DOMAINS.retail;
  }
  if (includesAny(label, ["logistics", "carrier", "transport"])) {
    return TOPOLOGY_DOMAINS.logistics;
  }
  if (includesAny(label, ["finance", "billing", "erp", "ledger"])) {
    return TOPOLOGY_DOMAINS.finance;
  }

  if (combined.includes("data platform")) {
    return TOPOLOGY_DOMAINS["data-platform"];
  }
  if (combined.includes("supply chain")) {
    return TOPOLOGY_DOMAINS["supply-chain"];
  }
  if (combined.includes("human capital")) {
    return TOPOLOGY_DOMAINS["human-capital"];
  }
  if (combined.includes("identity")) {
    return TOPOLOGY_DOMAINS.identity;
  }
  if (combined.includes("marketplace")) {
    return TOPOLOGY_DOMAINS.marketplace;
  }
  if (combined.includes("retail")) {
    return TOPOLOGY_DOMAINS.retail;
  }
  if (combined.includes("logistics")) {
    return TOPOLOGY_DOMAINS.logistics;
  }
  if (combined.includes("finance")) {
    return TOPOLOGY_DOMAINS.finance;
  }

  return TOPOLOGY_DOMAINS.shared;
}

export function qaTotalsForEdges(edges: GraphEdge[]): QaTotals {
  return edges.reduce<QaTotals>(
    (totals, edge) => {
      const ok = edge.qa_statuses.OK ?? 0;
      const review = edge.qa_statuses.REVISAR ?? 0;
      const pending = edge.qa_statuses.PENDING ?? 0;
      return {
        ok: totals.ok + ok,
        review: totals.review + review,
        pending: totals.pending + pending,
        total: totals.total + ok + review + pending,
      };
    },
    { ok: 0, review: 0, pending: 0, total: 0 },
  );
}

export function qaTotalsForNode(node: GraphNode, edges: GraphEdge[]): QaTotals {
  return qaTotalsForEdges(edges.filter((edge) => edge.source === node.id || edge.target === node.id));
}

export function degradedSystemCount(nodes: GraphNode[], edges: GraphEdge[]): number {
  return nodes.filter((node) => {
    const totals = qaTotalsForNode(node, edges);
    return totals.review + totals.pending > 0;
  }).length;
}

export function topPatternsForEdges(edges: GraphEdge[], limit: number): Array<{ pattern: string; count: number }> {
  const counts = new Map<string, number>();
  edges.forEach((edge) => {
    edge.patterns.forEach((pattern) => {
      counts.set(pattern, (counts.get(pattern) ?? 0) + edge.integration_count);
    });
  });
  return [...counts.entries()]
    .map(([pattern, count]) => ({ pattern, count }))
    .sort((left, right) => right.count - left.count || left.pattern.localeCompare(right.pattern))
    .slice(0, limit);
}
