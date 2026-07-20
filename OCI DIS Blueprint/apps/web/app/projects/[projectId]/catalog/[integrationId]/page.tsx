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
import type {
  AuditEvent,
  CanvasServiceProfile,
  Integration,
  ServiceLimit,
  ServiceProductDetail,
} from "@/lib/types";

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
  idempotency: "Idempotency",
  business_criticality: "Business criticality",
  target_latency_sla: "SLA / target latency",
  data_security_classification: "Data classification",
  retention_processing_window: "Retention / processing window",
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
  PATTERN_NOT_CERTIFIED: {
    title: "Pattern is not certified",
    hint: "Select a certified system pattern or publish a versioned certification contract before treating this architecture as ready.",
  },
  PATTERN_CORE_TOOLS_NOT_CERTIFIED: {
    title: "Core tools do not match the pattern certification",
    hint: "Open the Integration Design Canvas and use one of the certified core-tool compositions documented for this pattern.",
  },
  PATTERN_OVERLAYS_NOT_CERTIFIED: {
    title: "Required architectural overlays are missing",
    hint: "Open the Integration Design Canvas and add the identity, API, storage, catalog, observability, AI, or mesh overlays required by this certification.",
  },
  MISSING_PAYLOAD: {
    title: "Payload evidence missing",
    hint: "Forecast metrics stay low confidence until Payload KB is captured from the source workbook or architect review.",
  },
  MISSING_FAN_OUT_TARGETS: {
    title: "Fan-out targets missing",
    hint: "This integration is marked as fan-out, but the downstream target count is still missing or incomplete.",
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
  BATCH_WINDOW_REQUIRED: {
    title: "Batch window not defined",
    hint: "Scheduled Batch requires a processing window, retention, and reprocessing expectation before approval.",
  },
  TARGET_LATENCY_REQUIRED: {
    title: "Target latency not defined",
    hint: "Define the expected completion time or callback SLA so the asynchronous design can be validated.",
  },
  RETRY_POLICY_REQUIRED: {
    title: "Retry policy not defined",
    hint: "Specify bounded attempts, backoff, terminal handling, and DLQ ownership for this pattern.",
  },
  IDEMPOTENCY_REQUIRED: {
    title: "Idempotency control not defined",
    hint: "Document the deduplication key and retention window before enabling retries or replay.",
  },
  RETENTION_POLICY_REQUIRED: {
    title: "Payload retention not defined",
    hint: "Claim Check requires an explicit object lifecycle, access expiry, and orphan-cleanup policy.",
  },
  DATA_CLASSIFICATION_REQUIRED: {
    title: "Data classification not defined",
    hint: "Classify the payload so encryption, access, retention, and audit controls can be reviewed.",
  },
  BUSINESS_CRITICALITY_REQUIRED: {
    title: "Business criticality not defined",
    hint: "Classify the business impact so resilience, recovery, and operating controls can be validated against the pattern certification.",
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
  "Business Criticality",
  "Status",
  "Mapping Status",
  "Initial Scope",
  "Complexity",
  "Frequency",
  "Type",
  "Base",
  "Interface Status",
  "Real Time",
  "SLA / Target Latency",
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
  "Data / Security Classification",
  "Calendarization",
  "Retention / Processing Window",
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

  return signals;
}

function buildCanvasLimitMap(limits: ServiceLimit[]): Record<string, unknown> {
  return Object.fromEntries(
    limits
      .filter((limit) => limit.is_active)
      .map((limit) => [limit.limit_key, limit.value]),
  );
}

function buildCanvasLimitDefinitionMap(limits: ServiceLimit[]): Record<string, ServiceLimit> {
  return Object.fromEntries(
    limits
      .filter((limit) => limit.is_active)
      .map((limit) => [limit.limit_key, limit]),
  );
}

function toCanvasServiceProfile(product: ServiceProductDetail): CanvasServiceProfile {
  return {
    id: product.id,
    service_id: product.service_id,
    name: product.name,
    category: product.category,
    sla_uptime_pct: product.sla_uptime_pct,
    pricing_model: product.pricing_model,
    limits: buildCanvasLimitMap(product.limits),
    limit_definitions: buildCanvasLimitDefinitionMap(product.limits),
    summary: product.summary,
    architecture_role: product.architecture_role,
  };
}

async function loadCanvasServiceProfiles(): Promise<CanvasServiceProfile[]> {
  const productList = await api.listServiceProducts().catch(() => ({
    products: [],
    total: 0,
    stale_evidence_count: 0,
    open_findings_count: 0,
  }));
  const productDetails = await Promise.all(
    productList.products.map((product) =>
      api.getServiceProduct(product.service_id).catch(() => null),
    ),
  );
  return productDetails
    .filter((product): product is ServiceProductDetail => product !== null)
    .map(toCanvasServiceProfile);
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
  const [detail, patterns, canvasGovernance, integrationAudit, sourceRowAudit, serviceProfiles] = await Promise.all([
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
    loadCanvasServiceProfiles(),
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
            <h1 className="mt-2 break-words text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
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
            <AiReviewButton
              projectId={projectId}
              integrationId={integrationId}
              defaultScope="integration"
              label="Review integration"
            />
            <QaBadge status={integration.qa_status} />
          </div>
        </div>
      </section>

      <section className="grid min-w-0 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="app-card min-w-0 p-5">
          <p className="app-label">Route</p>
          <p className="mt-3 break-words text-sm font-semibold text-[var(--color-text-primary)]">
            {integration.source_system ?? "Unknown source"}
          </p>
          <p className="my-2 text-lg font-semibold text-[var(--color-accent)]">→</p>
          <p className="break-words text-sm font-semibold text-[var(--color-text-primary)]">
            {integration.destination_system ?? "Unknown destination"}
          </p>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">
            {displayUiValue(integration.source_technology)} to{" "}
            {displayUiValue(integration.destination_technology_1)}
          </p>
        </article>

        <article className="app-card min-w-0 p-5">
          <p className="app-label">Pattern</p>
          <p className="mt-3 break-words text-lg font-semibold text-[var(--color-text-primary)]">
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

        <article className="app-card min-w-0 p-5">
          <p className="app-label">Volumetry</p>
          <p className="mt-3 text-2xl font-semibold text-[var(--color-text-primary)]">
            {formatNumber(integration.payload_per_execution_kb, 1)} KB
          </p>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
            {displayUiValue(integration.frequency)} · {formatNumber(integration.executions_per_day, 1)} exec/day
          </p>
        </article>

        <article className="app-card min-w-0 p-5">
          <p className="app-label">Governance</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <QaBadge status={integration.qa_status} />
            <ComplexityBadge value={integration.complexity} />
            <span className="app-theme-chip">
              {integration.commercially_eligible ? "BOM eligible" : "Technical only"}
            </span>
          </div>
          <p className="mt-3 text-xs text-[var(--color-text-muted)]">
            {auditEvents.length} audit event{auditEvents.length === 1 ? "" : "s"} ·{" "}
            {integration.qa_reasons.length} QA reason{integration.qa_reasons.length === 1 ? "" : "s"}
          </p>
          {!integration.commercially_eligible ? (
            <p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">
              TBQ=N keeps this integration in architecture governance while excluding it from BOM and pricing.
            </p>
          ) : null}
        </article>
      </section>

      <div className="grid min-w-0 items-start gap-8 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <section className="min-w-0 space-y-6">
          <article className="app-card min-w-0 overflow-hidden p-5 sm:p-6">
            <p className="app-label">Source Data</p>
            <dl className="mt-5">
              <div className="grid min-w-0 gap-4 md:grid-cols-2">
                <div className="min-w-0">
                  <dt className="app-label">Interface ID</dt>
                  <dd className="mt-2 break-words font-mono text-sm font-medium text-[var(--color-text-primary)]">{integration.interface_id ?? "—"}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Interface Name</dt>
                  <dd className="mt-2 break-words text-sm font-medium text-[var(--color-text-primary)]">
                    {integration.interface_name ?? "—"}
                  </dd>
                </div>
              </div>

              <div className="mt-4 grid min-w-0 gap-4 border-t border-[var(--color-border)] pt-4 md:grid-cols-3">
                <div className="min-w-0">
                  <dt className="app-label">Brand</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{integration.brand ?? "—"}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Business Process</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{integration.business_process ?? "—"}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Status</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.status)}</dd>
                </div>
              </div>

              <div className="mt-4 grid min-w-0 gap-4 border-t border-[var(--color-border)] pt-4 md:grid-cols-2 lg:grid-cols-4">
                <div className="min-w-0">
                  <dt className="app-label">Source System</dt>
                  <dd className="mt-2 break-words text-sm font-medium text-[var(--color-text-primary)]">{integration.source_system ?? "—"}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Destination System</dt>
                  <dd className="mt-2 break-words text-sm font-medium text-[var(--color-text-primary)]">{integration.destination_system ?? "—"}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Frequency</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.frequency)}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Payload / Execution</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">
                    {formatNumber(integration.payload_per_execution_kb, 1)} KB
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Type</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.type)}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Complexity</dt>
                  <dd className="mt-2"><ComplexityBadge value={integration.complexity} /></dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Initial Scope</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.initial_scope)}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Business Criticality</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.business_criticality)}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">SLA / Target Latency</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.target_latency_sla)}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Data Classification</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.data_security_classification)}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Retention / Processing Window</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.retention_processing_window)}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Retry Policy</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.retry_policy)}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="app-label">Idempotency</dt>
                  <dd className="mt-2 break-words text-sm text-[var(--color-text-secondary)]">{displayUiValue(integration.idempotency)}</dd>
                </div>
              </div>
            </dl>
          </article>

          <article className="app-card min-w-0 overflow-hidden p-5 sm:p-6">
            <p className="app-label">Source Lineage</p>
            <div className="mt-5 grid min-w-0 gap-4 md:grid-cols-2">
              <div className="app-card-muted min-w-0 p-4">
                <p className="app-label">Source Row Number</p>
                <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{lineage.source_row_number}</p>
              </div>
              <div className="app-card-muted min-w-0 p-4">
                <p className="app-label">Import Batch</p>
                <p className="mt-2 break-words text-sm font-medium text-[var(--color-text-primary)]">{lineage.import_filename}</p>
              </div>
            </div>

            <div className="app-card-muted mt-6 min-w-0 overflow-hidden p-4">
              <p className="app-label">Raw Column Values</p>
              <RawColumnValuesTable
                projectId={projectId}
                integrationId={integrationId}
                initialValues={lineage.raw_data}
                columnNames={lineage.column_names}
              />
            </div>

            <div className="app-card-muted mt-6 min-w-0 overflow-hidden p-4">
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

        <aside className="min-w-0 space-y-8">
          <IntegrationPatchForm
            projectId={projectId}
            integration={integration}
            patterns={patterns.patterns}
            toolOptions={canvasGovernance.tools}
            overlayOptions={canvasGovernance.overlays}
            combinations={canvasGovernance.combinations}
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
                    className="rounded-2xl border border-sky-200 border-l-4 bg-sky-50 p-4 dark:border-[#64d2ff]/45 dark:bg-[var(--color-surface-2)]"
                  >
                    <p className="font-semibold text-sky-950 dark:text-[#64d2ff]">{signal.title}</p>
                    <p className="mt-2 text-sm leading-6 text-sky-900 dark:text-[var(--color-text-secondary)]">{signal.detail}</p>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {selectedPatternDefinition ? (
            <section className="app-card p-6">
              <p className="app-label">Pattern Certification</p>
              <div className="mt-4 space-y-3">
                <PatternSupportBadge support={selectedPatternDefinition.support} />
                <p className="text-sm leading-6 text-[var(--color-text-secondary)]">
                  {selectedPatternDefinition.support.summary}
                </p>
                {selectedPatternDefinition.support.certification_version ? (
                  <div className="grid gap-4 border-y border-[var(--color-border)] py-4 sm:grid-cols-2">
                    <div>
                      <p className="app-label">Contract</p>
                      <p className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">
                        v{selectedPatternDefinition.support.certification_version} · {selectedPatternDefinition.support.sizing_strategy?.replaceAll("_", " ")}
                      </p>
                    </div>
                    <div>
                      <p className="app-label">Required Evidence</p>
                      <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                        {selectedPatternDefinition.support.required_evidence
                          .map((item) => item.replaceAll("_", " "))
                          .join(" · ") || "No additional evidence"}
                      </p>
                    </div>
                  </div>
                ) : null}
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
        serviceProfiles={serviceProfiles}
        toolOptions={canvasGovernance.tools}
        overlayOptions={canvasGovernance.overlays}
        combinations={canvasGovernance.combinations}
      />
    </div>
  );
}
