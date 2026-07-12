"use client";

/* Client-side trigger for project recalculation and page refresh. */

import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";
import { RefreshCw } from "lucide-react";

import { emitToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";

type RecalculateButtonProps = {
  projectId: string;
};

export function RecalculateButton({ projectId }: RecalculateButtonProps): JSX.Element {
  const router = useRouter();
  const [pending, setPending] = useState<boolean>(false);

  async function waitForCompletion(jobId: string): Promise<void> {
    for (let attempt = 0; attempt < 12; attempt += 1) {
      const job = await api.getRecalculationJob(projectId, jobId);
      if (job.status === "completed") {
        emitToast("success", "Recalculation completed. Dashboard refreshed.");
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
    emitToast("info", "Recalculation is still running. The dashboard will use the current snapshot until it finishes.");
  }

  async function handleClick(): Promise<void> {
    setPending(true);
    try {
      const job = await api.recalculate(projectId);
      emitToast("info", "Recalculation started. Waiting for the governed worker.");
      await waitForCompletion(job.job_id);
    } catch (caughtError) {
      emitToast("error", caughtError instanceof Error ? caughtError.message : "Unable to recalculate.");
    } finally {
      setPending(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={pending}
      className="app-button-primary h-10 w-[10.5rem] gap-2"
      aria-busy={pending}
    >
      <RefreshCw className={`h-4 w-4 ${pending ? "animate-spin" : ""}`} />
      {pending ? "Recalculating…" : "Recalculate"}
    </button>
  );
}
