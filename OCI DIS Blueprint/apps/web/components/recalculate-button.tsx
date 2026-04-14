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

  async function handleClick(): Promise<void> {
    setPending(true);
    setError("");
    try {
      await api.recalculate(projectId);
      startTransition(() => {
        router.refresh();
      });
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
        className="inline-flex items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {pending ? "Running…" : "Run Recalculation"}
      </button>
      {error ? <p className="text-sm text-rose-600">{error}</p> : null}
    </div>
  );
}
