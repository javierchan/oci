"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, CheckCircle2, CircleDot } from "lucide-react";

import type { AiReviewActionWorkspace } from "@/lib/types";

const STATUS_META = {
  ready: { icon: CheckCircle2, label: "Ready to execute", tone: "text-emerald-600" },
  review: { icon: CircleDot, label: "Architect review", tone: "text-amber-600" },
  blocked: { icon: AlertTriangle, label: "Blocked", tone: "text-rose-600" },
} as const;

export function ActionRecommendationWorkspace({
  workspace,
}: {
  workspace: AiReviewActionWorkspace;
}): JSX.Element {
  return (
    <section className="space-y-4 border-t border-[var(--color-border)] pt-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-4xl">
          <p className="app-label">Governed alternatives (optional)</p>
          <h3 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">{workspace.title}</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            {workspace.recommendation_basis} The current design stays authoritative until an architect applies a
            candidate and runs Simulate impact or recalculation.
          </p>
        </div>
        <span className="app-theme-chip">{workspace.candidates.length} actions</span>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        {workspace.candidates.map((candidate) => {
          const meta = STATUS_META[candidate.status];
          const StatusIcon = meta.icon;
          return (
            <article key={candidate.id} className="flex min-w-0 flex-col rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold">
                <span className="app-theme-chip capitalize">{candidate.priority}</span>
                <span className={`inline-flex items-center gap-1.5 ${meta.tone}`}>
                  <StatusIcon className="h-4 w-4" />
                  {meta.label}
                </span>
              </div>
              <h4 className="mt-3 text-base font-semibold text-[var(--color-text-primary)]">{candidate.title}</h4>
              <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{candidate.summary}</p>

              <div className="mt-4 space-y-4 text-xs leading-5">
                <div>
                  <p className="font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">What to change</p>
                  <ul className="mt-2 space-y-1.5 text-[var(--color-text-secondary)]">
                    {candidate.what_to_change.map((item) => <li key={item}>• {item}</li>)}
                  </ul>
                </div>
                <details className="rounded-xl border border-[var(--color-border)] p-3">
                  <summary className="cursor-pointer font-semibold text-[var(--color-text-primary)]">How to implement and validate</summary>
                  <ol className="mt-3 space-y-1.5 text-[var(--color-text-secondary)]">
                    {candidate.implementation_steps.map((item, index) => <li key={item}>{index + 1}. {item}</li>)}
                  </ol>
                  <p className="mt-3 font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Validation</p>
                  <ul className="mt-2 space-y-1.5 text-[var(--color-text-secondary)]">
                    {candidate.validation_plan.map((item) => <li key={item}>• {item}</li>)}
                  </ul>
                </details>
                <div>
                  <p className="font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Expected impact</p>
                  <p className="mt-2 text-[var(--color-text-secondary)]">{candidate.expected_impact.join(" ")}</p>
                </div>
              </div>

              {candidate.action_href && candidate.action_label ? (
                <Link href={candidate.action_href} className="app-button-secondary mt-4 w-full justify-center gap-2">
                  {candidate.action_label}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              ) : null}
              <p className="mt-3 text-[11px] text-[var(--color-text-muted)]">
                Confidence: {candidate.confidence} · {candidate.evidence_ids.length} evidence reference{candidate.evidence_ids.length === 1 ? "" : "s"}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
