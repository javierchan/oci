"use client";

/* Context panel for selected systems and relationships in the topology workspace. */

import Link from "next/link";
import { ArrowLeft, ArrowRight, ExternalLink, MoreHorizontal, Pencil, Sparkles, X } from "lucide-react";
import type { ReactNode } from "react";

import { AiReviewButton } from "@/components/ai-review-button";
import { QaBadge } from "@/components/qa-badge";
import { displayQaStatus } from "@/lib/format";
import { qaTotalsForNode, topPatternsForEdges, topologyDomainForNode } from "@/lib/topology";
import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/types";

type GraphDetailPanelProps = {
  projectId: string;
  graph: GraphResponse;
  selectedNode: GraphNode | null;
  selectedEdge: GraphEdge | null;
  onClose?: () => void;
};

function edgeMode(edge: GraphEdge): string {
  const text = edge.patterns.join(" ").toLowerCase();
  if (edge.patterns.length > 1) {
    return "both";
  }
  if (
    text.includes("event") ||
    text.includes("pub") ||
    text.includes("async") ||
    text.includes("cdc") ||
    text.includes("batch") ||
    text.includes("webhook")
  ) {
    return "async";
  }
  return "sync";
}

function statusDot(status: string): string {
  if (status === "OK") {
    return "bg-emerald-600";
  }
  if (status === "PENDING") {
    return "bg-rose-700";
  }
  return "bg-amber-700";
}

function sortedEdges(edges: GraphEdge[]): GraphEdge[] {
  return [...edges].sort((left, right) => right.integration_count - left.integration_count || left.id.localeCompare(right.id));
}

function DirectionList({
  title,
  edges,
  selectedNode,
}: {
  title: string;
  edges: GraphEdge[];
  selectedNode: GraphNode;
}): JSX.Element {
  const inbound = title === "Inbound";
  return (
    <section className="border-t border-[var(--color-border)] px-5 py-5">
      <p className="app-label">
        {title} · {edges.length}
      </p>
      <div className="mt-3 space-y-2">
        {sortedEdges(edges).slice(0, 5).map((edge) => {
          const otherSystem = inbound ? edge.source : edge.target;
          return (
            <article
              key={edge.id}
              className="flex items-center gap-3 rounded-xl bg-[var(--color-surface-2)] px-3 py-3 text-sm"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-surface)] text-[var(--color-text-secondary)]">
                {inbound ? <ArrowLeft className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-[var(--color-text-primary)]" title={otherSystem}>
                  {otherSystem === selectedNode.id ? selectedNode.label : otherSystem}
                </p>
                <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                  {edge.integration_count} integrations · {edgeMode(edge)}
                </p>
              </div>
              <span className={`h-2.5 w-2.5 rounded-full ${statusDot(edge.dominant_qa_status)}`} />
            </article>
          );
        })}
        {edges.length === 0 ? (
          <p className="rounded-xl border border-dashed border-[var(--color-border)] px-3 py-4 text-sm text-[var(--color-text-muted)]">
            No {title.toLowerCase()} dependencies.
          </p>
        ) : null}
      </div>
    </section>
  );
}

function PanelShell({
  children,
  onClose,
}: {
  children: ReactNode;
  onClose?: () => void;
}): JSX.Element {
  return (
    <aside className="flex h-full min-h-0 w-full flex-col bg-[var(--color-surface)] text-[var(--color-text-primary)]">
      <div className="flex justify-end border-b border-[var(--color-border)] px-4 py-3">
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-[var(--color-text-secondary)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]"
            aria-label="Close topology detail panel"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
    </aside>
  );
}

