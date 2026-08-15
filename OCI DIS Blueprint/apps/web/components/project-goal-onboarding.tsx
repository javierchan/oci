"use client";

import Link from "next/link";
import { BarChart3, ClipboardCheck, FileUp, ReceiptText } from "lucide-react";
import { useEffect, useState } from "react";

type GoalId = "import" | "qa" | "sizing" | "cost";

type Goal = {
  id: GoalId;
  label: string;
  detail: string;
  href: string;
  icon: typeof FileUp;
};

function storageKey(projectId: string): string {
  return `oci-dis-project-goal:${projectId}`;
}

export function ProjectGoalOnboarding({ projectId }: { projectId: string }): JSX.Element {
  const [selected, setSelected] = useState<GoalId | null>(null);
  const goals: Goal[] = [
    { id: "import", label: "Import inventory", detail: "Bring in the governed source workbook.", href: `/projects/${projectId}/import`, icon: FileUp },
    { id: "qa", label: "Resolve QA", detail: "Clear missing evidence and architect decisions.", href: `/projects/${projectId}/catalog?qa_status=REVIEW`, icon: ClipboardCheck },
    { id: "sizing", label: "Estimate capacity", detail: "Review technical sizing and readiness.", href: `/projects/${projectId}#attention-center`, icon: BarChart3 },
    { id: "cost", label: "Review cost", detail: "Compare governed deployment scenarios and BOM.", href: `/projects/${projectId}/bom`, icon: ReceiptText },
  ];

  useEffect(() => {
    const saved = window.localStorage.getItem(storageKey(projectId));
    if (saved === "import" || saved === "qa" || saved === "sizing" || saved === "cost") setSelected(saved);
  }, [projectId]);

  function choose(goal: GoalId): void {
    setSelected(goal);
    window.localStorage.setItem(storageKey(projectId), goal);
  }

  return (
    <section className="app-card p-5" aria-labelledby="project-goal-title">
      <p className="app-label">Start with your goal</p>
      <h2 id="project-goal-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">What are you here to do?</h2>
      <p className="mt-1 text-sm leading-6 text-[var(--color-text-secondary)]">Choose an objective once; the app keeps the preference for this project and takes you to governed evidence.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {goals.map((goal) => {
          const Icon = goal.icon;
          const active = selected === goal.id;
          return (
            <Link
              key={goal.id}
              href={goal.href}
              onClick={() => choose(goal.id)}
              className={`rounded-lg border p-4 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)] ${active ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)]" : "border-[var(--color-border)] bg-[var(--color-surface-2)] hover:bg-[var(--color-hover)]"}`}
            >
              <Icon className="h-5 w-5 text-[var(--color-accent)]" />
              <h3 className="mt-3 text-sm font-semibold text-[var(--color-text-primary)]">{goal.label}</h3>
              <p className="mt-1 text-xs leading-5 text-[var(--color-text-secondary)]">{goal.detail}</p>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
