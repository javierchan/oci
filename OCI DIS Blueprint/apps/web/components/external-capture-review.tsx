"use client";

/* Governed review workspace for structured external capture evidence. */

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  CircleHelp,
  FileSearch,
  Loader2,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react";

import { AgentDecisionWorkspace } from "@/components/agent-decision-workspace";
import {
  ImportCorrectionBrief,
  selectLatestImportCorrectionSessionRun,
} from "@/components/import-correction-brief";
import { ConfirmModal } from "@/components/modal";
import { emitToast } from "@/hooks/use-toast";
import { api, getErrorMessage } from "@/lib/api";
import type {
  AgentRun,
  ExternalCaptureDraft,
  ExternalCaptureDraftStatus,
  ExternalCaptureSession,
  ExternalCaptureSessionDetail,
  PatternDefinition,
  Project,
} from "@/lib/types";

type CaptureReviewProps = {
  project: Project;
  initialSessions: ExternalCaptureSession[];
  patterns: PatternDefinition[];
};

type DraftForm = {
  brand: string;
  business_process: string;
  interface_name: string;
  source_system: string;
  destination_system: string;
  selected_pattern: string;
  pattern_rationale: string;
  payload_per_execution_kb: string;
};

const PAGE_SIZE = 25;

const REQUIRED_LABELS: Record<string, string> = {
  brand: "Brand",
  business_process: "Business process",
  interface_name: "Interface name",
  source_system: "Source system",
  destination_system: "Destination system",
  selected_pattern: "Governed pattern",
};

function stringValue(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  if (value === null || value === undefined) return "";
  return String(value);
}

function numberValue(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  return typeof value === "number" ? String(value) : "";
}

function formFromDraft(draft: ExternalCaptureDraft): DraftForm {
  return {
    brand: stringValue(draft.proposed_payload, "brand"),
    business_process: stringValue(draft.proposed_payload, "business_process"),
    interface_name: stringValue(draft.proposed_payload, "interface_name"),
    source_system: stringValue(draft.proposed_payload, "source_system"),
    destination_system: stringValue(draft.proposed_payload, "destination_system"),
    selected_pattern: stringValue(draft.proposed_payload, "selected_pattern"),
    pattern_rationale: stringValue(draft.proposed_payload, "pattern_rationale"),
    payload_per_execution_kb: numberValue(
      draft.proposed_payload,
      "payload_per_execution_kb",
    ),
  };
}

function statusTone(status: ExternalCaptureDraftStatus): string {
  if (status === "promoted") {
    return "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200";
  }
  if (status === "approved") {
    return "border-sky-300 bg-sky-50 text-sky-800 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-200";
  }
  if (status === "rejected") {
    return "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200";
  }
  return "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200";
}

