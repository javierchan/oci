/* Integration detail page with source lineage, audit history, and architect patching. */

import Link from "next/link";

import { Breadcrumb } from "@/components/breadcrumb";
import { IntegrationPatchForm } from "@/components/integration-patch-form";
import { QaBadge } from "@/components/qa-badge";
import { api } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";

type IntegrationDetailPageProps = {
  params: {
    projectId: string;
    integrationId: string;
  };
};

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function hasLineageValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value === "string") {
    return value.trim() !== "";
  }
  return true;
}

function compareLineageKeys(left: string, right: string): number {
  const leftIsNumeric = /^\d+$/.test(left);
  const rightIsNumeric = /^\d+$/.test(right);
  if (leftIsNumeric && rightIsNumeric) {
    return Number(left) - Number(right);
  }
  if (leftIsNumeric) {
    return -1;
  }
  if (rightIsNumeric) {
    return 1;
  }
  return left.localeCompare(right);
}

export default async function IntegrationDetailPage({
  params,
}: IntegrationDetailPageProps): Promise<JSX.Element> {
  const [project, detail, patterns, tools, audit] = await Promise.all([
    api.getProject(params.projectId),
    api.getIntegration(params.projectId, params.integrationId),
    api.listPatterns(),
    api.listDictionaryOptions("TOOLS"),
    api.listAudit(params.projectId, {
      entity_type: "catalog_integration",
      entity_id: params.integrationId,
    }),
  ]);

  const integration = detail.integration;
  const lineage = detail.lineage;
  const sourceRowHref = `/projects/${params.projectId}/import?batch_id=${lineage.import_batch_id}&row=${lineage.source_row_number}`;
  const lineageEntries = Object.entries(lineage.raw_data).sort(([left], [right]) => compareLineageKeys(left, right));
  const populatedLineageEntries = lineageEntries.filter(([, value]) => hasLineageValue(value));
  const hiddenLineageEntries = lineageEntries.filter(([, value]) => !hasLineageValue(value));

  return (
    <div className="space-y-8">
      <section className="app-card p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="app-kicker">Integration Detail</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
              {integration.interface_id ?? integration.interface_name ?? integration.id}
            </h1>
            <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
              Review immutable source lineage on the left and apply architect-owned patterning decisions on the right.
            </p>
            <div className="mt-4">
              <Breadcrumb
                items={[
                  { label: "Home", href: "/projects" },
                  { label: "Projects", href: "/projects" },
                  { label: project.name, href: `/projects/${params.projectId}` },
                  { label: "Catalog", href: `/projects/${params.projectId}/catalog` },
                  { label: integration.interface_name ?? integration.interface_id ?? "Integration" },
                ]}
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-4">
              <Link href={`/projects/${params.projectId}/catalog`} className="app-link">
                ← Back to Catalog
              </Link>
              <Link href={sourceRowHref} className="app-link">
                View Source Row →
              </Link>
              <Link href="#audit" className="app-link">
                View Audit Trail →
              </Link>
            </div>
          </div>
          <QaBadge status={integration.qa_status} />
        </div>
      </section>

      <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="space-y-6">
          <article className="app-card p-6">
            <p className="app-label">Source Data</p>
            <dl className="mt-5 grid gap-4 md:grid-cols-2">
              <div>
                <dt className="app-label">Interface ID</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{integration.interface_id ?? "—"}</dd>
              </div>
              <div>
                <dt className="app-label">Brand</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{integration.brand ?? "—"}</dd>
              </div>
              <div>
                <dt className="app-label">Business Process</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{integration.business_process ?? "—"}</dd>
              </div>
              <div>
                <dt className="app-label">Source System</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{integration.source_system ?? "—"}</dd>
              </div>
              <div>
                <dt className="app-label">Destination System</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{integration.destination_system ?? "—"}</dd>
              </div>
              <div>
                <dt className="app-label">Frequency</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{integration.frequency ?? "—"}</dd>
              </div>
              <div>
                <dt className="app-label">Payload per Execution</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">
                  {formatNumber(integration.payload_per_execution_kb, 1)} KB
                </dd>
              </div>
              <div>
                <dt className="app-label">Type</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{integration.type ?? "—"}</dd>
              </div>
              <div>
                <dt className="app-label">Complexity</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{integration.complexity ?? "—"}</dd>
              </div>
              <div>
                <dt className="app-label">Status</dt>
                <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{integration.status ?? "—"}</dd>
              </div>
            </dl>
          </article>

          <article className="app-card p-6">
            <p className="app-label">Source Lineage</p>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div className="app-card-muted p-4">
                <p className="app-label">Source Row Number</p>
                <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{lineage.source_row_number}</p>
              </div>
              <div className="app-card-muted p-4">
                <p className="app-label">Import Batch</p>
                <p className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{lineage.import_filename}</p>
              </div>
            </div>

            <div className="app-card-muted mt-6 p-4">
              <p className="app-label">Raw Column Values</p>
              <div className="mt-4 overflow-hidden rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)]">
                <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
                  <thead className="app-table-header">
                    <tr>
                      <th className="px-4 py-3">Field</th>
                      <th className="px-4 py-3">Source Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
                    {populatedLineageEntries.map(([key, value]: [string, unknown]) => (
                      <tr key={key} className="app-table-row">
                        <td className="px-4 py-3 font-medium text-[var(--color-text-primary)]">
                          {lineage.column_names?.[key] ?? `Column ${key}`}
                        </td>
                        <td className="px-4 py-3 text-[var(--color-text-secondary)]">
                          {stringifyValue(value)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {hiddenLineageEntries.length > 0 ? (
                <details className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)]">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-[var(--color-accent)]">
                    Show all columns ({hiddenLineageEntries.length})
                  </summary>
                  <div className="border-t border-[var(--color-border)]">
                    <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
                      <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
                        {hiddenLineageEntries.map(([key, value]: [string, unknown]) => (
                          <tr key={key} className="app-table-row">
                            <td className="px-4 py-3 font-medium text-[var(--color-text-primary)]">
                              {lineage.column_names?.[key] ?? `Column ${key}`}
                            </td>
                            <td className="px-4 py-3 text-[var(--color-text-secondary)]">
                              {stringifyValue(value)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              ) : null}
            </div>

            <div className="app-card-muted mt-6 p-4">
              <p className="app-label">Normalization Events</p>
              {lineage.normalization_events.length === 0 ? (
                <p className="mt-3 text-sm text-[var(--color-text-secondary)]">No normalization events were recorded for this row.</p>
              ) : (
                <ul className="mt-3 space-y-3 text-sm text-[var(--color-text-secondary)]">
                  {lineage.normalization_events.map((event) => (
                    <li key={`${event.field}-${event.rule}`} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
                      <p className="font-medium text-[var(--color-text-primary)]">{event.field}</p>
                      <p className="mt-1 text-[var(--color-text-secondary)]">
                        {stringifyValue(event.old_value)} → {stringifyValue(event.new_value)}
                      </p>
                      <p className="mt-2 text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">{event.rule}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </article>
        </section>

        <IntegrationPatchForm
          projectId={params.projectId}
          integration={integration}
          patterns={patterns.patterns}
          toolOptions={tools.options}
        />
      </div>

      <section id="audit" className="app-table-shell">
        <div className="border-b border-[var(--color-border)] px-6 py-5">
          <p className="app-label">Audit Trail</p>
          <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">Recent changes</h2>
        </div>
        {audit.events.length === 0 ? (
          <div className="px-6 py-10 text-sm text-[var(--color-text-secondary)]">No audit events recorded for this integration yet.</div>
        ) : (
          <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
            <thead className="app-table-header">
              <tr>
                <th className="px-6 py-4">When</th>
                <th className="px-6 py-4">Event</th>
                <th className="px-6 py-4">Actor</th>
                <th className="px-6 py-4">Entity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
              {audit.events.map((event) => (
                <tr key={event.id} className="app-table-row">
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{formatDate(event.created_at)}</td>
                  <td className="px-6 py-4 font-medium text-[var(--color-text-primary)]">{event.event_type}</td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{event.actor_id}</td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{event.entity_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
