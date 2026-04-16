"use client";

/* Client-side QA checklist that mirrors the backend QA readiness rules for manual capture. */

import { CheckCircle2, CircleX } from "lucide-react";

import { formatQaStatus } from "@/lib/format";
import type { ManualIntegrationCreate } from "@/lib/types";

type QaPreviewProps = {
  form: ManualIntegrationCreate;
};

type QaRule = {
  code: string;
  label: string;
  pass: boolean;
};

function buildRules(form: ManualIntegrationCreate): QaRule[] {
  return [
    { code: "MISSING_ID_FORMAL", label: "Interface ID assigned", pass: Boolean(form.interface_id) },
    { code: "INVALID_TRIGGER_TYPE", label: "Trigger type set", pass: Boolean(form.type) },
    { code: "INVALID_PATTERN", label: "OIC Pattern assigned", pass: Boolean(form.selected_pattern) },
    {
      code: "MISSING_RATIONALE",
      label: "Pattern rationale provided",
      pass: !form.selected_pattern || Boolean(form.pattern_rationale),
    },
    {
      code: "MISSING_CORE_TOOLS",
      label: "Core tools selected",
      pass: Boolean(form.core_tools && form.core_tools.length > 0),
    },
    {
      code: "MISSING_PAYLOAD",
      label: "Payload KB specified",
      pass: form.payload_per_execution_kb !== undefined,
    },
    {
      code: "TBD_UNCERTAINTY",
      label: "Uncertainty resolved",
      pass: form.uncertainty !== "TBD",
    },
  ];
}

export function QaPreview({ form }: QaPreviewProps): JSX.Element {
  const rules = buildRules(form);
  const qaStatus = rules.every((rule) => rule.pass) ? "OK" : "REVISAR";

  return (
    <section className="rounded-[1.5rem] border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-slate-500">QA Preview</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-950">Readiness before submit</h3>
        </div>
        <span
          className={[
            "inline-flex rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em]",
            qaStatus === "OK"
              ? "border-emerald-300 bg-emerald-50 text-emerald-700"
              : "border-amber-300 bg-amber-50 text-amber-700",
          ].join(" ")}
        >
          {formatQaStatus(qaStatus)}
        </span>
      </div>

      <ul className="mt-4 space-y-3">
        {rules.map((rule) => (
          <li
            key={rule.code}
            className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"
          >
            <span className="text-sm text-slate-700">{rule.label}</span>
            <span className={rule.pass ? "text-emerald-600" : "text-rose-500"}>
              {rule.pass ? <CheckCircle2 className="h-5 w-5" /> : <CircleX className="h-5 w-5" />}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
