"use client";

/* React + SVG renderer for the system dependency graph using D3 force layout only for positioning. */

import { useEffect, useMemo, useRef, useState } from "react";
import type { RefObject } from "react";
import * as d3 from "d3";

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
  svgRef: RefObject<SVGSVGElement>;
  mode: GraphMode;
  viewport: { x: number; y: number; scale: number };
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

type SimNode = d3.SimulationNodeDatum & GraphNode;
type SimEdge = d3.SimulationLinkDatum<SimNode> & GraphEdge;

const LOGICAL_WIDTH = 1200;
const LOGICAL_HEIGHT = 760;
const EDGE_COLORS: Record<string, string> = {
  OK: "#86efac",
  REVISAR: "#fde047",
  PENDING: "#d1d5db",
};
const BP_COLORS = ["#0ea5e9", "#22c55e", "#f97316", "#eab308", "#8b5cf6", "#ef4444", "#14b8a6", "#f43f5e"];

function edgeStatusKey(status: string): "ok" | "revisar" | "mixed" | "pending" {
  if (status === "OK") {
    return "ok";
  }
  if (status === "REVISAR") {
    return "revisar";
  }
  if (status === "PENDING") {
    return "pending";
  }
  return "mixed";
}

function fitViewport(nodes: SimNode[], maxNodeCount: number): { x: number; y: number; scale: number } {
  if (nodes.length === 0) {
    return { x: 0, y: 0, scale: 1 };
  }

  const padding = 40;
  const bounds = nodes.reduce(
    (accumulator, node) => {
      const radius = nodeRadius(node.integration_count, maxNodeCount);
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

  const contentWidth = Math.max(bounds.maxX - bounds.minX, 1);
  const contentHeight = Math.max(bounds.maxY - bounds.minY, 1);
  const scale = Math.min((LOGICAL_WIDTH - padding * 2) / contentWidth, (LOGICAL_HEIGHT - padding * 2) / contentHeight, 1);
  return {
    scale,
    x: padding - bounds.minX * scale + (LOGICAL_WIDTH - padding * 2 - contentWidth * scale) / 2,
    y: padding - bounds.minY * scale + (LOGICAL_HEIGHT - padding * 2 - contentHeight * scale) / 2,
  };
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
      x: source.x + offsetX * (sourceRadius + 4),
      y: source.y + offsetY * (sourceRadius + 4),
    },
    end: {
      id: target.id,
      x: target.x - offsetX * (targetRadius + 4),
      y: target.y - offsetY * (targetRadius + 4),
    },
  };
}

function edgeWidth(integrationCount: number, maxCount: number): number {
  if (maxCount <= 1) {
    return 1.5;
  }
  return 1.5 + ((integrationCount - 1) / (maxCount - 1)) * 2.5;
}

function nodeRadius(integrationCount: number, maxCount: number): number {
  if (maxCount === 0) {
    return 20;
  }
  return 20 + (integrationCount / maxCount) * 30;
}

function nodeColor(node: GraphNode, graph: GraphResponse, mode: "qa" | "bp"): string {
  if (mode === "bp") {
    const bp = node.business_processes[0] ?? node.id;
    const index = Math.abs(bp.split("").reduce((sum, char) => sum + char.charCodeAt(0), 0)) % BP_COLORS.length;
    return BP_COLORS[index];
  }

  const relatedEdges = graph.edges.filter((edge) => edge.source === node.id || edge.target === node.id);
  if (relatedEdges.length === 0) {
    return "#6b7280";
  }
  const statuses = relatedEdges.map((edge) => edge.dominant_qa_status);
  const allOk = statuses.every((status) => status === "OK");
  const allRevisar = statuses.every((status) => status === "REVISAR");
  const hasPending = statuses.some((status) => status === "PENDING");

  if (allOk) {
    return "#22c55e";
  }
  if (allRevisar) {
    return "#f97316";
  }
  if (hasPending) {
    return "#6b7280";
  }
  return "#eab308";
}

