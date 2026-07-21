"use client";

/* Governed review queue that promotes captured OCI products into BOM capability contracts. */

import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  RefreshCcw,
  Search,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { emitToast } from "@/hooks/use-toast";
import { api, getErrorMessage } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type {
  ProductCoverageDetail,
  ProductCoverageGeneration,
  ProductCoveragePage,
  ProductCoverageRow,
} from "@/lib/types";

const EMPTY_PAGE: ProductCoveragePage = { products: [], page: 1, page_size: 50, total: 0 };

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function readinessPresentation(product: ProductCoverageRow): {
  label: string;
  className: string;
  Icon: typeof CheckCircle2;
} {
  if (product.status === "approved") {
    return {
      label: "Approved for BOM",
      className: "border-emerald-400/45 text-emerald-700 dark:text-emerald-300",
      Icon: CheckCircle2,
    };
  }
  if (product.status === "rejected") {
    return {
      label: "Rejected",
      className: "border-rose-400/45 text-rose-700 dark:text-rose-300",
      Icon: XCircle,
    };
  }
  if (product.readiness_status === "ready") {
    if (product.commercial_readiness === "rate_card_required") {
      return {
        label: "Ready · rate card required",
        className: "border-amber-400/55 text-amber-800 dark:text-amber-300",
        Icon: ShieldCheck,
      };
    }
    return {
      label: "Ready for review",
      className: "border-emerald-400/45 text-emerald-700 dark:text-emerald-300",
      Icon: CheckCircle2,
    };
  }
  return {
    label: product.readiness_status === "blocked_release" ? "Blocked by release" : "Blocked by evidence",
    className: "border-amber-400/55 text-amber-800 dark:text-amber-300",
    Icon: AlertTriangle,
  };
}