export function GraphDetailPanel({
  projectId,
  graph,
  selectedNode,
  selectedEdge,
  onClose,
}: GraphDetailPanelProps): JSX.Element {
  if (selectedNode) {
    const connectedEdges = graph.edges.filter(
      (edge) => edge.source === selectedNode.id || edge.target === selectedNode.id,
    );
    const outbound = connectedEdges.filter((edge) => edge.source === selectedNode.id);
    const inbound = connectedEdges.filter((edge) => edge.target === selectedNode.id);
    const totals = qaTotalsForNode(selectedNode, graph.edges);
    const domain = topologyDomainForNode(selectedNode);
    const patterns = topPatternsForEdges(connectedEdges, 4);

    return (
      <PanelShell onClose={onClose}>
        <section className="px-5 py-5">
          <p className="app-label" style={{ color: domain.color }}>
            {domain.shortLabel}
          </p>
          <h2 className="mt-3 text-3xl font-semibold leading-tight text-[var(--color-text-primary)]">
            {selectedNode.label}
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            {domain.label} system · {selectedNode.integration_count} integrations connect through this system
          </p>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <AiReviewButton projectId={projectId} graphContext={{ type: "node", label: selectedNode.label }} label="Ask co-pilot" />
            <Link
              href={`/projects/${projectId}/catalog?system=${encodeURIComponent(selectedNode.label)}`}
              className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-[var(--color-text-secondary)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]"
            >
              <ExternalLink className="h-4 w-4" />
              Catalog
            </Link>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-[var(--color-text-secondary)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]"
            >
              <Pencil className="h-4 w-4" />
              Edit
            </button>
            <button
              type="button"
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-[var(--color-text-secondary)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]"
              aria-label="More system actions"
            >
              <MoreHorizontal className="h-4 w-4" />
            </button>
          </div>
        </section>

        <section className="border-t border-[var(--color-border)] px-5 py-5">
          <p className="app-label">System Health</p>
          <div className="mt-4 space-y-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2 text-[var(--color-text-secondary)]">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-600" />
                QA OK
              </span>
              <span className="font-semibold text-[var(--color-text-primary)]">{totals.ok}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2 text-[var(--color-text-secondary)]">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-700" />
                In review
              </span>
              <span className="font-semibold text-[var(--color-text-primary)]">{totals.review}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-2 text-[var(--color-text-secondary)]">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-700" />
                Pending
              </span>
              <span className="font-semibold text-[var(--color-text-primary)]">{totals.pending}</span>
            </div>
          </div>
        </section>

        <DirectionList title="Outbound" edges={outbound} selectedNode={selectedNode} />
        <DirectionList title="Inbound" edges={inbound} selectedNode={selectedNode} />

        <section className="border-t border-[var(--color-border)] px-5 py-5">
          <p className="app-label">Top Patterns</p>
          <div className="mt-3 space-y-2">
            {patterns.map((pattern) => (
              <div key={pattern.pattern} className="flex items-center justify-between gap-3 text-sm">
                <span className="inline-flex items-center gap-3">
                  <span className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1 text-xs font-semibold">
                    {pattern.pattern}
                  </span>
                  <span className="text-[var(--color-text-secondary)]">{pattern.pattern}</span>
                </span>
                <span className="font-semibold text-[var(--color-text-muted)]">{pattern.count}</span>
              </div>
            ))}
          </div>
        </section>
      </PanelShell>
    );
  }

  if (selectedEdge) {
    const reviewIntegrationId = selectedEdge.integration_ids.length === 1 ? selectedEdge.integration_ids[0] : undefined;
    const patterns = selectedEdge.patterns.length > 0 ? selectedEdge.patterns : ["Unassigned"];

    return (
      <PanelShell onClose={onClose}>
        <section className="px-5 py-5">
          <p className="app-label">Dependency Path</p>
          <h2 className="mt-3 text-2xl font-semibold leading-tight text-[var(--color-text-primary)]">
            {selectedEdge.source} → {selectedEdge.target}
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            {selectedEdge.integration_count} integrations · {edgeMode(selectedEdge)}
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <AiReviewButton
              projectId={projectId}
              integrationId={reviewIntegrationId}
              graphContext={{ type: "edge", source: selectedEdge.source, target: selectedEdge.target }}
              label="Ask co-pilot"
            />
            <Link
              href={`/projects/${projectId}/catalog?source_system=${encodeURIComponent(selectedEdge.source)}&destination_system=${encodeURIComponent(selectedEdge.target)}`}
              className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-[var(--color-text-secondary)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]"
            >
              <ExternalLink className="h-4 w-4" />
              Catalog
            </Link>
          </div>
        </section>

        <section className="border-t border-[var(--color-border)] px-5 py-5">
          <p className="app-label">QA Breakdown</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {Object.entries(selectedEdge.qa_statuses).map(([status, count]) => (
              <span
                key={status}
                className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-sm font-semibold text-[var(--color-text-secondary)]"
              >
                <span className={`h-2.5 w-2.5 rounded-full ${statusDot(status)}`} />
                {count} {displayQaStatus(status)}
              </span>
            ))}
          </div>
        </section>

        <section className="border-t border-[var(--color-border)] px-5 py-5">
          <p className="app-label">Patterns</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {patterns.map((pattern) => (
              <span
                key={pattern}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-sm font-semibold text-[var(--color-text-secondary)]"
              >
                {pattern}
              </span>
            ))}
          </div>
        </section>

        <section className="border-t border-[var(--color-border)] px-5 py-5">
          <p className="app-label">Integrations</p>
          <ul className="mt-3 space-y-2">
            {selectedEdge.integration_names.slice(0, 8).map((name, index) => {
              const qaStatus = selectedEdge.integration_qa_statuses[index] ?? selectedEdge.dominant_qa_status;
              return (
                <li
                  key={`${selectedEdge.integration_ids[index]}-${name}`}
                  className="flex items-center justify-between gap-3 rounded-xl bg-[var(--color-surface-2)] px-3 py-3"
                >
                  <span className="min-w-0 truncate text-sm font-semibold text-[var(--color-text-primary)]" title={name}>
                    {name}
                  </span>
                  <QaBadge status={qaStatus} />
                </li>
              );
            })}
          </ul>
        </section>

        <section className="border-t border-[var(--color-border)] px-5 py-5">
          <p className="app-label text-[var(--color-accent)]">Architect Co-pilot</p>
          <div className="mt-3 rounded-2xl border border-[var(--color-accent-border)] bg-[var(--color-accent-soft)] p-4 text-sm leading-6 text-[var(--color-text-secondary)]">
            <p className="inline-flex items-center gap-2 font-semibold text-[var(--color-text-primary)]">
              <Sparkles className="h-4 w-4 text-[var(--color-accent)]" />
              Review this dependency path
            </p>
            <p className="mt-2">
              Use the governed review board with this edge context to inspect evidence, QA blockers, service sizing, and safe remediation options.
            </p>
          </div>
        </section>
      </PanelShell>
    );
  }

  return (
    <PanelShell onClose={onClose}>
      <section className="px-5 py-5">
        <p className="app-label">Selection</p>
        <h2 className="mt-3 text-2xl font-semibold text-[var(--color-text-primary)]">Select a system or edge</h2>
        <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
          Click any node or dependency line to inspect health, direction, patterns, and catalog drill-through.
        </p>
      </section>
    </PanelShell>
  );
}
