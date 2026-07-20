"use client";

/* SVG topology map that ports the redesign's "Map, not the list" concept to real graph data. */

import Link from "next/link";
import { useMemo, useState } from "react";

import { AiReviewButton } from "@/components/ai-review-button";
import { CatalogIcon, GraphIcon, SearchIcon } from "@/components/icons";
import { displayQaStatus } from "@/lib/format";
import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/types";

type TopologyCanvasProps = {
  projectId: string;
  graph: GraphResponse;
};

type DomainTone = {
  stroke: string;
  fill: string;
  text: string;
};

type DomainCluster = {
  id: string;
  label: string;
  tone: DomainTone;
  x: number;
  y: number;
  width: number;
  height: number;
  nodes: LayoutNode[];
};

type LayoutNode = GraphNode & {
  domain: string;
  x: number;
  y: number;
  radius: number;
  shortLabel: string;
  hub: boolean;
};

type LayoutEdge = GraphEdge & {
  sourceNode: LayoutNode;
  targetNode: LayoutNode;
  tone: EdgeTone;
  strokeWidth: number;
  dash: string | undefined;
  patternMode: PatternMode;
  midpointX: number;
  midpointY: number;
  controlX: number;
  controlY: number;
};

type EdgeTone = "ok" | "review" | "pending" | "mixed";
type PatternMode = "sync" | "async" | "both";
type QaFilter = "all" | EdgeTone;

const VIEWBOX_WIDTH = 1440;
const VIEWBOX_HEIGHT = 820;

const DOMAIN_TONES: DomainTone[] = [
  { stroke: "var(--node-system)", fill: "var(--pat-sync-bg)", text: "var(--pat-sync)" },
  { stroke: "var(--node-oic)", fill: "var(--pat-async-bg)", text: "var(--pat-async)" },
  { stroke: "var(--node-fn)", fill: "var(--ok-bg)", text: "var(--ok)" },
  { stroke: "var(--node-stream)", fill: "var(--warn-bg)", text: "var(--warn)" },
  { stroke: "var(--node-storage)", fill: "var(--err-bg)", text: "var(--err)" },
  { stroke: "var(--node-gw)", fill: "var(--info-bg)", text: "var(--info)" },
  { stroke: "var(--node-db)", fill: "var(--surface-2)", text: "var(--ink-2)" },
];

const CLUSTER_SLOTS = [
  { x: 54, y: 78, width: 306, height: 260 },
  { x: 392, y: 52, width: 306, height: 260 },
  { x: 736, y: 78, width: 306, height: 260 },
  { x: 1078, y: 96, width: 306, height: 242 },
  { x: 72, y: 442, width: 330, height: 278 },
  { x: 454, y: 456, width: 330, height: 278 },
  { x: 836, y: 442, width: 330, height: 278 },
  { x: 1198, y: 452, width: 190, height: 268 },
];

const EDGE_COLOR: Record<EdgeTone, string> = {
  ok: "var(--ok)",
  review: "var(--warn)",
  pending: "var(--err)",
  mixed: "var(--signal)",
};

const EDGE_LABEL: Record<EdgeTone, string> = {
  ok: "OK",
  review: "Review",
  pending: "Pending",
  mixed: "Mixed",
};

const EDGE_SWATCH_CLASS: Record<EdgeTone, string> = {
  ok: "bg-[var(--ok)]",
  review: "bg-[var(--warn)]",
  pending: "bg-[var(--err)]",
  mixed: "bg-[var(--signal)]",
};

