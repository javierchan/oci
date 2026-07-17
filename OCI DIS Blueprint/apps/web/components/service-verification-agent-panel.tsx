"use client";

/* Interactive controls for governed service evidence verification. */

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Play, ShieldAlert } from "lucide-react";

import { api, getErrorMessage } from "@/lib/api";
import { AgentDecisionWorkspace } from "@/components/agent-decision-workspace";
import { formatDate } from "@/lib/format";
import type { AgentRun, ServiceVerificationFinding, ServiceVerificationJob } from "@/lib/types";

function labelize(value: string): string {
  return value.replace(/_/g, " ");
}

function findingTone(severity: string): string {
  if (severity === "high" || severity === "critical") {
    return "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-100";
  }
  if (severity === "medium") {
    return "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100";
  }
  return "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100";
}

function isTerminalJob(status: string): boolean {
  return status === "completed" || status === "failed";
}

function hasApplicableUpdate(finding: ServiceVerificationFinding): boolean {
  return (
    typeof finding.new_value === "object" &&
    finding.new_value !== null &&
    (finding.new_value as { target?: unknown }).target === "service_limit"
  );
}

async function waitForAgent(run: AgentRun): Promise<AgentRun> {
  let current = run;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (["completed", "failed", "cancelled"].includes(current.status)) return current;
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    current = await api.getAgentRun(current.id);
  }
  throw new Error("Official Source Governance Agent did not finish within two minutes.");
}

function isVerificationJob(value: unknown): value is ServiceVerificationJob {
  return typeof value === "object" && value !== null && typeof (value as ServiceVerificationJob).id === "string" && Array.isArray((value as ServiceVerificationJob).findings);
}

