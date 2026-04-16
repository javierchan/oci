"use client";

/* Architect-facing patch form for pattern, rationale, comments, and core tools. */

import { useRouter, useSearchParams } from "next/navigation";
import { startTransition, useEffect, useMemo, useRef, useState } from "react";

import { PatternBadge } from "@/components/pattern-badge";
import { PatternSupportBadge } from "@/components/pattern-support-badge";
import { QaBadge } from "@/components/qa-badge";
import { api } from "@/lib/api";
import { deriveCanvasSemantics, parseCanvasState } from "@/lib/canvas-governance";
import type { DictionaryOption, Integration, IntegrationPatch, PatternDefinition } from "@/lib/types";

type IntegrationPatchFormProps = {
  projectId: string;
  integration: Integration;
  patterns: PatternDefinition[];
  toolOptions: DictionaryOption[];
  overlayOptions: DictionaryOption[];
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
}: IntegrationPatchFormProps): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const patternSelectRef = useRef<HTMLSelectElement | null>(null);
  const [currentIntegration, setCurrentIntegration] = useState<Integration>(integration);
  const [selectedPattern, setSelectedPattern] = useState<string>(integration.selected_pattern ?? "");
  const [patternRationale, setPatternRationale] = useState<string>(integration.pattern_rationale ?? "");
  const [comments, setComments] = useState<string>(integration.comments ?? "");
  const [saving, setSaving] = useState<boolean>(false);
  const [deleting, setDeleting] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [error, setError] = useState<string>("");

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
        combinations: [],
        selectedPattern: currentIntegration.selected_pattern,
      }),
    [currentIntegration.selected_pattern, overlayOptions, savedCanvasState.edges, savedCanvasState.nodes],
  );

  useEffect(() => {
    if (searchParams.get("focus") === "patch") {
      patternSelectRef.current?.focus();
    }
  }, [searchParams]);

  async function handleSave(): Promise<void> {
    setSaving(true);
    setError("");
    setStatusMessage("");

    const payload: IntegrationPatch = {
      selected_pattern: selectedPattern || undefined,
      pattern_rationale: patternRationale || undefined,
      comments: comments || undefined,
    };

    try {
      const updated = await api.patchIntegration(projectId, integration.id, payload);
      setCurrentIntegration(updated);
      setStatusMessage("Saved to catalog and recalculated where required.");
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to save changes.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(): Promise<void> {
    const label = integration.interface_id ?? integration.interface_name ?? integration.id;
    const confirmed = window.confirm(
      `Remove integration "${label}" from this catalog and recalculate the project?`,
    );
    if (!confirmed) {
      return;
    }

    setDeleting(true);
    setError("");
    setStatusMessage("");
    try {
      await api.deleteIntegration(projectId, integration.id);
      router.push(`/projects/${projectId}/catalog`);
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to remove integration.");
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

      <div className="flex flex-wrap items-center gap-4">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || deleting}
          className="app-button-primary"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={() => {
            void handleDelete();
          }}
          disabled={saving || deleting}
          className="inline-flex items-center justify-center rounded-full border border-rose-200 bg-rose-50 px-5 py-3 text-sm font-semibold text-rose-700 transition hover:border-rose-300 hover:bg-rose-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400"
        >
          {deleting ? "Removing…" : "Remove Integration"}
        </button>
        {statusMessage ? <p className="text-sm text-emerald-600">{statusMessage}</p> : null}
        {error ? <p className="text-sm text-rose-600">{error}</p> : null}
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

      {selectedPatternDefinition ? (
        <div
          className={[
            "rounded-2xl border p-4 text-sm",
            selectedPatternDefinition.support.parity_ready
              ? "border-emerald-200 bg-emerald-50/80 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200"
              : "border-amber-200 bg-amber-50/90 text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200",
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

    </section>
  );
}
