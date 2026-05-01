/* Integration detail page with source lineage, audit history, and architect patching. */

import Link from "next/link";
import { notFound } from "next/navigation";

import { AiReviewButton } from "@/components/ai-review-button";
import { Breadcrumb } from "@/components/breadcrumb";
import { ComplexityBadge } from "@/components/complexity-badge";
import { IntegrationDesignCanvasPanel } from "@/components/integration-design-canvas-panel";
import { IntegrationPatchForm } from "@/components/integration-patch-form";
import { QaBadge } from "@/components/qa-badge";
import { RawColumnValuesTable } from "@/components/raw-column-values-table";
import { PatternSupportBadge } from "@/components/pattern-support-badge";
import { api } from "@/lib/api";
import { displayUiValue, formatDate, formatNumber } from "@/lib/format";
import { isProjectNotFoundError } from "@/lib/project-errors";
import type { AuditEvent, Integration } from "@/lib/types";

type IntegrationDetailPageProps = {
  params: Promise<{
    projectId: string;
    integrationId: string;
  }>;
};

function formatEventValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "—";
  }
  if (typeof value === "string") {
    return displayUiValue(value);
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

const AUDIT_LABELS: Record<string, string> = {
  additional_tools_overlays: "Canvas flow",
  selected_pattern: "Pattern",
  pattern_rationale: "Pattern rationale",
  comments: "Comments",
  retry_policy: "Retry policy",
  core_tools: "Core tools",
  raw_column_values: "Raw column values",
  source_system: "Source system",
  destination_system: "Destination system",
  interface_name: "Interface name",
  payload_per_execution_kb: "Payload per execution",
  frequency: "Frequency",
  complexity: "Complexity",
  status: "Status",
  qa_status: "QA status",
};

const QA_REASON_LABELS: Record<string, { title: string; hint: string }> = {
  MISSING_ID_FORMAL: {
    title: "Formal ID coverage gap",
    hint: "This is now treated as a governance coverage signal rather than the primary QA gate. Recalculate to refresh older snapshots.",
  },
  INVALID_TRIGGER_TYPE: {
    title: "Trigger type not recognized",
    hint: "The trigger type value does not match any known OIC trigger. Check the Trigger Type field.",
  },
  INVALID_PATTERN: {
    title: "Pattern not assigned",
    hint: "Select an OIC integration pattern from the Pattern dropdown on the right.",
  },
  MISSING_RATIONALE: {
    title: "Pattern rationale missing",
    hint: "Add a brief explanation for the selected pattern in the Pattern Rationale field.",
  },
  MISSING_CORE_TOOLS: {
    title: "No tools selected in canvas",
    hint: "Use the Integration Design Canvas to add at least one tool to this integration.",
  },
  PATTERN_REFERENCE_ONLY: {
    title: "Pattern is reference-only in phase parity",
    hint: "This workbook pattern is documented and selectable, but the current release does not yet provide pattern-specific sizing parity. Treat estimates as directional and keep the row in architect review.",
  },
  MISSING_PAYLOAD: {
    title: "Payload evidence missing",
    hint: "Forecast metrics stay low confidence until Payload KB is captured from the source workbook or architect review.",
  },
  MISSING_FAN_OUT_TARGETS: {
    title: "Fan-out targets missing",
    hint: "This integration is marked as fan-out, but the downstream target count is still missing or incomplete.",
  },
  TBD_UNCERTAINTY: {
    title: "Source uncertainty still open",
    hint: "The workbook still marks this row as TBD. Keep the uncertainty visible until source evidence is resolved.",
  },
  SCATTER_GATHER_EXCEEDS_OIC_PARALLEL_LIMIT: {
    title: "Scatter-gather exceeds OIC parallel limit",
    hint: "OIC Gen3 supports a maximum of 5 parallel branches. Split this flow into smaller fan-outs or redesign the aggregation path.",
  },
  SAGA_SYNC_DURATION_RISK: {
    title: "Saga selected on synchronous long-running path",
    hint: "This saga looks too heavy for a synchronous REST/SOAP flow. Move the transaction to an asynchronous orchestration path.",
  },
  STREAMING_PAYLOAD_EXCEEDS_1MB_LIMIT: {
    title: "Streaming payload exceeds 1 MB",
    hint: "OCI Streaming enforces a 1 MB message limit. Externalize the payload or change the tool stack.",
  },
  FUNCTIONS_PAYLOAD_EXCEEDS_6MB_LIMIT: {
    title: "Functions payload exceeds 6 MB",
    hint: "Oracle Functions cannot receive payloads above 6 MB. Route large payloads through OIC or object storage instead.",
  },
  QUEUE_PAYLOAD_EXCEEDS_256KB_LIMIT: {
    title: "Queue payload exceeds 256 KB",
    hint: "OCI Queue caps message size at 256 KB. Store the full payload elsewhere and queue a reference token.",
  },
  REFERENCE_PATTERN_NEEDS_EXPLICIT_RATIONALE: {
    title: "Reference pattern needs explicit rationale",
    hint: "Reference-only patterns require a substantive architect explanation before the row can be treated as governed.",
  },
};

const SOURCE_ROW_FIELD_NAMES = [
  "#",
  "Interface ID",
  "Owner",
  "Brand",
  "Business Process",
  "Interface Name",
  "Description",
  "Status",
  "Mapping Status",
  "Initial Scope",
  "Complexity",
  "Frequency",
  "Type",
  "Base",
  "Interface Status",
  "Real Time",
  "Trigger Type",
  "Response Size KB",
  "Payload per Execution KB",
  "Fan-out",
  "Fan-out Targets",
  "Source System",
  "Source Technology",
  "Source API Reference",
  "Source Owner",
  "Destination System",
  "Destination Technology 1",
  "Destination Technology 2",
  "Destination Owner",
  "Calendarization",
];

function isEqualAuditValue(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function auditFieldLabel(field: string): string {
  if (/^\d+$/.test(field)) {
    return SOURCE_ROW_FIELD_NAMES[Number(field)] ?? `Column ${Number(field) + 1}`;
  }
  return AUDIT_LABELS[field] ?? field.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function summarizeAuditEvent(event: AuditEvent): { title: string; changes: Array<{ field: string; detail: string }> } {
  if (event.entity_type === "source_integration_row") {
    const nextValues = event.new_value ?? {};
    return {
      title: "Source lineage updated",
      changes: Object.keys(nextValues)
        .slice(0, 6)
        .map((field) => ({
          field: auditFieldLabel(field),
          detail: formatEventValue(nextValues[field]),
        })),
    };
  }

  const oldValue = event.old_value ?? {};
  const newValue = event.new_value ?? {};
  const changedFields = Array.from(
    new Set([...Object.keys(oldValue), ...Object.keys(newValue)]),
  ).filter((field) => !["created_at", "updated_at"].includes(field) && !isEqualAuditValue(oldValue[field], newValue[field]));

  return {
    title: event.event_type === "catalog_update" ? "Integration updated" : "Integration change recorded",
    changes: changedFields.map((field) => ({
      field: auditFieldLabel(field),
      detail:
        field === "additional_tools_overlays"
          ? "Canvas nodes or connections changed."
          : `${formatEventValue(oldValue[field])} → ${formatEventValue(newValue[field])}`,
    })),
  };
}

function buildCoverageSignals(integration: Integration): Array<{ title: string; detail: string }> {
  const signals: Array<{ title: string; detail: string }> = [];

  if (!integration.interface_id || integration.interface_id.trim() === "") {
    signals.push({
      title: "Formal ID coverage gap",
      detail: "The integration is still evaluated by QA, but governance coverage remains incomplete until a formal Interface ID is assigned.",
    });
  }

  if (integration.payload_per_execution_kb === null || integration.payload_per_execution_kb === undefined) {
    signals.push({
      title: "Low-confidence forecast",
      detail: "Payload evidence is missing, so billing and throughput forecasts for this integration remain directional rather than precise.",
    });
  }

  if (integration.uncertainty && integration.uncertainty.toUpperCase().includes("TBD")) {
    signals.push({
      title: "Workbook uncertainty preserved",
      detail: "The source workbook still flags uncertainty as TBD. This signal should stay visible until the source team resolves it.",
    });
  }

  return signals;
}

export default async function IntegrationDetailPage({
  params,
}: IntegrationDetailPageProps): Promise<JSX.Element> {
  const { projectId, integrationId } = await params;
  let project;
  try {
    project = await api.getProject(projectId);
  } catch (error) {
    if (isProjectNotFoundError(error)) {
      notFound();
    }
    throw error;
  }
  const [detail, patterns, canvasGovernance, integrationAudit, sourceRowAudit, services] = await Promise.all([
    api.getIntegration(projectId, integrationId),
    api.listPatterns(),
    api.getCanvasGovernance(),
    api.listAudit(projectId, {
      entity_type: "catalog_integration",
      entity_id: integrationId,
    }),
    api.listAudit(projectId, {
      entity_type: "source_integration_row",
      entity_id: integrationId,
    }).catch(() => ({
      events: [],
      total: 0,
      page: 1,
      page_size: 50,
    })),
    api.listServices().catch(() => ({
      services: [],
      total: 0,
    })),
  ]);

  const integration = detail.integration;
  const lineage = detail.lineage;
  const sourceRowHref = `/projects/${projectId}/import?batch_id=${lineage.import_batch_id}&row=${lineage.source_row_number}`;
  const sourceAuditEvents =
    lineage.source_row_id && sourceRowAudit.events.length === 0
      ? (
          await api.listAudit(projectId, {
            entity_type: "source_integration_row",
            entity_id: lineage.source_row_id,
          }).catch(() => ({
            events: [],
            total: 0,
            page: 1,
            page_size: 50,
          }))
        ).events
      : sourceRowAudit.events;
  const auditEvents = [...integrationAudit.events, ...sourceAuditEvents].sort(
    (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
  );
  const coverageSignals = buildCoverageSignals(integration);
  const patternMap = new Map(patterns.patterns.map((pattern) => [pattern.pattern_id, pattern]));
  const selectedPatternDefinition = integration.selected_pattern
    ? patternMap.get(integration.selected_pattern) ?? null
    : null;
  const patternDetail =
    patterns.patterns.find(
      (pattern) =>
        pattern.name === integration.selected_pattern || pattern.pattern_id === integration.selected_pattern,
    ) ?? selectedPatternDefinition;

  return (
    <div className="console-page">
      <section className="console-hero">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="app-kicker">Catalog Drawer · Integration Detail</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
              {integration.interface_name ?? integration.interface_id ?? integration.id}
            </h1>
            {integration.interface_id && integration.interface_name ? (
              <p className="mt-1 font-mono text-sm text-[var(--color-text-muted)]">
                {integration.interface_id}
              </p>
            ) : null}
            <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
              Review immutable source lineage on the left and apply architect-owned patterning decisions on the right.
            </p>
            <div className="mt-4">
              <Breadcrumb
                items={[
                  { label: "Home", href: "/projects" },
                  { label: "Projects", href: "/projects" },
                  { label: project.name, href: `/projects/${projectId}` },
                  { label: "Catalog", href: `/projects/${projectId}/catalog` },
                  { label: integration.interface_name ?? integration.interface_id ?? "Integration" },
                ]}
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-4">
              <Link href={`/projects/${projectId}/catalog`} className="app-link">
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
          <div className="flex flex-wrap items-center gap-3">
            <AiReviewButton projectId={projectId} integrationId={integrationId} defaultScope="integration" />
            <QaBadge status={integration.qa_status} />
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="app-card p-5">
          <p className="app-label">Route</p>
          <p className="mt-3 text-sm font-semibold text-[var(--color-text-primary)]">
            {integration.source_system ?? "Unknown source"}
          </p>
          <p className="my-2 text-lg font-semibold text-[var(--color-accent)]">→</p>
          <p className="text-sm font-semibold text-[var(--color-text-primary)]">
            {integration.destination_system ?? "Unknown destination"}
          </p>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">
            {displayUiValue(integration.source_technology)} to{" "}
            {displayUiValue(integration.destination_technology_1)}
          </p>
        </article>

        <article className="app-card p-5">
          <p className="app-label">Pattern</p>
          <p className="mt-3 text-lg font-semibold text-[var(--color-text-primary)]">
            {selectedPatternDefinition
              ? `${selectedPatternDefinition.pattern_id} · ${selectedPatternDefinition.name}`
              : integration.selected_pattern ?? "Unassigned"}
          </p>
          {selectedPatternDefinition ? (
            <div className="mt-3">
              <PatternSupportBadge support={selectedPatternDefinition.support} />
            </div>
          ) : null}
        </article>

        <article className="app-card p-5">
          <p className="app-label">Volumetry</p>
          <p className="mt-3 text-2xl font-semibold text-[var(--color-text-primary)]">
            {formatNumber(integration.payload_per_execution_kb, 1)} KB
          </p>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
            {displayUiValue(integration.frequency)} · {formatNumber(integration.executions_per_day, 1)} exec/day
          </p>
        </article>

        <article className="app-card p-5">
          <p className="app-label">Governance</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <QaBadge status={integration.qa_status} />
            <ComplexityBadge value={integration.complexity} />
          </div>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">
            {auditEvents.length} audit event{auditEvents.length === 1 ? "" : "s"} ·{" "}
            {integration.qa_reasons.length} QA reason{integration.qa_reasons.length === 1 ? "" : "s"}
          </p>
        </article>
      </section>

      <div className="grid items-start gap-8 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="space-y-6">
          <article className="app-card p-6">
            <p className="app-label">Source Data</p>
            <dl className="mt-5">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <dt className="app-label">Interface ID</dt>
                  <dd className="mt-2 font-mono text-sm font-medium text-[var(--color-text-primary)]">{integration.interface_id ?? "—"}</dd>
                </div>
                <div>
                  <dt className="app-label">Interface Name</dt>
                  <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">
                    {integration.interface_name ?? "—"}
                  </dd>
                </div>
              </div>

              <div className="mt-4 grid gap-4 border-t border-[var(--color-border)] pt-4 md:grid-cols-3">
                <div>
                  <dt className="app-label">Brand</dt>
                  <dd className="mt-2 text-sm text-[var(--color-text-secondary)]">{integration.brand ?? "—"}</dd>
                </div>
                <div>
                  <dt className="app-label">Business Process</dt>
                  <dd className="mt-2 text-sm text-[var(--color-text-secondary)]">{integration.business_process ?? "—"}</dd>
                </div>
                <div>
                  <dt className="app-label">Status</dt>
                  <dd className="mt-2 text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.status)}</dd>
                </div>
              </div>

              <div className="mt-4 grid gap-4 border-t border-[var(--color-border)] pt-4 md:grid-cols-2 lg:grid-cols-4">
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
                  <dd className="mt-2 text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.frequency)}</dd>
                </div>
                <div>
                  <dt className="app-label">Payload / Execution</dt>
                  <dd className="mt-2 text-sm text-[var(--color-text-secondary)]">
                    {formatNumber(integration.payload_per_execution_kb, 1)} KB
                  </dd>
                </div>
                <div>
                  <dt className="app-label">Type</dt>
                  <dd className="mt-2 text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.type)}</dd>
                </div>
                <div>
                  <dt className="app-label">Complexity</dt>
                  <dd className="mt-2"><ComplexityBadge value={integration.complexity} /></dd>
                </div>
                <div>
                  <dt className="app-label">Initial Scope</dt>
                  <dd className="mt-2 text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.initial_scope)}</dd>
                </div>
                <div>
                  <dt className="app-label">Uncertainty</dt>
                  <dd className="mt-2 text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.uncertainty)}</dd>
                </div>
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
              <RawColumnValuesTable
                projectId={projectId}
                integrationId={integrationId}
                initialValues={lineage.raw_data}
                columnNames={lineage.column_names}
              />
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
                        {formatEventValue(event.old_value)} → {formatEventValue(event.new_value)}
                      </p>
                      <p className="mt-2 text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">{event.rule}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </article>
        </section>

        <aside className="space-y-8">
          <IntegrationPatchForm
            projectId={projectId}
            integration={integration}
            patterns={patterns.patterns}
            toolOptions={canvasGovernance.tools}
            overlayOptions={canvasGovernance.overlays}
          />

          {integration.qa_reasons.length > 0 ? (
            <section className="app-card p-6">
              <p className="app-label">QA Reasons</p>
              <div className="mt-4 space-y-3">
                {integration.qa_reasons.map((reason) => {
                  const details = QA_REASON_LABELS[reason];
                  return (
                    <article
                      key={reason}
                      className="rounded-2xl border border-[var(--color-qa-revisar-border)] border-l-4 bg-[var(--color-qa-revisar-bg)] p-4"
                    >
                      <p className="font-semibold text-[var(--color-text-primary)]">
                        {details?.title ?? reason}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                        {details?.hint ?? "Review this validation code in the imported data and update the integration as needed."}
                      </p>
                    </article>
                  );
                })}
              </div>
            </section>
          ) : null}

          {coverageSignals.length > 0 ? (
            <section className="app-card p-6">
              <p className="app-label">Coverage Signals</p>
              <div className="mt-4 space-y-3">
                {coverageSignals.map((signal) => (
                  <article
                    key={signal.title}
                    className="rounded-2xl border border-sky-200 border-l-4 bg-sky-50 p-4"
                  >
                    <p className="font-semibold text-sky-950">{signal.title}</p>
                    <p className="mt-2 text-sm leading-6 text-sky-900">{signal.detail}</p>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {selectedPatternDefinition ? (
            <section className="app-card p-6">
              <p className="app-label">Pattern Support</p>
              <div className="mt-4 space-y-3">
                <PatternSupportBadge support={selectedPatternDefinition.support} />
                <p className="text-sm leading-6 text-[var(--color-text-secondary)]">
                  {selectedPatternDefinition.support.summary}
                </p>
                {selectedPatternDefinition.when_not_to_use ? (
                  <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                    <p className="font-semibold text-[var(--color-text-primary)]">Anti-pattern guidance</p>
                    <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                      {selectedPatternDefinition.when_not_to_use}
                    </p>
                  </div>
                ) : null}
              </div>
            </section>
          ) : null}

          <section id="audit" className="app-card overflow-hidden">
            <div className="border-b border-[var(--color-border)] px-6 py-5">
              <p className="app-label">Audit Trail</p>
              <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">Recent changes</h2>
              <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
                Includes canvas edits, architect patch changes, and source-lineage overrides for this integration.
              </p>
            </div>
            {auditEvents.length === 0 ? (
              <div className="px-6 py-10 text-sm text-[var(--color-text-secondary)]">
                No audit events recorded for this integration yet.
              </div>
            ) : (
              <div className="space-y-4 px-6 py-5">
                {auditEvents.map((event) => {
                  const summary = summarizeAuditEvent(event);
                  return (
                    <article
                      key={event.id}
                      className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-medium text-[var(--color-text-primary)]">{summary.title}</p>
                          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
                            {event.entity_type.replace(/_/g, " ")}
                          </p>
                        </div>
                        <div className="text-right text-sm text-[var(--color-text-secondary)]">
                          <p>{formatDate(event.created_at)}</p>
                          <p>{event.actor_id}</p>
                        </div>
                      </div>
                      {summary.changes.length > 0 ? (
                        <ul className="mt-4 space-y-2 text-sm text-[var(--color-text-secondary)]">
                          {summary.changes.map((change) => (
                            <li key={`${event.id}-${change.field}`} className="rounded-xl bg-[var(--color-surface-2)] px-3 py-2">
                              <span className="font-medium text-[var(--color-text-primary)]">{change.field}: </span>
                              <span>{change.detail}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-4 text-sm text-[var(--color-text-secondary)]">
                          Change details were recorded without field-level differences.
                        </p>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </aside>
      </div>

      <IntegrationDesignCanvasPanel
        projectId={projectId}
        integration={integration}
        patterns={patterns.patterns}
        patternDetail={patternDetail}
        serviceProfiles={services.services}
        toolOptions={canvasGovernance.tools}
        overlayOptions={canvasGovernance.overlays}
        combinations={canvasGovernance.combinations}
      />
    </div>
  );
}
