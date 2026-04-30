"use client";

/* Pattern create/edit form for admin governance surfaces. */

import { useEffect, useMemo, useState } from "react";

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
  "SYNCHRONOUS",
  "ASYNCHRONOUS",
  "SECURITY / PERFORMANCE",
  "RESILIENCE",
  "DATA",
  "MIGRATION",
  "DATA / DELIVERY GUARANTEES",
  "DATA / ADVANCED",
  "API DESIGN",
  "ARCHITECTURE / DATA",
  "SECURITY",
  "API DESIGN / ASYNCHRONOUS",
  "AI",
  "ARCHITECTURE",
  "ASYNCHRONOUS / API",
];

const FORM_SECTIONS = [
  { id: "pattern-identity", label: "Identity", description: "ID, name, and description" },
  { id: "pattern-components", label: "OCI Components", description: "Search and govern component coverage" },
  { id: "pattern-guidance", label: "Usage Guidance", description: "When to use, anti-patterns, and value" },
  { id: "pattern-flow", label: "Technical Flow", description: "Implementation narrative" },
] as const;

function defaultPatternValue(): PatternDefinitionCreate {
  return {
    pattern_id: "",
    name: "",
    category: "SYNCHRONOUS",
    description: "",
    oci_components: "",
    when_to_use: "",
    when_not_to_use: "",
    technical_flow: "",
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
  const [componentSearch, setComponentSearch] = useState<string>("");

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
      oci_components: initialValue.oci_components ?? "",
      when_to_use: initialValue.when_to_use ?? "",
      when_not_to_use: initialValue.when_not_to_use ?? "",
      technical_flow: initialValue.technical_flow ?? "",
      business_value: initialValue.business_value ?? "",
    });
  }, [initialValue]);

  const selectedComponents = useMemo(
    () =>
      (form.oci_components ?? "")
        .split("|")
        .map((entry) => entry.trim())
        .filter(Boolean),
    [form.oci_components],
  );
  const uniqueToolOptions = useMemo(() => Array.from(new Set(toolOptions)), [toolOptions]);
  const filteredToolOptions = useMemo(() => {
    const normalizedSearch = componentSearch.trim().toLowerCase();
    if (!normalizedSearch) {
      return uniqueToolOptions;
    }
    return uniqueToolOptions.filter((option) => option.toLowerCase().includes(normalizedSearch));
  }, [componentSearch, uniqueToolOptions]);
  const populatedFieldCount = [
    form.pattern_id,
    form.name,
    form.category,
    form.description,
    form.oci_components,
    form.when_to_use,
    form.when_not_to_use,
    form.business_value,
    form.technical_flow,
  ].filter((value) => (value ?? "").trim() !== "").length;
  const guidanceFieldCount = [
    form.when_to_use,
    form.when_not_to_use,
    form.business_value,
    form.technical_flow,
  ].filter((value) => (value ?? "").trim() !== "").length;

  function toggleComponent(component: string): void {
    const nextComponents = selectedComponents.includes(component)
      ? selectedComponents.filter((entry) => entry !== component)
      : [...selectedComponents, component];
    setForm((current) => ({
      ...current,
      oci_components: nextComponents.join(" | "),
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
      oci_components: form.oci_components?.trim() || undefined,
      when_to_use: form.when_to_use?.trim() || undefined,
      when_not_to_use: form.when_not_to_use?.trim() || undefined,
      technical_flow: form.technical_flow?.trim() || undefined,
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

      <div className="mt-6 xl:grid xl:grid-cols-[15rem_minmax(0,1fr)] xl:gap-5">
        <aside className="mb-5 xl:mb-0">
          <div className="space-y-4 xl:sticky xl:top-6">
            <section className="app-card-muted p-4">
              <p className="app-label">Editor Summary</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
                <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
                  <p className="app-label">Sections</p>
                  <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{FORM_SECTIONS.length}</p>
                </div>
                <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
                  <p className="app-label">Fields Filled</p>
                  <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{populatedFieldCount}</p>
                </div>
                <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
                  <p className="app-label">Components</p>
                  <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{selectedComponents.length}</p>
                </div>
              </div>
              <p className="mt-4 text-sm leading-6 text-[var(--color-text-secondary)]">
                {guidanceFieldCount > 0
                  ? "Guidance text is already in progress. Use the jump list to move between sections without losing context."
                  : "Start with identity and OCI components, then fill the usage guidance and flow once the pattern shape is clear."}
              </p>
            </section>

            <nav className="app-card-muted p-3" aria-label="Pattern editor sections">
              <p className="app-label px-2 pt-1">Jump to Section</p>
              <div className="mt-3 flex gap-2 overflow-x-auto pb-1 xl:flex-col xl:overflow-visible">
                {FORM_SECTIONS.map((section) => (
                  <a
                    key={section.id}
                    href={`#${section.id}`}
                    className="min-w-[12rem] rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 text-left transition hover:border-[var(--color-accent)] hover:bg-[var(--color-surface-2)] xl:min-w-0"
                  >
                    <span className="block text-sm font-semibold text-[var(--color-text-primary)]">{section.label}</span>
                    <span className="mt-1 block text-xs leading-5 text-[var(--color-text-secondary)]">{section.description}</span>
                  </a>
                ))}
              </div>
            </nav>
          </div>
        </aside>

        <div className="space-y-5">
        <section id="pattern-identity" className="scroll-mt-24 app-card-muted p-5">
          <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="app-label">Identity</p>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
                Define the governed pattern identity and how it should be described across capture, QA, and exports.
              </p>
            </div>
            <span className="app-theme-chip">
              {mode === "create" ? "New governance entry" : "Editing existing pattern"}
            </span>
          </div>
          <div className="mt-5 grid gap-4 md:grid-cols-2">
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
        </section>

        <section id="pattern-components" className="scroll-mt-24 app-card-muted p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="app-label">OCI Components</p>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
                Select the governed components that define the pattern. Search narrows the list without altering the saved pipe-separated value.
              </p>
            </div>
            <span className="app-theme-chip">{selectedComponents.length} selected</span>
          </div>

          <label className="mt-4 block">
            <span className="app-label mb-2 block">Filter Components</span>
            <input
              value={componentSearch}
              onChange={(event) => setComponentSearch(event.target.value)}
              placeholder="Search OCI API Gateway, Functions, Streaming…"
              className="app-input"
            />
          </label>

          {selectedComponents.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {selectedComponents.map((component) => (
                <span key={component} className="app-theme-chip">
                  {component}
                </span>
              ))}
            </div>
          ) : null}

          <fieldset className="mt-4">
            <legend className="app-label">Component Library</legend>
            <div className="mt-3 rounded-[1.5rem] border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
              {filteredToolOptions.length === 0 ? (
                <div className="px-3 py-6 text-sm text-[var(--color-text-secondary)]">
                  No OCI components match the current search.
                </div>
              ) : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {filteredToolOptions.map((option) => {
                    const checked = selectedComponents.includes(option);
                    return (
                      <label
                        key={option}
                        className={[
                          "flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition",
                          checked
                            ? "border-[var(--color-accent)] bg-[var(--color-surface-2)] text-[var(--color-text-primary)]"
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
              )}
            </div>
          </fieldset>

          <label className="mt-4 block">
            <span className="app-label mb-2 block">OCI Components (pipe-separated)</span>
            <textarea
              value={form.oci_components}
              onChange={(event) => setForm((current) => ({ ...current, oci_components: event.target.value }))}
              rows={5}
              className="app-input"
            />
          </label>
        </section>

        <section id="pattern-guidance" className="scroll-mt-24 app-card-muted p-5">
          <p className="app-label">Usage Guidance</p>
          <div className="mt-4 grid gap-4 xl:grid-cols-3">
            <label className="block xl:col-span-1">
              <span className="app-label mb-2 block">When to Use</span>
              <textarea
                value={form.when_to_use}
                onChange={(event) => setForm((current) => ({ ...current, when_to_use: event.target.value }))}
                rows={5}
                className="app-input"
              />
            </label>

            <label className="block xl:col-span-1">
              <span className="app-label mb-2 block">When Not to Use / Anti-Pattern</span>
              <textarea
                value={form.when_not_to_use}
                onChange={(event) => setForm((current) => ({ ...current, when_not_to_use: event.target.value }))}
                rows={5}
                className="app-input"
              />
            </label>

            <label className="block xl:col-span-1">
              <span className="app-label mb-2 block">Business Value</span>
              <textarea
                value={form.business_value}
                onChange={(event) => setForm((current) => ({ ...current, business_value: event.target.value }))}
                rows={5}
                className="app-input"
              />
            </label>
          </div>
        </section>

        <section id="pattern-flow" className="scroll-mt-24 app-card-muted p-5">
          <p className="app-label">Technical Flow</p>
          <label className="mt-4 block">
            <span className="app-label mb-2 block">Implementation Narrative</span>
            <textarea
              value={form.technical_flow}
              onChange={(event) => setForm((current) => ({ ...current, technical_flow: event.target.value }))}
              rows={5}
              className="app-input"
            />
          </label>
        </section>
        </div>
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
          {isLoading ? "Saving…" : mode === "create" ? "Create Pattern" : "Save Changes"}
        </button>
      </div>
    </section>
  );
}
