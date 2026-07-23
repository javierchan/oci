"use client";

/* SVG renderer for the integration topology workspace with clustered system domains. */

import { ChevronDown, ChevronUp, Info } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent, MouseEvent, RefObject } from "react";
import * as d3 from "d3";

import { displayQaStatus } from "@/lib/format";
import {
  TOPOLOGY_DOMAIN_ORDER,
  TOPOLOGY_DOMAINS,
  BUSINESS_PROCESS_COLORS,
  businessProcessColor,
  businessProcessFamily,
  edgeMetricLabel,
  edgeMetricUnit,
  edgeMetricValue,
  qaTotalsForEdges,
  topologyDomainForNode,
} from "@/lib/topology";
import type {
  TopologyDomainId,
  TopologyLayoutMode,
  TopologyMetricMode,
  TopologyVisibilityMode,
} from "@/lib/topology";
import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/types";

type GraphMode = "select" | "pan";

type IntegrationGraphProps = {
  graph: GraphResponse;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  highlightedEdgeIds: string[];
  onNodeClick: (_node: GraphNode) => void;
  onEdgeClick: (_edge: GraphEdge) => void;
  colorMode: "qa" | "bp";
  metricMode: TopologyMetricMode;
  visibilityMode: TopologyVisibilityMode;
  focusedSystemId: string;
  layoutMode: TopologyLayoutMode;
  svgRef: RefObject<SVGSVGElement>;
  mode: GraphMode;
  viewport: { x: number; y: number; scale: number };
  onHomeViewportChange: (_viewport: { x: number; y: number; scale: number }) => void;
  onViewportChange: (
    _updater:
      | { x: number; y: number; scale: number }
      | ((_current: { x: number; y: number; scale: number }) => { x: number; y: number; scale: number }),
  ) => void;
};

type Position = {
  id: string;
  x: number;
  y: number;
};

type ClusterGeometry = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type SimNode = d3.SimulationNodeDatum & GraphNode & { domainId: TopologyDomainId };

const LOGICAL_WIDTH = 1320;
const LOGICAL_HEIGHT = 1000;
const LABELS_PER_DOMAIN = 1;

const CLUSTER_GEOMETRY: Record<TopologyDomainId, ClusterGeometry> = {
  finance: { x: 130, y: 315, width: 285, height: 190 },
  "human-capital": { x: 515, y: 278, width: 295, height: 205 },
  marketplace: { x: 900, y: 315, width: 315, height: 190 },
  identity: { x: 125, y: 565, width: 275, height: 182 },
  "data-platform": { x: 500, y: 528, width: 335, height: 210 },
  retail: { x: 900, y: 565, width: 315, height: 182 },
  logistics: { x: 205, y: 795, width: 340, height: 145 },
  "supply-chain": { x: 710, y: 795, width: 365, height: 145 },
  shared: { x: 550, y: 760, width: 230, height: 128 },
};

const EDGE_STATUS_STYLES: Record<
  "ok" | "review" | "mixed" | "pending",
  { stroke: string; marker: string; glow: string }
> = {
  ok: {
    stroke: "#15803d",
    marker: "#15803d",
    glow: "rgba(21, 128, 61, 0.26)",
  },
  review: {
    stroke: "#b45309",
    marker: "#b45309",
    glow: "rgba(180, 83, 9, 0.26)",
  },
  mixed: {
    stroke: "#ca8a04",
    marker: "#ca8a04",
    glow: "rgba(202, 138, 4, 0.24)",
  },
  pending: {
    stroke: "#b91c1c",
    marker: "#b91c1c",
    glow: "rgba(185, 28, 28, 0.24)",
  },
};

function clusterCenter(domainId: TopologyDomainId): { x: number; y: number } {
  const cluster = CLUSTER_GEOMETRY[domainId];
  return {
    x: cluster.x + cluster.width / 2,
    y: cluster.y + cluster.height / 2,
  };
}

function flowStageForNode(node: GraphNode): 0 | 1 | 2 {
  const label = node.label.toLowerCase();
  if (["core erp", "customer hub", "partner gateway"].some((term) => label.includes(term))) {
    return 0;
  }
  if (["warehouse", "analytics lake", "data lake", "reporting"].some((term) => label.includes(term))) {
    return 2;
  }
  if (["order hub", "inventory service", "pricing engine", "billing platform"].some((term) => label.includes(term))) {
    return 1;
  }
  const total = Math.max(node.as_source_count + node.as_destination_count, 1);
  const destinationRatio = node.as_destination_count / total;
  return destinationRatio < 0.42 ? 0 : destinationRatio > 0.58 ? 2 : 1;
}

