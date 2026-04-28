"use client";

/* Debounced OIC sizing preview for guided manual capture. */

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { OICEstimateResponse } from "@/lib/types";

type OicEstimatePreviewProps = {
  projectId: string;
  frequency?: string;
  payloadPerExecutionKb?: number;
};

const EMPTY_ESTIMATE: OICEstimateResponse = {
  billing_msgs_per_execution: null,
  billing_msgs_per_month: null,
  peak_packs_per_hour: null,
  executions_per_day: null,
  computable: false,
};

export function OicEstimatePreview({
  projectId,
  frequency,
  payloadPerExecutionKb,
}: OicEstimatePreviewProps): JSX.Element {
  const [estimate, setEstimate] = useState<OICEstimateResponse>(EMPTY_ESTIMATE);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const showActivationHint = !frequency || payloadPerExecutionKb === undefined || payloadPerExecutionKb === null;

  useEffect(() => {
    const hasInputs = Boolean(frequency) && payloadPerExecutionKb !== undefined;
    if (!hasInputs) {
      setEstimate(EMPTY_ESTIMATE);
      setLoading(false);
      setError("");
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError("");

    const timer = window.setTimeout(() => {
      void api
        .estimateOIC(projectId, {
          frequency,
          payload_per_execution_kb: payloadPerExecutionKb,
          response_kb: 0,
        })
        .then((response) => {
          if (!cancelled) {
            setEstimate(response);
          }
        })
        .catch((caughtError: unknown) => {
          if (!cancelled) {
            setError(caughtError instanceof Error ? caughtError.message : "Unable to compute OIC preview.");
            setEstimate(EMPTY_ESTIMATE);
          }
        })
        .finally(() => {
          if (!cancelled) {
            setLoading(false);
          }
        });
    }, 400);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [frequency, payloadPerExecutionKb, projectId]);

  return (
    <section className="app-card border-[var(--color-accent)]/30 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="app-kicker">OIC Estimate</p>
          <h3 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Live preview</h3>
        </div>
        {loading ? (
          <span className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">Calculating…</span>
        ) : null}
      </div>

      {showActivationHint && !loading ? (
        <p className="py-4 text-center text-xs text-[var(--color-text-secondary)]">
          Select a <strong>Frequency</strong> and enter a <strong>Payload KB</strong> above to preview OIC billing and
          pack pressure.
        </p>
      ) : null}

      {error ? <p className="mt-4 text-sm text-rose-300">{error}</p> : null}

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {[
          {
            label: "Billing msgs / execution",
            value: formatNumber(estimate.billing_msgs_per_execution, 1),
          },
          {
            label: "Billing msgs / month",
            value: formatNumber(estimate.billing_msgs_per_month, 1),
          },
          {
            label: "Peak packs / hour",
            value: formatNumber(estimate.peak_packs_per_hour, 1),
          },
          {
            label: "Executions / day",
            value: formatNumber(estimate.executions_per_day, 2),
          },
        ].map((metric) => (
          <article
            key={metric.label}
            className="app-card-muted px-4 py-4"
          >
            <p className="text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">{metric.label}</p>
            <p className="mt-3 text-2xl font-semibold text-[var(--color-text-primary)]">
              {showActivationHint && !loading ? "—" : loading ? "…" : metric.value}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
