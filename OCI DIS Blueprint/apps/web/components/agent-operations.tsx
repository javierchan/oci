"use client";

/* Operational view of governed OCI Generative AI definitions and Docker runs. */

import { useEffect, useState } from "react";
import { Bot, CheckCircle2, Clock3, Loader2, RefreshCcw, Square, TriangleAlert } from "lucide-react";

import { emitToast } from "@/hooks/use-toast";
import { agentExecutionIndicatorTone, type AgentExecutionIndicatorTone } from "@/lib/agent-status";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { AgentDefinition, AgentProviderMetrics, AgentProviderStatus, AgentRun } from "@/lib/types";

function isActive(status: AgentRun["status"]): boolean {
  return status === "pending" || status === "running" || status === "waiting_approval";
}

function indicatorColor(tone: AgentExecutionIndicatorTone): string {
  if (tone === "success") return "text-[var(--color-qa-ok-text)]";
  if (tone === "error") return "text-[var(--color-trend-down)]";
  return "text-[var(--color-qa-revisar-text)]";
}

function statusIcon(run: AgentRun): JSX.Element {
  const tone = agentExecutionIndicatorTone(run);
  const color = indicatorColor(tone);
  if (run.status === "completed") return <CheckCircle2 data-execution-tone={tone} className={`h-4 w-4 ${color}`} />;
  if (isActive(run.status)) return <Loader2 data-execution-tone={tone} className={`h-4 w-4 animate-spin ${color}`} />;
  return <Clock3 data-execution-tone={tone} className={`h-4 w-4 ${color}`} />;
}

