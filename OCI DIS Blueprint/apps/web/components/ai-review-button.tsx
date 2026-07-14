"use client";

/* Governed AI review launcher and result board for project and integration scopes. */

import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Download,
  Eye,
  ListChecks,
  Loader2,
  Route,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  X,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";

import { ConfirmModal } from "@/components/modal";
import { GovernedNarrative } from "@/components/governed-narrative";
import { ActionRecommendationWorkspace } from "@/components/action-recommendation-workspace";
import { api, apiDownloadUrl, getErrorMessage } from "@/lib/api";
import { formatAiReviewDriftValue, isAiReviewLayoutMetadataOnlyDrift } from "@/lib/ai-review";
import type {
  AiReviewBaseline,
  AiReviewCanvasDraftSelection,
  AiReviewCategory,
  AiReviewDriftStatus,
  AiReviewFinding,
  AiReviewGraphContext,
  AiReviewJob,
  AiReviewJobCompare,
  AiReviewProviderStatus,
  AiReviewRecommendationCandidate,
  AiReviewRecommendationWorkspace,
  AiReviewScope,
  AiReviewSeverity,
} from "@/lib/types";

type AiReviewButtonProps = {
  projectId: string;
  integrationId?: string;
  graphContext?: AiReviewGraphContext;
  defaultScope?: AiReviewScope;
  label?: string;
  className?: string;
  disabled?: boolean;
  beforeOpen?: () => boolean | Promise<boolean>;
  open?: boolean;
  onOpenChange?: (_open: boolean) => void;
  hideTrigger?: boolean;
  onPreviewCanvasRecommendation?: (_selection: AiReviewCanvasDraftSelection) => void;
};

const SEVERITY_STYLES: Record<AiReviewSeverity, string> = {
  critical: "border-rose-300 bg-rose-50 text-rose-900 dark:border-[#ff453a]/60 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]",
  high: "border-orange-300 bg-orange-50 text-orange-900 dark:border-[#ff9f0a]/60 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]",
  medium: "border-amber-300 bg-amber-50 text-amber-900 dark:border-[#ffd60a]/50 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]",
  low: "border-slate-300 bg-slate-50 text-slate-800 dark:border-[#0a84ff]/50 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]",
  positive: "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-[#30d158]/50 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]",
};

const SEVERITY_LABELS: Record<AiReviewSeverity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  positive: "Validated",
};

const GROUP_TONES: Record<AiReviewCategory, string> = {
  critical_blockers: "border-rose-300 bg-rose-50/70 dark:border-[#ff453a]/45 dark:bg-[var(--color-surface-2)]",
  high_confidence_fixes: "border-blue-300 bg-blue-50/70 dark:border-[#0a84ff]/45 dark:bg-[var(--color-surface-2)]",
  needs_architect_decision: "border-amber-300 bg-amber-50/80 dark:border-[#ffd60a]/40 dark:bg-[var(--color-surface-2)]",
  looks_production_ready: "border-emerald-300 bg-emerald-50/70 dark:border-[#30d158]/40 dark:bg-[var(--color-surface-2)]",
};

function scoreTone(score: number): string {
  if (score < 55) return "text-rose-600 dark:text-rose-300";
  if (score < 75) return "text-orange-600 dark:text-orange-300";
  if (score < 90) return "text-amber-600 dark:text-amber-300";
  return "text-emerald-600 dark:text-emerald-300";
}

function signoffTone(status: string): string {
  if (status === "blocked") return "border-rose-300 bg-rose-50 text-rose-900 dark:border-[#ff453a]/60 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
  if (status === "needs_review") return "border-orange-300 bg-orange-50 text-orange-900 dark:border-[#ff9f0a]/60 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
  if (status === "ready_with_caveats") return "border-amber-300 bg-amber-50 text-amber-900 dark:border-[#ffd60a]/50 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
  return "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-[#30d158]/50 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
}

function driftTone(status: AiReviewDriftStatus): string {
  if (status === "blocking_drift") return "border-rose-300 bg-rose-50 text-rose-900 dark:border-[#ff453a]/60 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
  if (status === "material_drift") return "border-orange-300 bg-orange-50 text-orange-900 dark:border-[#ff9f0a]/60 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
  if (status === "minor_drift") return "border-amber-300 bg-amber-50 text-amber-900 dark:border-[#ffd60a]/50 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
  if (status === "no_drift") return "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-[#30d158]/50 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
  return "border-slate-300 bg-slate-50 text-slate-800 dark:border-[var(--color-border)] dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
}

function driftLabel(status: AiReviewDriftStatus): string {
  return status.replace(/_/g, " ");
}

