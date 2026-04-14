"use client";

/* Architect-facing patch form for pattern, rationale, comments, and core tools. */

import { useRouter, useSearchParams } from "next/navigation";
import { startTransition, useEffect, useRef, useState } from "react";

import { IntegrationCanvas } from "@/components/integration-canvas";
import { PatternBadge } from "@/components/pattern-badge";
import { QaBadge } from "@/components/qa-badge";
import { api } from "@/lib/api";
import type { DictionaryOption, Integration, IntegrationPatch, PatternDefinition } from "@/lib/types";

type IntegrationPatchFormProps = {
  projectId: string;
  integration: Integration;
  patterns: PatternDefinition[];
  toolOptions: DictionaryOption[];
};

type PatternCategory = "SÍNCRONO" | "ASÍNCRONO" | "SÍNCRONO + ASÍNCRONO";

function parseCoreTools(value: string | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((entry: string) => entry.trim())
    .filter(Boolean);
}

function normalizePatternCategory(value: string | null | undefined): PatternCategory | null {
  if (value === "SÍNCRONO" || value === "ASÍNCRONO" || value === "SÍNCRONO + ASÍNCRONO") {
    return value;
  }
  return null;
}

export function IntegrationPatchForm({
  projectId,
  integration,
  patterns,
  toolOptions,
}: IntegrationPatchFormProps): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const patternSelectRef = useRef<HTMLSelectElement | null>(null);
  const [currentIntegration, setCurrentIntegration] = useState<Integration>(integration);
  const [selectedPattern, setSelectedPattern] = useState<string>(integration.selected_pattern ?? "");
  const [patternRationale, setPatternRationale] = useState<string>(integration.pattern_rationale ?? "");
  const [comments, setComments] = useState<string>(integration.comments ?? "");
  const [selectedTools, setSelectedTools] = useState<string[]>(parseCoreTools(integration.core_tools));
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
  const activePatternId = selectedPattern || null;
  const activePatternDefinition = activePatternId ? patternMap.get(activePatternId) ?? null : null;

  useEffect(() => {
    if (searchParams.get("focus") === "patch") {
      patternSelectRef.current?.focus();
    }
  }, [searchParams]);

  function toggleTool(tool: string): void {
    setSelectedTools((current: string[]) =>
      current.includes(tool)
        ? current.filter((entry: string) => entry !== tool)
        : [...current, tool],
    );
  }

  async function handleSave(): Promise<void> {
    setSaving(true);
    setError("");
    setStatusMessage("");

    const payload: IntegrationPatch = {
      selected_pattern: selectedPattern || undefined,
      pattern_rationale: patternRationale || undefined,
      comments: comments || undefined,
      core_tools: selectedTools,
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
    <section id="patch-form" className="app-card space-y-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="app-label">Architect Patch</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            Assign pattern and governed tools
          </h2>
        </div>
        <QaBadge status={currentIntegration.qa_status} />
      </div>

      <div className="app-card-muted p-4">
        <p className="app-label">Current Pattern</p>
        <div className="mt-3">
          <PatternBadge
            patternId={currentIntegration.selected_pattern}
            name={
              currentIntegration.selected_pattern
                ? patternMap.get(currentIntegration.selected_pattern)?.name ?? null
                : null
            }
            category={
              currentIntegration.selected_pattern
                ? patternMap.get(currentIntegration.selected_pattern)?.category ?? null
                : null
            }
          />
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

      <fieldset className="space-y-3">
        <legend className="text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Core Tools</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {toolOptions.map((option: DictionaryOption) => {
            const checked = selectedTools.includes(option.value);
            return (
              <label
                key={option.id}
                className={[
                  "flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition",
                  checked
                    ? "border-[var(--color-accent)] bg-[var(--color-surface)] text-[var(--color-text-primary)]"
                    : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:border-[var(--color-accent)]",
                ].join(" ")}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleTool(option.value)}
                  className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                />
                <span>{option.value}</span>
              </label>
            );
          })}
        </div>
      </fieldset>

      {integration.source_system ? (
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-[var(--color-text-secondary)]">
            Integration Design Canvas
          </h3>
          <IntegrationCanvas
            sourceSystem={integration.source_system}
            sourceTechnology={integration.source_technology}
            destinationSystem={integration.destination_system}
            destinationTechnology={integration.destination_technology_1}
            selectedPattern={activePatternId}
            coreTools={selectedTools}
            payloadKb={integration.payload_per_execution_kb}
            frequency={integration.frequency}
            patternCategory={normalizePatternCategory(activePatternDefinition?.category)}
          />
        </div>
      ) : null}

      {currentIntegration.qa_reasons.length > 0 ? (
        <section className="rounded-[1.5rem] border border-[var(--color-qa-revisar-border)] bg-[var(--color-qa-revisar-bg)] p-4">
          <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-qa-revisar-text)]">QA Reasons</p>
          <ul className="mt-3 space-y-2 text-sm text-[var(--color-text-primary)]">
            {currentIntegration.qa_reasons.map((reason: string) => (
              <li key={reason}>• {reason}</li>
            ))}
          </ul>
        </section>
      ) : null}

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
    </section>
  );
}
