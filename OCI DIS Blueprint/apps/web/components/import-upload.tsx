"use client";

/* Workbook upload dropzone and import history viewer. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Download } from "lucide-react";

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
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TEMPLATE_HEADERS = [
  "#",
  "ID de Interfaz",
  "Marca",
  "Proceso de Negocio",
  "Interfaz",
  "Descripción",
  "Tipo",
  "Estado Interfaz",
  "Complejidad",
  "Alcance Inicial",
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
    } catch (caughtError) {
      setPhase("failed");
      setError(caughtError instanceof Error ? caughtError.message : "Upload failed.");
    }
  }

  async function handleDeleteImport(batch: ImportBatch): Promise<void> {
    const confirmed = window.confirm(
      `Remove import ${batch.id.slice(0, 8)} and all catalog rows created from it?`,
    );
    if (!confirmed) {
      return;
    }

    setDeletingBatchId(batch.id);
    setError("");
    try {
      await api.deleteImport(projectId, batch.id);
      const nextHistory = history.filter((entry: ImportBatch) => entry.id !== batch.id);
      setHistory(nextHistory);
      if (currentBatch?.id === batch.id) {
        setCurrentBatch(nextHistory[0] ?? null);
      }
      router.refresh();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to remove import.");
    } finally {
      setDeletingBatchId("");
    }
  }

  return (
    <div className="space-y-8">
      <section className="app-card p-6">
        <div className="rounded-[1.75rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-6">
          <p className="app-label">Step 1</p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
            Download the import template
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Use this template to ensure your data matches the expected column order and format for workbook import.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-4">
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
          <div className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">Required columns (in order)</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {TEMPLATE_HEADERS.map((header) => (
                <span key={header} className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1 text-sm text-[var(--color-text-secondary)]">
                  {header}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-6">
          <p className="app-label">Step 2</p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
            Upload your completed file
          </h2>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
            Project: {projectName}
          </p>
        </div>
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
            "rounded-[1.75rem] border border-dashed px-8 py-12 text-center transition",
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
          <h3 className="mt-3 text-3xl font-semibold tracking-tight text-[var(--color-text-primary)]">Upload `Catálogo de Integraciones`</h3>
          <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
            Drag and drop the workbook here, or click to browse. The API will queue the workbook, and the worker will parse, normalize, and persist rows in the background.
          </p>
          {selectedFile ? (
            <div className="mt-6 inline-flex flex-col rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-4 text-left">
              <span className="text-sm font-semibold text-[var(--color-text-primary)]">{selectedFile.name}</span>
              <span className="mt-1 text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
                {formatBytes(selectedFile.size)}
              </span>
            </div>
          ) : null}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-4">
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
        </div>

        {currentBatch ? (
          currentBatch.status === "completed" ? (
            <div className="mt-6 space-y-4 rounded-[1.5rem] border border-[var(--color-qa-ok-border)] bg-[var(--color-qa-ok-bg)] p-5">
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
            <div className="mt-6 space-y-3 rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface-2)] p-5">
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
      </section>

      {initialRows && initialSelectedBatchId ? (
        <section className="app-table-shell">
          <div className="border-b border-[var(--color-border)] px-6 py-5">
            <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">
              Imported Rows for Batch {initialSelectedBatchId.slice(0, 8)}
            </h2>
            <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
              Reviewing {initialRows.rows.length} source rows pulled from the selected import batch.
            </p>
          </div>
          <div className="overflow-x-auto">
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
                {initialRows.rows.map((row) => {
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
        </section>
      ) : null}

      <section className="app-table-shell">
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
                          void handleDeleteImport(batch);
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
    </div>
  );
}
