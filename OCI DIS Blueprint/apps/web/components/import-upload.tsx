"use client";

/* Workbook upload dropzone and import history viewer. */

import { useRef, useState } from "react";

import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { ImportBatch } from "@/lib/types";

type ImportUploadProps = {
  projectId: string;
  initialBatches: ImportBatch[];
};

type UploadPhase = "idle" | "pending" | "processing" | "completed" | "failed";

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function ImportUpload({ projectId, initialBatches }: ImportUploadProps): JSX.Element {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [error, setError] = useState<string>("");
  const [currentBatch, setCurrentBatch] = useState<ImportBatch | null>(null);
  const [history, setHistory] = useState<ImportBatch[]>(initialBatches);
  const [dragActive, setDragActive] = useState<boolean>(false);

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
      setPhase("completed");
    } catch (caughtError) {
      setPhase("failed");
      setError(caughtError instanceof Error ? caughtError.message : "Upload failed.");
    }
  }

  return (
    <div className="space-y-8">
      <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
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
              ? "border-sky-400 bg-sky-50"
              : "border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-white",
          ].join(" ")}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(event) => updateSelectedFile(event.target.files?.item(0) ?? null)}
            className="hidden"
          />
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Workbook Import</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">Upload `Catálogo de Integraciones`</h1>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Drag and drop the workbook here, or click to browse. The API will parse, normalize, and persist rows immediately.
          </p>
          {selectedFile ? (
            <div className="mt-6 inline-flex flex-col rounded-2xl border border-slate-200 bg-white px-5 py-4 text-left">
              <span className="text-sm font-semibold text-slate-950">{selectedFile.name}</span>
              <span className="mt-1 text-xs uppercase tracking-[0.2em] text-slate-400">
                {formatBytes(selectedFile.size)}
              </span>
            </div>
          ) : null}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-4">
          <button
            type="button"
            onClick={handleUpload}
            disabled={!selectedFile || phase === "processing"}
            className="inline-flex items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {phase === "processing" ? "Importing…" : "Upload & Import"}
          </button>
          <span className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600">
            Status: {phase}
          </span>
        </div>

        {currentBatch ? (
          <div className="mt-6 grid gap-4 rounded-[1.5rem] border border-emerald-200 bg-emerald-50 p-5 md:grid-cols-3">
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-emerald-700">Loaded</p>
              <p className="mt-2 text-3xl font-semibold text-emerald-950">{currentBatch.loaded_count ?? 0}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-emerald-700">Excluded</p>
              <p className="mt-2 text-3xl font-semibold text-emerald-950">{currentBatch.excluded_count ?? 0}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-emerald-700">TBQ = Y</p>
              <p className="mt-2 text-3xl font-semibold text-emerald-950">{currentBatch.tbq_y_count ?? 0}</p>
            </div>
          </div>
        ) : null}

        {error ? <p className="mt-4 text-sm text-rose-600">{error}</p> : null}
      </section>

      <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-6 py-5">
          <h2 className="text-xl font-semibold text-slate-950">Import History</h2>
        </div>
        {history.length === 0 ? (
          <div className="px-6 py-10 text-sm text-slate-500">No imports have been run for this project yet.</div>
        ) : (
          <table className="min-w-full divide-y divide-slate-200 text-left">
            <thead className="bg-slate-950 text-xs uppercase tracking-[0.25em] text-slate-400">
              <tr>
                <th className="px-6 py-4 font-medium">Batch</th>
                <th className="px-6 py-4 font-medium">Created</th>
                <th className="px-6 py-4 font-medium">Loaded</th>
                <th className="px-6 py-4 font-medium">Excluded</th>
                <th className="px-6 py-4 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
              {history.map((batch: ImportBatch) => (
                <tr key={batch.id}>
                  <td className="px-6 py-4 font-mono text-xs text-slate-500">{batch.id.slice(0, 8)}</td>
                  <td className="px-6 py-4">{formatDate(batch.created_at)}</td>
                  <td className="px-6 py-4 font-medium text-slate-950">{batch.loaded_count ?? 0}</td>
                  <td className="px-6 py-4">{batch.excluded_count ?? 0}</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-slate-600">
                      {batch.status}
                    </span>
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
