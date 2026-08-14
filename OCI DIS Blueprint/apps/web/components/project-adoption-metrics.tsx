import { Activity } from "lucide-react";

import type { AdoptionMetric } from "@/lib/project-decision";

export function ProjectAdoptionMetrics({ metrics }: { metrics: AdoptionMetric[] }): JSX.Element {
  return (
    <section className="expert-mode-only app-card p-5" aria-labelledby="adoption-metrics-title">
      <div className="flex items-center gap-2 text-[var(--color-accent)]"><Activity className="h-5 w-5" /><p className="app-label">Operational signals</p></div>
      <h2 id="adoption-metrics-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Governance activity</h2>
      <p className="mt-1 text-sm leading-6 text-[var(--color-text-secondary)]">Signals are derived only from retained audit evidence; they never infer effort, productivity, or commercial approval.</p>
      <dl className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
            <dt className="app-label">{metric.label}</dt>
            <dd className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{metric.value}</dd>
            <p className="mt-1 text-xs leading-5 text-[var(--color-text-secondary)]">{metric.detail}</p>
          </div>
        ))}
      </dl>
    </section>
  );
}
