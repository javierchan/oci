"use client";

/* Mobile-first dependency explorer used when the full SVG topology is unavailable. */

import { Activity, ArrowRight, Network, Search, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { edgeRiskLabel, qaTotalsForNode, topologyDomainForNode } from "@/lib/topology";
import { buildTopologyPulseInsights } from "@/lib/topology-insights";
import { formatCompactNumber } from "@/lib/format";
import type { GraphResponse } from "@/lib/types";

type GraphMobileListProps = {
  projectId: string;
  graph: GraphResponse;
  loading: boolean;
  error: string;
};

export function GraphMobileList({ projectId, graph, loading, error }: GraphMobileListProps): JSX.Element {
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"systems" | "risks">("risks");
  const normalizedQuery = query.trim().toLowerCase();

  const systems = useMemo(
    () =>
      graph.nodes
        .filter((node) => node.label.toLowerCase().includes(normalizedQuery))
        .sort((left, right) => right.integration_count - left.integration_count || left.label.localeCompare(right.label)),
    [graph.nodes, normalizedQuery],
  );
  const risks = useMemo(
    () =>
      graph.edges
        .filter(
          (edge) =>
            edge.risk_qa_status !== "OK" &&
            `${edge.source} ${edge.target}`.toLowerCase().includes(normalizedQuery),
        )
        .sort((left, right) => right.risk_score - left.risk_score || right.integration_count - left.integration_count),
    [graph.edges, normalizedQuery],
  );
  const visibleRisks = normalizedQuery ? risks : risks.slice(0, 20);
  const visibleSystems = normalizedQuery ? systems : systems.slice(0, 30);
  const pulse = useMemo(
    () => buildTopologyPulseInsights(graph, { metricMode: "relationships" }),
    [graph],
  );
  const payloadPerExecution = pulse.totalPayloadPerExecutionKb === null
    ? "—"
    : pulse.totalPayloadPerExecutionKb >= 1024
      ? `${formatCompactNumber(pulse.totalPayloadPerExecutionKb / 1024)} MB`
      : `${formatCompactNumber(pulse.totalPayloadPerExecutionKb)} KB`;

  return (
    <section className="sm:hidden">
      <header className="border-b border-[var(--color-border)] pb-5">
        <p className="app-label text-[var(--color-accent)]">Integration topology</p>
        <h1 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">Dependency explorer</h1>
        <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
          {graph.meta.node_count} systems · {graph.meta.edge_count} paths · {graph.meta.integration_count} integrations
        </p>
      </header>

      {!loading && !error && graph.meta.integration_count > 0 ? (
        <section className="border-b border-[var(--color-border)] py-4" aria-label="Topology Pulse insights">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-[var(--color-accent)]" aria-hidden="true" />
            <h2 className="text-xs font-semibold text-[var(--color-text-primary)]">Topology Pulse</h2>
            <span className="rounded-sm bg-[var(--color-status-active-bg)] px-1.5 py-0.5 text-[9px] font-semibold uppercase text-[var(--color-status-active-text)]">
              Current
            </span>
          </div>
          <div className="mt-3 grid grid-cols-3 divide-x divide-[var(--color-border)]">
            <div className="pr-3">
              <p className="text-[10px] uppercase text-[var(--color-text-muted)]">Payload / execution</p>
              <p className="mt-1 text-sm font-semibold text-[var(--color-text-primary)]">{payloadPerExecution}</p>
              <p className="text-[10px] text-[var(--color-text-muted)]">
                {pulse.payloadExecutionCoverage}/{pulse.integrationCount} measured
              </p>
            </div>
            <div className="px-3">
              <p className="text-[10px] uppercase text-[var(--color-text-muted)]">QA OK</p>
              <p className="mt-1 text-sm font-semibold text-[var(--color-qa-ok-text)]">{pulse.qa.ok}</p>
              <p className="text-[10px] text-[var(--color-text-muted)]">{pulse.qa.review + pulse.qa.pending} attention</p>
            </div>
            <div className="pl-3">
              <p className="text-[10px] uppercase text-[var(--color-text-muted)]">Top path</p>
              <p className="mt-1 text-sm font-semibold text-[var(--color-text-primary)]">
                {Math.round(pulse.concentration.topPathShare * 100)}%
              </p>
              <p className="truncate text-[10px] text-[var(--color-text-muted)]">
                {pulse.concentration.topPathLabel}
              </p>
            </div>
          </div>
        </section>
      ) : null}

      <div className="sticky top-0 z-10 -mx-1 bg-[var(--color-bg)] px-1 py-4">
        <label className="flex min-h-11 items-center gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3">
          <Search className="h-4 w-4 text-[var(--color-text-muted)]" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search systems or dependency paths"
            className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--color-text-muted)]"
            aria-label="Search topology"
          />
        </label>
        <div className="mt-3 grid grid-cols-2 rounded-lg bg-[var(--color-surface-2)] p-1" role="tablist" aria-label="Topology views">
          {(["risks", "systems"] as const).map((option) => (
            <button
              key={option}
              type="button"
              role="tab"
              aria-selected={view === option}
              onClick={() => setView(option)}
              className={`rounded-md px-3 py-2 text-sm font-semibold capitalize transition ${
                view === option ? "bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-sm" : "text-[var(--color-text-muted)]"
              }`}
            >
              {option === "risks" ? `Triage (${risks.length})` : `Systems (${systems.length})`}
            </button>
          ))}
        </div>
      </div>

      {loading ? <p className="py-8 text-sm text-[var(--color-text-muted)]">Loading topology…</p> : null}
      {error ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">{error}</p> : null}

      {!loading && !error && view === "risks" ? (
        <div className="space-y-2 pb-8">
          {visibleRisks.map((edge) => (
            <Link
              key={edge.id}
              href={`/projects/${projectId}/catalog?source_system=${encodeURIComponent(edge.source)}&destination_system=${encodeURIComponent(edge.target)}`}
              className="block rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
            >
              <span className="flex items-center gap-2 text-sm font-semibold">
                <span className="truncate">{edge.source}</span>
                <ArrowRight className="h-4 w-4 shrink-0 text-[var(--color-accent)]" />
                <span className="truncate">{edge.target}</span>
              </span>
              <span className="mt-3 flex items-center justify-between gap-3 text-xs text-[var(--color-text-muted)]">
                <span className="inline-flex items-center gap-1.5 font-semibold text-amber-700 dark:text-amber-400">
                  <ShieldAlert className="h-3.5 w-3.5" />
                  {edgeRiskLabel(edge)}
                </span>
                <span>{edge.integration_count} integration{edge.integration_count === 1 ? "" : "s"}</span>
              </span>
            </Link>
          ))}
          {risks.length === 0 ? (
            <p className="rounded-lg border border-dashed border-[var(--color-border)] p-5 text-sm text-[var(--color-text-muted)]">
              No risk paths match the current search.
            </p>
          ) : null}
          {risks.length > visibleRisks.length ? (
            <Link
              href={`/projects/${projectId}/catalog?qa_status=REVISAR`}
              className="block rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-center text-sm font-semibold text-[var(--color-accent)]"
            >
              Open all {risks.length} risk paths in Catalog
            </Link>
          ) : null}
        </div>
      ) : null}

      {!loading && !error && view === "systems" ? (
        <div className="space-y-2 pb-8">
          {visibleSystems.map((node) => {
            const totals = qaTotalsForNode(node, graph.edges);
            const domain = topologyDomainForNode(node);
            return (
              <Link
                key={node.id}
                href={`/projects/${projectId}/catalog?system=${encodeURIComponent(node.label)}`}
                className="flex items-center gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
              >
                <span
                  className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                  style={{ backgroundColor: domain.softColor, color: domain.color }}
                >
                  <Network className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold">{node.label}</span>
                  <span className="mt-1 block text-xs text-[var(--color-text-muted)]">
                    {node.integration_count} integrations · {totals.review + totals.pending} require attention
                  </span>
                </span>
                <ArrowRight className="h-4 w-4 shrink-0 text-[var(--color-text-muted)]" />
              </Link>
            );
          })}
          {systems.length > visibleSystems.length ? (
            <Link
              href={`/projects/${projectId}/catalog`}
              className="block rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-center text-sm font-semibold text-[var(--color-accent)]"
            >
              Open all {systems.length} systems in Catalog
            </Link>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
