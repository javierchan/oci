import Link from "next/link";
import { ArrowRight, CircleAlert } from "lucide-react";

import type { DashboardRisk } from "@/lib/types";

type QaWorkQueueProps = {
  projectId: string;
  reviewCount: number;
  pendingCount: number;
  risks: DashboardRisk[];
};

export function QaWorkQueue({ projectId, reviewCount, pendingCount, risks }: QaWorkQueueProps): JSX.Element | null {
  const total = reviewCount + pendingCount;
  if (total === 0) return null;

  const href = `/projects/${projectId}/catalog?qa_status=${pendingCount > 0 ? "PENDING" : "REVIEW"}`;
  return (
    <section aria-labelledby="qa-work-queue-title" className="app-card border-[var(--color-qa-review-border)] p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 gap-3">
          <span className="mt-0.5 rounded-lg bg-[var(--color-qa-review-bg)] p-2 text-[var(--color-qa-review-text)]">
            <CircleAlert className="h-5 w-5" />
          </span>
          <div>
            <p className="app-label text-[var(--color-qa-review-text)]">QA work queue</p>
            <h2 id="qa-work-queue-title" className="mt-1 text-xl font-semibold text-[var(--color-text-primary)]">
              {total} integration{total === 1 ? " needs" : "s need"} a decision
            </h2>
            <p className="mt-1 text-sm leading-6 text-[var(--color-text-secondary)]">
              {reviewCount} need architect review · {pendingCount} still need required information.
            </p>
          </div>
        </div>
        <Link href={href} className="app-button-secondary shrink-0 gap-2">
          Open queue <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
      {risks.length > 0 ? (
        <ul className="mt-4 grid gap-2 md:grid-cols-3">
          {risks.map((risk) => (
            <li key={risk.code} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
              <p className="text-sm font-semibold text-[var(--color-text-primary)]">{risk.label}</p>
              <p className="mt-1 text-xs leading-5 text-[var(--color-text-secondary)]">
                {risk.count} affected integration{risk.count === 1 ? "" : "s"}
              </p>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
