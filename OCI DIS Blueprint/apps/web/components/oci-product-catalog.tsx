"use client";

/* Read-only, paginated browser for the captured OCI product taxonomy and SKUs. */

import { Database, Loader2, PackageSearch, Search, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { api, getErrorMessage } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { OciProductCatalogDetail, OciProductCatalogPage } from "@/lib/types";

const EMPTY_CATALOG: OciProductCatalogPage = {
  products: [],
  page: 1,
  page_size: 50,
  total: 0,
};

function humanize(value: string | null): string {
  if (!value) return "Not classified";
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatUnitPrice(value: number | null, currency = "USD"): string {
  if (value === null) return "No approved PAYG price";
  return `${currency} ${new Intl.NumberFormat("en-US", { maximumFractionDigits: 10 }).format(value)}`;
}

function productPriceRange(detail: Pick<OciProductCatalogDetail, "price_summary">): string {
  const summary = detail.price_summary;
  if (!summary) return "No approved USD PAYG price";
  if (summary.min_payg_unit_price === summary.max_payg_unit_price) {
    return formatUnitPrice(summary.min_payg_unit_price, summary.currency);
  }
  return `${formatUnitPrice(summary.min_payg_unit_price, summary.currency)} – ${formatUnitPrice(summary.max_payg_unit_price, summary.currency)}`;
}

export function OciProductCatalog(): JSX.Element {
  const [catalog, setCatalog] = useState<OciProductCatalogPage>(EMPTY_CATALOG);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [details, setDetails] = useState<Record<string, OciProductCatalogDetail>>({});
  const [detailLoading, setDetailLoading] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let active = true;
    setLoading(true);
    const timer = window.setTimeout(() => {
      api.listOciProducts({
        page,
        page_size: 50,
        search: query.trim() || undefined,
        category: category.trim() || undefined,
      })
        .then((result) => {
          if (!active) return;
          setCatalog(result);
          setError("");
        })
        .catch((caughtError) => {
          if (!active) return;
          setError(getErrorMessage(caughtError, "Unable to load the OCI product catalog."));
        })
        .finally(() => {
          if (active) setLoading(false);
        });
    }, query.trim() || category.trim() ? 250 : 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [category, page, query]);

  async function loadDetail(productKey: string, detailPage = 1): Promise<void> {
    setDetailLoading((current) => ({ ...current, [productKey]: true }));
    try {
      const detail = await api.getOciProduct(productKey, { page: detailPage, page_size: 25 });
      setDetails((current) => ({ ...current, [productKey]: detail }));
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to load the product SKU detail."));
    } finally {
      setDetailLoading((current) => ({ ...current, [productKey]: false }));
    }
  }

  return (
    <section className="app-table-shell min-w-0 overflow-hidden" aria-labelledby="oci-product-catalog-title">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-5">
        <div className="max-w-3xl">
          <p className="app-label">Read-only product taxonomy</p>
          <h2 id="oci-product-catalog-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
            OCI Product Catalog
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            Browse every captured OCI product and inspect its current SKU evidence. This catalog does not change mappings, scenarios, prices, approvals, or BOM generation.
          </p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] px-3 py-1.5 text-xs font-semibold text-[var(--color-text-secondary)]">
          <ShieldCheck className="h-4 w-4 text-[var(--color-accent)]" />
          Read only
        </span>
      </div>

      <div className="grid gap-3 border-b border-[var(--color-border)] px-5 py-4 md:grid-cols-2">
        <label className="relative block min-w-0">
          <span className="sr-only">Search OCI products</span>
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-[var(--color-text-muted)]" />
          <input
            aria-label="Search OCI products"
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] py-2.5 pl-9 pr-3 text-sm"
            placeholder="Search product or category"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(1);
            }}
          />
        </label>
        <label className="relative block min-w-0">
          <span className="sr-only">Filter OCI product category</span>
          <Database className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-[var(--color-text-muted)]" />
          <input
            aria-label="Filter OCI product category"
            className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] py-2.5 pl-9 pr-3 text-sm"
            placeholder="Filter category"
            value={category}
            onChange={(event) => {
              setCategory(event.target.value);
              setPage(1);
            }}
          />
        </label>
      </div>

      {error ? (
        <div role="alert" className="border-b border-rose-400/45 bg-[var(--color-surface-2)] px-5 py-4 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="divide-y divide-[var(--color-border)]">
        {catalog.products.map((product) => {
          const detail = details[product.product_key];
          const isLoadingDetail = detailLoading[product.product_key] ?? false;
          return (
            <details
              key={product.product_key}
              className="group px-5 py-4"
              onToggle={(event) => {
                if (event.currentTarget.open && !detail && !isLoadingDetail) {
                  void loadDetail(product.product_key);
                }
              }}
            >
              <summary className="grid cursor-pointer list-none gap-3 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-center">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <PackageSearch className="h-4 w-4 shrink-0 text-[var(--color-accent)]" />
                    <h3 className="break-words text-sm font-semibold text-[var(--color-text-primary)]">{product.name}</h3>
                  </div>
                  <p className="mt-1 break-words text-xs text-[var(--color-text-muted)]">{product.category ?? "Category not captured"}</p>
                </div>
                <div className="text-left md:text-right">
                  <p className="text-xs text-[var(--color-text-muted)]">Approved PAYG range</p>
                  <p className="mt-1 text-sm font-semibold text-[var(--color-text-primary)]">{productPriceRange(product)}</p>
                </div>
                <div className="flex items-center justify-between gap-3 md:justify-end">
                  <span className="app-theme-chip">{formatNumber(product.sku_count)} SKUs</span>
                  <span className="text-xs font-semibold text-[var(--color-text-secondary)] group-open:hidden">View SKUs</span>
                </div>
              </summary>

              {isLoadingDetail && !detail ? (
                <div className="mt-4 flex items-center gap-2 border-t border-[var(--color-border)] pt-4 text-sm text-[var(--color-text-secondary)]">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading SKU evidence…
                </div>
              ) : null}

              {detail ? (
                <div className="mt-4 border-t border-[var(--color-border)] pt-4">
                  <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
                    <table className="w-full min-w-[860px] text-left text-sm">
                      <thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-[0.1em] text-[var(--color-text-muted)]">
                        <tr>
                          <th className="px-4 py-3">SKU</th>
                          <th className="px-4 py-3">Metric</th>
                          <th className="px-4 py-3">Price type</th>
                          <th className="px-4 py-3">Current PAYG</th>
                          <th className="px-4 py-3">Classification</th>
                          <th className="px-4 py-3">BOM mapping</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--color-border)]">
                        {detail.skus.map((sku) => (
                          <tr key={sku.part_number}>
                            <td className="px-4 py-3 align-top">
                              <p className="font-mono text-xs font-semibold text-[var(--color-text-primary)]">{sku.part_number}</p>
                              <p className="mt-1 max-w-md break-words text-xs leading-5 text-[var(--color-text-secondary)]">{sku.display_name}</p>
                            </td>
                            <td className="px-4 py-3 align-top text-[var(--color-text-secondary)]">{sku.metric_name ?? "Not captured"}</td>
                            <td className="px-4 py-3 align-top text-[var(--color-text-secondary)]">{humanize(sku.price_type)}</td>
                            <td className="px-4 py-3 align-top font-medium text-[var(--color-text-primary)]">{formatUnitPrice(sku.current_payg_unit_price)}</td>
                            <td className="px-4 py-3 align-top text-[var(--color-text-secondary)]">{humanize(sku.commercial_classification)}</td>
                            <td className="px-4 py-3 align-top">
                              <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${sku.is_bom_mapped ? "border-emerald-400/45 text-emerald-700 dark:text-emerald-300" : "border-[var(--color-border)] text-[var(--color-text-muted)]"}`}>
                                {sku.is_bom_mapped ? "Mapped" : "Not mapped"}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-xs text-[var(--color-text-muted)]">
                    <span>SKU page {detail.page} of {Math.max(1, Math.ceil(detail.total / detail.page_size))} · {formatNumber(detail.total)} total</span>
                    <div className="flex gap-2">
                      <button className="app-button-secondary" type="button" disabled={isLoadingDetail || detail.page <= 1} onClick={() => void loadDetail(product.product_key, detail.page - 1)}>Previous SKUs</button>
                      <button className="app-button-secondary" type="button" disabled={isLoadingDetail || detail.page >= Math.ceil(detail.total / detail.page_size)} onClick={() => void loadDetail(product.product_key, detail.page + 1)}>Next SKUs</button>
                    </div>
                  </div>
                </div>
              ) : null}
            </details>
          );
        })}

        {!loading && catalog.products.length === 0 ? (
          <p className="px-5 py-8 text-sm text-[var(--color-text-secondary)]">No OCI products match the current filters.</p>
        ) : null}
        {loading && catalog.products.length === 0 ? (
          <div className="flex items-center gap-2 px-5 py-8 text-sm text-[var(--color-text-secondary)]">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading captured OCI products…
          </div>
        ) : null}
      </div>

      {catalog.total > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-border)] px-5 py-4 text-sm text-[var(--color-text-secondary)]">
          <span>Page {catalog.page} of {Math.max(1, Math.ceil(catalog.total / catalog.page_size))} · {formatNumber(catalog.total)} products</span>
          <div className="flex gap-2">
            <button className="app-button-secondary" type="button" disabled={loading || catalog.page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</button>
            <button className="app-button-secondary" type="button" disabled={loading || catalog.page >= Math.ceil(catalog.total / catalog.page_size)} onClick={() => setPage((current) => current + 1)}>Next</button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