function stableLabelOffset(label: string): number {
  return (label.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0) % 41) - 20;
}

function truncateNodeLabel(label: string, maxLength = 25): string {
  return label.length > maxLength ? `${label.slice(0, maxLength)}...` : label;
}

function edgeStatusKey(status: string): "ok" | "review" | "mixed" | "pending" {
  if (status === "OK") {
    return "ok";
  }
  if (status === "REVISAR") {
    return "review";
  }
  if (status === "PENDING") {
    return "pending";
  }
  return "mixed";
}

function nodeRadius(integrationCount: number, maxCount: number): number {
  if (maxCount === 0) {
    return 15;
  }
  return 14 + (integrationCount / maxCount) * 18;
}

function edgeWidth(value: number, maxValue: number): number {
  if (maxValue <= 0) {
    return 2.4;
  }
  const normalized = Math.sqrt(Math.max(value, 0) / maxValue);
  return 2.2 + normalized * 5.3;
}

function linkDistance(nodeCount: number, layoutMode: TopologyLayoutMode): number {
  if (layoutMode === "cluster") {
    return nodeCount >= 60 ? 112 : 126;
  }
  return nodeCount >= 60 ? 145 : 165;
}

function chargeStrength(nodeCount: number, layoutMode: TopologyLayoutMode): number {
  if (layoutMode === "cluster") {
    return nodeCount >= 60 ? -52 : -84;
  }
  return nodeCount >= 60 ? -70 : -110;
}

function edgeDashArray(edge: GraphEdge): string | undefined {
  if (edge.interaction_mode === "MIXED") {
    return "10 5 2 5";
  }
  if (edge.interaction_mode === "ASYNCHRONOUS") {
    return "8 6";
  }
  if (edge.interaction_mode === "UNSPECIFIED") {
    return "2 5";
  }
  return undefined;
}

function nodeQaColor(node: GraphNode, graph: GraphResponse): string {
  const relatedEdges = graph.edges.filter((edge) => edge.source === node.id || edge.target === node.id);
  if (relatedEdges.length === 0) {
    return "#64748b";
  }
  const totals = qaTotalsForEdges(relatedEdges);
  if (totals.pending > 0) {
    return EDGE_STATUS_STYLES.pending.stroke;
  }
  if (totals.review > 0 && totals.ok > 0) {
    return EDGE_STATUS_STYLES.mixed.stroke;
  }
  if (totals.review > 0) {
    return EDGE_STATUS_STYLES.review.stroke;
  }
  return EDGE_STATUS_STYLES.ok.stroke;
}

function nodeBusinessProcessColor(node: GraphNode): string {
  const bp = node.business_processes[0] ?? node.id;
  return businessProcessColor(bp);
}

function shortenEdge(
  source: Position,
  target: Position,
  sourceRadius: number,
  targetRadius: number,
): { start: Position; end: Position } {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.max(Math.hypot(dx, dy), 1);
  const offsetX = dx / distance;
  const offsetY = dy / distance;
  return {
    start: {
      id: source.id,
      x: source.x + offsetX * (sourceRadius + 6),
      y: source.y + offsetY * (sourceRadius + 6),
    },
    end: {
      id: target.id,
      x: target.x - offsetX * (targetRadius + 8),
      y: target.y - offsetY * (targetRadius + 8),
    },
  };
}

function fitViewport(nodes: SimNode[], maxNodeCount: number): { x: number; y: number; scale: number } {
  if (nodes.length === 0) {
    return { x: 0, y: 0, scale: 1 };
  }

  const bounds = nodes.reduce(
    (accumulator, node) => {
      const radius = nodeRadius(node.integration_count, maxNodeCount) + 62;
      return {
        minX: Math.min(accumulator.minX, (node.x ?? LOGICAL_WIDTH / 2) - radius),
        maxX: Math.max(accumulator.maxX, (node.x ?? LOGICAL_WIDTH / 2) + radius),
        minY: Math.min(accumulator.minY, (node.y ?? LOGICAL_HEIGHT / 2) - radius),
        maxY: Math.max(accumulator.maxY, (node.y ?? LOGICAL_HEIGHT / 2) + radius),
      };
    },
    {
      minX: Number.POSITIVE_INFINITY,
      maxX: Number.NEGATIVE_INFINITY,
      minY: Number.POSITIVE_INFINITY,
      maxY: Number.NEGATIVE_INFINITY,
    },
  );

  const padding = 44;
  // Keep the first graph row below the interactive Topology Pulse overlay.
  const topReserved = 215;
  const availableHeight = LOGICAL_HEIGHT - topReserved - padding;
  const contentWidth = Math.max(bounds.maxX - bounds.minX, 1);
  const contentHeight = Math.max(bounds.maxY - bounds.minY, 1);
  const fittedScale = Math.min(
    (LOGICAL_WIDTH - padding * 2) / contentWidth,
    availableHeight / contentHeight,
    1,
  );

  return {
    scale: fittedScale,
    x: padding - bounds.minX * fittedScale + (LOGICAL_WIDTH - padding * 2 - contentWidth * fittedScale) / 2,
    y: topReserved - bounds.minY * fittedScale + (availableHeight - contentHeight * fittedScale) / 2,
  };
}

