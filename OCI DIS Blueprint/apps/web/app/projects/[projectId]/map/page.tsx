"use client";

/* Modern topology map route backed by the existing catalog graph API. */

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Breadcrumb } from "@/components/breadcrumb";
import { TopologyCanvas } from "@/components/topology-canvas";
import { api, getErrorMessage } from "@/lib/api";
import { isProjectNotFoundError, projectRootHref } from "@/lib/project-errors";
import type { GraphResponse, Project } from "@/lib/types";

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
    payload_coverage: 0,
  },
};

export default function MapPage({ params }: MapPageProps): JSX.Element {
  const { projectId } = use(params);
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [graph, setGraph] = useState<GraphResponse>(EMPTY_GRAPH);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>("");
  const missingProjectHref = projectRootHref(projectId);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    async function load(): Promise<void> {
      try {
        const [projectResponse, graphResponse] = await Promise.all([
          api.getProject(projectId),
          api.getGraph(projectId),
        ]);
        if (!cancelled) {
          setProject(projectResponse);
          setGraph(graphResponse);
        }
      } catch (caughtError) {
        if (cancelled) {
          return;
        }
        if (isProjectNotFoundError(caughtError)) {
          router.replace(missingProjectHref);
          return;
        }
        setError(getErrorMessage(caughtError, "Unable to load topology map."));
        setGraph(EMPTY_GRAPH);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [missingProjectHref, projectId, router]);

  return (
    <div className="console-page">
      <section className="console-hero">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="app-kicker">The Map · Live Topology</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
              System Topology
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Read the catalog as a living architecture diagram. Systems are clustered by domain, integrations become
              directional edges, and QA/flow signals stay visible without leaving the map.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="card-quiet px-4 py-3">
              <p className="t-micro">Systems</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--ink-1)]">{graph.meta.node_count}</p>
            </div>
            <div className="card-quiet px-4 py-3">
              <p className="t-micro">Edges</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--ink-1)]">{graph.meta.edge_count}</p>
            </div>
            <div className="card-quiet px-4 py-3">
              <p className="t-micro">Rows</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--ink-1)]">{graph.meta.integration_count}</p>
            </div>
          </div>
        </div>
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

      {error ? (
        <section className="app-card p-6 text-sm text-rose-600">{error}</section>
      ) : null}

      {loading ? (
        <section className="app-card p-8">
          <div className="skeleton h-[640px] w-full" />
        </section>
      ) : graph.nodes.length === 0 ? (
        <section className="app-card p-10 text-center">
          <p className="text-lg font-semibold text-[var(--color-text-primary)]">No topology data yet</p>
          <p className="mx-auto mt-2 max-w-lg text-sm text-[var(--color-text-secondary)]">
            Import a workbook or capture integrations with source and destination systems to generate the topology map.
          </p>
        </section>
      ) : (
        <TopologyCanvas projectId={projectId} graph={graph} />
      )}
    </div>
  );
}