export function IntegrationGraph({
  graph,
  selectedNodeId,
  selectedEdgeId,
  onNodeClick,
  onEdgeClick,
  colorMode,
  focusedSystemId,
  svgRef,
  mode,
  viewport,
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

  useEffect(() => {
    viewportRef.current = viewport;
  }, [viewport]);

  useEffect(() => {
    const nodes: SimNode[] = graph.nodes.map((node) => ({ ...node }));
    const edges: SimEdge[] = graph.edges.map((edge) => ({ ...edge }));

    const sim = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink<SimNode, SimEdge>(edges)
          .id((datum) => datum.id)
          .distance(120),
      )
      .force("charge", d3.forceManyBody().strength(-400))
      .force("center", d3.forceCenter(LOGICAL_WIDTH / 2, LOGICAL_HEIGHT / 2))
      .force(
        "collision",
        d3.forceCollide<SimNode>().radius((datum) => nodeRadius(datum.integration_count, maxNodeCount) + 20),
      );

    sim.tick(300);
    sim.stop();

    onViewportChange(fitViewport(nodes, maxNodeCount));
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
  }, [graph, maxNodeCount, onViewportChange]);

  useEffect(() => {
    const element = svgRef.current;
    if (!element) {
      return;
    }

    function handleNativeWheel(event: WheelEvent): void {
      event.preventDefault();
      const currentViewport = viewportRef.current;
      const delta = event.deltaY > 0 ? 0.9 : 1.1;
      const rect = element!.getBoundingClientRect();
      const cx = event.clientX - rect.left;
      const cy = event.clientY - rect.top;
      onViewportChange(() => {
        const nextScale = Math.min(Math.max(currentViewport.scale * delta, 0.2), 4);
        return {
          scale: nextScale,
          x: cx - (cx - currentViewport.x) * (nextScale / currentViewport.scale),
          y: cy - (cy - currentViewport.y) * (nextScale / currentViewport.scale),
        };
      });
    }

    element.addEventListener("wheel", handleNativeWheel, { passive: false });
    return () => {
      element.removeEventListener("wheel", handleNativeWheel);
    };
  }, [onViewportChange, svgRef]);

  const hoveredEdge = hoveredEdgeId
    ? graph.edges.find((edge) => edge.id === hoveredEdgeId) ?? null
    : null;

  const activeNodeId = hoveredNodeId ?? selectedNodeId;
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
  const focusedSystemNode = focusedSystemId
    ? graph.nodes.find((node) => node.label === focusedSystemId) ?? null
    : null;
  const focusedSystemNeighborhood = useMemo(() => {
    if (!focusedSystemNode) {
      return new Set<string>();
    }
    const related = graph.edges.filter(
      (edge) => edge.source === focusedSystemNode.id || edge.target === focusedSystemNode.id,
    );
    return new Set([focusedSystemNode.id, ...related.flatMap((edge) => [edge.source, edge.target])]);
  }, [focusedSystemNode, graph.edges]);

  function handleMouseDown(event: React.MouseEvent<SVGSVGElement>): void {
    if (mode !== "pan") {
      return;
    }
    setIsDragging(true);
    setDragStart({ x: event.clientX, y: event.clientY });
  }

  function handleMouseMove(event: React.MouseEvent<SVGSVGElement>): void {
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
        "relative overflow-hidden rounded-[2rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] shadow-sm",
        mode === "pan" ? (isDragging ? "cursor-grabbing" : "cursor-grab") : "cursor-default",
      ].join(" ")}
      style={{ height: "min(760px, calc(100vh - 14rem))" }}
    >
      <svg
        ref={svgRef}
        viewBox={`0 0 ${LOGICAL_WIDTH} ${LOGICAL_HEIGHT}`}
        preserveAspectRatio="xMidYMid meet"
        className="block h-full w-full"
        style={{ touchAction: "none" }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
          <defs>
            <marker id="arrow-ok" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#22c55e" />
            </marker>
            <marker id="arrow-revisar" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#f97316" />
            </marker>
            <marker id="arrow-mixed" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#eab308" />
            </marker>
            <marker id="arrow-pending" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#94a3b8" />
            </marker>
          </defs>

          <g transform={`translate(${viewport.x}, ${viewport.y}) scale(${viewport.scale})`}>
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
            const isConnectedToHoveredNode = activeNodeId
              ? edge.source === activeNodeId || edge.target === activeNodeId
              : false;
            const shouldDim =
              (!!hoveredEdgeId && !isHovered) ||
              (!!activeNodeId && !isConnectedToHoveredNode && !isHovered) ||
              (!!focusedSystemNode && !focusedSystemNeighborhood.has(edge.source) && !focusedSystemNeighborhood.has(edge.target));
            const arrowKey = edgeStatusKey(edge.dominant_qa_status);
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
                  className={!shouldDim ? "graph-edge-animated" : undefined}
                  strokeWidth={edgeWidth(edge.integration_count, maxEdgeCount) * (isHovered ? 1.5 : 1)}
                  stroke={EDGE_COLORS[edge.dominant_qa_status] ?? "#d1d5db"}
                  markerEnd={`url(#arrow-${arrowKey})`}
                  opacity={shouldDim ? 0.2 : selectedEdgeId && selectedEdgeId !== edge.id ? 0.35 : 0.9}
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
            const fill = nodeColor(node, graph, colorMode);
            const isSelected = selectedNodeId === node.id;
            const isConnected = connectedNodeIds.size === 0 || connectedNodeIds.has(node.id);
            const matchesFocusedSystem =
              focusedSystemNeighborhood.size === 0 || focusedSystemNeighborhood.has(node.id);
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
                <circle
                  r={radius}
                  fill={fill}
                  stroke={isSelected ? "#0f172a" : "white"}
                  strokeWidth={isSelected ? 4 : 2}
                  opacity={isConnected && matchesFocusedSystem ? 1 : 0.2}
                  style={{
                    filter: isConnected && connectedNodeIds.size > 0 ? "drop-shadow(0 0 6px currentColor)" : undefined,
                  }}
                />
                <text textAnchor="middle" dominantBaseline="central" fontSize={radius * 0.55} fill="white" fontWeight="700">
                  {node.integration_count}
                </text>
                <text textAnchor="middle" y={radius + 14} fontSize={11} fontWeight="500" fill="var(--color-text-primary)">
                  {node.label}
                </text>
                <text textAnchor="middle" y={radius + 26} fontSize={9} fill="var(--color-text-muted)">
                  {node.brands.length} brand{node.brands.length === 1 ? "" : "s"}
                </text>
              </g>
            );
          })}

          {hoveredNodeId ? (
            (() => {
              const position = positions[hoveredNodeId];
              const node = graph.nodes.find((entry) => entry.id === hoveredNodeId);
              if (!position || !node) {
                return null;
              }
              const radius = nodeRadius(node.integration_count, maxNodeCount);
              return (
                <g transform={`translate(${position.x}, ${position.y - radius - 8})`} pointerEvents="none">
                  <rect
                    x={-80}
                    y={-44}
                    width={160}
                    height={44}
                    rx={6}
                    fill="var(--color-surface)"
                    stroke="var(--color-border)"
                    style={{ filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.15))" }}
                  />
                  <text textAnchor="middle" y={-26} fontSize={11} fontWeight="600" fill="var(--color-text-primary)">
                    {node.label}
                  </text>
                  <text textAnchor="middle" y={-10} fontSize={10} fill="var(--color-text-secondary)">
                    {node.integration_count} integrations
                  </text>
                </g>
              );
            })()
          ) : null}

          {hoveredEdge ? (
            (() => {
              const source = positions[hoveredEdge.source];
              const target = positions[hoveredEdge.target];
              if (!source || !target) {
                return null;
              }
              return (
                <text
                  x={(source.x + target.x) / 2}
                  y={(source.y + target.y) / 2 - 8}
                  textAnchor="middle"
                  fontSize={10}
                  fill="var(--color-text-secondary)"
                  className="pointer-events-none select-none"
                >
                  {hoveredEdge.integration_count} integration{hoveredEdge.integration_count === 1 ? "" : "s"}
                </text>
              );
            })()
          ) : null}
          </g>
        </svg>

      <div className="pointer-events-none absolute bottom-4 left-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3 text-xs text-[var(--color-text-secondary)]">
        <div className="mb-2 font-semibold text-[var(--color-text-primary)]">Legend</div>
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-[#22c55e]" />
          All OK
        </div>
        <div className="mt-1 flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-[#f97316]" />
          All REVISAR
        </div>
        <div className="mt-1 flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-[#eab308]" />
          Mixed
        </div>
        <div className="mt-2 border-t border-[var(--color-border)] pt-2">Node size = integration count</div>
        <div>Edge width = connection count</div>
      </div>
    </div>
  );
}
