"use client";

/* Governed AI review launcher and result board for project and integration scopes. */

import Link from "next/link";
import { AlertTriangle, ClipboardCheck, Loader2, ShieldCheck, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api, getErrorMessage } from "@/lib/api";
import type {
  AiReviewCategory,
  AiReviewFinding,
  AiReviewGraphContext,
  AiReviewJob,
  AiReviewScope,
  AiReviewSeverity,
} from "@/lib/types";

type AiReviewButtonProps = {
  projectId: string;
  integrationId?: string;
  graphContext?: AiReviewGraphContext;
  defaultScope?: AiReviewScope;
};

const SEVERITY_STYLES: Record<AiReviewSeverity, string> = {
  critical: "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-100",
  high: "border-orange-300 bg-orange-50 text-orange-900 dark:border-orange-900 dark:bg-orange-950/40 dark:text-orange-100",
  medium: "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100",
  low: "border-slate-300 bg-slate-50 text-slate-800 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-100",
  positive: "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100",
};

const SEVERITY_LABELS: Record<AiReviewSeverity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  positive: "Validated",
};

const GROUP_TONES: Record<AiReviewCategory, string> = {
  critical_blockers: "border-rose-300 bg-rose-50/70 dark:border-rose-950 dark:bg-rose-950/20",
  high_confidence_fixes: "border-blue-300 bg-blue-50/70 dark:border-blue-950 dark:bg-blue-950/20",
  needs_architect_decision: "border-amber-300 bg-amber-50/80 dark:border-amber-950 dark:bg-amber-950/20",
  looks_production_ready: "border-emerald-300 bg-emerald-50/70 dark:border-emerald-950 dark:bg-emerald-950/20",
};

