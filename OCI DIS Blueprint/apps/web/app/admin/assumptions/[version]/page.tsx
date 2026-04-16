"use client";

/* Assumption version detail page with current usage context and default promotion. */

import Link from "next/link";
import { useEffect, useState } from "react";

import { Breadcrumb } from "@/components/breadcrumb";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { AssumptionSet, Project, VolumetrySnapshot } from "@/lib/types";

type AdminAssumptionDetailPageProps = {
  params: {
    version: string;
  };
};

type ProjectUsage = {
  project: Project;
  snapshot: VolumetrySnapshot | null;
};

type MetadataValue = string | number | boolean;

const SERVICE_METADATA_LABELS: Record<string, string> = {
  data_integrator_usage_model: "Data Integrator usage model",
  data_integration_compute_isolated: "DI isolated compute per workspace",
  functions_cold_start_typical: "Functions cold start typical",
  functions_ram_default_per_ad: "Functions RAM default per AD",
  salesforce_batch_limit_millions: "Salesforce batch limit (millions)",
  file_server_concurrent_connections: "File Server concurrent connections",
  default_record_size_bytes: "Default record size (bytes)",
  hours_per_month: "Hours per month",
};

function readMetadataRecord(
  assumptions: Record<string, unknown> | undefined,
  key: string,
): Record<string, MetadataValue> {
  const candidate = assumptions?.[key];
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
    return {};
  }

  const entries = Object.entries(candidate);
  return entries.reduce<Record<string, MetadataValue>>((accumulator, [entryKey, value]) => {
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      accumulator[entryKey] = value;
    }
    return accumulator;
  }, {});
}

