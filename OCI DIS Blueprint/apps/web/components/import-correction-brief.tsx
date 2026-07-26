"use client";

/* Structured, presentation-safe rendering for Import Correction Agent output. */

import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  FileWarning,
  ShieldCheck,
} from "lucide-react";

import type {
  AgentOutputBrief,
  AgentOutputQuality,
  AgentRun,
} from "@/lib/types";

export interface ImportCorrectionDeviation {
  source_field: string | null;
  target_field: string | null;
  issue: string;
  evidence: string;
  proposed_action: string;
  confidence: "high" | "medium" | "low";
}

export interface ImportCorrectionBriefData {
  explanation: string;
  deviations: ImportCorrectionDeviation[];
  excluded_fields: string[];
  required_decisions: string[];
}

export function selectLatestImportCorrectionSessionRun(
  runs: AgentRun[],
  sessionId: string,
): AgentRun | null {
  return (
    runs.find(
      (run) =>
        run.agent_type === "import_quality" &&
        run.status === "completed" &&
        run.context.external_capture_session_id === sessionId &&
        !run.context.external_capture_draft_id,
    ) ?? null
  );
}

function asNonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function uniqueStrings(value: unknown, limit = 20): string[] {
  if (!Array.isArray(value)) return [];
  return [
    ...new Set(
      value
        .map(asNonEmptyString)
        .filter((item): item is string => item !== null),
    ),
  ].slice(0, limit);
}

function decodeJsonObject(value: string): Record<string, unknown> | null {
  const trimmed = value.trim();
  const fenced = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  const candidates = [fenced?.[1] ?? trimmed];
  const firstBrace = trimmed.indexOf("{");
  const lastBrace = trimmed.lastIndexOf("}");
  if (firstBrace >= 0 && lastBrace > firstBrace) {
    candidates.push(trimmed.slice(firstBrace, lastBrace + 1));
  }
  for (const candidate of candidates) {
    try {
      const decoded: unknown = JSON.parse(candidate);
      if (decoded && typeof decoded === "object" && !Array.isArray(decoded)) {
        return decoded as Record<string, unknown>;
      }
    } catch {
      // Historical provider output may contain prose around a valid JSON object.
    }
  }
  return null;
}

export function parseImportCorrectionBrief(
  summary: string | null | undefined,
): ImportCorrectionBriefData | null {
  if (!summary) return null;
  const decoded = decodeJsonObject(summary);
  if (!decoded) return null;
  const explanation = asNonEmptyString(decoded.explanation);
  if (!explanation) return null;
  const deviations = Array.isArray(decoded.deviations)
    ? decoded.deviations
        .map((value): ImportCorrectionDeviation | null => {
          if (!value || typeof value !== "object" || Array.isArray(value)) {
            return null;
          }
          const item = value as Record<string, unknown>;
          const issue = asNonEmptyString(item.issue);
          const evidence = asNonEmptyString(item.evidence);
          const proposedAction = asNonEmptyString(item.proposed_action);
          if (!issue || !evidence || !proposedAction) return null;
          const confidenceValue = asNonEmptyString(item.confidence)?.toLowerCase();
          const confidence =
            confidenceValue === "high" ||
            confidenceValue === "medium" ||
            confidenceValue === "low"
              ? confidenceValue
              : "medium";
          return {
            source_field: asNonEmptyString(item.source_field),
            target_field: asNonEmptyString(item.target_field),
            issue,
            evidence,
            proposed_action: proposedAction,
            confidence,
          };
        })
        .filter(
          (item): item is ImportCorrectionDeviation => item !== null,
        )
        .slice(0, 20)
    : [];
  return {
    explanation,
    deviations,
    excluded_fields: uniqueStrings(decoded.excluded_fields),
    required_decisions: uniqueStrings(decoded.required_decisions),
  };
}

function fieldLabel(value: string | null): string {
  return value?.replaceAll("_", " ") ?? "Evidence only";
}

function confidenceClasses(
  confidence: ImportCorrectionDeviation["confidence"],
): string {
  if (confidence === "high") {
    return "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300";
  }
  if (confidence === "low") {
    return "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300";
  }
  return "border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-300";
}

