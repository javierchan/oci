"use client";

/* React + SVG renderer for the system dependency graph using D3 force layout only for positioning. */

import { useEffect, useMemo, useState } from "react";
import type { RefObject } from "react";
import * as d3 from "d3";

import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/types";

type IntegrationGraphProps = {
  graph: GraphResponse;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  onNodeClick: (node: GraphNode) => void;
  onEdgeClick: (edge: GraphEdge) => void;
  zoom: number;
  colorMode: "qa" | "bp";
  svgRef: RefObject<SVGSVGElement>;
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
  zoom,
  colorMode,
  svgRef,
}: IntegrationGraphProps): JSX.Element {
  const [positions, setPositions] = useState<Record<string, Position>>({});

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

  return (
    <div className="overflow-auto rounded-[2rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4 shadow-sm">
      <div style={{ transform: `scale(${zoom})`, transformOrigin: "top left", width: WIDTH, height: HEIGHT }}>
        <svg ref={svgRef} width={WIDTH} height={HEIGHT} className="block">
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 z" fill="var(--color-text-muted)" />
            </marker>
          </defs>

          {graph.edges.map((edge) => {
            const source = positions[edge.source];
            const target = positions[edge.target];
            if (!source || !target) {
              return null;
            }
            return (
              <g key={edge.id} onClick={() => onEdgeClick(edge)} style={{ cursor: "pointer" }}>
                <line
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  strokeWidth={edgeWidth(edge.integration_count, maxEdgeCount)}
                  stroke={EDGE_COLORS[edge.dominant_qa_status] ?? "#d1d5db"}
                  markerEnd="url(#arrow)"
                  opacity={selectedEdgeId && selectedEdgeId !== edge.id ? 0.35 : 0.9}
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
            return (
              <g
                key={node.id}
                transform={`translate(${position.x}, ${position.y})`}
                onClick={() => onNodeClick(node)}
                style={{ cursor: "pointer" }}
              >
                <circle
                  r={radius}
                  fill={fill}
                  stroke={isSelected ? "#0f172a" : "white"}
                  strokeWidth={isSelected ? 4 : 2}
                />
                <text textAnchor="middle" dy={4} fontSize={10} fill="white" fontWeight="bold">
                  {node.integration_count}
                </text>
                <text textAnchor="middle" dy={radius + 14} fontSize={11} fill="var(--color-text-primary)">
                  {node.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
