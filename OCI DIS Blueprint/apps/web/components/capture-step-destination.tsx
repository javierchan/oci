"use client";

/* Step 3 of guided capture: destination application details and duplicate guardrails. */

import type { Integration } from "@/lib/types";
import { SystemAutocomplete } from "@/components/system-autocomplete";
import type { CaptureStepProps } from "@/components/capture-wizard";

type CaptureStepDestinationProps = CaptureStepProps & {
  duplicates: Integration[];
  duplicateLoading: boolean;
};

export function CaptureStepDestination({
  projectId,
  form,
  updateField,
  duplicates,
  duplicateLoading,
}: CaptureStepDestinationProps): JSX.Element {
  return (
    <div className="space-y-5">
      <div className="grid gap-5 md:grid-cols-2">
        <SystemAutocomplete
          projectId={projectId}
          label="Destination System"
          value={form.destination_system}
          onChange={(value) => updateField("destination_system", value)}
          placeholder="Oracle, WMS, Data Lake…"
        />
        <label className="block">
          <span className="app-label mb-2 block">Destination Technology</span>
          <input
            value={form.destination_technology ?? ""}
            onChange={(event) => updateField("destination_technology", event.target.value)}
            className="app-input"
            placeholder="REST, ATP, SOAP…"
          />
        </label>
        <label className="block">
          <span className="app-label mb-2 block">Destination Owner</span>
          <input
            value={form.destination_owner ?? ""}
            onChange={(event) => updateField("destination_owner", event.target.value)}
            className="app-input"
            placeholder="Receiving team or owner"
          />
        </label>
      </div>

      <section
        className={[
          "rounded-[1.5rem] border p-5",
          duplicates.length > 0
            ? "border-amber-300 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30"
            : "border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950/30",
        ].join(" ")}
      >
        <p className="app-label">Duplicate Check</p>
        {duplicateLoading ? (
          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">Checking existing integrations…</p>
        ) : duplicates.length > 0 ? (
          <div className="mt-3 space-y-3">
            <p className="text-sm text-amber-900 dark:text-amber-200">
              Matching integrations already exist for this source, destination, and business process. You can still continue if this is intentionally distinct.
            </p>
            <ul className="space-y-2">
              {duplicates.map((integration) => (
                <li
                  key={integration.id}
                  className="rounded-2xl border border-amber-200 bg-[var(--color-surface)] px-4 py-3 text-sm text-[var(--color-text-secondary)] dark:border-amber-900"
                >
                  {integration.interface_name ?? integration.interface_id ?? integration.id}
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="mt-3 text-sm text-emerald-900 dark:text-emerald-200">
            No duplicate matches were found for the current source, destination, and business process.
          </p>
        )}
      </section>
    </div>
  );
}
