"use client";

/* Interactive system dependency map page backed by the catalog graph endpoint. */

import { use, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { Breadcrumb } from "@/components/breadcrumb";
import { GraphControls } from "@/components/graph-controls";
import { GraphDetailPanel } from "@/components/graph-detail-panel";
import { IntegrationGraph } from "@/components/integration-graph";
import { api, getErrorMessage } from "@/lib/api";
import { isProjectNotFoundError, projectRootHref } from "@/lib/project-errors";
import type { GraphEdge, GraphNode, GraphParams, GraphResponse } from "@/lib/types";
import type { Project } from "@/lib/types";

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

export default function GraphPage({ params }: GraphPageProps): JSX.Element {
  const { projectId } = use(params);
  const router = useRouter();
  const svgRef = useRef<SVGSVGElement>(null);
  const [graph, setGraph] = useState<GraphResponse>(EMPTY_GRAPH);
  const [project, setProject] = useState<Project | null>(null);
  const [filters, setFilters] = useState<GraphParams>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [selectedSystem, setSelectedSystem] = useState<string>("");
  const [viewport, setViewport] = useState({ x: 0, y: 0, scale: 1 });
  const [homeViewport, setHomeViewport] = useState({ x: 0, y: 0, scale: 1 });
  const [colorMode, setColorMode] = useState<"qa" | "bp">("qa");
  const [mode, setMode] = useState<"select" | "pan">("select");
  const compactTopology = graph.nodes.length > 0 && graph.nodes.length <= 8;
  const [autoFocusSignature, setAutoFocusSignature] = useState<string>("");

  const rankedSystems = useMemo(() => {
    const connectionCounts = new Map<string, number>();
    graph.edges.forEach((edge) => {
      connectionCounts.set(edge.source, (connectionCounts.get(edge.source) ?? 0) + edge.integration_count);
      connectionCounts.set(edge.target, (connectionCounts.get(edge.target) ?? 0) + edge.integration_count);
    });

    return [...graph.nodes]
      .map((node) => ({
        label: node.label,
        score:
          (connectionCounts.get(node.id) ?? 0) +
          node.integration_count * 4 +
          node.business_processes.length * 2,
      }))
      .sort((left, right) => right.score - left.score || left.label.localeCompare(right.label));
  }, [graph.edges, graph.nodes]);

  const recommendedSystems = rankedSystems.slice(0, 4).map((entry) => entry.label);
  const largeTopology = graph.meta.node_count > 50;
  const stackDetailPanel = compactTopology || largeTopology;
  const missingProjectHref = projectRootHref(projectId);

  useEffect(() => {
    let cancelled = false;
    void api
      .getProject(projectId)
      .then((response) => {
        if (!cancelled) {
          setProject(response);
        }
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
          setGraph(response);
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

  useEffect(() => {
    const suggestedSystem = recommendedSystems[0] ?? "";
    const hasGlobalFilter = Boolean(filters.brand || filters.business_process || filters.qa_status);
    const signature = `${projectId}:${graph.meta.node_count}:${graph.meta.edge_count}:${suggestedSystem}`;

    if (!largeTopology || !suggestedSystem || hasGlobalFilter) {
      if (!largeTopology) {
        setAutoFocusSignature("");
      }
      return;
    }
    if (selectedSystem || autoFocusSignature === signature) {
      return;
    }
    setAutoFocusSignature(signature);
    setSelectedSystem(suggestedSystem);
  }, [
    autoFocusSignature,
    filters.brand,
    filters.business_process,
    filters.qa_status,
    graph.meta.edge_count,
    graph.meta.node_count,
    largeTopology,
    projectId,
    recommendedSystems,
    selectedSystem,
  ]);

  function handleFilterChange(field: keyof GraphParams, value: string): void {
    setFilters((current) => ({
      ...current,
      [field]: value || undefined,
    }));
  }

  return (
    <div className="space-y-6">
      <section className="app-card p-6">
        <p className="app-kicker">System Dependency Map</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          Integration Topology
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Inspect the project as a directed graph of source and destination systems, filter by business process or QA status, and drill back into the catalog from a node or edge.
        </p>
        <div className="mt-4">
          <Breadcrumb
            items={[
              { label: "Home", href: "/projects" },
              { label: "Projects", href: "/projects" },
              { label: project?.name ?? "Project", href: `/projects/${projectId}` },
              { label: "Map" },
            ]}
          />
        </div>
      </section>

      <GraphControls
        projectId={projectId}
        filters={filters}
        onFilterChange={handleFilterChange}
        selectedSystem={selectedSystem}
        systemOptions={graph.nodes.map((node) => node.label).sort((left, right) => left.localeCompare(right))}
        onSystemChange={setSelectedSystem}
        colorMode={colorMode}
        onColorModeChange={setColorMode}
        mode={mode}
        onModeChange={setMode}
        zoom={viewport.scale}
        onZoomIn={() => setViewport((current) => ({ ...current, scale: Math.min(current.scale * 1.2, 4) }))}
        onZoomOut={() => setViewport((current) => ({ ...current, scale: Math.max(current.scale / 1.2, 0.2) }))}
        onZoomReset={() => setViewport(homeViewport)}
        meta={graph.meta}
        svgRef={svgRef}
      />

      {largeTopology ? (
        <section className="rounded-[1.75rem] border border-amber-200 bg-amber-50/90 p-4 dark:border-amber-900 dark:bg-amber-950/30">
          <p className="app-label text-amber-700 dark:text-amber-300">Large Topology Mode</p>
          <div className="mt-3 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <p className="text-sm font-medium text-amber-950 dark:text-amber-100">
                {selectedSystem
                  ? `Starting on ${selectedSystem} and its closest dependency cluster so the first view stays readable.`
                  : `${graph.meta.node_count} systems detected. Use a focus system or a governance filter to simplify the map.`}
              </p>
              <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                The full graph remains available, but background systems stay intentionally quiet so the dependency story is readable.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {recommendedSystems.map((system) => (
                <button
                  key={system}
                  type="button"
                  onClick={() => setSelectedSystem(system)}
                  className={[
                    "rounded-full border px-3 py-1.5 text-xs font-semibold transition",
                    selectedSystem === system
                      ? "border-amber-500 bg-amber-500 text-white"
                      : "border-amber-300 bg-white/70 text-amber-900 hover:border-amber-500 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-100",
                  ].join(" ")}
                >
                  {system}
                </button>
              ))}
              {selectedSystem ? (
                <button
                  type="button"
                  onClick={() => setSelectedSystem("")}
                  className="rounded-full border border-amber-300 px-3 py-1.5 text-xs font-semibold text-amber-900 transition hover:border-amber-500 dark:border-amber-800 dark:text-amber-100"
                >
                  Clear focus
                </button>
              ) : null}
            </div>
          </div>
        </section>
      ) : null}

      {graph.nodes.length < 3 ? (
        <div className="mx-4 mb-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">
          <span className="font-medium text-[var(--color-text-primary)]">Limited topology: </span>
          This project&apos;s integrations share fewer than 3 distinct systems. Import a workbook with varied source and
          destination system names to see the full dependency map.
        </div>
      ) : null}

      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      <div className={stackDetailPanel ? "space-y-6" : "grid gap-6 xl:grid-cols-[1.45fr_0.55fr]"}>
        <div className="space-y-4">
          <section className="grid gap-4 md:grid-cols-3">
            <article className="app-card p-5">
              <p className="app-label">Nodes</p>
              <p className="mt-3 text-3xl font-semibold text-[var(--color-text-primary)]">{graph.meta.node_count}</p>
            </article>
            <article className="app-card p-5">
              <p className="app-label">Edges</p>
              <p className="mt-3 text-3xl font-semibold text-[var(--color-text-primary)]">{graph.meta.edge_count}</p>
            </article>
            <article className="app-card p-5">
              <p className="app-label">Integrations</p>
              <p className="mt-3 text-3xl font-semibold text-[var(--color-text-primary)]">{graph.meta.integration_count}</p>
            </article>
          </section>

          {loading ? (
            <div className="app-card p-10 text-sm text-[var(--color-text-secondary)]">
              Building force layout…
            </div>
          ) : (
            <>
              <div className="block sm:hidden app-card p-6 text-center">
                <p className="text-sm text-[var(--color-text-secondary)]">
                  The integration map is best viewed on a larger screen.
                </p>
                <p className="mt-2 text-xs text-[var(--color-text-muted)]">
                  {graph.nodes.length} systems · {graph.edges.length} connections
                </p>
              </div>
              <div className="hidden sm:block">
                <IntegrationGraph
                  graph={graph}
                  selectedNodeId={selectedNode?.id ?? null}
                  selectedEdgeId={selectedEdge?.id ?? null}
                  onNodeClick={(node) => {
                    setSelectedNode(node);
                    setSelectedEdge(null);
                  }}
                  onEdgeClick={(edge) => {
                    setSelectedEdge(edge);
                    setSelectedNode(null);
                  }}
                  colorMode={colorMode}
                  focusedSystemId={selectedSystem}
                  svgRef={svgRef}
                  mode={mode}
                  viewport={viewport}
                  onHomeViewportChange={setHomeViewport}
                  onViewportChange={setViewport}
                />
              </div>
            </>
          )}
        </div>
        {stackDetailPanel ? null : (
          <GraphDetailPanel
            projectId={projectId}
            graph={graph}
            selectedNode={selectedNode}
            selectedEdge={selectedEdge}
          />
        )}
      </div>

      {stackDetailPanel ? (
        <GraphDetailPanel
          projectId={projectId}
          graph={graph}
          selectedNode={selectedNode}
          selectedEdge={selectedEdge}
        />
      ) : null}
    </div>
  );
}
