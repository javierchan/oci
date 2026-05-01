"use client";

/* Assumption version detail page with current usage context and default promotion. */

import Link from "next/link";
import { CheckCircle2, Clock3, Gauge, Layers3 } from "lucide-react";
import { use, useEffect, useState } from "react";

import { Breadcrumb } from "@/components/breadcrumb";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { AssumptionSet, Project, VolumetrySnapshotSummary } from "@/lib/types";

type AdminAssumptionDetailPageProps = {
  params: Promise<{
    version: string;
  }>;
};

type ProjectUsage = {
  project: Project;
  snapshot: VolumetrySnapshotSummary | null;
};

type MetadataValue = string | number | boolean;
type ParameterValue = MetadataValue | null | undefined;

type ParameterItem = {
  label: string;
  value: ParameterValue;
  unit?: string;
};

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

const SOURCE_REFERENCE_LABELS: Record<string, string> = {
  oic_limits: "OIC limits",
  oic_billing: "OIC billing",
  streaming_limits: "Streaming limits",
  functions_limits: "Functions limits",
  queue_limits: "Queue limits",
  data_integration_limits: "Data Integration limits",
  data_integrator_proxy_usage: "Data Integrator proxy usage",
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

function formatParameterValue(value: ParameterValue, unit?: string): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  const rendered =
    typeof value === "number"
      ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 6 }).format(value)
      : value;
  return unit ? `${rendered} ${unit}` : String(rendered);
}

function formatMetadataValue(value: MetadataValue): string {
  return formatParameterValue(value).replace("TPL - Supuestos:", "TPL - Assumptions:");
}

