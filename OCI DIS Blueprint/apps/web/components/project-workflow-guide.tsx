import Link from "next/link";
import { ArrowRight, CheckCircle2, Circle, CircleDot } from "lucide-react";

import type { ProjectWorkflowGuide as ProjectWorkflowGuideData } from "@/lib/project-workflow";

const STEP_ICON = {
  complete: CheckCircle2,
  current: CircleDot,
  upcoming: Circle,
} as const;

export function ProjectWorkflowGuide({ guide }: { guide: ProjectWorkflowGuideData }): JSX.Element {
  return (
    <section aria-labelledby="project-workflow-title" className="app-card overflow-hidden p-0">
      <div className="grid gap-0 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.6fr)]">
        <div className="border-b border-[var(--color-border)] bg-[var(--color-surface-2)] p-5 lg:border-b-0 lg:border-r">
          <p className="app-label">Recommended next step</p>
          <h2 id="project-workflow-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
            {guide.nextAction.label}
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{guide.nextAction.description}</p>
          <p className="mt-3 text-xs leading-5 text-[var(--color-text-muted)]">Why now: {guide.nextAction.reason}</p>
          <Link href={guide.nextAction.href} className="app-button-primary mt-5 inline-flex gap-2">
            Continue
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
        <ol className="grid divide-y divide-[var(--color-border)] md:grid-cols-5 md:divide-x md:divide-y-0">
          {guide.steps.map((step, index) => {
            const Icon = STEP_ICON[step.state];
            return (
              <li key={step.id} className="min-w-0 p-4">
                <Link href={step.href} className="group block rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]">
                  <div className="flex items-center gap-2">
                    <Icon className={`h-4 w-4 shrink-0 ${step.state === "complete" ? "text-[var(--color-status-active-text)]" : step.state === "current" ? "text-[var(--color-accent)]" : "text-[var(--color-text-muted)]"}`} />
                    <span className="text-xs font-semibold text-[var(--color-text-primary)]">{index + 1}. {step.label}</span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">{step.description}</p>
                </Link>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
