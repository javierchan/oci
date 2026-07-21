"use client";

/* Project workspace for deployment scenarios and governed OCI Bills of Materials. */

import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Download,
  FileCheck2,
  Loader2,
  Play,
  RefreshCcw,
  Send,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { emitToast } from "@/hooks/use-toast";
import { AppDatePicker } from "@/components/app-date-picker";
import { BomConsumptionEditor } from "@/components/bom-consumption-editor";
import { BomRolloutExplorer } from "@/components/bom-rollout-explorer";
import { ActionRecommendationWorkspace } from "@/components/action-recommendation-workspace";
import { AgentDecisionWorkspace } from "@/components/agent-decision-workspace";
import { GovernedNarrative } from "@/components/governed-narrative";
import { api, apiDownloadBlob, getErrorMessage } from "@/lib/api";
import {
  activeComparisonCategories,
  buildComparisonPeriodData,
  explicitPlanReadiness,
  resizeConsumptionPlan,
} from "@/lib/bom-ramp";
import { formatDate } from "@/lib/format";
import { isBomJobTerminal } from "@/lib/types";
import type {
  AgentRun,
  BomJob,
  BomComparison,
  BomSnapshot,
  DeploymentScenario,
  DeploymentScenarioCreate,
  ScenarioAssistant,
} from "@/lib/types";

function statusTone(status: string): string {
  if (["approved", "published", "completed"].includes(status)) {
    return "border-emerald-400/45 text-emerald-700 dark:text-emerald-300";
  }
  if (["failed", "blocked"].includes(status)) {
    return "border-rose-400/45 text-rose-700 dark:text-rose-300";
  }
  return "border-amber-400/45 text-amber-700 dark:text-amber-300";
}

function readinessTone(status: string): string {
  if (status === "quote_ready") return "border-emerald-400/45 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300";
  if (status === "input_required") return "border-amber-400/45 bg-amber-500/5 text-amber-700 dark:text-amber-300";
  return "border-rose-400/45 bg-rose-500/5 text-rose-700 dark:text-rose-300";
}

function currency(value: number, code: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: code,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatNumber(value: number): string {
  const magnitude = Math.abs(value);
  const maximumFractionDigits = magnitude > 0 && magnitude < 1 ? 6 : magnitude < 10 ? 3 : 0;
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits,
    minimumFractionDigits: 0,
  }).format(value);
}

function warningText(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "object" && value !== null) {
    const row = value as { detail?: unknown; message?: unknown; title?: unknown };
    return String(row.detail ?? row.message ?? row.title ?? JSON.stringify(value));
  }
  return String(value);
}

function isScenarioAssistant(value: unknown): value is ScenarioAssistant {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<ScenarioAssistant>;
  return typeof candidate.confidence === "string" && Array.isArray(candidate.detected_services) && Array.isArray(candidate.required_questions) && typeof candidate.draft === "object";
}

async function waitForAgent(run: AgentRun): Promise<AgentRun> {
  let current = run;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (["completed", "failed", "cancelled"].includes(current.status)) return current;
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    current = await api.getAgentRun(current.id);
  }
  throw new Error("BOM scenario agent did not reach a terminal state within two minutes.");
}

