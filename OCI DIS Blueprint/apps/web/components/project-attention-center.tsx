"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, CircleAlert, GitBranch, Gauge, ShieldCheck } from "lucide-react";

import type { AttentionItem } from "@/lib/project-decision";
import { api } from "@/lib/api";
import type { ProjectAttentionTask } from "@/lib/types";

const SOURCE = {
  qa: { label: "QA", icon: ShieldCheck },
  topology: { label: "Topology", icon: GitBranch },
  coverage: { label: "Evidence", icon: Gauge },
  bom: { label: "BOM", icon: CircleAlert },
} as const;

const PRIORITY_CLASS: Record<AttentionItem["priority"], string> = {
  critical: "border-rose-400/50 bg-rose-500/10 text-rose-800 dark:text-rose-200",
  high: "border-orange-400/50 bg-orange-500/10 text-orange-800 dark:text-orange-200",
  medium: "border-amber-400/50 bg-amber-500/10 text-amber-800 dark:text-amber-200",
  low: "border-slate-400/50 bg-slate-500/10 text-slate-800 dark:text-slate-200",
};

export function ProjectAttentionCenter({ projectId, items }: { projectId: string; items: AttentionItem[] }): JSX.Element {
  const [tasks, setTasks] = useState<ProjectAttentionTask[]>([]);
  const [error, setError] = useState<string>("");
  const taskByKey = useMemo(() => new Map(tasks.map((task) => [task.attention_key, task])), [tasks]);

  useEffect(() => {
    let cancelled = false;
    void api.listProjectAttentionTasks(projectId).then((response) => {
      if (!cancelled) setTasks(response.tasks);
    }).catch((caughtError) => {
      if (!cancelled) setError(caughtError instanceof Error ? caughtError.message : "Unable to load coordination tasks.");
    });
    return () => { cancelled = true; };
  }, [projectId]);

  async function assign(item: AttentionItem): Promise<void> {
    const assignee = window.prompt("Assign this evidence item to", "")?.trim();
    if (!assignee) return;
    const dueDate = window.prompt("Due date (YYYY-MM-DD, optional)", "")?.trim() || null;
    try {
      const task = await api.createProjectAttentionTask(projectId, {
        attention_key: item.id, source: item.source, title: item.title, evidence_href: item.href,
        assignee, due_date: dueDate, note: item.detail,
      });
      setTasks((current) => [...current, task]);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to assign this attention item.");
    }
  }

  async function setTaskStatus(task: ProjectAttentionTask, status: "in_progress" | "resolved"): Promise<void> {
    const evidenceText = status === "resolved"
      ? window.prompt("Record the evidence or decision that resolves this coordination task", "")?.trim()
      : undefined;
    if (status === "resolved" && !evidenceText) return;
    try {
      const updated = await api.updateProjectAttentionTask(projectId, task.id, {
        status,
        evidence: evidenceText ? { summary: evidenceText } : undefined,
      });
      setTasks((current) => current.map((entry) => entry.id === updated.id ? updated : entry));
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to update the coordination task.");
    }
  }

  return (
    <section id="attention-center" aria-labelledby="attention-center-title" className="app-card overflow-hidden p-0 scroll-mt-6">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-5">
        <div>
          <p className="app-label">Project operations</p>
          <h2 id="attention-center-title" className="mt-1 text-xl font-semibold text-[var(--color-text-primary)]">Attention center</h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            One deterministic work list across QA, topology, evidence coverage, and governed commercial readiness.
          </p>
        </div>
        <span className="app-theme-chip">{items.length} prioritized item{items.length === 1 ? "" : "s"}</span>
      </div>
      {items.length === 0 ? (
        <div className="px-5 py-8 text-sm text-[var(--color-text-secondary)]">No material attention items are currently derived from the governed project evidence.</div>
      ) : (
        <ol className="divide-y divide-[var(--color-border)]">
          {items.map((item) => {
            const source = SOURCE[item.source];
            const Icon = source.icon;
            const task = taskByKey.get(item.id);
            return (
              <li key={item.id} className="flex flex-wrap items-start justify-between gap-4 px-5 py-4">
                <div className="flex min-w-0 gap-3">
                  <span className="mt-0.5 rounded-lg bg-[var(--color-surface-3)] p-2 text-[var(--color-accent)]"><Icon className="h-4 w-4" /></span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold capitalize ${PRIORITY_CLASS[item.priority]}`}>{item.priority}</span>
                      <span className="app-theme-chip">{source.label}</span>
                    </div>
                    <h3 className="mt-2 text-sm font-semibold text-[var(--color-text-primary)]">{item.title}</h3>
                    <p className="mt-1 text-sm leading-5 text-[var(--color-text-secondary)]">{item.detail}</p>
                    {task ? (
                      <p className={`mt-2 text-xs font-medium ${task.is_overdue ? "text-rose-600 dark:text-rose-300" : "text-[var(--color-text-muted)]"}`}>
                        {task.status.replace("_", " ")} · {task.assignee ?? "Unassigned"}{task.due_date ? ` · due ${task.due_date}` : ""}{task.is_overdue ? " · overdue" : ""}
                      </p>
                    ) : null}
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  {!task ? <button type="button" onClick={() => void assign(item)} className="app-button-secondary text-xs">Assign</button> : null}
                  {task?.status === "open" ? <button type="button" onClick={() => void setTaskStatus(task, "in_progress")} className="app-button-secondary text-xs">Start</button> : null}
                  {task && task.status !== "resolved" ? <button type="button" onClick={() => void setTaskStatus(task, "resolved")} className="app-button-secondary text-xs">Resolve</button> : null}
                  <Link href={item.href} className="app-button-secondary gap-2">Open evidence <ArrowRight className="h-4 w-4" /></Link>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {error ? <p className="border-t border-[var(--color-border)] px-5 py-3 text-xs text-rose-600 dark:text-rose-300">{error}</p> : null}
    </section>
  );
}
