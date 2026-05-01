"use client";

/* Dictionary option create/edit form for admin governance pages. */

import { useEffect, useState } from "react";

import type { DictOption, DictOptionCreate } from "@/lib/types";

type AdminDictionaryFormProps = {
  category: string;
  initialValue?: DictOption | null;
  isLoading: boolean;
  error: string;
  onSubmit: (_value: DictOptionCreate) => void | Promise<void>;
  onCancel: () => void;
};

export function AdminDictionaryForm({
  category,
  initialValue,
  isLoading,
  error,
  onSubmit,
  onCancel,
}: AdminDictionaryFormProps): JSX.Element {
  const [form, setForm] = useState<DictOptionCreate>({
    code: "",
    value: "",
    description: "",
    executions_per_day: null,
    is_volumetric: null,
    sort_order: 0,
    is_active: true,
    version: "1.0.0",
  });
  const [validationError, setValidationError] = useState<string>("");

  useEffect(() => {
    if (!initialValue) {
      setForm({
        code: "",
        value: "",
        description: "",
        executions_per_day: null,
        is_volumetric: null,
        sort_order: 0,
        is_active: true,
        version: "1.0.0",
      });
      return;
    }
    setForm({
      code: initialValue.code ?? "",
      value: initialValue.value,
      description: initialValue.description ?? "",
      executions_per_day: initialValue.executions_per_day ?? null,
      is_volumetric: initialValue.is_volumetric ?? null,
      sort_order: initialValue.sort_order ?? 0,
      is_active: initialValue.is_active ?? true,
      version: initialValue.version ?? "1.0.0",
    });
  }, [initialValue]);

  async function handleSubmit(): Promise<void> {
    if (!form.value.trim()) {
      setValidationError("Value is required.");
      return;
    }
    setValidationError("");
    await onSubmit({
      code: form.code.trim(),
      value: form.value.trim(),
      description: form.description?.trim() || undefined,
      executions_per_day: category === "FREQUENCY" ? form.executions_per_day ?? null : null,
      is_volumetric: form.is_volumetric ?? null,
      sort_order: form.sort_order ?? 0,
      is_active: form.is_active ?? true,
      version: form.version?.trim() || "1.0.0",
    });
  }

  return (
    <section className="app-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="app-label">Dictionary Editor</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            {initialValue ? `Edit ${initialValue.value}` : `New ${category} Option`}
          </h2>
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="app-button-secondary px-4 py-2"
        >
          Close
        </button>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <label className="block">
          <span className="app-label mb-2 block">Code</span>
          <input
            value={form.code}
            onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
            placeholder={category === "FREQUENCY" ? "FREQ-14" : "OPTION-01"}
            className="app-input"
          />
        </label>

        <label className="block">
          <span className="app-label mb-2 block">Value</span>
          <input
            value={form.value}
            onChange={(event) => setForm((current) => ({ ...current, value: event.target.value }))}
            placeholder="Every 2 hours"
            className="app-input"
          />
        </label>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <label className="block">
          <span className="app-label mb-2 block">Sort Order</span>
          <input
            type="number"
            value={form.sort_order ?? 0}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                sort_order: Number(event.target.value),
              }))
            }
            className="app-input"
          />
        </label>

        <label className="block">
          <span className="app-label mb-2 block">Version</span>
          <input
            value={form.version ?? "1.0.0"}
            onChange={(event) => setForm((current) => ({ ...current, version: event.target.value }))}
            className="app-input"
          />
        </label>
      </div>

      <label className="mt-4 block">
        <span className="app-label mb-2 block">Description</span>
        <input
          value={form.description}
          onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
          className="app-input"
        />
      </label>

      {category === "FREQUENCY" ? (
        <label className="mt-4 block">
          <span className="app-label mb-2 block">Executions per Day</span>
          <input
            type="number"
            step="0.000001"
            value={form.executions_per_day ?? ""}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                executions_per_day: event.target.value === "" ? null : Number(event.target.value),
              }))
            }
            className="app-input"
          />
        </label>
      ) : null}

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <label className="flex items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">
          <input
            type="checkbox"
            checked={form.is_volumetric ?? false}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                is_volumetric: event.target.checked,
              }))
            }
            className="h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-accent)] focus:ring-[var(--color-accent)]"
          />
          <span>Volumetric Option</span>
        </label>

        <label className="flex items-center gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">
          <input
            type="checkbox"
            checked={form.is_active ?? true}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                is_active: event.target.checked,
              }))
            }
            className="h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-accent)] focus:ring-[var(--color-accent)]"
          />
          <span>Active</span>
        </label>
      </div>

      {validationError ? <p className="mt-4 text-sm text-rose-600">{validationError}</p> : null}
      {error ? <p className="mt-2 text-sm text-rose-600">{error}</p> : null}

      <div className="mt-6 flex flex-wrap justify-end gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="app-button-secondary"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => {
            void handleSubmit();
          }}
          disabled={isLoading}
          className="app-button-primary"
        >
          {isLoading ? "Saving…" : initialValue ? "Save Option" : "Create Option"}
        </button>
      </div>
    </section>
  );
}
