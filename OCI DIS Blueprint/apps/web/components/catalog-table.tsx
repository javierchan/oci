"use client";

/* Interactive catalog table with filters, search, and pagination. */

import { useDeferredValue, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { PatternBadge } from "@/components/pattern-badge";
import { QaBadge } from "@/components/qa-badge";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { CatalogPage, Integration, PatternDefinition } from "@/lib/types";

type CatalogTableProps = {
  projectId: string;
  initialPage: CatalogPage;
  patterns: PatternDefinition[];
  brands: string[];
};

export function CatalogTable({
  projectId,
  initialPage,
  patterns,
  brands,
}: CatalogTableProps): JSX.Element {
  const router = useRouter();
  const [search, setSearch] = useState<string>("");
  const [qaStatus, setQaStatus] = useState<string>("");
  const [pattern, setPattern] = useState<string>("");
  const [brand, setBrand] = useState<string>("");
  const [page, setPage] = useState<number>(initialPage.page);
  const [data, setData] = useState<CatalogPage>(initialPage);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const deferredSearch = useDeferredValue(search);

  useEffect(() => {
    let cancelled = false;

    async function load(): Promise<void> {
      setLoading(true);
      setError("");
      try {
        const response = await api.listCatalog(projectId, {
          page,
          page_size: 50,
          search: deferredSearch || undefined,
          qa_status: qaStatus || undefined,
          pattern: pattern || undefined,
          brand: brand || undefined,
        });
        if (!cancelled) {
          setData(response);
        }
      } catch (caughtError) {
        if (!cancelled) {
          setError(caughtError instanceof Error ? caughtError.message : "Unable to load catalog.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, [brand, deferredSearch, page, pattern, projectId, qaStatus]);

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  const patternNames = new Map<string, string>(
    patterns.map((patternDefinition: PatternDefinition) => [
      patternDefinition.pattern_id,
      patternDefinition.name,
    ]),
  );

  function resetPageAndSet(setter: (value: string) => void, value: string): void {
    setter(value);
    setPage(1);
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end">
          <label className="flex-1">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Search</span>
            <input
              value={search}
              onChange={(event) => resetPageAndSet(setSearch, event.target.value)}
              placeholder="Interface, system, description…"
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
            />
          </label>
          <label className="min-w-[12rem]">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">QA Status</span>
            <select
              value={qaStatus}
              onChange={(event) => resetPageAndSet(setQaStatus, event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
            >
              <option value="">All</option>
              <option value="OK">OK</option>
              <option value="REVISAR">REVISAR</option>
              <option value="PENDING">PENDING</option>
            </select>
          </label>
          <label className="min-w-[14rem]">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Pattern</span>
            <select
              value={pattern}
              onChange={(event) => resetPageAndSet(setPattern, event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
            >
              <option value="">All</option>
              {patterns.map((patternDefinition: PatternDefinition) => (
                <option key={patternDefinition.pattern_id} value={patternDefinition.pattern_id}>
                  {patternDefinition.pattern_id} {patternDefinition.name}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-[12rem]">
            <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Brand</span>
            <select
              value={brand}
              onChange={(event) => resetPageAndSet(setBrand, event.target.value)}
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
            >
              <option value="">All</option>
              {brands.map((brandName: string) => (
                <option key={brandName} value={brandName}>
                  {brandName}
                </option>
              ))}
            </select>
          </label>
          <div className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600">
            {data.total} integrations
          </div>
        </div>
        {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
      </section>

      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left">
            <thead className="bg-slate-950 text-xs uppercase tracking-[0.25em] text-slate-400">
              <tr>
                <th className="px-6 py-4 font-medium">#</th>
                <th className="px-6 py-4 font-medium">Interface ID</th>
                <th className="px-6 py-4 font-medium">Brand</th>
                <th className="px-6 py-4 font-medium">Interface Name</th>
                <th className="px-6 py-4 font-medium">Pattern</th>
                <th className="px-6 py-4 font-medium">Frequency</th>
                <th className="px-6 py-4 font-medium">Payload KB</th>
                <th className="px-6 py-4 font-medium">QA Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.integrations.map((integration: Integration) => (
                <tr
                  key={integration.id}
                  onClick={() =>
                    router.push(`/projects/${projectId}/catalog/${integration.id}`)
                  }
                  className="cursor-pointer text-sm text-slate-700 transition hover:bg-slate-50"
                >
                  <td className="px-6 py-4 font-medium text-slate-950">{integration.seq_number}</td>
                  <td className="px-6 py-4">{integration.interface_id ?? "—"}</td>
                  <td className="px-6 py-4">{integration.brand ?? "—"}</td>
                  <td className="px-6 py-4">{integration.interface_name ?? "—"}</td>
                  <td className="px-6 py-4">
                    <PatternBadge
                      patternId={integration.selected_pattern}
                      name={
                        integration.selected_pattern
                          ? patternNames.get(integration.selected_pattern) ?? null
                          : null
                      }
                    />
                  </td>
                  <td className="px-6 py-4">{integration.frequency ?? "—"}</td>
                  <td className="px-6 py-4">{formatNumber(integration.payload_per_execution_kb, 1)}</td>
                  <td className="px-6 py-4">
                    <QaBadge status={integration.qa_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col gap-4 border-t border-slate-200 px-6 py-4 md:flex-row md:items-center md:justify-between">
          <div className="text-sm text-slate-500">
            {loading ? "Refreshing catalog…" : `Page ${data.page} of ${totalPages}`}
          </div>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => setPage((current: number) => Math.max(1, current - 1))}
              disabled={page <= 1 || loading}
              className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Prev
            </button>
            <button
              type="button"
              onClick={() => setPage((current: number) => Math.min(totalPages, current + 1))}
              disabled={page >= totalPages || loading}
              className="rounded-full border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