function Metric({
  label,
  value,
  detail,
  tone = "neutral",
}: {
  label: string;
  value: number;
  detail: string;
  tone?: "neutral" | "positive" | "warning";
}): JSX.Element {
  const valueClass =
    tone === "positive"
      ? "text-emerald-700 dark:text-emerald-300"
      : tone === "warning"
        ? "text-amber-700 dark:text-amber-300"
        : "text-[var(--color-text-primary)]";
  return (
    <div className="min-w-0 border-r border-[var(--color-border)] px-5 py-4 last:border-r-0">
      <p className="app-label">{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${valueClass}`}>{value}</p>
      <p className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">{detail}</p>
    </div>
  );
}

async function waitForAgent(run: AgentRun): Promise<AgentRun> {
  let current = run;
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (["completed", "failed", "cancelled"].includes(current.status)) return current;
    await new Promise((resolve) => window.setTimeout(resolve, 1000));
    current = await api.getAgentRun(current.id);
  }
  throw new Error("Import Correction Agent did not finish within two minutes.");
}

export function ExternalCaptureReview({
  project,
  initialSessions,
  patterns,
}: CaptureReviewProps): JSX.Element {
  const selectedSessionId = initialSessions[0]?.id ?? "";
  const [detail, setDetail] = useState<ExternalCaptureSessionDetail | null>(null);
  const [drafts, setDrafts] = useState<ExternalCaptureDraft[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<ExternalCaptureDraftStatus | "">(
    "",
  );
  const [search, setSearch] = useState("");
  const [committedSearch, setCommittedSearch] = useState("");
  const [expandedDraftId, setExpandedDraftId] = useState<string | null>(null);
  const [draftForm, setDraftForm] = useState<DraftForm | null>(null);
  const [reviewRationale, setReviewRationale] = useState("");
  const [isLoading, setIsLoading] = useState(Boolean(selectedSessionId));
  const [actionId, setActionId] = useState<string | null>(null);
  const [agentRun, setAgentRun] = useState<AgentRun | null>(null);
  const [focusedAgentRuns, setFocusedAgentRuns] = useState<Record<string, AgentRun>>(
    {},
  );
  const [agentActionId, setAgentActionId] = useState<string | null>(null);
  const [correctionActionId, setCorrectionActionId] = useState<string | null>(null);
  const [confirmFixAll, setConfirmFixAll] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedSession = useMemo(
    () => initialSessions.find((session) => session.id === selectedSessionId) ?? null,
    [initialSessions, selectedSessionId],
  );
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const patternById = useMemo(
    () => new Map(patterns.map((pattern) => [pattern.pattern_id, pattern])),
    [patterns],
  );

  async function loadWorkspace(): Promise<void> {
    if (!selectedSessionId) return;
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const [nextDetail, nextDrafts, recentAgentRuns] = await Promise.all([
        api.getExternalCaptureSession(project.id, selectedSessionId),
        api.listExternalCaptureDrafts(project.id, selectedSessionId, {
          page,
          page_size: PAGE_SIZE,
          status: statusFilter || undefined,
          search: committedSearch || undefined,
        }),
        api.listAgentRuns({ project_id: project.id, limit: 50 }),
      ]);
      setDetail(nextDetail);
      setDrafts(nextDrafts.drafts);
      setTotal(nextDrafts.total);
      setAgentRun(
        (current) =>
          current ??
          selectLatestImportCorrectionSessionRun(
            recentAgentRuns.runs,
            selectedSessionId,
          ),
      );
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "Unable to load the capture review."));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadWorkspace();
    // loadWorkspace intentionally derives from the selected filters and page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSessionId, page, statusFilter, committedSearch]);

  function openDraft(draft: ExternalCaptureDraft): void {
    if (expandedDraftId === draft.id) {
      setExpandedDraftId(null);
      setDraftForm(null);
      return;
    }
    setExpandedDraftId(draft.id);
    setDraftForm(formFromDraft(draft));
    setReviewRationale(draft.reviewer_rationale ?? "");
    if (
      draft.agent_analysis.run_id &&
      !focusedAgentRuns[draft.id]
    ) {
      void api
        .getAgentRun(draft.agent_analysis.run_id)
        .then((run) =>
          setFocusedAgentRuns((current) => ({ ...current, [draft.id]: run })),
        )
        .catch((error: unknown) =>
          setErrorMessage(
            getErrorMessage(error, "Unable to restore the latest row analysis."),
          ),
        );
    }
  }

  function replaceDraft(updated: ExternalCaptureDraft): void {
    setDrafts((current) =>
      current.map((draft) => (draft.id === updated.id ? updated : draft)),
    );
    if (expandedDraftId === updated.id) setDraftForm(formFromDraft(updated));
  }

  async function saveDraft(draft: ExternalCaptureDraft): Promise<void> {
    if (!draftForm) return;
    setActionId(draft.id);
    setErrorMessage(null);
    try {
      const payload: Record<string, unknown> = {
        ...draft.proposed_payload,
        brand: draftForm.brand || null,
        business_process: draftForm.business_process || null,
        interface_name: draftForm.interface_name || null,
        source_system: draftForm.source_system || null,
        destination_system: draftForm.destination_system || null,
        selected_pattern: draftForm.selected_pattern || null,
        pattern_rationale: draftForm.pattern_rationale || null,
        tbq: "Y",
      };
      if (draftForm.payload_per_execution_kb.trim()) {
        payload.payload_per_execution_kb = Number(draftForm.payload_per_execution_kb);
      } else {
        payload.payload_per_execution_kb = null;
      }
      const updated = await api.patchExternalCaptureDraft(
        project.id,
        selectedSessionId,
        draft.id,
        { proposed_payload: payload, expected_updated_at: draft.updated_at },
      );
      replaceDraft(updated);
      await loadWorkspace();
      emitToast(
        "success",
        "Proposal saved. The row was revalidated against the current App contract.",
      );
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "Unable to save the proposal."));
    } finally {
      setActionId(null);
    }
  }

  async function reviewDraft(
    draft: ExternalCaptureDraft,
    decision: "approve" | "reject",
  ): Promise<void> {
    const rationale = reviewRationale.trim();
    if (rationale.length < 3) {
      setErrorMessage("Add a short review rationale before recording the decision.");
      return;
    }
    setActionId(draft.id);
    setErrorMessage(null);
    try {
      const updated = await api.reviewExternalCaptureDraft(
        project.id,
        selectedSessionId,
        draft.id,
        { decision, rationale, expected_updated_at: draft.updated_at },
      );
      replaceDraft(updated);
      await loadWorkspace();
      emitToast(
        "success",
        `${decision === "approve" ? "Proposal approved" : "Proposal rejected"}. The governed decision and rationale were recorded.`,
      );
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "Unable to record the review decision."));
    } finally {
      setActionId(null);
    }
  }

  async function promoteDraft(draft: ExternalCaptureDraft): Promise<void> {
    setActionId(draft.id);
    setErrorMessage(null);
    try {
      const promoted = await api.promoteExternalCaptureDraft(
        project.id,
        selectedSessionId,
        draft.id,
      );
      replaceDraft(promoted.draft);
      await loadWorkspace();
      emitToast(
        "success",
        "Integration promoted. The approved proposal now follows the canonical catalog workflow.",
      );
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "Unable to promote the proposal."));
    } finally {
      setActionId(null);
    }
  }

  async function runCorrectionAgent(
    draft?: ExternalCaptureDraft,
  ): Promise<void> {
    if (!selectedSessionId) return;
    const scopeId = draft?.id ?? "session";
    setAgentActionId(scopeId);
    setErrorMessage(null);
    try {
      const terminal = await waitForAgent(
        await api.runAgent({
          agent_type: "import_quality",
          project_id: project.id,
          context: {
            external_capture_session_id: selectedSessionId,
            ...(draft ? { external_capture_draft_id: draft.id } : {}),
          },
          message:
            draft
              ? `Explain why source row ${draft.source_row_number} needs review. Use only its governed evidence and identify the minimum human decision required.`
              : "Inspect the external capture session, explain the repeated quality gaps, and prioritize the user decisions required before canonical promotion.",
          include_provider: true,
        }),
      );
      if (terminal.status !== "completed") {
        throw new Error("Import Correction Agent did not complete successfully.");
      }
      if (draft) {
        setFocusedAgentRuns((current) => ({
          ...current,
          [draft.id]: terminal,
        }));
        await loadWorkspace();
      } else {
        setAgentRun(terminal);
      }
    } catch (error) {
      setErrorMessage(getErrorMessage(error, "Unable to run Import Correction Agent."));
    } finally {
      setAgentActionId(null);
    }
  }

  async function applyCorrections(draft?: ExternalCaptureDraft): Promise<void> {
    if (!selectedSessionId) return;
    const scopeId = draft?.id ?? "all";
    setCorrectionActionId(scopeId);
    setErrorMessage(null);
    try {
      const result = await api.applyExternalCaptureCorrections(
        project.id,
        selectedSessionId,
        draft
          ? { scope: "selected", draft_ids: [draft.id], confirm: true }
          : { scope: "all_eligible", draft_ids: [], confirm: true },
      );
      setFocusedAgentRuns({});
      await loadWorkspace();
      if (result.applied > 0) {
        emitToast(
          "success",
          `${result.applied} correction${result.applied === 1 ? "" : "s"} applied. Every changed row now requires re-analysis; no row was approved or promoted.`,
        );
      } else {
        emitToast(
          "info",
          "No executable correction was applied. Rows without grounded evidence remain human decisions.",
        );
      }
    } catch (error) {
      setErrorMessage(
        getErrorMessage(error, "Unable to apply the authorized correction scope."),
      );
    } finally {
      setCorrectionActionId(null);
      setConfirmFixAll(false);
    }
  }

  if (!selectedSessionId) {
    return (
      <section className="app-card p-8">
        <FileSearch className="h-7 w-7 text-[var(--color-accent)]" />
        <h2 className="mt-4 text-2xl font-semibold text-[var(--color-text-primary)]">
          No external capture evidence is staged
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
          This workspace appears when structured customer evidence is staged through
          the governed external-capture API. Workbook uploads remain available in the
          regular Import workspace.
        </p>
        <Link
          href={`/projects/${project.id}/import`}
          className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[var(--color-accent)]"
        >
          Open workbook import <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    );
  }

  return (
    <div className="space-y-5">
      <section className="app-card overflow-hidden">
        <div className="grid divide-y divide-[var(--color-border)] md:grid-cols-5 md:divide-x md:divide-y-0">
          <Metric label="Source rows" value={detail?.summary.total ?? 0} detail="Preserved as client evidence" />
          <Metric label="Schema ready" value={detail?.summary.schema_ready ?? 0} detail="Eligible for human approval" tone="positive" />
          <Metric label="Missing evidence" value={detail?.summary.missing_required ?? 0} detail="Blocked without invention" tone="warning" />
          <Metric label="Pattern changes" value={detail?.summary.pattern_changes ?? 0} detail="Explicit source-to-proposal differences" tone="warning" />
          <Metric label="Promoted" value={detail?.summary.promoted ?? 0} detail="Canonical catalog records" />
        </div>
      </section>

      <section className="app-card overflow-hidden">
        <div className="grid gap-5 border-b border-[var(--color-border)] p-5 lg:grid-cols-[1fr_auto] lg:items-start">
          <div>
            <p className="app-label">Governed evidence boundary</p>
            <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
              Customer source and App proposal stay separate
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Supported source inputs remain immutable evidence. Excluded headers are
              retained without their values. The proposed App record is editable,
              revalidated on every save, and cannot reach the catalog until an architect
              approves and promotes it.
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={() => void runCorrectionAgent()}
              disabled={agentActionId !== null || correctionActionId !== null}
              className="app-button-secondary"
            >
              {agentActionId === "session" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bot className="h-4 w-4" />}
              {agentActionId === "session" ? "Analyzing evidence..." : "Analyze review backlog"}
            </button>
            <button
              type="button"
              onClick={() => setConfirmFixAll(true)}
              disabled={
                correctionActionId !== null ||
                agentActionId !== null ||
                (detail?.summary.corrections_available ?? 0) === 0
              }
              className="app-button-primary"
            >
              {correctionActionId === "all" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {correctionActionId === "all"
                ? "Applying grounded fixes..."
                : `Fix all eligible (${detail?.summary.corrections_available ?? 0})`}
            </button>
          </div>
        </div>
        <div className="grid gap-0 md:grid-cols-3">
          <div className="border-b border-[var(--color-border)] p-5 md:border-b-0 md:border-r">
            <p className="app-label">1 · Preserve</p>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
              Keep each supported value, row number, source label, and evidence hash.
            </p>
          </div>
          <div className="border-b border-[var(--color-border)] p-5 md:border-b-0 md:border-r">
            <p className="app-label">2 · Normalize</p>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
              Map dictionaries, payload units, TBQ, and pattern evidence without guessing.
            </p>
          </div>
          <div className="p-5">
            <p className="app-label">3 · Decide</p>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
              Approve only schema-ready proposals; promote them explicitly when accepted.
            </p>
          </div>
        </div>
        <div className="border-t border-[var(--color-border)] bg-[var(--color-surface-2)] px-5 py-4 text-sm text-[var(--color-text-secondary)]">
          <span className="font-semibold text-[var(--color-text-primary)]">
            {detail?.summary.corrections_available ?? 0} executable agent fixes
          </span>
          {" · "}
          {detail?.summary.human_decision_rows ?? 0} rows still need human evidence or
          judgment. Fixing never approves, rejects, or promotes integrations.
        </div>
      </section>

      {agentRun ? (
        <section className="app-card p-5">
          <p className="app-label">Import Correction Agent</p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
            Evidence-backed review brief
          </h2>
          <ImportCorrectionBrief
            summary={agentRun.result?.summary}
            brief={agentRun.result?.brief}
            quality={agentRun.result?.output_quality}
            providerStatus={agentRun.result?.provider_status}
          />
          {agentRun.result?.decision_workspace ? (
            <div className="mt-5">
              <AgentDecisionWorkspace run={agentRun} onRunChange={setAgentRun} />
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="app-table-shell overflow-hidden">
        <div className="grid gap-4 border-b border-[var(--color-border)] p-5 lg:grid-cols-[1fr_auto_auto] lg:items-end">
          <label className="min-w-0">
            <span className="app-label">Find customer evidence</span>
            <span className="mt-2 flex items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3">
              <Search className="h-4 w-4 text-[var(--color-text-muted)]" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    setPage(1);
                    setCommittedSearch(search.trim());
                  }
                }}
                placeholder="Interface, source, or destination..."
                className="h-11 min-w-0 flex-1 bg-transparent text-sm text-[var(--color-text-primary)] outline-none"
              />
            </span>
          </label>
          <label>
            <span className="app-label">Decision state</span>
            <select
              value={statusFilter}
              onChange={(event) => {
                setPage(1);
                setStatusFilter(event.target.value as ExternalCaptureDraftStatus | "");
              }}
              className="app-input mt-2 min-w-44"
            >
              <option value="">All proposals</option>
              <option value="needs_review">Needs review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
              <option value="promoted">Promoted</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() => {
              setPage(1);
              setCommittedSearch(search.trim());
            }}
            className="app-button-secondary"
          >
            <Search className="h-4 w-4" /> Search
          </button>
        </div>

        {errorMessage ? (
          <div className="border-b border-rose-300 bg-rose-50 px-5 py-4 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
            {errorMessage}
          </div>
        ) : null}

        <div className="border-b border-[var(--color-border)] bg-[var(--color-surface-2)] px-5 py-3 text-xs text-[var(--color-text-muted)]">
          {selectedSession?.source_label} · SHA-256 evidence registered · {total} matching proposal{total === 1 ? "" : "s"}
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 px-5 py-16 text-sm text-[var(--color-text-muted)]">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading governed proposals...
          </div>
        ) : drafts.length === 0 ? (
          <div className="px-5 py-16 text-center text-sm text-[var(--color-text-muted)]">
            No proposals match the current filters.
          </div>
        ) : (
          <div className="divide-y divide-[var(--color-border)]">
            {drafts.map((draft) => {
              const expanded = draft.id === expandedDraftId;
              const proposedPattern = stringValue(draft.pattern_assessment, "recommended_pattern");
              const sourcePattern = stringValue(draft.pattern_assessment, "source_pattern");
              const pattern = patternById.get(
                stringValue(draft.proposed_payload, "selected_pattern"),
              );
              const sourceSystem = stringValue(draft.proposed_payload, "source_system") || "Source missing";
              const destinationSystem = stringValue(draft.proposed_payload, "destination_system") || "Destination missing";
              const primaryTrigger = draft.review_triggers[0];
              const focusedAgentRun = focusedAgentRuns[draft.id] ?? null;
              return (
                <article key={draft.id} className="bg-[var(--color-surface)]">
                  <button
                    type="button"
                    onClick={() => openDraft(draft)}
                    className="grid w-full gap-3 px-5 py-4 text-left transition hover:bg-[var(--color-hover)] md:grid-cols-[4rem_minmax(0,2fr)_minmax(12rem,1fr)_auto] md:items-center"
                  >
                    <span className="font-mono text-xs text-[var(--color-text-muted)]">
                      Row {draft.source_row_number}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-semibold text-[var(--color-text-primary)]">
                        {stringValue(draft.proposed_payload, "interface_name") || "Interface name missing"}
                      </span>
                      <span className="mt-1 block truncate text-xs text-[var(--color-text-muted)]">
                        {sourceSystem} → {destinationSystem}
                      </span>
                      <span className="mt-1.5 block truncate text-xs font-medium text-amber-700 dark:text-amber-300">
                        {primaryTrigger?.title ?? "Explicit architect review required"}
                      </span>
                    </span>
                    <span className="min-w-0 text-xs text-[var(--color-text-secondary)]">
                      <span className="block truncate">
                        {pattern
                          ? `${pattern.pattern_id} · ${pattern.name}`
                          : proposedPattern || "Pattern evidence missing"}
                      </span>
                      {sourcePattern ? (
                        <span className="mt-1 block truncate text-amber-700 dark:text-amber-300">
                          {proposedPattern
                            ? `Source ${sourcePattern} → recommended ${proposedPattern}`
                            : `Source ${sourcePattern} · recommendation pending`}
                        </span>
                      ) : null}
                    </span>
                    <span className="flex items-center justify-between gap-3 md:justify-end">
                      {draft.approval_blocked ? (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-700 dark:text-amber-300">
                          <AlertTriangle className="h-3.5 w-3.5" />
                          approval blocked
                        </span>
                      ) : null}
                      <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusTone(draft.status)}`}>
                        {draft.status.replaceAll("_", " ")}
                      </span>
                      {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </span>
                  </button>

                  {expanded && draftForm ? (
                    <div className="border-t border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                      <section className="mb-5 rounded-xl border border-amber-300/80 bg-amber-50/70 p-4 dark:border-amber-800 dark:bg-amber-950/25">
                        <div className="flex flex-wrap items-start justify-between gap-4">
                          <div className="max-w-4xl">
                            <p className="app-label">Why this line needs review</p>
                            <h3 className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">
                              {draft.review_summary}
                            </h3>
                            <p className="mt-2 text-xs leading-5 text-[var(--color-text-muted)]">
                              Validation supplies the facts below. The Import Correction
                              Agent reasons from those facts; it cannot approve, reject, or
                              promote the integration.
                            </p>
                            <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-text-muted)]">
                              Agent analysis: {draft.agent_analysis.status}
                            </p>
                            <p className="mt-2 text-xs leading-5 text-[var(--color-text-muted)]">
                              Runs OCI Generative AI with supported row evidence and the
                              governed App contract. Formula values and unsupported source
                              values are excluded before inference.
                            </p>
                          </div>
                          <div className="flex flex-wrap justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => void runCorrectionAgent(draft)}
                              disabled={
                                agentActionId !== null || correctionActionId !== null
                              }
                              className="app-button-secondary"
                            >
                              {agentActionId === draft.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Bot className="h-4 w-4" />
                              )}
                              {agentActionId === draft.id
                                ? "Reasoning from evidence..."
                                : draft.agent_analysis.status === "required"
                                  ? "Analyze and propose correction"
                                  : "Re-analyze current evidence"}
                            </button>
                            {draft.agent_analysis.correction_available ? (
                              <button
                                type="button"
                                onClick={() => void applyCorrections(draft)}
                                disabled={
                                  correctionActionId !== null ||
                                  agentActionId !== null
                                }
                                className="app-button-primary"
                              >
                                {correctionActionId === draft.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <Sparkles className="h-4 w-4" />
                                )}
                                Fix this integration
                              </button>
                            ) : null}
                          </div>
                        </div>
                        {draft.agent_analysis.correction_available ? (
                          <p className="mt-3 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                            Grounded fix ready:{" "}
                            {draft.agent_analysis.correction_fields
                              .map((field) => field.replaceAll("_", " "))
                              .join(", ")}
                          </p>
                        ) : draft.agent_analysis.required_decisions.length > 0 ? (
                          <p className="mt-3 text-xs font-medium text-amber-700 dark:text-amber-300">
                            {draft.agent_analysis.required_decisions.length} human
                            decision
                            {draft.agent_analysis.required_decisions.length === 1
                              ? ""
                              : "s"}{" "}
                            remain; the agent will not invent missing evidence.
                          </p>
                        ) : null}
                        <div className="mt-4 grid gap-3 lg:grid-cols-2">
                          {draft.review_triggers.map((trigger) => (
                            <article
                              key={trigger.code}
                              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
                            >
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                                  {trigger.title}
                                </p>
                                {trigger.blocks_approval ? (
                                  <span className="rounded-full border border-rose-300 bg-rose-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-700 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
                                    Blocks approval
                                  </span>
                                ) : (
                                  <span className="app-theme-chip">Review decision</span>
                                )}
                              </div>
                              <p className="mt-1.5 text-xs leading-5 text-[var(--color-text-secondary)]">
                                {trigger.evidence}
                              </p>
                              <p className="mt-2 text-xs font-medium leading-5 text-[var(--color-text-primary)]">
                                Decision: {trigger.required_decision}
                              </p>
                            </article>
                          ))}
                        </div>
                        {focusedAgentRun || draft.agent_analysis.summary ? (
                          <div className="mt-4 rounded-lg border border-[var(--color-accent)]/35 bg-[var(--color-surface)] p-4">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm font-semibold text-[var(--color-text-primary)]">
                                Import Correction Agent explanation
                              </p>
                              <span className="app-theme-chip">
                                {(focusedAgentRun?.result?.output_quality
                                  ?.fallback_used ??
                                draft.agent_analysis.fallback_used)
                                  ? "Deterministic fallback"
                                  : draft.agent_analysis.status === "current"
                                    ? "Grounded OCI explanation"
                                    : `Analysis ${draft.agent_analysis.status}`}
                              </span>
                            </div>
                            <ImportCorrectionBrief
                              compact
                              summary={
                                focusedAgentRun?.result?.summary ??
                                draft.agent_analysis.summary ??
                                undefined
                              }
                              brief={focusedAgentRun?.result?.brief}
                              quality={focusedAgentRun?.result?.output_quality}
                              providerStatus={
                                focusedAgentRun?.result?.provider_status ??
                                draft.agent_analysis.provider_status ??
                                undefined
                              }
                            />
                            {focusedAgentRun?.result?.decision_workspace ? (
                              <AgentDecisionWorkspace
                                run={focusedAgentRun}
                                compact
                                onRunChange={(updatedRun) => {
                                  setFocusedAgentRuns((current) => ({
                                    ...current,
                                    [draft.id]: updatedRun,
                                  }));
                                  if (
                                    updatedRun.approvals.some(
                                      (approval) =>
                                        approval.execution_status === "completed",
                                    )
                                  ) {
                                    void loadWorkspace();
                                  }
                                }}
                              />
                            ) : null}
                          </div>
                        ) : null}
                      </section>

                      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
                        <section className="min-w-0">
                          <p className="app-label">Supported source evidence · read only</p>
                          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                            Only source fields with a governed App meaning are shown here.
                            Original supported values remain unchanged.
                          </p>
                          <dl className="mt-4 grid gap-x-4 gap-y-3 sm:grid-cols-2">
                            {Object.entries(draft.source_record)
                              .filter(([, value]) => value !== null && value !== "")
                              .map(([key, value]) => (
                                <div key={key} className="min-w-0 border-b border-[var(--color-border)] pb-2">
                                  <dt className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-muted)]">
                                    {key.replaceAll("_", " ")}
                                  </dt>
                                  <dd className="mt-1 break-words text-sm text-[var(--color-text-primary)]">
                                    {String(value)}
                                  </dd>
                                </div>
                              ))}
                          </dl>
                          {draft.ignored_source_fields.length ? (
                            <div className="mt-4 rounded-lg border border-sky-300 bg-sky-50 p-3 text-sm text-sky-900 dark:border-sky-800 dark:bg-sky-950/30 dark:text-sky-100">
                              <p className="font-semibold">
                                {draft.ignored_source_fields.length} source-only field
                                {draft.ignored_source_fields.length === 1 ? "" : "s"} excluded
                              </p>
                              <p className="mt-1 text-xs leading-5">
                                These values are not evaluated, mapped, or promoted into the
                                App record. Immutable audit evidence remains isolated from the
                                operational contract.
                              </p>
                              <ul className="mt-2 space-y-1 text-xs">
                                {draft.ignored_source_fields.map((field) => (
                                  <li key={field.source_header}>
                                    <span className="font-semibold">
                                      {field.source_header}
                                    </span>{" "}
                                    · {field.reason}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                        </section>

                        <section className="min-w-0 border-t border-[var(--color-border)] pt-5 xl:border-l xl:border-t-0 xl:pl-5 xl:pt-0">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="app-label">Proposed App record · editable</p>
                              <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                                Required gaps block approval. TBQ remains governed as Y for this exercise.
                              </p>
                            </div>
                            <span className="rounded-full border border-[var(--color-border)] px-2.5 py-1 text-xs text-[var(--color-text-muted)]">
                              QA {draft.qa_preview.status ?? "PENDING"}
                            </span>
                          </div>

                          {draft.approval_blocked ? (
                            <div className="mt-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/35 dark:text-amber-100">
                              <p className="font-semibold">Evidence required before approval</p>
                              <p className="mt-1">
                                {draft.required_field_gaps
                                  .map((field) => REQUIRED_LABELS[field] ?? field)
                                  .join(" · ")}
                              </p>
                            </div>
                          ) : (
                            <div className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-sky-700 dark:text-sky-300">
                              <CheckCircle2 className="h-4 w-4" /> Required fields complete · architecture review still required
                            </div>
                          )}

                          <div className="mt-4 grid gap-4 sm:grid-cols-2">
                            {(
                              [
                                ["brand", "Brand"],
                                ["business_process", "Business process"],
                                ["interface_name", "Interface name"],
                                ["source_system", "Source system"],
                                ["destination_system", "Destination system"],
                              ] as const
                            ).map(([field, label]) => (
                              <label key={field} className={field === "interface_name" ? "sm:col-span-2" : ""}>
                                <span className="text-xs font-semibold text-[var(--color-text-secondary)]">{label}</span>
                                <input
                                  value={draftForm[field]}
                                  onChange={(event) =>
                                    setDraftForm((current) =>
                                      current ? { ...current, [field]: event.target.value } : current,
                                    )
                                  }
                                  className="app-input mt-1.5 w-full"
                                />
                              </label>
                            ))}
                            <label>
                              <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Governed pattern</span>
                              <select
                                value={draftForm.selected_pattern}
                                onChange={(event) =>
                                  setDraftForm((current) =>
                                    current ? { ...current, selected_pattern: event.target.value } : current,
                                  )
                                }
                                className="app-input mt-1.5 w-full"
                              >
                                <option value="">Select pattern evidence</option>
                                {patterns.map((item) => (
                                  <option key={item.id} value={item.pattern_id}>
                                    {item.pattern_id} · {item.name}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label>
                              <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Payload / execution (KB)</span>
                              <input
                                type="number"
                                min="0"
                                step="0.001"
                                value={draftForm.payload_per_execution_kb}
                                onChange={(event) =>
                                  setDraftForm((current) =>
                                    current
                                      ? { ...current, payload_per_execution_kb: event.target.value }
                                      : current,
                                  )
                                }
                                className="app-input mt-1.5 w-full"
                              />
                            </label>
                            <label className="sm:col-span-2">
                              <span className="text-xs font-semibold text-[var(--color-text-secondary)]">Current proposed pattern rationale</span>
                              <textarea
                                value={draftForm.pattern_rationale}
                                onChange={(event) =>
                                  setDraftForm((current) =>
                                    current ? { ...current, pattern_rationale: event.target.value } : current,
                                  )
                                }
                                rows={3}
                                className="app-input mt-1.5 w-full resize-y py-2"
                              />
                            </label>
                          </div>

                          <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-[var(--color-border)] pt-4">
                            <button
                              type="button"
                              onClick={() => void saveDraft(draft)}
                              disabled={actionId === draft.id || draft.status === "promoted"}
                              className="app-button-secondary"
                            >
                              {actionId === draft.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                              Save and revalidate
                            </button>
                            <input
                              value={reviewRationale}
                              onChange={(event) => setReviewRationale(event.target.value)}
                              placeholder="Architect review rationale"
                              className="app-input min-w-[16rem] flex-1"
                              disabled={draft.status === "promoted"}
                            />
                            <button
                              type="button"
                              onClick={() => void reviewDraft(draft, "reject")}
                              disabled={actionId === draft.id || draft.status === "promoted"}
                              className="app-button-secondary"
                            >
                              <XCircle className="h-4 w-4" /> Reject
                            </button>
                            {draft.agent_analysis.status !== "current" ? (
                              <span className="text-xs font-medium text-amber-700 dark:text-amber-300">
                                Approval requires a grounded, current agent analysis.
                              </span>
                            ) : null}
                            <button
                              type="button"
                              onClick={() => void reviewDraft(draft, "approve")}
                              disabled={
                                actionId === draft.id ||
                                draft.status === "promoted" ||
                                draft.approval_blocked ||
                                draft.agent_analysis.status !== "current"
                              }
                              className="app-button-primary"
                            >
                              <ShieldCheck className="h-4 w-4" /> Approve
                            </button>
                            {draft.status === "approved" ? (
                              <button
                                type="button"
                                onClick={() => void promoteDraft(draft)}
                                disabled={actionId === draft.id}
                                className="app-button-primary"
                              >
                                <ArrowRight className="h-4 w-4" /> Promote to catalog
                              </button>
                            ) : null}
                            {draft.status === "promoted" && draft.promoted_integration_id ? (
                              <Link
                                href={`/projects/${project.id}/catalog/${draft.promoted_integration_id}`}
                                className="app-button-secondary"
                              >
                                Open integration <ArrowRight className="h-4 w-4" />
                              </Link>
                            ) : null}
                          </div>
                        </section>
                      </div>
                    </div>
                  ) : null}
                </article>
              );
            })}
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-border)] px-5 py-4">
          <p className="text-sm text-[var(--color-text-muted)]">
            Page {page} of {pageCount} · {total} proposals
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={page === 1}
              className="app-button-secondary"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
              disabled={page >= pageCount}
              className="app-button-secondary"
            >
              Next
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="app-card p-5">
          <CircleHelp className="h-5 w-5 text-[var(--color-accent)]" />
          <p className="app-label mt-4">Why rows are not auto-imported</p>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            External columns can be ambiguous. The App preserves that ambiguity and asks
            for a bounded decision instead of silently turning a guess into architecture.
          </p>
        </div>
        <div className="app-card p-5">
          <ShieldCheck className="h-5 w-5 text-[var(--color-accent)]" />
          <p className="app-label mt-4">Economic scope</p>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            {selectedSession?.normalization_policy.force_tbq_y === true
              ? "This session explicitly normalizes proposals to TBQ=Y while preserving the received source value as evidence."
              : "TBQ is preserved from supported source evidence. Missing or unsupported values require an explicit human decision; this review does not change commercial scope automatically."}
          </p>
        </div>
      </section>
      <ConfirmModal
        open={confirmFixAll}
        title="Apply all eligible agent fixes?"
        description={`This applies ${detail?.summary.corrections_available ?? 0} current, grounded correction drafts. ${detail?.summary.human_decision_rows ?? 0} rows will remain for human review. Every changed row becomes stale and must be re-analyzed. Nothing will be approved, rejected, or promoted.`}
        confirmLabel="Fix all eligible"
        cancelLabel="Review individually"
        onConfirm={() => void applyCorrections()}
        onCancel={() => setConfirmFixAll(false)}
      />
    </div>
  );
}
