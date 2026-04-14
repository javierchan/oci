"use client";

/* React + SVG renderer for the system dependency graph using D3 force layout only for positioning. */

import { useEffect, useMemo, useState } from "react";
import type { RefObject } from "react";
import * as d3 from "d3";

import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/types";

type GraphMode = "select" | "pan";

type IntegrationGraphProps = {
  graph: GraphResponse;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  onNodeClick: (node: GraphNode) => void;
  onEdgeClick: (edge: GraphEdge) => void;
  colorMode: "qa" | "bp";
  svgRef: RefObject<SVGSVGElement>;
  mode: GraphMode;
  viewport: { x: number; y: number; scale: number };
  onViewportChange: (
    updater:
      | { x: number; y: number; scale: number }
      | ((current: { x: number; y: number; scale: number }) => { x: number; y: number; scale: number }),
  ) => void;
};

type Position = {
  id: string;
  x: number;
  y: number;
};

type SimNode = d3.SimulationNodeDatum & GraphNode;
type SimEdge = d3.SimulationLinkDatum<SimNode> & GraphEdge;

const WIDTH = 1200;
const HEIGHT = 760;
const EDGE_COLORS: Record<string, string> = {
  OK: "#86efac",
  REVISAR: "#fde047",
  PENDING: "#d1d5db",
};
const BP_COLORS = ["#0ea5e9", "#22c55e", "#f97316", "#eab308", "#8b5cf6", "#ef4444", "#14b8a6", "#f43f5e"];

function edgeWidth(integrationCount: number, maxCount: number): number {
  if (maxCount === 0) {
    return 1.5;
  }
  return 1.5 + (integrationCount / maxCount) * 4.5;
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

  const maxNodeCount = useMemo(
    () => Math.max(1, ...graph.nodes.map((node) => node.integration_count)),
    [graph.nodes],
  );
  const maxEdgeCount = useMemo(
    () => Math.max(1, ...graph.edges.map((edge) => edge.integration_count)),
    [graph.edges],
  );

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
      .force("center", d3.forceCenter(WIDTH / 2, HEIGHT / 2))
      .force(
        "collision",
        d3.forceCollide<SimNode>().radius((datum) => nodeRadius(datum.integration_count, maxNodeCount) + 20),
      );

    sim.tick(300);
    sim.stop();

    setPositions(
      Object.fromEntries(
        nodes.map((node) => [
          node.id,
          {
            id: node.id,
            x: node.x ?? WIDTH / 2,
            y: node.y ?? HEIGHT / 2,
          },
        ]),
      ),
    );
  }, [graph, maxNodeCount]);

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

  function handleWheel(event: React.WheelEvent<HTMLDivElement>): void {
    event.preventDefault();
    const svg = svgRef.current;
    if (!svg) {
      return;
    }
    const delta = event.deltaY > 0 ? 0.9 : 1.1;
    const rect = svg.getBoundingClientRect();
    const cx = event.clientX - rect.left;
    const cy = event.clientY - rect.top;
    onViewportChange((current) => {
      const nextScale = Math.min(Math.max(current.scale * delta, 0.2), 4);
      return {
        scale: nextScale,
        x: cx - (cx - current.x) * (nextScale / current.scale),
        y: cy - (cy - current.y) * (nextScale / current.scale),
      };
    });
  }

  return (
    <div
      className={[
        "relative overflow-hidden rounded-[2rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4 shadow-sm",
        mode === "pan" ? (isDragging ? "cursor-grabbing" : "cursor-grab") : "cursor-default",
      ].join(" ")}
      onWheel={handleWheel}
    >
      <svg
        ref={svgRef}
        width={WIDTH}
        height={HEIGHT}
        className="block"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" fill="var(--color-text-muted)" />
            </marker>
          </defs>

          <g transform={`translate(${viewport.x}, ${viewport.y}) scale(${viewport.scale})`}>
          {graph.edges.map((edge) => {
            const source = positions[edge.source];
            const target = positions[edge.target];
            if (!source || !target) {
              return null;
            }
            const isHovered = hoveredEdgeId === edge.id;
            const isConnectedToHoveredNode = activeNodeId
              ? edge.source === activeNodeId || edge.target === activeNodeId
              : false;
            const shouldDim =
              (!!hoveredEdgeId && !isHovered) || (!!activeNodeId && !isConnectedToHoveredNode && !isHovered);
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
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  className={!shouldDim ? "graph-edge-animated" : undefined}
                  strokeWidth={edgeWidth(edge.integration_count, maxEdgeCount) * (isHovered ? 1.5 : 1)}
                  stroke={EDGE_COLORS[edge.dominant_qa_status] ?? "#d1d5db"}
                  markerEnd="url(#arrow)"
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
                  opacity={isConnected ? 1 : 0.3}
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

      <div className="absolute bottom-4 left-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3 text-xs text-[var(--color-text-secondary)]">
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
