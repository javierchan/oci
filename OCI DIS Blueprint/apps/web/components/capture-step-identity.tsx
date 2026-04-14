"use client";

/* Step 1 of guided capture: identity and governance metadata. */

import type { CaptureStepProps } from "@/components/capture-wizard";

export function CaptureStepIdentity({
  form,
  updateField,
}: CaptureStepProps): JSX.Element {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Brand</span>
        <input
          value={form.brand}
          onChange={(event) => updateField("brand", event.target.value)}
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
          placeholder="Grupo / brand"
        />
      </label>
      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Business Process</span>
        <input
          value={form.business_process}
          onChange={(event) => updateField("business_process", event.target.value)}
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
          placeholder="Finance, HR, Supply Chain…"
        />
      </label>
      <label className="block md:col-span-2">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Interface Name</span>
        <input
          value={form.interface_name}
          onChange={(event) => updateField("interface_name", event.target.value)}
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
          placeholder="Descriptive integration name"
        />
      </label>
      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Interface ID</span>
        <input
          value={form.interface_id ?? ""}
          onChange={(event) => updateField("interface_id", event.target.value)}
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
          placeholder="Optional formal identifier"
        />
      </label>
      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Owner</span>
        <input
          value={form.owner ?? ""}
          onChange={(event) => updateField("owner", event.target.value)}
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
          placeholder="Business or technical owner"
        />
      </label>
      <label className="block md:col-span-2">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Description</span>
        <textarea
          value={form.description ?? ""}
          onChange={(event) => updateField("description", event.target.value)}
          rows={4}
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
          placeholder="What does this integration do?"
        />
      </label>
      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Initial Scope</span>
        <input
          value={form.initial_scope ?? ""}
          onChange={(event) => updateField("initial_scope", event.target.value)}
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-950 outline-none focus:border-sky-400"
          placeholder="Optional scope note"
        />
      </label>
    </div>
  );
}
