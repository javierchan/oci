"use client";

/* Workbook upload dropzone and import history viewer. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import { Download } from "lucide-react";

import { ConfirmModal } from "@/components/modal";
import { emitToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import { APP_VERSION } from "@/lib/app-version";
import { formatDate } from "@/lib/format";
import type { ImportBatch, SourceRowList } from "@/lib/types";

type ImportUploadProps = {
  projectId: string;
  projectName: string;
  initialBatches: ImportBatch[];
  initialRows: SourceRowList | null;
  initialSelectedBatchId: string | null;
  highlightedRowNumber: number | null;
};

type UploadPhase = "idle" | "pending" | "processing" | "completed" | "failed";
const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/api\/v1\/?$/,
  "",
);
const TEMPLATE_COLUMNS = [
  { label: "#", workbookHeader: "#" },
  { label: "Interface ID", workbookHeader: "ID de Interfaz" },
  { label: "Brand", workbookHeader: "Marca" },
  { label: "Business Process", workbookHeader: "Proceso de Negocio" },
  { label: "Interface Name", workbookHeader: "Interfaz" },
  { label: "Description", workbookHeader: "Descripción" },
  { label: "Type", workbookHeader: "Tipo" },
  { label: "Interface Status", workbookHeader: "Estado Interfaz" },
  { label: "Complexity", workbookHeader: "Complejidad" },
  { label: "Initial Scope", workbookHeader: "Alcance Inicial" },
];

function phaseFromBatchStatus(batch: ImportBatch): UploadPhase {
  switch (batch.status) {
    case "pending":
      return "pending";
    case "processing":
      return "processing";
    case "completed":
      return "completed";
    case "failed":
      return "failed";
    default:
      return "idle";
  }
}

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function ImportUpload({
  projectId,
  projectName,
  initialBatches,
  initialRows,
  initialSelectedBatchId,
  highlightedRowNumber,
}: ImportUploadProps): JSX.Element {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [error, setError] = useState<string>("");
  const [currentBatch, setCurrentBatch] = useState<ImportBatch | null>(null);
  const [history, setHistory] = useState<ImportBatch[]>(initialBatches);
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [deletingBatchId, setDeletingBatchId] = useState<string>("");
  const [deleteTarget, setDeleteTarget] = useState<ImportBatch | null>(null);
  const [rowFilter, setRowFilter] = useState<"all" | "included" | "excluded">("all");
  const [rowSearch, setRowSearch] = useState<string>("");
  const [rowPage, setRowPage] = useState<number>(1);
  const [rowPageSize, setRowPageSize] = useState<number>(25);

  const filteredRows = useMemo(() => {
    if (!initialRows) {
      return [];
    }
    const search = rowSearch.trim().toLowerCase();
    return initialRows.rows.filter((row) => {
      const matchesFilter =
        rowFilter === "all" ||
        (rowFilter === "included" && row.included) ||
        (rowFilter === "excluded" && !row.included);
      if (!matchesFilter) {
        return false;
      }
      if (search === "") {
        return true;
      }
      const previewText = Object.values(row.raw_data)
        .filter((value) => value !== null && value !== "")
        .map((value) => String(value).toLowerCase())
        .join(" ");
      return (
        String(row.source_row_number).includes(search) ||
        (row.exclusion_reason ?? "").toLowerCase().includes(search) ||
        previewText.includes(search)
      );
    });
  }, [initialRows, rowFilter, rowSearch]);

  const rowTotalPages = Math.max(1, Math.ceil(filteredRows.length / rowPageSize));
  const visibleRows = useMemo(() => {
    const startIndex = (rowPage - 1) * rowPageSize;
    return filteredRows.slice(startIndex, startIndex + rowPageSize);
  }, [filteredRows, rowPage, rowPageSize]);
  const hasHistory = history.length > 0;
  const latestBatch = currentBatch ?? history[0] ?? null;
  const stepOneTitle = hasHistory ? "Need the latest template?" : "Download the import template";
  const stepTwoTitle = hasHistory ? "Queue another workbook" : "Upload your completed file";

  function updateSelectedFile(file: File | null): void {
    setSelectedFile(file);
    setError("");
    setPhase(file ? "pending" : "idle");
  }

  async function handleUpload(): Promise<void> {
    if (!selectedFile) {
      setError("Select an .xlsx workbook first.");
      return;
    }

    if (!selectedFile.name.toLowerCase().endsWith(".xlsx")) {
      setError("Only .xlsx files are supported.");
      return;
    }

    setPhase("processing");
    setError("");
    try {
      const batch = await api.uploadWorkbook(projectId, selectedFile);
      setCurrentBatch(batch);
      setHistory((current: ImportBatch[]) => [batch, ...current]);
      setPhase(phaseFromBatchStatus(batch));
      emitToast("success", `Workbook "${selectedFile.name}" queued.`);
    } catch (caughtError) {
      setPhase("failed");
      setError(caughtError instanceof Error ? caughtError.message : "Upload failed.");
      emitToast("error", caughtError instanceof Error ? caughtError.message : "Upload failed.");
    }
  }

  async function handleDeleteImport(batch: ImportBatch): Promise<void> {
    setDeletingBatchId(batch.id);
    setError("");
    try {
      await api.deleteImport(projectId, batch.id);
      const nextHistory = history.filter((entry: ImportBatch) => entry.id !== batch.id);
      setHistory(nextHistory);
      if (currentBatch?.id === batch.id) {
        setCurrentBatch(nextHistory[0] ?? null);
      }
      emitToast("success", `Import ${batch.id.slice(0, 8)} removed.`);
      router.refresh();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to remove import.");
      emitToast("error", caughtError instanceof Error ? caughtError.message : "Unable to remove import.");
    } finally {
      setDeletingBatchId("");
    }
  }

  return (
    <div className="space-y-6">
      {hasHistory && latestBatch ? (
        <section className="app-card p-4 md:p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="app-kicker">Monitoring</p>
              <h2 className="mt-2 text-lg font-semibold text-[var(--color-text-primary)] md:text-xl">
                Latest import activity
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
                This project already has governed import history. Review the latest batch first, then queue another workbook when you are ready.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <span className="app-theme-chip">{history.length} batches</span>
                <span className="app-theme-chip">Latest status: {latestBatch.status}</span>
                <span className="app-theme-chip">{latestBatch.loaded_count ?? 0} loaded</span>
                <span className="app-theme-chip">{latestBatch.excluded_count ?? 0} excluded</span>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Link
                href={`/projects/${projectId}/import?batch_id=${latestBatch.id}`}
                className="app-button-secondary px-4 py-2 text-sm"
              >
                View latest batch
              </Link>
              <a href="#import-history" className="app-link">
                Jump to history ↓
              </a>
            </div>
          </div>
        </section>
      ) : null}

      <section className={`grid gap-4 ${hasHistory ? "xl:grid-cols-[minmax(0,0.78fr)_minmax(0,1.22fr)]" : "xl:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]"}`}>
        <article className={`app-card ${hasHistory ? "p-4" : "p-5"}`}>
          <p className="app-label">Step 1</p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
            {stepOneTitle}
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
            {hasHistory
              ? "Refresh the workbook template only when you need the latest governed headers or validations before another upload."
              : "Use this template to ensure your data matches the expected column order and format for workbook import."}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <a
              href={`${API_BASE}/api/v1/exports/template/xlsx`}
              download={`oci-dis-import-template-v${APP_VERSION}.xlsx`}
              className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] px-4 py-2 text-sm font-semibold text-[var(--color-text-secondary)] transition hover:bg-[var(--color-surface)] hover:text-[var(--color-text-primary)]"
            >
              <Download className="h-4 w-4" />
              Download Template (.xlsx)
            </a>
            <span className="app-theme-chip">Last updated: v{APP_VERSION}</span>
          </div>
          <div className="mt-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-3.5">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">Required workbook columns</p>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {TEMPLATE_COLUMNS.map((column) => (
                <div
                  key={`${column.label}-${column.workbookHeader}`}
                  className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2"
                >
                  <p className="text-sm font-medium text-[var(--color-text-primary)]">{column.label}</p>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                    Workbook header: {column.workbookHeader}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </article>

        <article className={`app-card ${hasHistory ? "p-4" : "p-5"}`}>
          <p className="app-label">Step 2</p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
            {stepTwoTitle}
          </h2>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
            Project: {projectName}
          </p>
          <div
            role="button"
            tabIndex={0}
            onClick={() => inputRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                inputRef.current?.click();
              }
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              setDragActive(false);
            }}
            onDrop={(event) => {
              event.preventDefault();
              setDragActive(false);
              const file = event.dataTransfer.files.item(0);
              updateSelectedFile(file);
            }}
            className={[
              `mt-4 rounded-[1.75rem] border border-dashed text-center transition ${hasHistory ? "px-6 py-5" : "px-8 py-7"}`,
              dragActive
                ? "border-[var(--color-accent)] bg-[var(--color-surface)]"
                : "border-[var(--color-border)] bg-[var(--color-surface-3)] hover:border-[var(--color-accent)] hover:bg-[var(--color-surface)]",
            ].join(" ")}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => updateSelectedFile(event.target.files?.item(0) ?? null)}
              className="hidden"
            />
            <p className="app-label">Workbook Import</p>
            <h3 className="mt-3 text-xl font-semibold tracking-tight text-[var(--color-text-primary)] lg:text-[1.75rem]">
              Upload governed workbook
            </h3>
            <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
              Drag and drop the `.xlsx` file here, or click to browse. The governed template maps to the workbook header set from `Catálogo de Integraciones`, and the API will queue, parse, normalize, and persist rows in the background.
            </p>
            {selectedFile ? (
              <div className="mt-5 inline-flex flex-col rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-4 text-left">
                <span className="text-sm font-semibold text-[var(--color-text-primary)]">{selectedFile.name}</span>
                <span className="mt-1 text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                  {formatBytes(selectedFile.size)}
                </span>
              </div>
            ) : null}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={handleUpload}
              disabled={!selectedFile || phase === "pending" || phase === "processing"}
              className="app-button-primary"
            >
              {phase === "processing" || phase === "pending" ? "Queuing…" : "Upload & Queue Import"}
            </button>
            <span className="app-theme-chip">
              Status: {phase}
            </span>
            <span className="text-sm text-[var(--color-text-secondary)]">
              Import history below tracks every batch and row-level inclusion result.
            </span>
          </div>

          {currentBatch ? (
            currentBatch.status === "completed" ? (
              <div className="mt-4 space-y-4 rounded-[1.5rem] border border-[var(--color-qa-ok-border)] bg-[var(--color-qa-ok-bg)] p-5">
                <div className="grid gap-4 md:grid-cols-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-qa-ok-text)]">Loaded</p>
                    <p className="mt-2 text-3xl font-semibold text-[var(--color-text-primary)]">{currentBatch.loaded_count ?? 0}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-qa-ok-text)]">Excluded</p>
                    <p className="mt-2 text-3xl font-semibold text-[var(--color-text-primary)]">{currentBatch.excluded_count ?? 0}</p>
                  </div>
                  <div>
                    <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-qa-ok-text)]">TBQ = Y</p>
                    <p className="mt-2 text-3xl font-semibold text-[var(--color-text-primary)]">{currentBatch.tbq_y_count ?? 0}</p>
                  </div>
                </div>
                <Link
                  href={`/projects/${projectId}/import?batch_id=${currentBatch.id}`}
                  className="app-link inline-flex"
                >
                  View imported rows →
                </Link>
              </div>
            ) : (
              <div className="mt-4 space-y-3 rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
                <p className="text-xs uppercase tracking-[0.25em] text-[var(--color-text-secondary)]">Batch queued</p>
                <h3 className="text-lg font-semibold text-[var(--color-text-primary)]">
                  Import batch {currentBatch.id.slice(0, 8)} is {currentBatch.status}.
                </h3>
                <p className="text-sm leading-6 text-[var(--color-text-secondary)]">
                  The workbook has been accepted and the background worker is processing it. Refresh this page or open the batch detail to watch the counts update.
                </p>
                <Link
                  href={`/projects/${projectId}/import?batch_id=${currentBatch.id}`}
                  className="app-link inline-flex"
                >
                  View batch status →
                </Link>
              </div>
            )
          ) : null}

          {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
        </article>
      </section>

      {initialRows && initialSelectedBatchId ? (
        <section className="app-table-shell">
          <div className="border-b border-[var(--color-border)] px-6 py-5">
            <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">
              Imported Rows for Batch {initialSelectedBatchId.slice(0, 8)}
            </h2>
            <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
              Reviewing {initialRows.total} source rows pulled from the selected import batch.
            </p>
            <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto]">
              <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_180px]">
                <label>
                  <span className="mb-2 block text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                    Search rows
                  </span>
                  <input
                    value={rowSearch}
                    onChange={(event) => {
                      setRowSearch(event.target.value);
                      setRowPage(1);
                    }}
                    placeholder="Row number, exclusion, preview text..."
                    className="app-input"
                  />
                </label>
                <label>
                  <span className="mb-2 block text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                    Quick filter
                  </span>
                  <select
                    value={rowFilter}
                    onChange={(event) => {
                      setRowFilter(event.target.value as "all" | "included" | "excluded");
                      setRowPage(1);
                    }}
                    className="app-input"
                  >
                    <option value="all">All rows</option>
                    <option value="included">Included only</option>
                    <option value="excluded">Excluded only</option>
                  </select>
                </label>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="app-theme-chip">{filteredRows.length} matching</span>
                <span className="app-theme-chip">
                  {initialRows.rows.filter((row) => row.included).length} included
                </span>
                <span className="app-theme-chip">
                  {initialRows.rows.filter((row) => !row.included).length} excluded
                </span>
              </div>
            </div>
          </div>
          <div className="space-y-3 p-4 md:hidden">
            {visibleRows.map((row) => {
              const preview = Object.values(row.raw_data)
                .filter((value) => value !== null && value !== "")
                .slice(0, 4)
                .map((value) => String(value))
                .join(" • ");
              const highlighted = highlightedRowNumber === row.source_row_number;
              return (
                <article
                  key={row.id}
                  className={`rounded-[1.5rem] border p-4 ${
                    highlighted
                      ? "border-[var(--color-accent)] bg-[var(--color-pat-sync-bg)]"
                      : "border-[var(--color-border)] bg-[var(--color-surface)]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                        Row {row.source_row_number}
                      </p>
                      <p className="mt-2 text-sm font-semibold text-[var(--color-text-primary)]">
                        {row.included ? "Included" : "Excluded"}
                      </p>
                    </div>
                    <span className="app-theme-chip">{row.included ? "Included" : "Excluded"}</span>
                  </div>
                  <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
                    {row.exclusion_reason ?? "No exclusion reason"}
                  </p>
                  <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
                    {preview || "No preview data"}
                  </p>
                </article>
              );
            })}
          </div>
          <div className="hidden overflow-x-auto md:block">
            <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
              <thead className="app-table-header">
                <tr>
                  <th className="px-6 py-4">Row</th>
                  <th className="px-6 py-4">Included</th>
                  <th className="px-6 py-4">Exclusion Reason</th>
                  <th className="px-6 py-4">Preview</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
                {visibleRows.map((row) => {
                  const preview = Object.values(row.raw_data)
                    .filter((value) => value !== null && value !== "")
                    .slice(0, 3)
                    .map((value) => String(value))
                    .join(" • ");
                  const highlighted = highlightedRowNumber === row.source_row_number;
                  return (
                    <tr
                      key={row.id}
                      className={`app-table-row ${highlighted ? "bg-[var(--color-pat-sync-bg)]" : ""}`}
                    >
                      <td className="px-6 py-4 font-semibold">{row.source_row_number}</td>
                      <td className="px-6 py-4">{row.included ? "Yes" : "No"}</td>
                      <td className="px-6 py-4 text-[var(--color-text-secondary)]">
                        {row.exclusion_reason ?? "—"}
                      </td>
                      <td className="px-6 py-4 text-[var(--color-text-secondary)]">
                        {preview || "No preview data"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex flex-col gap-4 border-t border-[var(--color-border)] px-6 py-4 md:flex-row md:items-center md:justify-between">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:gap-6">
              <div className="text-sm text-[var(--color-text-secondary)]">
                Page {rowPage} of {rowTotalPages}
              </div>
              <label className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                Rows per page
                <select
                  value={rowPageSize}
                  onChange={(event) => {
                    setRowPageSize(Number(event.target.value));
                    setRowPage(1);
                  }}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text-primary)]"
                >
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </label>
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setRowPage((current) => Math.max(1, current - 1))}
                disabled={rowPage <= 1}
                className="app-button-secondary px-4 py-2"
              >
                Prev
              </button>
              <button
                type="button"
                onClick={() => setRowPage((current) => Math.min(rowTotalPages, current + 1))}
                disabled={rowPage >= rowTotalPages}
                className="app-button-secondary px-4 py-2"
              >
                Next
              </button>
            </div>
          </div>
        </section>
      ) : null}

      <section id="import-history" className="app-table-shell">
        <div className="border-b border-[var(--color-border)] px-6 py-5">
          <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">Import History</h2>
        </div>
        {history.length === 0 ? (
          <div className="px-6 py-10 text-sm text-[var(--color-text-secondary)]">No imports have been run for this project yet.</div>
        ) : (
          <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
            <thead className="app-table-header">
              <tr>
                <th className="px-6 py-4">Batch</th>
                <th className="px-6 py-4">Created</th>
                <th className="px-6 py-4">Loaded</th>
                <th className="px-6 py-4">Excluded</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
              {history.map((batch: ImportBatch) => (
                <tr key={batch.id} className="app-table-row">
                  <td className="px-6 py-4 font-mono text-xs text-[var(--color-text-secondary)]">
                    {batch.filename ? (
                      <span title={batch.id}>{batch.filename}</span>
                    ) : (
                      <span className="opacity-60" title={batch.id}>
                        {batch.id.slice(0, 8)}…
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{formatDate(batch.created_at)}</td>
                  <td className="px-6 py-4 font-medium text-[var(--color-text-primary)]">{batch.loaded_count ?? 0}</td>
                  <td className="px-6 py-4 text-[var(--color-text-secondary)]">{batch.excluded_count ?? 0}</td>
                  <td className="px-6 py-4">
                    <span className="app-theme-chip">
                      {batch.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap items-center gap-3">
                      <Link
                        href={`/projects/${projectId}/import?batch_id=${batch.id}`}
                        className="app-link"
                      >
                        View rows
                      </Link>
                      <button
                        type="button"
                        onClick={() => {
                          setDeleteTarget(batch);
                        }}
                        disabled={
                          deletingBatchId === batch.id ||
                          batch.status === "pending" ||
                          batch.status === "processing"
                        }
                        className="text-sm font-medium text-rose-700 hover:text-rose-500 disabled:cursor-not-allowed disabled:text-[var(--color-text-muted)]"
                      >
                        {deletingBatchId === batch.id ? "Removing…" : "Remove"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
      <ConfirmModal
        open={deleteTarget !== null}
        title="Remove import batch"
        description={`Import ${deleteTarget?.id.slice(0, 8)} and all catalog rows created from it will be permanently removed.`}
        confirmLabel="Remove import"
        cancelLabel="Keep it"
        danger
        onConfirm={() => {
          if (deleteTarget) {
            void handleDeleteImport(deleteTarget);
          }
          setDeleteTarget(null);
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