function BriefFallback({
  brief,
  summary,
}: {
  brief?: AgentOutputBrief;
  summary?: string;
}): JSX.Element {
  if (brief) {
    return (
      <div className="grid gap-3 lg:grid-cols-3">
        <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
          <p className="app-label">What the agent found</p>
          <p className="mt-2 text-sm font-semibold leading-6 text-[var(--color-text-primary)]">
            {brief.finding || brief.headline}
          </p>
        </article>
        <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
          <p className="app-label">Why it matters</p>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            {brief.why}
          </p>
        </article>
        <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
          <p className="app-label">What to do next</p>
          <ul className="mt-2 space-y-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            {brief.next_actions.map((action) => (
              <li key={action} className="flex gap-2">
                <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-[var(--color-accent)]" />
                <span>{action}</span>
              </li>
            ))}
          </ul>
        </article>
      </div>
    );
  }
  const safeSummary =
    summary && !summary.trimStart().startsWith("{")
      ? summary
      : "The agent response could not be normalized into the governed review format. Re-run the analysis or inspect the deterministic review decisions below.";
  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-amber-900 dark:border-amber-900 dark:bg-amber-950/35 dark:text-amber-100">
      <div className="flex items-center gap-2 font-semibold">
        <AlertTriangle className="h-4 w-4" />
        Review brief needs normalization
      </div>
      <p className="mt-2 text-sm leading-6">{safeSummary}</p>
    </div>
  );
}

export function ImportCorrectionBrief({
  summary,
  brief,
  quality,
  providerStatus,
  compact = false,
}: {
  summary?: string;
  brief?: AgentOutputBrief;
  quality?: AgentOutputQuality;
  providerStatus?: string;
  compact?: boolean;
}): JSX.Element {
  const parsed = parseImportCorrectionBrief(summary);
  return (
    <div className={compact ? "mt-3" : "mt-4"}>
      <div className="mb-4 flex flex-wrap gap-2">
        {quality ? (
          <>
            <span className="app-theme-chip">
              Evidence {quality.evidence_completeness_pct}%
            </span>
            <span className="app-theme-chip">
              {quality.fallback_used ? "Deterministic fallback" : "Grounded synthesis"}
            </span>
          </>
        ) : null}
        {providerStatus ? (
          <span className="app-theme-chip">Provider {providerStatus}</span>
        ) : null}
      </div>

      {parsed ? (
        <div className="space-y-4">
          <article className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-[var(--color-accent)]" />
              <p className="app-label">Review at a glance</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
              {parsed.explanation}
            </p>
          </article>

          {parsed.deviations.length > 0 ? (
            <section>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <FileWarning className="h-4 w-4 text-[var(--color-accent)]" />
                  <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
                    Issues found
                  </h3>
                </div>
                <span className="app-theme-chip">
                  {parsed.deviations.length} issue
                  {parsed.deviations.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                {parsed.deviations.map((deviation, index) => (
                  <article
                    key={`${deviation.issue}-${index}`}
                    className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                          {deviation.issue}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] font-semibold text-[var(--color-text-muted)]">
                          <span>{fieldLabel(deviation.source_field)}</span>
                          <ArrowRight className="h-3.5 w-3.5" />
                          <span>{fieldLabel(deviation.target_field)}</span>
                        </div>
                      </div>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${confidenceClasses(
                          deviation.confidence,
                        )}`}
                      >
                        {deviation.confidence}
                      </span>
                    </div>
                    <div className="mt-3 rounded-lg bg-[var(--color-surface-2)] p-3">
                      <p className="app-label">Evidence</p>
                      <p className="mt-1.5 text-xs leading-5 text-[var(--color-text-secondary)]">
                        {deviation.evidence}
                      </p>
                    </div>
                    <p className="mt-3 text-xs font-medium leading-5 text-[var(--color-text-primary)]">
                      Next: {deviation.proposed_action}
                    </p>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          <div className="grid gap-3 lg:grid-cols-2">
            {parsed.required_decisions.length > 0 ? (
              <section className="rounded-xl border border-amber-300 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
                <div className="flex items-center gap-2 text-amber-800 dark:text-amber-200">
                  <ClipboardList className="h-4 w-4" />
                  <h3 className="text-sm font-semibold">Human decisions required</h3>
                </div>
                <ol className="mt-3 space-y-2 text-sm leading-6 text-amber-900 dark:text-amber-100">
                  {parsed.required_decisions.map((decision, index) => (
                    <li key={decision} className="flex gap-2">
                      <span className="font-semibold">{index + 1}.</span>
                      <span>{decision}</span>
                    </li>
                  ))}
                </ol>
              </section>
            ) : (
              <section className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-100">
                <div className="flex items-center gap-2 font-semibold">
                  <CheckCircle2 className="h-4 w-4" />
                  No additional human decision was requested.
                </div>
              </section>
            )}

            {parsed.excluded_fields.length > 0 ? (
              <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                <p className="app-label">Excluded by governance</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {parsed.excluded_fields.map((field) => (
                    <span key={field} className="app-theme-chip">
                      {field}
                    </span>
                  ))}
                </div>
              </section>
            ) : null}
          </div>
        </div>
      ) : (
        <BriefFallback brief={brief} summary={summary} />
      )}
    </div>
  );
}