export default function AdminAssumptionDetailPage({
  params,
}: AdminAssumptionDetailPageProps): JSX.Element {
  const [assumption, setAssumption] = useState<AssumptionSet | null>(null);
  const [usages, setUsages] = useState<ProjectUsage[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    async function load(): Promise<void> {
      setLoading(true);
      try {
        const [assumptionResponse, projects] = await Promise.all([
          api.getAssumption(params.version),
          api.listProjects(),
        ]);
        const snapshotPairs = await Promise.all(
          projects.projects.map(async (project) => {
            const snapshots = await api.listSnapshots(project.id);
            return {
              project,
              snapshot: snapshots.snapshots[0] ?? null,
            };
          }),
        );
        if (!cancelled) {
          setAssumption(assumptionResponse);
          setUsages(
            snapshotPairs.filter(
              (entry) => entry.snapshot?.assumption_set_version === assumptionResponse.version,
            ),
          );
          setError("");
        }
      } catch (caughtError) {
        if (!cancelled) {
          setError(caughtError instanceof Error ? caughtError.message : "Unable to load assumption details.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [params.version]);

  async function handleSetDefault(): Promise<void> {
    if (!assumption) {
      return;
    }
    setSaving(true);
    try {
      const updated = await api.setDefaultAssumption(assumption.version);
      setAssumption(updated);
      setError("");
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to set default version.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="app-card p-8 text-sm text-[var(--color-text-secondary)]">Loading assumption version…</div>;
  }

  if (!assumption) {
    return <div className="rounded-[2rem] border border-rose-200 bg-rose-50 p-8 text-sm text-rose-700 shadow-sm">{error || "Assumption version not found."}</div>;
  }

  const sourceReferences = readMetadataRecord(assumption.raw_assumptions, "source_references");
  const serviceMetadata = readMetadataRecord(assumption.raw_assumptions, "service_metadata");

  return (
    <div className="space-y-6">
      <section className="app-card p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="app-kicker">Assumption Detail</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
              Version {assumption.version}
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Created {formatDate(assumption.created_at)}. Review the parameter set used by recalculation snapshots across the portfolio.
            </p>
            <div className="mt-4">
              <Breadcrumb
                items={[
                  { label: "Home", href: "/projects" },
                  { label: "Admin", href: "/admin" },
                  { label: "Assumptions", href: "/admin/assumptions" },
                  { label: assumption.version },
                ]}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            {!assumption.is_default ? (
              <button
                type="button"
                onClick={() => {
                  void handleSetDefault();
                }}
                disabled={saving}
                className="app-button-primary"
              >
                {saving ? "Updating…" : "Set as Default"}
              </button>
            ) : (
              <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">
                Default Version
              </span>
            )}
            <Link
              href={`/admin/assumptions?clone=${assumption.version}`}
              className="app-button-secondary"
            >
              Clone as New Version
            </Link>
          </div>
        </div>
        {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <article className="app-card p-6">
          <p className="app-label">OIC Parameters</p>
          <dl className="mt-5 space-y-3 text-sm text-[var(--color-text-secondary)]">
            <div className="flex items-center justify-between gap-4">
              <dt>Billing threshold (KB)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.oic_billing_threshold_kb}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Pack size Non-BYOL (msgs/hour)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.oic_pack_size_msgs_per_hour}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Pack size BYOL (msgs/hour)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.oic_byol_pack_size_msgs_per_hour}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>REST max payload (KB)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.oic_rest_max_payload_kb}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>FTP max payload (KB)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.oic_ftp_max_payload_kb}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Kafka max payload (KB)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.oic_kafka_max_payload_kb}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Timeout (seconds)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.oic_timeout_s}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Month days</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.month_days}</dd>
            </div>
          </dl>
        </article>

        <article className="app-card p-6">
          <p className="app-label">Queue + Streaming</p>
          <dl className="mt-5 space-y-3 text-sm text-[var(--color-text-secondary)]">
            <div className="flex items-center justify-between gap-4">
              <dt>Queue billing unit (KB)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.queue_billing_unit_kb}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Queue max message (KB)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.queue_max_message_kb}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Queue retention (days)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.queue_retention_days}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Queue throughput soft limit (msg/s)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">
                {assumption.queue_throughput_soft_limit_msgs_per_second}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Streaming write throughput (MB/s)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.streaming_partition_throughput_mb_s}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Streaming read throughput (MB/s)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.streaming_read_throughput_mb_s}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Streaming max message size (MB)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.streaming_max_message_size_mb}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Streaming retention (days)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.streaming_retention_days}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Streaming default partitions</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.streaming_default_partitions}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Functions default duration (ms)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.functions_default_duration_ms}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Functions default memory (MB)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.functions_default_memory_mb}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Functions default concurrency</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.functions_default_concurrency}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Functions max timeout (seconds)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.functions_max_timeout_s}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>Functions batch size (records)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.functions_batch_size_records}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>DI workspaces per region</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">{assumption.data_integration_workspaces_per_region}</dd>
            </div>
            <div className="flex items-center justify-between gap-4">
              <dt>DI deleted workspace retention (days)</dt>
              <dd className="font-semibold text-[var(--color-text-primary)]">
                {assumption.data_integration_deleted_workspace_retention_days}
              </dd>
            </div>
          </dl>
        </article>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <article className="app-card p-6">
          <p className="app-label">Workbook Source References</p>
          {Object.keys(sourceReferences).length === 0 ? (
            <p className="mt-4 text-sm text-[var(--color-text-secondary)]">No governed source references captured.</p>
          ) : (
            <dl className="mt-5 space-y-3 text-sm text-[var(--color-text-secondary)]">
              {Object.entries(sourceReferences).map(([key, value]) => (
                <div key={key} className="flex items-start justify-between gap-4">
                  <dt className="max-w-[16rem] font-medium text-[var(--color-text-primary)]">{key}</dt>
                  <dd className="max-w-xl text-right">{String(value)}</dd>
                </div>
              ))}
            </dl>
          )}
        </article>

        <article className="app-card p-6">
          <p className="app-label">Service Metadata</p>
          {Object.keys(serviceMetadata).length === 0 ? (
            <p className="mt-4 text-sm text-[var(--color-text-secondary)]">No workbook metadata captured.</p>
          ) : (
            <dl className="mt-5 space-y-3 text-sm text-[var(--color-text-secondary)]">
              {Object.entries(serviceMetadata).map(([key, value]) => (
                <div key={key} className="flex items-start justify-between gap-4">
                  <dt className="max-w-[16rem] font-medium text-[var(--color-text-primary)]">
                    {SERVICE_METADATA_LABELS[key] ?? key}
                  </dt>
                  <dd className="max-w-xl text-right">{String(value)}</dd>
                </div>
              ))}
            </dl>
          )}
        </article>
      </section>

      <section className="app-card p-6">
        <p className="app-label">Latest Snapshot Usage</p>
        {usages.length === 0 ? (
          <p className="mt-4 text-sm text-[var(--color-text-secondary)]">No project latest snapshot is currently using this version.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {usages.map((usage) => (
              <li key={usage.project.id} className="app-card-muted px-4 py-3">
                <p className="font-semibold text-[var(--color-text-primary)]">{usage.project.name}</p>
                <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
                  Latest snapshot: {usage.snapshot?.snapshot_id ?? "None"}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
