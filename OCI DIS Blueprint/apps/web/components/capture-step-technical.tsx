"use client";

/* Step 4 of guided capture: technical sizing, patterning, live OIC estimate, and QA preview. */

import { OicEstimatePreview } from "@/components/oic-estimate-preview";
import { PatternSupportBadge } from "@/components/pattern-support-badge";
import { QaPreview } from "@/components/qa-preview";
import type { CaptureStepProps } from "@/components/capture-wizard";

export function CaptureStepTechnical({
  form,
  updateField,
  patterns,
  toolOptions,
  frequencyOptions,
  triggerTypeOptions,
  complexityOptions,
  projectId,
}: CaptureStepProps): JSX.Element {
  const selectedTools = form.core_tools ?? [];
  const selectedPatternDefinition = patterns.find((pattern) => pattern.pattern_id === form.selected_pattern) ?? null;

  function toggleTool(tool: string): void {
    const nextTools = selectedTools.includes(tool)
      ? selectedTools.filter((entry) => entry !== tool)
      : [...selectedTools, tool];
    updateField("core_tools", nextTools);
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-5 md:grid-cols-2">
        <label className="block">
          <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Trigger Type</span>
          <select
            value={form.type ?? ""}
            onChange={(event) => updateField("type", event.target.value)}
            className="app-input"
          >
            <option value="">Select trigger type</option>
            {triggerTypeOptions.map((option) => (
              <option key={option.id} value={option.value}>
                {option.value}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Frequency</span>
          <select
            value={form.frequency ?? ""}
            onChange={(event) => updateField("frequency", event.target.value)}
            className="app-input"
          >
            <option value="">Select frequency</option>
            {frequencyOptions.map((option) => (
              <option key={option.id} value={option.value}>
                {option.value}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Payload per Execution (KB)</span>
          <input
            type="number"
            min="0"
            step="0.1"
            value={form.payload_per_execution_kb ?? ""}
            onChange={(event) =>
              updateField(
                "payload_per_execution_kb",
                event.target.value === "" ? undefined : Number(event.target.value),
              )
            }
            className="app-input"
            placeholder="0.0"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Complexity</span>
          <select
            value={form.complexity ?? ""}
            onChange={(event) => updateField("complexity", event.target.value)}
            className="app-input"
          >
            <option value="">Select complexity</option>
            {complexityOptions.map((option) => (
              <option key={option.id} value={option.value}>
                {option.value}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Uncertainty</span>
          <input
            value={form.uncertainty ?? ""}
            onChange={(event) => updateField("uncertainty", event.target.value)}
            className="app-input"
            placeholder="Resolved, TBD, medium confidence…"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Pattern</span>
          <select
            value={form.selected_pattern ?? ""}
            onChange={(event) => updateField("selected_pattern", event.target.value)}
            className="app-input"
          >
            <option value="">Unassigned</option>
            {patterns.map((pattern) => (
              <option key={pattern.id} value={pattern.pattern_id}>
                {pattern.pattern_id} {pattern.name}
              </option>
            ))}
          </select>
        </label>
        <label className="block md:col-span-2">
          <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Pattern Rationale</span>
          <textarea
            value={form.pattern_rationale ?? ""}
            onChange={(event) => updateField("pattern_rationale", event.target.value)}
            rows={4}
            className="app-input"
            placeholder="Why is this the best fit for the integration?"
          />
        </label>
      </div>

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
        </div>
      ) : null}

      <fieldset className="space-y-3">
        <legend className="text-xs uppercase tracking-[0.25em] text-slate-500">Core Tools</legend>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {toolOptions.map((option) => {
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

      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <OicEstimatePreview
          projectId={projectId}
          frequency={form.frequency}
          payloadPerExecutionKb={form.payload_per_execution_kb}
        />
        <QaPreview form={form} patterns={patterns} />
      </div>
    </div>
  );
}
