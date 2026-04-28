"use client";

/* Step 5 of guided capture: final review summary before persistence. */

import type { Integration } from "@/lib/types";
import type { CaptureStepProps } from "@/components/capture-wizard";

type CaptureStepReviewProps = CaptureStepProps & {
  duplicates: Integration[];
};

function stringifyValue(value: string | number | string[] | undefined): string {
  if (Array.isArray(value)) {
    return value.length > 0 ? value.join(", ") : "—";
  }
  if (value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

export function CaptureStepReview({
  form,
  duplicates,
}: CaptureStepReviewProps): JSX.Element {
  const sections = [
    {
      title: "Identity",
      rows: [
        ["Brand", form.brand],
        ["Business Process", form.business_process],
        ["Interface Name", form.interface_name],
        ["Interface ID", form.interface_id],
        ["Owner", form.owner],
      ] as Array<[string, string | undefined]>,
    },
    {
      title: "Topology",
      rows: [
        ["Source System", form.source_system],
        ["Destination System", form.destination_system],
        ["Source Technology", form.source_technology],
        ["Destination Technology", form.destination_technology],
      ] as Array<[string, string | undefined]>,
    },
    {
      title: "Technical",
      rows: [
        ["Trigger Type", form.type],
        ["Frequency", form.frequency],
        [
          "Payload per Execution",
          form.payload_per_execution_kb !== undefined
            ? `${form.payload_per_execution_kb} KB`
            : undefined,
        ],
        ["Complexity", form.complexity],
        ["Pattern", form.selected_pattern],
        ["Core Tools", stringifyValue(form.core_tools)],
      ] as Array<[string, string | undefined]>,
    },
  ];

  return (
    <div className="space-y-6">
      <section className="app-card p-5">
        <p className="app-label">Review</p>
        <h3 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Ready to capture</h3>
        <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
          The wizard will create an immutable source row, a governed catalog integration, and a manual capture audit event.
        </p>
      </section>

      <div className="grid gap-5 xl:grid-cols-3">
        {sections.map((section) => (
          <section key={section.title} className="app-card p-5">
            <p className="app-label">{section.title}</p>
            <dl className="mt-4 space-y-3">
              {section.rows.map(([label, value]) => (
                <div key={label} className="app-card-muted px-4 py-3">
                  <dt className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">{label}</dt>
                  <dd className="mt-2 text-sm font-medium text-[var(--color-text-primary)]">{stringifyValue(value)}</dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>

      {duplicates.length > 0 ? (
        <section className="rounded-[1.5rem] border border-amber-300 bg-amber-50 p-5 dark:border-amber-900 dark:bg-amber-950/30">
          <p className="text-xs uppercase tracking-[0.25em] text-amber-700 dark:text-amber-300">Duplicate Warning</p>
          <p className="mt-3 text-sm leading-6 text-amber-900 dark:text-amber-200">
            Existing integrations with the same source, destination, and business process were found. Confirm this capture is intentionally new before submitting.
          </p>
        </section>
      ) : null}
    </div>
  );
}
