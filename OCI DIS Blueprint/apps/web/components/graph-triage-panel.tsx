"use client";

/* Ranked QA triage queue for high-risk integration dependency paths. */

import { ArrowRight, Check, Clock3, ExternalLink, ShieldAlert, X } from "lucide-react";
import Link from "next/link";

import { edgeRiskLabel } from "@/lib/topology";
import type { GraphEdge } from "@/lib/types";

type GraphTriagePanelProps = {
  projectId: string;
  edges: GraphEdge[];
  reviewedEdgeIds: string[];
  onSelect: (_edge: GraphEdge) => void;
  onClose: () => void;
};

function relativeAge(value: string): string {
  const days = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000));
  if (days === 0) {
    return "updated today";
  }
  return `updated ${days}d ago`;
}

export function GraphTriagePanel({
  projectId,
  edges,
  reviewedEdgeIds,
  onSelect,
  onClose,
}: GraphTriagePanelProps): JSX.Element {
  const reviewed = new Set(reviewedEdgeIds);
  const ranked = [...edges]
    .filter((edge) => edge.risk_qa_status !== "OK")
    .sort((left, right) => {
      const reviewOrder = Number(reviewed.has(left.id)) - Number(reviewed.has(right.id));
      return reviewOrder || right.risk_score - left.risk_score || right.integration_count - left.integration_count;
    })
    .slice(0, 15);
  const reviewedCount = edges.filter((edge) => reviewed.has(edge.id) && edge.risk_qa_status !== "OK").length;
  const riskCount = edges.filter((edge) => edge.risk_qa_status !== "OK").length;

  return (
    <aside className="flex h-full min-h-0 w-full flex-col bg-[var(--color-surface)] text-[var(--color-text-primary)]">
      <header className="border-b border-[var(--color-border)] px-5 py-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="app-label text-[var(--color-accent)]">Risk queue</p>
            <h2 className="mt-2 text-2xl font-semibold">Architecture triage</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg hover:bg-[var(--color-hover)]"
            aria-label="Close risk queue"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
          Ranked by pending work, review findings, and affected integrations.
        </p>
        <p className="mt-2 text-xs font-semibold text-[var(--color-text-muted)]" aria-live="polite">
          {reviewedCount} of {riskCount} reviewed in this browser session
        </p>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <div className="space-y-2">
          {ranked.map((edge, index) => (
            <button
              key={edge.id}
              type="button"
              onClick={() => onSelect(edge)}
              className={`group w-full rounded-lg border p-3 text-left transition hover:border-[var(--color-line-strong)] hover:bg-[var(--color-hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-accent)] ${
                reviewed.has(edge.id)
                  ? "border-emerald-700/40 bg-emerald-950/10"
                  : "border-[var(--color-border)] bg-[var(--color-surface-2)]"
              }`}
            >
              <div className="flex items-start gap-3">
                <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-[var(--color-surface)] text-xs font-bold text-[var(--color-text-muted)]">
                  {index + 1}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2 text-sm font-semibold">
                    <span className="truncate" title={edge.source}>{edge.source}</span>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-[var(--color-accent)]" />
                    <span className="truncate" title={edge.target}>{edge.target}</span>
                  </span>
                  <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--color-text-muted)]">
                    {reviewed.has(edge.id) ? (
                      <span className="inline-flex items-center gap-1.5 font-semibold text-emerald-700 dark:text-emerald-400">
                        <Check className="h-3.5 w-3.5" />
                        Reviewed this session
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 font-semibold text-amber-700 dark:text-amber-400">
                        <ShieldAlert className="h-3.5 w-3.5" />
                        {edgeRiskLabel(edge)}
                      </span>
                    )}
                    <span>{edge.integration_count} integration{edge.integration_count === 1 ? "" : "s"}</span>
                    <span className="inline-flex items-center gap-1"><Clock3 className="h-3 w-3" />{relativeAge(edge.last_updated_at)}</span>
                  </span>
                </span>
              </div>
            </button>
          ))}
          {ranked.length === 0 ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-100">
              No dependency paths currently require QA triage.
            </div>
          ) : null}
        </div>
      </div>

      <footer className="border-t border-[var(--color-border)] p-4">
        <Link
          href={`/projects/${projectId}/catalog?qa_status=REVISAR`}
          className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-[var(--color-border)] px-4 py-2.5 text-sm font-semibold hover:bg-[var(--color-hover)]"
        >
          <ExternalLink className="h-4 w-4" />
          Open review catalog
        </Link>
      </footer>
    </aside>
  );
}
