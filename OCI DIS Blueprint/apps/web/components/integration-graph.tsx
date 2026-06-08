"use client";

/* SVG renderer for the integration topology workspace with clustered system domains. */

import { useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent, RefObject } from "react";
import * as d3 from "d3";

import { displayQaStatus } from "@/lib/format";
import {
  TOPOLOGY_DOMAIN_ORDER,
  TOPOLOGY_DOMAINS,
  qaTotalsForEdges,
  topologyDomainForNode,
} from "@/lib/topology";
import type { TopologyDomainId, TopologyLayoutMode } from "@/lib/topology";
import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/types";

type GraphMode = "select" | "pan";

type IntegrationGraphProps = {
  graph: GraphResponse;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  onNodeClick: (_node: GraphNode) => void;
  onEdgeClick: (_edge: GraphEdge) => void;
  colorMode: "qa" | "bp";
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
const LABELS_PER_DOMAIN = 3;

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

const BP_COLORS = ["#0f766e", "#2563eb", "#c2410c", "#7c3aed", "#be185d", "#ca8a04", "#0891b2", "#64748b"];

function clusterCenter(domainId: TopologyDomainId): { x: number; y: number } {
  const cluster = CLUSTER_GEOMETRY[domainId];
  return {
    x: cluster.x + cluster.width / 2,
    y: cluster.y + cluster.height / 2,
  };
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

function edgeWidth(integrationCount: number, maxCount: number): number {
  if (maxCount <= 1) {
    return 2.4;
  }
  return 2.2 + ((integrationCount - 1) / (maxCount - 1)) * 5.3;
}

function linkDistance(nodeCount: number, layoutMode: TopologyLayoutMode): number {
  if (layoutMode === "cluster") {
    return nodeCount >= 60 ? 112 : 126;
  }
  if (nodeCount >= 60) {
    return 58;
  }
  if (nodeCount >= 35) {
    return 72;
  }
  return 92;
}

function chargeStrength(nodeCount: number, layoutMode: TopologyLayoutMode): number {
  if (layoutMode === "cluster") {
    return nodeCount >= 60 ? -52 : -84;
  }
  return nodeCount >= 60 ? -125 : -190;
}

function edgeDashArray(edge: GraphEdge): string | undefined {
  const text = edge.patterns.join(" ").toLowerCase();
  if (edge.patterns.length > 1) {
    return "10 5 2 5";
  }
  if (
    text.includes("event") ||
    text.includes("pub") ||
    text.includes("async") ||
    text.includes("cdc") ||
    text.includes("batch") ||
    text.includes("webhook")
  ) {
    return "8 6";
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
  const index = Math.abs(bp.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0)) % BP_COLORS.length;
  return BP_COLORS[index];
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
  const topReserved = 255;
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
  onNodeClick,
  onEdgeClick,
  colorMode,
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
  const viewportRef = useRef(viewport);

  const maxNodeCount = useMemo(
    () => Math.max(1, ...graph.nodes.map((node) => node.integration_count)),
    [graph.nodes],
  );
  const maxEdgeCount = useMemo(
    () => Math.max(1, ...graph.edges.map((edge) => edge.integration_count)),
    [graph.edges],
  );
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
          .strength(layoutMode === "cluster" ? 0.055 : 0.35),
      )
      .force("charge", d3.forceManyBody().strength(chargeStrength(nodes.length, layoutMode)))
      .force(
        "x",
        d3
          .forceX<SimNode>((node) => (layoutMode === "cluster" ? clusterCenter(node.domainId).x : LOGICAL_WIDTH / 2))
          .strength(layoutMode === "cluster" ? 0.68 : 0.045),
      )
      .force(
        "y",
        d3
          .forceY<SimNode>((node) => (layoutMode === "cluster" ? clusterCenter(node.domainId).y : LOGICAL_HEIGHT / 2))
          .strength(layoutMode === "cluster" ? 0.72 : 0.05),
      )
      .force(
        "collision",
        d3
          .forceCollide<SimNode>()
          .radius((node) => nodeRadius(node.integration_count, maxNodeCount) + (layoutMode === "cluster" ? 18 : 10)),
      );

    simulation.tick(layoutMode === "cluster" ? 360 : 320);
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

  return (
    <div
      className={[
        "console-grid-bg relative h-full min-h-[42rem] overflow-hidden bg-[var(--color-surface)]",
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
        role="img"
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
              markerWidth="12"
              markerHeight="12"
              refX="10"
              refY="6"
              orient="auto"
              markerUnits="userSpaceOnUse"
            >
              <path d="M0,0 L0,12 L12,6 z" fill={style.marker} stroke="var(--color-surface)" strokeWidth="1" />
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
            const isConnectedToActiveNode = activeNodeId
              ? edge.source === activeNodeId || edge.target === activeNodeId
              : false;
            const isActive = isHovered || isSelected || isConnectedToActiveNode;
            const hasActiveContext = Boolean(activeNodeId || selectedEdgeId || hoveredEdgeId);
            const statusKey = edgeStatusKey(edge.dominant_qa_status);
            const statusStyle = EDGE_STATUS_STYLES[statusKey];
            const strokeWidth = edgeWidth(edge.integration_count, maxEdgeCount) * (isHovered || isSelected ? 1.28 : 1);
            const opacity = hasActiveContext ? (isActive ? 0.92 : 0.075) : layoutMode === "cluster" ? 0.22 : 0.52;
            const markerEnd = isActive || (!hasActiveContext && edge.integration_count >= maxEdgeCount * 0.58)
              ? `url(#topology-arrow-${statusKey})`
              : undefined;

            return (
              <g
                key={edge.id}
                onClick={() => {
                  if (mode === "select") {
                    onEdgeClick(edge);
                  }
                }}
                onMouseEnter={() => setHoveredEdgeId(edge.id)}
                onMouseLeave={() => setHoveredEdgeId(null)}
                style={{ cursor: mode === "select" ? "pointer" : undefined }}
              >
                <line
                  x1={shortened.start.x}
                  y1={shortened.start.y}
                  x2={shortened.end.x}
                  y2={shortened.end.y}
                  stroke="var(--color-surface)"
                  strokeWidth={strokeWidth + 4}
                  strokeLinecap="round"
                  opacity={isActive ? 0.95 : 0.28}
                  vectorEffect="non-scaling-stroke"
                />
                <line
                  x1={shortened.start.x}
                  y1={shortened.start.y}
                  x2={shortened.end.x}
                  y2={shortened.end.y}
                  stroke={statusStyle.stroke}
                  strokeWidth={strokeWidth}
                  strokeLinecap="round"
                  strokeDasharray={edgeDashArray(edge)}
                  markerEnd={markerEnd}
                  opacity={opacity}
                  vectorEffect="non-scaling-stroke"
                  style={{
                    filter: isActive ? `drop-shadow(0 0 7px ${statusStyle.glow})` : undefined,
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
                transform={`translate(${position.x}, ${position.y})`}
                onClick={() => {
                  if (mode === "select") {
                    onNodeClick(node);
                  }
                }}
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
              const label = `${hoveredEdge.integration_count} integration${hoveredEdge.integration_count === 1 ? "" : "s"}`;
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

      <div className="pointer-events-none absolute bottom-5 right-5 w-[min(18rem,calc(100%-2.5rem))] rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]/95 p-4 text-xs text-[var(--color-text-secondary)] shadow-[0_12px_30px_rgba(15,23,42,0.13)] backdrop-blur">
        <p className="app-label">Map Legend</p>
        <div className="mt-4">
          <p className="font-semibold text-[var(--color-text-primary)]">Edge thickness = volume</p>
          <div className="mt-3 flex items-end gap-5">
            {[2, 4, 7].map((width, index) => (
              <span key={width} className="flex flex-col items-center gap-1">
                <span className="block w-9 rounded-full bg-[var(--color-text-primary)]" style={{ height: `${width}px` }} />
                <span className="text-[10px] text-[var(--color-text-muted)]">{["low", "med", "high"][index]}</span>
              </span>
            ))}
          </div>
        </div>
        <div className="mt-4 border-t border-[var(--color-border)] pt-4">
          <p className="font-semibold text-[var(--color-text-primary)]">Color = QA status</p>
          <div className="mt-2 space-y-1.5">
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#15803d]" />OK</span>
              <span>{qaTotals.ok}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#b45309]" />{displayQaStatus("REVISAR")}</span>
              <span>{qaTotals.review}</span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-[#b91c1c]" />{displayQaStatus("PENDING")}</span>
              <span>{qaTotals.pending}</span>
            </div>
          </div>
        </div>
        <div className="mt-4 border-t border-[var(--color-border)] pt-4">
          <p className="font-semibold text-[var(--color-text-primary)]">Style = pattern</p>
          <div className="mt-2 space-y-2">
            <span className="flex items-center gap-3"><span className="h-px w-10 bg-[var(--color-text-primary)]" />Synchronous</span>
            <span className="flex items-center gap-3"><span className="h-px w-10 border-t border-dashed border-[var(--color-text-primary)]" />Asynchronous</span>
            <span className="flex items-center gap-3"><span className="h-px w-10 border-t-2 border-dotted border-[var(--color-text-primary)]" />Mixed</span>
          </div>
        </div>
      </div>
    </div>
  );
}
