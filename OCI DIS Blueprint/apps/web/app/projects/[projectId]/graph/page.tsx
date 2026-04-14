"use client";

/* Interactive system dependency map page backed by the catalog graph endpoint. */

import { useEffect, useRef, useState } from "react";

import { Breadcrumb } from "@/components/breadcrumb";
import { GraphControls } from "@/components/graph-controls";
import { GraphDetailPanel } from "@/components/graph-detail-panel";
import { IntegrationGraph } from "@/components/integration-graph";
import { api } from "@/lib/api";
import type { GraphEdge, GraphNode, GraphParams, GraphResponse } from "@/lib/types";
import type { Project } from "@/lib/types";

type GraphPageProps = {
  params: {
    projectId: string;
  };
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
  const svgRef = useRef<SVGSVGElement>(null);
  const [graph, setGraph] = useState<GraphResponse>(EMPTY_GRAPH);
  const [project, setProject] = useState<Project | null>(null);
  const [filters, setFilters] = useState<GraphParams>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [zoom, setZoom] = useState<number>(1);
  const [colorMode, setColorMode] = useState<"qa" | "bp">("qa");

  useEffect(() => {
    let cancelled = false;
    void api.getProject(params.projectId).then((response) => {
      if (!cancelled) {
        setProject(response);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [params.projectId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    void api
      .getGraph(params.projectId, filters)
      .then((response) => {
        if (!cancelled) {
          setGraph(response);
          setSelectedNode(null);
          setSelectedEdge(null);
        }
      })
      .catch((caughtError: unknown) => {
        if (!cancelled) {
          setError(caughtError instanceof Error ? caughtError.message : "Unable to load dependency graph.");
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
  }, [filters, params.projectId]);

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
              { label: project?.name ?? "Project", href: `/projects/${params.projectId}` },
              { label: "Map" },
            ]}
          />
        </div>
      </section>

      <GraphControls
        projectId={params.projectId}
        filters={filters}
        onFilterChange={handleFilterChange}
        colorMode={colorMode}
        onColorModeChange={setColorMode}
        zoom={zoom}
        onZoomIn={() => setZoom((current) => current * 1.2)}
        onZoomOut={() => setZoom((current) => current / 1.2)}
        onZoomReset={() => setZoom(1)}
        meta={graph.meta}
        svgRef={svgRef}
      />

      {graph.meta.node_count > 50 ? (
        <div className="rounded-2xl bg-yellow-900 p-3 text-sm text-yellow-200">
          ⚠ {graph.meta.node_count} systems detected. Apply a filter to improve readability.
        </div>
      ) : null}

      {error ? <p className="text-sm text-rose-600">{error}</p> : null}

      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        <div className="space-y-4">
          <section className="grid gap-4 md:grid-cols-3">
            <article className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Nodes</p>
              <p className="mt-3 text-3xl font-semibold text-slate-950">{graph.meta.node_count}</p>
            </article>
            <article className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Edges</p>
              <p className="mt-3 text-3xl font-semibold text-slate-950">{graph.meta.edge_count}</p>
            </article>
            <article className="rounded-[1.75rem] border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Integrations</p>
              <p className="mt-3 text-3xl font-semibold text-slate-950">{graph.meta.integration_count}</p>
            </article>
          </section>

          {loading ? (
            <div className="rounded-[2rem] border border-slate-200 bg-white p-10 text-sm text-slate-500 shadow-sm">
              Building force layout…
            </div>
          ) : (
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
              zoom={zoom}
              colorMode={colorMode}
              svgRef={svgRef}
            />
          )}
        </div>

        <GraphDetailPanel
          projectId={params.projectId}
          graph={graph}
          selectedNode={selectedNode}
          selectedEdge={selectedEdge}
        />
      </div>
    </div>
  );
}
