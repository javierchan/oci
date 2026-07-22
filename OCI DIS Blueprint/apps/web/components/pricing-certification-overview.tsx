"use client";

import {
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  CircleDashed,
  FileCheck2,
  GitCompareArrows,
  Loader2,
  PackageCheck,
  Scale,
  ShieldCheck,
  Tags,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api, getErrorMessage } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import {
  PRICING_CERTIFICATION_STAGES,
  PRICING_CLASSIFICATIONS,
  nextPricingAction,
  type PricingWorkspaceView,
} from "@/lib/pricing-workspace";
import { commercialReleaseCoverage } from "@/lib/types";
import type {
  CommercialWorkspace,
  GovernanceChangeSet,
  ProductCoveragePage,
} from "@/lib/types";

interface PricingCertificationOverviewProps {
  sourceCount: number;
  approvedMappingCount: number;
  mappingCount: number;
  latestChangeSet: GovernanceChangeSet | undefined;
  onNavigate: (_view: PricingWorkspaceView) => void;
}

const EMPTY_COVERAGE: ProductCoveragePage = {
  products: [],
  page: 1,
  page_size: 1,
  total: 0,
};

function signalTone(ready: boolean): string {
  return ready
    ? "border-emerald-400/45 text-emerald-700 dark:text-emerald-300"
    : "border-amber-400/55 text-amber-800 dark:text-amber-300";
}

