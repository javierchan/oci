/* Governed service product library overview. */

import Link from "next/link";
import { AlertTriangle, ArrowRight, CheckCircle2, ExternalLink, Network } from "lucide-react";

import { Breadcrumb } from "@/components/breadcrumb";
import { ServiceVerificationAgentPanel } from "@/components/service-verification-agent-panel";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";

function verificationTone(status: string): string {
  if (status === "verified") {
    return "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100";
  }
  if (status === "needs_attention") {
    return "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-100";
  }
  return "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100";
}

function compactCategory(value: string): string {
  return value.replace(/_/g, " ").toLowerCase();
}

export default async function AdminServicesPage(): Promise<JSX.Element> {
  const [serviceProducts, matrix, verificationJobs, verificationAlerts] = await Promise.all([
    api.listServiceProducts(),
    api.getServiceInteroperabilityMatrix(),
    api.listServiceVerificationJobs({ limit: 5 }).catch(() => ({ jobs: [], total: 0 })),
    api.listServiceVerificationAlerts({ limit: 6 }).catch(() => ({
      alerts: [],
      total: 0,
      open_findings_count: 0,
      stale_evidence_count: 0,
    })),
  ]);
  const latestVerificationJob = verificationJobs.jobs[0] ?? null;

  return (
    <div className="console-page">
      <section className="console-hero">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="app-kicker">Admin Governance · Service Products</p>
            <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
              Service Product Library
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Govern OCI service descriptions, hard limits, interoperability rules, and official evidence freshness separately from client assumptions.
            </p>
            <div className="mt-4">
              <Breadcrumb
                items={[
                  { label: "Home", href: "/projects" },
                  { label: "Admin", href: "/admin" },
                  { label: "Service Products" },
                ]}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:min-w-[24rem]">
            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3">
              <p className="app-label">Products</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)]">{serviceProducts.total}</p>
            </div>
            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3">
              <p className="app-label">Matrix Rules</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)]">{matrix.total_rules}</p>
            </div>
            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3">
              <p className="app-label">Pending Evidence</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)]">
                {serviceProducts.stale_evidence_count}
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3">
              <p className="app-label">Open Findings</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--color-text-primary)]">
                {verificationAlerts.open_findings_count}
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {serviceProducts.products.map((service) => (
            <Link
              key={service.service_id}
              href={`/admin/services/${service.service_id}`}
              className="app-card group flex min-h-[17rem] flex-col p-5 transition hover:-translate-y-0.5 hover:border-[var(--color-accent)] hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-4">
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-3)] text-[var(--color-accent)]">
                  <Network className="h-5 w-5" />
                </span>
                <span className={`rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${verificationTone(service.verification_status)}`}>
                  {service.verification_status.replace(/_/g, " ")}
                </span>
              </div>
              <p className="mt-5 app-label">{compactCategory(service.category)}</p>
              <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">{service.name}</h2>
              <p className="mt-3 line-clamp-3 text-sm leading-6 text-[var(--color-text-secondary)]">
                {service.summary ?? "No architecture summary has been captured yet."}
              </p>
              <div className="mt-4 grid grid-cols-3 gap-2 text-xs text-[var(--color-text-secondary)]">
                <span>{service.limits_count} limits</span>
                <span>{service.interoperability_count} rules</span>
                <span>{service.evidence_count} sources</span>
              </div>
              <span className="mt-auto inline-flex items-center gap-2 pt-5 text-sm font-semibold text-[var(--color-accent)]">
                Open product
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              </span>
            </Link>
          ))}
        </div>

        <aside className="space-y-4">
          <ServiceVerificationAgentPanel initialJob={latestVerificationJob} />

          <section className="app-card p-5">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-1 h-5 w-5 text-[var(--color-accent)]" />
              <div>
                <p className="app-label">Verification Alerts</p>
                <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Review queue</h2>
              </div>
            </div>
            <div className="mt-4 space-y-3">
              {verificationAlerts.alerts.slice(0, 4).map((alert) => (
                <div key={alert.id} className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-semibold text-[var(--color-text-primary)]">{alert.title}</p>
                    <span className="font-mono text-xs text-[var(--color-text-muted)]">{alert.service_id ?? "Library"}</span>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{alert.summary}</p>
                  <p className="mt-2 text-xs text-[var(--color-text-muted)]">{formatDate(alert.created_at)}</p>
                </div>
              ))}
              {verificationAlerts.alerts.length === 0 ? (
                <div className="flex items-start gap-2 rounded-2xl border border-emerald-300 bg-emerald-50 p-4 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100">
                  <CheckCircle2 className="mt-0.5 h-4 w-4" />
                  No verification alerts are open.
                </div>
              ) : null}
            </div>
          </section>

          <section className="app-card p-5">
            <p className="app-label">Assumption Boundary</p>
            <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Rules vs assumptions</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
              Service limits belong here. Client-specific unknowns such as business hours, growth multipliers, retention, and peak concentration stay in Assumptions.
            </p>
          </section>
        </aside>
      </section>

      <section className="app-table-shell">
        <div className="border-b border-[var(--color-border)] px-6 py-5">
          <p className="app-label">Interoperability Matrix</p>
          <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">Supported service routes</h2>
          <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
            Initial matrix rules are seeded from governed product profiles and are pending external source verification.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-[0.16em] text-[var(--color-text-muted)]">
              <tr>
                <th className="px-6 py-3">Source</th>
                <th className="px-6 py-3">Target</th>
                <th className="px-6 py-3">Relationship</th>
                <th className="px-6 py-3">Patterns</th>
                <th className="px-6 py-3">Confidence</th>
                <th className="px-6 py-3">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {matrix.rules.slice(0, 12).map((rule) => (
                <tr key={rule.id}>
                  <td className="px-6 py-4 font-semibold text-[var(--color-text-primary)]">{rule.source_service_id}</td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{rule.target_service_id}</td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{rule.relationship_type.replace(/_/g, " ")}</td>
                  <td className="px-6 py-4 font-mono text-xs text-[var(--color-text-secondary)]">
                    {rule.patterns.map(String).join(", ")}
                  </td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{Math.round(rule.confidence * 100)}%</td>
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
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {serviceProducts.stale_evidence_count > 0 ? (
        <section className="app-card border-[var(--color-qa-revisar-border)] bg-[var(--color-qa-revisar-bg)] p-5">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-1 h-5 w-5 text-[var(--color-qa-revisar-text)]" />
            <div>
              <p className="app-label text-[var(--color-qa-revisar-text)]">Next slice</p>
              <p className="mt-2 text-sm leading-6 text-[var(--color-qa-revisar-text)]">
                Evidence is seeded but not externally verified yet. The execute agent should fetch allowlisted Oracle sources, compute content hashes, and create review findings before rules are changed.
              </p>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
