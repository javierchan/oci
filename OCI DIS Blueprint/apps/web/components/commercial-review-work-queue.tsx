"use client";

import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  ClipboardList,
  Loader2,
  RefreshCcw,
  Save,
  UserRound,
} from "lucide-react";
import { useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";

import { emitToast } from "@/hooks/use-toast";
import { api, getErrorMessage } from "@/lib/api";
import {
  commercialReviewEntityLabel,
  commercialReviewPriorityPresentation,
  commercialReviewWorkflowLabel,
  toDateTimeLocal,
} from "@/lib/commercial-review-queue";
import { formatDate, formatNumber } from "@/lib/format";
import type {
  CommercialReviewEntityType,
  CommercialReviewWorkItem,
  CommercialReviewWorkQueue,
  CommercialReviewWorkflowStatus,
} from "@/lib/types";

type AssignmentDraft = {
  assignee: string;
  workflowStatus: CommercialReviewWorkflowStatus;
  dueAt: string;
  note: string;
};

function itemKey(item: CommercialReviewWorkItem): string {
  return `${item.entity_type}:${item.entity_id}`;
}

function initialDraft(item: CommercialReviewWorkItem): AssignmentDraft {
  return {
    assignee: item.assignee ?? "",
    workflowStatus: item.workflow_status,
    dueAt: toDateTimeLocal(item.due_at),
    note: item.note ?? "",
  };
}

function summaryCards(queue: CommercialReviewWorkQueue): Array<{
  label: string;
  value: number;
  detail: string;
}> {
  return [
    {
      label: "Unresolved",
      value: queue.summary.total,
      detail: `${formatNumber(queue.summary.exceptions)} exceptions · ${formatNumber(queue.summary.mapping_candidates)} mappings · ${formatNumber(queue.summary.product_coverage)} products`,
    },
    {
      label: "Urgent + high",
      value: queue.summary.urgent + queue.summary.high,
      detail: `${formatNumber(queue.summary.urgent)} urgent · ${formatNumber(queue.summary.high)} high`,
    },
    {
      label: "Unassigned",
      value: queue.summary.unassigned,
      detail: "Operational owner is not yet established",
    },
    {
      label: "Overdue",
      value: queue.summary.overdue,
      detail: "Due date passed; commercial state is unchanged",
    },
  ];
}

export function CommercialReviewWorkQueue({
  onOpenAdvancedReview,
}: {
  onOpenAdvancedReview: () => void;
}): JSX.Element {
  const [queue, setQueue] = useState<CommercialReviewWorkQueue | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [entityType, setEntityType] = useState<"all" | CommercialReviewEntityType>("all");
  const [priority, setPriority] = useState("all");
  const [workflowStatus, setWorkflowStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [drafts, setDrafts] = useState<Record<string, AssignmentDraft>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await api.getCommercialReviewWorkQueue({
        search: deferredQuery || undefined,
        entity_type: entityType,
        priority: priority as "all" | "urgent" | "high" | "normal" | "low",
        workflow_status: workflowStatus as
          | "all"
          | CommercialReviewWorkflowStatus,
        page,
        page_size: 20,
      });
      setQueue(next);
      setDrafts((current) => {
        const nextDrafts = { ...current };
        for (const item of next.items) {
          if (!nextDrafts[itemKey(item)]) {
            nextDrafts[itemKey(item)] = initialDraft(item);
          }
        }
        return nextDrafts;
      });
    } catch (loadError) {
      setError(getErrorMessage(loadError, "Unable to load the commercial review work queue."));
    } finally {
      setLoading(false);
    }
  }, [deferredQuery, entityType, page, priority, workflowStatus]);

  useEffect(() => {
    void load();
  }, [load]);

  const cards = useMemo(() => (queue ? summaryCards(queue) : []), [queue]);
  const pageCount = queue ? Math.max(1, Math.ceil(queue.total / queue.page_size)) : 1;

  function updateDraft(
    item: CommercialReviewWorkItem,
    patch: Partial<AssignmentDraft>,
  ): void {
    const key = itemKey(item);
    setDrafts((current) => ({
      ...current,
      [key]: { ...(current[key] ?? initialDraft(item)), ...patch },
    }));
  }

  async function saveAssignment(item: CommercialReviewWorkItem): Promise<void> {
    const key = itemKey(item);
    const draft = drafts[key] ?? initialDraft(item);
    if (draft.workflowStatus !== "unassigned" && !draft.assignee.trim()) {
      emitToast("error", "Choose an assignee before saving this workflow state.");
      return;
    }
    setSaving(key);
    try {
      const updated = await api.replaceCommercialReviewAssignment(item.entity_type, item.entity_id, {
        assignee:
          draft.workflowStatus === "unassigned" ? null : draft.assignee.trim(),
        workflow_status: draft.workflowStatus,
        due_at: draft.dueAt ? new Date(draft.dueAt).toISOString() : null,
        note: draft.note.trim() || null,
      });
      emitToast("success", "Operational ownership updated. Commercial disposition was not changed.");
      setDrafts((current) => ({ ...current, [key]: initialDraft(updated) }));
      await load();
    } catch (saveError) {
      emitToast("error", getErrorMessage(saveError, "Unable to update operational ownership."));
    } finally {
      setSaving(null);
    }
  }

  return (
    <section className="app-card min-w-0 overflow-hidden" aria-labelledby="commercial-work-queue-title">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-5">
        <div className="max-w-3xl">
          <div className="flex items-center gap-2 text-[var(--color-accent)]">
            <ClipboardList className="h-5 w-5" />
            <p className="app-label">M71 · Commercial review operations</p>
          </div>
          <h2 id="commercial-work-queue-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
            Governed commercial work queue
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            Priorities schedule human review from explicit evidence, BOM impact, blockers, and due dates. Assignment changes only operational metadata; approval remains in the governed decision controls below.
          </p>
          {queue?.source_release_version ? (
            <p className="mt-2 text-xs text-[var(--color-text-muted)]">
              Active global release: <span className="font-mono">{queue.source_release_version}</span>
            </p>
          ) : null}
        </div>
        <button className="app-button-secondary gap-2" type="button" disabled={loading} onClick={() => void load()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
          Refresh
        </button>
      </div>

      {queue ? (
        <div className="grid gap-px border-b border-[var(--color-border)] bg-[var(--color-border)] sm:grid-cols-2 xl:grid-cols-4">
          {cards.map((card) => (
            <div key={card.label} className="bg-[var(--color-surface-2)] p-4">
              <p className="app-label">{card.label}</p>
              <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{formatNumber(card.value)}</p>
              <p className="mt-1 text-xs leading-5 text-[var(--color-text-secondary)]">{card.detail}</p>
            </div>
          ))}
        </div>
      ) : null}

      <div className="grid gap-3 border-b border-[var(--color-border)] px-5 py-4 lg:grid-cols-[minmax(16rem,1fr)_repeat(3,minmax(10rem,0.25fr))]">
        <label className="relative">
          <span className="sr-only">Search commercial review work</span>
          <input
            className="app-input pr-10"
            value={query}
            placeholder="Search product, part number, or category"
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <select
          aria-label="Filter review item type"
          className="app-select"
          value={entityType}
          onChange={(event) => {
            setEntityType(event.target.value as "all" | CommercialReviewEntityType);
            setPage(1);
          }}
        >
          <option value="all">All item types</option>
          <option value="exception">Exceptions</option>
          <option value="mapping_candidate">SKU mappings</option>
          <option value="product_coverage">Product coverage</option>
        </select>
        <select
          aria-label="Filter review priority"
          className="app-select"
          value={priority}
          onChange={(event) => {
            setPriority(event.target.value);
            setPage(1);
          }}
        >
          <option value="all">All priorities</option>
          <option value="urgent">Urgent</option>
          <option value="high">High</option>
          <option value="normal">Normal</option>
          <option value="low">Low</option>
        </select>
        <select
          aria-label="Filter review workflow status"
          className="app-select"
          value={workflowStatus}
          onChange={(event) => {
            setWorkflowStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="all">All workflow states</option>
          <option value="unassigned">Unassigned</option>
          <option value="assigned">Assigned</option>
          <option value="in_progress">In progress</option>
          <option value="waiting_evidence">Waiting for evidence</option>
        </select>
      </div>

      {error ? (
        <div role="alert" className="border-b border-rose-400/45 bg-rose-500/5 px-5 py-4 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="divide-y divide-[var(--color-border)]">
        {loading && !queue ? (
          <div className="flex items-center gap-2 px-5 py-10 text-sm text-[var(--color-text-secondary)]">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading governed review work…
          </div>
        ) : null}
        {!loading && queue?.items.length === 0 ? (
          <div className="px-5 py-10 text-sm text-[var(--color-text-secondary)]">
            No unresolved review work matches these filters.
          </div>
        ) : null}
        {queue?.items.map((item) => {
          const key = itemKey(item);
          const draft = drafts[key] ?? initialDraft(item);
          const priorityPresentation = commercialReviewPriorityPresentation(item.priority_tier);
          return (
            <details key={key} className="group">
              <summary className="cursor-pointer list-none px-5 py-4 hover:bg-[var(--color-surface-2)]">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${priorityPresentation.className}`}>
                        {priorityPresentation.label} · {item.priority_score}
                      </span>
                      <span className="app-theme-chip">{commercialReviewEntityLabel(item.entity_type)}</span>
                      <span className="app-theme-chip">{commercialReviewWorkflowLabel(item.workflow_status)}</span>
                      {item.overdue ? (
                        <span className="rounded-full border border-rose-400/50 bg-rose-500/10 px-2 py-0.5 text-xs font-semibold text-rose-700 dark:text-rose-300">Overdue</span>
                      ) : null}
                    </div>
                    <h3 className="mt-2 truncate font-semibold text-[var(--color-text-primary)]">{item.title}</h3>
                    <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                      {item.part_number ?? "No part number"} · {item.category ?? "Uncategorized"} · Source state: {item.source_status.replaceAll("_", " ")}
                    </p>
                  </div>
                  <div className="text-right text-xs text-[var(--color-text-secondary)]">
                    <p>{item.assignee ? `Owner: ${item.assignee}` : "No owner"}</p>
                    <p className="mt-1">{item.due_at ? `Due ${formatDate(item.due_at)}` : "No due date"}</p>
                  </div>
                </div>
              </summary>
              <div className="border-t border-[var(--color-border)] bg-[var(--color-surface-2)] px-5 py-5">
                <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.7fr)]">
                  <div>
                    <p className="app-label">Why this priority</p>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      {item.priority_signals.map((signal) => (
                        <div key={signal.code} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                          <p className="text-sm font-semibold text-[var(--color-text-primary)]">+{signal.points} · {signal.label}</p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                      <p className="app-label">Next governed action</p>
                      <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{item.recommended_next_action}</p>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--color-text-secondary)]">
                        {item.bom_impact ? <span className="app-theme-chip">Approved BOM mapping impact</span> : null}
                        <span className="app-theme-chip">{item.blocker_count} blocker{item.blocker_count === 1 ? "" : "s"}</span>
                      </div>
                    </div>
                    <button type="button" className="app-button-secondary mt-4 gap-2" onClick={onOpenAdvancedReview}>
                      Open governed decision controls <ArrowRight className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                    <div className="flex items-center gap-2">
                      <UserRound className="h-4 w-4 text-[var(--color-accent)]" />
                      <p className="font-semibold text-[var(--color-text-primary)]">Operational ownership</p>
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <label className="text-sm text-[var(--color-text-secondary)]">
                        Workflow state
                        <select
                          className="app-select mt-1.5 w-full"
                          value={draft.workflowStatus}
                          onChange={(event) => {
                            const nextStatus = event.target.value as CommercialReviewWorkflowStatus;
                            updateDraft(item, {
                              workflowStatus: nextStatus,
                              assignee: nextStatus === "unassigned" ? "" : draft.assignee,
                            });
                          }}
                        >
                          <option value="unassigned">Unassigned</option>
                          <option value="assigned">Assigned</option>
                          <option value="in_progress">In progress</option>
                          <option value="waiting_evidence">Waiting for evidence</option>
                        </select>
                      </label>
                      <label className="text-sm text-[var(--color-text-secondary)]">
                        Assignee
                        <input
                          className="app-input mt-1.5"
                          disabled={draft.workflowStatus === "unassigned"}
                          value={draft.assignee}
                          placeholder="Reviewer identifier"
                          onChange={(event) => updateDraft(item, { assignee: event.target.value })}
                        />
                      </label>
                      <label className="text-sm text-[var(--color-text-secondary)] sm:col-span-2">
                        <span className="flex items-center gap-1.5"><CalendarClock className="h-4 w-4" /> Due date</span>
                        <input
                          type="datetime-local"
                          className="app-input mt-1.5"
                          value={draft.dueAt}
                          onChange={(event) => updateDraft(item, { dueAt: event.target.value })}
                        />
                      </label>
                      <label className="text-sm text-[var(--color-text-secondary)] sm:col-span-2">
                        Operational note
                        <textarea
                          className="app-input mt-1.5 min-h-24 resize-y"
                          maxLength={2000}
                          value={draft.note}
                          placeholder="Record the next evidence or coordination step. Do not record an approval here."
                          onChange={(event) => updateDraft(item, { note: event.target.value })}
                        />
                      </label>
                    </div>
                    <button
                      type="button"
                      className="app-button-primary mt-4 w-full gap-2"
                      disabled={saving === key}
                      onClick={() => void saveAssignment(item)}
                    >
                      {saving === key ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                      Save operational ownership
                    </button>
                    <div className="mt-3 flex items-start gap-2 text-xs leading-5 text-[var(--color-text-secondary)]">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-300" />
                      This action cannot approve a candidate, resolve an exception, or publish product coverage.
                    </div>
                  </div>
                </div>
              </div>
            </details>
          );
        })}
      </div>

      {queue ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-border)] px-5 py-4 text-sm">
          <p className="text-[var(--color-text-secondary)]">
            Page {queue.page} of {pageCount} · {formatNumber(queue.total)} matching items
          </p>
          <div className="flex gap-2">
            <button className="app-button-secondary" type="button" disabled={page <= 1 || loading} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</button>
            <button className="app-button-secondary" type="button" disabled={page >= pageCount || loading} onClick={() => setPage((current) => current + 1)}>Next</button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