function providerModeTone(mode: AiReviewProviderStatus["mode"]): string {
  if (mode === "llm_available") {
    return "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-[#30d158]/45 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
  }
  if (mode === "misconfigured") {
    return "border-rose-300 bg-rose-50 text-rose-900 dark:border-[#ff453a]/60 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
  }
  if (mode === "llm_degraded") {
    return "border-orange-300 bg-orange-50 text-orange-900 dark:border-[#ff9f0a]/60 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
  }
  if (mode === "llm_configured") {
    return "border-blue-300 bg-blue-50 text-blue-900 dark:border-[#0a84ff]/50 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
  }
  return "border-amber-300 bg-amber-50 text-amber-900 dark:border-[#ffd60a]/50 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]";
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function aiReviewJobMatchesScope(
  job: AiReviewJob,
  scope: AiReviewScope,
  integrationId: string | undefined,
): boolean {
  if (job.scope !== scope) {
    return false;
  }
  if (scope === "integration") {
    return Boolean(integrationId) && job.integration_id === integrationId;
  }
  return true;
}

function completedAiReviewJobsForScope(
  jobs: AiReviewJob[],
  scope: AiReviewScope,
  integrationId: string | undefined,
): AiReviewJob[] {
  return jobs.filter(
    (item) =>
      aiReviewJobMatchesScope(item, scope, integrationId) &&
      item.status === "completed" &&
      Boolean(item.result),
  );
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
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-current/15 bg-white/45 p-3 text-xs dark:bg-black/15">
          <p className="font-semibold uppercase tracking-[0.12em] opacity-60">What we found</p>
          <p className="mt-2 text-sm leading-6">{finding.summary}</p>
        </div>
        <div className="rounded-xl border border-current/15 bg-white/45 p-3 text-xs dark:bg-black/15">
          <p className="font-semibold uppercase tracking-[0.12em] opacity-60">Why it matters</p>
          <p className="mt-2 text-sm leading-6">{finding.current_state}</p>
        </div>
      </div>

      <div className="mt-3 rounded-xl border border-current/15 bg-white/45 p-3 dark:bg-black/15">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] opacity-60">Recommended action</p>
        <p className="mt-2 text-sm font-medium leading-6">{finding.recommendation}</p>
      </div>

      <details className="mt-3 rounded-xl border border-current/15 bg-white/45 p-3 text-xs dark:bg-black/15">
        <summary className="cursor-pointer font-semibold uppercase tracking-[0.12em] opacity-70">
          Technical evidence and architecture diff
        </summary>
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
      </details>

      {finding.evidence.length > 0 ? (
        <details className="mt-3 rounded-xl border border-current/15 bg-white/45 p-3 text-xs dark:bg-black/15">
          <summary className="cursor-pointer font-semibold uppercase tracking-[0.12em] opacity-70">Evidence IDs</summary>
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
        </details>
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

const RECOMMENDATION_MODE_LABELS: Record<AiReviewRecommendationCandidate["mode"], string> = {
  minimum_change: "Minimum change",
  resilience: "Higher resilience",
  cost_optimized: "Lower service footprint",
};

function RecommendationWorkspace({
  job,
  workspace,
  selectingCandidateId,
  onPreviewCandidate,
}: {
  job: AiReviewJob;
  workspace: AiReviewRecommendationWorkspace;
  selectingCandidateId: string | null;
  onPreviewCandidate: (_candidate: AiReviewRecommendationCandidate) => void;
}): JSX.Element {
  const acceptedCandidateIds = new Set(
    job.accepted_recommendations
      .filter((item) => item.recommendation_type === "candidate")
      .map((item) => item.finding_id),
  );

  return (
    <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl">
          <p className="app-label">Recommendation workspace</p>
          <h4 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
            Compare governed designs before changing the canvas
          </h4>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            {workspace.recommendation_basis} Previewing records your decision for audit; it does not save the
            integration. Apply a candidate to the unsaved draft and use Simulate impact before deciding to save.
          </p>
        </div>
        <span className="app-theme-chip">{workspace.candidates.length} alternatives</span>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-3">
        {workspace.candidates.map((candidate) => {
          const recommended = candidate.id === workspace.recommended_candidate_id;
          const selected = acceptedCandidateIds.has(candidate.id);
          const blockedChecks = candidate.checks.filter((check) => check.status === "blocked");
          const reviewChecks = candidate.checks.filter((check) => check.status === "review");
          return (
            <article
              key={candidate.id}
              className={`flex min-w-0 flex-col rounded-2xl border bg-[var(--color-surface)] p-4 ${
                recommended ? "border-[var(--color-accent)] shadow-sm" : "border-[var(--color-border)]"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="app-theme-chip">{RECOMMENDATION_MODE_LABELS[candidate.mode]}</span>
                {recommended ? <span className="app-status-chip active">Recommended</span> : null}
              </div>
              <h5 className="mt-3 text-base font-semibold text-[var(--color-text-primary)]">{candidate.title}</h5>
              <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{candidate.summary}</p>

              <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-xl bg-[var(--color-surface-2)] p-3">
                  <p className="font-semibold text-[var(--color-text-primary)]">{candidate.combination_code}</p>
                  <p className="mt-1 text-[var(--color-text-muted)]">Governed combination</p>
                </div>
                <div className="rounded-xl bg-[var(--color-surface-2)] p-3">
                  <p className="font-semibold capitalize text-[var(--color-text-primary)]">{candidate.confidence}</p>
                  <p className="mt-1 text-[var(--color-text-muted)]">Evidence confidence</p>
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-[var(--color-border)] p-3 text-xs">
                <p className="font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Canvas diff</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {candidate.change_set.added_tools.map((tool) => (
                    <span key={`add-${tool}`} className="rounded-full bg-emerald-50 px-2 py-1 font-semibold text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300">
                      + {tool}
                    </span>
                  ))}
                  {candidate.change_set.removed_tools.map((tool) => (
                    <span key={`remove-${tool}`} className="rounded-full bg-rose-50 px-2 py-1 font-semibold text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
                      - {tool}
                    </span>
                  ))}
                  {candidate.change_set.added_overlays.map((tool) => (
                    <span key={`overlay-${tool}`} className="rounded-full bg-blue-50 px-2 py-1 font-semibold text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
                      + overlay {tool}
                    </span>
                  ))}
                  {candidate.change_set.added_tools.length === 0 &&
                  candidate.change_set.removed_tools.length === 0 &&
                  candidate.change_set.added_overlays.length === 0 ? (
                    <span className="text-[var(--color-text-secondary)]">No topology change</span>
                  ) : null}
                </div>
              </div>

              <div className="mt-4 space-y-2">
                {candidate.checks.map((check) => (
                  <div key={check.id} className="flex items-start gap-2 text-xs leading-5 text-[var(--color-text-secondary)]">
                    {check.status === "pass" ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                    ) : check.status === "blocked" ? (
                      <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-500" />
                    ) : (
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                    )}
                    <span><strong className="text-[var(--color-text-primary)]">{check.label}:</strong> {check.detail}</span>
                  </div>
                ))}
              </div>

              <details className="mt-4 rounded-xl border border-[var(--color-border)] p-3 text-xs">
                <summary className="cursor-pointer font-semibold text-[var(--color-text-primary)]">Implementation and validation plan</summary>
                <p className="mt-3 font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">How to implement</p>
                <ol className="mt-2 space-y-1.5 text-[var(--color-text-secondary)]">
                  {candidate.implementation_steps.map((step, index) => <li key={step}>{index + 1}. {step}</li>)}
                </ol>
                <p className="mt-3 font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">Validate before save</p>
                <ul className="mt-2 space-y-1.5 text-[var(--color-text-secondary)]">
                  {candidate.validation_plan.map((step) => <li key={step}>• {step}</li>)}
                </ul>
                {candidate.tradeoffs.length > 0 ? (
                  <p className="mt-3 leading-5 text-[var(--color-text-muted)]">Trade-off: {candidate.tradeoffs.join(" ")}</p>
                ) : null}
              </details>

              <div className="mt-auto pt-4">
                <p className="mb-3 text-xs leading-5 text-[var(--color-text-muted)]">{candidate.cost_impact.detail}</p>
                <button
                  type="button"
                  onClick={() => onPreviewCandidate(candidate)}
                  disabled={!candidate.applicable || selectingCandidateId !== null}
                  className="app-button-primary w-full justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {selectingCandidateId === candidate.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}
                  {selected ? "Preview again on canvas" : blockedChecks.length > 0 ? "Resolve blockers first" : "Preview on canvas"}
                </button>
                {reviewChecks.length > 0 ? (
                  <p className="mt-2 text-center text-[11px] text-[var(--color-text-muted)]">
                    {reviewChecks.length} architect check{reviewChecks.length === 1 ? "" : "s"} remain
                  </p>
                ) : null}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function AiReviewDialog({
  integrationId,
  graphContext,
  selectedScope,
  setSelectedScope,
  job,
  loading,
  acceptingFindingId,
  applyingPatchFindingId,
  baseline,
  baselineHistory,
  baselineLoading,
  baselineSaving,
  baselineLabel,
  baselineNote,
  error,
  providerStatus,
  historyCompare,
  onRun,
  onRequestSaveBaseline,
  onBaselineLabelChange,
  onBaselineNoteChange,
  onAccept,
  onApplyPatch,
  selectingCandidateId,
  onPreviewCandidate,
  history,
  historyLoading,
  onOpenHistoryJob,
  onClose,
}: {
  integrationId?: string;
  graphContext?: AiReviewGraphContext;
  selectedScope: AiReviewScope;
  setSelectedScope: (_scope: AiReviewScope) => void;
  job: AiReviewJob | null;
  loading: boolean;
  acceptingFindingId: string | null;
  applyingPatchFindingId: string | null;
  baseline: AiReviewBaseline | null;
  baselineHistory: AiReviewBaseline[];
  baselineLoading: boolean;
  baselineSaving: boolean;
  baselineLabel: string;
  baselineNote: string;
  error: string | null;
  providerStatus: AiReviewProviderStatus | null;
  historyCompare: AiReviewJobCompare | null;
  onRun: () => void;
  onRequestSaveBaseline: () => void;
  onBaselineLabelChange: (_value: string) => void;
  onBaselineNoteChange: (_value: string) => void;
  onAccept: (_findingId: string) => void;
  onApplyPatch: (_findingId: string) => void;
  selectingCandidateId: string | null;
  onPreviewCandidate: (_candidate: AiReviewRecommendationCandidate) => void;
  history: AiReviewJob[];
  historyLoading: boolean;
  onOpenHistoryJob: (_job: AiReviewJob) => void;
  onClose: () => void;
}): JSX.Element {
  const review = job?.result ?? null;
  const acceptedIds = new Set(job?.accepted_recommendations.map((item) => item.finding_id) ?? []);
  const canRunIntegrationScope = integrationId !== undefined;
  const layoutMetadataOnlyItems =
    review?.drift.items.filter((item) =>
      isAiReviewLayoutMetadataOnlyDrift(item.field, item.planned, item.actual),
    ) ?? [];
  const actionableDriftItems =
    review?.drift.items.filter(
      (item) => !isAiReviewLayoutMetadataOnlyDrift(item.field, item.planned, item.actual),
    ) ?? [];
  const hasHistoricalLayoutOnlyDrift =
    layoutMetadataOnlyItems.length > 0 && actionableDriftItems.length === 0;
  const serviceRulesMetric = review?.metrics.find((metric) => metric.label.toLowerCase() === "service rules") ?? null;
  const evidenceMetrics = review?.metrics.filter((metric) => metric !== serviceRulesMetric) ?? [];

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/35 px-4 py-8 backdrop-blur-sm">
      <button type="button" aria-label="Dismiss AI review" className="absolute inset-0 cursor-default" onClick={onClose} />
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
              {review ? `${review.project_name} architecture review` : "Architecture Review Board"}
            </h3>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Evidence-backed decision brief for architecture sign-off. Review the recommendation, material drift, and
              next actions first; detailed evidence remains available below.
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

        <div className="flex max-h-[calc(100vh-10rem)] flex-col overflow-y-auto px-6 py-5">
          {providerStatus ? (
            <section className={`mb-5 rounded-2xl border p-4 ${providerModeTone(providerStatus.mode)}`}>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] opacity-70">AI explanation status</p>
                  <h4 className="mt-1 text-sm font-semibold leading-6">{providerStatus.status_message}</h4>
                </div>
                <span className="rounded-full border border-current/20 px-3 py-1 text-xs font-semibold uppercase tracking-[0.12em]">
                  {providerStatus.mode.replace(/_/g, " ")}
                </span>
              </div>
              <details className="mt-3 border-t border-current/15 pt-3 text-xs opacity-80">
                <summary className="cursor-pointer font-semibold">Technical provider details</summary>
                <p className="mt-2 leading-5">
                  Model {providerStatus.model} · {providerStatus.region} · Responses-first with Chat fallback ·{" "}
                  {providerStatus.quota.remaining_jobs_today} of {providerStatus.quota.daily_job_limit} jobs remaining
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <span className="app-theme-chip">Responses {providerStatus.transport_strategy.responses_capability}</span>
                  <span className="app-theme-chip">
                    Guardrails {providerStatus.safety.guardrails_enabled ? `v${providerStatus.safety.guardrails_version}` : "off"}
                  </span>
                  <span className="app-theme-chip">{providerStatus.retry_policy.max_retries} retries</span>
                </div>
              </details>
            </section>
          ) : null}

          {graphContext ? (
            <section className="mb-5 flex items-start gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
              <Route className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-accent)]" />
              <div>
                <p className="app-label">Selected topology scope</p>
                <p className="mt-1 text-sm font-semibold text-[var(--color-text-primary)]">
                  {graphContext.type === "node"
                    ? `Graph node: ${graphContext.label}`
                    : `Graph edge: ${graphContext.source} → ${graphContext.target}`}
                </p>
                <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
                  Only integrations adjacent to this selection are included in the review evidence.
                </p>
              </div>
            </section>
          ) : null}

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
              <div className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                      Planned baseline
                    </p>
                    {baselineLoading ? (
                      <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Checking active baseline…</p>
                    ) : baseline ? (
                      <>
                        <p className="mt-2 text-sm font-semibold text-[var(--color-text-primary)]">{baseline.label}</p>
                        <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                          {baseline.row_count} row{baseline.row_count === 1 ? "" : "s"} · saved by {baseline.created_by} ·{" "}
                          {formatJobTimestamp(baseline.created_at)}
                        </p>
                      </>
                    ) : (
                      <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
                        No planned baseline exists for this scope. Save one after the project reflects the approved plan.
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={onRequestSaveBaseline}
                    disabled={baselineSaving || baselineLoading || (selectedScope === "integration" && !canRunIntegrationScope)}
                    className="app-button-secondary px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {baselineSaving ? "Saving…" : baseline ? "Replace baseline" : "Save planned baseline"}
                  </button>
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
                  <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">
                      Baseline label
                    </span>
                    <input
                      value={baselineLabel}
                      onChange={(event) => onBaselineLabelChange(event.target.value)}
                      placeholder="Approved project baseline"
                      className="mt-2 w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">
                      Approval notes
                    </span>
                    <textarea
                      value={baselineNote}
                      onChange={(event) => onBaselineNoteChange(event.target.value)}
                      placeholder="What plan, meeting, or design decision does this baseline represent?"
                      rows={2}
                      className="mt-2 w-full rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
                    />
                  </label>
                </div>
                {baselineHistory.length > 0 ? (
                  <div className="mt-5 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                        Baseline history
                      </p>
                      {baselineHistory[1] ? (
                        <span className="text-xs text-[var(--color-text-secondary)]">
                          Active is {baselineHistory[0].row_count - baselineHistory[1].row_count >= 0 ? "+" : ""}
                          {baselineHistory[0].row_count - baselineHistory[1].row_count} rows vs previous
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-3 grid gap-2">
                      {baselineHistory.slice(0, 5).map((item) => (
                        <article
                          key={item.id}
                          className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-xs"
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="font-semibold text-[var(--color-text-primary)]">{item.label}</p>
                            <span
                              className={
                                item.is_active
                                  ? "app-status-chip active px-2 py-0.5 text-[10px]"
                                  : "app-status-chip archived px-2 py-0.5 text-[10px]"
                              }
                            >
                              {item.is_active ? "Active" : "Archived"}
                            </span>
                          </div>
                          <p className="mt-1 text-[var(--color-text-muted)]">
                            {item.row_count} row{item.row_count === 1 ? "" : "s"} · {formatJobTimestamp(item.created_at)}
                          </p>
                          {item.note ? (
                            <p className="mt-1 leading-5 text-[var(--color-text-secondary)]">{item.note}</p>
                          ) : null}
                        </article>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
              <button type="button" onClick={onRun} className="app-button-primary mt-5 px-5 py-3">
                Start governed review
              </button>
            </section>
          ) : null}

          {!loading && history.length > 0 ? (
            <section className="order-3 mt-5 rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
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
              {historyCompare ? (
                <div className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                    Evolution vs previous completed review
                  </p>
                  <div className="mt-3 grid gap-3 md:grid-cols-3">
                    <div>
                      <p className="text-2xl font-semibold text-[var(--color-text-primary)]">
                        {historyCompare.readiness_score_delta >= 0 ? "+" : ""}
                        {historyCompare.readiness_score_delta}
                      </p>
                      <p className="text-xs text-[var(--color-text-muted)]">readiness score</p>
                    </div>
                    <div>
                      <p className="text-2xl font-semibold text-[var(--color-text-primary)]">
                        {historyCompare.critical_high_delta >= 0 ? "+" : ""}
                        {historyCompare.critical_high_delta}
                      </p>
                      <p className="text-xs text-[var(--color-text-muted)]">critical/high findings</p>
                    </div>
                    <div>
                      <p className="text-2xl font-semibold text-[var(--color-text-primary)]">
                        {historyCompare.resolved_findings.length}
                      </p>
                      <p className="text-xs text-[var(--color-text-muted)]">resolved findings</p>
                    </div>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">{historyCompare.summary}</p>
                </div>
              ) : null}
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
            <div className="order-2 space-y-5">
              {job && review.recommendation_workspace ? (
                <RecommendationWorkspace
                  job={job}
                  workspace={review.recommendation_workspace}
                  selectingCandidateId={selectingCandidateId}
                  onPreviewCandidate={onPreviewCandidate}
                />
              ) : null}
              {review.action_workspace ? (
                <ActionRecommendationWorkspace workspace={review.action_workspace} />
              ) : null}
              <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_14rem]">
                <article className={`rounded-3xl border p-5 ${signoffTone(review.decision_brief.signoff_status)}`}>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                    Decision at a glance
                  </p>
                  <div className="mt-4 grid gap-3 md:grid-cols-3">
                    <div className="rounded-2xl border border-current/15 bg-white/45 p-4 dark:bg-black/15">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] opacity-60">What we found</p>
                      <p className="mt-2 text-sm font-semibold leading-6">{review.decision_brief.headline}</p>
                    </div>
                    <div className="rounded-2xl border border-current/15 bg-white/45 p-4 dark:bg-black/15">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] opacity-60">Why it matters</p>
                      <p className="mt-2 text-sm leading-6">{review.decision_brief.primary_risk}</p>
                    </div>
                    <div className="rounded-2xl border border-current/15 bg-white/45 p-4 dark:bg-black/15">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] opacity-60">What to do next</p>
                      <p className="mt-2 text-sm leading-6">{review.decision_brief.recommended_next_action}</p>
                    </div>
                  </div>
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
                  {review.llm_summary ? (
                    <details className="mt-4 rounded-2xl border border-current/15 bg-white/45 p-4 dark:bg-black/15">
                      <summary className="cursor-pointer text-sm font-semibold">Read the OCI Generative AI explanation</summary>
                      <div className="mt-3">
                        <GovernedNarrative content={review.llm_summary} />
                      </div>
                    </details>
                  ) : (
                    <p className="mt-4 text-sm leading-6 opacity-80">{review.summary}</p>
                  )}
                  {job?.status === "completed" ? (
                    <a
                      href={apiDownloadUrl(`/api/v1/ai-reviews/${job.id}/export`)}
                      download
                      className="mt-4 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-[var(--color-text-secondary)] transition hover:bg-[var(--color-hover)] hover:text-[var(--color-text-primary)]"
                    >
                      <Download className="h-3.5 w-3.5" />
                      Export Markdown
                    </a>
                  ) : null}
                  <p className="mt-4 text-xs text-[var(--color-text-muted)]">
                    Engine: {review.engine} · LLM: {review.llm_status}
                    {review.llm_model ? ` (${review.llm_model})` : ""} · Generated {new Date(review.generated_at).toLocaleString()}
                  </p>
                </article>
                <article className="self-start rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5 text-center">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                    Readiness
                  </p>
                  <p className={`mt-4 text-5xl font-semibold tracking-tight ${scoreTone(review.readiness_score)}`}>
                    {review.readiness_score}
                  </p>
                  <p className="mt-2 text-xs text-[var(--color-text-muted)]">out of 100</p>
                </article>
              </section>

              <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-muted)]">Decision requirements</p>
                    <h4 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">What must be resolved before sign-off</h4>
                    <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                      The board separates decisions that need an architect from conditions that directly block approval.
                    </p>
                  </div>
                  <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${signoffTone(review.decision_brief.signoff_status)}`}>
                    {review.decision_brief.signoff_status.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="mt-4 grid gap-3 lg:grid-cols-2">
                  <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-sm">
                    <p className="font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Architect decisions</p>
                    <ul className="mt-3 space-y-2 leading-6">
                      {review.decision_brief.decision_points.slice(0, 4).map((item) => (
                        <li key={item}>• {item}</li>
                      ))}
                    </ul>
                  </div>
                  <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-sm">
                    <p className="font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Sign-off blockers</p>
                    {review.decision_brief.blockers.length > 0 ? (
                      <ul className="mt-3 space-y-2 leading-6">
                        {review.decision_brief.blockers.slice(0, 5).map((item) => (
                          <li key={item}>• {item}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-3 leading-6 opacity-80">No critical or high-priority blocker is visible.</p>
                    )}
                  </div>
                </div>
              </section>

              <section
                className={`rounded-3xl border p-5 ${
                  hasHistoricalLayoutOnlyDrift
                    ? "border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-text-primary)]"
                    : driftTone(review.drift.status)
                }`}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] opacity-70">
                      Planned vs actual drift
                    </p>
                    <h4 className="mt-2 text-xl font-semibold capitalize">
                      {hasHistoricalLayoutOnlyDrift ? "Historical layout metadata only" : driftLabel(review.drift.status)}
                    </h4>
                    <p className="mt-2 max-w-3xl text-sm leading-6 opacity-85">
                      {hasHistoricalLayoutOnlyDrift
                        ? "This stored review predates semantic canvas comparison. The governed overlays are unchanged; only canvas layout/version metadata differed. New reviews ignore this non-architectural change."
                        : review.drift.summary}
                    </p>
                    {review.drift.baseline ? (
                      <p className="mt-2 text-xs opacity-70">
                        Baseline: {review.drift.baseline.label} · {review.drift.baseline.row_count} row
                        {review.drift.baseline.row_count === 1 ? "" : "s"} · saved{" "}
                        {formatJobTimestamp(review.drift.baseline.created_at)}
                      </p>
                    ) : null}
                  </div>
                  <span className="rounded-full border border-current/20 px-3 py-1 text-xs font-semibold">
                    {hasHistoricalLayoutOnlyDrift
                      ? "0 governed drift items"
                      : `${review.drift.item_count} drift item${review.drift.item_count === 1 ? "" : "s"}`}
                  </span>
                </div>
                {actionableDriftItems.length > 0 ? (
                  <div className="mt-4 grid gap-3 lg:grid-cols-2">
                    {actionableDriftItems.slice(0, 8).map((item) => (
                      <article key={item.id} className="rounded-2xl border border-current/15 bg-white/45 p-3 text-xs dark:bg-black/15">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="font-mono font-semibold opacity-70">{item.id}</p>
                            <h5 className="mt-1 text-sm font-semibold">{item.label}</h5>
                          </div>
                          <span className="rounded-full border border-current/20 px-2 py-0.5 font-semibold uppercase">
                            {item.severity}
                          </span>
                        </div>
                        <dl className="mt-3 grid gap-2 md:grid-cols-2">
                          <div className="rounded-lg border border-current/10 bg-white/45 p-2.5 dark:bg-white/[0.04]">
                            <dt className="font-semibold opacity-65">Approved plan</dt>
                            <dd className="mt-1 break-words text-sm leading-5">
                              {formatAiReviewDriftValue(item.field, item.planned)}
                            </dd>
                          </div>
                          <div className="rounded-lg border border-current/10 bg-white/45 p-2.5 dark:bg-white/[0.04]">
                            <dt className="font-semibold opacity-65">Current state</dt>
                            <dd className="mt-1 break-words text-sm leading-5">
                              {formatAiReviewDriftValue(item.field, item.actual)}
                            </dd>
                          </div>
                        </dl>
                        <p className="mt-2 leading-5 opacity-80">{item.detail}</p>
                        {item.action_href ? (
                          <Link href={item.action_href} className="mt-2 inline-flex font-semibold underline underline-offset-4">
                            Open affected item
                          </Link>
                        ) : null}
                      </article>
                    ))}
                  </div>
                ) : null}
              </section>

              <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[var(--color-text-muted)]">Evidence coverage</p>
                <h4 className="mt-2 text-lg font-semibold text-[var(--color-text-primary)]">What the review measured</h4>
                <p className="mt-1 text-sm leading-6 text-[var(--color-text-secondary)]">
                  Coverage explains how much governed evidence supports the recommendation; it does not replace architectural approval.
                </p>
                <div className="mt-4 grid auto-rows-fr gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {evidenceMetrics.map((metric) => (
                  <article key={metric.label} className="min-w-0 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                      {metric.label}
                    </p>
                    <p className="mt-2 [overflow-wrap:anywhere] text-2xl font-semibold text-[var(--color-text-primary)]">{metric.value}</p>
                    <p className="mt-2 [overflow-wrap:anywhere] text-xs leading-5 text-[var(--color-text-secondary)]">{metric.detail}</p>
                  </article>
                ))}
                </div>
                {serviceRulesMetric ? (
                  <div className="mt-3 grid gap-2 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 md:grid-cols-[10rem_minmax(0,1fr)] md:items-center">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">Service rules</p>
                      <p className="mt-1 text-lg font-semibold text-[var(--color-text-primary)]">{serviceRulesMetric.value}</p>
                    </div>
                    <p className="[overflow-wrap:anywhere] text-sm leading-6 text-[var(--color-text-secondary)]">
                      {serviceRulesMetric.detail.replace(/\.$/, "")}. These versioned rules provide the OCI limits and compatibility evidence used by this review.
                    </p>
                  </div>
                ) : null}
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

              <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                  <div className="flex items-center gap-2">
                    <Route className="h-5 w-5 text-[var(--color-accent)]" />
                    <h4 className="text-lg font-semibold text-[var(--color-text-primary)]">Topology intelligence</h4>
                  </div>
                  <div className="mt-4 grid gap-3">
                    {review.topology_insights.length > 0 ? (
                      review.topology_insights.map((insight) => (
                        <article key={insight.id} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                                {insight.id} · {insight.insight_type.replace(/_/g, " ")}
                              </p>
                              <h5 className="mt-1 font-semibold text-[var(--color-text-primary)]">{insight.title}</h5>
                            </div>
                            <span className="rounded-full border border-[var(--color-border)] px-2 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">
                              {insight.metric}
                            </span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{insight.summary}</p>
                          {insight.action_href ? (
                            <Link href={insight.action_href} className="mt-3 inline-flex text-sm font-semibold underline underline-offset-4">
                              Open scoped catalog
                            </Link>
                          ) : null}
                        </article>
                      ))
                    ) : (
                      <p className="text-sm text-[var(--color-text-secondary)]">No topology insight was generated for this scope.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-[var(--color-accent)]" />
                    <h4 className="text-lg font-semibold text-[var(--color-text-primary)]">Stress scenarios</h4>
                  </div>
                  <div className="mt-4 grid gap-3">
                    {review.stress_scenarios.length > 0 ? (
                      review.stress_scenarios.map((scenario) => (
                        <article key={scenario.id} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                                {scenario.id} · {scenario.multiplier}x · {scenario.confidence} confidence
                              </p>
                              <h5 className="mt-1 font-semibold text-[var(--color-text-primary)]">{scenario.name}</h5>
                            </div>
                            <span className="rounded-full border border-[var(--color-border)] px-2 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">
                              {scenario.projected_daily_payload_gb} GB/day
                            </span>
                          </div>
                          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{scenario.summary}</p>
                          {scenario.warnings.length > 0 ? (
                            <div className="mt-3 space-y-1 text-xs leading-5 text-[var(--color-text-muted)]">
                              {scenario.warnings.slice(0, 3).map((warning) => (
                                <p key={warning}>• {warning}</p>
                              ))}
                            </div>
                          ) : null}
                        </article>
                      ))
                    ) : (
                      <p className="text-sm text-[var(--color-text-secondary)]">No stress scenario was generated for this scope.</p>
                    )}
                  </div>
                </div>
              </section>

              <section className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                <div className="flex items-center gap-2">
                  <ListChecks className="h-5 w-5 text-[var(--color-accent)]" />
                  <h4 className="text-lg font-semibold text-[var(--color-text-primary)]">Remediation plan</h4>
                </div>
                <div className="mt-4 grid gap-3 lg:grid-cols-2">
                  {review.remediation_plan.length > 0 ? (
                    review.remediation_plan.map((step) => (
                      <article key={step.id} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                              {step.id} · Priority {step.priority}
                            </p>
                            <h5 className="mt-1 font-semibold text-[var(--color-text-primary)]">{step.title}</h5>
                          </div>
                          <span className="rounded-full border border-[var(--color-border)] px-2 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">
                            {step.owner}
                          </span>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{step.action}</p>
                        <p className="mt-2 text-xs leading-5 text-[var(--color-text-muted)]">{step.expected_impact}</p>
                        {step.action_href ? (
                          <Link href={step.action_href} className="mt-3 inline-flex text-sm font-semibold underline underline-offset-4">
                            Open action target
                          </Link>
                        ) : null}
                      </article>
                    ))
                  ) : (
                    <p className="text-sm text-[var(--color-text-secondary)]">
                      No remediation steps were generated because the review has no blocking findings.
                    </p>
                  )}
                </div>
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
  label = "Run AI review",
  className = "app-button-secondary gap-2",
  disabled = false,
  beforeOpen,
  open: controlledOpen,
  onOpenChange,
  hideTrigger = false,
  onPreviewCanvasRecommendation,
}: AiReviewButtonProps): JSX.Element {
  const [internalOpen, setInternalOpen] = useState<boolean>(false);
  const open = controlledOpen ?? internalOpen;
  const [selectedScope, setSelectedScope] = useState<AiReviewScope>(defaultScope);
  const [loading, setLoading] = useState<boolean>(false);
  const [job, setJob] = useState<AiReviewJob | null>(null);
  const [history, setHistory] = useState<AiReviewJob[]>([]);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [acceptingFindingId, setAcceptingFindingId] = useState<string | null>(null);
  const [applyingPatchFindingId, setApplyingPatchFindingId] = useState<string | null>(null);
  const [selectingCandidateId, setSelectingCandidateId] = useState<string | null>(null);
  const [baseline, setBaseline] = useState<AiReviewBaseline | null>(null);
  const [baselineHistory, setBaselineHistory] = useState<AiReviewBaseline[]>([]);
  const [baselineLoading, setBaselineLoading] = useState<boolean>(false);
  const [baselineSaving, setBaselineSaving] = useState<boolean>(false);
  const [baselineLabel, setBaselineLabel] = useState<string>("Approved project baseline");
  const [baselineNote, setBaselineNote] = useState<string>("");
  const [preparing, setPreparing] = useState<boolean>(false);

  function setOpen(nextOpen: boolean): void {
    if (controlledOpen === undefined) {
      setInternalOpen(nextOpen);
    }
    onOpenChange?.(nextOpen);
  }

  async function openReview(): Promise<void> {
    if (disabled || preparing) return;
    setPreparing(true);
    try {
      const canOpen = beforeOpen ? await beforeOpen() : true;
      if (canOpen) setOpen(true);
    } finally {
      setPreparing(false);
    }
  }
  const [confirmBaselineOpen, setConfirmBaselineOpen] = useState<boolean>(false);
  const [providerStatus, setProviderStatus] = useState<AiReviewProviderStatus | null>(null);
  const [historyCompare, setHistoryCompare] = useState<AiReviewJobCompare | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!open) {
      return () => {
        cancelled = true;
      };
    }
    setHistoryLoading(true);
    void api
      .getAiReviewProviderStatus()
      .then((response) => {
        if (!cancelled) {
          setProviderStatus(response);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProviderStatus(null);
        }
      });
    void api
      .listAiReviewJobs(projectId)
      .then((response) => {
        if (!cancelled) {
          const scopedJobs = response.jobs.filter((item) =>
            aiReviewJobMatchesScope(item, selectedScope, integrationId),
          );
          setHistory(scopedJobs);
          const completedJobs = completedAiReviewJobsForScope(scopedJobs, selectedScope, integrationId);
          if (completedJobs.length >= 2) {
            void api
              .compareAiReviewJobs(projectId, {
                base_job_id: completedJobs[1].id,
                target_job_id: completedJobs[0].id,
              })
              .then((comparison) => {
                if (!cancelled) {
                  setHistoryCompare(comparison);
                }
              })
              .catch(() => {
                if (!cancelled) {
                  setHistoryCompare(null);
                }
              });
          } else {
            setHistoryCompare(null);
          }
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHistory([]);
          setHistoryCompare(null);
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
  }, [integrationId, open, projectId, selectedScope]);

  useEffect(() => {
    let cancelled = false;
    if (!open || (selectedScope === "integration" && !integrationId)) {
      setBaseline(null);
      return () => {
        cancelled = true;
      };
    }
    setBaselineLoading(true);
    void api
      .getAiReviewBaseline(projectId, {
        scope: selectedScope,
        integration_id: selectedScope === "integration" ? integrationId : undefined,
      })
      .then((response) => {
        if (!cancelled) {
          setBaseline(response.baseline);
          if (response.baseline) {
            setBaselineLabel(response.baseline.label);
            setBaselineNote(response.baseline.note ?? "");
          } else {
            setBaselineLabel(selectedScope === "integration" ? "Approved integration baseline" : "Approved project baseline");
            setBaselineNote("");
          }
        }
      })
      .catch(() => {
        if (!cancelled) {
          setBaseline(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setBaselineLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [integrationId, open, projectId, selectedScope]);

  useEffect(() => {
    let cancelled = false;
    if (!open || (selectedScope === "integration" && !integrationId)) {
      setBaselineHistory([]);
      return () => {
        cancelled = true;
      };
    }
    void api
      .listAiReviewBaselines(projectId, {
        scope: selectedScope,
        integration_id: selectedScope === "integration" ? integrationId : undefined,
        limit: 10,
      })
      .then((response) => {
        if (!cancelled) {
          setBaselineHistory(response.baselines);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setBaselineHistory([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [integrationId, open, projectId, selectedScope]);

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
        const scopedJobs = refreshed.jobs.filter((item) =>
          aiReviewJobMatchesScope(item, selectedScope, integrationId),
        );
        setHistory(scopedJobs);
        const completedJobs = completedAiReviewJobsForScope(scopedJobs, selectedScope, integrationId);
        if (completedJobs.length >= 2) {
          const comparison = await api.compareAiReviewJobs(projectId, {
            base_job_id: completedJobs[1].id,
            target_job_id: completedJobs[0].id,
          });
          setHistoryCompare(comparison);
        } else {
          setHistoryCompare(null);
        }
      } catch {}
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to run AI review."));
    } finally {
      setLoading(false);
    }
  }

  async function saveBaseline(): Promise<void> {
    if (selectedScope === "integration" && !integrationId) return;
    setBaselineSaving(true);
    setError(null);
    try {
      const saved = await api.createAiReviewBaseline(projectId, {
        scope: selectedScope,
        integration_id: selectedScope === "integration" ? integrationId : undefined,
        label: baselineLabel.trim() || undefined,
        note: baselineNote.trim() || undefined,
      });
      setBaseline(saved);
      const historyResponse = await api.listAiReviewBaselines(projectId, {
        scope: selectedScope,
        integration_id: selectedScope === "integration" ? integrationId : undefined,
        limit: 10,
      });
      setBaselineHistory(historyResponse.baselines);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to save planned baseline."));
    } finally {
      setBaselineSaving(false);
      setConfirmBaselineOpen(false);
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

  async function previewCandidate(candidate: AiReviewRecommendationCandidate): Promise<void> {
    if (!job || !job.result?.recommendation_workspace || !onPreviewCanvasRecommendation) return;
    setSelectingCandidateId(candidate.id);
    setError(null);
    try {
      const response = await api.selectAiReviewCandidateForDraft(
        job.id,
        candidate.id,
        "Selected for local canvas comparison from the governed review board.",
      );
      setJob(response.job);
      setHistory((current) => current.map((item) => (item.id === response.job.id ? response.job : item)));
      onPreviewCanvasRecommendation({
        jobId: response.job.id,
        candidate: response.candidate,
        baselineCanvasState: job.result.recommendation_workspace.current_canvas_state,
      });
      setOpen(false);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to prepare the canvas preview."));
    } finally {
      setSelectingCandidateId(null);
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
      {!hideTrigger ? (
        <button
          type="button"
          onClick={() => void openReview()}
          disabled={disabled || preparing}
          className={className}
        >
          {preparing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {preparing ? "Preparing evidence…" : label}
        </button>
      ) : null}
      {open ? (
        <AiReviewDialog
          integrationId={integrationId}
          graphContext={graphContext}
          selectedScope={selectedScope}
          setSelectedScope={setSelectedScope}
          job={job}
          loading={loading}
          acceptingFindingId={acceptingFindingId}
          applyingPatchFindingId={applyingPatchFindingId}
          selectingCandidateId={selectingCandidateId}
          baseline={baseline}
          baselineHistory={baselineHistory}
          baselineLoading={baselineLoading}
          baselineSaving={baselineSaving}
          baselineLabel={baselineLabel}
          baselineNote={baselineNote}
          error={error}
          providerStatus={providerStatus}
          historyCompare={historyCompare}
          onRun={() => {
            void runReview();
          }}
          onRequestSaveBaseline={() => {
            if (baseline) {
              setConfirmBaselineOpen(true);
            } else {
              void saveBaseline();
            }
          }}
          onBaselineLabelChange={setBaselineLabel}
          onBaselineNoteChange={setBaselineNote}
          onAccept={(findingId) => {
            void acceptFinding(findingId);
          }}
          onApplyPatch={(findingId) => {
            void applyFindingPatch(findingId);
          }}
          onPreviewCandidate={(candidate) => {
            void previewCandidate(candidate);
          }}
          history={history}
          historyLoading={historyLoading}
          onOpenHistoryJob={(historyJob) => {
            void openHistoryJob(historyJob);
          }}
          onClose={() => setOpen(false)}
        />
      ) : null}
      <ConfirmModal
        open={confirmBaselineOpen}
        title="Replace planned baseline"
        description="The current active baseline will be archived and the current governed state will become the new planned baseline for drift detection."
        confirmLabel="Replace baseline"
        cancelLabel="Keep current"
        onConfirm={() => {
          void saveBaseline();
        }}
        onCancel={() => setConfirmBaselineOpen(false)}
      />
    </>
  );
}
