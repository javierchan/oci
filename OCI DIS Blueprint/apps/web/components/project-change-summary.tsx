import { ArrowRightLeft } from "lucide-react";

import type { ChangeSummary } from "@/lib/project-decision";

const TONE: Record<ChangeSummary["tone"], string> = {
  positive: "border-emerald-400/40 bg-emerald-500/5",
  neutral: "border-[var(--color-border)] bg-[var(--color-surface-2)]",
  attention: "border-amber-400/40 bg-amber-500/5",
};

export function ProjectChangeSummary({ changes }: { changes: ChangeSummary[] }): JSX.Element | null {
  if (changes.length === 0) return null;
  return (
    <section aria-labelledby="project-change-title" className="app-card p-5">
      <div className="flex items-center gap-2 text-[var(--color-accent)]"><ArrowRightLeft className="h-5 w-5" /><p className="app-label">Change intelligence</p></div>
      <h2 id="project-change-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">What changed since the last review</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {changes.map((change) => (
          <article key={change.title} className={`rounded-lg border p-4 ${TONE[change.tone]}`}>
            <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">{change.title}</h3>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{change.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
