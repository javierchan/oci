"use client";

/* Architect-facing patch form for pattern, rationale, comments, and core tools. */

import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";

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
}: IntegrationPatchFormProps): JSX.Element {
  const router = useRouter();
  const [currentIntegration, setCurrentIntegration] = useState<Integration>(integration);
  const [selectedPattern, setSelectedPattern] = useState<string>(integration.selected_pattern ?? "");
  const [patternRationale, setPatternRationale] = useState<string>(integration.pattern_rationale ?? "");
  const [comments, setComments] = useState<string>(integration.comments ?? "");
  const [selectedTools, setSelectedTools] = useState<string[]>(parseCoreTools(integration.core_tools));
  const [saving, setSaving] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [error, setError] = useState<string>("");

  const patternMap = new Map<string, string>(
    patterns.map((patternDefinition: PatternDefinition) => [
      patternDefinition.pattern_id,
      patternDefinition.name,
    ]),
  );

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

  return (
    <section className="space-y-6 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Architect Patch</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">
            Assign pattern and governed tools
          </h2>
        </div>
        <QaBadge status={currentIntegration.qa_status} />
      </div>

      <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
        <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Current Pattern</p>
        <div className="mt-3">
          <PatternBadge
            patternId={currentIntegration.selected_pattern}
            name={
              currentIntegration.selected_pattern
                ? patternMap.get(currentIntegration.selected_pattern) ?? null
                : null
            }
          />
        </div>
      </div>

      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Pattern</span>
        <select
          value={selectedPattern}
          onChange={(event) => setSelectedPattern(event.target.value)}
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
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
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">
          Pattern Rationale
        </span>
        <textarea
          value={patternRationale}
          onChange={(event) => setPatternRationale(event.target.value)}
          rows={4}
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
        />
      </label>

      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Comments</span>
        <textarea
          value={comments}
          onChange={(event) => setComments(event.target.value)}
          rows={4}
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
        />
      </label>

      <fieldset className="space-y-3">
        <legend className="text-xs uppercase tracking-[0.25em] text-slate-500">Core Tools</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {toolOptions.map((option: DictionaryOption) => {
            const checked = selectedTools.includes(option.value);
            return (
              <label
                key={option.id}
                className={[
                  "flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition",
                  checked
                    ? "border-sky-300 bg-sky-50 text-slate-950"
                    : "border-slate-200 bg-white text-slate-700 hover:border-slate-300",
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

      {currentIntegration.qa_reasons.length > 0 ? (
        <section className="rounded-[1.5rem] border border-amber-200 bg-amber-50 p-4">
          <p className="text-xs uppercase tracking-[0.25em] text-amber-700">QA Reasons</p>
          <ul className="mt-3 space-y-2 text-sm text-amber-900">
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
          disabled={saving}
          className="inline-flex items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {saving ? "Saving…" : "Save"}
        </button>
        {statusMessage ? <p className="text-sm text-emerald-600">{statusMessage}</p> : null}
        {error ? <p className="text-sm text-rose-600">{error}</p> : null}
      </div>
    </section>
  );
}
