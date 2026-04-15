"use client";

/* Step 2 of guided capture: source application details with autocomplete. */

import { SystemAutocomplete } from "@/components/system-autocomplete";
import type { CaptureStepProps } from "@/components/capture-wizard";

export function CaptureStepSource({
  projectId,
  form,
  updateField,
}: CaptureStepProps): JSX.Element {
  return (
    <div className="grid gap-5 md:grid-cols-2">
      <SystemAutocomplete
        projectId={projectId}
        label="Source System"
        value={form.source_system}
        onChange={(value) => updateField("source_system", value)}
        placeholder="SAP, Salesforce, Legacy ERP…"
      />
      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Source Technology</span>
        <input
          value={form.source_technology ?? ""}
          onChange={(event) => updateField("source_technology", event.target.value)}
          className="app-input"
          placeholder="REST, JDBC, FTP, SOAP…"
        />
      </label>
      <label className="block md:col-span-2">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Source API Reference</span>
        <input
          value={form.source_api_reference ?? ""}
          onChange={(event) => updateField("source_api_reference", event.target.value)}
          className="app-input"
          placeholder="/api/v1/orders or reference URL"
        />
      </label>
      <label className="block">
        <span className="mb-2 block text-xs uppercase tracking-[0.25em] text-slate-500">Source Owner</span>
        <input
          value={form.source_owner ?? ""}
          onChange={(event) => updateField("source_owner", event.target.value)}
          className="app-input"
          placeholder="Team or owner"
        />
      </label>
    </div>
  );
}
