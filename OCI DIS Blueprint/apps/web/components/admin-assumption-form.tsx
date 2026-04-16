"use client";

/* Versioned assumption-set creation form for admin governance pages. */

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
    oic_billing_threshold_kb: 50,
    oic_pack_size_msgs_per_hour: 5000,
    oic_byol_pack_size_msgs_per_hour: 20000,
    month_days: 31,
    oic_rest_max_payload_kb: 51200,
    oic_ftp_max_payload_kb: 51200,
    oic_kafka_max_payload_kb: 10240,
    oic_timeout_s: 300,
    streaming_partition_throughput_mb_s: 1,
    streaming_read_throughput_mb_s: 2,
    streaming_max_message_size_mb: 1,
    streaming_retention_days: 7,
    streaming_default_partitions: 200,
    functions_default_duration_ms: 2000,
    functions_default_memory_mb: 256,
    functions_default_concurrency: 1,
    functions_max_timeout_s: 300,
    functions_batch_size_records: 500,
    queue_billing_unit_kb: 64,
    queue_max_message_kb: 256,
    queue_retention_days: 7,
    queue_throughput_soft_limit_msgs_per_second: 10,
    data_integration_workspaces_per_region: 5,
    data_integration_deleted_workspace_retention_days: 15,
    raw_assumptions: {
      source_references: {
        oic_limits: "TPL - Supuestos: OCI Gen3 official service limits",
        oic_billing: "TPL - Supuestos: OIC billing message and pack guidance",
        streaming_limits: "TPL - Supuestos: OCI Streaming service limits",
        functions_limits: "TPL - Supuestos: OCI Functions operational limits",
        queue_limits: "TPL - Supuestos: OCI Queue limits and pricing unit",
        data_integration_limits: "TPL - Supuestos: OCI Data Integration regional limits",
        data_integrator_proxy_usage: "TPL - Supuestos: Data Integrator uses jobs/month proxy guidance",
      },
      service_metadata: {
        data_integrator_usage_model: "Jobs/month (proxy)",
        data_integration_compute_isolated: true,
        functions_cold_start_typical: "10-20 sec",
        functions_ram_default_per_ad: 60,
        salesforce_batch_limit_millions: 8,
        file_server_concurrent_connections: 50,
        default_record_size_bytes: 250,
        hours_per_month: 744,
      },
    },
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

      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <section className="app-card-muted p-5">
          <p className="app-label">OIC Parameters</p>
          <div className="mt-4 space-y-4">
            {[
              ["oic_billing_threshold_kb", "Billing Threshold (KB)"],
              ["oic_pack_size_msgs_per_hour", "Pack Size (msgs/hour)"],
              ["oic_byol_pack_size_msgs_per_hour", "BYOL Pack Size (msgs/hour)"],
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
                  value={form[field as EditableAssumptionField]}
                  onChange={(event) => updateNumber(field as EditableAssumptionField, Number(event.target.value))}
                  className="app-input"
                />
              </label>
            ))}
          </div>
        </section>

        <section className="app-card-muted p-5">
          <p className="app-label">Queue + Streaming</p>
          <div className="mt-4 space-y-4">
            {[
              ["queue_billing_unit_kb", "Queue Billing Unit (KB)"],
              ["queue_max_message_kb", "Queue Max Message (KB)"],
              ["queue_retention_days", "Queue Retention (days)"],
              ["queue_throughput_soft_limit_msgs_per_second", "Queue Throughput Soft Limit (msg/s)"],
              ["streaming_partition_throughput_mb_s", "Streaming Write Throughput (MB/s)"],
              ["streaming_read_throughput_mb_s", "Streaming Read Throughput (MB/s)"],
              ["streaming_max_message_size_mb", "Streaming Max Message (MB)"],
              ["streaming_retention_days", "Streaming Retention (days)"],
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

        <section className="app-card-muted p-5">
          <p className="app-label">Functions + Data Integration</p>
          <div className="mt-4 space-y-4">
            {[
              ["functions_default_duration_ms", "Functions Default Duration (ms)"],
              ["functions_default_memory_mb", "Functions Default Memory (MB)"],
              ["functions_default_concurrency", "Functions Default Concurrency"],
              ["functions_max_timeout_s", "Functions Max Timeout (seconds)"],
              ["functions_batch_size_records", "Functions Batch Size (records)"],
              ["data_integration_workspaces_per_region", "DI Workspaces per Region"],
              ["data_integration_deleted_workspace_retention_days", "DI Deleted Workspace Retention (days)"],
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