export function IntegrationGraph({
  graph,
  selectedNodeId,
  selectedEdgeId,
  highlightedEdgeIds,
  onNodeClick,
  onEdgeClick,
  colorMode,
  metricMode,
  visibilityMode,
  focusedSystemId,
  layoutMode,
  svgRef,
  mode,
  viewport,
  onHomeViewportChange,
  onViewportChange,
}: IntegrationGraphProps): JSX.Element {
  const [positions, setPositions] = useState<Record<string, Position>>({});
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [legendOpen, setLegendOpen] = useState<boolean>(false);
  const viewportRef = useRef(viewport);

  const maxNodeCount = useMemo(
    () => Math.max(1, ...graph.nodes.map((node) => node.integration_count)),
    [graph.nodes],
  );
  const maxEdgeMetric = useMemo(
    () => Math.max(1, ...graph.edges.map((edge) => edgeMetricValue(edge, metricMode))),
    [graph.edges, metricMode],
  );
  const highlightedEdgeIdSet = useMemo(() => new Set(highlightedEdgeIds), [highlightedEdgeIds]);
  const processLegend = useMemo(() => {
    const counts = new Map<string, number>();
    graph.edges.forEach((edge) => {
      edge.business_processes.forEach((process) => {
        const family = businessProcessFamily(process);
        counts.set(family, (counts.get(family) ?? 0) + edge.integration_count);
      });
    });
    return [...counts.entries()]
      .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
      .slice(0, 8);
  }, [graph.edges]);
  const priorityEdgeIds = useMemo(() => {
    const riskEdges = graph.edges
      .filter((edge) => edge.risk_qa_status !== "OK")
      .sort((left, right) => right.risk_score - left.risk_score || edgeMetricValue(right, metricMode) - edgeMetricValue(left, metricMode))
      .slice(0, 52);
    const highVolumeOkEdges = graph.edges
      .filter((edge) => edge.risk_qa_status === "OK")
      .sort((left, right) => edgeMetricValue(right, metricMode) - edgeMetricValue(left, metricMode))
      .slice(0, 8);
    return new Set([...riskEdges, ...highVolumeOkEdges].map((edge) => edge.id));
  }, [graph.edges, metricMode]);
  const domainCounts = useMemo(() => {
    const counts = new Map<TopologyDomainId, number>();
    graph.nodes.forEach((node) => {
      const domain = topologyDomainForNode(node);
      counts.set(domain.id, (counts.get(domain.id) ?? 0) + 1);
    });
    return counts;
  }, [graph.nodes]);
  const labelNodeIds = useMemo(() => {
    const ids = new Set<string>();
    TOPOLOGY_DOMAIN_ORDER.forEach((domainId) => {
      graph.nodes
        .filter((node) => topologyDomainForNode(node).id === domainId)
        .sort((left, right) => right.integration_count - left.integration_count || left.label.localeCompare(right.label))
        .slice(0, LABELS_PER_DOMAIN)
        .forEach((node) => ids.add(node.id));
    });
    return ids;
  }, [graph.nodes]);
  const focusedNode = focusedSystemId ? graph.nodes.find((node) => node.label === focusedSystemId) ?? null : null;
  const focusedNodeId = focusedNode?.id ?? selectedNodeId;
  const activeNodeId = hoveredNodeId ?? focusedNodeId;
  const hoveredEdge = hoveredEdgeId ? graph.edges.find((edge) => edge.id === hoveredEdgeId) ?? null : null;
  const connectedNodeIds = useMemo(() => {
    if (hoveredEdge) {
      return new Set([hoveredEdge.source, hoveredEdge.target]);
    }
    if (!activeNodeId) {
      return new Set<string>();
    }
    const related = graph.edges.filter((edge) => edge.source === activeNodeId || edge.target === activeNodeId);
    return new Set([activeNodeId, ...related.flatMap((edge) => [edge.source, edge.target])]);
  }, [activeNodeId, graph.edges, hoveredEdge]);
  const qaTotals = useMemo(() => qaTotalsForEdges(graph.edges), [graph.edges]);

  useEffect(() => {
    viewportRef.current = viewport;
  }, [viewport]);

  useEffect(() => {
    const nodes: SimNode[] = graph.nodes.map((node) => ({
      ...node,
      domainId: topologyDomainForNode(node).id,
    }));
    const links: Array<d3.SimulationLinkDatum<SimNode>> = graph.edges.map((edge) => ({
      source: edge.source,
      target: edge.target,
    }));

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, d3.SimulationLinkDatum<SimNode>>(links)
          .id((datum) => datum.id)
          .distance(linkDistance(nodes.length, layoutMode))
          .strength(layoutMode === "cluster" ? 0.055 : 0.015),
      )
      .force("charge", d3.forceManyBody().strength(chargeStrength(nodes.length, layoutMode)))
      .force(
        "x",
        d3
          .forceX<SimNode>((node) => {
            if (layoutMode === "cluster") {
              return clusterCenter(node.domainId).x;
            }
            return [220, LOGICAL_WIDTH / 2, LOGICAL_WIDTH - 220][flowStageForNode(node)];
          })
          .strength(layoutMode === "cluster" ? 0.68 : 0.96),
      )
      .force(
        "y",
        d3
          .forceY<SimNode>((node) => {
            if (layoutMode === "cluster") {
              return clusterCenter(node.domainId).y;
            }
            const domainIndex = Math.max(0, TOPOLOGY_DOMAIN_ORDER.indexOf(node.domainId));
            return 175 + (domainIndex / Math.max(TOPOLOGY_DOMAIN_ORDER.length - 1, 1)) * 660 + stableLabelOffset(node.label);
          })
          .strength(layoutMode === "cluster" ? 0.72 : 0.64),
      )
      .force(
        "collision",
        d3
          .forceCollide<SimNode>()
          .radius((node) => nodeRadius(node.integration_count, maxNodeCount) + (layoutMode === "cluster" ? 18 : 10)),
      );

    simulation.tick(layoutMode === "cluster" ? 360 : 420);
    simulation.stop();

    const fittedViewport = fitViewport(nodes, maxNodeCount);
    onHomeViewportChange(fittedViewport);
    onViewportChange(fittedViewport);
    setPositions(
      Object.fromEntries(
        nodes.map((node) => [
          node.id,
          {
            id: node.id,
            x: node.x ?? LOGICAL_WIDTH / 2,
            y: node.y ?? LOGICAL_HEIGHT / 2,
          },
        ]),
      ),
    );
  }, [graph, layoutMode, maxNodeCount, onHomeViewportChange, onViewportChange]);

  useEffect(() => {
    if (!focusedSystemId || Object.keys(positions).length === 0) {
      return;
    }
    const focusNode = graph.nodes.find((node) => node.id === focusedSystemId || node.label === focusedSystemId);
    if (!focusNode) {
      return;
    }
    const neighborhood = new Set<string>([focusNode.id]);
    graph.edges.forEach((edge) => {
      if (edge.source === focusNode.id || edge.target === focusNode.id) {
        neighborhood.add(edge.source);
        neighborhood.add(edge.target);
      }
    });
    const focusNodes: SimNode[] = graph.nodes
      .filter((node) => neighborhood.has(node.id))
      .map((node) => ({
        ...node,
        domainId: topologyDomainForNode(node).id,
        x: positions[node.id]?.x,
        y: positions[node.id]?.y,
      }));
    onViewportChange(fitViewport(focusNodes, maxNodeCount));
  }, [focusedSystemId, graph.edges, graph.nodes, maxNodeCount, onViewportChange, positions]);

  useEffect(() => {
    const element = svgRef.current;
    if (!element) {
      return;
    }
    const svgElement = element;

    function handleNativeWheel(event: WheelEvent): void {
      event.preventDefault();
      const currentViewport = viewportRef.current;
      const delta = event.deltaY > 0 ? 0.9 : 1.1;
      const rect = svgElement.getBoundingClientRect();
      const cx = event.clientX - rect.left;
      const cy = event.clientY - rect.top;
      onViewportChange(() => {
        const nextScale = Math.min(Math.max(currentViewport.scale * delta, 0.2), 3.8);
        return {
          scale: nextScale,
          x: cx - (cx - currentViewport.x) * (nextScale / currentViewport.scale),
          y: cy - (cy - currentViewport.y) * (nextScale / currentViewport.scale),
        };
      });
    }

    svgElement.addEventListener("wheel", handleNativeWheel, { passive: false });
    return () => {
      svgElement.removeEventListener("wheel", handleNativeWheel);
    };
  }, [onViewportChange, svgRef]);

  function handleMouseDown(event: MouseEvent<SVGSVGElement>): void {
    if (mode !== "pan") {
      return;
    }
    setIsDragging(true);
    setDragStart({ x: event.clientX, y: event.clientY });
  }

  function handleMouseMove(event: MouseEvent<SVGSVGElement>): void {
    if (mode !== "pan" || !isDragging || !dragStart) {
      return;
    }
    const dx = event.clientX - dragStart.x;
    const dy = event.clientY - dragStart.y;
    setDragStart({ x: event.clientX, y: event.clientY });
    onViewportChange((current) => ({
      ...current,
      x: current.x + dx,
      y: current.y + dy,
    }));
  }

  function handleMouseUp(): void {
    setIsDragging(false);
    setDragStart(null);
  }

  function activateWithKeyboard(event: KeyboardEvent<SVGGElement>, action: () => void): void {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      action();
    }
  }

  return (
    <div
      className={[
        "console-grid-bg relative h-full min-h-0 overflow-hidden bg-[var(--color-surface)]",
        mode === "pan" ? (isDragging ? "cursor-grabbing" : "cursor-grab") : "cursor-default",
      ].join(" ")}
    >
      <svg
        ref={svgRef}
        viewBox={`0 0 ${LOGICAL_WIDTH} ${LOGICAL_HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
        className="block h-full w-full"
        style={{ touchAction: "none" }}
        aria-label="Integration system dependency topology"
        role="group"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <defs>
          {Object.entries(EDGE_STATUS_STYLES).map(([key, style]) => (
            <marker
              key={key}
              id={`topology-arrow-${key}`}
              markerWidth="8"
              markerHeight="8"
              refX="7"
              refY="4"
              orient="auto"
              markerUnits="userSpaceOnUse"
            >
              <path d="M0,0 L0,8 L8,4 z" fill={style.marker} stroke="var(--color-surface)" strokeWidth="0.8" />
            </marker>
          ))}
          {BUSINESS_PROCESS_COLORS.map((color) => (
            <marker
              key={color}
              id={`topology-arrow-process-${color.slice(1)}`}
              markerWidth="8"
              markerHeight="8"
              refX="7"
              refY="4"
              orient="auto"
              markerUnits="userSpaceOnUse"
            >
              <path d="M0,0 L0,8 L8,4 z" fill={color} stroke="var(--color-surface)" strokeWidth="0.8" />
            </marker>
          ))}
        </defs>

        <g transform={`translate(${viewport.x}, ${viewport.y}) scale(${viewport.scale})`}>
          {layoutMode === "cluster"
            ? TOPOLOGY_DOMAIN_ORDER.map((domainId) => {
                const count = domainCounts.get(domainId) ?? 0;
                if (count === 0) {
                  return null;
                }
                const geometry = CLUSTER_GEOMETRY[domainId];
                const domain = TOPOLOGY_DOMAINS[domainId];
                return (
                  <g key={domainId} pointerEvents="none">
                    <rect
                      x={geometry.x}
                      y={geometry.y}
                      width={geometry.width}
                      height={geometry.height}
                      rx={18}
                      fill={domain.color}
                      opacity={0.08}
                      stroke={domain.color}
                      strokeWidth={2}
                      strokeDasharray="4 5"
                    />
                    <text
                      x={geometry.x + 18}
                      y={geometry.y + 28}
                      fontSize={11}
                      fontWeight={800}
                      fill={domain.color}
                    >
                      {domain.shortLabel}
                    </text>
                  </g>
                );
              })
            : null}

          {layoutMode === "flow" ? (
            <g pointerEvents="none">
              {[
                { x: 220, label: "SYSTEMS OF RECORD" },
                { x: LOGICAL_WIDTH / 2, label: "OPERATIONAL SERVICES" },
                { x: LOGICAL_WIDTH - 220, label: "ANALYTICS & DELIVERY" },
              ].map((stage) => (
                <g key={stage.label}>
                  <text x={stage.x} y={80} textAnchor="middle" fontSize={12} fontWeight={800} fill="var(--color-text-muted)">{stage.label}</text>
                  <line x1={stage.x - 145} y1={100} x2={stage.x + 145} y2={100} stroke="var(--color-border)" strokeWidth={1.5} />
                </g>
              ))}
            </g>
          ) : null}

          {graph.edges.map((edge) => {
            const source = positions[edge.source];
            const target = positions[edge.target];
            if (!source || !target) {
              return null;
            }
            const sourceNode = graph.nodes.find((node) => node.id === edge.source);
            const targetNode = graph.nodes.find((node) => node.id === edge.target);
            if (!sourceNode || !targetNode) {
              return null;
            }
            const sourceRadius = nodeRadius(sourceNode.integration_count, maxNodeCount);
            const targetRadius = nodeRadius(targetNode.integration_count, maxNodeCount);
            const shortened = shortenEdge(source, target, sourceRadius, targetRadius);
            const isHovered = hoveredEdgeId === edge.id;
            const isSelected = selectedEdgeId === edge.id;
            const isPulseHighlighted = highlightedEdgeIdSet.has(edge.id);
            const isConnectedToActiveNode = activeNodeId
              ? edge.source === activeNodeId || edge.target === activeNodeId
              : false;
            const isActive = isHovered || isSelected || isPulseHighlighted || isConnectedToActiveNode;
            if (visibilityMode === "priority" && !priorityEdgeIds.has(edge.id) && !isActive) {
              return null;
            }
            const hasActiveContext = Boolean(
              activeNodeId || selectedEdgeId || hoveredEdgeId || highlightedEdgeIdSet.size,
            );
            const statusKey = edgeStatusKey(edge.risk_qa_status);
            const statusStyle = EDGE_STATUS_STYLES[statusKey];
            const processColor = businessProcessColor(edge.business_processes[0] ?? edge.id);
            const edgeColor = colorMode === "qa" ? statusStyle.stroke : processColor;
            const metricValue = edgeMetricValue(edge, metricMode);
            const strokeWidth = edgeWidth(metricValue, maxEdgeMetric)
              * (isHovered || isSelected || isPulseHighlighted ? 1.24 : 1);
            const opacity = hasActiveContext ? (isActive ? 0.96 : 0.045) : layoutMode === "cluster" ? 0.28 : 0.38;
            const markerEnd = !hasActiveContext || isActive
              ? colorMode === "qa"
                ? `url(#topology-arrow-${statusKey})`
                : `url(#topology-arrow-process-${processColor.slice(1)})`
              : undefined;
            const metricLabel = metricMode === "relationships"
              ? `${metricValue} integration${metricValue === 1 ? "" : "s"}`
              : `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(metricValue)} ${edgeMetricUnit(metricMode)}`;

            return (
              <g
                key={edge.id}
                data-edge-id={edge.id}
                data-pulse-highlighted={isPulseHighlighted ? "true" : undefined}
                role="button"
                tabIndex={mode === "select" ? 0 : -1}
                aria-label={`${edge.source} to ${edge.target}, ${metricLabel}, ${edge.risk_qa_status}`}
                onClick={() => {
                  if (mode === "select") {
                    onEdgeClick(edge);
                  }
                }}
                onKeyDown={(event) => activateWithKeyboard(event, () => onEdgeClick(edge))}
                onMouseEnter={() => setHoveredEdgeId(edge.id)}
                onMouseLeave={() => setHoveredEdgeId(null)}
                style={{ cursor: mode === "select" ? "pointer" : undefined }}
              >
                <title>{`${edge.source} to ${edge.target} · ${metricLabel}`}</title>
                <line
                  x1={shortened.start.x}
                  y1={shortened.start.y}
                  x2={shortened.end.x}
                  y2={shortened.end.y}
                  stroke="transparent"
                  strokeWidth={Math.max(strokeWidth + 10, 14)}
                  vectorEffect="non-scaling-stroke"
                />
                <line
                  x1={shortened.start.x}
                  y1={shortened.start.y}
                  x2={shortened.end.x}
                  y2={shortened.end.y}
                  stroke="var(--color-surface)"
                  strokeWidth={strokeWidth + 4}
                  strokeLinecap="round"
                  opacity={isActive ? 0.95 : 0.42}
                  vectorEffect="non-scaling-stroke"
                />
                <line
                  x1={shortened.start.x}
                  y1={shortened.start.y}
                  x2={shortened.end.x}
                  y2={shortened.end.y}
                  stroke={edgeColor}
                  strokeWidth={strokeWidth}
                  strokeLinecap="round"
                  strokeDasharray={edgeDashArray(edge)}
                  markerEnd={markerEnd}
                  opacity={opacity}
                  vectorEffect="non-scaling-stroke"
                  style={{
                    filter: isActive ? `drop-shadow(0 0 7px ${colorMode === "qa" ? statusStyle.glow : processColor})` : undefined,
                  }}
                />
              </g>
            );
          })}

          {graph.nodes.map((node) => {
            const position = positions[node.id];
            if (!position) {
              return null;
            }
            const radius = nodeRadius(node.integration_count, maxNodeCount);
            const domain = topologyDomainForNode(node);
            const qaColor = colorMode === "qa" ? nodeQaColor(node, graph) : nodeBusinessProcessColor(node);
            const isSelected = selectedNodeId === node.id;
            const isHovered = hoveredNodeId === node.id;
            const isFocused = focusedNodeId === node.id;
            const isConnected = connectedNodeIds.size === 0 || connectedNodeIds.has(node.id);
            const hasActiveContext = Boolean(activeNodeId || selectedEdgeId || hoveredEdgeId);
            const opacity = hasActiveContext ? (isConnected || isFocused || isSelected || isHovered ? 1 : 0.22) : 1;
            const shouldShowLabel =
              labelNodeIds.has(node.id) ||
              isSelected ||
              isHovered ||
              isFocused ||
              (connectedNodeIds.size > 0 && connectedNodeIds.has(node.id));
            const label = truncateNodeLabel(node.label, isSelected || isFocused ? 32 : 24);
            const labelWidth = Math.min(180, Math.max(86, label.length * 5.8 + 22));

            return (
              <g
                key={node.id}
                role="button"
                tabIndex={mode === "select" ? 0 : -1}
                aria-label={`${node.label}, ${node.integration_count} integrations`}
                transform={`translate(${position.x}, ${position.y})`}
                onClick={() => {
                  if (mode === "select") {
                    onNodeClick(node);
                  }
                }}
                onKeyDown={(event) => activateWithKeyboard(event, () => onNodeClick(node))}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                style={{ cursor: mode === "select" ? "pointer" : undefined }}
              >
                <title>{node.label}</title>
                {isFocused || isSelected ? (
                  <circle
                    r={radius + 8}
                    fill="none"
                    stroke="var(--color-text-primary)"
                    strokeWidth={3.2}
                    opacity={0.9}
                  />
                ) : null}
                <circle
                  r={radius}
                  fill="var(--color-surface)"
                  stroke={qaColor}
                  strokeWidth={isHovered || isSelected || isFocused ? 4 : 2.8}
                  opacity={opacity}
                  style={{ filter: isHovered || isSelected || isFocused ? "drop-shadow(0 8px 16px rgba(15, 23, 42, 0.18))" : undefined }}
                />
                <circle r={Math.max(4, radius * 0.18)} cx={radius * 0.48} cy={-radius * 0.44} fill={domain.color} opacity={opacity} />
                <text
                  textAnchor="middle"
                  y={-2}
                  fontSize={Math.max(9, radius * 0.42)}
                  fill="var(--color-text-primary)"
                  fontWeight={800}
                  opacity={opacity}
                >
                  {node.integration_count}
                </text>
                <text
                  textAnchor="middle"
                  y={radius * 0.42}
                  fontSize={8.5}
                  fill="var(--color-text-muted)"
                  fontWeight={700}
                  opacity={opacity}
                >
                  ix
                </text>
                {shouldShowLabel ? (
                  <g transform={`translate(0, ${radius + 9})`} pointerEvents="none" opacity={opacity}>
                    <rect
                      x={-labelWidth / 2}
                      y={0}
                      width={labelWidth}
                      height={23}
                      rx={11.5}
                      fill="var(--color-surface)"
                      stroke="var(--color-border)"
                      opacity={0.96}
                      style={{ filter: "drop-shadow(0 3px 10px rgba(15, 23, 42, 0.12))" }}
                    />
                    <text
                      textAnchor="middle"
                      y={15}
                      fontSize={9.5}
                      fontWeight={700}
                      fill="var(--color-text-primary)"
                    >
                      {label}
                    </text>
                  </g>
                ) : null}
              </g>
            );
          })}

          {hoveredEdge ? (
            (() => {
              const source = positions[hoveredEdge.source];
              const target = positions[hoveredEdge.target];
              if (!source || !target) {
                return null;
              }
              const x = (source.x + target.x) / 2;
              const y = (source.y + target.y) / 2 - 10;
              const metricValue = edgeMetricValue(hoveredEdge, metricMode);
              const label = `${new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(metricValue)} ${edgeMetricUnit(metricMode)}`;
              return (
                <g transform={`translate(${x}, ${y})`} pointerEvents="none">
                  <rect
                    x={-62}
                    y={-18}
                    width={124}
                    height={27}
                    rx={13.5}
                    fill="var(--color-text-primary)"
                    opacity={0.94}
                  />
                  <text textAnchor="middle" y={0} fontSize={10.5} fontWeight={700} fill="var(--color-surface)">
                    {label}
                  </text>
                </g>
              );
            })()
          ) : null}
        </g>
      </svg>

      <div className="absolute bottom-4 right-4 w-[min(17rem,calc(100%-2rem))] overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]/95 text-xs text-[var(--color-text-secondary)] shadow-[0_12px_30px_rgba(15,23,42,0.13)] backdrop-blur">
        <button
          type="button"
          onClick={() => setLegendOpen((current) => !current)}
          className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left"
          aria-expanded={legendOpen}
        >
          <span className="inline-flex items-center gap-2 font-semibold text-[var(--color-text-primary)]">
            <Info className="h-3.5 w-3.5" />
            Map legend
          </span>
          {legendOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}
        </button>
        {legendOpen ? (
          <div className="max-h-[24rem] overflow-y-auto border-t border-[var(--color-border)] px-3 py-3">
            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase text-[var(--color-text-muted)]">
                {visibilityMode === "priority" ? `${priorityEdgeIds.size} priority paths shown` : `${graph.edges.length} paths shown`}
              </p>
              <p className="font-semibold text-[var(--color-text-primary)]">Thickness = {edgeMetricLabel(metricMode)}</p>
              <div className="mt-2 flex items-end gap-5">
                {[2, 4, 7].map((width, index) => (
                  <span key={width} className="flex flex-col items-center gap-1">
                    <span className="block w-9 rounded-full bg-[var(--color-text-primary)]" style={{ height: `${width}px` }} />
                    <span className="text-[10px] text-[var(--color-text-muted)]">{["low", "med", "high"][index]}</span>
                  </span>
                ))}
              </div>
              {metricMode !== "relationships" ? (
                <p className="mt-2 text-[10px] leading-4 text-[var(--color-text-muted)]">
                  Coverage: {metricMode === "executions" ? graph.meta.executions_coverage : graph.meta.payload_coverage} of {graph.meta.integration_count} integrations
                </p>
              ) : null}
            </div>

            <div className="mt-3 border-t border-[var(--color-border)] pt-3">
              <p className="font-semibold text-[var(--color-text-primary)]">Color = {colorMode === "qa" ? "worst QA state" : "process family"}</p>
              {colorMode === "qa" ? (
                <div className="mt-2 space-y-1.5">
                  <div className="flex items-center justify-between gap-3"><span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#15803d]" />OK</span><span>{qaTotals.ok}</span></div>
                  <div className="flex items-center justify-between gap-3"><span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#b45309]" />{displayQaStatus("REVISAR")}</span><span>{qaTotals.review}</span></div>
                  <div className="flex items-center justify-between gap-3"><span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#b91c1c]" />{displayQaStatus("PENDING")}</span><span>{qaTotals.pending}</span></div>
                </div>
              ) : (
                <div className="mt-2 space-y-1.5">
                  {processLegend.map(([family, count]) => (
                    <div key={family} className="flex items-center justify-between gap-3">
                      <span className="inline-flex min-w-0 items-center gap-2"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: businessProcessColor(family) }} /><span className="truncate">{family}</span></span>
                      <span>{count}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-3 border-t border-[var(--color-border)] pt-3">
              <p className="font-semibold text-[var(--color-text-primary)]">Line = interaction mode</p>
              <div className="mt-2 space-y-2">
                <span className="flex items-center gap-3"><span className="h-px w-10 bg-[var(--color-text-primary)]" />Synchronous</span>
                <span className="flex items-center gap-3"><span className="h-px w-10 border-t border-dashed border-[var(--color-text-primary)]" />Asynchronous</span>
                <span className="flex items-center gap-3"><span className="h-px w-10 border-t-2 border-dotted border-[var(--color-text-primary)]" />Mixed / unspecified</span>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