export function OciCoverageReview(): JSX.Element {
  const [coverage, setCoverage] = useState<ProductCoveragePage>(EMPTY_PAGE);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [readiness, setReadiness] = useState("all");
  const [page, setPage] = useState(1);
  const [details, setDetails] = useState<Record<string, ProductCoverageDetail>>({});
  const [rationales, setRationales] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [generation, setGeneration] = useState<ProductCoverageGeneration | null>(null);

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      const result = await api.listProductCoverage({
        page,
        page_size: 50,
        search: query.trim() || undefined,
        status,
        readiness_status: readiness,
      });
      setCoverage(result);
      setError("");
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to load OCI coverage proposals."));
    } finally {
      setLoading(false);
    }
  }, [page, query, readiness, status]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), query.trim() ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [load, query]);

  async function generate(): Promise<void> {
    setBusy("generate");
    try {
      const result = await api.generateProductCoverage();
      setGeneration(result);
      setDetails({});
      await load();
      emitToast("success", `Coverage refreshed for ${formatNumber(result.total)} OCI products.`);
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to generate OCI coverage proposals."));
    } finally {
      setBusy(null);
    }
  }

  async function loadDetail(productKey: string): Promise<void> {
    if (details[productKey] || busy === `detail:${productKey}`) return;
    setBusy(`detail:${productKey}`);
    try {
      const detail = await api.getProductCoverage(productKey);
      setDetails((current) => ({ ...current, [productKey]: detail }));
      setRationales((current) => ({
        ...current,
        [productKey]: current[productKey] ?? detail.review_rationale ?? "",
      }));
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to load the coverage proposal."));
    } finally {
      setBusy(null);
    }
  }

  async function review(productKey: string, decision: "approve" | "reject"): Promise<void> {
    const rationale = rationales[productKey]?.trim() ?? "";
    if (rationale.length < 8) {
      emitToast("error", "Add a review rationale of at least 8 characters.");
      return;
    }
    setBusy(`${decision}:${productKey}`);
    try {
      const updated = await api.reviewProductCoverage(productKey, { decision, rationale });
      setDetails((current) => ({ ...current, [productKey]: updated }));
      await load();
      emitToast("success", decision === "approve" ? "Product approved for governed BOM use." : "Product proposal rejected.");
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to record the coverage decision."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="app-table-shell min-w-0 overflow-hidden" aria-labelledby="oci-coverage-title">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-5">
        <div className="max-w-3xl">
          <p className="app-label">Governed product activation</p>
          <h2 id="oci-coverage-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
            OCI BOM Coverage
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            Generate reviewable capability, policy, and SKU mapping proposals for every captured OCI product. A product becomes quoteable only after its release, pricing rules, fixtures, and human approval are complete.
          </p>
        </div>
        <button className="app-button-primary gap-2" type="button" disabled={busy !== null} onClick={() => void generate()}>
          {busy === "generate" ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
          Generate / Refresh
        </button>
      </div>

      {generation ? (
        <div className="grid gap-px border-b border-[var(--color-border)] bg-[var(--color-border)] sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Products evaluated", generation.total],
            ["Ready", generation.ready],
            ["Release blocked", generation.blocked_release],
            ["Evidence blocked", generation.blocked_evidence],
          ].map(([label, value]) => (
            <div key={String(label)} className="bg-[var(--color-surface)] px-5 py-4">
              <p className="app-label">{label}</p>
              <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{formatNumber(Number(value))}</p>
            </div>
          ))}
        </div>
      ) : null}

      <div className="grid gap-3 border-b border-[var(--color-border)] px-5 py-4 md:grid-cols-[minmax(0,1fr)_12rem_13rem]">
        <label className="relative block min-w-0">
          <span className="sr-only">Search OCI coverage</span>
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-[var(--color-text-muted)]" />
          <input
            aria-label="Search OCI coverage"
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] py-2.5 pl-9 pr-3 text-sm"
            placeholder="Search product or category"
            value={query}
            onChange={(event) => { setQuery(event.target.value); setPage(1); }}
          />
        </label>
        <select aria-label="Filter review status" className="app-select" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
          <option value="all">All decisions</option>
          <option value="pending_review">Pending review</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
        <select aria-label="Filter readiness" className="app-select" value={readiness} onChange={(event) => { setReadiness(event.target.value); setPage(1); }}>
          <option value="all">All readiness states</option>
          <option value="ready">Ready</option>
          <option value="blocked_release">Blocked by release</option>
          <option value="blocked_evidence">Blocked by evidence</option>
        </select>
      </div>

      {error ? <div role="alert" className="border-b border-rose-400/45 px-5 py-4 text-sm text-rose-700 dark:text-rose-300">{error}</div> : null}

      <div className="divide-y divide-[var(--color-border)]">
        {coverage.products.map((product) => {
          const presentation = readinessPresentation(product);
          const detail = details[product.product_key];
          const rationale = rationales[product.product_key] ?? "";
          return (
            <details key={product.product_key} className="group" onToggle={(event) => {
              if (event.currentTarget.open) void loadDetail(product.product_key);
            }}>
              <summary className="grid cursor-pointer list-none gap-3 px-5 py-4 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-center">
                <div className="min-w-0">
                  <h3 className="break-words text-sm font-semibold text-[var(--color-text-primary)]">{product.product_name}</h3>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">{product.category ?? "Category not captured"}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-[var(--color-text-secondary)]">
                  <span>{formatNumber(product.sku_count)} SKUs</span>
                  <span>{formatNumber(product.mapping_count)} proposed mappings</span>
                  <span>{formatNumber(product.blocker_count)} blockers</span>
                </div>
                <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${presentation.className}`}>
                  <presentation.Icon className="h-3.5 w-3.5" />
                  {presentation.label}
                </span>
              </summary>

              {busy === `detail:${product.product_key}` && !detail ? (
                <div className="flex items-center gap-2 border-t border-[var(--color-border)] px-5 py-5 text-sm text-[var(--color-text-secondary)]">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading governed proposal...
                </div>
              ) : null}

              {detail ? (
                <div className="border-t border-[var(--color-border)] bg-[var(--color-surface-2)] px-5 py-5">
                  <div className="grid gap-5 lg:grid-cols-[minmax(0,0.75fr)_minmax(0,1.25fr)]">
                    <div className="min-w-0 space-y-5">
                      <div>
                        <p className="app-label">Proposed service contract</p>
                        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                          <div><dt className="text-[var(--color-text-muted)]">Service ID</dt><dd className="mt-1 break-all font-mono text-xs text-[var(--color-text-primary)]">{detail.proposed_service_id}</dd></div>
                          <div><dt className="text-[var(--color-text-muted)]">Pricing model</dt><dd className="mt-1 text-[var(--color-text-primary)]">{String(detail.proposed_profile.pricing_model ?? "Not established")}</dd></div>
                          <div><dt className="text-[var(--color-text-muted)]">Classification</dt><dd className="mt-1 text-[var(--color-text-primary)]">{humanize(String(detail.proposed_policy.classification ?? "unclassified"))}</dd></div>
                          <div><dt className="text-[var(--color-text-muted)]">Generator</dt><dd className="mt-1 font-mono text-xs text-[var(--color-text-primary)]">{detail.generator_version}</dd></div>
                        </dl>
                      </div>
                      {detail.commercial_readiness === "rate_card_required" ? (
                        <div className="rounded-lg border border-amber-400/45 bg-amber-500/5 p-4 text-sm leading-6 text-[var(--color-text-secondary)]">
                          <p className="font-semibold text-amber-800 dark:text-amber-300">Customer rate card required at quote time</p>
                          <p className="mt-1">The product definition and quantity rules are ready. A BOM can price these SKUs only when the selected approved customer rate card contains an exact part-number match.</p>
                        </div>
                      ) : null}
                      <div>
                        <p className="app-label">Readiness blockers</p>
                        {detail.readiness_blockers.length ? (
                          <ul className="mt-3 space-y-2">
                            {detail.readiness_blockers.slice(0, 25).map((blocker, index) => (
                              <li key={`${blocker.part_number ?? "product"}-${blocker.code}-${index}`} className="text-sm leading-5 text-[var(--color-text-secondary)]">
                                <span className="font-mono text-xs font-semibold text-[var(--color-text-primary)]">{blocker.part_number ?? "PRODUCT"}</span>
                                <span className="mx-2 text-[var(--color-text-muted)]">-</span>{blocker.detail}
                              </li>
                            ))}
                          </ul>
                        ) : <p className="mt-3 text-sm text-emerald-700 dark:text-emerald-300">All deterministic readiness gates passed.</p>}
                        {detail.readiness_blockers.length > 25 ? <p className="mt-3 text-xs text-[var(--color-text-muted)]">Showing 25 of {formatNumber(detail.readiness_blockers.length)} blockers.</p> : null}
                      </div>
                    </div>

                    <div className="min-w-0">
                      <p className="app-label">Proposed SKU mappings</p>
                      <div className="mt-3 max-h-80 overflow-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
                        <table className="w-full min-w-[760px] text-left text-xs">
                          <thead className="sticky top-0 bg-[var(--color-surface-2)] uppercase tracking-[0.08em] text-[var(--color-text-muted)]">
                            <tr><th className="px-3 py-2.5">SKU</th><th className="px-3 py-2.5">Description</th><th className="px-3 py-2.5">Metric</th><th className="px-3 py-2.5">Behavior</th><th className="px-3 py-2.5">Minimum / increment</th></tr>
                          </thead>
                          <tbody className="divide-y divide-[var(--color-border)]">
                            {detail.proposed_mappings.map((mapping) => (
                              <tr key={`${mapping.part_number}-${mapping.billing_metric_key}`}>
                                <td className="px-3 py-3 align-top font-mono font-semibold">{mapping.part_number}</td>
                                <td className="max-w-sm px-3 py-3 align-top text-[var(--color-text-secondary)]">{mapping.display_name}</td>
                                <td className="px-3 py-3 align-top text-[var(--color-text-secondary)]">{mapping.quantity_unit}</td>
                                <td className="px-3 py-3 align-top text-[var(--color-text-secondary)]">{humanize(mapping.quantity_behavior)}</td>
                                <td className="px-3 py-3 align-top text-[var(--color-text-secondary)]">{mapping.minimum_quantity} / {mapping.quantity_increment}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {detail.proposed_mappings.length === 0 ? <p className="px-3 py-5 text-sm text-[var(--color-text-muted)]">No complete SKU mappings can be proposed from current evidence.</p> : null}
                      </div>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-3 border-t border-[var(--color-border)] pt-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                    <label className="min-w-0 text-sm font-medium text-[var(--color-text-primary)]">
                      Review rationale
                      <textarea
                        className="mt-2 min-h-20 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm"
                        placeholder="Record why this product is approved or rejected."
                        value={rationale}
                        onChange={(event) => setRationales((current) => ({ ...current, [product.product_key]: event.target.value }))}
                      />
                    </label>
                    <div className="flex flex-wrap gap-2">
                      <button className="app-button-secondary gap-2" type="button" disabled={busy !== null || detail.status === "rejected"} onClick={() => void review(product.product_key, "reject")}><XCircle className="h-4 w-4" />Reject</button>
                      <button className="app-button-primary gap-2" type="button" disabled={busy !== null || !detail.promotable} title={detail.promotable ? "Approve and materialize governed BOM coverage" : "Resolve readiness blockers before approval"} onClick={() => void review(product.product_key, "approve")}><ShieldCheck className="h-4 w-4" />Approve for BOM</button>
                    </div>
                  </div>
                </div>
              ) : null}
            </details>
          );
        })}
        {!loading && coverage.products.length === 0 ? <p className="px-5 py-8 text-sm text-[var(--color-text-secondary)]">No coverage proposals match these filters. Generate coverage after the OCI product catalog is loaded.</p> : null}
        {loading && coverage.products.length === 0 ? <div className="flex items-center gap-2 px-5 py-8 text-sm text-[var(--color-text-secondary)]"><Loader2 className="h-4 w-4 animate-spin" />Loading OCI coverage...</div> : null}
      </div>

      {coverage.total > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-border)] px-5 py-4 text-sm text-[var(--color-text-secondary)]">
          <span>Page {coverage.page} of {Math.max(1, Math.ceil(coverage.total / coverage.page_size))} - {formatNumber(coverage.total)} products</span>
          <div className="flex gap-2">
            <button className="app-button-secondary" type="button" disabled={loading || coverage.page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</button>
            <button className="app-button-secondary" type="button" disabled={loading || coverage.page >= Math.ceil(coverage.total / coverage.page_size)} onClick={() => setPage((current) => current + 1)}>Next</button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
