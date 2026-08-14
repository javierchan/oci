"use client";

import { Compass, SlidersHorizontal } from "lucide-react";
import { useEffect, useState } from "react";

export type ExperienceMode = "guided" | "expert";

const STORAGE_KEY = "oci-dis-experience-mode";

function applyMode(mode: ExperienceMode): void {
  document.documentElement.dataset.experienceMode = mode;
  window.localStorage.setItem(STORAGE_KEY, mode);
}

export function ExperienceModeToggle(): JSX.Element {
  const [mode, setMode] = useState<ExperienceMode>("expert");

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    const next: ExperienceMode = saved === "guided" ? "guided" : "expert";
    setMode(next);
    applyMode(next);
  }, []);

  return (
    <div className="mt-3 border-t border-[var(--color-border)] pt-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">Workspace mode</p>
      <div className="mt-2 grid grid-cols-2 gap-1 rounded-lg bg-[var(--color-surface-3)] p-1" role="group" aria-label="Workspace mode">
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold transition ${mode === "guided" ? "bg-[var(--color-accent)] text-white shadow-sm" : "text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)]"}`}
          aria-pressed={mode === "guided"}
          onClick={() => { setMode("guided"); applyMode("guided"); }}
          title="Show the recommended sequence and concise explanations"
        >
          <Compass className="h-3.5 w-3.5" /> Guided
        </button>
        <button
          type="button"
          className={`inline-flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold transition ${mode === "expert" ? "bg-[var(--color-accent)] text-white shadow-sm" : "text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)]"}`}
          aria-pressed={mode === "expert"}
          onClick={() => { setMode("expert"); applyMode("expert"); }}
          title="Show the complete architecture workspace"
        >
          <SlidersHorizontal className="h-3.5 w-3.5" /> Expert
        </button>
      </div>
    </div>
  );
}
