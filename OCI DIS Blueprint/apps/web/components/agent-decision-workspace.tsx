"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowRight,
  Check,
  CheckCircle2,
  CircleAlert,
  CircleDashed,
  Loader2,
  Play,
  ShieldCheck,
  X,
} from "lucide-react";

import { emitToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import type { AgentApproval, AgentDecisionAlternative, AgentRun } from "@/lib/types";

function approvalFor(alternative: AgentDecisionAlternative, approvals: AgentApproval[]): AgentApproval | undefined {
  return approvals.find((approval) => approval.proposed_payload.alternative_id === alternative.id);
}

function statusMeta(status: AgentDecisionAlternative["status"]): { label: string; icon: typeof CheckCircle2; tone: string } {
  if (status === "ready") return { label: "Ready", icon: CheckCircle2, tone: "text-[var(--color-qa-ok-text)]" };
  if (status === "blocked") return { label: "Blocked", icon: CircleAlert, tone: "text-[var(--color-trend-down)]" };
  return { label: "Architect review", icon: CircleDashed, tone: "text-[var(--color-qa-revisar-text)]" };
}

function ImpactList({ label, values }: { label: string; values: string[] }): JSX.Element | null {
  if (!values.length) return null;
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">{label}</p>
      <ul className="mt-1.5 space-y-1 text-sm leading-5 text-[var(--color-text-secondary)]">
        {values.map((value) => <li key={value}>• {value}</li>)}
      </ul>
    </div>
  );
}

