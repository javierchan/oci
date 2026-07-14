"use client";

/* Operational admin surface for governed OCI price catalogs and SKU mappings. */

import {
  Check,
  FileUp,
  Loader2,
  Pencil,
  RefreshCcw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { emitToast } from "@/hooks/use-toast";
import { api, getErrorMessage } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import { isPriceSyncTerminal } from "@/lib/types";
import type {
  PriceCatalogSnapshot,
  PriceItem,
  PriceSource,
  PriceSyncJob,
  SkuMapping,
  SkuMappingPatch,
  SkuMappingStatus,
} from "@/lib/types";

function statusClasses(status: string): string {
  if (status === "approved" || status === "completed" || status === "active") {
    return "border-emerald-400/45 text-emerald-700 dark:text-emerald-300";
  }
  if (status === "failed" || status === "retired") {
    return "border-rose-400/45 text-rose-700 dark:text-rose-300";
  }
  return "border-amber-400/45 text-amber-700 dark:text-amber-300";
}

function compactId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}…` : value;
}

type MappingDraft = {
  partNumber: string;
  status: SkuMappingStatus;
  predicates: string;
  quantityBehavior: SkuMapping["quantity_behavior"];
  quantityIncrement: number;
  minimumQuantity: number;
  quantityUnit: string;
};

export function PricingAdminPanel(): JSX.Element {
  const [sources, setSources] = useState<PriceSource[]>([]);
  const [jobs, setJobs] = useState<PriceSyncJob[]>([]);
  const [snapshots, setSnapshots] = useState<PriceCatalogSnapshot[]>([]);
  const [mappings, setMappings] = useState<SkuMapping[]>([]);
  const [items, setItems] = useState<PriceItem[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string>("");
  const [itemSearch, setItemSearch] = useState<string>("");
  const [currency, setCurrency] = useState<string>("USD");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [rateCardName, setRateCardName] = useState<string>("Customer contract rate card");
  const [editingMappingId, setEditingMappingId] = useState<string | null>(null);
  const [mappingDraft, setMappingDraft] = useState<MappingDraft | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string>("");

  const load = useCallback(async (silent = false): Promise<void> => {
    if (!silent) {
      setLoading(true);
    }
    try {
      const [sourceResult, jobResult, snapshotResult, mappingResult] = await Promise.all([
        api.listPriceSources(),
        api.listPriceSyncJobs(12),
        api.listPriceCatalogSnapshots(12),
        api.listSkuMappings(),
      ]);
      setSources(sourceResult.sources);
      setJobs(jobResult.jobs);
      setSnapshots(snapshotResult.snapshots);
      setMappings(mappingResult.mappings);
      setSelectedSnapshotId((current) => current || snapshotResult.snapshots[0]?.id || "");
      setError("");
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to load governed pricing."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const hasActiveJob = useMemo(
    () => jobs.some((job) => !isPriceSyncTerminal(job.status)),
    [jobs],
  );

  useEffect(() => {
    if (!hasActiveJob) {
      return undefined;
    }
    const timer = window.setInterval(() => void load(true), 3000);
    return () => window.clearInterval(timer);
  }, [hasActiveJob, load]);

  useEffect(() => {
    let active = true;
    if (!selectedSnapshotId) {
      setItems([]);
      return () => {
        active = false;
      };
    }
    const timer = window.setTimeout(() => {
      api
        .listPriceItems(selectedSnapshotId, { search: itemSearch || undefined, page: 1, page_size: 100 })
        .then((result) => {
          if (active) {
            setItems(result.items);
          }
        })
        .catch((caughtError) => {
          if (active) {
            setError(getErrorMessage(caughtError, "Unable to load normalized price items."));
          }
        });
    }, 200);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [itemSearch, selectedSnapshotId]);

  async function runSync(): Promise<void> {
    setBusyAction("sync");
    try {
      await api.createPriceSyncJob({ source_id: sources[0]?.id, currency: currency.toUpperCase() });
      emitToast("info", "Price synchronization queued.");
      await load(true);
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to start price synchronization."));
    } finally {
      setBusyAction(null);
    }
  }

  async function uploadRateCard(): Promise<void> {
    if (!uploadFile) {
      return;
    }
    setBusyAction("upload");
    try {
      const snapshot = await api.importPriceRateCard(uploadFile, rateCardName.trim(), currency.toUpperCase());
      setSelectedSnapshotId(snapshot.id);
      setUploadFile(null);
      emitToast("success", "Rate card imported into an immutable snapshot.");
      await load(true);
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to import the rate card."));
    } finally {
      setBusyAction(null);
    }
  }

  async function approveSnapshot(snapshotId: string): Promise<void> {
    setBusyAction(snapshotId);
    try {
      await api.approvePriceCatalogSnapshot(snapshotId);
      emitToast("success", "Price catalog approved for governed estimates.");
      await load(true);
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to approve the price catalog."));
    } finally {
      setBusyAction(null);
    }
  }

  function startMappingEdit(mapping: SkuMapping): void {
    setEditingMappingId(mapping.id);
    setMappingDraft({
      partNumber: mapping.part_number ?? "",
      status: mapping.status,
      predicates: JSON.stringify(mapping.predicates, null, 2),
      quantityBehavior: mapping.quantity_behavior,
      quantityIncrement: mapping.quantity_increment,
      minimumQuantity: mapping.minimum_quantity,
      quantityUnit: mapping.quantity_unit,
    });
  }

  async function saveMapping(mapping: SkuMapping): Promise<void> {
    if (!mappingDraft) {
      return;
    }
    let predicates: Record<string, unknown>;
    try {
      predicates = JSON.parse(mappingDraft.predicates) as Record<string, unknown>;
    } catch {
      emitToast("error", "Predicates must be a valid JSON object.");
      return;
    }
    setBusyAction(mapping.id);
    const patch: SkuMappingPatch = {
      part_number: mappingDraft.partNumber.trim() || null,
      status: mappingDraft.status,
      predicates,
      quantity_behavior: mappingDraft.quantityBehavior,
      quantity_increment: mappingDraft.quantityIncrement,
      minimum_quantity: mappingDraft.minimumQuantity,
      quantity_unit: mappingDraft.quantityUnit.trim(),
    };
    try {
      const updated = await api.patchSkuMapping(mapping.id, patch);
      setMappings((current) => current.map((entry) => (entry.id === updated.id ? updated : entry)));
      setEditingMappingId(null);
      setMappingDraft(null);
      emitToast("success", "SKU mapping updated and audited.");
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to update the SKU mapping."));
    } finally {
      setBusyAction(null);
    }
  }

  const approvedMappings = mappings.filter((mapping) => mapping.status === "approved").length;

  return (
    <div className="space-y-5">
      {error ? (
        <div role="alert" className="rounded-lg border border-rose-400/45 bg-[var(--color-surface-2)] p-4 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      ) : null}

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(20rem,0.7fr)]">
        <div className="app-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="app-label">Provider Status</p>
              <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Governed price sources</h2>
            </div>
            <button className="app-button-primary gap-2" type="button" disabled={busyAction !== null || hasActiveJob} onClick={() => void runSync()}>
              {busyAction === "sync" || hasActiveJob ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
              {hasActiveJob ? "Sync running" : "Sync public prices"}
            </button>
          </div>
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[620px] text-left text-sm">
              <thead className="text-xs uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
                <tr><th className="pb-3">Source</th><th className="pb-3">Type</th><th className="pb-3">Currency</th><th className="pb-3">Status</th><th className="pb-3">Last sync</th></tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {sources.map((source) => (
                  <tr key={source.id}>
                    <td className="py-3 font-semibold text-[var(--color-text-primary)]">{source.name}</td>
                    <td className="py-3 text-[var(--color-text-secondary)]">{source.source_type.replace(/_/g, " ")}</td>
                    <td className="py-3 font-mono text-[var(--color-text-secondary)]">{source.currency}</td>
                    <td className="py-3"><span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClasses(source.status)}`}>{source.status}</span></td>
                    <td className="py-3 text-[var(--color-text-muted)]">{source.last_synced_at ? formatDate(source.last_synced_at) : "Never"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="app-card p-5">
          <p className="app-label">Contract Rate Card</p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Import reviewed CSV</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">Creates an immutable commercial source without replacing public list prices.</p>
          <label className="mt-4 block text-sm font-semibold text-[var(--color-text-primary)]">
            Source name
            <input className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2" value={rateCardName} onChange={(event) => setRateCardName(event.target.value)} />
          </label>
          <label className="mt-3 block text-sm font-semibold text-[var(--color-text-primary)]">
            Currency
            <input className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2" maxLength={3} value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} />
          </label>
          <label className="mt-3 block text-sm font-semibold text-[var(--color-text-primary)]">
            CSV rate card
            <input className="mt-2 block w-full text-sm text-[var(--color-text-secondary)] file:mr-3 file:rounded-lg file:border-0 file:bg-[var(--color-surface-3)] file:px-3 file:py-2 file:font-semibold file:text-[var(--color-text-primary)]" type="file" accept=".csv,text/csv" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
          </label>
          <button className="app-button-secondary mt-4 w-full gap-2" type="button" disabled={!uploadFile || !rateCardName.trim() || busyAction !== null} onClick={() => void uploadRateCard()}>
            {busyAction === "upload" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
            Import rate card
          </button>
        </div>
      </section>

      <section className="app-card p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><p className="app-label">Immutable Catalogs</p><h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Review and approval queue</h2></div>
          <span className="text-sm text-[var(--color-text-secondary)]">{snapshots.length} recent snapshots</span>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {snapshots.map((snapshot) => (
            <div key={snapshot.id} className={`rounded-lg border p-4 ${selectedSnapshotId === snapshot.id ? "border-[var(--color-accent)]" : "border-[var(--color-border)]"}`}>
              <button type="button" className="w-full text-left" onClick={() => setSelectedSnapshotId(snapshot.id)}>
                <div className="flex items-center justify-between gap-3"><span className="font-mono text-xs text-[var(--color-text-muted)]">{compactId(snapshot.id)}</span><span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClasses(snapshot.approval_status)}`}>{snapshot.approval_status.replace(/_/g, " ")}</span></div>
                <p className="mt-3 text-2xl font-semibold text-[var(--color-text-primary)]">{formatNumber(snapshot.item_count)} items</p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">{snapshot.currency} · {formatDate(snapshot.retrieved_at)}</p>
              </button>
              {snapshot.approval_status !== "approved" ? <button type="button" className="app-button-secondary mt-4 w-full gap-2" disabled={busyAction !== null} onClick={() => void approveSnapshot(snapshot.id)}>{busyAction === snapshot.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}Approve</button> : null}
            </div>
          ))}
          {!loading && snapshots.length === 0 ? <p className="text-sm text-[var(--color-text-secondary)]">No price snapshots exist yet.</p> : null}
        </div>
      </section>

      <section className="app-table-shell">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--color-border)] px-5 py-4">
          <div><p className="app-label">Normalized Price Items</p><h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Selected catalog evidence</h2></div>
          <label className="relative block min-w-[18rem] text-sm"><Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-[var(--color-text-muted)]" /><input aria-label="Search price items" className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] py-2.5 pl-9 pr-3" placeholder="Part number, product or metric" value={itemSearch} onChange={(event) => setItemSearch(event.target.value)} /></label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-[0.12em] text-[var(--color-text-muted)]"><tr><th className="px-5 py-3">Part number</th><th className="px-5 py-3">Product</th><th className="px-5 py-3">Metric</th><th className="px-5 py-3">Model</th><th className="px-5 py-3 text-right">Unit price</th><th className="px-5 py-3">Tier</th></tr></thead><tbody className="divide-y divide-[var(--color-border)]">{items.map((item) => <tr key={item.id}><td className="px-5 py-3 font-mono text-[var(--color-text-primary)]">{item.part_number}</td><td className="px-5 py-3 font-medium text-[var(--color-text-primary)]">{item.display_name}</td><td className="px-5 py-3 text-[var(--color-text-secondary)]">{item.metric_name}</td><td className="px-5 py-3 text-[var(--color-text-secondary)]">{item.model}</td><td className="px-5 py-3 text-right font-mono text-[var(--color-text-primary)]">{item.currency} {item.value.toFixed(6)}</td><td className="px-5 py-3 text-[var(--color-text-muted)]">{item.range_min ?? "–"} to {item.range_max ?? "∞"}</td></tr>)}</tbody></table>
        </div>
      </section>

      <section className="app-table-shell">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--color-border)] px-5 py-4"><div><p className="app-label">SKU Mapping Coverage</p><h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Service demand to commercial SKU</h2></div><p className="text-sm font-semibold text-[var(--color-text-primary)]">{approvedMappings} of {mappings.length} approved</p></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-left text-sm"><thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-[0.12em] text-[var(--color-text-muted)]"><tr><th className="px-5 py-3">Service / tool</th><th className="px-5 py-3">Part number</th><th className="px-5 py-3">Metric / formula</th><th className="px-5 py-3">Predicates</th><th className="px-5 py-3">Status</th><th className="px-5 py-3 text-right">Action</th></tr></thead><tbody className="divide-y divide-[var(--color-border)]">{mappings.map((mapping) => {
          const editing = editingMappingId === mapping.id && mappingDraft !== null;
          return <tr key={mapping.id} className="align-top"><td className="px-5 py-4"><p className="font-semibold text-[var(--color-text-primary)]">{mapping.service_id}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{mapping.tool_key}</p></td><td className="px-5 py-4">{editing ? <input aria-label={`Part number for ${mapping.tool_key}`} className="w-36 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 font-mono" value={mappingDraft.partNumber} onChange={(event) => setMappingDraft({ ...mappingDraft, partNumber: event.target.value })} /> : <span className="font-mono text-[var(--color-text-primary)]">{mapping.part_number ?? "Non-billable"}</span>}</td><td className="min-w-72 px-5 py-4"><p className="text-[var(--color-text-primary)]">{mapping.billing_metric_key}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{mapping.formula_key}</p>{editing ? <div className="mt-3 grid grid-cols-2 gap-2"><label className="text-xs text-[var(--color-text-muted)]">Rule<select className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5" value={mappingDraft.quantityBehavior} onChange={(event) => setMappingDraft({ ...mappingDraft, quantityBehavior: event.target.value as SkuMapping["quantity_behavior"] })}><option value="packaged">Packaged</option><option value="fixed_capacity">Fixed capacity</option><option value="hourly">Hourly</option><option value="continuous">Continuous</option><option value="manual_monthly">Manual monthly</option></select></label><label className="text-xs text-[var(--color-text-muted)]">Unit<input className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5" value={mappingDraft.quantityUnit} onChange={(event) => setMappingDraft({ ...mappingDraft, quantityUnit: event.target.value })} /></label><label className="text-xs text-[var(--color-text-muted)]">Increment<input type="number" min={0.000001} step="any" className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5" value={mappingDraft.quantityIncrement} onChange={(event) => setMappingDraft({ ...mappingDraft, quantityIncrement: Number(event.target.value) })} /></label><label className="text-xs text-[var(--color-text-muted)]">Minimum<input type="number" min={0} step="any" className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5" value={mappingDraft.minimumQuantity} onChange={(event) => setMappingDraft({ ...mappingDraft, minimumQuantity: Number(event.target.value) })} /></label></div> : <p className="mt-2 text-xs text-[var(--color-text-secondary)]">{mapping.quantity_behavior.replaceAll("_", " ")} · {mapping.quantity_increment} increment · {mapping.minimum_quantity} minimum · {mapping.quantity_unit}</p>}</td><td className="max-w-xs px-5 py-4">{editing ? <textarea aria-label={`Predicates for ${mapping.tool_key}`} className="min-h-24 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 font-mono text-xs" value={mappingDraft.predicates} onChange={(event) => setMappingDraft({ ...mappingDraft, predicates: event.target.value })} /> : <code className="break-all text-xs text-[var(--color-text-secondary)]">{JSON.stringify(mapping.predicates)}</code>}</td><td className="px-5 py-4">{editing ? <select aria-label={`Status for ${mapping.tool_key}`} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2" value={mappingDraft.status} onChange={(event) => setMappingDraft({ ...mappingDraft, status: event.target.value as SkuMappingStatus })}><option value="draft">Draft</option><option value="approved">Approved</option><option value="retired">Retired</option></select> : <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClasses(mapping.status)}`}>{mapping.status}</span>}</td><td className="px-5 py-4 text-right">{editing ? <div className="flex justify-end gap-2"><button type="button" aria-label={`Cancel editing ${mapping.tool_key}`} className="app-button-secondary h-9 w-9 p-0" onClick={() => { setEditingMappingId(null); setMappingDraft(null); }}><X className="h-4 w-4" /></button><button type="button" aria-label={`Save ${mapping.tool_key}`} className="app-button-primary h-9 w-9 p-0" disabled={busyAction === mapping.id} onClick={() => void saveMapping(mapping)}>{busyAction === mapping.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}</button></div> : <button type="button" aria-label={`Edit ${mapping.tool_key}`} className="app-button-secondary h-9 w-9 p-0" onClick={() => startMappingEdit(mapping)}><Pencil className="h-4 w-4" /></button>}</td></tr>;
        })}</tbody></table></div>
      </section>

      {jobs.length > 0 ? <section className="app-card p-5"><p className="app-label">Recent Sync Jobs</p><div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">{jobs.slice(0, 6).map((job) => <div key={job.id} className="rounded-lg border border-[var(--color-border)] p-3"><div className="flex items-center justify-between gap-3"><span className="font-mono text-xs text-[var(--color-text-muted)]">{compactId(job.id)}</span><span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClasses(job.status)}`}>{job.status}</span></div><p className="mt-2 text-sm text-[var(--color-text-secondary)]">{job.item_count} items · {job.changes_detected} changes</p></div>)}</div></section> : null}
    </div>
  );
}