export function AgentOperations({
  definitions,
  providerStatus,
  initialMetrics,
  initialRuns,
}: {
  definitions: AgentDefinition[];
  providerStatus: AgentProviderStatus;
  initialMetrics: AgentProviderMetrics;
  initialRuns: AgentRun[];
}): JSX.Element {
  const [runs, setRuns] = useState<AgentRun[]>(initialRuns);
  const [metrics, setMetrics] = useState<AgentProviderMetrics>(initialMetrics);
  const [refreshing, setRefreshing] = useState(false);

  async function refresh(silent = false): Promise<void> {
    if (!silent) setRefreshing(true);
    try {
      const [runResult, metricResult] = await Promise.all([
        api.listAgentRuns({ limit: 50 }),
        api.getAgentProviderMetrics(),
      ]);
      setRuns(runResult.runs);
      setMetrics(metricResult);
    } catch (error) {
      if (!silent) emitToast("error", error instanceof Error ? error.message : "Unable to refresh agent runs.");
    } finally {
      if (!silent) setRefreshing(false);
    }
  }

  useEffect(() => {
    if (!runs.some((run) => isActive(run.status))) return;
    const timer = window.setInterval(() => void refresh(true), 1200);
    return () => window.clearInterval(timer);
  }, [runs]);

  async function cancel(run: AgentRun): Promise<void> {
    try {
      const updated = await api.cancelAgentRun(run.id);
      setRuns((current) => current.map((item) => item.id === updated.id ? updated : item));
      emitToast("success", "Agent cancellation requested.");
    } catch (error) {
      emitToast("error", error instanceof Error ? error.message : "Unable to cancel agent run.");
    }
  }

  return (
    <div className="space-y-5">
      <section className={`app-card flex flex-col gap-3 p-5 md:flex-row md:items-center md:justify-between ${providerStatus.function_calling_available ? "border-emerald-500/40" : "border-amber-500/45"}`}>
        <div className="flex items-start gap-3">
          {providerStatus.function_calling_available ? <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-500" /> : <TriangleAlert className="mt-0.5 h-5 w-5 text-amber-500" />}
          <div>
            <p className="app-label">Provider status</p>
            <p className="mt-2 text-sm font-semibold text-[var(--color-text-primary)]">{providerStatus.status_message}</p>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">
              {providerStatus.model} · {providerStatus.region} · Responses-first · Docker agents queue
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="app-theme-chip">Responses {providerStatus.responses_capability}</span>
              <span className="app-theme-chip">
                Guardrails {providerStatus.guardrails_enabled ? `v${providerStatus.guardrails_version}` : "off"}
              </span>
              <span className="app-theme-chip">{providerStatus.max_retries} retries</span>
            </div>
          </div>
        </div>
        <span className="app-theme-chip">{providerStatus.function_calling_available ? "Function calling ready" : "Deterministic fallback"}</span>
      </section>
      <section aria-label="OCI provider telemetry" className="app-table-shell p-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="app-label">Provider telemetry</p>
            <h2 className="mt-1 text-xl font-semibold text-[var(--color-text-primary)]">Resilience and safety signals</h2>
          </div>
          <span className="app-theme-chip">{metrics.source === "redis" ? "Shared runtime" : "Process fallback"}</span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {[
            ["Retries", metrics.counters.retries_total],
            ["Guardrail blocks", metrics.counters.guardrail_blocks_total],
            ["HTTP 429", metrics.counters.http_429_total],
            ["HTTP 5xx", metrics.counters.http_5xx_total],
            ["Responses fallbacks", metrics.counters.responses_fallbacks_total],
            ["Degradations", metrics.counters.provider_degradations_total],
          ].map(([label, value]) => (
            <article key={label} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
              <p className="text-xs font-semibold text-[var(--color-text-muted)]">{label}</p>
              <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{value}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {definitions.map((definition) => (
          <article key={definition.type} className="app-card p-5">
            <div className="flex items-start justify-between gap-3">
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--color-surface-2)] text-[var(--color-accent)]">
                <Bot className="h-5 w-5" />
              </span>
              <span className="app-theme-chip">v{definition.version}</span>
            </div>
            <h2 className="mt-4 text-lg font-semibold text-[var(--color-text-primary)]">{definition.name}</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{definition.description}</p>
            <p className="mt-4 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--color-text-muted)]">{definition.location}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {definition.tools.map((tool) => <span key={tool} className="app-theme-chip font-mono text-[10px]">{tool}</span>)}
            </div>
          </article>
        ))}
      </section>

      <section className="app-table-shell">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] px-5 py-4">
          <div>
            <p className="app-label">Docker Agent Runtime</p>
            <h2 className="mt-1 text-xl font-semibold text-[var(--color-text-primary)]">Execution history</h2>
          </div>
          <button type="button" className="app-button-secondary gap-2" disabled={refreshing} onClick={() => void refresh()}>
            <RefreshCcw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
        {runs.length === 0 ? (
          <div className="px-5 py-12 text-center text-sm text-[var(--color-text-secondary)]">No agent runs yet. Contextual actions in Dashboard, Map, Import, Canvas, Service Products, and BOM create runs here.</div>
        ) : (
          <div className="divide-y divide-[var(--color-border)]">
            {runs.map((run) => (
              <article key={run.id} className="grid gap-3 px-5 py-4 lg:grid-cols-[minmax(15rem,1fr)_10rem_12rem_auto] lg:items-center">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-semibold text-[var(--color-text-primary)]">{statusIcon(run)} {run.agent_type.replaceAll("_", " ")}</p>
                  <p className="mt-1 truncate text-sm text-[var(--color-text-secondary)]">{run.result?.summary ?? "Waiting for governed evidence."}</p>
                </div>
                <div><p className="app-label">Status</p><p className="mt-1 text-sm font-semibold capitalize text-[var(--color-text-primary)]">{run.status.replaceAll("_", " ")}</p></div>
                <div><p className="app-label">Created</p><p className="mt-1 text-sm text-[var(--color-text-secondary)]">{formatDate(run.created_at)}</p></div>
                {isActive(run.status) ? <button type="button" className="app-button-secondary gap-2" onClick={() => void cancel(run)}><Square className="h-3.5 w-3.5" /> Cancel</button> : <span className="app-theme-chip">{run.result?.provider_status ?? "deterministic"}</span>}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