function scoreTone(score: number): string {
  if (score < 55) return "text-rose-600 dark:text-rose-300";
  if (score < 75) return "text-orange-600 dark:text-orange-300";
  if (score < 90) return "text-amber-600 dark:text-amber-300";
  return "text-emerald-600 dark:text-emerald-300";
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function FindingCard({
  finding,
  accepted,
  accepting,
  applyingPatch,
  onAccept,
  onApplyPatch,
}: {
  finding: AiReviewFinding;
  accepted: boolean;
  accepting: boolean;
  applyingPatch: boolean;
  onAccept: (_findingId: string) => void;
  onApplyPatch: (_findingId: string) => void;
}): JSX.Element {
  return (
    <article className={`rounded-2xl border p-4 ${SEVERITY_STYLES[finding.severity]}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-70">
            {SEVERITY_LABELS[finding.severity]} · {finding.review_area.replace(/_/g, " ")}
          </p>
          <h4 className="mt-1 text-base font-semibold">{finding.title}</h4>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {finding.integration_ids.length > 0 ? (
            <span className="rounded-full border border-current/20 px-2 py-1 text-xs font-semibold">
              {finding.integration_ids.length} linked
            </span>
          ) : null}
          {accepted ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-current/20 px-2 py-1 text-xs font-semibold">
              <ClipboardCheck className="h-3 w-3" />
              Accepted
            </span>
          ) : null}
        </div>
      </div>
      <p className="mt-2 text-sm leading-6 opacity-85">{finding.summary}</p>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-current/15 bg-white/45 p-3 text-xs dark:bg-black/15">
          <p className="font-semibold uppercase tracking-[0.12em] opacity-60">Current</p>
          <p className="mt-2 leading-5">{finding.current_state}</p>
        </div>
        <div className="rounded-xl border border-current/15 bg-white/45 p-3 text-xs dark:bg-black/15">
          <p className="font-semibold uppercase tracking-[0.12em] opacity-60">Recommended</p>
          <p className="mt-2 leading-5">{finding.recommended_state}</p>
        </div>
      </div>

      <p className="mt-3 text-sm font-medium leading-6">{finding.recommendation}</p>

      <div className="mt-3 rounded-xl border border-current/15 bg-white/45 p-3 text-xs dark:bg-black/15">
        <p className="font-semibold uppercase tracking-[0.12em] opacity-60">Architecture diff</p>
        <div className="mt-2 grid gap-2 md:grid-cols-2">
          <div>
            <p className="font-semibold opacity-70">Current design</p>
            <p className="mt-1 leading-5">{finding.current_state}</p>
          </div>
          <div>
            <p className="font-semibold opacity-70">Recommended design</p>
            <p className="mt-1 leading-5">{finding.recommended_state}</p>
          </div>
        </div>
        {finding.suggested_patch ? (
          <div className="mt-3 rounded-lg border border-current/10 bg-white/40 p-3 dark:bg-black/10">
            <p className="font-semibold opacity-75">{finding.suggested_patch.label}</p>
            <p className="mt-1 leading-5 opacity-80">{finding.suggested_patch.description}</p>
            <div className="mt-2 space-y-2">
              {finding.suggested_patch.field_diffs.map((diff) => (
                <div key={diff.field} className="grid gap-2 md:grid-cols-2">
                  <p>
                    <span className="font-semibold">Current {diff.field}: </span>
                    {diff.current || "—"}
                  </p>
                  <p>
                    <span className="font-semibold">Recommended {diff.field}: </span>
                    {diff.recommended || "—"}
                  </p>
                </div>
              ))}
            </div>
            <p className="mt-2 text-[11px] font-medium leading-5 opacity-75">{finding.suggested_patch.safety_note}</p>
          </div>
        ) : null}
      </div>

      {finding.evidence.length > 0 ? (
        <div className="mt-3 rounded-xl border border-current/15 bg-white/45 p-3 text-xs dark:bg-black/15">
          <p className="font-semibold uppercase tracking-[0.12em] opacity-60">Evidence IDs</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {finding.evidence_ids.map((item) => (
              <span key={item} className="rounded-full bg-current/10 px-2 py-1 font-mono">
                {item}
              </span>
            ))}
          </div>
          <div className="mt-2 space-y-1 leading-5 opacity-80">
            {finding.evidence.slice(0, 4).map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {finding.action_href ? (
          <Link href={finding.action_href} className="inline-flex text-sm font-semibold underline underline-offset-4">
            {finding.action_label}
          </Link>
        ) : (
          <p className="text-sm font-semibold">{finding.action_label}</p>
        )}
        {finding.severity !== "positive" ? (
          <button
            type="button"
            onClick={() => onAccept(finding.id)}
            disabled={accepted || accepting}
            className="rounded-full border border-current/25 px-3 py-1.5 text-xs font-semibold transition hover:bg-current/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {accepting ? "Accepting…" : accepted ? "Accepted" : "Accept recommendation"}
          </button>
        ) : null}
        {finding.suggested_patch ? (
          <button
            type="button"
            onClick={() => onApplyPatch(finding.id)}
            disabled={accepted || applyingPatch || !finding.suggested_patch.safe_to_apply}
            className="rounded-full border border-current/25 px-3 py-1.5 text-xs font-semibold transition hover:bg-current/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {applyingPatch ? "Applying…" : accepted ? "Applied" : "Apply suggested patch"}
          </button>
        ) : null}
      </div>
    </article>
  );
}

function formatJobTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function jobResultLabel(job: AiReviewJob): string {
  if (job.result) {
    return `${job.result.readiness_score}/100 · ${job.result.findings.length} finding${
      job.result.findings.length === 1 ? "" : "s"
    }`;
  }
  if (job.status === "failed") {
    return "Failed before producing a board";
  }
  return "Waiting for review board output";
}

function AiReviewDialog({
  integrationId,
  selectedScope,
  setSelectedScope,
  job,
  loading,
  acceptingFindingId,
  applyingPatchFindingId,
  error,
  onRun,
  onAccept,
  onApplyPatch,
  history,
  historyLoading,
  onOpenHistoryJob,
  onClose,
}: {
  integrationId?: string;
  selectedScope: AiReviewScope;
  setSelectedScope: (_scope: AiReviewScope) => void;
  job: AiReviewJob | null;
  loading: boolean;
  acceptingFindingId: string | null;
  applyingPatchFindingId: string | null;
  error: string | null;
  onRun: () => void;
  onAccept: (_findingId: string) => void;
  onApplyPatch: (_findingId: string) => void;
  history: AiReviewJob[];
  historyLoading: boolean;
  onOpenHistoryJob: (_job: AiReviewJob) => void;
  onClose: () => void;
}): JSX.Element {
  const review = job?.result ?? null;
  const acceptedIds = new Set(job?.accepted_recommendations.map((item) => item.finding_id) ?? []);
  const canRunIntegrationScope = integrationId !== undefined;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/35 px-4 py-8 backdrop-blur-sm">
      <button type="button" aria-label="Close AI review" className="absolute inset-0 cursor-default" onClick={onClose} />
      <section
        className="relative w-full max-w-6xl overflow-hidden rounded-[2rem] border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl"
        role="dialog"
        aria-modal="true"
        aria-label="Governed AI review"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] px-6 py-5">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-accent)]">
              <Sparkles className="h-4 w-4" />
              Governed AI Review
            </p>
            <h3 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
              Architecture Review Board
            </h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Job-based review across QA, service sizing, canvas compatibility, 10x stress, red-team contradictions,
              and reviewer personas. Catalog data changes only when you explicitly apply a deterministic suggested patch.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[var(--color-border)] p-2 text-[var(--color-text-muted)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]"
            aria-label="Close AI review"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-[calc(100vh-10rem)] overflow-y-auto px-6 py-5">
          {!job && !loading ? (
            <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                Review scope
              </p>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setSelectedScope("project")}
                  className={[
                    "rounded-2xl border px-4 py-4 text-left transition",
                    selectedScope === "project"
                      ? "border-[var(--color-accent)] bg-[var(--color-surface-3)]"
                      : "border-[var(--color-border)] hover:border-[var(--color-accent)]",
                  ].join(" ")}
                >
                  <span className="font-semibold text-[var(--color-text-primary)]">Project review</span>
                  <span className="mt-2 block text-sm text-[var(--color-text-secondary)]">
                    Full project board with catalog, snapshots, graph-adjacent evidence, and demo readiness.
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (canRunIntegrationScope) setSelectedScope("integration");
                  }}
                  disabled={!canRunIntegrationScope}
                  className={[
                    "rounded-2xl border px-4 py-4 text-left transition disabled:cursor-not-allowed disabled:opacity-50",
                    selectedScope === "integration"
                      ? "border-[var(--color-accent)] bg-[var(--color-surface-3)]"
                      : "border-[var(--color-border)] hover:border-[var(--color-accent)]",
                  ].join(" ")}
                >
                  <span className="font-semibold text-[var(--color-text-primary)]">Integration review</span>
                  <span className="mt-2 block text-sm text-[var(--color-text-secondary)]">
                    Focused review for the current integration, canvas route, pattern, and service compatibility.
                  </span>
                </button>
              </div>
              <button type="button" onClick={onRun} className="app-button-primary mt-5 px-5 py-3">
                Start governed review
              </button>
            </section>
          ) : null}

          {!loading && history.length > 0 ? (
            <section className="mt-5 rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                    Review history
                  </p>
                  <h4 className="mt-1 text-lg font-semibold text-[var(--color-text-primary)]">
                    Recent governed review jobs
                  </h4>
                </div>
                {historyLoading ? (
                  <span className="inline-flex items-center gap-2 text-xs font-semibold text-[var(--color-text-muted)]">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Refreshing
                  </span>
                ) : null}
              </div>
              <div className="mt-4 grid gap-2 md:grid-cols-2">
                {history.slice(0, 4).map((historyJob) => (
                  <button
                    key={historyJob.id}
                    type="button"
                    onClick={() => onOpenHistoryJob(historyJob)}
                    className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-left transition hover:border-[var(--color-accent)] hover:bg-[var(--color-surface-3)]"
                  >
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-[var(--color-border)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-secondary)]">
                        {historyJob.scope}
                      </span>
                      <span className="rounded-full border border-[var(--color-border)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-secondary)]">
                        {historyJob.status}
                      </span>
                    </span>
                    <span className="mt-2 block text-sm font-semibold text-[var(--color-text-primary)]">
                      {jobResultLabel(historyJob)}
                    </span>
                    <span className="mt-1 block text-xs text-[var(--color-text-muted)]">
                      {formatJobTimestamp(historyJob.created_at)}
                    </span>
                  </button>
                ))}
              </div>
            </section>
          ) : null}

          {loading ? (
            <div className="flex min-h-[18rem] flex-col items-center justify-center text-center">
              <Loader2 className="h-8 w-8 animate-spin text-[var(--color-accent)]" />
              <p className="mt-4 text-lg font-semibold text-[var(--color-text-primary)]">Running governed review job</p>
              <p className="mt-2 max-w-md text-sm text-[var(--color-text-secondary)]">
                Building evidence IDs, deterministic findings, reviewer personas, and optional LLM synthesis.
              </p>
              {job ? (
                <p className="mt-3 font-mono text-xs text-[var(--color-text-muted)]">
                  Job {job.id} · {job.status}
                </p>
              ) : null}
            </div>
          ) : null}

          {error ? (
            <div className="rounded-2xl border border-rose-300 bg-rose-50 p-5 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-100">
              <div className="flex items-center gap-2 font-semibold">
                <AlertTriangle className="h-5 w-5" />
                Review failed
              </div>
              <p className="mt-2 text-sm">{error}</p>
            </div>
          ) : null}

          {review && !loading ? (
            <div className="space-y-5">
              <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_14rem]">
                <article className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                    Review summary
                  </p>
                  <h4 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">{review.readiness_label}</h4>
                  <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
                    {review.llm_summary ?? review.summary}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {review.llm_summary ? (
                      <span className="rounded-full border border-emerald-300 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">
                        LLM synthesis completed
                      </span>
                    ) : null}
                    <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">
                      Scope: {review.scope}
                    </span>
                    {job ? (
                      <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">
                        Job: {job.status}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-4 text-xs text-[var(--color-text-muted)]">
                    Engine: {review.engine} · LLM: {review.llm_status}
                    {review.llm_model ? ` (${review.llm_model})` : ""} · Generated {new Date(review.generated_at).toLocaleString()}
                  </p>
                </article>
                <article className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5 text-center">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                    Readiness
                  </p>
                  <p className={`mt-4 text-5xl font-semibold tracking-tight ${scoreTone(review.readiness_score)}`}>
                    {review.readiness_score}
                  </p>
                  <p className="mt-2 text-xs text-[var(--color-text-muted)]">out of 100</p>
                </article>
              </section>

              <section className="grid gap-3 md:grid-cols-5">
                {review.metrics.map((metric) => (
                  <article key={metric.label} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                      {metric.label}
                    </p>
                    <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{metric.value}</p>
                    <p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">{metric.detail}</p>
                  </article>
                ))}
              </section>

              <section className="grid gap-3 md:grid-cols-4">
                {review.reviewer_personas.map((persona) => (
                  <article key={persona.persona} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                      {persona.persona}
                    </p>
                    <h4 className="mt-2 font-semibold text-[var(--color-text-primary)]">{persona.title}</h4>
                    <p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">{persona.summary}</p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {persona.focus.slice(0, 3).map((item) => (
                        <span key={item} className="rounded-full bg-[var(--color-surface-3)] px-2 py-1 text-[10px] font-semibold text-[var(--color-text-secondary)]">
                          {item}
                        </span>
                      ))}
                    </div>
                  </article>
                ))}
              </section>

              <section className="space-y-4">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-[var(--color-accent)]" />
                  <h4 className="text-lg font-semibold text-[var(--color-text-primary)]">Review board</h4>
                </div>
                {review.groups.map((group) =>
                  group.count > 0 ? (
                    <div key={group.id} className={`rounded-3xl border p-4 ${GROUP_TONES[group.id]}`}>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <h5 className="text-base font-semibold text-[var(--color-text-primary)]">{group.title}</h5>
                          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{group.description}</p>
                        </div>
                        <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">
                          {group.count} item{group.count === 1 ? "" : "s"}
                        </span>
                      </div>
                      <div className="mt-4 grid gap-3 lg:grid-cols-2">
                        {review.findings
                          .filter((finding) => finding.category === group.id)
                          .map((finding) => (
                            <FindingCard
                              key={finding.id}
                              finding={finding}
                              accepted={acceptedIds.has(finding.id)}
                              accepting={acceptingFindingId === finding.id}
                              applyingPatch={applyingPatchFindingId === finding.id}
                              onAccept={onAccept}
                              onApplyPatch={onApplyPatch}
                            />
                          ))}
                      </div>
                    </div>
                  ) : null,
                )}
              </section>

              <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                  Formal evidence registry
                </p>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {review.evidence.map((entry) => (
                    <div key={entry.id} className="rounded-xl bg-[var(--color-surface-3)] px-3 py-2 text-xs text-[var(--color-text-secondary)]">
                      <p className="font-mono font-semibold text-[var(--color-text-primary)]">{entry.id}</p>
                      <p className="mt-1 font-semibold">{entry.label}</p>
                      <p className="mt-1 leading-5">{entry.detail}</p>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}

export function AiReviewButton({
  projectId,
  integrationId,
  graphContext,
  defaultScope = integrationId ? "integration" : "project",
}: AiReviewButtonProps): JSX.Element {
  const [open, setOpen] = useState<boolean>(false);
  const [selectedScope, setSelectedScope] = useState<AiReviewScope>(defaultScope);
  const [loading, setLoading] = useState<boolean>(false);
  const [job, setJob] = useState<AiReviewJob | null>(null);
  const [history, setHistory] = useState<AiReviewJob[]>([]);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [acceptingFindingId, setAcceptingFindingId] = useState<string | null>(null);
  const [applyingPatchFindingId, setApplyingPatchFindingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!open) {
      return () => {
        cancelled = true;
      };
    }
    setHistoryLoading(true);
    void api
      .listAiReviewJobs(projectId)
      .then((response) => {
        if (!cancelled) {
          setHistory(response.jobs);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHistory([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setHistoryLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, projectId]);

  async function pollJob(jobId: string): Promise<AiReviewJob> {
    let current = await api.getAiReviewJob(jobId);
    setJob(current);
    for (let attempt = 0; attempt < 45 && ["pending", "running"].includes(current.status); attempt += 1) {
      await delay(1200);
      current = await api.getAiReviewJob(jobId);
      setJob(current);
    }
    return current;
  }

  async function runReview(): Promise<void> {
    setLoading(true);
    setJob(null);
    setError(null);
    try {
      const created = await api.runAiReview(projectId, {
        scope: selectedScope,
        integration_id: selectedScope === "integration" ? integrationId : undefined,
        graph_context: selectedScope === "project" ? graphContext : undefined,
        include_llm: true,
      });
      setJob(created);
      const completed = await pollJob(created.id);
      if (completed.status === "failed") {
        setError("The AI review job failed. Check the job evidence or API logs for details.");
      }
      try {
        const refreshed = await api.listAiReviewJobs(projectId);
        setHistory(refreshed.jobs);
      } catch {}
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to run AI review."));
    } finally {
      setLoading(false);
    }
  }

  async function acceptFinding(findingId: string): Promise<void> {
    if (!job) return;
    setAcceptingFindingId(findingId);
    setError(null);
    try {
      const updated = await api.acceptAiReviewFinding(job.id, findingId, "Accepted from the review board.");
      setJob(updated);
      setHistory((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to accept recommendation."));
    } finally {
      setAcceptingFindingId(null);
    }
  }

  async function applyFindingPatch(findingId: string): Promise<void> {
    if (!job) return;
    setApplyingPatchFindingId(findingId);
    setError(null);
    try {
      const response = await api.applyAiReviewFindingPatch(
        job.id,
        findingId,
        "Applied from the governed review board.",
      );
      setJob(response.job);
      setHistory((current) => current.map((item) => (item.id === response.job.id ? response.job : item)));
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to apply suggested patch."));
    } finally {
      setApplyingPatchFindingId(null);
    }
  }

  async function openHistoryJob(historyJob: AiReviewJob): Promise<void> {
    setSelectedScope(historyJob.scope);
    setJob(historyJob);
    setError(null);
    if (historyJob.status === "pending" || historyJob.status === "running") {
      setLoading(true);
      try {
        const completed = await pollJob(historyJob.id);
        if (completed.status === "failed") {
          setError("The AI review job failed. Check the job evidence or API logs for details.");
        }
      } catch (caughtError) {
        setError(getErrorMessage(caughtError, "Unable to refresh AI review job."));
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setOpen(true);
        }}
        className="inline-flex items-center justify-center gap-2 rounded-xl bg-[var(--color-text-primary)] px-4 py-2 text-sm font-semibold text-[var(--color-surface)] shadow-sm transition hover:translate-y-[-1px] hover:shadow-md"
      >
        <Sparkles className="h-4 w-4" />
        Run AI review
      </button>
      {open ? (
        <AiReviewDialog
          integrationId={integrationId}
          selectedScope={selectedScope}
          setSelectedScope={setSelectedScope}
          job={job}
          loading={loading}
          acceptingFindingId={acceptingFindingId}
          applyingPatchFindingId={applyingPatchFindingId}
          error={error}
          onRun={() => {
            void runReview();
          }}
          onAccept={(findingId) => {
            void acceptFinding(findingId);
          }}
          onApplyPatch={(findingId) => {
            void applyFindingPatch(findingId);
          }}
          history={history}
          historyLoading={historyLoading}
          onOpenHistoryJob={(historyJob) => {
            void openHistoryJob(historyJob);
          }}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}