export function AgentDecisionWorkspace({
  run,
  onRunChange,
  compact = false,
}: {
  run: AgentRun;
  onRunChange: (_run: AgentRun) => void;
  compact?: boolean;
}): JSX.Element | null {
  const workspace = run.result?.decision_workspace;
  const [busy, setBusy] = useState<string | null>(null);
  if (!workspace || workspace.alternatives.length === 0) return null;

  async function decide(approval: AgentApproval, decision: "approved" | "rejected"): Promise<void> {
    setBusy(`${approval.id}:${decision}`);
    try {
      const updated = await api.decideAgentApproval(run.id, approval.id, decision);
      onRunChange(updated);
      emitToast("success", decision === "approved" ? "Proposal approved. It is ready for deterministic execution." : "Proposal rejected. No governed data changed.");
    } catch (error) {
      emitToast("error", error instanceof Error ? error.message : "Unable to record the decision.");
    } finally {
      setBusy(null);
    }
  }

  async function execute(approval: AgentApproval): Promise<void> {
    setBusy(`${approval.id}:execute`);
    try {
      const updated = await api.executeAgentApproval(run.id, approval.id);
      onRunChange(updated);
      emitToast("success", "Approved proposal executed and post-validation recorded.");
    } catch (error) {
      emitToast("error", error instanceof Error ? error.message : "Unable to execute the approved proposal.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section aria-label="Agent decision workspace" className="border-t border-[var(--color-border)] pt-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-4xl">
          <p className="app-label">Decision workspace</p>
          <h3 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">{workspace.goal}</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{workspace.current_state}</p>
          {!compact ? <p className="mt-2 text-xs leading-5 text-[var(--color-text-muted)]">{workspace.recommendation_basis}</p> : null}
        </div>
        <span className="app-theme-chip">{workspace.alternatives.length} alternatives</span>
      </div>

      <div className="mt-4 divide-y divide-[var(--color-border)] overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
        {workspace.alternatives.map((alternative) => {
          const meta = statusMeta(alternative.status);
          const StatusIcon = meta.icon;
          const approval = approvalFor(alternative, run.approvals);
          const approved = approval?.status === "approved";
          const executed = approval?.execution_status === "completed";
          const impactValues = [
            ...alternative.impact.technical,
            ...alternative.impact.commercial,
            ...alternative.impact.operational,
          ];
          return (
            <article key={alternative.id} className={`p-4 ${alternative.recommended ? "bg-[var(--color-accent-soft)]" : ""}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 max-w-4xl">
                  <div className="flex flex-wrap items-center gap-2">
                    {alternative.recommended ? <span className="app-theme-chip">Recommended</span> : null}
                    <span className={`inline-flex items-center gap-1.5 text-xs font-semibold ${meta.tone}`}><StatusIcon className="h-4 w-4" />{meta.label}</span>
                    <span className="text-xs text-[var(--color-text-muted)]">Confidence {alternative.confidence}</span>
                    {alternative.missing_inputs.length ? (
                      <span className="app-theme-chip">{alternative.missing_inputs.length} inputs needed</span>
                    ) : null}
                  </div>
                  <h4 className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">{alternative.title}</h4>
                  <p className="mt-1 text-sm leading-6 text-[var(--color-text-secondary)]">{alternative.summary}</p>
                </div>
                {alternative.action_href && !approval ? (
                  <Link href={alternative.action_href} className="app-button-secondary gap-2">Open workspace <ArrowRight className="h-4 w-4" /></Link>
                ) : null}
              </div>

              {!compact ? (
                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                  <ImpactList label="What changes" values={alternative.changes} />
                  <ImpactList label="Expected impact" values={impactValues} />
                </div>
              ) : null}

              {!compact && (alternative.implementation_steps.length || alternative.validation_steps.length || alternative.missing_inputs.length) ? (
                <details className="mt-4 rounded-lg border border-[var(--color-border)] px-3 py-2.5">
                  <summary className="cursor-pointer text-sm font-semibold text-[var(--color-text-primary)]">
                    Implementation, inputs, and validation
                  </summary>
                  <div className="mt-3 grid gap-4 lg:grid-cols-3">
                    <div><p className="app-label">Implementation</p><ol className="mt-2 space-y-1 text-sm leading-5 text-[var(--color-text-secondary)]">{alternative.implementation_steps.map((step, index) => <li key={step}>{index + 1}. {step}</li>)}</ol></div>
                    <ImpactList label="Inputs needed" values={alternative.missing_inputs} />
                    <ImpactList label="Validation" values={alternative.validation_steps} />
                  </div>
                </details>
              ) : null}

              {approval ? (
                <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-[var(--color-border)] pt-3">
                  {approval.status === "pending" ? (
                    <>
                      <button className="app-button-primary gap-2" type="button" disabled={busy !== null} onClick={() => void decide(approval, "approved")}>{busy === `${approval.id}:approved` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}{alternative.action_label ?? "Approve proposal"}</button>
                      <button className="app-button-secondary gap-2" type="button" disabled={busy !== null} onClick={() => void decide(approval, "rejected")}><X className="h-4 w-4" />Reject</button>
                      <span className="text-xs text-[var(--color-text-muted)]">Approval never executes a change by itself.</span>
                    </>
                  ) : approved && !executed ? (
                    <button className="app-button-primary gap-2" type="button" disabled={busy !== null || approval.execution_status === "running"} onClick={() => void execute(approval)}>{busy === `${approval.id}:execute` ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}{approval.action_type === "simulate_integration_design_candidate" ? "Simulate approved draft" : "Execute approved action"}</button>
                  ) : executed ? (
                    <span className="inline-flex items-center gap-2 text-sm font-semibold text-[var(--color-qa-ok-text)]"><ShieldCheck className="h-4 w-4" />Executed and post-validated</span>
                  ) : (
                    <span className="text-sm text-[var(--color-text-muted)]">Proposal rejected. No governed data changed.</span>
                  )}
                  {executed && approval.execution_result?.action_href ? (
                    <Link href={String(approval.execution_result.action_href)} className="app-button-secondary gap-2">Inspect outcome <ArrowRight className="h-4 w-4" /></Link>
                  ) : null}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      {!compact && workspace.post_validation.length ? (
        <div className="mt-4 flex items-start gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-[var(--color-accent)]" />
          <div><p className="text-sm font-semibold text-[var(--color-text-primary)]">Completion contract</p><p className="mt-1 text-sm leading-6 text-[var(--color-text-secondary)]">{workspace.post_validation.join(" ")}</p></div>
        </div>
      ) : null}
    </section>
  );
}
