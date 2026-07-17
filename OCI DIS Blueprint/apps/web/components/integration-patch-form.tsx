"use client";

/* Architect-facing patch form for pattern, rationale, comments, and core tools. */

import { useRouter, useSearchParams } from "next/navigation";
import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import { Save, Trash2 } from "lucide-react";

import { ConfirmModal } from "@/components/modal";
import { PatternBadge } from "@/components/pattern-badge";
import { PatternSupportBadge } from "@/components/pattern-support-badge";
import { QaBadge } from "@/components/qa-badge";
import { emitToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import { deriveCanvasSemantics, parseCanvasState } from "@/lib/canvas-governance";
import type { CanvasCombination, DictionaryOption, Integration, IntegrationPatch, PatternDefinition } from "@/lib/types";

type IntegrationPatchFormProps = {
  projectId: string;
  integration: Integration;
  patterns: PatternDefinition[];
  toolOptions: DictionaryOption[];
  overlayOptions: DictionaryOption[];
  combinations: CanvasCombination[];
};

function parseCoreTools(value: string | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((entry: string) => entry.trim())
    .filter(Boolean);
}

export function IntegrationPatchForm({
  projectId,
  integration,
  patterns,
  toolOptions,
  overlayOptions,
  combinations,
}: IntegrationPatchFormProps): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const patternSelectRef = useRef<HTMLSelectElement | null>(null);
  const [currentIntegration, setCurrentIntegration] = useState<Integration>(integration);
  const [selectedPattern, setSelectedPattern] = useState<string>(integration.selected_pattern ?? "");
  const [patternRationale, setPatternRationale] = useState<string>(integration.pattern_rationale ?? "");
  const [comments, setComments] = useState<string>(integration.comments ?? "");
  const [businessCriticality, setBusinessCriticality] = useState<string>(integration.business_criticality ?? "");
  const [targetLatencySla, setTargetLatencySla] = useState<string>(integration.target_latency_sla ?? "");
  const [dataClassification, setDataClassification] = useState<string>(integration.data_security_classification ?? "");
  const [retentionWindow, setRetentionWindow] = useState<string>(integration.retention_processing_window ?? "");
  const [retryPolicy, setRetryPolicy] = useState<string>(integration.retry_policy ?? "");
  const [idempotency, setIdempotency] = useState<string>(integration.idempotency ?? "");
  const [tbq, setTbq] = useState<"Y" | "N">(integration.tbq);
  const [saving, setSaving] = useState<boolean>(false);
  const [deleting, setDeleting] = useState<boolean>(false);
  const [deleteOpen, setDeleteOpen] = useState<boolean>(false);

  const patternMap = new Map<string, PatternDefinition>(
    patterns.map((patternDefinition: PatternDefinition) => [
      patternDefinition.pattern_id,
      patternDefinition,
    ]),
  );
  const selectedPatternDefinition = selectedPattern ? patternMap.get(selectedPattern) ?? null : null;
  const currentPatternDefinition = currentIntegration.selected_pattern
    ? patternMap.get(currentIntegration.selected_pattern) ?? null
    : null;
  const savedCanvasState = useMemo(
    () => parseCanvasState(currentIntegration.additional_tools_overlays, parseCoreTools(currentIntegration.core_tools)),
    [currentIntegration.additional_tools_overlays, currentIntegration.core_tools],
  );
  const canvasSemantics = useMemo(
    () =>
      deriveCanvasSemantics({
        nodes: savedCanvasState.nodes,
        edges: savedCanvasState.edges,
        overlayToolKeys: overlayOptions.map((option) => option.value),
        combinations,
        selectedPattern: currentIntegration.selected_pattern,
      }),
    [combinations, currentIntegration.selected_pattern, overlayOptions, savedCanvasState.edges, savedCanvasState.nodes],
  );

  useEffect(() => {
    if (searchParams.get("focus") === "patch") {
      patternSelectRef.current?.focus();
    }
  }, [searchParams]);

  async function handleSave(): Promise<void> {
    setSaving(true);

    const payload: IntegrationPatch = {
      selected_pattern: selectedPattern || undefined,
      pattern_rationale: patternRationale || undefined,
      comments: comments || undefined,
      business_criticality: businessCriticality,
      target_latency_sla: targetLatencySla,
      data_security_classification: dataClassification,
      retention_processing_window: retentionWindow,
      retry_policy: retryPolicy,
      idempotency,
      tbq,
    };

    try {
      const updated = await api.patchIntegration(projectId, integration.id, payload);
      setCurrentIntegration(updated);
      emitToast("success", "Integration saved and recalculated.");
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      emitToast("error", caughtError instanceof Error ? caughtError.message : "Unable to save.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(): Promise<void> {
    setDeleting(true);
    try {
      await api.deleteIntegration(projectId, integration.id);
      emitToast("success", "Integration removed.");
      router.push(`/projects/${projectId}/catalog`);
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      emitToast("error", caughtError instanceof Error ? caughtError.message : "Unable to remove integration.");
      setDeleting(false);
    }
  }

  return (
    <section id="patch-form" className="app-card sticky top-4 space-y-6 p-6 max-h-[calc(100vh-2rem)] overflow-y-auto">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="app-label">Architect Patch</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            Assign pattern and governed tools
          </h2>
        </div>
        <QaBadge status={currentIntegration.qa_status} />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || deleting}
          className="app-button-primary h-10 gap-2"
        >
          <Save className="h-4 w-4" />
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={() => {
            setDeleteOpen(true);
          }}
          disabled={saving || deleting}
          className="app-button-danger h-10 gap-2"
          aria-label="Remove integration"
        >
          <Trash2 className="h-4 w-4" />
          {deleting ? "Removing…" : "Remove"}
        </button>
      </div>

      <div className="app-card-muted p-4">
        <p className="app-label">Current Pattern</p>
        <div className="mt-3">
          <PatternBadge
            patternId={currentIntegration.selected_pattern}
            name={
              currentPatternDefinition?.name ?? null
            }
            category={
              currentPatternDefinition?.category ?? null
            }
          />
          {currentPatternDefinition ? (
            <div className="mt-3">
              <PatternSupportBadge support={currentPatternDefinition.support} />
            </div>
          ) : null}
        </div>
      </div>

      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Pattern</span>
        <select
          ref={patternSelectRef}
          value={selectedPattern}
          onChange={(event) => setSelectedPattern(event.target.value)}
          className="app-input"
        >
          <option value="">Unassigned</option>
          {patterns.map((patternDefinition: PatternDefinition) => (
            <option key={patternDefinition.pattern_id} value={patternDefinition.pattern_id}>
              {patternDefinition.pattern_id} {patternDefinition.name}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="space-y-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
        <legend className="app-label px-1">Operational Design</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="app-label mb-2 block">Commercial Scope</span>
            <select value={tbq} onChange={(event) => setTbq(event.target.value as "Y" | "N")} className="app-input">
              <option value="Y">BOM eligible (TBQ=Y)</option>
              <option value="N">Technical only (TBQ=N)</option>
            </select>
            <span className="mt-1.5 block text-xs leading-5 text-[var(--color-text-muted)]">This changes BOM and pricing eligibility only; the integration remains in the technical catalog.</span>
          </label>
          <label className="block">
            <span className="app-label mb-2 block">Business Criticality</span>
            <select value={businessCriticality} onChange={(event) => setBusinessCriticality(event.target.value)} className="app-input">
              <option value="">Not assessed</option>
              <option value="Baja">Low</option>
              <option value="Media">Medium</option>
              <option value="Alta">High</option>
              <option value="Crítica">Critical</option>
            </select>
          </label>
          <label className="block">
            <span className="app-label mb-2 block">Data Classification</span>
            <select value={dataClassification} onChange={(event) => setDataClassification(event.target.value)} className="app-input">
              <option value="">Not assessed</option>
              <option value="Pública">Public</option>
              <option value="Interna">Internal</option>
              <option value="Confidencial">Confidential</option>
              <option value="Restringida">Restricted</option>
            </select>
          </label>
        </div>
        <label className="block">
          <span className="app-label mb-2 block">SLA / Target Latency</span>
          <input value={targetLatencySla} onChange={(event) => setTargetLatencySla(event.target.value)} className="app-input" placeholder="p95 under 5 seconds" />
        </label>
        <label className="block">
          <span className="app-label mb-2 block">Retention / Processing Window</span>
          <input value={retentionWindow} onChange={(event) => setRetentionWindow(event.target.value)} className="app-input" placeholder="Retain 7 days; process 22:00-02:00" />
        </label>
        <label className="block">
          <span className="app-label mb-2 block">Retry Policy</span>
          <textarea value={retryPolicy} onChange={(event) => setRetryPolicy(event.target.value)} rows={3} className="app-input" placeholder="3 attempts; exponential backoff; DLQ" />
        </label>
        <label className="block">
          <span className="app-label mb-2 block">Idempotency</span>
          <textarea value={idempotency} onChange={(event) => setIdempotency(event.target.value)} rows={3} className="app-input" placeholder="Use orderId as key; retain deduplication state for 7 days" />
        </label>
      </fieldset>

      {selectedPatternDefinition ? (
        <div
          className={[
            "rounded-2xl border p-4 text-sm",
            selectedPatternDefinition.support.certification_status === "certified"
              ? "border-emerald-200 bg-emerald-50/80 text-emerald-900 dark:border-[#30d158]/45 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]"
              : "border-amber-200 bg-amber-50/90 text-amber-900 dark:border-[#ffd60a]/45 dark:bg-[var(--color-surface-2)] dark:text-[var(--color-text-primary)]",
          ].join(" ")}
        >
          <div className="flex flex-wrap items-center gap-3">
            <PatternSupportBadge support={selectedPatternDefinition.support} />
            <p className="font-medium text-[var(--color-text-primary)]">
              {selectedPatternDefinition.pattern_id} {selectedPatternDefinition.name}
            </p>
          </div>
          <p className="mt-3 leading-6">{selectedPatternDefinition.support.summary}</p>
          {selectedPatternDefinition.when_not_to_use ? (
            <p className="mt-3 leading-6 text-[var(--color-text-secondary)]">
              <span className="font-medium text-[var(--color-text-primary)]">Anti-pattern watch:</span>{" "}
              {selectedPatternDefinition.when_not_to_use}
            </p>
          ) : null}
        </div>
      ) : null}

      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">
          Pattern Rationale
        </span>
        <textarea
          value={patternRationale}
          onChange={(event) => setPatternRationale(event.target.value)}
          rows={4}
          className="app-input"
        />
      </label>

      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Comments</span>
        <textarea
          value={comments}
          onChange={(event) => setComments(event.target.value)}
          rows={4}
          className="app-input"
        />
      </label>

      <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
        <p className="app-label">Flow Tools</p>
        <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
          The design canvas is now the source of truth for the real processing route. Save the canvas to update governed core tools and overlays for this integration.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {canvasSemantics.coreToolKeys.length > 0 ? (
            canvasSemantics.coreToolKeys.map((tool) => (
              <span key={tool} className="app-theme-chip">
                {tool}
              </span>
            ))
          ) : (
            <span className="text-sm text-[var(--color-text-muted)]">
              No flow tools are currently registered. Use the canvas below to add them.
            </span>
          )}
        </div>
        <div className="mt-3 rounded-xl bg-[var(--color-surface)] px-3 py-3 text-sm text-[var(--color-text-secondary)]">
          <p>
            <span className="font-medium text-[var(--color-text-primary)]">Processing route:</span>{" "}
            {canvasSemantics.processingSummary}
          </p>
          <p className="mt-2">
            <span className="font-medium text-[var(--color-text-primary)]">Overlays:</span>{" "}
            {canvasSemantics.overlaySummary}
          </p>
          <p className="mt-2">
            <span className="font-medium text-[var(--color-text-primary)]">Saved route status:</span>{" "}
            {canvasSemantics.hasConnectedRoute
              ? "Source and destination are connected through the designed flow."
              : "The saved canvas does not yet connect source to destination through a core route."}
          </p>
        </div>
        <p className="mt-3 text-xs text-[var(--color-text-muted)]">
          {toolOptions.length} core tool definitions and {overlayOptions.length} overlay definitions are available in governance.
        </p>
      </div>

      <ConfirmModal
        open={deleteOpen}
        title="Remove integration"
        description={`"${integration.interface_id ?? integration.interface_name ?? integration.id}" will be removed from this catalog and the project will be recalculated.`}
        confirmLabel="Remove integration"
        cancelLabel="Keep it"
        danger
        onConfirm={() => {
          setDeleteOpen(false);
          void handleDelete();
        }}
        onCancel={() => setDeleteOpen(false)}
      />
    </section>
  );
}
