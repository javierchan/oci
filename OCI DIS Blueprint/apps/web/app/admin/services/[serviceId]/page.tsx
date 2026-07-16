/* Governed service product detail page. */

import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowRight, ExternalLink, Network, ShieldCheck } from "lucide-react";

import { Breadcrumb } from "@/components/breadcrumb";
import { ServiceVerificationAgentPanel } from "@/components/service-verification-agent-panel";
import { api, isApiErrorCode } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { ServiceInteroperabilityRule, ServiceLimit, ServiceProductDetail } from "@/lib/types";

function labelize(value: string | null | undefined): string {
  if (!value) {
    return "Not captured";
  }
  return value.replace(/_/g, " ");
}

function formatUnknownValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Not captured";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString("en-US") : value.toLocaleString("en-US", { maximumFractionDigits: 4 });
  }
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(formatUnknownValue).join(", ");
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, entry]) => `${labelize(key)}: ${formatUnknownValue(entry)}`)
      .join("; ");
  }
  return String(value);
}

function verificationTone(status: string): string {
  if (status === "verified") {
    return "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100";
  }
  if (status === "needs_attention") {
    return "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-100";
  }
  return "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100";
}

function splitText(value: string | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(/\n|;|\.\s+/)
    .map((item) => item.trim().replace(/\.$/, ""))
    .filter(Boolean);
}

function servicePeer(rule: ServiceInteroperabilityRule, serviceId: string): {
  direction: "Outbound" | "Inbound";
  peerId: string;
  peerName: string;
} {
  if (rule.source_service_id === serviceId) {
    return {
      direction: "Outbound",
      peerId: rule.target_service_id,
      peerName: rule.target_service_name,
    };
  }
  return {
    direction: "Inbound",
    peerId: rule.source_service_id,
    peerName: rule.source_service_name,
  };
}

function sortedLimits(limits: ServiceLimit[]): ServiceLimit[] {
  return [...limits].sort((left, right) => `${left.limit_type}:${left.limit_key}`.localeCompare(`${right.limit_type}:${right.limit_key}`));
}

function StatCard({ label, value }: { label: string; value: string | number }): JSX.Element {
  return (
    <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3">
      <p className="app-label">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{value}</p>
    </div>
  );
}

async function loadService(serviceId: string): Promise<ServiceProductDetail> {
  try {
    return await api.getServiceProduct(serviceId);
  } catch (error) {
    if (isApiErrorCode(error, "SERVICE_PRODUCT_NOT_FOUND")) {
      notFound();
    }
    throw error;
  }
}

