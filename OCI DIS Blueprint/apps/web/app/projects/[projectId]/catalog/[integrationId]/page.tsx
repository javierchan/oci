/* Integration detail page with source lineage, audit history, and architect patching. */

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

export default async function IntegrationDetailPage({
  params,
}: IntegrationDetailPageProps): Promise<JSX.Element> {
  const [detail, patterns, tools, audit] = await Promise.all([
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

  return (
    <div className="space-y-8">
      <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-sky-700">Integration Detail</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-slate-950">
              {integration.interface_id ?? integration.interface_name ?? integration.id}
            </h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Review immutable source lineage on the left and apply architect-owned patterning decisions on the right.
            </p>
          </div>
          <QaBadge status={integration.qa_status} />
        </div>
      </section>

      <div className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="space-y-6">
          <article className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Source Data</p>
            <dl className="mt-5 grid gap-4 md:grid-cols-2">
              <div>
                <dt className="text-xs uppercase tracking-[0.2em] text-slate-400">Interface ID</dt>
                <dd className="mt-2 text-sm font-medium text-slate-950">{integration.interface_id ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.2em] text-slate-400">Brand</dt>
                <dd className="mt-2 text-sm font-medium text-slate-950">{integration.brand ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.2em] text-slate-400">Business Process</dt>
                <dd className="mt-2 text-sm font-medium text-slate-950">{integration.business_process ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.2em] text-slate-400">Source System</dt>
                <dd className="mt-2 text-sm font-medium text-slate-950">{integration.source_system ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.2em] text-slate-400">Destination System</dt>
                <dd className="mt-2 text-sm font-medium text-slate-950">{integration.destination_system ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.2em] text-slate-400">Frequency</dt>
                <dd className="mt-2 text-sm font-medium text-slate-950">{integration.frequency ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.2em] text-slate-400">Payload per Execution</dt>
                <dd className="mt-2 text-sm font-medium text-slate-950">
                  {formatNumber(integration.payload_per_execution_kb, 1)} KB
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.2em] text-slate-400">Type</dt>
                <dd className="mt-2 text-sm font-medium text-slate-950">{integration.type ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.2em] text-slate-400">Complexity</dt>
                <dd className="mt-2 text-sm font-medium text-slate-950">{integration.complexity ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-[0.2em] text-slate-400">Status</dt>
                <dd className="mt-2 text-sm font-medium text-slate-950">{integration.status ?? "—"}</dd>
              </div>
            </dl>
          </article>

          <article className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Source Lineage</p>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Source Row Number</p>
                <p className="mt-2 text-2xl font-semibold text-slate-950">{lineage.source_row_number}</p>
              </div>
              <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Import Batch</p>
                <p className="mt-2 text-sm font-medium text-slate-950">{lineage.import_filename}</p>
              </div>
            </div>

            <div className="mt-6 rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Raw Column Values</p>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {Object.entries(lineage.raw_data).map(([key, value]: [string, unknown]) => (
                  <div key={key} className="rounded-2xl border border-white bg-white px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Column {key}</p>
                    <p className="mt-2 break-all text-sm text-slate-900">{stringifyValue(value)}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-6 rounded-[1.5rem] border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Normalization Events</p>
              {lineage.normalization_events.length === 0 ? (
                <p className="mt-3 text-sm text-slate-500">No normalization events were recorded for this row.</p>
              ) : (
                <ul className="mt-3 space-y-3 text-sm text-slate-700">
                  {lineage.normalization_events.map((event) => (
                    <li key={`${event.field}-${event.rule}`} className="rounded-2xl border border-white bg-white px-4 py-3">
                      <p className="font-medium text-slate-950">{event.field}</p>
                      <p className="mt-1 text-slate-500">
                        {stringifyValue(event.old_value)} → {stringifyValue(event.new_value)}
                      </p>
                      <p className="mt-2 text-xs uppercase tracking-[0.2em] text-slate-400">{event.rule}</p>
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

      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-6 py-5">
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Audit Trail</p>
          <h2 className="mt-2 text-2xl font-semibold text-slate-950">Recent changes</h2>
        </div>
        {audit.events.length === 0 ? (
          <div className="px-6 py-10 text-sm text-slate-500">No audit events recorded for this integration yet.</div>
        ) : (
          <table className="min-w-full divide-y divide-slate-200 text-left">
            <thead className="bg-slate-950 text-xs uppercase tracking-[0.25em] text-slate-400">
              <tr>
                <th className="px-6 py-4 font-medium">When</th>
                <th className="px-6 py-4 font-medium">Event</th>
                <th className="px-6 py-4 font-medium">Actor</th>
                <th className="px-6 py-4 font-medium">Entity</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
              {audit.events.map((event) => (
                <tr key={event.id}>
                  <td className="px-6 py-4 text-slate-500">{formatDate(event.created_at)}</td>
                  <td className="px-6 py-4 font-medium text-slate-950">{event.event_type}</td>
                  <td className="px-6 py-4">{event.actor_id}</td>
                  <td className="px-6 py-4">{event.entity_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
