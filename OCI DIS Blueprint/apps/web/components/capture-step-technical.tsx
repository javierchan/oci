"use client";

/* Step 4 of guided capture: technical sizing, patterning, live OIC estimate, and QA preview. */

import { OicEstimatePreview } from "@/components/oic-estimate-preview";
import { PatternSupportBadge } from "@/components/pattern-support-badge";
import { QaPreview } from "@/components/qa-preview";
import { displayComplexity, displayUiValue } from "@/lib/format";
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
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="block">
          <span className="app-label mb-2 block">Trigger Type</span>
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
          <span className="app-label mb-2 block">Frequency</span>
          <select
            value={form.frequency ?? ""}
            onChange={(event) => updateField("frequency", event.target.value)}
            className="app-input"
          >
            <option value="">Select frequency</option>
            {frequencyOptions.map((option) => (
              <option key={option.id} value={option.value}>
                {displayUiValue(option.value)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="app-label mb-2 block">Payload per Execution (KB)</span>
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
          <span className="app-label mb-2 block">Complexity</span>
          <select
            value={form.complexity ?? ""}
            onChange={(event) => updateField("complexity", event.target.value)}
            className="app-input"
          >
            <option value="">Select complexity</option>
            {complexityOptions.map((option) => (
              <option key={option.id} value={option.value}>
                {displayComplexity(option.value)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="app-label mb-2 block">Uncertainty</span>
          <input
            value={form.uncertainty ?? ""}
            onChange={(event) => updateField("uncertainty", event.target.value)}
            className="app-input"
            placeholder="Resolved, TBD, medium confidence…"
          />
        </label>
        <label className="block">
          <span className="app-label mb-2 block">Business Criticality</span>
          <select value={form.business_criticality ?? ""} onChange={(event) => updateField("business_criticality", event.target.value)} className="app-input">
            <option value="">Not assessed</option>
            <option value="Baja">Low</option>
            <option value="Media">Medium</option>
            <option value="Alta">High</option>
            <option value="Crítica">Critical</option>
          </select>
        </label>
        <label className="block">
          <span className="app-label mb-2 block">SLA / Target Latency</span>
          <input value={form.target_latency_sla ?? ""} onChange={(event) => updateField("target_latency_sla", event.target.value)} className="app-input" placeholder="p95 under 5 seconds" />
        </label>
        <label className="block">
          <span className="app-label mb-2 block">Data Classification</span>
          <select value={form.data_security_classification ?? ""} onChange={(event) => updateField("data_security_classification", event.target.value)} className="app-input">
            <option value="">Not assessed</option>
            <option value="Pública">Public</option>
            <option value="Interna">Internal</option>
            <option value="Confidencial">Confidential</option>
            <option value="Restringida">Restricted</option>
          </select>
        </label>
        <label className="block md:col-span-2">
          <span className="app-label mb-2 block">Retention / Processing Window</span>
          <input value={form.retention_processing_window ?? ""} onChange={(event) => updateField("retention_processing_window", event.target.value)} className="app-input" placeholder="Retain 7 days; process 22:00-02:00" />
        </label>
        <label className="block md:col-span-2">
          <span className="app-label mb-2 block">Retry Policy</span>
          <textarea value={form.retry_policy ?? ""} onChange={(event) => updateField("retry_policy", event.target.value)} rows={3} className="app-input" placeholder="3 attempts; exponential backoff; DLQ" />
        </label>
        <label className="block md:col-span-2">
          <span className="app-label mb-2 block">Idempotency</span>
          <textarea value={form.idempotency ?? ""} onChange={(event) => updateField("idempotency", event.target.value)} rows={3} className="app-input" placeholder="Use orderId as deduplication key" />
        </label>
        <label className="block">
          <span className="app-label mb-2 block">Pattern</span>
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
          <span className="app-label mb-2 block">Pattern Rationale</span>
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
            selectedPatternDefinition.support.certification_status === "certified"
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
        <legend className="app-label">Core Tools</legend>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {toolOptions.map((option) => {
            const checked = selectedTools.includes(option.value);
            return (
              <label
                key={option.id}
                className={[
                  "flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition",
                  checked
                    ? "border-[var(--color-accent)] bg-[var(--color-surface)] text-[var(--color-text-primary)] shadow-[0_0_0_1px_var(--color-accent)]"
                    : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:border-[var(--color-accent)]",
                ].join(" ")}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleTool(option.value)}
                  className="h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-accent)]"
                />
                <span>{option.value}</span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
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
