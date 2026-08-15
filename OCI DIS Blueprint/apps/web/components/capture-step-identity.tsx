"use client";

/* Step 1 of guided capture: identity and governance metadata. */

import type { CaptureStepProps } from "@/components/capture-wizard";

export function CaptureStepIdentity({
  form,
  updateField,
}: CaptureStepProps): JSX.Element {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <p className="md:col-span-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3 text-sm leading-6 text-[var(--color-text-secondary)]">
        Start with the business identity. Brand, business process, and interface name are required because they make duplicate checks, QA, and project reporting meaningful. Formal IDs and scope notes can be added later.
      </p>
      <label className="block">
        <span className="app-label mb-2 block">Brand <span className="text-[var(--color-qa-review-text)]">required</span></span>
        <input
          value={form.brand}
          onChange={(event) => updateField("brand", event.target.value)}
          className="app-input"
          placeholder="Brand or group"
        />
      </label>
      <label className="block">
        <span className="app-label mb-2 block">Business Process <span className="text-[var(--color-qa-review-text)]">required</span></span>
        <input
          value={form.business_process}
          onChange={(event) => updateField("business_process", event.target.value)}
          className="app-input"
          placeholder="Finance, HR, Supply Chain…"
        />
      </label>
      <label className="block md:col-span-2">
        <span className="app-label mb-2 block">Interface Name <span className="text-[var(--color-qa-review-text)]">required</span></span>
        <input
          value={form.interface_name}
          onChange={(event) => updateField("interface_name", event.target.value)}
          className="app-input"
          placeholder="Descriptive integration name"
        />
      </label>
      <label className="block">
        <span className="app-label mb-2 block">Interface ID</span>
        <input
          value={form.interface_id ?? ""}
          onChange={(event) => updateField("interface_id", event.target.value)}
          className="app-input"
          placeholder="Optional formal identifier"
        />
      </label>
      <label className="block">
        <span className="app-label mb-2 block">Owner</span>
        <input
          value={form.owner ?? ""}
          onChange={(event) => updateField("owner", event.target.value)}
          className="app-input"
          placeholder="Business or technical owner"
        />
      </label>
      <label className="block md:col-span-2">
        <span className="app-label mb-2 block">Description</span>
        <textarea
          value={form.description ?? ""}
          onChange={(event) => updateField("description", event.target.value)}
          rows={4}
          className="app-input"
          placeholder="What does this integration do?"
        />
      </label>
      <label className="block">
        <span className="app-label mb-2 block">Initial Scope</span>
        <input
          value={form.initial_scope ?? ""}
          onChange={(event) => updateField("initial_scope", event.target.value)}
          className="app-input"
          placeholder="Optional scope note"
        />
      </label>
    </div>
  );
}
