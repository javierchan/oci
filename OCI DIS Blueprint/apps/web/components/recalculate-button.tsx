"use client";

/* Client-side trigger for project recalculation and page refresh. */

import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";

import { api } from "@/lib/api";

type RecalculateButtonProps = {
  projectId: string;
};

export function RecalculateButton({ projectId }: RecalculateButtonProps): JSX.Element {
  const router = useRouter();
  const [pending, setPending] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<string>("");

  async function waitForCompletion(jobId: string): Promise<void> {
    for (let attempt = 0; attempt < 12; attempt += 1) {
      const job = await api.getRecalculationJob(projectId, jobId);
      if (job.status === "completed") {
        setStatusMessage("Recalculation completed. Dashboard refreshed.");
        startTransition(() => {
          router.refresh();
        });
        return;
      }
      if (job.status === "failed") {
        throw new Error("Recalculation failed in the background worker.");
      }
      await new Promise((resolve) => {
        window.setTimeout(resolve, 1000);
      });
    }
    setStatusMessage("Recalculation queued. Refresh in a moment to load the new snapshot.");
  }

  async function handleClick(): Promise<void> {
    setPending(true);
    setError("");
    setStatusMessage("");
    try {
      const job = await api.recalculate(projectId);
      setStatusMessage("Recalculation queued. Waiting for the worker to finish...");
      await waitForCompletion(job.job_id);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to recalculate.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <button
        type="button"
        onClick={handleClick}
        disabled={pending}
        className="app-button-primary"
      >
        {pending ? "Queueing…" : "Run Recalculation"}
      </button>
      {statusMessage ? <p className="text-sm text-emerald-600">{statusMessage}</p> : null}
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
    </div>
  );
}
