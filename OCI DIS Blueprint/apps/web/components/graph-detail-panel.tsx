"use client";

/* Context panel for selected systems and relationships in the topology workspace. */

import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Clock3,
  Cpu,
  ExternalLink,
  Gauge,
  Sparkles,
  UserRound,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { ReactNode } from "react";

import { AiReviewButton } from "@/components/ai-review-button";
import { QaBadge } from "@/components/qa-badge";
import { displayQaStatus, formatCompactNumber } from "@/lib/format";
import { qaTotalsForNode, topPatternsForEdges, topologyDomainForNode } from "@/lib/topology";
import type { GraphEdge, GraphNode, GraphResponse } from "@/lib/types";

type GraphDetailPanelProps = {
  projectId: string;
  graph: GraphResponse;
  selectedNode: GraphNode | null;
  selectedEdge: GraphEdge | null;
  onEdgeSelect: (_edge: GraphEdge) => void;
  onClose?: () => void;
};

function edgeMode(edge: GraphEdge): string {
  const labels: Record<GraphEdge["interaction_mode"], string> = {
    SYNCHRONOUS: "synchronous",
    ASYNCHRONOUS: "asynchronous",
    MIXED: "mixed",
    UNSPECIFIED: "mode unspecified",
  };
  return labels[edge.interaction_mode];
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
  onEdgeSelect,
}: {
  title: string;
  edges: GraphEdge[];
  selectedNode: GraphNode;
  onEdgeSelect: (_edge: GraphEdge) => void;
}): JSX.Element {
  const inbound = title === "Inbound";
  const [expanded, setExpanded] = useState<boolean>(false);
  const visibleEdges = expanded ? sortedEdges(edges) : sortedEdges(edges).slice(0, 5);
  return (
    <section className="border-t border-[var(--color-border)] px-5 py-5">
      <p className="app-label">
        {title} · {edges.length}
      </p>
      <div className="mt-3 space-y-2">
        {visibleEdges.map((edge) => {
          const otherSystem = inbound ? edge.source : edge.target;
          return (
            <button
              type="button"
              key={edge.id}
              onClick={() => onEdgeSelect(edge)}
              className="flex w-full items-center gap-3 rounded-lg bg-[var(--color-surface-2)] px-3 py-3 text-left text-sm transition hover:bg-[var(--color-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)]"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--color-surface)] text-[var(--color-text-secondary)]">
                {inbound ? <ArrowLeft className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-[var(--color-text-primary)]" title={otherSystem}>
                  {otherSystem === selectedNode.id ? selectedNode.label : otherSystem}
                </p>
                <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                  {edge.integration_count} integration{edge.integration_count === 1 ? "" : "s"} · {edgeMode(edge)}
                </p>
              </div>
              <span className={`h-2.5 w-2.5 rounded-full ${statusDot(edge.risk_qa_status)}`} />
            </button>
          );
        })}
        {edges.length === 0 ? (
          <p className="rounded-xl border border-dashed border-[var(--color-border)] px-3 py-4 text-sm text-[var(--color-text-muted)]">
            No {title.toLowerCase()} dependencies.
          </p>
        ) : null}
        {edges.length > 5 ? (
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="inline-flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-semibold text-[var(--color-accent)] hover:bg-[var(--color-hover)]"
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {expanded ? "Show less" : `Show all ${edges.length}`}
          </button>
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
  onEdgeSelect,
  onClose,
}: GraphDetailPanelProps): JSX.Element {
  const [showAllIntegrations, setShowAllIntegrations] = useState<boolean>(false);
  const edgeMetricTotals = useMemo(() => {
    if (!selectedEdge) {
      return { executions: 0, payload: 0 };
    }
    return {
      executions: selectedEdge.total_executions_per_day,
      payload: selectedEdge.total_payload_per_hour_kb,
    };
  }, [selectedEdge]);

  if (selectedNode) {
    const connectedEdges = graph.edges.filter(
      (edge) => edge.source === selectedNode.id || edge.target === selectedNode.id,
    );
    const outbound = connectedEdges.filter((edge) => edge.source === selectedNode.id);
    const inbound = connectedEdges.filter((edge) => edge.target === selectedNode.id);
    const totals = qaTotalsForNode(selectedNode, graph.edges);
    const domain = topologyDomainForNode(selectedNode);
    const patterns = topPatternsForEdges(connectedEdges, 4);
    const owners = selectedNode.owners.slice(0, 3);
    const technologies = selectedNode.technologies.slice(0, 3);

    return (
      <PanelShell onClose={onClose}>
        <section className="px-5 py-5">
          <p className="app-label" style={{ color: domain.color }}>
            {domain.shortLabel}
          </p>
          <h2 className="mt-3 text-2xl font-semibold leading-tight text-[var(--color-text-primary)]">
            {selectedNode.label}
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            {domain.label} system · {selectedNode.integration_count} integrations connect through this system
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-[var(--color-text-muted)]">
            {owners.length > 0 ? (
              <span className="inline-flex items-center gap-1.5"><UserRound className="h-3.5 w-3.5" />{owners.join(", ")}</span>
            ) : null}
            {technologies.length > 0 ? (
              <span className="inline-flex items-center gap-1.5"><Cpu className="h-3.5 w-3.5" />{technologies.join(", ")}</span>
            ) : null}
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <AiReviewButton projectId={projectId} graphContext={{ type: "node", label: selectedNode.label }} label="Analyze system" />
            <Link
              href={`/projects/${projectId}/catalog?system=${encodeURIComponent(selectedNode.label)}`}
              className="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-[var(--color-text-secondary)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]"
            >
              <ExternalLink className="h-4 w-4" />
              Catalog
            </Link>
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

        <DirectionList title="Outbound" edges={outbound} selectedNode={selectedNode} onEdgeSelect={onEdgeSelect} />
        <DirectionList title="Inbound" edges={inbound} selectedNode={selectedNode} onEdgeSelect={onEdgeSelect} />

        <section className="border-t border-[var(--color-border)] px-5 py-5">
          <p className="app-label">Top Patterns</p>
          <div className="mt-3 space-y-2">
            {patterns.map((pattern) => {
              const [patternId, ...nameParts] = pattern.pattern.split(" · ");
              const patternName = nameParts.join(" · ") || "Pattern definition unavailable";

              return (
                <div
                  key={pattern.pattern}
                  className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 text-sm"
                >
                  <span className="whitespace-nowrap rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1 text-xs font-semibold">
                    {patternId}
                  </span>
                  <span className="min-w-0 text-[var(--color-text-secondary)]">{patternName}</span>
                  <span className="font-semibold tabular-nums text-[var(--color-text-muted)]">{pattern.count}</span>
                </div>
              );
            })}
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
            {selectedEdge.integration_count} integration{selectedEdge.integration_count === 1 ? "" : "s"} · {edgeMode(selectedEdge)}
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <AiReviewButton
              projectId={projectId}
              integrationId={reviewIntegrationId}
              graphContext={{ type: "edge", source: selectedEdge.source, target: selectedEdge.target }}
              label="Analyze dependency path"
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

        <section className="grid grid-cols-2 gap-2 border-t border-[var(--color-border)] px-5 py-5">
          <div className="rounded-lg bg-[var(--color-surface-2)] p-3">
            <p className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--color-text-muted)]"><Gauge className="h-3.5 w-3.5" />Executions / day</p>
            <p className="mt-2 text-xl font-semibold">{formatCompactNumber(edgeMetricTotals.executions)}</p>
            <p className="mt-1 text-[10px] text-[var(--color-text-muted)]">{selectedEdge.executions_coverage}/{selectedEdge.integration_count} integrations covered</p>
          </div>
          <div className="rounded-lg bg-[var(--color-surface-2)] p-3">
            <p className="inline-flex items-center gap-1.5 text-xs font-semibold text-[var(--color-text-muted)]"><Cpu className="h-3.5 w-3.5" />Payload / hour</p>
            <p className="mt-2 text-xl font-semibold">{formatCompactNumber(edgeMetricTotals.payload)} KB</p>
            <p className="mt-1 text-[10px] text-[var(--color-text-muted)]">{selectedEdge.payload_coverage}/{selectedEdge.integration_count} integrations covered</p>
          </div>
          <p className="col-span-2 inline-flex items-center gap-1.5 text-xs text-[var(--color-text-muted)]">
            <Clock3 className="h-3.5 w-3.5" />
            Last catalog change {new Date(selectedEdge.last_updated_at).toLocaleString("en-US")}
          </p>
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
            {(showAllIntegrations ? selectedEdge.integrations : selectedEdge.integrations.slice(0, 8)).map((integration) => {
              return (
                <li
                  key={integration.id}
                >
                  <Link
                    href={`/projects/${projectId}/catalog/${integration.id}`}
                    className="flex items-center justify-between gap-3 rounded-lg bg-[var(--color-surface-2)] px-3 py-3 transition hover:bg-[var(--color-hover)]"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-semibold text-[var(--color-text-primary)]" title={integration.name}>{integration.name}</span>
                      <span className="mt-1 block truncate text-xs text-[var(--color-text-muted)]">
                        {[integration.pattern, integration.owner].filter(Boolean).join(" · ") || "Open integration record"}
                      </span>
                    </span>
                    <QaBadge status={integration.qa_status} />
                  </Link>
                </li>
              );
            })}
          </ul>
          {selectedEdge.integrations.length > 8 ? (
            <button
              type="button"
              onClick={() => setShowAllIntegrations((current) => !current)}
              className="mt-2 inline-flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-xs font-semibold text-[var(--color-accent)] hover:bg-[var(--color-hover)]"
            >
              {showAllIntegrations ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              {showAllIntegrations ? "Show less" : `Show all ${selectedEdge.integrations.length}`}
            </button>
          ) : null}
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
