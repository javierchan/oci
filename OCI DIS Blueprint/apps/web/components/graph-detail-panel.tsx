"use client";

/* Detail panel for node and edge selections in the dependency graph. */

import Link from "next/link";

import { QaBadge } from "@/components/qa-badge";
import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/types";

type GraphDetailPanelProps = {
  projectId: string;
  graph: GraphResponse;
  selectedNode: GraphNode | null;
  selectedEdge: GraphEdge | null;
};

export function GraphDetailPanel({
  projectId,
  graph,
  selectedNode,
  selectedEdge,
}: GraphDetailPanelProps): JSX.Element {
  if (selectedNode) {
    const connectedEdges = graph.edges.filter(
      (edge) => edge.source === selectedNode.id || edge.target === selectedNode.id,
    );

    return (
      <aside className="app-card p-6">
        <p className="app-label">System</p>
        <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{selectedNode.label}</h2>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="app-card-muted p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">As source</p>
            <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{selectedNode.as_source_count}</p>
          </div>
          <div className="app-card-muted p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">As destination</p>
            <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{selectedNode.as_destination_count}</p>
          </div>
        </div>

        <section className="mt-6">
          <p className="app-label">Business Processes</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedNode.business_processes.map((process) => (
              <span
                key={process}
                className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-slate-700"
              >
                {process}
              </span>
            ))}
          </div>
        </section>

        <section className="mt-6">
          <p className="app-label">Connected Systems</p>
          <ul className="mt-3 space-y-2">
            {connectedEdges.map((edge) => {
              const isSource = edge.source === selectedNode.id;
              const otherSystem = isSource ? edge.target : edge.source;
              return (
                <li
                  key={edge.id}
                  className="flex items-center justify-between rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-3)] px-4 py-3 text-sm text-[var(--color-text-secondary)]"
                >
                  <span>
                    {isSource ? "→" : "←"} {otherSystem}
                  </span>
                  <span className="font-semibold text-[var(--color-text-primary)]">{edge.integration_count}</span>
                </li>
              );
            })}
          </ul>
        </section>

        <div className="mt-6">
          <Link
            href={`/projects/${projectId}/catalog?source_system=${encodeURIComponent(selectedNode.id)}`}
            className="app-link"
          >
            View in Catalog →
          </Link>
        </div>
      </aside>
    );
  }

  if (selectedEdge) {
    return (
      <aside className="app-card p-6">
        <p className="app-label">Relationship</p>
        <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">
          {selectedEdge.source} → {selectedEdge.target}
        </h2>
        <div className="app-theme-chip mt-4 inline-flex">
          {selectedEdge.integration_count} integrations
        </div>

        <section className="mt-6">
          <p className="app-label">QA Breakdown</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.entries(selectedEdge.qa_statuses).map(([status, count]) => (
              <span
                key={status}
                className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-slate-700"
              >
                {count} {status}
              </span>
            ))}
          </div>
        </section>

        <section className="mt-6">
          <p className="app-label">Patterns</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedEdge.patterns.length > 0 ? selectedEdge.patterns.map((pattern) => (
              <span
                key={pattern}
                className="inline-flex rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-sky-700"
              >
                {pattern}
              </span>
            )) : <span className="text-sm text-slate-500">No pattern assignments yet.</span>}
          </div>
        </section>

        <section className="mt-6">
          <p className="app-label">Business Processes</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedEdge.business_processes.map((process) => (
              <span
                key={process}
                className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-slate-700"
              >
                {process}
              </span>
            ))}
          </div>
        </section>

        <section className="mt-6">
          <p className="app-label">Integrations</p>
          <ul className="mt-3 space-y-3">
            {selectedEdge.integration_names.map((name, index) => {
              const qaStatus = selectedEdge.integration_qa_statuses[index] ?? selectedEdge.dominant_qa_status;
              return (
                <li
                  key={`${selectedEdge.integration_ids[index]}-${name}`}
                  className="flex items-center justify-between gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-3)] px-4 py-3"
                >
                  <span className="text-sm font-medium text-[var(--color-text-primary)]">{name}</span>
                  <QaBadge status={qaStatus} />
                </li>
              );
            })}
          </ul>
        </section>

        <div className="mt-6">
          <Link
            href={`/projects/${projectId}/catalog?source_system=${encodeURIComponent(selectedEdge.source)}&destination_system=${encodeURIComponent(selectedEdge.target)}`}
            className="app-link"
          >
            View all in Catalog →
          </Link>
        </div>
      </aside>
    );
  }

  return (
    <aside className="app-card p-6">
      <p className="app-label">Selection</p>
      <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">Choose a node or edge</h2>
      <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
        Click a system or dependency line to inspect QA mix, connected systems, and drill back into the catalog with the relevant filters already applied.
      </p>
    </aside>
  );
}