export function ServiceVerificationAgentPanel({
  initialJob,
  scopeServiceId,
}: {
  initialJob: ServiceVerificationJob | null;
  scopeServiceId?: string;
}): JSX.Element {
  const [job, setJob] = useState<ServiceVerificationJob | null>(initialJob);
  const [findings, setFindings] = useState<ServiceVerificationFinding[]>([]);
  const [maxSources, setMaxSources] = useState(scopeServiceId ? 4 : 8);
  const [force, setForce] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isLoadingFindings, setIsLoadingFindings] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null);

  const scopeLabel = useMemo(() => (scopeServiceId ? scopeServiceId : "All products"), [scopeServiceId]);

  useEffect(() => {
    let isActive = true;
    async function loadFindings(): Promise<void> {
      if (!job) {
        setFindings([]);
        return;
      }
      setIsLoadingFindings(true);
      try {
        const rows = await api.listServiceVerificationFindings(job.id);
        if (isActive) {
          setFindings(rows);
        }
      } catch {
        if (isActive) {
          setFindings([]);
        }
      } finally {
        if (isActive) {
          setIsLoadingFindings(false);
        }
      }
    }
    void loadFindings();
    return () => {
      isActive = false;
    };
  }, [job]);

  useEffect(() => {
    if (!job || isTerminalJob(job.status)) {
      setIsRunning(false);
      return;
    }
    setIsRunning(true);
    let isActive = true;
    const timer = window.setTimeout(() => {
      api
        .getServiceVerificationJob(job.id)
        .then((refreshed) => {
          if (isActive) {
            setJob(refreshed);
            setIsRunning(!isTerminalJob(refreshed.status));
          }
        })
        .catch((error) => {
          if (isActive) {
            setErrorMessage(getErrorMessage(error, "Unable to refresh service verification job."));
            setIsRunning(false);
          }
        });
    }, 2500);
    return () => {
      isActive = false;
      window.clearTimeout(timer);
    };
  }, [job]);

  async function runVerification(): Promise<void> {
    setIsRunning(true);
    setErrorMessage(null);
    try {
      const terminal = await waitForAgent(await api.runAgent({
        agent_type: "service_verification",
        context: { request: { service_ids: scopeServiceId ? [scopeServiceId] : [], max_sources: maxSources, force } },
        message: "Compare official Oracle evidence with governed Service Product rules and prepare reviewable decisions.",
      }));
      if (terminal.status !== "completed" || !isVerificationJob(terminal.result?.evidence)) {
        throw new Error("Official Source Governance Agent returned an invalid result.");
      }
      setAgentRun(terminal);
      setJob(terminal.result.evidence);
      setIsRunning(false);
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "Unable to run service verification."));
      setIsRunning(false);
    }
  }

  async function reviewFinding(
    finding: ServiceVerificationFinding,
    reviewStatus: "accepted" | "dismissed" | "reviewed",
  ): Promise<void> {
    setErrorMessage(null);
    try {
      const reviewed = await api.reviewServiceVerificationFinding(job?.id ?? finding.job_id, finding.id, {
        review_status: reviewStatus,
      });
      setFindings((current) => current.map((item) => (item.id === reviewed.id ? reviewed : item)));
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "Unable to review verification finding."));
    }
  }

  return (
    <section className="app-card p-5">
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-1 h-5 w-5 text-[var(--color-accent)]" />
        <div>
          <p className="app-label">Verification Agent</p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Evidence queue</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            Official sources are checked against the governed evidence registry. Findings require review before rules change.
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3">
        <div className="grid gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
          <div className="flex items-center justify-between gap-4">
            <span className="text-xs uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Scope</span>
            <span className="font-mono text-sm font-semibold text-[var(--color-text-primary)]">{scopeLabel}</span>
          </div>
          <label className="grid gap-1 text-sm text-[var(--color-text-secondary)]">
            <span className="text-xs uppercase tracking-[0.14em] text-[var(--color-text-muted)]">Max sources</span>
            <input
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-[var(--color-text-primary)]"
              min={1}
              max={50}
              type="number"
              value={maxSources}
              onChange={(event) => setMaxSources(Math.max(1, Math.min(50, Number(event.target.value) || 1)))}
            />
          </label>
          <label className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
            <input
              checked={force}
              className="h-4 w-4 accent-[var(--color-accent)]"
              type="checkbox"
              onChange={(event) => setForce(event.target.checked)}
            />
            Force re-check
          </label>
          <button
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-[var(--color-accent)] bg-[var(--color-accent)] px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            disabled={isRunning}
            type="button"
            onClick={() => void runVerification()}
          >
            <Play className="h-4 w-4" />
            {isRunning ? "Checking sources" : "Review official-source changes"}
          </button>
        </div>

        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
          <p className="app-label">Latest job</p>
          {job ? (
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <span className="text-[var(--color-text-muted)]">Status</span>
                <span className="inline-flex items-center gap-1 font-semibold text-[var(--color-text-primary)]">
                  {!isTerminalJob(job.status) ? <Clock3 className="h-3.5 w-3.5" /> : null}
                  {labelize(job.status)}
                </span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-[var(--color-text-muted)]">Sources</span>
                <span className="font-semibold text-[var(--color-text-primary)]">{job.sources_checked}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-[var(--color-text-muted)]">Changes</span>
                <span className="font-semibold text-[var(--color-text-primary)]">{job.changes_detected}</span>
              </div>
              <p className="text-xs text-[var(--color-text-muted)]">{formatDate(job.updated_at)}</p>
            </div>
          ) : (
            <p className="mt-2 text-sm text-[var(--color-text-secondary)]">No verification jobs yet</p>
          )}
        </div>

        {errorMessage ? (
          <div className="rounded-2xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-100">
            {errorMessage}
          </div>
        ) : null}

        {agentRun ? <AgentDecisionWorkspace run={agentRun} onRunChange={setAgentRun} compact /> : null}

        {job ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <p className="app-label">Findings</p>
              <span className="text-xs text-[var(--color-text-muted)]">
                {isLoadingFindings ? "Loading" : `${findings.length} open/reviewed`}
              </span>
            </div>
            {findings.length === 0 ? (
              <div className="flex items-start gap-2 rounded-2xl border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100">
                <CheckCircle2 className="mt-0.5 h-4 w-4" />
                No findings for this job.
              </div>
            ) : (
              findings.slice(0, 3).map((finding) => (
                <article key={finding.id} className={`rounded-2xl border p-4 text-sm ${findingTone(finding.severity)}`}>
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                      <p className="font-semibold">{finding.title}</p>
                      <p className="mt-3 text-[11px] font-semibold uppercase tracking-[0.14em] opacity-65">What changed</p>
                      <p className="mt-1 leading-6">{finding.summary}</p>
                      {finding.recommended_action ? (
                        <div className="mt-3 rounded-xl border border-current/15 bg-white/45 p-3 dark:bg-black/15">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] opacity-65">What to review next</p>
                          <p className="mt-1 leading-6">{finding.recommended_action}</p>
                        </div>
                      ) : null}
                      {finding.source_url ? (
                        <a className="mt-2 inline-flex text-xs font-semibold underline" href={finding.source_url} target="_blank" rel="noreferrer">
                          Open source
                        </a>
                      ) : null}
                      <p className="mt-2 text-xs uppercase tracking-[0.14em]">{labelize(finding.review_status)}</p>
                      {finding.review_status === "open" ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {hasApplicableUpdate(finding) ? (
                            <button
                              className="rounded-lg border border-current px-3 py-1 text-xs font-semibold"
                              type="button"
                              onClick={() => void reviewFinding(finding, "accepted")}
                            >
                              Accept update
                            </button>
                          ) : null}
                          <button
                            className="rounded-lg border border-current px-3 py-1 text-xs font-semibold"
                            type="button"
                            onClick={() => void reviewFinding(finding, "reviewed")}
                          >
                            Mark reviewed
                          </button>
                          <button
                            className="rounded-lg border border-current px-3 py-1 text-xs font-semibold"
                            type="button"
                            onClick={() => void reviewFinding(finding, "dismissed")}
                          >
                            Dismiss
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </article>
              ))
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}
