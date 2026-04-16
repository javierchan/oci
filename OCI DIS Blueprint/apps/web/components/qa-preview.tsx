"use client";

/* Client-side QA checklist that mirrors the backend QA readiness rules for manual capture. */

import { CheckCircle2, CircleX } from "lucide-react";

import type { ManualIntegrationCreate, PatternDefinition } from "@/lib/types";

type QaPreviewProps = {
  form: ManualIntegrationCreate;
  patterns: PatternDefinition[];
};

type QaRule = {
  code: string;
  label: string;
  pass: boolean;
};

type CoverageSignal = {
  title: string;
  detail: string;
};

const VALID_TRIGGER_TYPES = new Set([
  "scheduled",
  "rest",
  "rest trigger",
  "event",
  "event trigger",
  "ftp/sftp",
  "db polling",
  "jms",
  "kafka",
  "webhook",
  "soap",
  "soap trigger",
]);

function normalizeTriggerType(value: string | undefined): string | null {
  if (!value) {
    return null;
  }
  return value.trim().toLowerCase().replace(/-/g, " ").split(/\s+/).join(" ");
}

function buildRules(form: ManualIntegrationCreate, patterns: PatternDefinition[]): QaRule[] {
  const normalizedTrigger = normalizeTriggerType(form.type);
  const selectedPattern = patterns.find((pattern) => pattern.pattern_id === form.selected_pattern) ?? null;
  return [
    {
      code: "INVALID_TRIGGER_TYPE",
      label: "Trigger type recognized",
      pass: normalizedTrigger !== null && VALID_TRIGGER_TYPES.has(normalizedTrigger),
    },
    {
      code: "INVALID_PATTERN",
      label: "OIC Pattern assigned",
      pass: Boolean(form.selected_pattern),
    },
    {
      code: "PATTERN_REFERENCE_ONLY",
      label: "Pattern is parity-ready",
      pass: !selectedPattern || selectedPattern.support.parity_ready,
    },
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

function buildCoverageSignals(form: ManualIntegrationCreate, patterns: PatternDefinition[]): CoverageSignal[] {
  const signals: CoverageSignal[] = [];
  const selectedPattern = patterns.find((pattern) => pattern.pattern_id === form.selected_pattern) ?? null;

  if (!form.interface_id) {
    signals.push({
      title: "Formal ID coverage gap",
      detail: "QA still runs, but governance coverage remains incomplete until an Interface ID is assigned.",
    });
  }

  if (form.payload_per_execution_kb === undefined) {
    signals.push({
      title: "Low-confidence forecast",
      detail: "Payload evidence is still missing, so billing estimates will remain directional after submit.",
    });
  }

  if (form.uncertainty && form.uncertainty.toUpperCase().includes("TBD")) {
    signals.push({
      title: "Workbook uncertainty preserved",
      detail: "Keep the source uncertainty visible until the owning team resolves the TBD evidence.",
    });
  }

  if (selectedPattern && !selectedPattern.support.parity_ready) {
    signals.push({
      title: "Reference-only pattern",
      detail: "This pattern stays in architect review because the current release does not yet provide pattern-specific parity sizing.",
    });
  }

  return signals;
}

export function QaPreview({ form, patterns }: QaPreviewProps): JSX.Element {
  const rules = buildRules(form, patterns);
  const coverageSignals = buildCoverageSignals(form, patterns);
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
          {qaStatus}
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

      {coverageSignals.length > 0 ? (
        <div className="mt-4 space-y-3">
          {coverageSignals.map((signal) => (
            <article
              key={signal.title}
              className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3"
            >
              <p className="text-sm font-semibold text-sky-950">{signal.title}</p>
              <p className="mt-1 text-sm text-sky-900">{signal.detail}</p>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