export function PricingCertificationOverview({
  sourceCount,
  approvedMappingCount,
  mappingCount,
  latestChangeSet,
  onNavigate,
}: PricingCertificationOverviewProps): JSX.Element {
  const [commercial, setCommercial] = useState<CommercialWorkspace | null>(null);
  const [coverage, setCoverage] = useState<ProductCoveragePage>(EMPTY_COVERAGE);
  const [approvedCoverageCount, setApprovedCoverageCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      api.getCommercialCatalog({ page: 1, page_size: 1, status: "all" }),
      api.listProductCoverage({ page: 1, page_size: 1, status: "all", readiness_status: "all" }),
      api.listProductCoverage({ page: 1, page_size: 1, status: "approved", readiness_status: "all" }),
    ])
      .then(([commercialResult, coverageResult, approvedResult]) => {
        if (!active) return;
        setCommercial(commercialResult);
        setCoverage(coverageResult);
        setApprovedCoverageCount(approvedResult.total);
        setError("");
      })
      .catch((caughtError) => {
        if (!active) return;
        setError(getErrorMessage(caughtError, "Unable to load the pricing certification summary."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const latestRelease = commercial?.releases[0];
  const releaseCoverage = latestRelease ? commercialReleaseCoverage(latestRelease) : null;
  const sourceReady = latestChangeSet?.validation_status === "passed";
  const evidenceApproved = commercial?.document?.status === "approved_evidence";
  const reviewReady = Boolean(
    commercial
    && commercial.summary.pending === 0
    && commercial.summary.exceptions === 0
    && commercial.summary.approved > 0,
  );
  const releaseReady = Boolean(latestRelease && approvedMappingCount > 0);
  const nextAction = useMemo(
    () => nextPricingAction({
      sourceCount,
      sourceValidationPassed: sourceReady,
      hasCommercialDocument: Boolean(commercial?.document),
      evidenceApproved,
      pendingDecisions: commercial?.summary.pending ?? 0,
      openExceptions: commercial?.summary.exceptions ?? 0,
      coverageTotal: coverage.total,
      coverageApproved: approvedCoverageCount,
      releaseCount: commercial?.releases.length ?? 0,
      approvedMappings: approvedMappingCount,
    }),
    [approvedCoverageCount, approvedMappingCount, commercial, coverage.total, evidenceApproved, sourceCount, sourceReady],
  );

  const signals = [
    {
      label: "Official evidence",
      value: sourceReady ? "Verified" : "Needs review",
      detail: latestChangeSet ? `${latestChangeSet.artifacts.length} source artifacts` : "No governed baseline",
      ready: sourceReady,
    },
    {
      label: "Product proposals",
      value: coverage.total ? `${formatNumber(approvedCoverageCount)} / ${formatNumber(coverage.total)}` : "Not generated",
      detail: "approved for BOM capability",
      ready: coverage.total > 0 && approvedCoverageCount === coverage.total,
    },
    {
      label: "SKU decisions",
      value: reviewReady ? "Complete" : `${formatNumber(commercial?.summary.pending ?? 0)} pending`,
      detail: `${formatNumber(commercial?.summary.exceptions ?? 0)} open exception(s)`,
      ready: reviewReady,
    },
    {
      label: "Published scope",
      value: releaseCoverage ? `${formatNumber(releaseCoverage.quoteReady)} quote-ready` : "No release",
      detail: `${formatNumber(approvedMappingCount)} of ${formatNumber(mappingCount)} App mappings approved`,
      ready: releaseReady,
    },
  ];

  const stageIcons = [FileCheck2, Tags, GitCompareArrows, BookOpenCheck, ShieldCheck, PackageCheck, Scale];

  return (
    <div className="min-w-0 space-y-5">
      {error ? <div role="alert" className="rounded-lg border border-rose-400/45 bg-[var(--color-surface-2)] p-4 text-sm text-rose-700 dark:text-rose-300">{error}</div> : null}

      <section className="app-card min-w-0 overflow-hidden" aria-labelledby="pricing-readiness-title">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-5">
          <div className="max-w-3xl">
            <p className="app-label">Commercial readiness</p>
            <h2 id="pricing-readiness-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Can governed OCI evidence produce a defensible BOM?</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">These signals follow the evidence from Oracle source material to the exact SKU mappings used by the deterministic pricing engine.</p>
          </div>
          {loading ? <span className="inline-flex items-center gap-2 text-sm text-[var(--color-text-secondary)]"><Loader2 className="h-4 w-4 animate-spin" />Loading readiness</span> : null}
        </div>
        <div className="grid gap-px bg-[var(--color-border)] sm:grid-cols-2 xl:grid-cols-4">
          {signals.map((signal) => (
            <div key={signal.label} className="bg-[var(--color-surface)] p-5">
              <div className="flex items-center gap-2">
                {signal.ready ? <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-300" /> : <CircleDashed className="h-4 w-4 text-amber-700 dark:text-amber-300" />}
                <p className="app-label">{signal.label}</p>
              </div>
              <p className={`mt-3 text-lg font-semibold ${signalTone(signal.ready)}`}>{signal.value}</p>
              <p className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">{signal.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="grid min-w-0 gap-4 border-y border-[var(--color-border)] py-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div>
          <p className="app-label">Next required action</p>
          <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{nextAction.title}</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">{nextAction.detail}</p>
        </div>
        <button type="button" className="app-button-primary gap-2" onClick={() => onNavigate(nextAction.view)}>
          {nextAction.label}<ArrowRight className="h-4 w-4" />
        </button>
      </section>

      <section className="app-card min-w-0 overflow-hidden" aria-labelledby="certification-path-title">
        <div className="border-b border-[var(--color-border)] px-5 py-5">
          <p className="app-label">Certification path</p>
          <h2 id="certification-path-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">How a SKU becomes safe to use in a BOM</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-[var(--color-text-secondary)]">A SKU identifies an Oracle commercial unit, but its existence alone does not make it quote-ready. Identity, pricing behavior, evidence quality, and explicit approval remain separate so the App cannot silently turn incomplete data into a customer commitment.</p>
        </div>
        <div className="grid gap-px bg-[var(--color-border)] sm:grid-cols-2 xl:grid-cols-7">
          {PRICING_CERTIFICATION_STAGES.map(({ label, detail, view }, index) => {
            const Icon = stageIcons[index];
            return (
            <button key={label} type="button" className="group flex min-h-40 flex-col items-stretch justify-start bg-[var(--color-surface)] p-4 text-left transition-colors hover:bg-[var(--color-surface-2)]" onClick={() => onNavigate(view)}>
              <div className="flex h-8 shrink-0 items-center justify-between gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-md border border-[var(--color-border)] text-[var(--color-accent)]"><Icon className="h-4 w-4" /></span>
                <span className="font-mono text-xs text-[var(--color-text-muted)]">0{index + 1}</span>
              </div>
              <p className="mt-4 text-sm font-semibold text-[var(--color-text-primary)]">{label}</p>
              <p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">{detail}</p>
            </button>
            );
          })}
        </div>
      </section>

      <section className="app-card min-w-0 overflow-hidden" aria-labelledby="classification-rationale-title">
        <div className="border-b border-[var(--color-border)] px-5 py-5">
          <p className="app-label">Why SKUs are separated</p>
          <h2 id="classification-rationale-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Different evidence requires different pricing decisions</h2>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-[var(--color-text-secondary)]">The categories describe how Oracle sells and measures each component. They are not quality grades. Keeping them distinct prevents a public unit price, a customer contract rate, a deployment input, and an included entitlement from being treated as interchangeable.</p>
        </div>
        <div className="grid gap-px bg-[var(--color-border)] md:grid-cols-2 xl:grid-cols-4">
          {PRICING_CLASSIFICATIONS.map(({ title, detail }, index) => (
            <div key={title} className="bg-[var(--color-surface)] p-5">
              <span className="font-mono text-xs text-[var(--color-text-muted)]">PATH {index + 1}</span>
              <h3 className="mt-3 text-base font-semibold text-[var(--color-text-primary)]">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">{detail}</p>
            </div>
          ))}
        </div>
        <details className="border-t border-[var(--color-border)] px-5 py-4">
          <summary className="cursor-pointer text-sm font-semibold text-[var(--color-text-primary)]">What remains deterministic, and what requires human approval?</summary>
          <div className="mt-3 grid gap-4 text-sm leading-6 text-[var(--color-text-secondary)] md:grid-cols-2">
            <p><strong className="text-[var(--color-text-primary)]">The App calculates:</strong> quantity transformations, increments, minimums, tiers, monthly periods, rates, and totals from persisted governed rules.</p>
            <p><strong className="text-[var(--color-text-primary)]">The reviewer decides:</strong> whether evidence is authoritative, an exception is acceptable, a product is BOM-ready, and a release may be published.</p>
          </div>
        </details>
      </section>
    </div>
  );
}