export function BomWorkspace({ projectId, projectName }: { projectId: string; projectName: string }): JSX.Element {
  const [assistant, setAssistant] = useState<ScenarioAssistant | null>(null);
  const [draft, setDraft] = useState<DeploymentScenarioCreate | null>(null);
  const [scenarios, setScenarios] = useState<DeploymentScenario[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>("");
  const [jobs, setJobs] = useState<BomJob[]>([]);
  const [snapshots, setSnapshots] = useState<BomSnapshot[]>([]);
  const [selectedSnapshot, setSelectedSnapshot] = useState<BomSnapshot | null>(null);
  const [baselineSnapshotId, setBaselineSnapshotId] = useState<string>("");
  const [comparisonSnapshotId, setComparisonSnapshotId] = useState<string>("");
  const [comparison, setComparison] = useState<BomComparison | null>(null);
  const [reviewNote, setReviewNote] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string>("");
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null);

  const load = useCallback(async (silent = false): Promise<void> => {
    if (!silent) {
      setLoading(true);
    }
    try {
      const [assistantResult, scenarioResult, jobResult, snapshotResult] = await Promise.all([
        api.getDeploymentScenarioAssistant(projectId).catch(() => null),
        api.listDeploymentScenarios(projectId),
        api.listBomJobs(projectId, 12),
        api.listBomSnapshots(projectId, 12),
      ]);
      setAssistant(assistantResult);
      setDraft((current) => current ?? assistantResult?.draft ?? null);
      setScenarios(scenarioResult.scenarios);
      setJobs(jobResult.jobs);
      setSnapshots(snapshotResult.snapshots);
      setComparisonSnapshotId((current) => current || snapshotResult.snapshots[0]?.id || "");
      setBaselineSnapshotId((current) => current || snapshotResult.snapshots[1]?.id || "");
      setSelectedScenarioId((current) => current || scenarioResult.scenarios.find((row) => row.status === "approved")?.id || scenarioResult.scenarios[0]?.id || "");
      const latest = snapshotResult.snapshots[0] ?? null;
      if (latest) {
        const fullSnapshot = latest.line_items.length > 0 ? latest : await api.getBomSnapshot(projectId, latest.id);
        setSelectedSnapshot((current) => current?.id === fullSnapshot.id ? current : fullSnapshot);
      }
      setError("");
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to load the BOM workspace."));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  const hasActiveJob = useMemo(() => jobs.some((job) => !isBomJobTerminal(job.status)), [jobs]);
  useEffect(() => {
    if (!hasActiveJob) {
      return undefined;
    }
    const timer = window.setInterval(() => void load(true), 3000);
    return () => window.clearInterval(timer);
  }, [hasActiveJob, load]);

  const selectedScenario = scenarios.find((scenario) => scenario.id === selectedScenarioId) ?? null;
  const snapshotScenario = selectedSnapshot ? scenarios.find((scenario) => scenario.id === selectedSnapshot.scenario_id) ?? null : null;
  const planReadiness = useMemo(
    () => explicitPlanReadiness(draft?.environments ?? []),
    [draft?.environments],
  );
  const comparisonPeriods = useMemo(
    () => comparison ? buildComparisonPeriodData(comparison) : [],
    [comparison],
  );
  const comparisonCategories = useMemo(
    () => comparison ? activeComparisonCategories(comparison) : [],
    [comparison],
  );

  function patchDraft(patch: Partial<DeploymentScenarioCreate>): void {
    setDraft((current) => current ? { ...current, ...patch } : current);
  }

  async function refreshAssistant(includeLlm: boolean): Promise<void> {
    setBusyAction("assistant");
    try {
      if (includeLlm) {
        const terminal = await waitForAgent(await api.runBomScenarioAgent(projectId));
        if (terminal.status !== "completed") {
          throw new Error("BOM scenario agent did not complete successfully.");
        }
        const evidence = terminal.result?.evidence;
        if (!isScenarioAssistant(evidence)) {
          throw new Error("BOM scenario agent returned an invalid evidence contract.");
        }
        const result: ScenarioAssistant = {
          ...evidence,
          ai_status: terminal.result?.provider_status ?? "skipped",
          ai_summary: terminal.result?.summary ?? null,
        };
        setAssistant(result);
        setDraft(result.draft);
        setAgentRun(terminal);
        emitToast("success", "Governed BOM scenario agent completed.");
        return;
      }
      const result = await api.getDeploymentScenarioAssistant(projectId, false);
      setAssistant(result);
      setDraft(result.draft);
      emitToast("success", "Scenario evidence refreshed.");
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to refresh scenario evidence."));
    } finally {
      setBusyAction(null);
    }
  }

  async function createScenario(): Promise<void> {
    if (!draft) {
      return;
    }
    setBusyAction("create-scenario");
    try {
      const created = await api.createDeploymentScenario(projectId, draft);
      setSelectedScenarioId(created.id);
      emitToast("success", "Deployment scenario created as a governed draft.");
      await load(true);
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to create the deployment scenario."));
    } finally {
      setBusyAction(null);
    }
  }

  async function approveScenario(): Promise<void> {
    if (!selectedScenario) {
      return;
    }
    setBusyAction("approve-scenario");
    try {
      await api.approveDeploymentScenario(projectId, selectedScenario.id);
      emitToast("success", "Deployment scenario approved for pricing.");
      await load(true);
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to approve the deployment scenario."));
    } finally {
      setBusyAction(null);
    }
  }

  async function generateBom(): Promise<void> {
    if (!selectedScenario || selectedScenario.status !== "approved") {
      return;
    }
    setBusyAction("generate");
    try {
      await api.createBomJob(projectId, selectedScenario.id);
      emitToast("info", "BOM generation queued.");
      await load(true);
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to generate the BOM."));
    } finally {
      setBusyAction(null);
    }
  }

  async function selectSnapshot(snapshot: BomSnapshot): Promise<void> {
    setBusyAction(snapshot.id);
    try {
      setSelectedSnapshot(snapshot.line_items.length > 0 ? snapshot : await api.getBomSnapshot(projectId, snapshot.id));
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to load the BOM snapshot."));
    } finally {
      setBusyAction(null);
    }
  }

  async function reviewSnapshot(status: "approved" | "published"): Promise<void> {
    if (!selectedSnapshot) {
      return;
    }
    setBusyAction(status);
    try {
      const updated = await api.reviewBomSnapshot(projectId, selectedSnapshot.id, status, reviewNote || undefined);
      setSelectedSnapshot(updated);
      emitToast("success", status === "published" ? "BOM published." : "BOM approved.");
      await load(true);
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, `Unable to mark the BOM as ${status}.`));
    } finally {
      setBusyAction(null);
    }
  }

  async function downloadBom(format: "xlsx" | "json" | "pdf"): Promise<void> {
    if (!selectedSnapshot) {
      return;
    }
    setBusyAction(`download-${format}`);
    try {
      const result = await apiDownloadBlob(
        `/api/v1/projects/${projectId}/bom-snapshots/${selectedSnapshot.id}/exports/${format}`,
      );
      const url = URL.createObjectURL(result.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = result.filename ?? `oci-bom-${selectedSnapshot.id}.${format}`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      emitToast("success", `BOM ${format.toUpperCase()} downloaded.`);
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, `Unable to download BOM ${format.toUpperCase()}.`));
    } finally {
      setBusyAction(null);
    }
  }

  async function compareSnapshots(): Promise<void> {
    if (!baselineSnapshotId || !comparisonSnapshotId || baselineSnapshotId === comparisonSnapshotId) {
      emitToast("error", "Choose two different BOM snapshots to compare.");
      return;
    }
    setBusyAction("compare");
    try {
      setComparison(await api.compareBomSnapshots(projectId, baselineSnapshotId, comparisonSnapshotId));
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to compare BOM snapshots."));
    } finally {
      setBusyAction(null);
    }
  }

  if (loading && !draft) {
    return <div className="app-card flex min-h-64 items-center justify-center gap-3 p-8 text-[var(--color-text-secondary)]"><Loader2 className="h-5 w-5 animate-spin" />Loading governed pricing context</div>;
  }

  return (
    <div className="space-y-5">
      {error ? <div role="alert" className="rounded-lg border border-rose-400/45 bg-[var(--color-surface-2)] p-4 text-sm text-rose-700 dark:text-rose-300">{error}</div> : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(22rem,0.75fr)]">
        <div id="deployment-scenario-editor" className="app-card scroll-mt-6 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div><p className="app-label">Deployment Scenario</p><h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Convert logical demand into deployable capacity</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">Commercial estimates for {projectName} are isolated from the technical Dashboard and require an approved physical deployment scenario.</p></div>
            <button className="app-button-secondary gap-2" type="button" disabled={busyAction !== null} onClick={() => void refreshAssistant(true)}>{busyAction === "assistant" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}{busyAction === "assistant" ? "Comparing scenarios" : "Compare deployment alternatives"}</button>
          </div>

          {draft ? <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <label className="text-sm font-semibold text-[var(--color-text-primary)] xl:col-span-2">Scenario name<input className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5" value={draft.name} onChange={(event) => patchDraft({ name: event.target.value })} /></label>
            <label className="text-sm font-semibold text-[var(--color-text-primary)]">Region<input className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5" value={draft.region} onChange={(event) => patchDraft({ region: event.target.value })} /></label>
            <label className="text-sm font-semibold text-[var(--color-text-primary)]">Currency<input className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 font-mono" maxLength={3} value={draft.currency} onChange={(event) => patchDraft({ currency: event.target.value.toUpperCase() })} /></label>
            <label className="text-sm font-semibold text-[var(--color-text-primary)]">Price source<select className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5" value={draft.price_mode} onChange={(event) => patchDraft({ price_mode: event.target.value as DeploymentScenarioCreate["price_mode"] })}><option value="public_list">Public list</option><option value="contract_rate">Contract rate</option><option value="manual_rate_card">Manual rate card</option></select></label>
            <label className="text-sm font-semibold text-[var(--color-text-primary)]">Commercial model<select className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5" value={draft.commitment_model} onChange={(event) => patchDraft({ commitment_model: event.target.value as DeploymentScenarioCreate["commitment_model"] })}><option value="pay_as_you_go">Pay as you go</option><option value="annual_commitment">Annual commitment</option><option value="annual_flex">Annual Flex</option><option value="monthly_flex">Monthly Flex</option></select></label>
            <label className="text-sm font-semibold text-[var(--color-text-primary)]">Licensing<select className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5" value={draft.licensing_model} onChange={(event) => patchDraft({ licensing_model: event.target.value as DeploymentScenarioCreate["licensing_model"] })}><option value="license_included">License Included</option><option value="byol">Bring Your Own License (BYOL)</option></select></label>
            <label className="text-sm font-semibold text-[var(--color-text-primary)]">Contract months<input type="number" min={1} max={120} className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5" value={draft.contract_months} onChange={(event) => { const contractMonths = Math.min(Math.max(Number(event.target.value), 1), 120); patchDraft({ contract_months: contractMonths, environments: resizeConsumptionPlan(draft.environments, contractMonths) }); }} /></label>
            <AppDatePicker label="Contract start" value={draft.start_date} onChange={(startDate) => patchDraft({ start_date: startDate })} />
            <div className="md:col-span-2 xl:col-span-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div><p className="app-label">Commercial Coverage</p><h3 className="mt-1 text-lg font-semibold text-[var(--color-text-primary)]">Every detected product has an explicit quote path</h3></div>
                <span className="text-xs text-[var(--color-text-muted)]">{assistant?.commercial_coverage?.length ?? 0} products evaluated</span>
              </div>
              <div className="mt-4 grid gap-3 lg:grid-cols-2">
                {assistant?.commercial_coverage?.map((coverage) => (
                  <div key={coverage.service_id} className={`rounded-lg border p-4 ${readinessTone(coverage.readiness)}`}>
                    <div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-[var(--color-text-primary)]">{coverage.product_name}</p><p className="mt-1 text-xs uppercase tracking-[0.12em]">{coverage.classification.replaceAll("_", " ")}</p></div><span className="rounded-full border border-current/30 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em]">{coverage.readiness.replaceAll("_", " ")}</span></div>
                    <p className="mt-3 text-sm leading-5 text-[var(--color-text-secondary)]">{coverage.guidance}</p>
                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-[var(--color-text-muted)]">
                      <span>
                        {coverage.approved_mapping_count} governed {coverage.approved_mapping_count === 1 ? "meter" : "meters"}
                      </span>
                      {coverage.dependencies_present.length ? <span>Dependencies present: {coverage.dependencies_present.join(", ")}</span> : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="md:col-span-2 xl:col-span-4">
              <BomConsumptionEditor
                contractMonths={draft.contract_months}
                environments={draft.environments}
                metricOptions={assistant?.metric_options ?? []}
                onChange={(environments) => patchDraft({ environments, consumption_model: "explicit_units" })}
              />
            </div>
          </div> : null}

          <div className="mt-5 flex flex-wrap gap-2"><button className="app-button-primary gap-2" type="button" disabled={!draft || busyAction !== null || !planReadiness.ready} onClick={() => void createScenario()}>{busyAction === "create-scenario" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}Save new scenario</button><button className="app-button-secondary gap-2" type="button" disabled={!selectedScenario || selectedScenario.status === "approved" || busyAction !== null} onClick={() => void approveScenario()}>{busyAction === "approve-scenario" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}Approve selected</button></div>
        </div>

        <aside className="app-card p-5">
          <div className="flex items-start justify-between gap-3"><div><p className="app-label">BOM Decision Assistant</p><h2 className="mt-2 text-lg font-semibold text-[var(--color-text-primary)]">What this scenario means</h2></div><span className="rounded-full border border-[var(--color-border)] px-2.5 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">{assistant?.confidence ?? "unavailable"} confidence</span></div>
          {assistant?.current_bom ? <div className={`mt-4 rounded-lg border p-4 ${assistant.current_bom.ready_for_use ? "border-emerald-400/45 bg-emerald-500/5" : "border-amber-400/45 bg-amber-500/5"}`}>
            <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="app-label">Current governed BOM</p><h3 className="mt-1 font-semibold text-[var(--color-text-primary)]">{assistant.current_bom.scenario_name}</h3></div><span className="rounded-full border border-current/30 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em]">{assistant.current_bom.ready_for_use ? "Published and current" : "Review required"}</span></div>
            <p className="mt-3 text-sm leading-5 text-[var(--color-text-secondary)]">{assistant.current_bom.coverage_pct}% coverage across {assistant.current_bom.line_item_count} line items in {assistant.current_bom.environment_names.join(", ") || "the approved environment plan"}. Contract total: {assistant.current_bom.currency} {assistant.current_bom.contract_total.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}.</p>
          </div> : null}
          <div className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">{assistant?.ai_summary ? <GovernedNarrative content={assistant.ai_summary} compact /> : <p className="text-sm leading-6 text-[var(--color-text-secondary)]">Deterministic scenario evidence is ready. OCI Generative AI can explain it, but never changes governed quantities, prices, or totals.</p>}</div>
          <p className="app-label mt-5">Products represented</p><p className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">These OCI products were resolved from the governed architecture and scenario.</p><div className="mt-2 flex flex-wrap gap-2">{assistant?.detected_services.map((service) => <span key={service} className="rounded-full border border-[var(--color-border)] px-2.5 py-1 text-xs font-semibold text-[var(--color-text-secondary)]">{service}</span>)}</div>
          {assistant?.required_questions.length ? <><p className="app-label mt-5">What the client still needs to confirm</p><ol className="mt-2 space-y-2">{assistant.required_questions.map((question, index) => <li key={question} className="flex gap-2 text-sm leading-5 text-[var(--color-text-secondary)]"><span className="font-mono text-[var(--color-accent)]">{index + 1}.</span>{question}</li>)}</ol></> : <div className="mt-5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3"><p className="text-sm font-semibold text-[var(--color-text-primary)]">No blocking client inputs</p><p className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">The current published baseline is complete. Create an alternative only when a governed architecture or rollout input changes.</p></div>}
          {assistant?.warnings.length ? <div className="mt-4 rounded-lg border border-amber-400/45 p-3 text-sm text-amber-700 dark:text-amber-300"><p className="mb-2 font-semibold"><AlertTriangle className="mr-2 inline h-4 w-4" />Why the estimate needs review</p>{assistant.warnings.join(" ")}</div> : null}
        </aside>
      </section>

      {agentRun ? (
        <section className="app-card p-5">
          <AgentDecisionWorkspace
            run={agentRun}
            onRunChange={(updated) => {
              setAgentRun(updated);
              if (updated.approvals.some((approval) => approval.execution_status === "completed")) void load(true);
            }}
          />
        </section>
      ) : null}

      <section className="app-card p-5">
        <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="app-label">Approved Input</p><h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Generate an immutable BOM</h2></div><button className="app-button-primary gap-2" type="button" disabled={!selectedScenario || selectedScenario.status !== "approved" || busyAction !== null || hasActiveJob} onClick={() => void generateBom()}>{busyAction === "generate" || hasActiveJob ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}{hasActiveJob ? "Generation running" : "Generate BOM"}</button></div>
        <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end"><label className="text-sm font-semibold text-[var(--color-text-primary)]">Deployment scenario<select className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5" value={selectedScenarioId} onChange={(event) => setSelectedScenarioId(event.target.value)}>{scenarios.map((scenario) => <option key={scenario.id} value={scenario.id}>{scenario.name} · {scenario.status}</option>)}</select></label><button className="app-button-secondary gap-2" type="button" onClick={() => void load(true)}><RefreshCcw className="h-4 w-4" />Refresh</button></div>
        {selectedScenario ? <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-7"><div><p className="app-label">Status</p><p className="mt-1 font-semibold text-[var(--color-text-primary)]">{selectedScenario.status}</p></div><div><p className="app-label">Price source</p><p className="mt-1 text-sm text-[var(--color-text-secondary)]">{selectedScenario.price_mode.replace(/_/g, " ")}</p></div><div><p className="app-label">Commercial model</p><p className="mt-1 text-sm text-[var(--color-text-secondary)]">{selectedScenario.commitment_model.replace(/_/g, " ")}</p></div><div><p className="app-label">Licensing</p><p className="mt-1 text-sm text-[var(--color-text-secondary)]">{selectedScenario.licensing_model.replace(/_/g, " ")}</p></div><div><p className="app-label">Region</p><p className="mt-1 text-sm text-[var(--color-text-secondary)]">{selectedScenario.region}</p></div><div><p className="app-label">Currency</p><p className="mt-1 font-mono text-sm text-[var(--color-text-secondary)]">{selectedScenario.currency}</p></div><div><p className="app-label">Updated</p><p className="mt-1 text-sm text-[var(--color-text-secondary)]">{formatDate(selectedScenario.updated_at)}</p></div></div> : <p className="mt-4 text-sm text-[var(--color-text-secondary)]">Create and approve a scenario before generating a BOM.</p>}
      </section>

      {selectedSnapshot ? <>
        <ActionRecommendationWorkspace workspace={selectedSnapshot.recommendation_workspace} />
        <BomRolloutExplorer
          snapshot={selectedSnapshot}
          scenario={snapshotScenario}
          metricOptions={assistant?.metric_options ?? []}
          onEditScenario={() => document.getElementById("deployment-scenario-editor")?.scrollIntoView({ behavior: "smooth", block: "start" })}
        />

        <section className="app-card p-5">
          <div className="flex min-w-0 flex-wrap items-start justify-between gap-4"><div className="min-w-0"><div className="flex items-center gap-3"><p className="app-label">Governed BOM</p><span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusTone(selectedSnapshot.publication_status)}`}>{selectedSnapshot.publication_status}</span></div><h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Review, approve and publish</h2><p className="mt-2 [overflow-wrap:anywhere] text-sm text-[var(--color-text-secondary)]">Price snapshot <span className="font-mono">{selectedSnapshot.price_catalog_snapshot_id.slice(0, 8)}</span> · mapping <span className="font-mono">{selectedSnapshot.mapping_version}</span> · engine <span className="font-mono">{selectedSnapshot.engine_version}</span></p></div><div className="flex flex-wrap gap-2"><button type="button" className="app-button-secondary gap-2" disabled={busyAction !== null} onClick={() => void downloadBom("xlsx")}>{busyAction === "download-xlsx" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}XLSX</button><button type="button" className="app-button-secondary gap-2" disabled={busyAction !== null} onClick={() => void downloadBom("json")}>{busyAction === "download-json" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}JSON</button><button type="button" className="app-button-secondary gap-2" disabled={busyAction !== null} onClick={() => void downloadBom("pdf")}>{busyAction === "download-pdf" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}PDF</button></div></div>
          {selectedSnapshot.line_items.some((line) => line.status === "rate_card_required") ? <div className="mt-4 rounded-lg border border-amber-400/45 bg-amber-500/5 p-4"><p className="font-semibold text-amber-700 dark:text-amber-300">Customer rate card required</p><p className="mt-1 text-sm leading-6 text-[var(--color-text-secondary)]">Technical quantities are governed, but one or more external-rate SKUs have no exact part-number match in the selected approved rate card. These lines are intentionally unpriced and prevent approval.</p></div> : null}
          {selectedSnapshot.line_items.some((line) => line.status === "input_required") ? <div className="mt-4 rounded-lg border border-sky-400/45 bg-sky-500/5 p-4"><p className="font-semibold text-sky-700 dark:text-sky-300">Client evidence required</p><p className="mt-1 text-sm leading-6 text-[var(--color-text-secondary)]">One or more governed products have no authoritative public rate or require entitlement evidence. They remain visible and unpriced until the client provides the required commercial input.</p></div> : null}
          {selectedSnapshot.warnings.length ? <div className="mt-4 rounded-lg border border-amber-400/45 p-4"><p className="font-semibold text-amber-700 dark:text-amber-300">Review notes</p><ul className="mt-2 space-y-1 text-sm text-[var(--color-text-secondary)]">{selectedSnapshot.warnings.map((warning, index) => <li key={`${warningText(warning)}-${index}`}>{warningText(warning)}</li>)}</ul></div> : null}
          <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto_auto]"><label className="text-sm font-semibold text-[var(--color-text-primary)]">Review note<input className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5" placeholder="Decision, approval meeting or commercial caveat" value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} /></label><button className="app-button-secondary self-end gap-2" type="button" disabled={selectedSnapshot.coverage_pct < 100 || busyAction !== null} onClick={() => void reviewSnapshot("approved")}>{busyAction === "approved" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileCheck2 className="h-4 w-4" />}Approve</button><button className="app-button-primary self-end gap-2" type="button" disabled={selectedSnapshot.coverage_pct < 100 || selectedSnapshot.publication_status !== "approved" || busyAction !== null} onClick={() => void reviewSnapshot("published")}>{busyAction === "published" ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}Publish</button></div>
        </section>

        <section className="app-table-shell"><div className="border-b border-[var(--color-border)] px-5 py-4"><p className="app-label">Line Items</p><h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Demand, commercial variant, price and provenance</h2></div><div className="overflow-x-auto"><table className="w-full min-w-[1200px] text-left text-sm"><thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-[0.12em] text-[var(--color-text-muted)]"><tr><th className="px-5 py-3">Environment / service</th><th className="px-5 py-3">Edition / license / SKU</th><th className="px-5 py-3">Metric</th><th className="px-5 py-3 text-right">Quantity</th><th className="px-5 py-3 text-right">Unit price</th><th className="px-5 py-3 text-right">Monthly</th><th className="px-5 py-3">Status / provenance</th></tr></thead><tbody className="divide-y divide-[var(--color-border)]">{selectedSnapshot.line_items.map((line) => { const requiresRateCard = line.status === "rate_card_required"; const requiresInput = line.status === "input_required"; const intentionallyUnpriced = requiresRateCard || requiresInput; return <tr key={line.id} className="align-top"><td className="px-5 py-4"><p className="font-semibold text-[var(--color-text-primary)]">{line.description}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{line.environment} · {line.service_id}</p></td><td className="px-5 py-4"><p className="font-medium text-[var(--color-text-primary)]">{typeof line.provenance.commercial_variant === "string" ? line.provenance.commercial_variant : "Governed default"}</p><p className="mt-1 font-mono text-xs text-[var(--color-text-muted)]">{line.part_number ?? "Policy-level product"}</p></td><td className="px-5 py-4 text-[var(--color-text-secondary)]">{line.metric_name}</td><td className="px-5 py-4 text-right font-mono text-[var(--color-text-primary)]">{formatNumber(line.quantity)} {line.unit}</td><td className="px-5 py-4 text-right font-mono text-[var(--color-text-secondary)]">{intentionallyUnpriced ? "—" : line.unit_price.toFixed(6)}</td><td className="px-5 py-4 text-right font-semibold text-[var(--color-text-primary)]">{intentionallyUnpriced ? "—" : currency(line.monthly_amount, selectedSnapshot.currency)}</td><td className="max-w-sm px-5 py-4"><span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusTone(line.status)}`}>{requiresRateCard ? "Rate card required" : requiresInput ? "Client input required" : line.status.replaceAll("_", " ")}</span><p className="mt-2 break-words text-xs leading-5 text-[var(--color-text-muted)]">{requiresRateCard ? "Exact customer-rate part-number match required" : requiresInput ? "Client pricing or entitlement evidence required" : line.formula}</p>{line.warnings.length ? <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">{line.warnings.map(warningText).join(" · ")}</p> : null}</td></tr>; })}</tbody></table></div></section>
      </> : <section className="app-card p-8 text-center"><p className="font-semibold text-[var(--color-text-primary)]">No BOM snapshot yet</p><p className="mt-2 text-sm text-[var(--color-text-secondary)]">Approve a deployment scenario and run the first estimate.</p></section>}

      {snapshots.length > 1 ? (
        <section className="app-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="app-label">Snapshot Comparison</p>
              <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Explain estimate movement</h2>
            </div>
            <button
              type="button"
              className="app-button-secondary gap-2"
              disabled={busyAction !== null || baselineSnapshotId === comparisonSnapshotId}
              onClick={() => void compareSnapshots()}
            >
              {busyAction === "compare" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
              Compare
            </button>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <label className="text-sm font-semibold text-[var(--color-text-primary)]">
              Baseline
              <select
                className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5"
                value={baselineSnapshotId}
                onChange={(event) => {
                  setBaselineSnapshotId(event.target.value);
                  setComparison(null);
                }}
              >
                {snapshots.map((snapshot) => (
                  <option key={snapshot.id} value={snapshot.id}>{formatDate(snapshot.created_at)} · {currency(snapshot.monthly_total, snapshot.currency)}</option>
                ))}
              </select>
            </label>
            <label className="text-sm font-semibold text-[var(--color-text-primary)]">
              Comparison
              <select
                className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5"
                value={comparisonSnapshotId}
                onChange={(event) => {
                  setComparisonSnapshotId(event.target.value);
                  setComparison(null);
                }}
              >
                {snapshots.map((snapshot) => (
                  <option key={snapshot.id} value={snapshot.id}>{formatDate(snapshot.created_at)} · {currency(snapshot.monthly_total, snapshot.currency)}</option>
                ))}
              </select>
            </label>
          </div>
          {comparison ? (
            <div className="mt-5 border-t border-[var(--color-border)] pt-5">
              <div className="grid gap-3 sm:grid-cols-3">
                <div><p className="app-label">Monthly delta</p><p className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">{currency(comparison.monthly_delta, comparison.currency)}</p></div>
                <div><p className="app-label">Annual delta</p><p className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">{currency(comparison.annual_delta, comparison.currency)}</p></div>
                <div><p className="app-label">Contract delta</p><p className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">{currency(comparison.contract_delta, comparison.currency)}</p></div>
              </div>
              <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(14rem,1fr)]">
                <div>
                  <p className="app-label">Monthly impact profile</p>
                  <div className="mt-3 h-56 w-full" aria-label="Monthly BOM comparison delta chart">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={comparisonPeriods} margin={{ top: 8, right: 8, bottom: 4, left: 0 }}>
                        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="period" tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} interval="preserveStartEnd" />
                        <YAxis tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} tickFormatter={(value) => new Intl.NumberFormat("en-US", { notation: "compact" }).format(Number(value))} />
                        <Tooltip contentStyle={{ background: "var(--color-surface)", borderColor: "var(--color-border)", borderRadius: 8, color: "var(--color-text-primary)" }} formatter={(value) => currency(Number(value), comparison.currency)} />
                        <ReferenceLine y={0} stroke="var(--color-text-muted)" />
                        <Bar dataKey="delta" name="Monthly delta" fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <div>
                  <p className="app-label">Change categories</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {comparisonCategories.length ? comparisonCategories.map((category) => (
                      <span key={category} className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2.5 py-1 text-xs font-semibold capitalize text-[var(--color-text-secondary)]">
                        {category}
                      </span>
                    )) : <span className="text-sm text-[var(--color-text-muted)]">No material category change detected.</span>}
                  </div>
                  <p className="mt-4 text-sm leading-6 text-[var(--color-text-secondary)]">
                    Period deltas preserve activation timing, so a later start remains visible even when steady-state run rates converge.
                  </p>
                </div>
              </div>
              <div className="mt-5 grid gap-5 border-t border-[var(--color-border)] pt-5 lg:grid-cols-3">
                <div><p className="app-label">Service deltas</p><div className="mt-2 space-y-2">{Object.entries(comparison.service_monthly_deltas).map(([label, value]) => <div key={label} className="flex justify-between gap-3 text-sm"><span className="text-[var(--color-text-secondary)]">{label}</span><span className="font-mono text-[var(--color-text-primary)]">{currency(value, comparison.currency)}</span></div>)}</div></div>
                <div><p className="app-label">Environment deltas</p><div className="mt-2 space-y-2">{Object.entries(comparison.environment_monthly_deltas).map(([label, value]) => <div key={label} className="flex justify-between gap-3 text-sm"><span className="text-[var(--color-text-secondary)]">{label}</span><span className="font-mono text-[var(--color-text-primary)]">{currency(value, comparison.currency)}</span></div>)}</div></div>
                <div><p className="app-label">Drivers</p><ul className="mt-2 space-y-2 text-sm leading-5 text-[var(--color-text-secondary)]">{comparison.drivers.map((driver) => <li key={driver}>{driver}</li>)}</ul></div>
              </div>
            </div>
          ) : null}
          <div className="mt-5 border-t border-[var(--color-border)] pt-4">
            <p className="app-label">Snapshot History</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {snapshots.map((snapshot) => (
                <button
                  key={snapshot.id}
                  type="button"
                  className={`rounded-lg border px-3 py-2 text-left text-sm ${selectedSnapshot?.id === snapshot.id ? "border-[var(--color-accent)] text-[var(--color-text-primary)]" : "border-[var(--color-border)] text-[var(--color-text-secondary)]"}`}
                  onClick={() => void selectSnapshot(snapshot)}
                >
                  {formatDate(snapshot.created_at)} · {currency(snapshot.monthly_total, snapshot.currency)}
                </button>
              ))}
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
