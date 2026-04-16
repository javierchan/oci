"use client";

/* Pattern create/edit form for admin governance surfaces. */

import { useEffect, useState } from "react";

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

const CATEGORY_SUGGESTIONS = [
  "SÍNCRONO",
  "ASÍNCRONO",
  "SÍNCRONO + ASÍNCRONO",
  "SEGURIDAD / PERFORMANCE",
  "RESILIENCIA",
  "DATOS",
  "MIGRACIÓN",
  "DATOS / GARANTÍAS",
  "DATOS / AVANZADO",
  "API DESIGN",
  "ARQUITECTURA / DATOS",
  "SEGURIDAD",
  "API DESIGN / ASÍNCRONO",
  "IA / INTELIGENCIA ARTIFICIAL",
  "ARQUITECTURA",
  "ASÍNCRONO / API",
];

function defaultPatternValue(): PatternDefinitionCreate {
  return {
    pattern_id: "",
    name: "",
    category: "SÍNCRONO",
    description: "",
    components: [],
    component_details: "",
    when_to_use: "",
    when_not_to_use: "",
    flow: "",
    business_value: "",
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
      category: initialValue.category,
      description: initialValue.description ?? "",
      components: initialValue.components ?? [],
      component_details: initialValue.component_details ?? "",
      when_to_use: initialValue.when_to_use ?? "",
      when_not_to_use: initialValue.when_not_to_use ?? "",
      flow: initialValue.flow ?? "",
      business_value: initialValue.business_value ?? "",
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
      component_details: form.component_details?.trim() || undefined,
      when_to_use: form.when_to_use?.trim() || undefined,
      when_not_to_use: form.when_not_to_use?.trim() || undefined,
      flow: form.flow?.trim() || undefined,
      business_value: form.business_value?.trim() || undefined,
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
          <input
            value={form.category}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                category: event.target.value,
              }))
            }
            list="pattern-category-suggestions"
            className="app-input"
          />
          <datalist id="pattern-category-suggestions">
            {CATEGORY_SUGGESTIONS.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
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
        <span className="app-label mb-2 block">Component Details</span>
        <textarea
          value={form.component_details}
          onChange={(event) => setForm((current) => ({ ...current, component_details: event.target.value }))}
          rows={5}
          className="app-input"
        />
      </label>

      <label className="mt-4 block">
        <span className="app-label mb-2 block">When to Use</span>
        <textarea
          value={form.when_to_use}
          onChange={(event) => setForm((current) => ({ ...current, when_to_use: event.target.value }))}
          rows={4}
          className="app-input"
        />
      </label>

      <label className="mt-4 block">
        <span className="app-label mb-2 block">When Not to Use / Anti-Pattern</span>
        <textarea
          value={form.when_not_to_use}
          onChange={(event) => setForm((current) => ({ ...current, when_not_to_use: event.target.value }))}
          rows={5}
          className="app-input"
        />
      </label>

      <label className="mt-4 block">
        <span className="app-label mb-2 block">Flow Description</span>
        <textarea
          value={form.flow}
          onChange={(event) => setForm((current) => ({ ...current, flow: event.target.value }))}
          rows={4}
          className="app-input"
        />
      </label>

      <label className="mt-4 block">
        <span className="app-label mb-2 block">Business Value</span>
        <textarea
          value={form.business_value}
          onChange={(event) => setForm((current) => ({ ...current, business_value: event.target.value }))}
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