export default async function AdminServiceDetailPage({
  params,
}: {
  params: Promise<{ serviceId: string }>;
}): Promise<JSX.Element> {
  const { serviceId } = await params;
  const service = await loadService(serviceId);
  const verificationJobs = await api.listServiceVerificationJobs({ limit: 10 }).catch(() => ({ jobs: [], total: 0 }));
  const latestServiceJob =
    verificationJobs.jobs.find((job) => job.services_checked.map(String).includes(service.service_id)) ?? null;
  const fitBullets = splitText(service.architectural_fit);
  const antiPatternBullets = splitText(service.anti_patterns);

  return (
    <div className="console-page">
      <section className="console-hero">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/admin/services" className="app-link inline-flex items-center gap-2 text-sm font-semibold">
              <ArrowLeft className="h-4 w-4" />
              Service Products
            </Link>
            <p className="mt-5 app-kicker">Admin Governance · Service Product</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">{service.name}</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
              {service.summary ?? "Governed product profile for architecture recommendations, limits, evidence, and interoperability."}
            </p>
            <div className="mt-4">
              <Breadcrumb
                items={[
                  { label: "Home", href: "/projects" },
                  { label: "Admin", href: "/admin" },
                  { label: "Service Products", href: "/admin/services" },
                  { label: service.service_id },
                ]}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${verificationTone(service.verification_status)}`}>
              {labelize(service.verification_status)}
            </span>
            <span className="app-theme-chip">{service.version}</span>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Limits" value={service.limits.length} />
        <StatCard label="Evidence Sources" value={service.evidence_sources.length} />
        <StatCard label="Interoperability Rules" value={service.interoperability_rules.length} />
        <StatCard label="SLA Uptime" value={service.sla_uptime_pct === null ? "Not captured" : `${service.sla_uptime_pct}%`} />
        <StatCard label="Commercial Meters" value={service.approved_mapping_count} />
      </section>

      <section className="app-card p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-4xl">
            <p className="app-label">Commercial Coverage</p>
            <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">How this product enters a governed BOM</h2>
            <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">{service.commercial_guidance}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="app-theme-chip">{labelize(service.commercial_classification)}</span>
            <span className="app-theme-chip">{labelize(service.commercial_readiness)}</span>
            <span className="app-theme-chip">{labelize(service.publication_policy)}</span>
          </div>
        </div>
        {service.commercial_required_inputs.length > 0 ? (
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {service.commercial_required_inputs.map((item) => (
              <div key={item} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">{item}</div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="min-w-0 space-y-4">
          <section className="app-card p-6">
            <div className="flex items-start gap-3">
              <Network className="mt-1 h-5 w-5 text-[var(--color-accent)]" />
              <div>
                <p className="app-label">Architecture Fit</p>
                <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">How this service should be used</h2>
              </div>
            </div>
            {fitBullets.length > 0 ? (
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {fitBullets.slice(0, 6).map((item) => (
                  <div key={item} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4 text-sm leading-6 text-[var(--color-text-secondary)]">
                    {item}
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-[var(--color-text-secondary)]">No architecture fit guidance has been captured yet.</p>
            )}
          </section>

          <section className="app-table-shell min-w-0">
            <div className="border-b border-[var(--color-border)] px-6 py-5">
              <p className="app-label">Maximums And Constraints</p>
              <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">Governed service limits</h2>
              <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
                These are product/service rules, not client business assumptions.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-left text-sm">
                <thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
                  <tr>
                    <th className="px-6 py-3">Limit</th>
                    <th className="px-6 py-3">Value</th>
                    <th className="px-6 py-3">Type</th>
                    <th className="px-6 py-3">Scope</th>
                    <th className="px-6 py-3">Confidence</th>
                    <th className="px-6 py-3">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {sortedLimits(service.limits).map((limit) => (
                    <tr key={limit.id}>
                      <td className="px-6 py-4">
                        <p className="font-semibold text-[var(--color-text-primary)]">{limit.label}</p>
                        <p className="mt-1 font-mono text-xs text-[var(--color-text-muted)]">{limit.limit_key}</p>
                      </td>
                      <td className="px-6 py-4 font-semibold text-[var(--color-text-primary)]">
                        {formatUnknownValue(limit.value)}
                        {limit.unit ? <span className="ml-1 text-[var(--color-text-muted)]">{limit.unit}</span> : null}
                      </td>
                      <td className="px-6 py-4 text-[var(--color-text-secondary)]">{labelize(limit.limit_type)}</td>
                      <td className="px-6 py-4 text-[var(--color-text-secondary)]">{labelize(limit.scope)}</td>
                      <td className="px-6 py-4 text-[var(--color-text-secondary)]">{Math.round(limit.confidence * 100)}%</td>
                      <td className="px-6 py-4">
                        {limit.source_url ? (
                          <a href={limit.source_url} className="app-link inline-flex items-center gap-1" target="_blank" rel="noreferrer">
                            Source <ExternalLink className="h-3 w-3" />
                          </a>
                        ) : (
                          <span className="text-[var(--color-text-muted)]">Pending</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {service.limits.length === 0 ? (
                    <tr>
                      <td className="px-6 py-8 text-sm text-[var(--color-text-secondary)]" colSpan={6}>
                        No normalized limits have been captured for this service.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <section className="app-card p-6">
            <p className="app-label">Anti-Patterns</p>
            <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">Where recommendations should be cautious</h2>
            {antiPatternBullets.length > 0 ? (
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {antiPatternBullets.slice(0, 6).map((item) => (
                  <div key={item} className="rounded-2xl border border-[var(--color-qa-pendiente-border)] bg-[var(--color-qa-pendiente-bg)] p-4 text-sm leading-6 text-[var(--color-qa-pendiente-text)]">
                    {item}
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-[var(--color-text-secondary)]">No anti-pattern guidance has been captured yet.</p>
            )}
          </section>
        </div>

        <aside className="min-w-0 space-y-4">
          <ServiceVerificationAgentPanel initialJob={latestServiceJob} scopeServiceId={service.service_id} />

          <section className="app-card p-5">
            <p className="app-label">Product Metadata</p>
            <div className="mt-4 space-y-3 text-sm">
              <div className="flex justify-between gap-4">
                <span className="text-[var(--color-text-muted)]">Service ID</span>
                <span className="font-mono text-[var(--color-text-primary)]">{service.service_id}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-[var(--color-text-muted)]">Category</span>
                <span className="text-right text-[var(--color-text-primary)]">{labelize(service.category)}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-[var(--color-text-muted)]">Pricing</span>
                <span className="text-right text-[var(--color-text-primary)]">{labelize(service.pricing_model)}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-[var(--color-text-muted)]">Last updated</span>
                <span className="text-right text-[var(--color-text-primary)]">{formatDate(service.updated_at)}</span>
              </div>
            </div>
          </section>

          <section className="app-card p-5">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-1 h-5 w-5 text-[var(--color-accent)]" />
              <div>
                <p className="app-label">Evidence</p>
                <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Trusted sources</h2>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              {service.evidence_sources.map((source) => (
                <a
                  key={source.id}
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="block rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4 transition hover:border-[var(--color-accent)]"
                >
                  <p className="text-sm font-semibold text-[var(--color-text-primary)]">{source.title}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.14em] text-[var(--color-text-muted)]">
                    {source.publisher} · {labelize(source.status)}
                  </p>
                  <p className="mt-2 text-xs text-[var(--color-text-muted)]">
                    Expected check every {source.expected_update_frequency_days} days
                  </p>
                </a>
              ))}
              {service.evidence_sources.length === 0 ? (
                <p className="text-sm text-[var(--color-text-secondary)]">No trusted evidence sources have been registered yet.</p>
              ) : null}
            </div>
          </section>
        </aside>
      </section>

      <section className="app-table-shell min-w-0">
        <div className="border-b border-[var(--color-border)] px-6 py-5">
          <p className="app-label">Interoperability</p>
          <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">Supported service routes</h2>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
            Routes describe service compatibility. Integration patterns remain tool-agnostic and can map to different service stacks.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[960px] text-left text-sm">
            <thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
              <tr>
                <th className="px-6 py-3">Direction</th>
                <th className="px-6 py-3">Peer Service</th>
                <th className="px-6 py-3">Relationship</th>
                <th className="px-6 py-3">Patterns</th>
                <th className="px-6 py-3">Constraints</th>
                <th className="px-6 py-3">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {service.interoperability_rules.map((rule) => {
                const peer = servicePeer(rule, service.service_id);
                return (
                  <tr key={rule.id}>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] px-3 py-1 text-xs font-semibold text-[var(--color-text-primary)]">
                        {peer.direction === "Outbound" ? <ArrowRight className="h-3 w-3" /> : <ArrowLeft className="h-3 w-3" />}
                        {peer.direction}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <p className="font-semibold text-[var(--color-text-primary)]">{peer.peerName}</p>
                      <p className="mt-1 font-mono text-xs text-[var(--color-text-muted)]">{peer.peerId}</p>
                    </td>
                    <td className="px-6 py-4 text-[var(--color-text-secondary)]">{labelize(rule.relationship_type)}</td>
                    <td className="px-6 py-4 font-mono text-xs text-[var(--color-text-secondary)]">{rule.patterns.map(formatUnknownValue).join(", ")}</td>
                    <td className="px-6 py-4 text-[var(--color-text-secondary)]">{formatUnknownValue(rule.constraints)}</td>
                    <td className="px-6 py-4">
                      {rule.source_url ? (
                        <a href={rule.source_url} className="app-link inline-flex items-center gap-1" target="_blank" rel="noreferrer">
                          Source <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : (
                        <span className="text-[var(--color-text-muted)]">Pending</span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {service.interoperability_rules.length === 0 ? (
                <tr>
                  <td className="px-6 py-8 text-sm text-[var(--color-text-secondary)]" colSpan={6}>
                    No interoperability rules have been captured for this service.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
