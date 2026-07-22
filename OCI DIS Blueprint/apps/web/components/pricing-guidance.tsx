"use client";

import { HelpCircle } from "lucide-react";
import type { ReactNode } from "react";

import { PRICING_GLOSSARY, type PricingGlossaryKey } from "@/lib/pricing-workspace";
import type { CommercialCoverageReport } from "@/lib/types";
import { formatNumber } from "@/lib/format";

export function PricingTerm({ term, children }: { term: PricingGlossaryKey; children?: ReactNode }): JSX.Element {
  const glossary = PRICING_GLOSSARY[term];
  return (
    <span className="group relative inline-flex items-center gap-1">
      <span>{children ?? glossary.label}</span>
      <button type="button" aria-label={`Explain ${glossary.label}`} className="inline-flex h-5 w-5 items-center justify-center rounded-full text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]">
        <HelpCircle className="h-3.5 w-3.5" />
      </button>
      <span role="tooltip" className="pointer-events-none absolute left-0 top-full z-40 mt-2 hidden w-72 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-left text-xs font-normal leading-5 text-[var(--color-text-secondary)] shadow-lg group-hover:block group-focus-within:block">
        <strong className="block text-[var(--color-text-primary)]">{glossary.label}</strong>
        {glossary.definition}
      </span>
    </span>
  );
}

export function CoverageFunnel({ report }: { report: CommercialCoverageReport | null }): JSX.Element {
  if (!report) {
    return (
      <div className="rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-4 text-sm leading-6 text-[var(--color-text-secondary)]">
        Run Preview to see how the current candidates divide into quote-ready, customer-rate, input-required, and blocked paths. No records change during preview.
      </div>
    );
  }
  const segments = [
    { label: "Quote-ready", value: report.projected_direct_metered_approved, color: "bg-emerald-500" },
    { label: "Rate card required", value: report.projected_external_rate_card_approved, color: "bg-sky-500" },
    { label: "Input required", value: report.input_required_count, color: "bg-amber-500" },
    { label: "Blocked", value: report.projected_blocked, color: "bg-[var(--color-text-muted)]" },
  ];
  const evaluatedTotal = segments.reduce((sum, segment) => sum + segment.value, 0);
  const widthTotal = Math.max(1, evaluatedTotal);
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-[var(--color-text-primary)]"><PricingTerm term="candidate_funnel">Projected candidate paths</PricingTerm></p>
        <span className="text-xs text-[var(--color-text-muted)]">{formatNumber(evaluatedTotal)} candidates evaluated</span>
      </div>
      <div className="mt-3 flex h-3 overflow-hidden rounded-full bg-[var(--color-surface-3)]" aria-label="Commercial coverage funnel">
        {segments.map((segment) => segment.value > 0 ? <span key={segment.label} className={segment.color} style={{ width: `${(segment.value / widthTotal) * 100}%` }} title={`${segment.label}: ${segment.value}`} /> : null)}
      </div>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {segments.map((segment) => (
          <div key={segment.label} className="flex items-center justify-between gap-2 text-xs">
            <span className="flex min-w-0 items-center gap-2 text-[var(--color-text-secondary)]"><span className={`h-2.5 w-2.5 shrink-0 rounded-full ${segment.color}`} />{segment.label}</span>
            <strong className="text-[var(--color-text-primary)]">{formatNumber(segment.value)}</strong>
          </div>
        ))}
      </div>
      {report.dependent_entitlement_count > 0 ? <p className="mt-3 text-xs leading-5 text-[var(--color-text-muted)]">{formatNumber(report.dependent_entitlement_count)} dependent entitlement(s) remain governed outside independently priced paths.</p> : null}
    </div>
  );
}
