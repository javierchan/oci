/* Deterministic, presentation-ready metrics for the current topology selection. */

import { edgeMetricValue } from "@/lib/topology";
import type { TopologyMetricMode } from "@/lib/topology";
import type { GraphEdge, GraphIntegrationSummary, GraphResponse } from "@/lib/types";

export type TopologyPulseScope = "graph" | "system" | "path" | "integration";

export type TopologyPulsePath = {
  edgeId: string;
  label: string;
  value: number;
  integrationCount: number;
  payloadPerExecutionKb: number | null;
  qaStatus: string;
};

export type TopologyPulseInsights = {
  scope: TopologyPulseScope;
  scopeLabel: string;
  edges: GraphEdge[];
  paths: TopologyPulsePath[];
  integrations: GraphIntegrationSummary[];
  integrationCount: number;
  systemCount: number;
  totalExecutionsPerDay: number;
  executionsCoverage: number;
  totalPayloadPerExecutionKb: number | null;
  payloadExecutionCoverage: number;
  totalPayloadPerHourKb: number;
  payloadHourCoverage: number;
  qa: {
    ok: number;
    review: number;
    pending: number;
    total: number;
  };
  flow: {
    leftLabel: string;
    leftValue: number;
    rightLabel: string;
    rightValue: number;
  };
  pathStats: {
    p50: number;
    p95: number;
    max: number;
  };
  concentration: {
    topPathLabel: string;
    topPathShare: number;
    topSystemLabel: string;
    topSystemShare: number;
  };
};

export type BuildTopologyPulseOptions = {
  selectedNodeId?: string | null;
  selectedEdgeId?: string | null;
  selectedIntegrationId?: string | null;
  metricMode: TopologyMetricMode;
};

function percentile(values: number[], percentileValue: number): number {
  if (values.length === 0) {
    return 0;
  }
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.max(0, Math.ceil(percentileValue * sorted.length) - 1)] ?? 0;
}

function integrationMetricValue(
  integration: GraphIntegrationSummary,
  metricMode: TopologyMetricMode,
): number {
  if (metricMode === "executions") {
    return integration.executions_per_day ?? 0;
  }
  if (metricMode === "payload") {
    return integration.payload_per_hour_kb ?? 0;
  }
  return 1;
}

function qaFromIntegrations(integrations: GraphIntegrationSummary[]): TopologyPulseInsights["qa"] {
  return integrations.reduce<TopologyPulseInsights["qa"]>(
    (totals, integration) => {
      if (integration.qa_status === "OK") {
        totals.ok += 1;
      } else if (integration.qa_status === "REVISAR") {
        totals.review += 1;
      } else {
        totals.pending += 1;
      }
      totals.total += 1;
      return totals;
    },
    { ok: 0, review: 0, pending: 0, total: 0 },
  );
}

function qaFromEdges(edges: GraphEdge[]): TopologyPulseInsights["qa"] {
  return edges.reduce<TopologyPulseInsights["qa"]>(
    (totals, edge) => {
      totals.ok += edge.qa_statuses.OK ?? 0;
      totals.review += edge.qa_statuses.REVISAR ?? 0;
      totals.pending += edge.qa_statuses.PENDING ?? 0;
      totals.total += edge.integration_count;
      return totals;
    },
    { ok: 0, review: 0, pending: 0, total: 0 },
  );
}

function edgeLabel(edge: GraphEdge): string {
  return `${edge.source} → ${edge.target}`;
}

