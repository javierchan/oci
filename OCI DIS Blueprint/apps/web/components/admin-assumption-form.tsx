"use client";

/* Versioned assumption-set creation form for admin governance pages. */

import { useEffect, useState } from "react";

import type { AssumptionSet, AssumptionSetCreate } from "@/lib/types";

type AdminAssumptionFormProps = {
  initialValue: AssumptionSet | null;
  suggestedVersion: string;
  isLoading: boolean;
  error: string;
  onSubmit: (value: AssumptionSetCreate) => void | Promise<void>;
  onCancel: () => void;
};

function blankAssumption(version: string): AssumptionSetCreate {
  return {
    version,
    oic_billing_threshold_kb: 50,
    oic_pack_size_msgs_per_hour: 5000,
    month_days: 30,
    oic_rest_max_payload_kb: 50000,
    oic_ftp_max_payload_kb: 50000,
    oic_kafka_max_payload_kb: 10000,
    oic_timeout_s: 300,
    streaming_partition_throughput_mb_s: 1,
    functions_default_duration_ms: 200,
    functions_default_memory_mb: 256,
    functions_default_concurrency: 1,
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

  function updateNumber<K extends keyof AssumptionSetCreate>(field: K, value: number): void {
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

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="app-card-muted p-5">
          <p className="app-label">OIC Parameters</p>
          <div className="mt-4 space-y-4">
            {[
              ["oic_billing_threshold_kb", "Billing Threshold (KB)"],
              ["oic_pack_size_msgs_per_hour", "Pack Size (msgs/hour)"],
              ["oic_rest_max_payload_kb", "REST Max Payload (KB)"],
              ["oic_ftp_max_payload_kb", "FTP Max Payload (KB)"],
              ["oic_kafka_max_payload_kb", "Kafka Max Payload (KB)"],
              ["oic_timeout_s", "Timeout (seconds)"],
              ["month_days", "Month Days"],
            ].map(([field, label]) => (
              <label key={field} className="block">
                <span className="app-label mb-2 block">{label}</span>
                <input
                  type="number"
                  step="0.000001"
                  value={form[field as keyof AssumptionSetCreate]}
                  onChange={(event) =>
                    updateNumber(field as keyof AssumptionSetCreate, Number(event.target.value))
                  }
                  className="app-input"
                />
              </label>
            ))}
          </div>
        </section>

        <section className="app-card-muted p-5">
          <p className="app-label">OCI Services Parameters</p>
          <div className="mt-4 space-y-4">
            {[
              ["streaming_partition_throughput_mb_s", "Streaming Partition Throughput (MB/s)"],
              ["functions_default_duration_ms", "Functions Default Duration (ms)"],
              ["functions_default_memory_mb", "Functions Default Memory (MB)"],
              ["functions_default_concurrency", "Functions Default Concurrency"],
            ].map(([field, label]) => (
              <label key={field} className="block">
                <span className="app-label mb-2 block">{label}</span>
                <input
                  type="number"
                  step="0.000001"
                  value={form[field as keyof AssumptionSetCreate]}
                  onChange={(event) =>
                    updateNumber(field as keyof AssumptionSetCreate, Number(event.target.value))
                  }
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
