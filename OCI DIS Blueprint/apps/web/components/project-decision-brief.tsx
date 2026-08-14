import Link from "next/link";
import { ArrowRight, BadgeCheck, CircleAlert, ShieldAlert } from "lucide-react";

import type { DecisionBrief } from "@/lib/project-decision";

const STATUS = {
  blocked: { label: "Blocked", icon: ShieldAlert, className: "border-rose-400/45 bg-rose-500/5 text-rose-800 dark:text-rose-200" },
  needs_review: { label: "Needs review", icon: CircleAlert, className: "border-amber-400/45 bg-amber-500/5 text-amber-900 dark:text-amber-200" },
  ready_with_caveats: { label: "Ready with caveats", icon: CircleAlert, className: "border-blue-400/45 bg-blue-500/5 text-blue-900 dark:text-blue-200" },
  ready: { label: "Ready", icon: BadgeCheck, className: "border-emerald-400/45 bg-emerald-500/5 text-emerald-900 dark:text-emerald-200" },
} as const;

export function ProjectDecisionBrief({ brief }: { brief: DecisionBrief }): JSX.Element {
  const status = STATUS[brief.status];
  const Icon = status.icon;
  return (
    <section aria-labelledby="decision-brief-title" className={`app-card border p-5 ${status.className}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <div className="flex items-center gap-2">
            <Icon className="h-5 w-5" aria-hidden="true" />
            <p className="app-label">Decision brief · {status.label}</p>
          </div>
          <h2 id="decision-brief-title" className="mt-3 text-xl font-semibold text-[var(--color-text-primary)]">
            {brief.headline}
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{brief.recommendation}</p>
        </div>
        <Link href={brief.primaryAction.href} className="app-button-primary shrink-0 gap-2">
          {brief.primaryAction.label} <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
      <dl className="mt-5 grid gap-px overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-border)] sm:grid-cols-4">
        <div className="bg-[var(--color-surface)] p-3">
          <dt className="app-label">Confidence</dt>
          <dd className="mt-1 text-sm font-semibold text-[var(--color-text-primary)]">{brief.confidence}</dd>
        </div>
        {brief.evidence.map((item) => (
          <div key={item.label} className="bg-[var(--color-surface)] p-3">
            <dt className="app-label">{item.label}</dt>
            <dd className="mt-1 text-sm font-semibold text-[var(--color-text-primary)]">{item.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