function slug(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function truncate(value: string, maxLength: number): string {
  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}…` : value;
}

function resolveDomain(node: GraphNode): string {
  const label = node.label.toLowerCase();
  const candidates = [
    "Data Platform",
    "Human Capital",
    "Supply Chain",
    "Marketplace",
    "Logistics",
    "Identity",
    "Finance",
    "Retail",
  ];
  const match = candidates.find((candidate) => label.startsWith(candidate.toLowerCase()));
  if (match) {
    return match;
  }
  const processDomain = node.business_processes[0]?.split(" — ")[1]?.split(" to ")[0]?.trim();
  return processDomain || node.brands[0] || "Enterprise Services";
}

function edgeTone(edge: GraphEdge): EdgeTone {
  if (edge.dominant_qa_status === "OK") {
    return "ok";
  }
  if (edge.dominant_qa_status === "REVISAR") {
    return "review";
  }
  if (edge.dominant_qa_status === "PENDING") {
    return "pending";
  }
  return "mixed";
}

function patternMode(edge: GraphEdge): PatternMode {
  const values = edge.patterns.join(" ").toLowerCase();
  const hasAsync =
    values.includes("#02") ||
    values.includes("#05") ||
    values.includes("#08") ||
    values.includes("#09") ||
    values.includes("#14") ||
    values.includes("#16") ||
    values.includes("#17") ||
    values.includes("event") ||
    values.includes("cdc") ||
    values.includes("webhook") ||
    values.includes("async");
  const hasSync =
    values.includes("#01") ||
    values.includes("#04") ||
    values.includes("#10") ||
    values.includes("#11") ||
    values.includes("#13") ||
    values.includes("request") ||
    values.includes("api") ||
    values.includes("sync");
  if (hasAsync && hasSync) {
    return "both";
  }
  if (hasAsync) {
    return "async";
  }
  return "sync";
}

function edgeDash(mode: PatternMode): string | undefined {
  if (mode === "async") {
    return "6 5";
  }
  if (mode === "both") {
    return "10 4 2 4";
  }
  return undefined;
}

function radiusForNode(count: number, maxCount: number): number {
  if (maxCount <= 0) {
    return 16;
  }
  return 15 + Math.round((count / maxCount) * 10);
}

function widthForEdge(count: number, maxCount: number): number {
  if (maxCount <= 1) {
    return 2.4;
  }
  const normalized = Math.log(count + 1) / Math.log(maxCount + 1);
  return Math.min(8, Math.max(1.5, 1.5 + normalized * 6.5));
}

function layoutNodesInCluster(
  nodes: GraphNode[],
  slot: (typeof CLUSTER_SLOTS)[number],
  domain: string,
  maxCount: number,
): LayoutNode[] {
  const columns = nodes.length <= 4 ? 2 : nodes.length <= 9 ? 3 : 4;
  const rows = Math.max(1, Math.ceil(nodes.length / columns));
  const gapX = slot.width / (columns + 1);
  const gapY = Math.max(44, (slot.height - 62) / (rows + 1));

  return nodes.map((node, index) => {
    const row = Math.floor(index / columns);
    const column = index % columns;
    return {
      ...node,
      domain,
      x: slot.x + gapX * (column + 1),
      y: slot.y + 58 + gapY * (row + 1),
      radius: radiusForNode(node.integration_count, maxCount),
      shortLabel: truncate(node.label.replace(domain, "").trim() || node.label, 18),
      hub: node.label.toLowerCase().includes("integration") || node.integration_count >= maxCount * 0.92,
    };
  });
}

function buildLayout(graph: GraphResponse): { clusters: DomainCluster[]; edges: LayoutEdge[] } {
  const maxNodeCount = Math.max(1, ...graph.nodes.map((node) => node.integration_count));
  const maxEdgeCount = Math.max(1, ...graph.edges.map((edge) => edge.integration_count));
  const grouped = new Map<string, GraphNode[]>();

  graph.nodes.forEach((node) => {
    const domain = resolveDomain(node);
    grouped.set(domain, [...(grouped.get(domain) ?? []), node]);
  });

  const orderedGroups = [...grouped.entries()].sort((left, right) => {
    if (right[1].length !== left[1].length) {
      return right[1].length - left[1].length;
    }
    return left[0].localeCompare(right[0]);
  });

  const clusters = orderedGroups.map(([domain, nodes], index) => {
    const slot = CLUSTER_SLOTS[index % CLUSTER_SLOTS.length];
    const tone = DOMAIN_TONES[index % DOMAIN_TONES.length];
    const sortedNodes = [...nodes].sort(
      (left, right) => right.integration_count - left.integration_count || left.label.localeCompare(right.label),
    );
    return {
      id: slug(domain),
      label: domain,
      tone,
      ...slot,
      nodes: layoutNodesInCluster(sortedNodes, slot, domain, maxNodeCount),
    };
  });

  const nodeIndex = new Map<string, LayoutNode>();
  clusters.forEach((cluster) => {
    cluster.nodes.forEach((node) => nodeIndex.set(node.id, node));
  });

  const edges = graph.edges
    .map((edge): LayoutEdge | null => {
      const sourceNode = nodeIndex.get(edge.source);
      const targetNode = nodeIndex.get(edge.target);
      if (!sourceNode || !targetNode) {
        return null;
      }
      const dx = targetNode.x - sourceNode.x;
      const dy = targetNode.y - sourceNode.y;
      const mode = patternMode(edge);
      return {
        ...edge,
        sourceNode,
        targetNode,
        tone: edgeTone(edge),
        strokeWidth: widthForEdge(edge.integration_count, maxEdgeCount),
        dash: edgeDash(mode),
        patternMode: mode,
        midpointX: (sourceNode.x + targetNode.x) / 2,
        midpointY: (sourceNode.y + targetNode.y) / 2,
        controlX: (sourceNode.x + targetNode.x) / 2 + dy * 0.08,
        controlY: (sourceNode.y + targetNode.y) / 2 - dx * 0.08,
      };
    })
    .filter((edge): edge is LayoutEdge => edge !== null)
    .sort((left, right) => left.integration_count - right.integration_count);

  return { clusters, edges };
}

function edgePath(edge: LayoutEdge): string {
  return `M ${edge.sourceNode.x} ${edge.sourceNode.y} Q ${edge.controlX} ${edge.controlY} ${edge.targetNode.x} ${edge.targetNode.y}`;
}

export function TopologyCanvas({ projectId, graph }: TopologyCanvasProps): JSX.Element {
  const [selectedNodeId, setSelectedNodeId] = useState<string>("");
  const [selectedEdgeId, setSelectedEdgeId] = useState<string>("");
  const [qaFilter, setQaFilter] = useState<QaFilter>("all");
  const { clusters, edges } = useMemo(() => buildLayout(graph), [graph]);
  const selectedNode = clusters.flatMap((cluster) => cluster.nodes).find((node) => node.id === selectedNodeId) ?? null;
  const selectedEdge = edges.find((edge) => edge.id === selectedEdgeId) ?? null;
  const activeEdgeIds = new Set(
    selectedNode
      ? edges
          .filter((edge) => edge.source === selectedNode.id || edge.target === selectedNode.id)
          .map((edge) => edge.id)
      : selectedEdge
        ? [selectedEdge.id]
        : [],
  );
  const filteredEdges = qaFilter === "all" ? edges : edges.filter((edge) => edge.tone === qaFilter);
  const selectedContextActive = selectedNode !== null || selectedEdge !== null;
  const topEdgeIds = new Set(
    [...filteredEdges]
      .sort((left, right) => right.integration_count - left.integration_count || left.id.localeCompare(right.id))
      .slice(0, 140)
      .map((edge) => edge.id),
  );
  const visibleEdges = selectedContextActive
    ? filteredEdges.filter((edge) => activeEdgeIds.has(edge.id))
    : filteredEdges.filter((edge) => topEdgeIds.has(edge.id));
  const selectedItem = selectedEdge ?? selectedNode;
  function selectNode(node: LayoutNode): void {
    setSelectedNodeId(node.id);
    setSelectedEdgeId("");
  }

  function selectEdge(edge: LayoutEdge): void {
    setSelectedEdgeId(edge.id);
    setSelectedNodeId("");
  }

  return (
    <section className="relative overflow-hidden rounded-[2rem] border border-[var(--line)] bg-[var(--bg)] shadow-2">
      <div className="grid min-h-[760px] 2xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="relative min-h-[760px] overflow-hidden">
          <div className="absolute left-4 right-4 top-4 z-10 flex flex-wrap items-start justify-between gap-3">
            <div className="rounded-pill border border-[var(--line)] bg-[var(--surface)]/95 px-3 py-2 text-xs text-[var(--ink-2)] shadow-1 backdrop-blur">
              <span className="mr-2 inline-block h-1.5 w-1.5 rounded-full bg-[var(--ok)]" />
              <span className="font-semibold text-[var(--ink-1)]">Live topology</span>
              <span className="text-[var(--ink-3)]">
                {" "}
                · {graph.meta.integration_count} integrations · {graph.meta.node_count} systems · showing{" "}
                {visibleEdges.length}/{filteredEdges.length} edges
              </span>
            </div>
            <div className="flex flex-wrap gap-2 rounded-pill border border-[var(--line)] bg-[var(--surface)]/95 p-1 shadow-1 backdrop-blur">
              {(["all", "ok", "review", "pending", "mixed"] as QaFilter[]).map((filter) => (
                <button
                  key={filter}
                  type="button"
                  onClick={() => setQaFilter(filter)}
                  className={[
                    "rounded-pill px-3 py-1 text-xs font-semibold transition",
                    qaFilter === filter
                      ? "bg-[var(--ink-1)] text-[var(--surface)]"
                      : "text-[var(--ink-2)] hover:bg-[var(--hover)] hover:text-[var(--ink-1)]",
                  ].join(" ")}
                >
                  {filter === "all" ? "All QA" : EDGE_LABEL[filter]}
                </button>
              ))}
            </div>
          </div>

          <svg
            viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
            preserveAspectRatio="xMidYMid meet"
            className="h-full min-h-[760px] w-full"
            role="img"
            aria-label="Project topology map grouped by domain"
          >
            <defs>
              {(["ok", "review", "pending", "mixed"] as EdgeTone[]).map((tone) => (
                <marker
                  key={tone}
                  id={`topology-arrow-${tone}`}
                  markerWidth="16"
                  markerHeight="16"
                  refX="14"
                  refY="8"
                  orient="auto"
                  markerUnits="userSpaceOnUse"
                >
                  <path d="M1,1 L1,15 L15,8 z" fill={EDGE_COLOR[tone]} />
                </marker>
              ))}
              <pattern id="topology-dots" width="24" height="24" patternUnits="userSpaceOnUse">
                <circle cx="2" cy="2" r="1" fill="var(--line-strong)" opacity="0.35" />
              </pattern>
            </defs>
            <rect width={VIEWBOX_WIDTH} height={VIEWBOX_HEIGHT} fill="url(#topology-dots)" opacity="0.75" />

            {clusters.map((cluster) => (
              <g key={cluster.id}>
                <rect
                  x={cluster.x}
                  y={cluster.y}
                  width={cluster.width}
                  height={cluster.height}
                  rx="22"
                  fill={cluster.tone.fill}
                  fillOpacity="0.55"
                  stroke={cluster.tone.stroke}
                  strokeOpacity="0.22"
                  strokeWidth="1.5"
                  strokeDasharray="3 4"
                />
                <text
                  x={cluster.x + 16}
                  y={cluster.y + 28}
                  fill={cluster.tone.text}
                  className="fill-current font-mono text-[11px] font-bold uppercase tracking-[0.22em]"
                >
                  {cluster.label}
                </text>
              </g>
            ))}

            <g>
              {visibleEdges.map((edge) => {
                const active = selectedEdge?.id === edge.id || activeEdgeIds.has(edge.id);
                const dimmed = selectedItem !== null && !active;
                return (
                  <g key={edge.id}>
                    {active ? (
                      <path
                        d={edgePath(edge)}
                        fill="none"
                        stroke={EDGE_COLOR[edge.tone]}
                        strokeWidth={edge.strokeWidth + 9}
                        strokeLinecap="round"
                        strokeOpacity="0.14"
                      />
                    ) : null}
                    <path
                      d={edgePath(edge)}
                      fill="none"
                      stroke={EDGE_COLOR[edge.tone]}
                      strokeWidth={edge.strokeWidth}
                      strokeLinecap="round"
                      strokeOpacity={dimmed ? 0.05 : active ? 0.94 : 0.42}
                      strokeDasharray={edge.dash}
                      markerEnd={`url(#topology-arrow-${edge.tone})`}
                      className="cursor-pointer transition-opacity"
                      role="button"
                      tabIndex={0}
                      aria-label={`${edge.sourceNode.label} to ${edge.targetNode.label}, ${edge.integration_count} integrations`}
                      onClick={() => selectEdge(edge)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          selectEdge(edge);
                        }
                      }}
                    />
                  </g>
                );
              })}
            </g>

            {clusters.map((cluster) => (
              <g key={`${cluster.id}-nodes`}>
                {cluster.nodes.map((node) => {
                  const active = selectedNode?.id === node.id;
                  const dimmed = selectedEdge !== null && selectedEdge.source !== node.id && selectedEdge.target !== node.id;
                  return (
                    <g
                      key={node.id}
                      transform={`translate(${node.x}, ${node.y})`}
                      className="cursor-pointer"
                      role="button"
                      tabIndex={0}
                      aria-label={`${node.label}, ${node.integration_count} integrations`}
                      onClick={() => selectNode(node)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          selectNode(node);
                        }
                      }}
                      opacity={dimmed ? 0.3 : 1}
                    >
                      {node.hub ? (
                        <circle
                          r={node.radius + 9}
                          fill="none"
                          stroke={cluster.tone.stroke}
                          strokeWidth="1.5"
                          strokeOpacity="0.38"
                          strokeDasharray="2 4"
                        />
                      ) : null}
                      {active ? (
                        <circle r={node.radius + 7} fill="none" stroke="var(--ink-1)" strokeWidth="2.5" />
                      ) : null}
                      <circle r={node.radius} fill="var(--surface)" stroke={cluster.tone.stroke} strokeWidth="2.5" />
                      <circle r={Math.max(7, node.radius - 7)} fill={cluster.tone.stroke} fillOpacity="0.13" />
                      <text
                        y="-1"
                        textAnchor="middle"
                        fill="var(--ink-1)"
                        className="font-display text-[10px] font-bold"
                      >
                        {node.shortLabel.split(" ")[0] ?? "System"}
                      </text>
                      <text
                        y="12"
                        textAnchor="middle"
                        fill={cluster.tone.text}
                        className="font-mono text-[9px] font-bold"
                      >
                        {node.integration_count} ix
                      </text>
                      <text
                        y={node.radius + 18}
                        textAnchor="middle"
                        fill="var(--ink-2)"
                        className="font-sans text-[10px] font-semibold"
                      >
                        {node.shortLabel}
                      </text>
                    </g>
                  );
                })}
              </g>
            ))}
          </svg>
        </div>

        <aside className="border-t border-[var(--line)] bg-[var(--surface)] p-5 2xl:border-l 2xl:border-t-0">
          <div className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
              <GraphIcon className="h-4 w-4" />
            </span>
            <div>
              <p className="t-micro">Topology Inspector</p>
              <h2 className="text-lg font-semibold text-[var(--ink-1)]">The Map</h2>
            </div>
          </div>

          {selectedEdge ? (
            <div className="mt-6 space-y-4">
              <div>
                <p className="t-micro">Selected Connection</p>
                <h3 className="mt-2 text-xl font-semibold leading-tight text-[var(--ink-1)]">
                  {selectedEdge.sourceNode.label} → {selectedEdge.targetNode.label}
                </h3>
                <p className="mt-2 text-sm text-[var(--ink-2)]">
                  {selectedEdge.integration_count} governed integrations. QA majority:{" "}
                  {displayQaStatus(selectedEdge.dominant_qa_status)}.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="card-quiet p-3">
                  <p className="t-micro">Pattern</p>
                  <p className="mt-2 text-sm font-semibold capitalize text-[var(--ink-1)]">{selectedEdge.patternMode}</p>
                </div>
                <div className="card-quiet p-3">
                  <p className="t-micro">Thickness</p>
                  <p className="mt-2 text-sm font-semibold text-[var(--ink-1)]">Volume-weighted</p>
                </div>
              </div>
              <div>
                <p className="t-micro">Sample Flows</p>
                <div className="mt-3 space-y-2">
                  {selectedEdge.integration_names.slice(0, 4).map((name) => (
                    <p key={name} className="rounded-md border border-[var(--line)] bg-[var(--surface-2)] px-3 py-2 text-xs text-[var(--ink-2)]">
                      {name}
                    </p>
                  ))}
                </div>
              </div>
              <Link
                href={`/projects/${projectId}/catalog/${selectedEdge.integration_ids[0] ?? ""}`}
                className="btn btn--accent w-full"
              >
                Open leading integration
              </Link>
              <AiReviewButton
                projectId={projectId}
                graphContext={{
                  type: "edge",
                  source: selectedEdge.sourceNode.label,
                  target: selectedEdge.targetNode.label,
                }}
              />
            </div>
          ) : selectedNode ? (
            <div className="mt-6 space-y-4">
              <div>
                <p className="t-micro">Selected System</p>
                <h3 className="mt-2 text-xl font-semibold leading-tight text-[var(--ink-1)]">{selectedNode.label}</h3>
                <p className="mt-2 text-sm text-[var(--ink-2)]">
                  {selectedNode.integration_count} integrations · {selectedNode.as_source_count} outbound ·{" "}
                  {selectedNode.as_destination_count} inbound.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="card-quiet p-3">
                  <p className="t-micro">Domain</p>
                  <p className="mt-2 text-sm font-semibold text-[var(--ink-1)]">{selectedNode.domain}</p>
                </div>
                <div className="card-quiet p-3">
                  <p className="t-micro">Brands</p>
                  <p className="mt-2 text-sm font-semibold text-[var(--ink-1)]">{selectedNode.brands.length}</p>
                </div>
              </div>
              <Link href={`/projects/${projectId}/catalog?system=${encodeURIComponent(selectedNode.label)}`} className="btn btn--accent w-full">
                <SearchIcon className="h-4 w-4" />
                Filter catalog by system
              </Link>
              <AiReviewButton projectId={projectId} graphContext={{ type: "node", label: selectedNode.label }} />
            </div>
          ) : (
            <div className="mt-6 space-y-4">
              <p className="text-sm leading-6 text-[var(--ink-2)]">
                Select a system or connection to inspect dependency evidence, open the catalog, or launch a governed
                architecture review scoped to the map context.
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div className="card-quiet p-3">
                  <p className="t-micro">Systems</p>
                  <p className="mt-2 text-2xl font-semibold text-[var(--ink-1)]">{graph.meta.node_count}</p>
                </div>
                <div className="card-quiet p-3">
                  <p className="t-micro">Edges</p>
                  <p className="mt-2 text-2xl font-semibold text-[var(--ink-1)]">{graph.meta.edge_count}</p>
                </div>
              </div>
              <AiReviewButton projectId={projectId} />
            </div>
          )}

          <div className="mt-8 border-t border-[var(--line)] pt-5">
            <p className="t-micro">Legend</p>
            <div className="mt-3 space-y-2">
              {(["ok", "review", "pending", "mixed"] as EdgeTone[]).map((tone) => (
                <div key={tone} className="flex items-center justify-between gap-3 text-xs text-[var(--ink-2)]">
                  <span className="inline-flex items-center gap-2">
                    <span className={`h-1.5 w-8 rounded-full ${EDGE_SWATCH_CLASS[tone]}`} />
                    {EDGE_LABEL[tone]}
                  </span>
                  <span>QA color</span>
                </div>
              ))}
              <div className="flex items-center justify-between gap-3 text-xs text-[var(--ink-2)]">
                <span className="inline-flex items-center gap-2">
                  <CatalogIcon className="h-4 w-4 text-[var(--accent)]" />
                  Solid / dashed
                </span>
                <span>Flow mode</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
