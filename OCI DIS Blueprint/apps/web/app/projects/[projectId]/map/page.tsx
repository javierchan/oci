"use client";

/* Interactive system dependency map page backed by the catalog graph endpoint. */

import { use, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { GraphControls } from "@/components/graph-controls";
import { GraphDetailPanel } from "@/components/graph-detail-panel";
import { GraphMobileList } from "@/components/graph-mobile-list";
import { GraphTriagePanel } from "@/components/graph-triage-panel";
import { IntegrationGraph } from "@/components/integration-graph";
import { TopologyPulse } from "@/components/topology-pulse";
import { api, getErrorMessage } from "@/lib/api";
import { isProjectNotFoundError, projectRootHref } from "@/lib/project-errors";
import { advanceRiskReview, degradedSystemCount, qaTotalsForEdges } from "@/lib/topology";
import type { TopologyLayoutMode, TopologyMetricMode, TopologyVisibilityMode } from "@/lib/topology";
import { buildTopologyPulseInsights } from "@/lib/topology-insights";
import type { GraphEdge, GraphNode, GraphParams, GraphResponse } from "@/lib/types";

type MapPageProps = {
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
    business_process_families: [],
    brands: [],
    latest_updated_at: null,
    executions_coverage: 0,
    payload_execution_coverage: 0,
    payload_coverage: 0,
  },
};

const REVIEW_SESSION_KEY_PREFIX = "oci-dis-topology-reviewed:";

function normalizeGraphResponse(value: unknown): GraphResponse {
  if (typeof value !== "object" || value === null) {
    return EMPTY_GRAPH;
  }

  const candidate = value as Partial<GraphResponse>;
  const nodes = Array.isArray(candidate.nodes)
    ? candidate.nodes.map((node) => ({
        ...node,
        owners: Array.isArray(node.owners) ? node.owners : [],
        technologies: Array.isArray(node.technologies) ? node.technologies : [],
      }))
    : EMPTY_GRAPH.nodes;
  const edges = Array.isArray(candidate.edges)
    ? candidate.edges.map((edge) => ({
        ...edge,
        risk_qa_status: edge.risk_qa_status ?? edge.dominant_qa_status ?? "PENDING",
        risk_score: typeof edge.risk_score === "number" ? edge.risk_score : edge.integration_count,
        interaction_mode: edge.interaction_mode ?? "UNSPECIFIED",
        total_executions_per_day: edge.total_executions_per_day ?? 0,
        total_payload_per_execution_kb: edge.total_payload_per_execution_kb ?? 0,
        total_payload_per_hour_kb: edge.total_payload_per_hour_kb ?? 0,
        executions_coverage: edge.executions_coverage ?? 0,
        payload_execution_coverage: edge.payload_execution_coverage ?? 0,
        payload_coverage: edge.payload_coverage ?? 0,
        last_updated_at: edge.last_updated_at ?? new Date(0).toISOString(),
        integrations: Array.isArray(edge.integrations)
          ? edge.integrations.map((integration) => ({
              ...integration,
              executions_per_day: integration.executions_per_day ?? null,
              payload_per_execution_kb: integration.payload_per_execution_kb ?? null,
              payload_per_hour_kb: integration.payload_per_hour_kb ?? null,
            }))
          : [],
      }))
    : EMPTY_GRAPH.edges;
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
            business_process_families: Array.isArray(meta.business_process_families) ? meta.business_process_families : [],
            brands: Array.isArray(meta.brands) ? meta.brands : [],
            latest_updated_at: typeof meta.latest_updated_at === "string" ? meta.latest_updated_at : null,
            executions_coverage: typeof meta.executions_coverage === "number" ? meta.executions_coverage : 0,
            payload_execution_coverage:
              typeof meta.payload_execution_coverage === "number" ? meta.payload_execution_coverage : 0,
            payload_coverage: typeof meta.payload_coverage === "number" ? meta.payload_coverage : 0,
          }
        : {
            ...EMPTY_GRAPH.meta,
            node_count: nodes.length,
            edge_count: edges.length,
            integration_count: integrationCount,
          },
  };
}

