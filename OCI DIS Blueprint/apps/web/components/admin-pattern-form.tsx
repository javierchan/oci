"use client";

/* Pattern create/edit form for admin governance surfaces. */

import { useEffect, useState } from "react";

import { formatPatternCategory } from "@/lib/format";
import type { PatternDefinition, PatternDefinitionCreate } from "@/lib/types";

type AdminPatternFormProps = {
  mode: "create" | "edit";
  toolOptions: string[];
  initialValue?: PatternDefinition | null;
  isLoading: boolean;
  error: string;
  onSubmit: (_value: PatternDefinitionCreate) => void | Promise<void>;
  onCancel: () => void;
};

const CATEGORY_OPTIONS: PatternDefinitionCreate["category"][] = [
  "Synchronous",
  "Asynchronous",
  "Synchronous + Asynchronous",
];

function normalizeCategory(value: string | null | undefined): string {
  if (!value) {
    return "Synchronous";
  }
  return formatPatternCategory(value);
}

function defaultPatternValue(): PatternDefinitionCreate {
  return {
    pattern_id: "",
    name: "",
    category: "Synchronous",
    description: "",
    components: [],
    flow: "",
  };
}

export function AdminPatternForm({
  mode,
  toolOptions,
  initialValue,
  isLoading,
  error,
  onSubmit,
  onCancel,
}: AdminPatternFormProps): JSX.Element {
  const [form, setForm] = useState<PatternDefinitionCreate>(defaultPatternValue());
  const [validationError, setValidationError] = useState<string>("");

  useEffect(() => {
    if (!initialValue) {
      setForm(defaultPatternValue());
      return;
    }
    setForm({
      pattern_id: initialValue.pattern_id,
      name: initialValue.name,
      category: normalizeCategory(initialValue.category),
      description: initialValue.description ?? "",
      components: initialValue.components ?? [],
      flow: initialValue.flow ?? "",
    });
  }, [initialValue]);

  function toggleComponent(component: string): void {
    setForm((current) => ({
      ...current,
      components: current.components?.includes(component)
        ? current.components.filter((entry) => entry !== component)
        : [...(current.components ?? []), component],
    }));
  }

  async function handleSubmit(): Promise<void> {
    const normalizedId = form.pattern_id.trim();
    if (!/^#\d{2}$/.test(normalizedId)) {
      setValidationError("Pattern ID must use #NN format.");
      return;
    }
    if (!form.name.trim()) {
      setValidationError("Pattern name is required.");
      return;
    }
    setValidationError("");
    await onSubmit({
      ...form,
      pattern_id: normalizedId,
      name: form.name.trim(),
      description: form.description?.trim() || undefined,
      components: form.components?.length ? form.components : undefined,
      flow: form.flow?.trim() || undefined,
    });
  }

  return (
    <section className="app-card p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="app-label">Pattern Editor</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
            {mode === "create" ? "New Pattern" : `Edit ${initialValue?.pattern_id ?? "Pattern"}`}
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
          <span className="app-label mb-2 block">Pattern ID</span>
          <input
            value={form.pattern_id}
            onChange={(event) => setForm((current) => ({ ...current, pattern_id: event.target.value }))}
            placeholder="#18"
            disabled={mode === "edit"}
            className="app-input disabled:cursor-not-allowed disabled:opacity-60"
          />
        </label>

        <label className="block">
          <span className="app-label mb-2 block">Category</span>
          <select
            value={form.category}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                category: event.target.value as PatternDefinitionCreate["category"],
              }))
            }
            className="app-input"
          >
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {formatPatternCategory(option)}
              </option>
            ))}
          </select>
        </label>

        <label className="block md:col-span-2">
          <span className="app-label mb-2 block">Name</span>
          <input
            value={form.name}
            onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            placeholder="GraphQL Federation"
            className="app-input"
          />
        </label>
      </div>

      <label className="mt-4 block">
        <span className="app-label mb-2 block">Description</span>
        <textarea
          value={form.description}
          onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
          rows={4}
          className="app-input"
        />
      </label>

      <fieldset className="mt-4">
        <legend className="app-label">OCI Components</legend>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {toolOptions.map((option) => {
            const checked = form.components?.includes(option) ?? false;
            return (
              <label
                key={option}
                className={[
                  "flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition",
                  checked
                    ? "border-[var(--color-accent)] bg-[var(--color-surface)] text-[var(--color-text-primary)]"
                    : "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text-primary)]",
                ].join(" ")}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleComponent(option)}
                  className="h-4 w-4 rounded border-[var(--color-border)] text-[var(--color-accent)] focus:ring-[var(--color-accent)]"
                />
                <span>{option}</span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <label className="mt-4 block">
        <span className="app-label mb-2 block">Flow Description</span>
        <textarea
          value={form.flow}
          onChange={(event) => setForm((current) => ({ ...current, flow: event.target.value }))}
          rows={4}
          className="app-input"
        />
      </label>

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
          {isLoading ? "Saving…" : mode === "create" ? "Create Pattern" : "Save Changes"}
        </button>
      </div>
    </section>
  );
}