function ParameterPanel({
  title,
  summary,
  items,
}: {
  title: string;
  summary: string;
  items: ParameterItem[];
}): JSX.Element {
  return (
    <article className="app-card overflow-hidden">
      <div className="border-b border-[var(--color-border)] px-5 py-4">
        <p className="app-label">{summary}</p>
        <h2 className="mt-1 text-xl font-semibold text-[var(--color-text-primary)]">{title}</h2>
      </div>
      <dl className="divide-y divide-[var(--color-border)]">
        {items.map((item) => (
          <div key={item.label} className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 px-5 py-3 text-sm">
            <dt className="text-[var(--color-text-secondary)]">{item.label}</dt>
            <dd className="text-right font-mono font-semibold text-[var(--color-text-primary)]">
              {formatParameterValue(item.value, item.unit)}
            </dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

function MetadataPanel({
  title,
  empty,
  entries,
  labels = {},
}: {
  title: string;
  empty: string;
  entries: Record<string, MetadataValue>;
  labels?: Record<string, string>;
}): JSX.Element {
  return (
    <article className="app-card overflow-hidden">
      <div className="border-b border-[var(--color-border)] px-5 py-4">
        <p className="app-label">{title}</p>
      </div>
      {Object.keys(entries).length === 0 ? (
        <p className="px-5 py-6 text-sm text-[var(--color-text-secondary)]">{empty}</p>
      ) : (
        <dl className="divide-y divide-[var(--color-border)]">
          {Object.entries(entries).map(([key, value]) => (
            <div key={key} className="grid gap-2 px-5 py-3 text-sm sm:grid-cols-[minmax(0,16rem)_1fr]">
              <dt className="font-medium text-[var(--color-text-primary)]">{labels[key] ?? key}</dt>
              <dd className="break-words text-[var(--color-text-secondary)] sm:text-right">
                {formatMetadataValue(value)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  );
}

export default function AdminAssumptionDetailPage({
  params,
}: AdminAssumptionDetailPageProps): JSX.Element {
  const { version } = use(params);
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
          api.getAssumption(version),
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
  }, [version]);

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
  const oicParameters: ParameterItem[] = [
    { label: "Billing threshold", value: assumption.oic_billing_threshold_kb, unit: "KB" },
    { label: "Pack size Non-BYOL", value: assumption.oic_pack_size_msgs_per_hour, unit: "msgs/hour" },
    { label: "Pack size BYOL", value: assumption.oic_byol_pack_size_msgs_per_hour, unit: "msgs/hour" },
    { label: "REST max payload", value: assumption.oic_rest_max_payload_kb, unit: "KB" },
    { label: "FTP max payload", value: assumption.oic_ftp_max_payload_kb, unit: "KB" },
    { label: "Kafka max payload", value: assumption.oic_kafka_max_payload_kb, unit: "KB" },
    { label: "Timeout", value: assumption.oic_timeout_s, unit: "seconds" },
    { label: "Month days", value: assumption.month_days },
  ];
  const queueStreamingParameters: ParameterItem[] = [
    { label: "Queue billing unit", value: assumption.queue_billing_unit_kb, unit: "KB" },
    { label: "Queue max message", value: assumption.queue_max_message_kb, unit: "KB" },
    { label: "Queue retention", value: assumption.queue_retention_days, unit: "days" },
    {
      label: "Queue throughput soft limit",
      value: assumption.queue_throughput_soft_limit_msgs_per_second,
      unit: "msg/s",
    },
    { label: "Streaming write throughput", value: assumption.streaming_partition_throughput_mb_s, unit: "MB/s" },
    { label: "Streaming read throughput", value: assumption.streaming_read_throughput_mb_s, unit: "MB/s" },
    { label: "Streaming max message size", value: assumption.streaming_max_message_size_mb, unit: "MB" },
    { label: "Streaming retention", value: assumption.streaming_retention_days, unit: "days" },
    { label: "Streaming default partitions", value: assumption.streaming_default_partitions },
  ];
  const functionsDataParameters: ParameterItem[] = [
    { label: "Functions default duration", value: assumption.functions_default_duration_ms, unit: "ms" },
    { label: "Functions default memory", value: assumption.functions_default_memory_mb, unit: "MB" },
    { label: "Functions default concurrency", value: assumption.functions_default_concurrency },
    { label: "Functions max timeout", value: assumption.functions_max_timeout_s, unit: "seconds" },
    { label: "Functions batch size", value: assumption.functions_batch_size_records, unit: "records" },
    { label: "DI workspaces per region", value: assumption.data_integration_workspaces_per_region },
    {
      label: "DI deleted workspace retention",
      value: assumption.data_integration_deleted_workspace_retention_days,
      unit: "days",
    },
  ];

  return (
    <div className="console-page">
      <section className="console-hero">
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

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="app-card p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="app-label">Version State</p>
            <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-emerald-600 dark:text-emerald-300">
              <CheckCircle2 className="h-4 w-4" />
            </span>
          </div>
          <p className="mt-3 text-2xl font-semibold text-[var(--color-text-primary)]">
            {assumption.is_default ? "Default" : "Versioned"}
          </p>
        </article>
        <article className="app-card p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="app-label">Created</p>
            <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-[var(--color-accent)]">
              <Clock3 className="h-4 w-4" />
            </span>
          </div>
          <p className="mt-3 text-lg font-semibold text-[var(--color-text-primary)]">
            {formatDate(assumption.created_at)}
          </p>
        </article>
        <article className="app-card p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="app-label">OIC Threshold</p>
            <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-[var(--color-accent)]">
              <Gauge className="h-4 w-4" />
            </span>
          </div>
          <p className="mt-3 font-mono text-2xl font-semibold text-[var(--color-text-primary)]">
            {formatParameterValue(assumption.oic_billing_threshold_kb, "KB")}
          </p>
        </article>
        <article className="app-card p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="app-label">Latest Snapshot Usage</p>
            <span className="rounded-lg bg-[var(--color-surface-2)] p-2 text-[var(--color-accent)]">
              <Layers3 className="h-4 w-4" />
            </span>
          </div>
          <p className="mt-3 text-2xl font-semibold text-[var(--color-text-primary)]">{usages.length}</p>
        </article>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <ParameterPanel title="OIC Parameters" summary="Billing + limits" items={oicParameters} />
        <ParameterPanel title="Queue + Streaming" summary="Messaging constraints" items={queueStreamingParameters} />
        <ParameterPanel title="Functions + Data Integration" summary="Compute + workspace limits" items={functionsDataParameters} />
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <MetadataPanel
          title="Workbook Source References"
          empty="No governed source references captured."
          entries={sourceReferences}
          labels={SOURCE_REFERENCE_LABELS}
        />
        <MetadataPanel
          title="Service Metadata"
          empty="No workbook metadata captured."
          entries={serviceMetadata}
          labels={SERVICE_METADATA_LABELS}
        />
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