export default function MapPage({ params }: MapPageProps): JSX.Element {
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
  const [metricMode, setMetricMode] = useState<TopologyMetricMode>("relationships");
  const [visibilityMode, setVisibilityMode] = useState<TopologyVisibilityMode>("priority");
  const [layoutMode, setLayoutMode] = useState<TopologyLayoutMode>("cluster");
  const [mode, setMode] = useState<"select" | "pan">("select");
  const [triageOpen, setTriageOpen] = useState<boolean>(false);
  const [reviewedRiskEdgeIds, setReviewedRiskEdgeIds] = useState<string[]>([]);
  const [reviewSessionProjectId, setReviewSessionProjectId] = useState<string | null>(null);
  const [pulseExpanded, setPulseExpanded] = useState<boolean>(true);
  const [pulseHighlightedEdgeIds, setPulseHighlightedEdgeIds] = useState<string[]>([]);
  const [pulseIntegrationId, setPulseIntegrationId] = useState<string>("");
  const [widePanel, setWidePanel] = useState<boolean>(false);
  const [desktopMap, setDesktopMap] = useState<boolean>(false);
  const missingProjectHref = projectRootHref(projectId);
  const qaTotals = useMemo(() => qaTotalsForEdges(graph.edges), [graph.edges]);
  const degradedSystems = useMemo(() => degradedSystemCount(graph.nodes, graph.edges), [graph.edges, graph.nodes]);
  const selectedPanelNode = selectedNode ?? (selectedSystem ? graph.nodes.find((node) => node.label === selectedSystem) ?? null : null);
  const hasSelection = Boolean(selectedPanelNode || selectedEdge || selectedSystem);
  const riskEdges = useMemo(
    () => graph.edges.filter((edge) => edge.risk_qa_status !== "OK").sort((left, right) => right.risk_score - left.risk_score),
    [graph.edges],
  );
  const reviewedRiskIds = useMemo(() => new Set(reviewedRiskEdgeIds), [reviewedRiskEdgeIds]);
  const reviewedRiskCount = useMemo(
    () => riskEdges.filter((edge) => reviewedRiskIds.has(edge.id)).length,
    [reviewedRiskIds, riskEdges],
  );
  const currentRiskSelected = Boolean(selectedEdge && riskEdges.some((edge) => edge.id === selectedEdge.id));
  const activeFilterCount = Object.values(filters).filter(Boolean).length + (selectedSystem ? 1 : 0);
  const pulseInsights = useMemo(
    () => buildTopologyPulseInsights(graph, {
      metricMode,
      selectedNodeId: selectedPanelNode?.id,
      selectedEdgeId: selectedEdge?.id,
      selectedIntegrationId: pulseIntegrationId,
    }),
    [graph, metricMode, pulseIntegrationId, selectedEdge?.id, selectedPanelNode?.id],
  );

  useEffect(() => {
    const query = window.matchMedia("(min-width: 1536px)");
    const desktopQuery = window.matchMedia("(min-width: 640px)");
    const update = (): void => {
      setWidePanel(query.matches);
      setDesktopMap(desktopQuery.matches);
    };
    update();
    query.addEventListener("change", update);
    desktopQuery.addEventListener("change", update);
    return () => {
      query.removeEventListener("change", update);
      desktopQuery.removeEventListener("change", update);
    };
  }, []);

  useEffect(() => {
    const storageKey = `${REVIEW_SESSION_KEY_PREFIX}${projectId}`;
    try {
      const saved = window.sessionStorage.getItem(storageKey);
      const parsed: unknown = saved ? JSON.parse(saved) : [];
      setReviewedRiskEdgeIds(
        Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === "string") : [],
      );
    } catch {
      setReviewedRiskEdgeIds([]);
    }
    setReviewSessionProjectId(projectId);
  }, [projectId]);

  useEffect(() => {
    if (reviewSessionProjectId !== projectId) {
      return;
    }
    window.sessionStorage.setItem(
      `${REVIEW_SESSION_KEY_PREFIX}${projectId}`,
      JSON.stringify(reviewedRiskEdgeIds),
    );
  }, [projectId, reviewSessionProjectId, reviewedRiskEdgeIds]);

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
          setPulseIntegrationId("");
          setPulseHighlightedEdgeIds([]);
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
      if (event.key === "Escape") {
        setPulseHighlightedEdgeIds([]);
        setPulseIntegrationId("");
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
    setPulseIntegrationId("");
    setPulseHighlightedEdgeIds([]);
    setSelectedNode(value ? graph.nodes.find((node) => node.label === value) ?? null : null);
    setTriageOpen(false);
  }

  function clearSelection(): void {
    setSelectedNode(null);
    setSelectedEdge(null);
    setSelectedSystem("");
    setPulseIntegrationId("");
    setPulseHighlightedEdgeIds([]);
    setTriageOpen(false);
    setViewport(homeViewport);
  }

  function clearFilters(): void {
    setFilters({});
    clearSelection();
  }

  function selectEdge(edge: GraphEdge): void {
    setSelectedEdge(edge);
    setSelectedNode(null);
    setSelectedSystem("");
    setPulseIntegrationId("");
    setPulseHighlightedEdgeIds([]);
    setTriageOpen(false);
  }

  function pinPulseEdge(edgeId: string): void {
    const edge = graph.edges.find((candidate) => candidate.id === edgeId);
    if (edge) {
      selectEdge(edge);
    }
  }

  function reviewNextRisk(): void {
    if (riskEdges.length === 0) {
      return;
    }

    if (reviewedRiskCount >= riskEdges.length) {
      const visibleRiskIds = new Set(riskEdges.map((edge) => edge.id));
      setReviewedRiskEdgeIds((current) => current.filter((id) => !visibleRiskIds.has(id)));
      selectEdge(riskEdges[0]);
      return;
    }

    const step = advanceRiskReview(riskEdges, reviewedRiskEdgeIds, selectedEdge?.id ?? null);
    setReviewedRiskEdgeIds(step.reviewedIds);
    if (step.nextEdge) {
      selectEdge(step.nextEdge);
      return;
    }

    if (step.complete) {
      setSelectedEdge(null);
      setTriageOpen(true);
    }
  }

  return (
    <div className="mx-auto w-full max-w-none">
      {!desktopMap ? <GraphMobileList projectId={projectId} graph={graph} loading={loading} error={error} /> : null}

      {desktopMap ? (
      <section className="relative h-[calc(100vh-7.25rem)] min-h-[40rem] overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] shadow-[0_16px_45px_rgba(15,23,42,0.12)]">
        <div className="flex h-full min-h-0">
          <div className="flex min-w-0 flex-1 flex-col">
            <GraphControls
              projectId={projectId}
              filters={filters}
              onFilterChange={handleFilterChange}
              selectedSystem={selectedSystem}
              systemOptions={graph.nodes.map((node) => node.label).sort((left, right) => left.localeCompare(right))}
              onSystemChange={handleSystemChange}
              colorMode={colorMode}
              onColorModeChange={setColorMode}
              metricMode={metricMode}
              onMetricModeChange={setMetricMode}
              visibilityMode={visibilityMode}
              onVisibilityModeChange={setVisibilityMode}
              layoutMode={layoutMode}
              onLayoutModeChange={setLayoutMode}
              mode={mode}
              onModeChange={setMode}
              zoom={viewport.scale}
              onZoomIn={() => setViewport((current) => ({ ...current, scale: Math.min(current.scale * 1.2, 3.8) }))}
              onZoomOut={() => setViewport((current) => ({ ...current, scale: Math.max(current.scale / 1.2, 0.2) }))}
              onZoomReset={() => setViewport(homeViewport)}
              onClearSelection={clearSelection}
              onClearFilters={clearFilters}
              onOpenTriage={() => {
                setSelectedNode(null);
                setSelectedEdge(null);
                setSelectedSystem("");
                setPulseIntegrationId("");
                setPulseHighlightedEdgeIds([]);
                setTriageOpen(true);
                setViewport(homeViewport);
              }}
              onReviewNext={reviewNextRisk}
              loading={loading}
              hasSelection={hasSelection}
              activeFilterCount={activeFilterCount}
              reviewedRiskCount={reviewedRiskCount}
              currentRiskSelected={currentRiskSelected}
              meta={graph.meta}
              qaTotals={qaTotals}
              degradedSystemCount={degradedSystems}
              riskPathCount={riskEdges.length}
              svgRef={svgRef}
              compact={widePanel && Boolean(selectedPanelNode || selectedEdge || triageOpen)}
            />

            <div className="relative min-h-0 flex-1">
              {!loading && graph.meta.integration_count > 0 ? (
                <div className="pointer-events-none absolute left-3 right-3 top-3 z-20">
                  <TopologyPulse
                    insights={pulseInsights}
                    metricMode={metricMode}
                    expanded={pulseExpanded}
                    selectedIntegrationId={pulseIntegrationId}
                    onExpandedChange={setPulseExpanded}
                    onIntegrationChange={setPulseIntegrationId}
                    onHighlightEdges={setPulseHighlightedEdgeIds}
                    onPinEdge={pinPulseEdge}
                  />
                </div>
              ) : null}

              {loading ? (
                <div className="flex h-full items-center justify-center text-sm font-medium text-[var(--color-text-secondary)]">
                Building live topology...
                </div>
              ) : (
                <IntegrationGraph
                  graph={graph}
                  selectedNodeId={selectedPanelNode?.id ?? null}
                  selectedEdgeId={selectedEdge?.id ?? null}
                  highlightedEdgeIds={pulseHighlightedEdgeIds}
                  onNodeClick={(node) => {
                    setSelectedNode(node);
                    setSelectedEdge(null);
                    setSelectedSystem(node.label);
                    setPulseIntegrationId("");
                    setPulseHighlightedEdgeIds([]);
                    setTriageOpen(false);
                  }}
                  onEdgeClick={selectEdge}
                  colorMode={colorMode}
                  metricMode={metricMode}
                  visibilityMode={visibilityMode}
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
                <div className="absolute bottom-5 left-5 max-w-xl rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]/95 px-4 py-3 text-sm text-[var(--color-text-secondary)] shadow-sm backdrop-blur">
                <span className="font-medium text-[var(--color-text-primary)]">Limited topology: </span>
                This project&apos;s integrations share fewer than 3 distinct systems.
                </div>
              ) : null}

              {error ? (
                <p className="absolute bottom-5 left-5 max-w-xl rounded-lg border border-rose-200 bg-rose-50/95 px-4 py-3 text-sm font-semibold text-rose-800 shadow-sm dark:border-rose-900 dark:bg-rose-950/80 dark:text-rose-100">
                {error}
                </p>
              ) : null}
            </div>
          </div>

          {(selectedPanelNode || selectedEdge || triageOpen) && widePanel ? (
            <div className="w-[25rem] shrink-0 border-l border-[var(--color-border)]">
              {triageOpen ? (
                <GraphTriagePanel projectId={projectId} edges={graph.edges} reviewedEdgeIds={reviewedRiskEdgeIds} onSelect={selectEdge} onClose={clearSelection} />
              ) : (
                <GraphDetailPanel
                  projectId={projectId}
                  graph={graph}
                  selectedNode={selectedPanelNode}
                  selectedEdge={selectedEdge}
                  onEdgeSelect={selectEdge}
                  onClose={clearSelection}
                />
              )}
            </div>
          ) : null}
        </div>

        {(selectedPanelNode || selectedEdge || triageOpen) && !widePanel ? (
            <div className="absolute inset-y-0 right-0 z-30 w-[min(27rem,calc(100%-2rem))] border-l border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl">
              {triageOpen ? (
                <GraphTriagePanel projectId={projectId} edges={graph.edges} reviewedEdgeIds={reviewedRiskEdgeIds} onSelect={selectEdge} onClose={clearSelection} />
              ) : (
                <GraphDetailPanel
                  projectId={projectId}
                  graph={graph}
                  selectedNode={selectedPanelNode}
                  selectedEdge={selectedEdge}
                  onEdgeSelect={selectEdge}
                  onClose={clearSelection}
                />
              )}
            </div>
        ) : null}
      </section>
      ) : null}
    </div>
  );
}