export function buildTopologyPulseInsights(
  graph: GraphResponse,
  options: BuildTopologyPulseOptions,
): TopologyPulseInsights {
  const selectedEdge = options.selectedEdgeId
    ? graph.edges.find((edge) => edge.id === options.selectedEdgeId) ?? null
    : null;
  const selectedNode = options.selectedNodeId
    ? graph.nodes.find((node) => node.id === options.selectedNodeId) ?? null
    : null;

  let edges = selectedEdge
    ? [selectedEdge]
    : selectedNode
      ? graph.edges.filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id)
      : graph.edges;

  let selectedIntegration: GraphIntegrationSummary | null = null;
  if (selectedEdge && options.selectedIntegrationId) {
    selectedIntegration = selectedEdge.integrations.find(
      (integration) => integration.id === options.selectedIntegrationId,
    ) ?? null;
  }

  if (selectedIntegration && selectedEdge) {
    edges = [selectedEdge];
  }

  const integrations = selectedIntegration
    ? [selectedIntegration]
    : edges.flatMap((edge) => edge.integrations);
  const hasCompleteIntegrationDetails = edges.every(
    (edge) => edge.integrations.length === edge.integration_count,
  );
  const integrationCount = selectedIntegration
    ? 1
    : edges.reduce((total, edge) => total + edge.integration_count, 0);
  const systems = new Set(edges.flatMap((edge) => [edge.source, edge.target]));

  const totalExecutionsPerDay = selectedIntegration
    ? selectedIntegration.executions_per_day ?? 0
    : edges.reduce((total, edge) => total + edge.total_executions_per_day, 0);
  const executionsCoverage = selectedIntegration
    ? Number(selectedIntegration.executions_per_day !== null)
    : edges.reduce((total, edge) => total + edge.executions_coverage, 0);
  const payloadExecutionCoverage = selectedIntegration
    ? Number(selectedIntegration.payload_per_execution_kb !== null)
    : edges.reduce((total, edge) => total + edge.payload_execution_coverage, 0);
  const totalPayloadPerExecutionKb = payloadExecutionCoverage > 0
    ? selectedIntegration
      ? selectedIntegration.payload_per_execution_kb
      : edges.reduce((total, edge) => total + edge.total_payload_per_execution_kb, 0)
    : null;
  const totalPayloadPerHourKb = selectedIntegration
    ? selectedIntegration.payload_per_hour_kb ?? 0
    : edges.reduce((total, edge) => total + edge.total_payload_per_hour_kb, 0);
  const payloadHourCoverage = selectedIntegration
    ? Number(selectedIntegration.payload_per_hour_kb !== null)
    : edges.reduce((total, edge) => total + edge.payload_coverage, 0);

  const paths = edges
    .map<TopologyPulsePath>((edge) => {
      const pathIntegration = selectedIntegration && edge.id === selectedEdge?.id
        ? selectedIntegration
        : null;
      const edgePayloadExecutionCoverage = pathIntegration
        ? Number(pathIntegration.payload_per_execution_kb !== null)
        : edge.payload_execution_coverage;
      return {
        edgeId: edge.id,
        label: pathIntegration?.name ?? edgeLabel(edge),
        value: pathIntegration
          ? integrationMetricValue(pathIntegration, options.metricMode)
          : edgeMetricValue(edge, options.metricMode),
        integrationCount: pathIntegration ? 1 : edge.integration_count,
        payloadPerExecutionKb: edgePayloadExecutionCoverage > 0
          ? pathIntegration?.payload_per_execution_kb ?? edge.total_payload_per_execution_kb
          : null,
        qaStatus: pathIntegration?.qa_status ?? edge.risk_qa_status,
      };
    })
    .sort((left, right) => right.value - left.value || left.label.localeCompare(right.label));

  const qa = hasCompleteIntegrationDetails || selectedIntegration
    ? qaFromIntegrations(integrations)
    : qaFromEdges(edges);

  let flow: TopologyPulseInsights["flow"];
  if (selectedNode) {
    flow = {
      leftLabel: "Inbound",
      leftValue: edges
        .filter((edge) => edge.target === selectedNode.id)
        .reduce((total, edge) => total + edge.integration_count, 0),
      rightLabel: "Outbound",
      rightValue: edges
        .filter((edge) => edge.source === selectedNode.id)
        .reduce((total, edge) => total + edge.integration_count, 0),
    };
  } else if (selectedEdge) {
    flow = {
      leftLabel: selectedEdge.source,
      leftValue: integrationCount,
      rightLabel: selectedEdge.target,
      rightValue: integrationCount,
    };
  } else {
    flow = {
      leftLabel: "Sources",
      leftValue: new Set(edges.map((edge) => edge.source)).size,
      rightLabel: "Destinations",
      rightValue: new Set(edges.map((edge) => edge.target)).size,
    };
  }

  const topPath = [...edges].sort(
    (left, right) => right.integration_count - left.integration_count || edgeLabel(left).localeCompare(edgeLabel(right)),
  )[0];
  const systemLoads = new Map<string, number>();
  edges.forEach((edge) => {
    const scopedIntegrationCount = selectedIntegration ? 1 : edge.integration_count;
    systemLoads.set(edge.source, (systemLoads.get(edge.source) ?? 0) + scopedIntegrationCount);
    systemLoads.set(edge.target, (systemLoads.get(edge.target) ?? 0) + scopedIntegrationCount);
  });
  const [topSystemLabel = "—", topSystemLoad = 0] = [...systemLoads.entries()].sort(
    (left, right) => right[1] - left[1] || left[0].localeCompare(right[0]),
  )[0] ?? [];
  const values = paths.map((path) => path.value);

  let scope: TopologyPulseScope = "graph";
  let scopeLabel = "Filtered topology";
  if (selectedNode) {
    scope = "system";
    scopeLabel = selectedNode.label;
  }
  if (selectedEdge) {
    scope = "path";
    scopeLabel = edgeLabel(selectedEdge);
  }
  if (selectedIntegration) {
    scope = "integration";
    scopeLabel = selectedIntegration.name;
  }

  return {
    scope,
    scopeLabel,
    edges,
    paths,
    integrations,
    integrationCount,
    systemCount: systems.size,
    totalExecutionsPerDay,
    executionsCoverage,
    totalPayloadPerExecutionKb,
    payloadExecutionCoverage,
    totalPayloadPerHourKb,
    payloadHourCoverage,
    qa,
    flow,
    pathStats: {
      p50: percentile(values, 0.5),
      p95: percentile(values, 0.95),
      max: Math.max(0, ...values),
    },
    concentration: {
      topPathLabel: topPath ? edgeLabel(topPath) : "—",
      topPathShare:
        integrationCount > 0
          ? (selectedIntegration ? 1 : (topPath?.integration_count ?? 0)) / integrationCount
          : 0,
      topSystemLabel,
      topSystemShare: integrationCount > 0 ? topSystemLoad / (integrationCount * 2) : 0,
    },
  };
}
