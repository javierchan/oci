"use client";

/* Interactive system dependency map page backed by the catalog graph endpoint. */

import { use, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { GraphControls } from "@/components/graph-controls";
import { GraphDetailPanel } from "@/components/graph-detail-panel";
import { IntegrationGraph } from "@/components/integration-graph";
import { api, getErrorMessage } from "@/lib/api";
import { isProjectNotFoundError, projectRootHref } from "@/lib/project-errors";
import { degradedSystemCount, qaTotalsForEdges } from "@/lib/topology";
import type { TopologyLayoutMode } from "@/lib/topology";
import type { GraphEdge, GraphNode, GraphParams, GraphResponse } from "@/lib/types";

type GraphPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

const EMPTY_GRAPH: GraphResponse = {
  nodes: [],
  edges: [],
  meta: {
    node_count: 0,
    edge_count: 0,
    integration_count: 0,
    business_processes: [],
    brands: [],
  },
};

function normalizeGraphResponse(value: unknown): GraphResponse {
  if (typeof value !== "object" || value === null) {
    return EMPTY_GRAPH;
  }

  const candidate = value as Partial<GraphResponse>;
  const nodes = Array.isArray(candidate.nodes) ? candidate.nodes : EMPTY_GRAPH.nodes;
  const edges = Array.isArray(candidate.edges) ? candidate.edges : EMPTY_GRAPH.edges;
  const meta = candidate.meta;
  const integrationCount = edges.reduce(
    (total, edge) => total + (typeof edge.integration_count === "number" ? edge.integration_count : 0),
    0,
  );

  return {
    nodes,
    edges,
    meta:
      typeof meta === "object" && meta !== null
        ? {
            node_count: typeof meta.node_count === "number" ? meta.node_count : nodes.length,
            edge_count: typeof meta.edge_count === "number" ? meta.edge_count : edges.length,
            integration_count:
              typeof meta.integration_count === "number" ? meta.integration_count : integrationCount,
            business_processes: Array.isArray(meta.business_processes) ? meta.business_processes : [],
            brands: Array.isArray(meta.brands) ? meta.brands : [],
          }
        : {
            ...EMPTY_GRAPH.meta,
            node_count: nodes.length,
            edge_count: edges.length,
            integration_count: integrationCount,
          },
  };
}

export default function GraphPage({ params }: GraphPageProps): JSX.Element {
  const { projectId } = use(params);
  const router = useRouter();
  const svgRef = useRef<SVGSVGElement>(null);
  const [graph, setGraph] = useState<GraphResponse>(EMPTY_GRAPH);
  const [filters, setFilters] = useState<GraphParams>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [selectedSystem, setSelectedSystem] = useState<string>("");
  const [viewport, setViewport] = useState({ x: 0, y: 0, scale: 1 });
  const [homeViewport, setHomeViewport] = useState({ x: 0, y: 0, scale: 1 });
  const [colorMode, setColorMode] = useState<"qa" | "bp">("qa");
  const [layoutMode, setLayoutMode] = useState<TopologyLayoutMode>("cluster");
  const [mode, setMode] = useState<"select" | "pan">("select");
  const missingProjectHref = projectRootHref(projectId);
  const qaTotals = useMemo(() => qaTotalsForEdges(graph.edges), [graph.edges]);
  const degradedSystems = useMemo(() => degradedSystemCount(graph.nodes, graph.edges), [graph.edges, graph.nodes]);
  const selectedPanelNode = selectedNode ?? (selectedSystem ? graph.nodes.find((node) => node.label === selectedSystem) ?? null : null);
  const hasSelection = Boolean(selectedPanelNode || selectedEdge || selectedSystem);

  useEffect(() => {
    let cancelled = false;
    void api
      .getProject(projectId)
      .then(() => {
        return undefined;
      })
      .catch((caughtError: unknown) => {
        if (cancelled) {
          return;
        }
        if (isProjectNotFoundError(caughtError)) {
          router.replace(missingProjectHref);
          return;
        }
        setError(getErrorMessage(caughtError, "Unable to load project."));
      });
    return () => {
      cancelled = true;
    };
  }, [missingProjectHref, projectId, router]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    void api
      .getGraph(projectId, filters)
      .then((response) => {
        if (!cancelled) {
          setGraph(normalizeGraphResponse(response));
          setSelectedNode(null);
          setSelectedEdge(null);
        }
      })
      .catch((caughtError: unknown) => {
        if (!cancelled) {
          if (isProjectNotFoundError(caughtError)) {
            router.replace(missingProjectHref);
            return;
          }
          setError(getErrorMessage(caughtError, "Unable to load dependency graph."));
          setGraph(EMPTY_GRAPH);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [filters, missingProjectHref, projectId, router]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent): void {
      if (event.key.toLowerCase() === "v") {
        setMode("select");
      }
      if (event.key.toLowerCase() === "h") {
        setMode("pan");
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (!selectedSystem) {
      return;
    }
    if (graph.nodes.some((node) => node.label === selectedSystem)) {
      return;
    }
    setSelectedSystem("");
  }, [graph.nodes, selectedSystem]);

  function handleFilterChange(field: keyof GraphParams, value: string): void {
    setFilters((current) => ({
      ...current,
      [field]: value || undefined,
    }));
  }

  function handleSystemChange(value: string): void {
    setSelectedSystem(value);
    setSelectedEdge(null);
    setSelectedNode(value ? graph.nodes.find((node) => node.label === value) ?? null : null);
  }

  function clearSelection(): void {
    setSelectedNode(null);
    setSelectedEdge(null);
    setSelectedSystem("");
  }

  return (
    <div className="mx-auto w-full max-w-none">
      <div className="block sm:hidden app-card p-6 text-center">
        <p className="text-sm text-[var(--color-text-secondary)]">
          The integration map is best viewed on a larger screen.
        </p>
        <p className="mt-2 text-xs text-[var(--color-text-muted)]">
          {graph.nodes.length} systems · {graph.edges.length} connections
        </p>
      </div>

      <section className="hidden h-[calc(100vh-7.25rem)] min-h-[46rem] overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-[0_16px_45px_rgba(15,23,42,0.12)] sm:block">
        <div className="flex h-full min-h-0">
          <div className="relative min-w-0 flex-1">
            <GraphControls
              projectId={projectId}
              filters={filters}
              onFilterChange={handleFilterChange}
              selectedSystem={selectedSystem}
              systemOptions={graph.nodes.map((node) => node.label).sort((left, right) => left.localeCompare(right))}
              onSystemChange={handleSystemChange}
              colorMode={colorMode}
              onColorModeChange={setColorMode}
              layoutMode={layoutMode}
              onLayoutModeChange={setLayoutMode}
              mode={mode}
              onModeChange={setMode}
              zoom={viewport.scale}
              onZoomIn={() => setViewport((current) => ({ ...current, scale: Math.min(current.scale * 1.2, 3.8) }))}
              onZoomOut={() => setViewport((current) => ({ ...current, scale: Math.max(current.scale / 1.2, 0.2) }))}
              onZoomReset={() => setViewport(homeViewport)}
              onClearSelection={clearSelection}
              hasSelection={hasSelection}
              meta={graph.meta}
              qaTotals={qaTotals}
              degradedSystemCount={degradedSystems}
              svgRef={svgRef}
            />

            {loading ? (
              <div className="flex h-full items-center justify-center text-sm font-medium text-[var(--color-text-secondary)]">
                Building live topology...
              </div>
            ) : (
              <IntegrationGraph
                graph={graph}
                selectedNodeId={selectedPanelNode?.id ?? null}
                selectedEdgeId={selectedEdge?.id ?? null}
                onNodeClick={(node) => {
                  setSelectedNode(node);
                  setSelectedEdge(null);
                  setSelectedSystem(node.label);
                }}
                onEdgeClick={(edge) => {
                  setSelectedEdge(edge);
                  setSelectedNode(null);
                  setSelectedSystem("");
                }}
                colorMode={colorMode}
                focusedSystemId={selectedSystem}
                layoutMode={layoutMode}
                svgRef={svgRef}
                mode={mode}
                viewport={viewport}
                onHomeViewportChange={setHomeViewport}
                onViewportChange={setViewport}
              />
            )}

            {graph.nodes.length > 0 && graph.nodes.length < 3 ? (
              <div className="absolute bottom-5 left-5 max-w-xl rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]/95 px-4 py-3 text-sm text-[var(--color-text-secondary)] shadow-sm backdrop-blur">
                <span className="font-medium text-[var(--color-text-primary)]">Limited topology: </span>
                This project&apos;s integrations share fewer than 3 distinct systems.
              </div>
            ) : null}

            {error ? (
              <p className="absolute bottom-5 left-5 max-w-xl rounded-xl border border-rose-200 bg-rose-50/95 px-4 py-3 text-sm font-semibold text-rose-800 shadow-sm dark:border-rose-900 dark:bg-rose-950/80 dark:text-rose-100">
                {error}
              </p>
            ) : null}
          </div>

          {selectedPanelNode || selectedEdge ? (
            <div className="hidden w-[26rem] shrink-0 border-l border-[var(--color-border)] xl:block">
              <GraphDetailPanel
                projectId={projectId}
                graph={graph}
                selectedNode={selectedPanelNode}
                selectedEdge={selectedEdge}
                onClose={clearSelection}
              />
            </div>
          ) : null}
        </div>
      </section>

      {selectedPanelNode || selectedEdge ? (
        <div className="mt-4 overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-sm xl:hidden">
          <GraphDetailPanel
            projectId={projectId}
            graph={graph}
            selectedNode={selectedPanelNode}
            selectedEdge={selectedEdge}
            onClose={clearSelection}
          />
        </div>
      ) : null}
    </div>
  );
}
