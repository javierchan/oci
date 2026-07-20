"use client";

/** Guided, approval-gated mapping review for an external workbook import. */

import { useMemo, useState } from "react";
import { Bot, CheckCircle2, FileWarning, Save, ShieldCheck } from "lucide-react";

import { emitToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import type { ImportBatch, ImportMappingContract, ImportMappingField } from "@/lib/types";

type ImportMappingReviewProps = {
  batch: ImportBatch;
  projectId: string;
  onBatchChange: (_batch: ImportBatch) => void;
};

const EVIDENCE_ONLY = "evidence_only";

const TARGET_FIELDS: Array<{ value: string; label: string }> = [
  { value: EVIDENCE_ONLY, label: "Evidence only (do not operationalize)" },
  { value: "seq_number", label: "Sequence number" },
  { value: "interface_id", label: "Integration ID" },
  { value: "brand", label: "Business unit / brand" },
  { value: "business_process", label: "Business process" },
  { value: "interface_name", label: "Integration name" },
  { value: "description", label: "Description" },
  { value: "business_criticality", label: "Business criticality" },
  { value: "base", label: "Base" },
  { value: "interface_status", label: "Interface status" },
  { value: "status", label: "Status" },
  { value: "mapping_status", label: "Mapping status" },
  { value: "complexity", label: "Complexity" },
  { value: "initial_scope", label: "Initial scope" },
  { value: "frequency", label: "Frequency" },
  { value: "is_real_time", label: "Real-time flag" },
  { value: "type", label: "Integration type" },
  { value: "trigger_type", label: "Trigger type" },
  { value: "target_latency_sla", label: "Target latency / SLA" },
  { value: "response_size_kb", label: "Response size (KB)" },
  { value: "payload_per_execution_kb", label: "Payload per execution (KB)" },
  { value: "is_fan_out", label: "Fan-out flag" },
  { value: "fan_out_targets", label: "Fan-out destinations" },
  { value: "calendarization", label: "Calendarization" },
  { value: "source_system", label: "Source system" },
  { value: "source_technology", label: "Source technology" },
  { value: "source_api_reference", label: "Source API reference" },
  { value: "source_owner", label: "Source owner" },
  { value: "destination_system", label: "Destination system" },
  { value: "destination_technology_1", label: "Destination technology 1" },
  { value: "destination_technology_2", label: "Destination technology 2" },
  { value: "destination_owner", label: "Destination owner" },
  { value: "data_security_classification", label: "Data / security classification" },
  { value: "selected_pattern", label: "Integration pattern" },
  { value: "pattern_rationale", label: "Pattern rationale" },
  { value: "comments", label: "Comments" },
  { value: "retry_policy", label: "Retry policy" },
  { value: "idempotency", label: "Idempotency" },
  { value: "retention_processing_window", label: "Retention / processing window" },
  { value: "core_tools", label: "Core tools" },
  { value: "additional_tools_overlays", label: "Architectural overlays" },
  { value: "tbq", label: "To be quoted (TBQ)" },
  { value: "owner", label: "Owner" },
  { value: "identified_in", label: "Identified in" },
  { value: "slide", label: "Slide reference" },
];

function contractFrom(batch: ImportBatch): ImportMappingContract {
  return batch.mapping_contract ?? {
    version: "1.0.0",
    source_kind: "external_workbook",
    fields: [],
    questions: [],
    answers: {},
  };
}

function initialFieldTargets(fields: ImportMappingField[]): Record<string, string> {
  return Object.fromEntries(fields.map((field) => [field.source_header, field.target_field]));
}

export function ImportMappingReview({ batch, projectId, onBatchChange }: ImportMappingReviewProps): JSX.Element {
  const contract = contractFrom(batch);
  const fields = contract.fields ?? [];
  const questions = contract.questions ?? [];
  const formulaColumns = contract.formula_columns ?? [];
  const [targets, setTargets] = useState<Record<string, string>>(() => initialFieldTargets(fields));
  const [answers, setAnswers] = useState<Record<string, string>>(contract.answers ?? {});
  const [saveProfile, setSaveProfile] = useState(false);
  const [profileName, setProfileName] = useState("");
  const [busy, setBusy] = useState<"save" | "approve" | "">("");

  const mappedCount = useMemo(
    () => Object.values(targets).filter((target) => target !== EVIDENCE_ONLY).length,
    [targets],
  );
  const unansweredCount = questions.filter((question) => question.required && !answers[question.id]).length;
  const payload = () => ({
    fields: fields.map((field) => ({
      source_header: field.source_header,
      target_field: targets[field.source_header] ?? EVIDENCE_ONLY,
    })),
    answers,
  });

  async function saveReview(): Promise<void> {
    setBusy("save");
    try {
      const updated = await api.saveImportMappingReview(projectId, batch.id, payload());
      onBatchChange(updated);
      emitToast("success", "Mapping draft saved. The workbook remains safely staged.");
    } catch (error) {
      emitToast("error", error instanceof Error ? error.message : "Unable to save mapping review.");
    } finally {
      setBusy("");
    }
  }

  async function approveReview(): Promise<void> {
    setBusy("approve");
    try {
      const updated = await api.approveImportMappingReview(projectId, batch.id, {
        ...payload(),
        save_profile: saveProfile,
        profile_name: profileName.trim() || undefined,
      });
      onBatchChange(updated);
      emitToast("success", "Mapping approved. Catalog materialization is now queued.");
    } catch (error) {
      emitToast("error", error instanceof Error ? error.message : "Unable to approve mapping review.");
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="app-card border-[var(--color-accent)]/40 p-5 sm:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="app-kicker">External workbook mapping review</p>
          <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">Turn client evidence into governed data</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            This workbook is preserved, but nothing has reached Catalog, QA, topology, or BOM. Confirm what each
            source column means before you approve a one-way materialization.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="app-theme-chip">{fields.length} source columns</span>
          <span className="app-theme-chip">{mappedCount} operationalized</span>
          <span className="app-theme-chip">{unansweredCount} decisions open</span>
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <article className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
          <p className="app-label">1. Inspect</p>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">Samples remain source evidence. They do not become App values until you map them.</p>
        </article>
        <article className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
          <p className="app-label">2. Decide</p>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">Choose one governed target, or keep a client-only column as evidence.</p>
        </article>
        <article className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
          <p className="app-label">3. Approve</p>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">Only an explicit approval releases eligible integrations into the governed workflow.</p>
        </article>
      </div>

      {formulaColumns.length > 0 ? (
        <section className="mt-6 rounded-lg border border-[var(--color-qa-revisar-border)] bg-[var(--color-qa-revisar-bg)] p-4 sm:p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <FileWarning className="h-4 w-4 text-[var(--color-qa-revisar-text)]" aria-hidden="true" />
                <h3 className="font-semibold text-[var(--color-text-primary)]">Formula evidence found</h3>
              </div>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
                The App did not execute these formulas. Their expressions and cached workbook values are preserved for review,
                while the source inputs remain the only candidates for governed mapping.
              </p>
            </div>
            <span className="app-theme-chip shrink-0">{formulaColumns.length} formula-bearing columns</span>
          </div>
          <div className="mt-4 grid gap-3 xl:grid-cols-2">
            {formulaColumns.map((column) => (
              <article key={column.source_index} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-[var(--color-text-primary)]">{column.source_header}</p>
                    <p className="mt-1 text-xs uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
                      {column.classification.replaceAll("_", " ")} · {column.operational_policy === "evidence_only" ? "column protected" : "formula rows protected"}
                    </p>
                  </div>
                  <span className="app-theme-chip">{column.formula_count} formulas</span>
                </div>
                <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">{column.rationale}</p>
                <p className="mt-3 break-words rounded-md bg-[var(--color-surface-2)] px-3 py-2 font-mono text-xs leading-5 text-[var(--color-text-muted)]">
                  {column.sample_formulas[0] ?? "Formula retained in source evidence"}
                </p>
                <p className="mt-2 text-xs text-[var(--color-text-muted)]">
                  Cached values: {column.cached_value_count} available · {column.cached_error_count} errors
                </p>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {questions.length > 0 ? (
        <div className="mt-6 rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
          <div className="flex items-center gap-2">
            <Bot className="h-4 w-4 text-amber-700 dark:text-amber-300" aria-hidden="true" />
            <h3 className="font-semibold text-[var(--color-text-primary)]">Import Correction Agent guidance</h3>
          </div>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            These questions prevent a plausible-looking import from misrepresenting operational demand or cost.
          </p>
          <div className="mt-4 space-y-4">
            {questions.map((question) => (
              <fieldset key={question.id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                <legend className="px-1 text-sm font-semibold text-[var(--color-text-primary)]">{question.prompt}</legend>
                <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{question.reason}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {question.options.map((option) => (
                    <label key={option.value} className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-text-primary)] has-[:checked]:border-[var(--color-accent)] has-[:checked]:bg-[var(--color-accent-soft)]">
                      <input
                        type="radio"
                        name={question.id}
                        value={option.value}
                        checked={answers[question.id] === option.value}
                        onChange={() => setAnswers((current) => ({ ...current, [question.id]: option.value }))}
                      />
                      {option.label}
                    </label>
                  ))}
                </div>
              </fieldset>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-6 overflow-x-auto rounded-lg border border-[var(--color-border)]">
        <table className="min-w-[760px] w-full text-left">
          <thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-[0.14em] text-[var(--color-text-muted)]">
            <tr><th className="px-4 py-3">Source column</th><th className="px-4 py-3">Examples</th><th className="px-4 py-3">Use in the App</th></tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {fields.map((field) => (
              <tr key={field.source_index} className="align-top">
                <td className="px-4 py-4"><p className="font-medium text-[var(--color-text-primary)]">{field.source_header}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">Proposed: {TARGET_FIELDS.find((target) => target.value === field.proposed_target)?.label ?? "Evidence only"}</p></td>
                <td className="max-w-xs px-4 py-4 text-sm leading-5 text-[var(--color-text-secondary)]">{field.sample_values.length ? field.sample_values.join(" · ") : "No sample value"}</td>
                <td className="px-4 py-4">
                  <select
                    value={targets[field.source_header] ?? EVIDENCE_ONLY}
                    onChange={(event) => setTargets((current) => ({ ...current, [field.source_header]: event.target.value }))}
                    className="app-input min-w-64"
                    disabled={field.formula_policy === "evidence_only"}
                  >
                    <option value={EVIDENCE_ONLY}>{field.formula_policy === "evidence_only" ? "Formula evidence only (protected)" : "Evidence only (do not operationalize)"}</option>
                    {field.formula_policy === "evidence_only" ? null : TARGET_FIELDS.filter((option) => option.value !== EVIDENCE_ONLY).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6 flex flex-col gap-4 border-t border-[var(--color-border)] pt-5 lg:flex-row lg:items-end lg:justify-between">
        <label className="flex max-w-xl items-start gap-3 text-sm text-[var(--color-text-secondary)]">
          <input type="checkbox" checked={saveProfile} onChange={(event) => setSaveProfile(event.target.checked)} className="mt-1" />
          <span><strong className="text-[var(--color-text-primary)]">Save as a reusable project mapping</strong><br />Use only for future workbooks with this exact header fingerprint. It will never apply outside this project.</span>
        </label>
        {saveProfile ? <input value={profileName} onChange={(event) => setProfileName(event.target.value)} placeholder="Mapping profile name" className="app-input w-full lg:w-72" /> : null}
        <div className="flex flex-wrap gap-3">
          <button type="button" onClick={() => void saveReview()} disabled={busy !== ""} className="app-button-secondary"><Save className="h-4 w-4" aria-hidden="true" />{busy === "save" ? "Saving" : "Save draft"}</button>
          <button type="button" onClick={() => void approveReview()} disabled={busy !== ""} className="app-button-primary"><ShieldCheck className="h-4 w-4" aria-hidden="true" />{busy === "approve" ? "Approving" : "Approve & materialize"}</button>
        </div>
      </div>
      <p className="mt-3 flex items-center gap-2 text-xs leading-5 text-[var(--color-text-muted)]"><CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />Approval creates an audit event and queues materialization; it never overwrites the original workbook evidence.</p>
    </section>
  );
}
