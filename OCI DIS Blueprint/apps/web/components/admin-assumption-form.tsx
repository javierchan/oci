"use client";

/* Versioned assumption-set creation form for admin governance pages. */

import Link from "next/link";
import { useEffect, useState } from "react";

import type { AssumptionSet, AssumptionSetCreate } from "@/lib/types";

type AdminAssumptionFormProps = {
  initialValue: AssumptionSet | null;
  suggestedVersion: string;
  isLoading: boolean;
  error: string;
  onSubmit: (_value: AssumptionSetCreate) => void | Promise<void>;
  onCancel: () => void;
};

type EditableAssumptionField = Exclude<keyof AssumptionSetCreate, "version" | "raw_assumptions">;

function blankAssumption(version: string): AssumptionSetCreate {
  return {
    version,
    month_days: 31,
    streaming_default_partitions: 200,
    functions_default_duration_ms: 2000,
    functions_default_memory_mb: 256,
    functions_default_concurrency: 1,
    functions_batch_size_records: 500,
    queue_throughput_soft_limit_msgs_per_second: 10,
    raw_assumptions: {},
  };
}

export function AdminAssumptionForm({
  initialValue,
  suggestedVersion,
  isLoading,
  error,
  onSubmit,
  onCancel,
}: AdminAssumptionFormProps): JSX.Element {
  const [form, setForm] = useState<AssumptionSetCreate>(blankAssumption(suggestedVersion));
  const [validationError, setValidationError] = useState<string>("");

  useEffect(() => {
    if (initialValue) {
      setForm({ ...initialValue, version: suggestedVersion || initialValue.version });
      return;
    }
    setForm(blankAssumption(suggestedVersion));
  }, [initialValue, suggestedVersion]);

  function updateNumber(field: EditableAssumptionField, value: number): void {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(): Promise<void> {
    if (!form.version.trim()) {
      setValidationError("Version is required.");
      return;
    }
    setValidationError("");
    await onSubmit({
      ...form,
      version: form.version.trim(),
    });
  }

  return (
    <section className="app-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="app-label">Assumption Version</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">New Assumption Set</h2>
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="app-button-secondary px-4 py-2"
        >
          Close
        </button>
      </div>

      <label className="mt-6 block">
        <span className="app-label mb-2 block">Version</span>
        <input
          value={form.version}
          onChange={(event) => setForm((current) => ({ ...current, version: event.target.value }))}
          placeholder={suggestedVersion}
          className="app-input"
        />
      </label>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-y border-[var(--color-border)] py-4 text-sm">
        <div>
          <p className="font-medium text-[var(--color-text-primary)]">Service limits are managed separately</p>
          <p className="mt-1 text-[var(--color-text-secondary)]">
            Assumptions capture client workload inputs. Oracle limits and interoperability rules come from Service Product Library.
          </p>
        </div>
        <Link href="/admin/services" className="app-link">Open Service Products</Link>
      </div>

      <div className="mt-6 grid gap-8 xl:grid-cols-2">
        <section>
          <p className="app-label">Business Calendar + Messaging</p>
          <div className="mt-4 space-y-4">
            {[
              ["month_days", "Month Days"],
              ["queue_throughput_soft_limit_msgs_per_second", "Queue Throughput Soft Limit (msg/s)"],
              ["streaming_default_partitions", "Streaming Default Partitions"],
            ].map(([field, label]) => (
              <label key={field} className="block">
                <span className="app-label mb-2 block">{label}</span>
                <input
                  type="number"
                  step="0.000001"
                  value={form[field as EditableAssumptionField]}
                  onChange={(event) => updateNumber(field as EditableAssumptionField, Number(event.target.value))}
                  className="app-input"
                />
              </label>
            ))}
          </div>
        </section>

        <section>
          <p className="app-label">Workload Defaults</p>
          <div className="mt-4 space-y-4">
            {[
              ["functions_default_duration_ms", "Functions Default Duration (ms)"],
              ["functions_default_memory_mb", "Functions Default Memory (MB)"],
              ["functions_default_concurrency", "Functions Default Concurrency"],
              ["functions_batch_size_records", "Functions Batch Size (records)"],
            ].map(([field, label]) => (
              <label key={field} className="block">
                <span className="app-label mb-2 block">{label}</span>
                <input
                  type="number"
                  step="0.000001"
                  value={form[field as EditableAssumptionField]}
                  onChange={(event) => updateNumber(field as EditableAssumptionField, Number(event.target.value))}
                  className="app-input"
                />
              </label>
            ))}
          </div>
        </section>
      </div>

      {validationError ? <p className="mt-4 text-sm text-rose-600">{validationError}</p> : null}
      {error ? <p className="mt-2 text-sm text-rose-600">{error}</p> : null}

      <div className="mt-6 flex flex-wrap justify-end gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="app-button-secondary"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => {
            void handleSubmit();
          }}
          disabled={isLoading}
          className="app-button-primary"
        >
          {isLoading ? "Saving…" : "Create Version"}
        </button>
      </div>
    </section>
  );
}
